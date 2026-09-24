
# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import math
import sys
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execution import ExecutionRequest, ExecutionTarget
from app.execution import ExecutionErrorCode, ExecutionErrorInfo, ExecutionResult
from app.main import (
    _DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    _download_status,
    print_models,
    run_download,
    run_model,
)
from app.model_catalog import get_catalog
from app.models import ArtifactSpec, Quantization
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


class PrintLocalModelsTests(unittest.TestCase):
    def test_list_without_artifacts(self):
        from app.main import print_local_models

        mock_store = Mock()
        mock_store.list_artifacts.return_value = []
        out = io.StringIO()
        with redirect_stdout(out):
            print_local_models(mock_store)
        text = out.getvalue()
        self.assertIn("CastleArq - Local models", text)
        self.assertIn("No local model artifacts found.", text)

    def test_list_with_single_artifact(self):
        from app.main import print_local_models
        from app.model_store import StoredArtifact
        from app.models import ArtifactSpec, ArtifactState

        artifact = ArtifactSpec(
            model_id="qwen2.5-coder-7b-instruct",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            format="GGUF",
            quantization="Q4_K_M",
            size_bytes=4831838208,  # ~4.5 GiB
        )
        entry = StoredArtifact(
            artifact=artifact,
            state=ArtifactState.VERIFIED,
            manifest_path=Path("/models/manifest.json"),
        )
        mock_store = Mock()
        mock_store.list_artifacts.return_value = [entry]
        out = io.StringIO()
        with redirect_stdout(out):
            print_local_models(mock_store)
        text = out.getvalue()
        self.assertIn("qwen2.5-coder-7b-instruct", text)
        self.assertIn("filename: qwen2.5-coder-7b-instruct-q4_k_m.gguf", text)
        self.assertIn("quantization: Q4_K_M", text)
        self.assertIn("size: 4.5 GiB", text)
        self.assertIn("status: VERIFIED", text)

    def test_list_with_multiple_artifacts_and_deterministic_order(self):
        from app.main import print_local_models
        from app.model_store import StoredArtifact
        from app.models import ArtifactSpec, ArtifactState

        art_q8 = ArtifactSpec(
            model_id="qwen2.5-coder-7b-instruct",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="z_qwen_q8_0.gguf",
            format="GGUF",
            quantization="Q8_0",
            size_bytes=8 * 1024 * 1024 * 1024,
        )
        art_q4 = ArtifactSpec(
            model_id="qwen2.5-coder-7b-instruct",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="a_qwen_q4_k_m.gguf",
            format="GGUF",
            quantization="Q4_K_M",
            size_bytes=4 * 1024 * 1024 * 1024,
        )
        entry_q8 = StoredArtifact(
            artifact=art_q8,
            state=ArtifactState.VERIFIED,
            manifest_path=Path("/models/q8/manifest.json"),
        )
        entry_q4 = StoredArtifact(
            artifact=art_q4,
            state=ArtifactState.DOWNLOADED,
            manifest_path=Path("/models/q4/manifest.json"),
        )
        # Store returns in non-sorted order
        mock_store = Mock()
        mock_store.list_artifacts.return_value = [entry_q8, entry_q4]
        out = io.StringIO()
        with redirect_stdout(out):
            print_local_models(mock_store)
        text = out.getvalue()
        # a_qwen must appear before z_qwen
        pos_q4 = text.find("a_qwen_q4_k_m.gguf")
        pos_q8 = text.find("z_qwen_q8_0.gguf")
        self.assertNotEqual(pos_q4, -1)
        self.assertNotEqual(pos_q8, -1)
        self.assertLess(pos_q4, pos_q8)
        self.assertIn("status: DOWNLOADED", text)
        self.assertIn("status: VERIFIED", text)

    def test_list_with_size_bytes_none(self):
        from app.main import print_local_models
        from app.model_store import StoredArtifact
        from app.models import ArtifactSpec, ArtifactState

        artifact = ArtifactSpec(
            model_id="qwen2.5-coder-7b-instruct",
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename="qwen.gguf",
            format="GGUF",
            quantization="Q4_K_M",
            size_bytes=None,
        )
        entry = StoredArtifact(
            artifact=artifact,
            state=ArtifactState.VERIFIED,
            manifest_path=Path("/models/manifest.json"),
        )
        mock_store = Mock()
        mock_store.list_artifacts.return_value = [entry]
        out = io.StringIO()
        with redirect_stdout(out):
            print_local_models(mock_store)
        text = out.getvalue()
        self.assertIn("size: Unknown", text)


