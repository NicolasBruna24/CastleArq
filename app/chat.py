
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

"""Interactive one-session chat primitive (Fase 5, Bloque 1).

A single persistent ``llama cli`` process serves an entire conversation. The
model is loaded once per session; prompts are fed over stdin and the response
is read incrementally from stdout. The Fase 4 security guarantees are kept:
``shell=False``, a fixed structured ``argv``, the executable coming only from
``RuntimeCapability`` and the model path only from ``ExecutableArtifact``, a
controlled environment, and no auto-download or ModelStore mutation.

This module is strictly additive and does not touch the Fase 4 ``run`` path.
"""

from __future__ import annotations

import os
import re
import signal
import stat
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .execution import ExecutableArtifact, ExecutionTarget, RuntimeMetrics
from .runtime_metrics import parse_llama_human_output
from .runtimes import RuntimeCapability


class ChatSessionState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    GENERATING = "generating"
    CANCELING = "cancelling"
    CLOSED = "closed"
    FAILED = "failed"


class ChatSessionError(Exception):
    """Base error for interactive chat session failures."""


class ChatSessionClosedError(ChatSessionError):
    """Raised when an operation requires an open, usable session."""


class ChatLaunchError(ChatSessionError):
    """Raised when the runtime subprocess cannot be started or become ready."""


class ChatProcessError(ChatSessionError):
    """Raised when the runtime process dies or a pipe fails mid-turn."""


@dataclass(frozen=True)
class ChatTurn:
    """One completed user/assistant exchange of an interactive session."""

    user: str
    assistant: str
    chunks: tuple[str, ...] = ()
    metrics: RuntimeMetrics | None = None


ChunkCallback = Callable[[str], None]
PopenFactory = Callable[..., subprocess.Popen]


class ChatSession(ABC):
    """Minimal abstraction for a single interactive runtime session."""

    @abstractmethod
    def send(self, prompt: str) -> ChatTurn:
        """Submit one prompt and return the completed turn."""

    @abstractmethod
    def cancel(self) -> None:
        """Stop the in-progress generation, if any."""

    @abstractmethod
    def close(self) -> None:
        """Shut down the session, safe and idempotent."""


def start_chat_session(
    capability: RuntimeCapability,
    executable_artifact: ExecutableArtifact,
    target: ExecutionTarget,
    **kwargs: object,
) -> "LlamaCppChatSession":
    """Build a ready interactive session from already-selected inputs."""
    return LlamaCppChatSession(capability, executable_artifact, target, **kwargs)


def _ready_marker(txt: str) -> bool:
    """True when the accumulated stdout ends at the llama interactive marker."""
    lines = txt.rstrip().splitlines()
    return bool(lines) and lines[-1].strip() == ">"


def _is_end_of_turn(txt: str) -> bool:
    """A turn is complete once a valid metrics block and the ready marker appear.

    The llama runtime prints the metrics block exactly once, at the end of each
    response, immediately followed by the ``> `` prompt marker. Requiring both
    the metrics block (via the reused hardened parser) and a trailing ``> ``
    line avoids ending a turn early on a metrics-shaped substring generated
    inside the model output.
    """
    if parse_llama_human_output(txt) is None:
        return False
    return _ready_marker(txt)


def _extract_assistant(txt: str) -> str:
    """Strip the leading/trailing markers and the timing block from a turn."""
    start = txt.rfind("[ Prompt:")
    if start >= 0:
        end = txt.find("]", start)
        if end >= 0:
            txt = txt[:start]
    txt = re.sub(r"\s*\n?\s*>\s*$", "", txt)
    txt = re.sub(r"^\s*>\s*", "", txt)
    return txt.strip()


