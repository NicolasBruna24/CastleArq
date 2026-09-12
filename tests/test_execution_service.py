import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execution import (
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionResult,
)
from app.execution_service import ModelExecutionService
from app.models import ArtifactSpec, ModelSpec
from app.runtimes import PromptInputMode, RuntimeCapability
from app.selection import RuntimeSelection, RuntimeSelectionError
from app.execution import ExecutionTarget


def artifact() -> ArtifactSpec:
    return ArtifactSpec(
        model_id="model",
        source="huggingface",
        repository="owner/repo",
        filename="model.gguf",
        format="GGUF",
    )


def compatibility(status=CompatibilityStatus.COMPATIBLE, warnings=()):
    return CompatibilityResult(
        model=ModelSpec(name="model"),
        status=status,
        score=50,
        reasons=("test",),
        warnings=warnings,
        estimated_memory_bytes=None,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime="llama.cpp / llama.app",
        recommended_backend="Vulkan",
    )


class ModelExecutionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.spec = artifact()
        self.model = self.spec
        self.model_spec = ModelSpec(name="model")
        self.request = ExecutionRequest(self.spec, "hello")
        self.executable = ExecutableArtifact(
            self.spec, Path(self.tempdir.name) / self.spec.filename, False, False
        )
        self.target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        self.evaluator = Mock(return_value=compatibility())
        self.preflight = Mock()
        self.preflight.validate.return_value = self.executable
        self.selector = Mock()
        self.selector.select.return_value = RuntimeSelection(self.target)
        self.runner = Mock()
        self.runner.run.return_value = ExecutionResult(True, 0, "out", "")
        self.capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/opt/llama",
            version="test",
            supported_formats=("GGUF",),
            supported_backends=("Vulkan",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp / llama.app",),
            backend_arguments=(("Vulkan", "Vulkan0"),),
        )
        self.service = ModelExecutionService(
            self.evaluator,
            self.preflight,
            self.selector,
            self.capability,
            self.runner,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_successful_flow_passes_exact_objects_to_runner(self):
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertTrue(result.success)
        self.evaluator.assert_called_once_with(self.model_spec)
        self.preflight.validate.assert_called_once_with(self.spec)
        self.selector.select.assert_called_once_with(
            compatibility(), self.capability, self.executable
        )
        self.runner.run.assert_called_once_with(
            self.executable, self.target, self.request
        )

    def test_marginal_warnings_are_preserved_and_merged(self):
        self.evaluator.return_value = compatibility(
            CompatibilityStatus.MARGINAL, ("compat warning",)
        )
        self.selector.select.return_value = RuntimeSelection(
            self.target, ("selection warning", "compat warning")
        )
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertEqual(result.warnings, ("compat warning", "selection warning"))

    def test_incompatible_and_unknown_stop_before_runner(self):
        for status in (CompatibilityStatus.INCOMPATIBLE, CompatibilityStatus.UNKNOWN):
            with self.subTest(status=status):
                self.evaluator.return_value = compatibility(status)
                result = self.service.execute(
                    self.model_spec, self.spec, self.request
                )
                self.assertEqual(
                    result.error.code, ExecutionErrorCode.COMPATIBILITY_REJECTED
                )
                self.runner.run.assert_not_called()
                self.preflight.validate.assert_not_called()
                self.selector.select.assert_not_called()
                self.evaluator.reset_mock()

    def test_preflight_failure_stops_before_selection_and_runner(self):
        self.preflight.validate.side_effect = ArtifactPreflightError(
            __import__("app.execution", fromlist=["PreflightErrorCode"]).PreflightErrorCode.MISSING_ARTIFACT,
            "missing",
        )
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.PREFLIGHT_FAILED)
        self.selector.select.assert_not_called()
        self.runner.run.assert_not_called()

    def test_selection_failure_stops_before_runner(self):
        self.selector.select.side_effect = RuntimeSelectionError(
            __import__("app.selection", fromlist=["SelectionErrorCode"]).SelectionErrorCode.BACKEND_UNSUPPORTED,
            "unsupported",
        )
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.SELECTION_FAILED)
        self.runner.run.assert_not_called()

    def test_runner_result_and_errors_are_propagated_with_warnings(self):
        expected = ExecutionResult(
            False, 2, "out", "err", warnings=("existing warning",)
        )
        self.runner.run.return_value = expected
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertIs(result, expected)

    def test_inputs_and_components_are_not_mutated(self):
        before_request = self.request
        before_artifact = self.spec
        before_capability = self.capability
        result = self.service.execute(self.model_spec, self.spec, self.request)
        self.assertEqual(result.success, True)
        self.assertEqual(self.request, before_request)
        self.assertEqual(self.spec, before_artifact)
        self.assertEqual(self.capability, before_capability)

    def test_service_does_not_create_processes_or_use_filesystem_directly(self):
        self.service.execute(self.model_spec, self.spec, self.request)
        self.runner.run.assert_called_once()
        self.assertFalse(hasattr(self.service, "run_process"))


if __name__ == "__main__":
    unittest.main()
