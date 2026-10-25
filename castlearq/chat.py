
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
from pathlib import Path
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


class ChatSessionConfigError(ChatSessionError):
    """Raised when a session is configured or used outside its limits."""


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

class OpenVINOChatSession(ChatSession):
    """Conservative OpenVINO chat session with explicit, per-session history.

    The session owns only its conversation history and turn lock. It does NOT
    own the underlying OpenVINO pipeline: ``OpenVINOInferenceService`` may
    cache a pipeline, so closing a session must not release resources that
    could belong to the service or to another session.
    """

    def __init__(
        self,
        manifest_path,
        *,
        device: str = "CPU",
        service,
        max_new_tokens: int = 8,
        max_transcript_chars: int = 4000,
    ) -> None:
        if isinstance(max_transcript_chars, bool) or not isinstance(max_transcript_chars, int):
            raise ChatSessionConfigError(
                "max_transcript_chars must be a positive integer, got "
                f"{type(max_transcript_chars).__name__}"
            )
        if max_transcript_chars <= 0:
            raise ChatSessionConfigError(
                f"max_transcript_chars must be positive, got {max_transcript_chars}"
            )
        self._manifest_path = Path(manifest_path)
        self._device = device
        self._service = service
        self._max_new_tokens = max_new_tokens
        self._max_transcript_chars = max_transcript_chars
        self._history: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._closed = False
        self._closed_lock = threading.Lock()
        self._closed_cv = threading.Condition(self._closed_lock)
        # Number of send() calls that have started a generation but have not yet
        # finished (they hold self._lock). close() waits until this is zero so
        # an in-flight turn completes before the service is shut down.
        self._active_sends = 0
        # Service ownership: this session creates (acquires) the service when it
        # is supplied from this phase (None means the owner passes one in).
        self._service_owned = True
        # Service close is invoked at most once even with concurrent close()
        # calls (see _close_service).
        self._service_closed = False
        self._service_closed_lock = threading.Lock()

    def _check_open(self) -> None:
        if self._closed:
            raise ChatSessionClosedError("session is closed")

    def send(self, prompt: str) -> ChatTurn:
        # The session lock serialises turns. Nothing may start a generation after
        # this session has been closed, so the closed state is checked here,
        # under the session lock.
        with self._lock:
            with self._closed_cv:
                if self._closed:
                    raise ChatSessionClosedError("session is closed")
                self._active_sends += 1
            try:
                # The current turn must fit on its own, with its role prefix, before
                # any older turn is considered for removal.
                current_transcript = "User: " + prompt + "\nAssistant:"
                if len(current_transcript) > self._max_transcript_chars:
                    raise ChatSessionConfigError(
                        "prompt exceeds max_transcript_chars "
                        f"({len(current_transcript)} > {self._max_transcript_chars})"
                    )
                # Keep the newest history turns until the full transcript (history
                # plus the current turn, with role prefixes) fits within the limit.
                # Older turns are dropped from the transcript, while the full
                # history stays intact on the session.
                selected = list(self._history)
                while True:
                    parts = []
                    for user_text, assistant_text in selected:
                        parts.append("User: " + user_text + "\nAssistant: " + assistant_text)
                    parts.append("User: " + prompt + "\nAssistant:")
                    full_prompt = "\n".join(parts)
                    if len(full_prompt) <= self._max_transcript_chars:
                        break
                    selected.pop(0)
                result = self._service.generate(
                    self._manifest_path,
                    full_prompt,
                    device=self._device,
                    max_new_tokens=self._max_new_tokens,
                )
                turn = ChatTurn(user=prompt, assistant=result.text)
                # Append only after a successful generation, never on failure.
                self._history.append((prompt, result.text))
                return turn
            finally:
                with self._closed_cv:
                    self._active_sends -= 1
                    self._closed_cv.notify_all()

    def _close_service(self) -> None:
        # Close the exclusive service exactly once. This method is idempotent
        # with respect to repeated calls on the same session.
        with self._service_closed_lock:
            if self._service_closed:
                return
            self._service_closed = True
        # Delegates to the service, which is responsible for its own pipeline
        # cache and resource release policy. OpenVINO native resource cleanup
        # is not assumed beyond this reference drop.
        self._service.close()

    def cancel(self) -> None:
        # OpenVINO GenAI generation is not cancellable through the current
        # service API. This is a documented no-op, not a real interruption.
        return None

    def close(self) -> None:
        # This method waits for active turns to finish before stopping the
        # service, so an in-flight send is allowed to complete normally.
        # The service is closed exactly once (and only by the closing session
        # that owns it). Concurrent close() calls never double-close the
        # service or deadlock: the closed state and the service-close flag are
        # guarded by their own locks and the block below runs at most once per
        # session.
        with self._closed_cv:
            # Wait until there are no active sends (each send holds the session
            # lock while generating). We are inside the closed condition's lock,
            # and send() only uses _closed_cv briefly under _lock, so the order
            # is: _lock (send) -> _closed_cv; _closed_cv (close) -> no reverse
            # acquisition, hence no lock ordering deadlock.
            if self._closed:
                while self._active_sends > 0:
                    self._closed_cv.wait()
                return
            # Mark as closing so no new sends are admitted.
            self._closed = True
            while self._active_sends > 0:
                self._closed_cv.wait()
            self._close_service()
            self._closed_cv.notify_all()

    @property
    def history(self) -> list[tuple[str, str]]:
        return list(self._history)
