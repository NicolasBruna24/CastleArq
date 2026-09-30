# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""B9.67 stage 3: imported artifacts traverse the existing execute pipeline.

Everything is a double: capability, compatibility, selector and ModelRunner. No
llama.cpp runs and no real hardware is probed. The point is that an imported
artifact reaches the runner through the *same* gates a catalog artifact does.
"""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execute_model import (
    EvaluationAdmission,
    ExecuteModelDependencies,
    ExecutePreparationError,
    execute_model,
)
from app.execution import (
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
    PreflightErrorCode,
)
from app.importing import ImportStatus, LocalArtifactImporter
from app.model_catalog import get_catalog
from app.model_store import ModelStore
from app.models import ArtifactSpec, ModelSpec
from app.resolver import ModelArtifactResolver
from app.runner import ModelRunner
from app.runtimes import PromptInputMode, RuntimeCapability
from app.selection import RuntimeSelection, RuntimeSelectionError, SelectionErrorCode


def _gguf(architecture="qwen2") -> bytes:
    """Minimal GGUF the existing reader accepts."""
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    key = b"general.architecture"
    raw = architecture.encode("utf-8")
    data += struct.pack("<Q", len(key)) + key
    data += struct.pack("<I", 8)
    data += struct.pack("<Q", len(raw)) + raw
    return bytes(data)


MODEL = _gguf()


def _capability(**overrides):
    base = dict(
        name="llama.cpp CLI",
        executable_path="/usr/bin/fake",
        version="v1",
        supported_formats=("GGUF",),
        supported_backends=("CPU",),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        reason=None,
        compatibility_names=("llama.cpp / llama.app",),
    )
    base.update(overrides)
    return RuntimeCapability(**base)


def _compat(model, status=CompatibilityStatus.MARGINAL, backend="CPU", **over):
    base = dict(
        model=model,
        status=status,
        score=0,
        reasons=("memory not estimated",),
        # B9.66: a tolerated UNKNOWN is surfaced as a warning, never as a
        # silent pass. The pipeline propagates `warnings`, not `reasons`.
        warnings=("Memory requirement is not estimated for this imported "
                  "artifact; no memory sufficiency was established.",),
        estimated_memory_bytes=None,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime="llama.cpp / llama.app",
        recommended_backend=backend,
    )
    base.update(over)
    return CompatibilityResult(**base)


def _target(backend="CPU"):
    return ExecutionTarget(runtime="llama.cpp / llama.app", backend=backend)


class _RecordingRunner(ModelRunner):
    """Captures exactly what the pipeline hands to the runner."""

    def __init__(self):
        self.calls = []

    def run(self, artifact, target, request):
        self.calls.append((artifact, target, request))
        return ExecutionResult(True, 0, "OUT", "")


class _RecordingSelector:
    def __init__(self, target=None, error=None):
        self.target = target or _target()
        self.error = error
        self.calls = []

    def select(self, compatibility, capability, artifact):
        self.calls.append((compatibility, capability, artifact))
        if self.error is not None:
            raise self.error
        return RuntimeSelection(target=self.target, warnings=())



class _ExecutionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(self.root / "models")
        self.importer = LocalArtifactImporter(self.store)
        self.external = self.root / "external"
        self.external.mkdir()
        self.runner = _RecordingRunner()
        self.selector = _RecordingSelector()
        self.compat_calls = []

    def _source(self, name="local.gguf", data=MODEL):
        path = self.external / name
        path.write_bytes(data)
        return path

    def _import(self, name="local.gguf", data=MODEL, label="Local"):
        result = self.importer.import_artifact(self._source(name, data), label=label)
        self.assertEqual(result.status, ImportStatus.IMPORTED, result.error)
        return result

    def _compat_provider(self, factory=None):
        def provider(model, capability):
            self.compat_calls.append(model)
            return (factory or _compat)(model)
        return provider

    def _deps(self, compat=None, selector=None, **overrides):
        base = dict(
            model_store=self.store,
            # The real catalog is passed through: a catalog artifact must keep
            # resolving by its catalog id exactly as before stage 3.
            models=get_catalog(),
            capability_provider=_capability,
            compatibility_provider=self._compat_provider(compat),
            selector=selector if selector is not None else self.selector,
            runner=self.runner,
        )
        base.update(overrides)
        return ExecuteModelDependencies(**base)

    def _seed_catalog(self, filename="catalog.gguf"):
        model = get_catalog()[0]
        artifact = ArtifactSpec(
            model_id=model.model_id, source="huggingface", repository="owner/repo",
            filename=filename, format="GGUF", quantization="Q4_K_M",
        )
        manifest = self.store.save_manifest(artifact)
        (manifest.parent / filename).write_bytes(b"catalog")
        return artifact


class ImportedHappyPathTests(_ExecutionCase):
    def test_imported_artifact_reaches_the_runner(self):
        self._import()
        result = execute_model("Local", "hello", dependencies=self._deps())
        self.assertTrue(result.success)
        self.assertEqual(len(self.runner.calls), 1)

    def test_runner_receives_the_managed_path(self):
        imported = self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        artifact, _, _ = self.runner.calls[0]
        self.assertEqual(artifact.path, imported.destination)

    def test_runner_path_is_inside_the_model_store(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        artifact, _, _ = self.runner.calls[0]
        self.assertTrue(str(artifact.path).startswith(str(self.store.root)))

    def test_runner_path_matches_the_resolver_path(self):
        self._import()
        resolved = ModelArtifactResolver(self.store, models=()).resolve("Local")
        execute_model("Local", "hello", dependencies=self._deps())
        artifact, _, _ = self.runner.calls[0]
        self.assertEqual(artifact.path, resolved.path)

    def test_runner_receives_the_prompt(self):
        self._import()
        execute_model("Local", "hola", dependencies=self._deps())
        _, _, request = self.runner.calls[0]
        self.assertEqual(request.prompt, "hola")

    def test_runner_receives_the_selected_target(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        _, target, _ = self.runner.calls[0]
        self.assertEqual(target.backend, "CPU")

    def test_managed_file_is_the_one_executed(self):
        imported = self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        artifact, _, _ = self.runner.calls[0]
        self.assertEqual(artifact.path.read_bytes(), MODEL)
        self.assertEqual(artifact.artifact.content_id, imported.content_id)

    def test_imported_flag_remains_available(self):
        self._import()
        resolved = ModelArtifactResolver(self.store, models=()).resolve("Local")
        self.assertTrue(resolved.imported)

    def test_model_id_stays_none_throughout(self):
        self._import()
        resolved = ModelArtifactResolver(self.store, models=()).resolve("Local")
        self.assertIsNone(resolved.model.id)
        execute_model("Local", "hello", dependencies=self._deps())
        self.assertIsNone(self.compat_calls[0].id)

    def test_no_identity_laundering_to_allow_execution(self):
        self._import(label="Local")
        resolved = ModelArtifactResolver(self.store, models=()).resolve("Local")
        self.assertEqual(resolved.model.name, resolved.artifact.model_id)
        self.assertIsNone(resolved.model.id)
        execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 1)


class CatalogRegressionTests(_ExecutionCase):
    def test_catalog_artifact_still_executes(self):
        artifact = self._seed_catalog()
        result = execute_model(artifact.model_id, "hello", dependencies=self._deps())
        self.assertTrue(result.success)
        self.assertEqual(len(self.runner.calls), 1)

    def test_catalog_runner_path_is_the_managed_file(self):
        artifact = self._seed_catalog()
        execute_model(artifact.model_id, "hello", dependencies=self._deps())
        managed, _, _ = self.runner.calls[0]
        self.assertTrue(str(managed.path).startswith(str(self.store.root)))
        self.assertEqual(managed.artifact, artifact)

    def test_catalog_compatibility_receives_the_real_id(self):
        artifact = self._seed_catalog()
        execute_model(artifact.model_id, "hello", dependencies=self._deps())
        self.assertEqual(self.compat_calls[0].id, artifact.model_id)

    def test_catalog_and_imported_use_the_same_pipeline(self):
        artifact = self._seed_catalog()
        self._import(label="Local")
        execute_model(artifact.model_id, "a", dependencies=self._deps())
        execute_model("Local", "b", dependencies=self._deps())
        self.assertEqual(len(self.selector.calls), 2)
        self.assertEqual(len(self.runner.calls), 2)


class ExternalPathTests(_ExecutionCase):
    def test_external_source_path_never_reaches_the_runner(self):
        source = self._source("original.gguf")
        self.importer.import_artifact(source, label="Local")
        resolved = ModelArtifactResolver(self.store, models=()).resolve("Local")
        self.assertNotEqual(resolved.path, source)
        execute_model("Local", "hello", dependencies=self._deps())
        artifact, _, _ = self.runner.calls[0]
        self.assertNotEqual(artifact.path, source)
        self.assertNotEqual(artifact.path.resolve(), source.resolve())

    def test_pipeline_still_works_after_the_original_is_deleted(self):
        source = self._source("original.gguf")
        self.importer.import_artifact(source, label="Local")
        source.unlink()
        result = execute_model("Local", "hello", dependencies=self._deps())
        self.assertTrue(result.success)
        artifact, _, _ = self.runner.calls[0]
        self.assertTrue(artifact.path.is_file())
        self.assertTrue(str(artifact.path).startswith(str(self.store.root)))

    def test_external_path_is_not_a_valid_model_id(self):
        self._import()
        with self.assertRaises(ExecutePreparationError):
            execute_model(
                str(self.external / "original.gguf"), "hello",
                dependencies=self._deps(),
            )
        self.assertEqual(len(self.runner.calls), 0)

    def test_external_path_does_not_trigger_an_import(self):
        self._source("loose.gguf")
        with self.assertRaises(ExecutePreparationError):
            execute_model(
                str(self.external / "loose.gguf"), "hello",
                dependencies=self._deps(),
            )
        self.assertEqual(self.store.list_artifacts(), [])
        self.assertEqual(len(self.runner.calls), 0)


class AdmissionTests(_ExecutionCase):
    def test_memory_unknown_imported_passes_as_marginal(self):
        self._import()
        result = execute_model("Local", "hello", dependencies=self._deps())
        self.assertTrue(result.success)
        # MARGINAL carries its reason forward as a warning, never as a block.
        self.assertTrue(any("memory" in w.lower() for w in result.warnings))

    def test_marginal_is_not_treated_as_incompatible(self):
        self._import()
        result = execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 1)
        self.assertFalse(result.exit_code)

    def test_incompatible_blocks_before_the_runner(self):
        self._import()
        deps = self._deps(
            compat=lambda model: _compat(model, status=CompatibilityStatus.INCOMPATIBLE)
        )
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=deps)
        self.assertEqual(len(self.runner.calls), 0)

    def test_unknown_compatibility_blocks_before_the_runner(self):
        self._import()
        deps = self._deps(
            compat=lambda model: _compat(model, status=CompatibilityStatus.UNKNOWN)
        )
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=deps)
        self.assertEqual(len(self.runner.calls), 0)

    def test_failed_compatibility_blocks_before_the_runner(self):
        """A concrete failure is never downgraded to a warning."""
        self._import()
        deps = self._deps(
            compat=lambda model: _compat(
                model, status=CompatibilityStatus.INCOMPATIBLE,
                reasons=("architecture not supported",),
            )
        )
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=deps)
        self.assertEqual(len(self.runner.calls), 0)

    def test_admission_denial_blocks_before_the_runner(self):
        self._import()
        admission = EvaluationAdmission(status="evaluated", verdict="blocked")
        with self.assertRaises(ExecutePreparationError):
            execute_model(
                "Local", "hello", admission=admission, dependencies=self._deps()
            )
        self.assertEqual(len(self.runner.calls), 0)

    def test_admitting_verdict_does_not_block(self):
        self._import()
        admission = EvaluationAdmission(status="evaluated", verdict="compatible")
        result = execute_model(
            "Local", "hello", admission=admission, dependencies=self._deps()
        )
        self.assertTrue(result.success)
        self.assertEqual(len(self.runner.calls), 1)


class PipelineOrderTests(_ExecutionCase):
    def test_compatibility_gate_runs_before_preflight(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.compat_calls), 1)
        self.assertEqual(len(self.selector.calls), 1)

    def test_backend_selector_is_traversed(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.selector.calls), 1)
        compatibility, _, artifact = self.selector.calls[0]
        self.assertEqual(compatibility.status, CompatibilityStatus.MARGINAL)
        self.assertIsNotNone(artifact.artifact.content_id)

    def test_selector_receives_the_imported_artifact(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        _, _, artifact = self.selector.calls[0]
        self.assertIsNone(artifact.artifact.sha256)
        self.assertIsNotNone(artifact.artifact.content_id)

    def test_preflight_failure_stops_before_the_selector(self):
        self._import()

        def failing_factory(store):
            class _Failing:
                def validate(self, artifact):
                    raise ArtifactPreflightError(
                        PreflightErrorCode.INVALID_ARTIFACT, "preflight refused"
                    )
            return _Failing()

        with self.assertRaises(ExecutePreparationError):
            execute_model(
                "Local", "hello",
                dependencies=self._deps(preflight_factory=failing_factory),
            )
        self.assertEqual(len(self.selector.calls), 0)
        self.assertEqual(len(self.runner.calls), 0)

    def test_backend_selection_failure_stops_before_the_runner(self):
        self._import()
        selector = _RecordingSelector(
            error=RuntimeSelectionError(
                SelectionErrorCode.BACKEND_UNSUPPORTED, "no backend"
            )
        )
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps(selector=selector))
        self.assertEqual(len(selector.calls), 1)
        self.assertEqual(len(self.runner.calls), 0)

    def test_empty_prompt_stops_before_the_runner(self):
        self._import()
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "   ", dependencies=self._deps())
        self.assertEqual(len(self.selector.calls), 0)
        self.assertEqual(len(self.runner.calls), 0)

    def test_backend_preference_mismatch_stops_before_the_runner(self):
        self._import()
        with self.assertRaises(ExecutePreparationError):
            execute_model(
                "Local", "hello", backend_preference="CUDA",
                dependencies=self._deps(),
            )
        self.assertEqual(len(self.runner.calls), 0)

    def test_every_gate_precedes_the_runner(self):
        self._import()
        execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.compat_calls), 1)
        self.assertEqual(len(self.selector.calls), 1)
        self.assertEqual(len(self.runner.calls), 1)


class SecurityBlockTests(_ExecutionCase):
    def test_missing_managed_file_blocks_before_the_runner(self):
        imported = self._import()
        imported.destination.unlink()
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_symlinked_managed_file_blocks_before_the_runner(self):
        imported = self._import()
        outside = self.root / "outside.gguf"
        outside.write_bytes(MODEL)
        imported.destination.unlink()
        imported.destination.symlink_to(outside)
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_partial_artifact_blocks_before_the_runner(self):
        imported = self._import()
        imported.destination.unlink()
        (imported.destination.parent / "local.gguf.part").write_bytes(MODEL)
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_inconsistent_manifest_blocks_before_the_runner(self):
        imported = self._import()
        (imported.destination.parent / "manifest.json").write_text(
            "{ broken", encoding="utf-8"
        )
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_tampered_managed_file_blocks_before_the_runner(self):
        """Size mismatch is caught by the existing preflight, not a new check."""
        imported = self._import()
        imported.destination.write_bytes(MODEL + b"tampered")
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_unknown_label_blocks_before_the_runner(self):
        self._import()
        with self.assertRaises(ExecutePreparationError):
            execute_model("Nope", "hello", dependencies=self._deps())
        self.assertEqual(len(self.runner.calls), 0)

    def test_incompatible_capability_blocks_before_the_runner(self):
        self._import()
        with self.assertRaises(ExecutePreparationError):
            execute_model(
                "Local", "hello",
                dependencies=self._deps(
                    capability_provider=lambda: _capability(available=False)
                ),
            )
        self.assertEqual(len(self.runner.calls), 0)

    def test_unsupported_backend_blocks_before_the_runner(self):
        self._import()
        selector = _RecordingSelector(error=RuntimeSelectionError(
            SelectionErrorCode.BACKEND_UNSUPPORTED, "backend unsupported"
        ))
        with self.assertRaises(ExecutePreparationError):
            execute_model("Local", "hello", dependencies=self._deps(selector=selector))
        self.assertEqual(len(self.runner.calls), 0)


class ImportedPathRequiredTests(_ExecutionCase):
    def test_imported_without_managed_path_is_refused(self):
        """The B9.67 security rule: imported implies a verified managed path."""
        self._import()
        from dataclasses import replace

        import app.execute_model as em

        original = em.ModelArtifactResolver.resolve

        def without_path(self_resolver, *args, **kwargs):
            return replace(original(self_resolver, *args, **kwargs), path=None)

        em.ModelArtifactResolver.resolve = without_path
        try:
            with self.assertRaisesRegex(ExecutePreparationError, "managed path"):
                execute_model("Local", "hello", dependencies=self._deps())
        finally:
            em.ModelArtifactResolver.resolve = original
        self.assertEqual(len(self.runner.calls), 0)

    def test_imported_with_managed_path_is_accepted(self):
        """The guard is narrow: a real managed path still executes."""
        self._import()
        result = execute_model("Local", "hello", dependencies=self._deps())
        self.assertTrue(result.success)
        self.assertEqual(len(self.runner.calls), 1)
