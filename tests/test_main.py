import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from app.execution import ExecutionErrorCode, ExecutionErrorInfo, ExecutionResult
from app.main import run_model
from app.model_catalog import get_catalog
from app.models import ArtifactSpec
from app.resolver import ModelArtifactResolutionError, ResolvedModelArtifact


class MainRunTests(unittest.TestCase):
    def setUp(self):
        self.model = get_catalog()[0]
        self.artifact = ArtifactSpec(
            model_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="model.Q4_K_M.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        )
        self.resolved = ResolvedModelArtifact(self.model, self.artifact)

    def test_empty_prompt_is_usage_error_without_resolution(self):
        with patch("app.main.ModelArtifactResolver") as resolver:
            self.assertEqual(run_model(self.model.model_id, "  "), 2)
            resolver.assert_not_called()

    def test_run_rejects_extra_positional_argument(self):
        with patch.object(
            sys,
            "argv",
            [
                "app.main",
                "run",
                "unknown-model",
                "unexpected",
                "--prompt",
                "hello",
            ],
        ):
            with self.assertRaises(SystemExit) as context:
                from app.main import main

                main()
        self.assertEqual(context.exception.code, 2)

    def test_run_with_one_model_id_reaches_resolution_error(self):
        with patch.object(
            sys,
            "argv",
            ["app.main", "run", "unknown-model", "--prompt", "hello"],
        ), patch(
            "app.main.ModelArtifactResolver"
        ) as resolver:
            resolver.return_value.resolve.side_effect = (
                ModelArtifactResolutionError("missing")
            )
            from app.main import main

            self.assertEqual(main(), 1)

    def test_resolution_error_returns_one_without_execution(self):
        resolver = Mock()
        resolver.resolve.side_effect = ModelArtifactResolutionError("missing")
        with patch("app.main.ModelArtifactResolver", return_value=resolver), patch(
            "app.main.ModelExecutionService"
        ) as service:
            error = io.StringIO()
            with redirect_stderr(error):
                code = run_model(self.model.model_id, "hello")
            self.assertEqual(code, 1)
            self.assertIn("missing", error.getvalue())
            service.assert_not_called()

    def test_success_prints_stdout_and_warnings(self):
        service = Mock()
        service.execute.return_value = ExecutionResult(
            True, 0, "model response\n", "runtime diagnostic\n",
            warnings=("estimated memory",),
        )
        output = io.StringIO()
        error = io.StringIO()
        with patch("app.main.ModelArtifactResolver", return_value=Mock(
            resolve=Mock(return_value=self.resolved)
        )), patch("app.main.ModelExecutionService", return_value=service), patch(
            "app.main.detect_hardware"
        ), patch("app.main.detect_llama_capability"), patch(
            "app.main.detect_backends"
        ), redirect_stdout(output), redirect_stderr(error):
            code = run_model(self.model.model_id, "hello")
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "model response\n")
        self.assertIn("runtime diagnostic", error.getvalue())
        self.assertIn("Warning: estimated memory", error.getvalue())

    def test_runner_error_returns_one(self):
        service = Mock()
        service.execute.return_value = ExecutionResult(
            False, 2, "", "bad runtime", 
            error=ExecutionErrorInfo(
                ExecutionErrorCode.PROCESS_FAILED, "process failed"
            ),
        )
        error = io.StringIO()
        with patch("app.main.ModelArtifactResolver", return_value=Mock(
            resolve=Mock(return_value=self.resolved)
        )), patch("app.main.ModelExecutionService", return_value=service), patch(
            "app.main.detect_hardware"
        ), patch("app.main.detect_llama_capability"), patch(
            "app.main.detect_backends"
        ), redirect_stderr(error):
            code = run_model(self.model.model_id, "hello")
        self.assertEqual(code, 1)
        self.assertIn("process failed", error.getvalue())


if __name__ == "__main__":
    unittest.main()
