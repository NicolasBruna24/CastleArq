
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

"""Tests proving that run_model and chat_model share one preparation pipeline."""

from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from castlearq.compatibility import CompatibilityResult, CompatibilityStatus
from castlearq.execution import ExecutionResult, ExecutionTarget
from castlearq.execute_model import EvaluationAdmission, ExecuteAdmissionDeniedError

# B9.78: strict admission is the mandatory gate for the shared preparation
# pipeline, so tests exercising preparation supply an admitting signal.
ADMITTING = EvaluationAdmission(status="evaluated", verdict="compatible")
from castlearq.main import PreparationError, _prepare
from castlearq.models import ArtifactSpec, ArtifactState, ModelSpec
from castlearq.resolver import ResolvedModelArtifact
from castlearq.runtimes import PromptInputMode, RuntimeCapability


def _invocable_capability() -> RuntimeCapability:
    """An available runtime, expressed with the production capability type.

    It exists only to satisfy the ``capability.invocable`` precondition of
    ``chat_model``. It performs no probing and encodes no host state, so the
    test result does not depend on whether llama.cpp is installed on PATH.
    """
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path="/usr/bin/llama",
        version="0.0.0-test",
        supported_formats=("GGUF",),
        supported_backends=("Vulkan", "CPU"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
    )


def _compatible(model):
    return CompatibilityResult(
        model=model,
        status=CompatibilityStatus.COMPATIBLE,
        score=100,
        reasons=("fits",),
        warnings=(),
        estimated_memory_bytes=4 * 10**9,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime="llama.cpp / llama.app",
        recommended_backend="Vulkan",
    )


def _make_resolved():
    model = ModelSpec(
        id="qwen2.5-coder-7b-instruct",
        name="Qwen2.5 Coder 7B Instruct",
        provider="Qwen",
        format="GGUF",
        supported_backends=("Vulkan", "CPU"),
    )
    artifact = ArtifactSpec(
        model_id="qwen2.5-coder-7b-instruct",
        source="huggingface",
        repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename="model.Q4_K_M.gguf",
        format="GGUF",
        quantization="Q4_K_M",
        state=ArtifactState.VERIFIED,
    )
    return model, artifact, ResolvedModelArtifact(model, artifact)