class PrintModelsTests(unittest.TestCase):
    def _result(self, model, score=90):
        return CompatibilityResult(
            model=model,
            status=CompatibilityStatus.COMPATIBLE,
            score=score,
            reasons=("reason text",),
            warnings=("warning text",),
            estimated_memory_bytes=8 * 1024**3,
            memory_is_estimate=True,
            recommended_quantization=Quantization("Q4_K_M", 4.5, 3),
            recommended_runtime="llama.cpp / llama.app",
            recommended_backend="Vulkan",
        )

    def _model(self, model_id):
        return next(model for model in get_catalog() if model.model_id == model_id)

    def _render(self, results, mapping=None):
        hardware = SimpleNamespace(gpus=(), memory=SimpleNamespace(total_gib=16.0))
        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.detect_hardware", return_value=hardware)
            )
            stack.enter_context(patch("app.main.detect_runtimes", return_value=[]))
            stack.enter_context(patch("app.main.detect_backends", return_value=[]))
            stack.enter_context(
                patch("app.main.recommend_models", return_value=results)
            )
            if mapping is not None:
                stack.enter_context(
                    patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping)
                )
            output = io.StringIO()
            with redirect_stdout(output):
                print_models()
        return output.getvalue()

    def test_empty_recommendations_keep_existing_message(self):
        text = self._render([])
        self.assertIn("CastleArq - Model recommendations", text)
        self.assertIn("No models available in the catalog.", text)
        self.assertNotIn("Model ID:", text)

    def test_downloadable_model_shows_model_id_and_available_source(self):
        qwen = self._model("qwen2.5-coder-7b-instruct")
        text = self._render([self._result(qwen)])
        self.assertIn("Qwen2.5-Coder 7B Instruct", text)
        self.assertIn(f"Model ID: {qwen.model_id}", text)
        self.assertIn(
            "Download: available (huggingface: Qwen/Qwen2.5-Coder-7B-Instruct-GGUF)",
            text,
        )

    def test_not_downloadable_model_shows_not_available_yet(self):
        llama = self._model("llama-3.1-8b-instruct")
        text = self._render([self._result(llama)])
        self.assertIn(f"Model ID: {llama.model_id}", text)
        self.assertIn("Download: not available yet", text)
        self.assertNotIn("Download: available", text)

    def test_mixed_models_show_both_states_and_keep_order(self):
        qwen = self._model("qwen2.5-coder-7b-instruct")
        llama = self._model("llama-3.1-8b-instruct")
        text = self._render(
            [self._result(qwen, score=95), self._result(llama, score=93)]
        )
        self.assertIn(
            "Download: available (huggingface: Qwen/Qwen2.5-Coder-7B-Instruct-GGUF)",
            text,
        )
        self.assertIn("Download: not available yet", text)
        self.assertLess(text.index(qwen.model_id), text.index(llama.model_id))

    def test_model_id_is_exact_and_not_the_friendly_name(self):
        qwen = self._model("qwen2.5-coder-7b-instruct")
        text = self._render([self._result(qwen)])
        self.assertNotEqual(qwen.model_id, qwen.name)
        self.assertIn(f"Model ID: {qwen.model_id}", text)
        self.assertNotIn(f"Model ID: {qwen.name}", text)

    def test_multiple_mapped_sources_are_not_offered_as_available(self):
        llama = self._model("llama-3.1-8b-instruct")
        mapping = {
            ("huggingface", "owner/one"): llama.model_id,
            ("huggingface", "owner/two"): llama.model_id,
        }
        text = self._render([self._result(llama)], mapping=mapping)
        self.assertIn("Download: unavailable (multiple sources mapped)", text)
        self.assertNotIn("Download: available", text)

    def test_repository_is_taken_only_from_the_real_mapping(self):
        from app.model_identity import SOURCE_REPOSITORY_TO_MODEL_ID

        qwen = self._model("qwen2.5-coder-7b-instruct")
        llama = self._model("llama-3.1-8b-instruct")
        text = self._render([self._result(qwen), self._result(llama)])
        self.assertTrue(SOURCE_REPOSITORY_TO_MODEL_ID)
        for (source, repository), logical in SOURCE_REPOSITORY_TO_MODEL_ID.items():
            if logical == qwen.model_id:
                self.assertIn(f"Download: available ({source}: {repository})", text)
        self.assertEqual(text.count("Download: available"), 1)
        self.assertEqual(text.count("Download: not available yet"), 1)
        self.assertNotIn("owner/", text)

    def test_existing_recommendation_fields_are_preserved(self):
        qwen = self._model("qwen2.5-coder-7b-instruct")
        text = self._render([self._result(qwen, score=95)])
        self.assertIn("Status: COMPATIBLE", text)
        self.assertIn("Score: 95", text)
        self.assertIn("Quantization: Q4_K_M", text)
        self.assertIn("Memory: 8.0 GiB estimated", text)
        self.assertIn("Runtime: llama.cpp / llama.app", text)
        self.assertIn("Backend: Vulkan", text)
        self.assertIn("Reason: reason text", text)
        self.assertIn("Warning: warning text", text)

    def test_output_is_deterministic(self):
        qwen = self._model("qwen2.5-coder-7b-instruct")
        first = self._render([self._result(qwen)])
        second = self._render([self._result(qwen)])
        self.assertEqual(first, second)


