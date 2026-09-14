import io
import math
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.execution import ExecutionRequest, ExecutionTarget
from app.execution import ExecutionErrorCode, ExecutionErrorInfo, ExecutionResult
from app.main import _DEFAULT_EXECUTION_TIMEOUT_SECONDS, run_model
from app.model_catalog import get_catalog
from app.models import ArtifactSpec
from app.resolver import ModelArtifactResolutionError, ResolvedModelArtifact


class MainRunTests(unittest.TestCase):
    def setUp(self):
        self.model = get_catalog()[0]
        self.artifact = ArtifactSpec(
            model_id="qwen2.5-coder-7b-instruct",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="model.Q4_K_M.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        )
        self.resolved = ResolvedModelArtifact(self.model, self.artifact)
        self.preparation = SimpleNamespace(
            executable_artifact=Mock(),
            target=ExecutionTarget("llama.cpp CLI", "Vulkan"),
            compatibility_warnings=(),
            selection_warnings=(),
        )

    def _runner(self, result):
        runner = Mock()
        runner.run.return_value = result
        return runner

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
        with patch("app.main.ModelArtifactResolver") as resolver, patch(
            "app.main._prepare"
        ) as prepare, patch("app.main.LlamaCppRunner") as runner:
            resolver.return_value.resolve.side_effect = (
                ModelArtifactResolutionError("missing")
            )
            error = io.StringIO()
            with redirect_stderr(error):
                code = run_model(self.model.model_id, "hello")
            self.assertEqual(code, 1)
            self.assertIn("missing", error.getvalue())
            prepare.assert_not_called()
            runner.assert_not_called()

    def test_preparation_error_returns_one_without_running(self):
        error_class = __import__("app.main", fromlist=["PreparationError"]).PreparationError
        with patch("app.main.ModelArtifactResolver") as resolver, patch(
            "app.main._prepare"
        ) as prepare, patch("app.main.LlamaCppRunner") as runner:
            resolver.return_value.resolve.return_value = self.resolved
            prepare.side_effect = error_class(
                "Model compatibility does not permit execution",
                compatibility_warnings=("marginal",),
            )
            error = io.StringIO()
            with redirect_stderr(error):
                code = run_model(self.model.model_id, "hello")
            self.assertEqual(code, 1)
            self.assertIn("Model compatibility", error.getvalue())
            self.assertIn("marginal", error.getvalue())
            runner.assert_not_called()

    def test_success_prints_stdout_and_warnings(self):
        self.preparation.compatibility_warnings = ("estimated memory",)
        result = ExecutionResult(True, 0, "model response\n", "runtime diagnostic\n")
        with patch("app.main.ModelArtifactResolver", return_value=Mock(
            resolve=Mock(return_value=self.resolved)
        )), patch("app.main._prepare", return_value=self.preparation), patch(
            "app.main.LlamaCppRunner", return_value=self._runner(result)
        ):
            code = run_model(self.model.model_id, "hello")
        self.assertEqual(code, 0)

    def test_runner_error_returns_one(self):
        result = ExecutionResult(
            False, 2, "", "bad runtime",
            error=ExecutionErrorInfo(
                ExecutionErrorCode.PROCESS_FAILED, "process failed"
            ),
        )
        error = io.StringIO()
        with patch("app.main.ModelArtifactResolver", return_value=Mock(
            resolve=Mock(return_value=self.resolved)
        )), patch("app.main._prepare", return_value=self.preparation), patch(
            "app.main.LlamaCppRunner", return_value=self._runner(result)
        ), redirect_stderr(error):
            code = run_model(self.model.model_id, "hello")
        self.assertEqual(code, 1)
        self.assertIn("process failed", error.getvalue())

    def test_run_passes_finite_positive_default_timeout(self):
        captured = {}

        def run(executable_artifact, target, request):
            captured["request"] = request
            return ExecutionResult(True, 0, "ok\n", "")

        runner = Mock()
        runner.run.side_effect = run
        with patch("app.main.ModelArtifactResolver", return_value=Mock(
            resolve=Mock(return_value=self.resolved)
        )), patch("app.main._prepare", return_value=self.preparation), patch(
            "app.main.LlamaCppRunner", return_value=runner
        ):
            code = run_model(self.model.model_id, "hello")
        self.assertEqual(code, 0)
        request = captured["request"]
        self.assertEqual(request.timeout_seconds, _DEFAULT_EXECUTION_TIMEOUT_SECONDS)
        self.assertGreater(request.timeout_seconds, 0)
        self.assertTrue(math.isfinite(request.timeout_seconds))

    def test_run_model_forwards_quantization_and_filename_to_resolver(self):
        resolver_mock = Mock()
        resolver_mock.resolve.return_value = self.resolved
        with patch("app.main.ModelArtifactResolver", return_value=resolver_mock), patch(
            "app.main._prepare", return_value=self.preparation
        ), patch("app.main.LlamaCppRunner", return_value=self._runner(ExecutionResult(True, 0, "ok\n", ""))):
            code = run_model(
                self.model.model_id,
                "hello",
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
            )
            self.assertEqual(code, 0)
            resolver_mock.resolve.assert_called_once_with(
                self.model.model_id,
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
            )

    def test_chat_model_forwards_quantization_and_filename_to_resolver(self):
        from app.main import chat_model

        resolver_mock = Mock()
        resolver_mock.resolve.return_value = self.resolved
        session_mock = Mock()
        session_mock.state = Mock(value="closed")
        capability = Mock()
        capability.invocable = True
        with patch("app.main.ModelArtifactResolver", return_value=resolver_mock), patch(
            "app.main.detect_llama_capability", return_value=capability
        ), patch(
            "app.main._prepare", return_value=self.preparation
        ), patch("app.main.start_chat_session", return_value=session_mock):
            out = io.StringIO()
            err = io.StringIO()
            code = chat_model(
                self.model.model_id,
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
                input_fn=lambda: "/exit",
                out=out,
                err=err,
            )
            self.assertEqual(code, 0)
            resolver_mock.resolve.assert_called_once_with(
                self.model.model_id,
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
            )

    def test_main_cli_forwards_selection_to_run(self):
        with patch.object(
            sys,
            "argv",
            [
                "app.main",
                "run",
                self.model.model_id,
                "--prompt",
                "hello",
                "--quantization",
                "Q4_K_M",
                "--filename",
                "model.Q4_K_M.gguf",
            ],
        ), patch("app.main.run_model", return_value=0) as run_mock:
            from app.main import main

            self.assertEqual(main(), 0)
            run_mock.assert_called_once_with(
                self.model.model_id,
                "hello",
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
            )

    def test_main_cli_forwards_selection_to_chat(self):
        with patch.object(
            sys,
            "argv",
            [
                "app.main",
                "chat",
                self.model.model_id,
                "--quantization",
                "Q4_K_M",
                "--filename",
                "model.Q4_K_M.gguf",
            ],
        ), patch("app.main.chat_model", return_value=0) as chat_mock:
            from app.main import main

            self.assertEqual(main(), 0)
            chat_mock.assert_called_once_with(
                self.model.model_id,
                quantization="Q4_K_M",
                filename="model.Q4_K_M.gguf",
            )


if __name__ == "__main__":
    unittest.main()