class LlamaCppChatSession(ChatSession):
    """A one-process interactive session over the local llama.cpp CLI."""

    def __init__(
        self,
        capability: RuntimeCapability,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        *,
        popen_factory: PopenFactory | None = None,
        chunk_callback: ChunkCallback | None = None,
        ready_timeout: float = 30.0,
        operation_timeout: float = 120.0,
        cancel_grace: float = 2.0,
        close_grace: float = 5.0,
    ) -> None:
        _validate_selected_inputs(capability, executable_artifact)
        if not isinstance(target, ExecutionTarget):
            raise ChatLaunchError("chat session requires an ExecutionTarget")

        device = capability.backend_argument(target.backend)
        if device is None:
            raise ChatLaunchError(
                "backend %r is not supported by the runtime capability"
                % target.backend
            )

        self._capability = capability
        self._artifact = executable_artifact
        self._target = target
        self._chunk_callback = chunk_callback
        self._ready_timeout = ready_timeout
        self._operation_timeout = operation_timeout
        self._cancel_grace = cancel_grace
        self._close_grace = close_grace
        self._argv = [
            capability.executable_path,
            "cli",
            "--model",
            str(executable_artifact.path),
            "--device",
            device,
            "--simple-io",
        ]

        self._state = ChatSessionState.STARTING
        self._state_lock = threading.Lock()
        self._buf = bytearray()
        self._buf_cond = threading.Condition()
        self._err = bytearray()
        self._err_lock = threading.Lock()
        self._turns: list[ChatTurn] = []
        self._closed_event = threading.Event()
        self._reader_threads: list[threading.Thread] = []

        factory: PopenFactory = popen_factory or subprocess.Popen
        try:
            self._proc = factory(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                env={"PATH": os.defpath},
            )
        except (OSError, PermissionError) as error:
            self._set_state(ChatSessionState.FAILED)
            raise ChatLaunchError("could not start runtime: %s" % error) from error

        self._start_reader(self._proc.stdout, self._append_stdout)
        self._start_reader(self._proc.stderr, self._append_stderr)
        self._wait_ready()
# -- lifecycle / state ---------------------------------------------------

    def _set_state(self, state: ChatSessionState) -> None:
        with self._state_lock:
            self._state = state

    @property
    def state(self) -> ChatSessionState:
        with self._state_lock:
            return self._state

    @property
    def turns(self) -> tuple[ChatTurn, ...]:
        with self._state_lock:
            return tuple(self._turns)

    @property
    def stderr_text(self) -> str:
        with self._err_lock:
            return bytes(self._err).decode("utf-8", "replace")

    def _pgid(self) -> int:
        try:
            return os.getpgid(self._proc.pid)
        except (OSError, AttributeError):
            return self._proc.pid

    def _signal_group(self, pgid: int, sig: int) -> None:
        try:
            os.killpg(pgid, sig)
        except OSError:
            # Process group already gone; nothing to signal.
            pass

    # -- readers -----------------------------------------------------------

    def _start_reader(self, stream: object, sink: Callable[[bytes], None]) -> None:
        def loop() -> None:
            while not self._closed_event.is_set():
                try:
                    data = os.read(stream.fileno(), 4096)  # type: ignore[union-attr]
                except OSError:
                    break
                if not data:
                    break
                sink(data)

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        self._reader_threads.append(thread)

    def _append_stdout(self, data: bytes) -> None:
        with self._buf_cond:
            self._buf += data
            self._buf_cond.notify_all()

    def _append_stderr(self, data: bytes) -> None:
        with self._err_lock:
            self._err += data

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self._ready_timeout
        while True:
            with self._buf_cond:
                txt = bytes(self._buf).decode("utf-8", "replace")
            if _ready_marker(txt):
                self._set_state(ChatSessionState.READY)
                return
            if self._proc.poll() is not None:
                raise ChatLaunchError("runtime exited before becoming ready")
            if time.monotonic() >= deadline:
                raise ChatLaunchError("runtime did not become ready in time")
            time.sleep(0.05)