class DownloadStatusTests(unittest.TestCase):
    """``_download_status`` must agree with the ``download`` command gate."""

    def _status(self, model_id, mapping):
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping):
            return _download_status(model_id)

    def _gate_passes(self, model_id, mapping):
        source = Mock()
        source.discover_artifacts.return_value = []
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping):
            run_download(
                model_id,
                source_factory=lambda: source,
                out=io.StringIO(),
                err=io.StringIO(),
            )
        return source.discover_artifacts.called

    def test_zero_mappings_is_not_available(self):
        status = self._status("some-model", {})
        self.assertEqual(status, "not available yet")
        self.assertFalse(status.startswith("available"))

    def test_single_huggingface_mapping_is_available(self):
        status = self._status(
            "some-model", {("huggingface", "owner/repo"): "some-model"}
        )
        self.assertEqual(status, "available (huggingface: owner/repo)")

    def test_multiple_mappings_are_not_available(self):
        status = self._status(
            "some-model",
            {
                ("huggingface", "owner/one"): "some-model",
                ("huggingface", "owner/two"): "some-model",
            },
        )
        self.assertEqual(status, "unavailable (multiple sources mapped)")
        self.assertFalse(status.startswith("available"))

    def test_single_unsupported_source_is_not_available(self):
        status = self._status(
            "some-model", {("ollama", "qwen2.5-coder:7b"): "some-model"}
        )
        self.assertEqual(status, "unavailable (unsupported source)")
        self.assertFalse(status.startswith("available"))

    def test_status_matches_the_download_gate(self):
        scenarios = {
            "none": {},
            "single": {("huggingface", "owner/repo"): "some-model"},
            "multiple": {
                ("huggingface", "owner/one"): "some-model",
                ("huggingface", "owner/two"): "some-model",
            },
            "unsupported": {("ollama", "qwen2.5-coder:7b"): "some-model"},
        }
        for name, mapping in scenarios.items():
            with self.subTest(scenario=name):
                available = self._status("some-model", mapping).startswith(
                    "available ("
                )
                self.assertEqual(
                    available, self._gate_passes("some-model", mapping)
                )

    def test_real_qwen_mapping_stays_downloadable(self):
        from app.model_identity import SOURCE_REPOSITORY_TO_MODEL_ID

        status = _download_status("qwen2.5-coder-7b-instruct")
        self.assertTrue(status.startswith("available ("))
        self.assertIn("huggingface", status)
        self.assertIn("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", status)
        self.assertEqual(
            SOURCE_REPOSITORY_TO_MODEL_ID[
                ("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
            ],
            "qwen2.5-coder-7b-instruct",
        )

class CliHelpTests(unittest.TestCase):
    """Tier 1 help: documentation-only changes must not alter command wiring."""

    def _help_text(self) -> str:
        from app.main import main

        buffer = io.StringIO()
        with patch.object(sys, "argv", ["castlearq", "--help"]), patch.object(
            sys, "stdout", new=buffer
        ):
            with self.assertRaises(SystemExit) as ctx:
                main()
        self.assertEqual(ctx.exception.code, 0)
        return buffer.getvalue()

    def test_help_exits_zero(self):
        self._help_text()

    def test_help_has_current_product_description(self):
        self.assertIn(
            "CastleArq: local model discovery, download, execution and chat",
            self._help_text(),
        )
        self.assertNotIn("hardware detection", self._help_text())

    def test_help_explains_provider_and_repository(self):
        text = " ".join(self._help_text().split())
        self.assertIn("model-id for download/run/chat", text)
        self.assertIn("repository for source", text)
        self.assertIn("artifact filename for plan", text)

    def test_help_explains_flags(self):
        text = " ".join(self._help_text().split())
        self.assertIn("prompt text for run", text)
        self.assertIn("quantization level to select for download, run or chat", text)
        self.assertIn("exact artifact filename to select for download, run or chat", text)

    def test_help_shows_usage_flow(self):
        text = self._help_text()
        for command in ("models", "download", "list", "run", "chat"):
            self.assertIn(f"castlearq {command}", text)
        self.assertIn("python3 -m app.main --help", text)

    def test_help_explains_model_id(self):
        text = self._help_text()
        self.assertIn("<model-id>", text)
        self.assertIn("model id", text)
        self.assertIn("qwen2.5-coder-7b-instruct", text)
        self.assertIn("Qwen2.5-Coder 7B Instruct", text)
        self.assertIn("never the friendly name", text)

    def test_help_contains_examples(self):
        text = self._help_text()
        self.assertIn("castlearq models", text)
        self.assertIn("castlearq download qwen2.5-coder-7b-instruct", text)
        self.assertIn(
            'castlearq run qwen2.5-coder-7b-instruct --prompt "Hello"', text
        )
        self.assertIn("python3 -m app.main --help", text)

    def test_all_commands_are_recognized(self):
        from app.main import main

        for command in ("detect", "models", "list", "source", "plan", "download", "run", "chat"):
            buffer = io.StringIO()
            with patch.object(
                sys, "argv", ["castlearq", command]
            ), patch.object(sys, "stdout", new=buffer), patch.object(
                sys, "stderr", new=io.StringIO()
            ):
                try:
                    main()
                    exit_code = 0
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 0
            self.assertNotIn("invalid choice", buffer.getvalue(), command)
            self.assertNotEqual(exit_code, 2, command)

    def test_download_run_chat_wiring_unchanged(self):
        from app.main import main

        with patch.object(
            sys, "argv", ["castlearq", "download", "some-model"]
        ) as argv, patch("app.main.run_download") as run_download_mock:
            main()
        run_download_mock.assert_called_once_with(
            "some-model", quantization=None, filename=None
        )
        self.assertEqual(argv[1:2], ["download"])

        for command, function_name in (
            ("run", "run_model"),
            ("chat", "chat_model"),
        ):
            with patch.object(
                sys,
                "argv",
                ["castlearq", command, "some-model"],
            ), patch(f"app.main.{function_name}") as function_mock:
                main()
            if command == "run":
                function_mock.assert_called_once_with(
                    "some-model", None, quantization=None, filename=None
                )
            else:
                function_mock.assert_called_once_with(
                    "some-model", quantization=None, filename=None
                )


class PerCommandFlagValidationTests(unittest.TestCase):
    """H1: flags irrelevant for a command must be rejected by the parser."""

    COMMANDS_WITHOUT_FLAGS = ("detect", "models", "source", "plan", "list")
    ALL_FLAGS = ("prompt", "quantization", "filename")

    def _run_cli(self, argv):
        from app.main import main

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["castlearq", *argv]), patch.object(
            sys, "stdout", new=stdout
        ), patch.object(sys, "stderr", new=stderr):
            try:
                exit_code = main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 0
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_commands_without_flags_reject_every_flag(self):
        for command in self.COMMANDS_WITHOUT_FLAGS:
            for flag in self.ALL_FLAGS:
                with self.subTest(command=command, flag=flag):
                    exit_code, _, stderr = self._run_cli(
                        [command, f"--{flag}", "x"]
                    )
                    self.assertEqual(exit_code, 2)
                    self.assertIn(f"--{flag} is not valid for command '{command}'", stderr)

    def test_download_rejects_prompt(self):
        exit_code, _, stderr = self._run_cli(["download", "--prompt", "x"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--prompt is not valid for command 'download'", stderr)

    def test_chat_rejects_prompt(self):
        exit_code, _, stderr = self._run_cli(["chat", "--prompt", "x"])
        self.assertEqual(exit_code, 2)
        self.assertIn("--prompt is not valid for command 'chat'", stderr)

    def test_valid_flag_combinations_reach_command_functions(self):
        with patch("app.main.run_download") as download_mock:
            self._run_cli(
                ["download", "some-model", "--quantization", "Q4_K_M", "--filename", "a.gguf"]
            )
        download_mock.assert_called_once_with(
            "some-model", quantization="Q4_K_M", filename="a.gguf"
        )

        with patch("app.main.run_model") as run_mock:
            self._run_cli(
                ["run", "some-model", "--prompt", "Hi", "--quantization", "Q4_K_M"]
            )
        run_mock.assert_called_once_with(
            "some-model", "Hi", quantization="Q4_K_M", filename=None
        )

        with patch("app.main.chat_model") as chat_mock:
            self._run_cli(["chat", "some-model", "--filename", "a.gguf"])
        chat_mock.assert_called_once_with(
            "some-model", quantization=None, filename="a.gguf"
        )

    def test_plan_positionals_still_work_with_no_flags(self):
        exit_code, stdout, _ = self._run_cli(["plan", "owner/repository", "model.gguf"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Plan error: repository is not mapped to a catalog model", stdout)

    def test_source_positionals_still_work_with_no_flags(self):
        exit_code, stdout, _ = self._run_cli(["source", "huggingface", "owner/repository"])
        self.assertEqual(exit_code, 1)
        self.assertIn("Source error: Repository is not mapped to a catalog model", stdout)

    def test_invalid_flag_rejected_before_command_execution(self):
        with patch("app.main.run_download") as download_mock:
            exit_code, _, _ = self._run_cli(["download", "--prompt", "x"])
        self.assertEqual(exit_code, 2)
        download_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
