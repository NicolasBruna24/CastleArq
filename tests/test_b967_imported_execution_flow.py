"""End-to-end test: imported GGUF artifact through resolution, evaluation,
admission, and execution up to a simulated runner."""

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq.compatibility_domain import CheckStatus
from castlearq.evaluate_compatibility import (
    EvaluateCompatibilityDependencies,
    evaluate_model_compatibility,
    to_admission,
)
from castlearq.execution import (
    ArtifactExecutionPreflight,
    ExecutionResult,
    ExecutionTarget,
)
from castlearq.importing import ImportStatus, LocalArtifactImporter
from castlearq.model_store import ModelStore
from castlearq.observation_knowledge import IntegrationResult
from castlearq.resolver import (
    ModelArtifactResolver,
    ResolvedModelArtifact,
)
from castlearq.runtimes import (
    PromptInputMode,
    RuntimeCapability,
)
from castlearq.execute_model import (
    EvaluationAdmission,
    ExecuteAdmissionDeniedError,
    ExecuteModelDependencies,
    execute_model,
)
from castlearq.runner import ModelRunner


def _gguf(entries=(), *, version=3, magic=b"GGUF"):
    data = bytearray(magic + struct.pack("<IQQ", version, 0, len(entries)))
    for key, value in entries:
        raw = value.encode("utf-8")
        data.extend(struct.pack("<Q", len(key.encode("utf-8"))))
        data.extend(key.encode("utf-8"))
        data.extend(struct.pack("<I", 8))
        data.extend(struct.pack("<Q", len(raw)))
        data.extend(raw)
    return bytes(data)


MODEL = _gguf((("general.architecture", "qwen2"),))


class ImportedExecutionFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(self.root / "models")
        self.importer = LocalArtifactImporter(self.store)
        self.sources = self.root / "sources"
        self.sources.mkdir()

    def _write(self, name, data=MODEL):
        path = self.sources / name
        path.write_bytes(data)
        return path

    def _import_artifact(self, label="qwen-3-8-27b"):
        source = self._write(f"{label}.gguf")
        result = self.importer.import_artifact(source, label=label)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertIsNotNone(result.content_id)
        self.assertIsNotNone(result.artifact)
        return result

    def _capability(self):
        return RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/fake/llama",
            version="v1",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
        )

    # ------------------------------------------------------------------
    # 1. Resolution
    # ------------------------------------------------------------------

    def test_imported_artifact_resolves_by_label(self):
        self._import_artifact("qwen-3-8-27b")

        resolver = ModelArtifactResolver(self.store)
        resolved = resolver.resolve("qwen-3-8-27b")

        self.assertIsInstance(resolved, ResolvedModelArtifact)
        self.assertTrue(resolved.imported)
        self.assertIsNone(resolved.model.id)
        self.assertEqual(resolved.model.name, "qwen-3-8-27b")
        self.assertIsNotNone(resolved.path)
        self.assertTrue(resolved.path.is_file())

    # ------------------------------------------------------------------
    # 2. Evaluation + admission
    # ------------------------------------------------------------------

    def test_imported_artifact_admits_via_evaluation(self):
        result = self._import_artifact("qwen-3-8-27b")

        entries = self.store.list_artifacts()
        self.assertEqual(len(entries), 1)
        stored = entries[0]
        self.assertIsNotNone(stored.artifact)
        self.assertEqual(stored.artifact.content_id, result.content_id)

        capability = self._capability()

        def evaluate_fn(**_kwargs):
            strict_result = mock.Mock()
            strict_result.status = "insufficient_evidence"
            check = mock.Mock()
            check.name = "artifact-model identity"
            check.status = CheckStatus.UNKNOWN
            strict_result.checks = (check,)
            evaluation = mock.Mock()
            evaluation.result = strict_result
            return evaluation

        eval_result = evaluate_model_compatibility(
            "qwen-3-8-27b",
            dependencies=EvaluateCompatibilityDependencies(
                model_store=self.store,
                models=(),
                capability=capability,
                integrate_fn=lambda: IntegrationResult(),
                evaluate_fn=evaluate_fn,
            ),
        )

        self.assertEqual(eval_result.status, "evaluated")
        self.assertTrue(eval_result.imported)

        admission = to_admission(eval_result)
        self.assertEqual(admission.status, "evaluated")
        self.assertEqual(admission.verdict, "compatible")

    # ------------------------------------------------------------------
    # 3. Execution reaching a simulated runner
    # ------------------------------------------------------------------

    def test_imported_artifact_executes_with_admission(self):
        result = self._import_artifact("qwen-3-8-27b")
        capability = self._capability()
        admission = EvaluationAdmission(status="evaluated", verdict="compatible")

        runner = mock.Mock(spec=ModelRunner)
        runner.run.return_value = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            error=None,
        )

        compatibility = mock.Mock()
        compatibility.recommended_runtime = "llama.cpp"
        compatibility.recommended_backend = "CPU"
        compatibility.warnings = ()

        selector = mock.Mock()
        selection = mock.Mock()
        selection.target = ExecutionTarget(runtime="llama.cpp", backend="CPU")
        selection.warnings = ()
        selector.select.return_value = selection

        deps = ExecuteModelDependencies(
            model_store=self.store,
            models=(),
            capability_provider=lambda: capability,
            compatibility_provider=lambda model, cap: compatibility,
            preflight_factory=ArtifactExecutionPreflight,
            selector=selector,
            runner=runner,
        )

        exec_result = execute_model(
            "qwen-3-8-27b",
            "Hello, world!",
            admission=admission,
            dependencies=deps,
        )

        self.assertTrue(exec_result.success)
        runner.run.assert_called_once()
        call_args = runner.run.call_args
        self.assertEqual(len(call_args.args), 3)
        _artifact_arg, target_arg, request_arg = call_args.args
        self.assertEqual(
            target_arg, ExecutionTarget(runtime="llama.cpp", backend="CPU")
        )
        self.assertEqual(request_arg.prompt, "Hello, world!")

    # ------------------------------------------------------------------
    # 4. Negative: admission absent → denied
    # ------------------------------------------------------------------

    def test_execution_without_admission_is_denied(self):
        self._import_artifact("qwen-3-8-27b")
        capability = self._capability()

        deps = ExecuteModelDependencies(
            model_store=self.store,
            models=(),
            capability_provider=lambda: capability,
        )

        with self.assertRaises(ExecuteAdmissionDeniedError):
            execute_model(
                "qwen-3-8-27b",
                "Hello, world!",
                admission=None,
                dependencies=deps,
            )


if __name__ == "__main__":
    unittest.main()
