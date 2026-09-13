"""Tests for the Fase 5 interactive chat primitive (Bloque 1).

No real inference runs here: every subprocess is simulated with a fake
``Popen`` built on real ``os.pipe()`` descriptors so the reader threads and
streaming behaviour are exercised for real.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest

import app.chat as chat_module
from app.chat import (
    ChatLaunchError,
    ChatProcessError,
    ChatSessionClosedError,
    ChatSessionState,
    LlamaCppChatSession,
    start_chat_session,
)
from app.execution import ExecutableArtifact, ExecutionTarget
from app.models import ArtifactSpec, ArtifactState
from app.runtimes import PromptInputMode, RuntimeCapability


BANNER = b"Loading model...\nlog: built with nothing useful\n> \n"
TIMING = b"[ Prompt: 68,9 t/s | Generation: 8,9 t/s ]\n"
EXE = "/tmp/fake-llama-cli"


def make_capability(exe_path: str = EXE) -> RuntimeCapability:
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path=exe_path,
        version="0.4.0-dev",
        supported_formats=("GGUF",),
        supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
    )


def make_artifact(tmp_path: Path) -> ExecutableArtifact:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    spec = ArtifactSpec(
        model_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        source="huggingface",
        repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename="model.gguf",
        state=ArtifactState.VERIFIED,
    )
    return ExecutableArtifact(
        artifact=spec,
        path=model,
        size_verified=True,
        checksum_verified=True,
    )


def make_target() -> ExecutionTarget:
    return ExecutionTarget(runtime="llama.cpp CLI", backend="CPU")


class _Writer:
    def __init__(self, fd: int) -> None:
        self._fd = fd

    def write(self, data: bytes) -> int:
        return os.write(self._fd, data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass


class _Reader:
    def __init__(self, fd: int) -> None:
        self._fd = fd

    def fileno(self) -> int:
        return self._fd


class FakeRuntime:
    """Simulated interactive llama process backed by real pipes."""

    def __init__(
        self,
        argv,
        *,
        respond: bool = True,
        chunks: tuple[bytes, ...] = (b"Hello ", b"there ", b"!"),
        **kwargs,
    ):
        self.argv = argv
        self.kwargs = kwargs
        self.stdin_r, self.stdin_w = os.pipe()
        self.stdout_r, self.stdout_w = os.pipe()
        self.stderr_r, self.stderr_w = os.pipe()
        self.pid = 90000 + (os.getpid() % 1000)
        self.stdin = _Writer(self.stdin_w)
        self.stdout = _Reader(self.stdout_r)
        self.stderr = _Reader(self.stderr_r)
        self.returncode: int | None = None
        self.stdin_lines: list[bytes] = []
        self._respond = respond
        self._chunks = chunks
        os.write(self.stdout_w, BANNER)
        if respond:
            threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        try:
            while True:
                line = b""
                while not line.endswith(b"\n"):
                    data = os.read(self.stdin_r, 1)
                    if not data:
                        return
                    line += data
                self.stdin_lines.append(line)
                if line.strip() == b"/exit":
                    self.returncode = 0
                    os.close(self.stdout_w)
                    return
                for chunk in self._chunks:
                    os.write(self.stdout_w, chunk)
                    time.sleep(0.02)
                os.write(self.stdout_w, b"\n" + TIMING + b"\n> \n")
        except OSError:
            return

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout=None) -> int:
        deadline = time.monotonic() + (timeout or 0)
        while self.returncode is None:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(self.argv, timeout)
            time.sleep(0.01)
        return self.returncode


@pytest.fixture()
def popen_log(monkeypatch):
    """Replace subprocess.Popen inside app.chat with a recording factory."""

    created: list = []
    options: dict = {"respond": True}
    killpg_calls: list[tuple[int, int]] = []

    def factory(argv, **kwargs):
        proc = FakeRuntime(argv, **options, **kwargs)
        created.append(proc)
        return proc

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))
        if sig == signal.SIGKILL and created:
            created[-1].returncode = -9

    monkeypatch.setattr(chat_module.subprocess, "Popen", factory)
    monkeypatch.setattr(chat_module.os, "killpg", fake_killpg)

    class Log:
        pass

    log = Log()
    log.created = created
    log.options = options
    log.killpg_calls = killpg_calls
    return log


def build_session(popen_log, tmp_path, **kwargs) -> LlamaCppChatSession:
    # The session validates the executable with a real lstat, so tests
    # provide a genuine executable stub file inside tmp_path.
    exe = tmp_path / "llama"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return start_chat_session(
        make_capability(str(exe)),
        make_artifact(tmp_path),
        make_target(),
        **kwargs,
    )

# -- construction, security and lifecycle ---------------------------------


def test_popen_called_once_with_secured_arguments(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.send("Hola")
    session.close()

    assert len(popen_log.created) == 1
    kwargs = popen_log.created[0].kwargs
    argv = popen_log.created[0].argv
    assert kwargs["shell"] is False
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.PIPE
    assert kwargs["env"] == {"PATH": os.defpath}
    assert argv == [
        str(tmp_path / "llama"),
        "cli",
        "--model",
        str(tmp_path / "model.gguf"),
        "--device",
        "none",
        "--simple-io",
    ]
    assert "--prompt" not in argv
    assert "--single-turn" not in argv


def test_multiple_turns_use_a_single_process(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.send("one")
    session.send("two")
    session.send("three")
    session.close()
    assert len(popen_log.created) == 1
    assert len(session.turns) == 3
    assert [t.user for t in session.turns] == ["one", "two", "three"]


def test_banner_is_not_part_of_the_first_turn(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    turn = session.send("Hello")
    session.close()
    assert "Loading model" not in turn.assistant
    assert turn.assistant == "Hello there !"
    assert turn.metrics is not None
    assert turn.metrics.prompt_tokens_per_second == 68.9
    assert turn.metrics.generation_tokens_per_second == 8.9


def test_streaming_delivers_incremental_chunks(popen_log, tmp_path):
    seen: list[str] = []
    session = build_session(popen_log, tmp_path, chunk_callback=seen.append)
    turn = session.send("Hello")
    session.close()
    assert len(turn.chunks) >= 3
    assert "".join(turn.chunks) == "Hello there !\n" + TIMING.decode() + "\n> \n"
    assert seen  # callback observed increments as well


def test_send_rejects_empty_and_non_string_prompts(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    with pytest.raises(chat_module.ChatSessionError):
        session.send("   ")
    with pytest.raises(chat_module.ChatSessionError):
        session.send(123)  # type: ignore[arg-type]
    session.close()


def test_send_after_close_fails(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.close()
    with pytest.raises(ChatSessionClosedError):
        session.send("too late")


def test_close_is_idempotent(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.send("one")
    session.close()
    session.close()
    session.close()
    assert session.state == ChatSessionState.CLOSED


def test_close_sends_exit_command(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.send("one")
    session.close()
    proc = popen_log.created[0]
    assert b"/exit\n" in proc.stdin_lines


def test_cancel_sends_sigint_then_sigkill_to_the_group(popen_log, tmp_path):
    popen_log.options["respond"] = False  # runtime never answers
    session = build_session(
        popen_log, tmp_path, operation_timeout=5.0, cancel_grace=0.2
    )

    outcome: dict = {}

    def run_send():
        try:
            session.send("hang forever")
        except chat_module.ChatSessionError as error:
            outcome["error"] = error

    thread = threading.Thread(target=run_send)
    thread.start()
    for _ in range(200):
        if session.state == ChatSessionState.GENERATING:
            break
        time.sleep(0.01)
    session.cancel()
    thread.join(timeout=5)

    signals = [sig for _, sig in popen_log.killpg_calls]
    assert signal.SIGINT in signals
    assert signal.SIGKILL in signals
    assert signals.index(signal.SIGINT) < signals.index(signal.SIGKILL)
    assert session.state in (ChatSessionState.CLOSED, ChatSessionState.FAILED)


def test_cancel_without_generation_is_a_noop(popen_log, tmp_path):
    session = build_session(popen_log, tmp_path)
    session.cancel()  # READY: nothing generating
    assert session.state == ChatSessionState.READY
    session.close()


# -- input validation ------------------------------------------------------


def test_symlinked_executable_is_rejected(tmp_path):
    real = tmp_path / "real-llama"
    real.write_text("#!/bin/sh\n")
    real.chmod(0o755)
    link = tmp_path / "llama-link"
    os.symlink(real, link)
    capability = make_capability()
    object.__setattr__(capability, "executable_path", str(link))
    with pytest.raises(ChatLaunchError):
        start_chat_session(capability, make_artifact(tmp_path), make_target())


def test_part_artifact_is_rejected(tmp_path):
    model = tmp_path / "model.gguf.part"
    model.write_bytes(b"gguf")
    spec = ArtifactSpec(
        model_id="m",
        source="huggingface",
        repository="r",
        filename="model.gguf.part",
        state=ArtifactState.VERIFIED,
    )
    artifact = ExecutableArtifact(
        artifact=spec, path=model, size_verified=True, checksum_verified=True
    )
    with pytest.raises(ChatLaunchError):
        start_chat_session(make_capability(), artifact, make_target())


def test_missing_executable_is_rejected(tmp_path):
    capability = make_capability()
    object.__setattr__(capability, "executable_path", "/nonexistent/llama")
    with pytest.raises(ChatLaunchError):
        start_chat_session(capability, make_artifact(tmp_path), make_target())


def test_unsupported_backend_is_rejected(tmp_path):
    with pytest.raises(ChatLaunchError):
        start_chat_session(
            make_capability(),
            make_artifact(tmp_path),
            ExecutionTarget(runtime="llama.cpp CLI", backend="CUDA"),
        )



# =====================================================================
# Fase 5 — Bloque 2: multi-turn session hardening
# =====================================================================


def _timing(index: int) -> bytes:
    return (
        f"[ Prompt: {50 + index},{index} t/s | Generation: {8},{index} t/s ]\n"
    ).encode()


class ScriptedRuntime(FakeRuntime):
    """Interactive fake that answers each turn from a scripted sequence."""

    def __init__(self, argv, *, script=None, stderr_noise=False, **kwargs):
        self.script = list(script or [])
        self.stderr_noise = stderr_noise
        super().__init__(argv, respond=False, **kwargs)
        if self.script:
            threading.Thread(target=self._serve_scripted, daemon=True).start()

    def _serve_scripted(self) -> None:
        try:
            while True:
                line = b""
                while not line.endswith(b"\n"):
                    data = os.read(self.stdin_r, 1)
                    if not data:
                        return
                    line += data
                self.stdin_lines.append(line)
                if line.strip() == b"/exit":
                    self.returncode = 0
                    os.close(self.stdout_w)
                    return
                turns = len(self.stdin_lines) - 1
                chunks = (
                    self.script[turns] if turns < len(self.script) else (b"? ",)
                )
                for chunk in chunks:
                    os.write(self.stdout_w, chunk)
                    time.sleep(0.01)
                if self.stderr_noise:
                    os.write(self.stderr_w, b"runtime-diagnostic-only\n")
                os.write(self.stdout_w, b"\n" + _timing(turns) + b"\n> \n")
        except OSError:
            return


@pytest.fixture()
def scripted_factory(monkeypatch):
    """Recording Popen factory returning ScriptedRuntime instances."""

    created: list = []
    settings: dict = {"script": None, "stderr_noise": False}
    killpg_calls: list[tuple[int, int]] = []

    def factory(argv, **kwargs):
        proc = ScriptedRuntime(
            argv, script=settings["script"],
            stderr_noise=settings["stderr_noise"], **kwargs,
        )
        created.append(proc)
        return proc

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))
        if sig == signal.SIGKILL and created:
            created[-1].returncode = -9

    monkeypatch.setattr(chat_module.subprocess, "Popen", factory)
    monkeypatch.setattr(chat_module.os, "killpg", fake_killpg)

    class Log:
        pass

    log = Log()
    log.created = created
    log.settings = settings
    log.killpg_calls = killpg_calls
    return log


def build_scripted_session(log, tmp_path, **kwargs) -> LlamaCppChatSession:
    exe = tmp_path / "llama"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return start_chat_session(
        make_capability(str(exe)),
        make_artifact(tmp_path),
        make_target(),
        **kwargs,
    )


def scripted_response(tag: str) -> tuple[bytes, ...]:
    return (
        f"{tag} part-1 ".encode(),
        f"{tag} part-2 ".encode(),
        f"{tag} part-3".encode(),
    )


def test_multi_turn_single_process_and_ordered_stdin(
    scripted_factory, tmp_path
):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
        scripted_response("three"),
    ]
    session = build_scripted_session(log, tmp_path)
    session.send("T1")
    session.send("T2")
    session.send("T3")
    session.close()

    assert len(log.created) == 1  # exactly one runtime process
    stdin_lines = log.created[0].stdin_lines
    assert stdin_lines == [b"T1\n", b"T2\n", b"T3\n", b"/exit\n"]


def test_each_turn_maps_to_its_own_prompt_and_response(
    scripted_factory, tmp_path
):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
        scripted_response("three"),
    ]
    session = build_scripted_session(log, tmp_path)
    t1, t2, t3 = session.send("T1"), session.send("T2"), session.send("T3")
    session.close()

    assert [t.user for t in session.turns] == ["T1", "T2", "T3"]
    assert t1.assistant == "one part-1 one part-2 one part-3"
    assert t2.assistant == "two part-1 two part-2 two part-3"
    assert t3.assistant == "three part-1 three part-2 three part-3"



def test_streaming_and_callback_are_turn_scoped(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
    ]
    seen: list[str] = []
    session = build_scripted_session(log, tmp_path, chunk_callback=seen.append)

    turn1 = session.send("T1")
    one_chunks = tuple(turn1.chunks)
    turn2 = session.send("T2")
    two_chunks = tuple(turn2.chunks)
    session.close()

    assert len(one_chunks) >= 2 and len(two_chunks) >= 2
    one_text = "".join(one_chunks)
    two_text = "".join(two_chunks)
    assert "two" not in one_text  # no T2 content leaked into T1
    assert "one" not in two_text  # no T1 content leaked into T2
    # The callback saw chunks from both turns, in arrival order.
    assert any("one" in c for c in seen) and any("two" in c for c in seen)


def test_context_is_delegated_to_the_runtime_process(
    scripted_factory, tmp_path
):
    log = scripted_factory
    # The scripted runtime "answers from history", like the real runtime's KV.
    log.settings["script"] = [
        ("Encantado, Nicolás. ".encode(),),
        ("Tu nombre es Nicolás. ".encode(),),
    ]
    session = build_scripted_session(log, tmp_path)
    session.send("Mi nombre es Nicolás.")
    answer = session.send("¿Cuál es mi nombre?")
    session.close()

    assert answer.assistant == "Tu nombre es Nicolás."
    # Both prompts were delivered to the SAME process stdin, in order.
    assert log.created[0].stdin_lines == [
        "Mi nombre es Nicolás.\n".encode(),
        "¿Cuál es mi nombre?\n".encode(),
        b"/exit\n",
    ]


def test_state_transitions_across_turns(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
    ]
    session = build_scripted_session(log, tmp_path)
    assert session.state == ChatSessionState.READY
    assert log.created[0].stdin_lines == []  # no write before READY

    states = [session.state]
    turn = session.send("T1")
    states.append(session.state)  # READY again after a completed turn
    session.send("T2")
    states.append(session.state)
    session.close()
    states.append(session.state)

    assert states == [
        ChatSessionState.READY,
        ChatSessionState.READY,
        ChatSessionState.READY,
        ChatSessionState.CLOSED,
    ]
    assert turn is not None


def test_cancel_from_ready_state_keeps_session_usable(
    scripted_factory, tmp_path
):
    log = scripted_factory
    log.settings["script"] = [scripted_response("one")]
    session = build_scripted_session(log, tmp_path)
    session.cancel()
    assert session.state == ChatSessionState.READY
    turn = session.send("T1")  # session survives a spurious cancel
    session.close()
    assert turn.assistant.startswith("one")



def test_invalid_prompts_never_reach_the_process(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [scripted_response("one")]
    session = build_scripted_session(log, tmp_path)
    with pytest.raises(chat_module.ChatSessionError):
        session.send("")
    with pytest.raises(chat_module.ChatSessionError):
        session.send("   ")
    with pytest.raises(chat_module.ChatSessionError):
        session.send(None)  # type: ignore[arg-type]
    with pytest.raises(chat_module.ChatSessionError):
        session.send(123)  # type: ignore[arg-type]
    assert log.created[0].stdin_lines == []  # nothing was written
    turn = session.send("T1")  # still usable after rejected prompts
    session.close()
    assert turn.user == "T1"


def test_cancel_during_partial_generation_leaves_session_coherent(
    scripted_factory, tmp_path
):
    log = scripted_factory
    session = build_scripted_session(
        log, tmp_path, cancel_grace=0.2, operation_timeout=5.0
    )
    # A runtime that emits partial output and then hangs: never scripted.
    proc = log.created[0]
    threading.Thread(
        target=lambda: os.write(proc.stdout_w, b"partial "), daemon=True
    ).start()

    outcome: dict = {}

    def run_send():
        try:
            session.send("T1")
        except chat_module.ChatSessionError as error:
            outcome["error"] = error

    thread = threading.Thread(target=run_send)
    thread.start()
    for _ in range(200):
        if session.state == ChatSessionState.GENERATING:
            break
        time.sleep(0.01)
    session.cancel()
    thread.join(timeout=5)

    signals = [sig for _, sig in log.killpg_calls]
    assert signals[0] == signal.SIGINT
    # SIGKILL only arrives when the runtime ignored the graceful signal.
    if signal.SIGKILL in signals:
        assert session.state in (ChatSessionState.CLOSED, ChatSessionState.FAILED)
        assert isinstance(outcome.get("error"), ChatProcessError)
    else:
        assert session.state == ChatSessionState.READY
    assert proc.poll() is not None or session.state == ChatSessionState.READY
    assert len(log.created) == 1  # no restart, no fallback


def test_close_after_multiple_turns_is_single_process_and_idempotent(
    scripted_factory, tmp_path
):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
        scripted_response("three"),
    ]
    session = build_scripted_session(log, tmp_path)
    session.send("T1")
    session.send("T2")
    session.send("T3")
    session.close()
    session.close()
    session.close()
    assert len(log.created) == 1
    assert session.state == ChatSessionState.CLOSED
    assert log.created[0].returncode == 0


def test_dead_process_is_detected_without_restart(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [scripted_response("one")]
    session = build_scripted_session(log, tmp_path)
    session.send("T1")
    # Simulate the runtime dying after T1, before T2.
    proc = log.created[0]
    proc.returncode = 0
    os.close(proc.stdout_w)
    os.close(proc.stderr_w)

    with pytest.raises(ChatProcessError):
        session.send("T2")

    assert session.state == ChatSessionState.FAILED
    assert len(log.created) == 1  # no automatic restart, no fallback
    with pytest.raises(ChatSessionClosedError):
        session.send("T3")
    session.close()  # still safe to close


def test_metrics_stay_per_turn(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [
        scripted_response("one"), scripted_response("two"),
    ]
    session = build_scripted_session(log, tmp_path)
    turn1 = session.send("T1")
    turn2 = session.send("T2")
    session.close()

    assert turn1.metrics is not None and turn2.metrics is not None
    assert turn1.metrics.prompt_tokens_per_second == 50.0
    assert turn1.metrics.generation_tokens_per_second == 8.0
    assert turn2.metrics.prompt_tokens_per_second == 51.1
    assert turn2.metrics.generation_tokens_per_second == 8.1


def test_stderr_stays_separate_from_assistant(scripted_factory, tmp_path):
    log = scripted_factory
    log.settings["script"] = [scripted_response("one")]
    log.settings["stderr_noise"] = True
    session = build_scripted_session(log, tmp_path)
    turn = session.send("T1")
    session.close()

    assert "runtime-diagnostic-only" not in turn.assistant
    assert "runtime-diagnostic-only" in session.stderr_text

