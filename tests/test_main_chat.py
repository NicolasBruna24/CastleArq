
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

"""CLI tests for the Fase 5 ``chat`` command (Bloque 3).

No real inference: the pipeline is patched at the ``app.main`` seams and the
session is a fake, mirroring the Fase 4 CLI test style.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

import app.main as main_module
import app.run_service as run_service_module
from app.chat import ChatProcessError
from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execution import ExecutableArtifact
from app.main import chat_model
from app.models import ArtifactSpec, ArtifactState, ModelSpec, Quantization
from app.runtimes import PromptInputMode, RuntimeCapability
from app.selection import RuntimeSelectionError, SelectionErrorCode


def make_capability(tmp_path):
    exe = tmp_path / "llama"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return RuntimeCapability(
        name="llama.cpp / llama.app",
        executable_path=str(exe),
        version="0.4.0-dev",
        supported_formats=("GGUF",),
        supported_backends=("CPU",),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        backend_arguments=(("CPU", "none"),),
    )


class FakeSession:
    def __init__(self, capability, artifact, target, chunk_callback=None):
        self.capability = capability
        self.artifact = artifact
        self.target = target
        self.chunk_callback = chunk_callback
        self.sent: list[str] = []
        self.cancel_count = 0
        self.close_count = 0
        self.state_value = "ready"
        self.script = ["Hello world!"]

    def send(self, prompt):
        self.sent.append(prompt)
        index = len(self.sent) - 1
        text = self.script[index] if index < len(self.script) else "ok."
        for chunk in (text[:6], text[6:]):
            if self.chunk_callback:
                self.chunk_callback(chunk)
        return SimpleNamespace(
            user=prompt,
            assistant=text,
            chunks=(text,),
            metrics=None,
        )

    def cancel(self):
        self.cancel_count += 1

    def close(self):
        self.close_count += 1

    @property
    def state(self):
        return SimpleNamespace(value=self.state_value)


@pytest.fixture()
def pipeline(tmp_path, monkeypatch):
    """Patch the chat pipeline seams inside app.main."""

    capability = make_capability(tmp_path)
    model = ModelSpec(
        name="Qwen2.5 Coder 7B Instruct",
        provider="Qwen",
        format="GGUF",
    )
    artifact = ArtifactSpec(
        model_id=model.name,
        source="huggingface",
        repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename="model.gguf",
        format="GGUF",
        state=ArtifactState.VERIFIED,
    )
    compatibility = CompatibilityResult(
        model=model,
        status=CompatibilityStatus.COMPATIBLE,
        score=100,
        reasons=(),
        warnings=(),
        estimated_memory_bytes=None,
        memory_is_estimate=False,
        recommended_quantization=Quantization(
            name="Q4_K_M", bits_per_parameter=4.5, quality=4
        ),
        recommended_runtime="llama.cpp / llama.app",
        recommended_backend="CPU",
    )
    sessions: list[FakeSession] = []

    def factory(capability, artifact, target, chunk_callback=None):
        session = FakeSession(capability, artifact, target, chunk_callback)
        sessions.append(session)
        return session

    class FakeResolver:
        def __init__(self, store):
            pass

        def resolve(self, model_id, *, quantization=None, filename=None):
            return SimpleNamespace(model=model, artifact=artifact)

    class FakePreflight:
        def __init__(self, store):
            pass

        def validate(self, artifact):
            return ExecutableArtifact(
                artifact=artifact,
                path=tmp_path / "model.gguf",
                size_verified=True,
                checksum_verified=True,
            )

    monkeypatch.setattr(main_module, "ModelStore", lambda: object())
    monkeypatch.setattr(main_module, "ModelArtifactResolver", FakeResolver)
    monkeypatch.setattr(
        run_service_module, "detect_hardware", lambda: SimpleNamespace(gpus=())
    )
    monkeypatch.setattr(
        main_module, "detect_llama_capability", lambda: capability
    )
    monkeypatch.setattr(
        run_service_module,
        "assess_model",
        lambda *args, **kwargs: compatibility,
    )
    monkeypatch.setattr(run_service_module, "ArtifactExecutionPreflight", FakePreflight)
    return SimpleNamespace(
        capability=capability,
        artifact=artifact,
        sessions=sessions,
        factory=factory,
    )


def make_inputs(lines):
    iterator = iter(lines)

    def input_fn(prompt=""):
        try:
            return next(iterator)
        except StopIteration:
            raise EOFError from None

    return input_fn


def run_chat(pipeline, lines, **kwargs):
    out = io.StringIO()
    code = chat_model(
        "some-model",
        input_fn=make_inputs(lines),
        out=out,
        err=io.StringIO(),
        session_factory=pipeline.factory,
        **kwargs,
    )
    return code, out.getvalue()


def test_chat_runs_multi_turn_over_one_session(pipeline):
    code, output = run_chat(pipeline, ["hello", "second", "third", "/exit"])
    assert code == 0
    assert len(pipeline.sessions) == 1
    session = pipeline.sessions[0]
    assert session.sent == ["hello", "second", "third"]
    assert session.close_count == 1
    assert "Session closed." in output


def test_chat_exit_command_is_not_sent_to_the_model(pipeline):
    code, output = run_chat(pipeline, ["/exit"])
    assert code == 0
    assert pipeline.sessions[0].sent == []
    assert pipeline.sessions[0].close_count == 1


def test_chat_streams_chunks_incrementally(pipeline):
    code, output = run_chat(pipeline, ["hello", "/exit"])
    assert code == 0
    assert "Hello " in output
    assert "world!" in output
    assert "you> " in output  # prompt markers present


def test_chat_eof_closes_the_session(pipeline):
    code, output = run_chat(pipeline, [])
    assert code == 0
    assert pipeline.sessions[0].sent == []
    assert pipeline.sessions[0].close_count == 1


def test_chat_missing_model_id_returns_usage_error(pipeline):
    code = chat_model(
        None,
        input_fn=make_inputs([]),
        out=io.StringIO(),
        err=io.StringIO(),
        session_factory=pipeline.factory,
    )
    assert code == 2


def test_chat_ctrl_c_during_generation_calls_cancel(pipeline):
    session_holder: dict = {}

    def factory(*args, **kwargs):
        session = pipeline.factory(*args, **kwargs)
        original_send = session.send

        def interrupting_send(text):
            raise KeyboardInterrupt

        session.send = interrupting_send
        session_holder["session"] = session
        return session

    calls = {"count": 0}

    def input_fn(prompt=""):
        calls["count"] += 1
        if calls["count"] == 1:
            return "hola"
        raise EOFError

    code = chat_model(
        "some-model",
        input_fn=input_fn,
        out=io.StringIO(),
        err=io.StringIO(),
        session_factory=factory,
    )
    session = session_holder["session"]
    assert session.cancel_count == 1
    assert session.close_count == 1
    assert code == 0


def test_chat_error_during_turn_stops_without_restart(pipeline):
    def factory(*args, **kwargs):
        session = pipeline.factory(*args, **kwargs)
        original_send = session.send

        def failing_send(prompt):
            if session.sent:
                raise ChatProcessError("runtime process ended unexpectedly")
            original_send(prompt)

        session.send = failing_send
        return session

    out = io.StringIO()
    err = io.StringIO()
    code = chat_model(
        "some-model",
        input_fn=make_inputs(["ok", "boom"]),
        out=out,
        err=err,
        session_factory=factory,
    )
    assert code == 0  # handled gracefully; session closed cleanly
    assert "Chat error" in err.getvalue()
    assert len(pipeline.sessions) == 1  # no second session / no restart


def test_chat_resolution_failure_returns_1(pipeline, monkeypatch):
    from app.resolver import ModelArtifactResolutionError

    class FailingResolver:
        def __init__(self, store):
            pass

        def resolve(self, model_id, *, quantization=None, filename=None):
            raise ModelArtifactResolutionError("model not found")

    monkeypatch.setattr(main_module, "ModelArtifactResolver", FailingResolver)
    err = io.StringIO()
    code = chat_model(
        "unknown-model",
        input_fn=make_inputs([]),
        out=io.StringIO(),
        err=err,
        session_factory=pipeline.factory,
    )
    assert code == 1
    assert "model not found" in err.getvalue()


def test_chat_preflight_failure_returns_1(pipeline, monkeypatch):
    from app.execution import ArtifactPreflightError, PreflightErrorCode

    class FailingPreflight:
        def __init__(self, store):
            pass

        def validate(self, artifact):
            raise ArtifactPreflightError(
                PreflightErrorCode.MISSING_ARTIFACT, "final artifact missing"
            )

    monkeypatch.setattr(
        run_service_module, "ArtifactExecutionPreflight", FailingPreflight
    )
    err = io.StringIO()
    code = chat_model(
        "some-model",
        input_fn=make_inputs([]),
        out=io.StringIO(),
        err=err,
        session_factory=pipeline.factory,
    )
    assert code == 1
    assert "final artifact missing" in err.getvalue()


def test_chat_selection_failure_returns_1(pipeline, monkeypatch):
    class FailingSelector:
        def select(self, *args, **kwargs):
            raise RuntimeSelectionError(
                SelectionErrorCode.BACKEND_UNSUPPORTED,
                "Recommended backend is not supported by the runtime",
            )

    monkeypatch.setattr(run_service_module, "RuntimeBackendSelector", FailingSelector)
    err = io.StringIO()
    code = chat_model(
        "some-model",
        input_fn=make_inputs([]),
        out=io.StringIO(),
        err=err,
        session_factory=pipeline.factory,
    )
    assert code == 1
    assert "backend" in err.getvalue()


def test_chat_unavailable_runtime_returns_1(pipeline, monkeypatch, tmp_path):
    unavailable = make_capability(tmp_path)
    object.__setattr__(unavailable, "available", False)
    monkeypatch.setattr(
        main_module, "detect_llama_capability", lambda: unavailable
    )
    err = io.StringIO()
    code = chat_model(
        "some-model",
        input_fn=make_inputs([]),
        out=io.StringIO(),
        err=err,
        session_factory=pipeline.factory,
    )
    assert code == 1
    assert "no invocable runtime" in err.getvalue()
    assert len(pipeline.sessions) == 0  # never reached the session