class SharedPreparationTests(unittest.TestCase):
    def setUp(self):
        self.model, self.artifact, self.resolved = _make_resolved()
        self.exe = Mock()
        self.exe.path = "/models/qwen/model.gguf"
        self.capability = Mock()
        self.capability.executable_path = "/usr/bin/llama"
        self.capability.available = True
        self.capability.supported_backends = ("Vulkan", "CPU")
        self.capability.backend_argument = Mock(return_value="Vulkan0")
        self.preflight = Mock()
        self.preflight.validate.return_value = self.exe
        self.selector = Mock()
        self.selection = SimpleNamespace(
            target=ExecutionTarget("llama.cpp / llama.app", "Vulkan"),
            warnings=("marginal",),
        )
        self.selector.select.return_value = self.selection
        self.model_store = Mock()

    def test_prepare_evaluates_compatibility_once(self):
        with patch("castlearq.run_service.assess_model") as assess_model, patch(
            "castlearq.run_service.ArtifactExecutionPreflight", return_value=self.preflight
        ), patch("castlearq.run_service.RuntimeBackendSelector", return_value=self.selector):
            assess_model.return_value = _compatible(self.model)
            _prepare(self.model, self.artifact, self.capability, self.model_store, admission=ADMITTING)
            assess_model.assert_called_once()

    def test_prepare_runs_preflight_once(self):
        with patch("castlearq.run_service.assess_model") as assess_model, patch(
            "castlearq.run_service.ArtifactExecutionPreflight", return_value=self.preflight
        ), patch("castlearq.run_service.RuntimeBackendSelector", return_value=self.selector):
            assess_model.return_value = _compatible(self.model)
            _prepare(self.model, self.artifact, self.capability, self.model_store, admission=ADMITTING)
            self.preflight.validate.assert_called_once_with(self.artifact)

    def test_prepare_runs_selection_once(self):
        with patch("castlearq.run_service.assess_model") as assess_model, patch(
            "castlearq.run_service.ArtifactExecutionPreflight", return_value=self.preflight
        ), patch("castlearq.run_service.RuntimeBackendSelector", return_value=self.selector):
            assess_model.return_value = _compatible(self.model)
            _prepare(self.model, self.artifact, self.capability, self.model_store, admission=ADMITTING)
            self.selector.select.assert_called_once()

    def test_prepare_returns_same_target_for_run_and_chat(self):
        with patch("castlearq.run_service.assess_model") as assess_model, patch(
            "castlearq.run_service.ArtifactExecutionPreflight", return_value=self.preflight
        ), patch("castlearq.run_service.RuntimeBackendSelector", return_value=self.selector):
            assess_model.return_value = _compatible(self.model)
            preparation = _prepare(
                self.model, self.artifact, self.capability, self.model_store,
                admission=ADMITTING,
            )
            self.assertEqual(
                preparation.target,
                ExecutionTarget("llama.cpp / llama.app", "Vulkan"),
            )
            self.assertIn("marginal", preparation.selection_warnings)

    def test_prepare_refuses_without_admission(self):
        # B9.78: the gate that refuses on this path is strict admission, not the
        # legacy compatibility verdict.
        with self.assertRaises(ExecuteAdmissionDeniedError):
            _prepare(self.model, self.artifact, self.capability, self.model_store)

    def test_legacy_incompatible_no_longer_refuses_preparation(self):
        # B9.78 (D1-A): the legacy verdict is selection recommendation data only.
        with patch("castlearq.run_service.assess_model") as assess_model, patch(
            "castlearq.run_service.ArtifactExecutionPreflight",
            return_value=self.preflight,
        ), patch(
            "castlearq.run_service.RuntimeBackendSelector", return_value=self.selector
        ):
            assess_model.return_value = CompatibilityResult(
                model=self.model,
                status=CompatibilityStatus.INCOMPATIBLE,
                score=0,
                reasons=("too large",),
                warnings=("will not fit",),
                estimated_memory_bytes=100 * 10**9,
                memory_is_estimate=True,
                recommended_quantization=None,
                recommended_runtime=None,
                recommended_backend=None,
            )
            preparation = _prepare(
                self.model, self.artifact, self.capability, self.model_store,
                admission=ADMITTING,
            )
            self.assertIn("will not fit", preparation.compatibility_warnings)

    def test_run_and_chat_both_call_prepare(self):
        """run_model and chat_model must both delegate to the shared _prepare."""
        from contextlib import redirect_stderr, redirect_stdout
        from castlearq.main import run_model, chat_model

        preparation = SimpleNamespace(
            executable_artifact=self.exe,
            target=ExecutionTarget("llama.cpp / llama.app", "Vulkan"),
            compatibility_warnings=(),
            selection_warnings=(),
        )

        # run_model path
        runner = Mock()
        runner.run.return_value = ExecutionResult(True, 0, "ok\n", "")
        output = io.StringIO()
        error = io.StringIO()
        with patch("castlearq.main.ModelArtifactResolver") as resolver, patch(
            "castlearq.main._prepare", return_value=preparation
        ) as prepare, patch("castlearq.main.LlamaCppRunner", return_value=runner), patch(
            "castlearq.main.detect_hardware"
        ), patch(
            "castlearq.main.detect_llama_capability"
        ), patch(
            "castlearq.main.detect_backends"
        ), redirect_stdout(
            output
        ), redirect_stderr(
            error
        ):
            resolver.return_value.resolve.return_value = self.resolved
            run_model("qwen2.5-coder-7b-instruct", "hello")
            self.assertTrue(prepare.called)

        # chat_model path
        session = Mock()
        session.state = SimpleNamespace(value="closed")
        session.send.return_value = SimpleNamespace(
            user="hi", assistant="Hello!", chunks=("Hello!",), metrics=None
        )
        with patch("castlearq.run_service.ModelArtifactResolver") as resolver, patch(
            "castlearq.main.detect_llama_capability", return_value=_invocable_capability()
        ), patch(
            "castlearq.run_service.prepare", return_value=preparation
        ) as prepare, patch(
            "castlearq.chat.start_chat_session", return_value=session
        ):
            resolver.return_value.resolve.return_value = self.resolved
            out = io.StringIO()
            err = io.StringIO()
            chat_model(
                "qwen2.5-coder-7b-instruct",
                out=out,
                err=err,
                input_fn=lambda: "/exit",
            )
            self.assertTrue(prepare.called)


if __name__ == "__main__":
    unittest.main()
