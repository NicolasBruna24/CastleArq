import unittest
from dataclasses import FrozenInstanceError

from app.execution import (
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from app.models import ArtifactSpec


def artifact() -> ArtifactSpec:
    return ArtifactSpec(
        model_id="qwen/coder",
        source="huggingface",
        repository="owner/repository",
        filename="model-q4.gguf",
        format="GGUF",
        quantization="Q4_K_M",
    )


class ExecutionContractTests(unittest.TestCase):
    def test_target_contains_only_selected_runtime_and_backend(self):
        target = ExecutionTarget(runtime="llama.cpp", backend="Vulkan")
        self.assertEqual(target.runtime, "llama.cpp")
        self.assertEqual(target.backend, "Vulkan")

    def test_request_references_artifact_without_process_configuration(self):
        request = ExecutionRequest(
            artifact=artifact(),
            prompt="hello",
            target=ExecutionTarget("llama.cpp", "CPU"),
        )
        self.assertEqual(request.artifact, artifact())
        self.assertEqual(request.prompt, "hello")
        self.assertIsNone(getattr(request, "executable", None))
        self.assertIsNone(getattr(request, "environment", None))
        self.assertIsNone(getattr(request, "arguments", None))

    def test_request_can_omit_target_before_selection(self):
        request = ExecutionRequest(artifact=artifact(), prompt="hello")
        self.assertIsNone(request.target)
        self.assertIsNone(request.timeout_seconds)

    def test_result_exposes_success_process_output_and_error(self):
        error = ExecutionErrorInfo(ExecutionErrorCode.PROCESS_FAILED, "process failed")
        result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="partial output",
            stderr="failure",
            error=error,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "partial output")
        self.assertEqual(result.stderr, "failure")
        self.assertEqual(result.error.code, ExecutionErrorCode.PROCESS_FAILED)

    def test_domain_types_are_frozen(self):
        target = ExecutionTarget("llama.cpp", "CPU")
        request = ExecutionRequest(artifact(), "hello")
        result = ExecutionResult(True, 0, "", "")
        error = ExecutionErrorInfo(ExecutionErrorCode.TIMEOUT, "timed out")

        for value, field in (
            (target, "runtime"),
            (request, "prompt"),
            (result, "success"),
            (error, "message"),
        ):
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field, "changed")


if __name__ == "__main__":
    unittest.main()
