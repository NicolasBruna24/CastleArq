import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.execution import (
    ExecutionDiagnostics,
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
    RuntimeMetricSource,
    RuntimeMetrics,
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

    def test_diagnostics_are_optional_and_frozen(self):
        diagnostics = ExecutionDiagnostics(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_seconds=0.1,
            stdout_bytes=3,
            stderr_bytes=2,
            exit_code=0,
            timed_out=False,
            terminated_normally=True,
        )
        result = ExecutionResult(True, 0, "", "", diagnostics=diagnostics)
        self.assertIs(result.diagnostics, diagnostics)
        with self.assertRaises(FrozenInstanceError):
            diagnostics.exit_code = 1

    def test_runtime_metrics_can_be_empty_or_partial(self):
        empty = RuntimeMetrics()
        self.assertEqual(empty.source, RuntimeMetricSource.UNAVAILABLE)
        metrics = RuntimeMetrics(
            prompt_tokens=12,
            generated_tokens=7,
            prompt_tokens_per_second=10.5,
            generation_tokens_per_second=4.25,
            load_time_seconds=0.8,
            total_time_seconds=2.4,
            source=RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
        )
        self.assertEqual(metrics.prompt_tokens, 12)
        self.assertEqual(metrics.generated_tokens, 7)
        self.assertEqual(metrics.prompt_tokens_per_second, 10.5)
        self.assertEqual(metrics.generation_tokens_per_second, 4.25)
        self.assertEqual(metrics.load_time_seconds, 0.8)
        self.assertEqual(metrics.total_time_seconds, 2.4)

    def test_runtime_metrics_reject_invalid_values(self):
        invalid_values = (
            {"prompt_tokens": -1},
            {"generated_tokens": -1},
            {"prompt_tokens": True},
            {"generation_tokens_per_second": False},
            {"prompt_tokens_per_second": -0.1},
            {"load_time_seconds": -0.1},
            {"total_time_seconds": "2"},
            {"generation_tokens_per_second": float("nan")},
            {"source": "llama_human_output"},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    RuntimeMetrics(**values)

    def test_runtime_metrics_and_result_are_immutable(self):
        metrics = RuntimeMetrics(prompt_tokens=1)
        result = ExecutionResult(True, 0, "", "", runtime_metrics=metrics)
        self.assertIs(result.runtime_metrics, metrics)
        with self.assertRaises(FrozenInstanceError):
            metrics.prompt_tokens = 2
        with self.assertRaises(FrozenInstanceError):
            result.runtime_metrics = None

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