# -- public API ---------------------------------------------------------

    def send(self, prompt: str) -> ChatTurn:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ChatSessionError("prompt must be a non-empty string")
        with self._state_lock:
            if self._state in (ChatSessionState.CLOSED, ChatSessionState.FAILED):
                raise ChatSessionClosedError("session is closed")
            if self._state != ChatSessionState.READY:
                raise ChatSessionError(
                    "session is not ready to accept a prompt (state=%s)"
                    % self._state.value
                )
            self._state = ChatSessionState.GENERATING

        try:
            if self._proc.poll() is not None:
                self._set_state(ChatSessionState.FAILED)
                raise ChatProcessError("runtime process is no longer running")
            self._proc.stdin.write(prompt.encode("utf-8") + b"\n")  # type: ignore[union-attr]
            self._proc.stdin.flush()  # type: ignore[union-attr]
        except (OSError, ValueError) as error:
            self._set_state(ChatSessionState.FAILED)
            raise ChatProcessError("could not write prompt: %s" % error) from error

        with self._buf_cond:
            snapshot = len(self._buf)
        chunks: list[str] = []
        delivered = 0
        deadline = time.monotonic() + self._operation_timeout
        while True:
            with self._buf_cond:
                txt = bytes(self._buf[snapshot:]).decode("utf-8", "replace")
            increment = txt[delivered:]
            if increment:
                chunks.append(increment)
                delivered = len(txt)
                if self._chunk_callback is not None:
                    self._chunk_callback(increment)
            if _is_end_of_turn(txt):
                break
            if self._proc.poll() is not None:
                with self._state_lock:
                    if self._state == ChatSessionState.GENERATING:
                        self._state = ChatSessionState.FAILED
                raise ChatProcessError(
                    "runtime process ended before turn completed"
                )
            if time.monotonic() >= deadline:
                self._set_state(ChatSessionState.FAILED)
                raise ChatSessionError("timed out waiting for the turn to complete")
            time.sleep(0.02)

        turn_bytes = bytes(self._buf[snapshot:])
        turn_text = turn_bytes.decode("utf-8", "replace")
        metrics = parse_llama_human_output(turn_text)
        assistant = _extract_assistant(turn_text)
        turn = ChatTurn(
            user=prompt,
            assistant=assistant,
            chunks=tuple(chunks),
            metrics=metrics,
        )
        with self._state_lock:
            self._turns.append(turn)
            self._state = ChatSessionState.READY
        return turn

    def cancel(self) -> None:
        with self._state_lock:
            state = self._state
        if state in (ChatSessionState.CLOSED, ChatSessionState.FAILED):
            raise ChatSessionClosedError("session is closed")
        if state == ChatSessionState.READY:
            # Nothing is generating; nothing to cancel.
            return
        if state == ChatSessionState.CANCELING:
            return
        self._set_state(ChatSessionState.CANCELING)
        pgid = self._pgid()
        self._signal_group(pgid, signal.SIGINT)
        deadline = time.monotonic() + self._cancel_grace
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                break
            time.sleep(0.05)
        if self._proc.poll() is None:
            self._signal_group(pgid, signal.SIGKILL)
            try:
                self._proc.wait(timeout=self._cancel_grace + 2)
            except subprocess.TimeoutExpired:
                pass
        else:
            try:
                self._proc.wait(timeout=self._cancel_grace)
            except subprocess.TimeoutExpired:
                pass
        if self._proc.poll() is None:
            self._set_state(ChatSessionState.READY)
        else:
            self._closed_event.set()
            self._set_state(ChatSessionState.CLOSED)

    def close(self) -> None:
        with self._state_lock:
            state = self._state
        if state == ChatSessionState.CLOSED:
            self._join_readers()
            return
        if self._proc.poll() is None:
            try:
                self._proc.stdin.write(b"/exit\n")  # type: ignore[union-attr]
                self._proc.stdin.flush()  # type: ignore[union-attr]
            except (OSError, ValueError):
                pass
            try:
                self._proc.stdin.close()  # type: ignore[union-attr]
            except (OSError, ValueError):
                pass
            try:
                self._proc.wait(timeout=self._close_grace)
            except subprocess.TimeoutExpired:
                pgid = self._pgid()
                self._signal_group(pgid, signal.SIGINT)
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._signal_group(pgid, signal.SIGKILL)
                    try:
                        self._proc.wait(timeout=self._close_grace)
                    except subprocess.TimeoutExpired:
                        pass
        self._closed_event.set()
        self._join_readers()
        self._set_state(ChatSessionState.CLOSED)

    def _join_readers(self, timeout: float = 2.0) -> None:
        for thread in self._reader_threads:
            thread.join(timeout=timeout)


def _validate_selected_inputs(
    capability: RuntimeCapability, artifact: ExecutableArtifact
) -> None:
    """Reject any capability/artifact that must never reach subprocess launch."""
    if not isinstance(capability, RuntimeCapability):
        raise ChatLaunchError("chat session requires a RuntimeCapability")
    if not isinstance(artifact, ExecutableArtifact):
        raise ChatLaunchError("chat session requires an ExecutableArtifact")

    exe = capability.executable_path
    if not exe:
        raise ChatLaunchError("no runtime executable is available")
    try:
        mode = os.lstat(exe).st_mode
    except FileNotFoundError as error:
        raise ChatLaunchError("runtime executable does not exist") from error
    except PermissionError as error:
        raise ChatLaunchError(f"runtime executable is not accessible: {error}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or not os.access(exe, os.X_OK):
        raise ChatLaunchError("runtime executable is not a regular executable file")

    path = artifact.path
    if not os.path.isabs(path):
        raise ChatLaunchError("validated artifact path must be absolute")
    try:
        amode = os.lstat(path).st_mode
    except FileNotFoundError as error:
        raise ChatLaunchError("validated artifact does not exist") from error
    if stat.S_ISLNK(amode) or not stat.S_ISREG(amode):
        raise ChatLaunchError("validated artifact is not a regular non-symlink file")
    if str(path).endswith(".part"):
        raise ChatLaunchError("partial artifacts cannot be executed")
    return None