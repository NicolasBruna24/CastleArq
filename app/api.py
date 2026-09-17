
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

"""Local HTTP API (Fase 6.1, bloques 1-3.4).

Transport: ``http.server.ThreadingHTTPServer`` + ``BaseHTTPRequestHandler``
(stdlib only; no third-party dependencies).

Architecture: HTTP is a thin transport over the existing application/core
layer. This module never calls the CLI and never executes shell commands.
It reuses the catalog (``app.model_catalog``), the identity mapping
(``app.model_identity``) and the local artifact store (``app.model_store``)
directly, and maps their results into explicit API DTOs.

Block 1 endpoints (read-only):

- ``GET /health``      -> liveness + project version.
- ``GET /v1/models``   -> catalog models with safe, API-appropriate fields.
- ``GET /v1/artifacts``-> locally stored artifacts, deterministic order.

Block 2 endpoint:

- ``POST /v1/run``     -> one-shot execution through the shared run
  pipeline (``app.run_service.run_once``), guarded by one global
  execution lock: a second concurrent run gets HTTP 409.

Block 3.1 endpoints (chat session lifecycle):

- ``POST /v1/chat/sessions``          -> open a session through the shared
  chat pipeline (``app.run_service.open_chat_session``); HTTP 201.
- ``GET /v1/chat/sessions/{id}``      -> session metadata (no history yet).
- ``DELETE /v1/chat/sessions/{id}``   -> ``session.close()`` + unregister;
  204 when the session exists and is idle, 409 while it is processing a turn
  (full contract in the handler docstring).

Block 3.2 endpoint (turns, per-session concurrency):

- ``POST /v1/chat/sessions/{id}/turns`` -> one prompt on a live session,
  submitted through the session's own ``send()`` (the existing state machine
  in ``app.chat`` decides what a session accepts); HTTP 200 with
  ``session_id``, ``response`` and ``turn_count``.

  Exclusion is strictly per session: every registered session owns one turn
  slot (``_ChatSessionEntry.turn_lock``) claimed non-blockingly for the whole
  generation, so a second concurrent turn for the same session is rejected
  immediately with HTTP 409 while different sessions run independently (there
  is no server-wide turn lock, and no queue, scheduling or retry). A turn is
  counted only after a successful generation, and ``turn_count`` is read from
  the session's own completed-turn log rather than a parallel API counter.
  ``DELETE`` uses the same slot, so a session whose turn is generating is
  reported as busy (409) instead of being closed underneath it. Sessions live
  only in memory, are capped by ``MAX_CHAT_SESSIONS`` and are closed in an
  orderly fashion when the server shuts down. Streaming/SSE, OpenAI
  compatibility, downloads via API, auth/TLS, persistence, job queues and
  Ollama integration are NOT part of this block.

Block 3.3 (lifecycle hardening, shutdown gate):

- ``_ChatSessionRegistry.close_all()`` flips a shutdown gate in the same
  critical section that drains the map, and ``register()`` checks that gate
  under the same lock. A create request racing shutdown therefore has exactly
  two deterministic outcomes: its already-registered session is closed by
  ``close_all()``, or its registration is rejected and the create handler
  closes the just-launched session immediately (503). No session or runtime
  can outlive the shutdown as an orphan, and once the gate is set no new
  session can ever be registered (create answers 503 "server is shutting
  down"). ``close_all()`` never waits for in-flight turns.

Block 3.4 (contract & reliability hardening):

- ``Content-Length: 0`` (or a missing Content-Length) on any POST that shares
  ``_read_json_body`` (``/v1/run``, session create, turns) now answers a
  deterministic 400 ``"request body is required"`` instead of silently closing
  the connection. Invalid/oversized/read-error bodies keep their own answers
  and never get a second response.
- Error messages match the session's observable state: a FAILED session
  answers 409 ``"chat session has failed"`` (GET reports ``status: failed``);
  a CLOSED session keeps answering 409 ``"chat session is closed"``. No new
  states, codes or exception hierarchy.
- Infrastructure error paths are traced in the log (module logger
  ``castlearq.api``): failed session closes in ``close_all``/``server_close``,
  a released-unheld turn slot, and expected client disconnects mid-turn.
  Prompts and client payloads are never logged.

Safety rules enforced here:

- The server only binds loopback interfaces (default ``127.0.0.1``);
  non-loopback hosts are rejected explicitly at construction time.
- DTOs never expose local paths, argv, environment or internal objects.
- Errors are reported as JSON without stack traces.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import threading
import tomllib
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .chat import ChatSessionClosedError, ChatSessionError
from .model_catalog import get_catalog
from .model_identity import downloadable_locator
from .model_store import ModelStore, StoredArtifact
from .models import ModelSpec
from .run_service import (
    ChatDependencies,
    ChatLaunchFailedError,
    ChatSessionOpened,
    ModelNotFoundError,
    RunDependencies,
    RunExecutionFailedError,
    RunOutcome,
    RunPreparationFailedError,
    open_chat_session,
    run_once,
)

# Module-level logger for infrastructure paths that run outside a request
# handler (registry bookkeeping, shutdown) and therefore cannot use the
# handler's ``log_error``. Only failure details are logged, never prompts or
# client payloads.
_LOG = logging.getLogger("castlearq.api")

__all__ = [
    "APIConfigurationError",
    "ArtifactDTO",
    "MAX_CHAT_SESSIONS",
    "MAX_REQUEST_BODY_BYTES",
    "DRAIN_CAP_BYTES",
    "ChatSessionRequestDTO",
    "ChatSessionResponseDTO",
    "ChatTurnRequestDTO",
    "ChatTurnResponseDTO",
    "ModelDTO",
    "RunRequestDTO",
    "RunResponseDTO",
    "build_server",
    "get_version",
    "list_artifact_dtos",
    "list_model_dtos",
    "parse_chat_session_request",
    "parse_chat_turn_request",
    "serve",
]

# Requests are GET-only in this block; a generous limit guards against
# oversized (or future) request bodies even though GET carries no body.
MAX_REQUEST_BODY_BYTES = 1024 * 1024

# After an early 413 the announced body is drained (discarded, never kept)
# so the client can finish sending and reliably read the response instead
# of hitting a TCP RST mid-upload (BrokenPipeError). ``DRAIN_CAP_BYTES``
# bounds how much we are ever willing to consume: a body slightly over the
# limit is drained; a Content-Length beyond the cap is refused with the
# 413 and an immediate connection close — draining it would reward abuse.
# The cap is comfortably above the request limit (never a memory copy: the
# bytes are discarded chunk by chunk).
DRAIN_CAP_BYTES = 8 * 1024 * 1024
_DRAIN_CHUNK_BYTES = 64 * 1024


def _drain_request_body(rfile, length: int) -> None:
    """Discard an announced request body after an early rejection.

    Reads at most ``min(length, DRAIN_CAP_BYTES)`` bytes in small chunks and
    drops them immediately (nothing is accumulated in memory), so a client
    that is still uploading can finish sending and reliably read the 413
    instead of receiving a TCP reset mid-send. A Content-Length beyond
    ``DRAIN_CAP_BYTES`` is never drained at all: the connection is simply
    closed, since consuming unbounded input would reward abuse. Read errors
    are swallowed — the 413 was already sent; the connection closes anyway.
    """
    if length > DRAIN_CAP_BYTES:
        return
    remaining = length
    try:
        while remaining > 0:
            chunk = rfile.read(min(remaining, _DRAIN_CHUNK_BYTES))
            if not chunk:
                break
            remaining -= len(chunk)
            del chunk  # discarded immediately; never accumulated
    except OSError:
        pass

# Block 3.1: hard cap on concurrent in-memory chat sessions. Small on
# purpose (each session holds a loaded model process); no dynamic config yet.
MAX_CHAT_SESSIONS = 4

_LOOPBACK_HOSTNAMES = frozenset({"localhost"})


class APIConfigurationError(Exception):
    """Raised when the API server would be configured unsafely."""


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def _pyproject_path() -> Path:
    return Path(__file__).resolve().parent.parent / "pyproject.toml"


def get_version() -> str:
    """Return the project version from the existing source of truth.

    The version lives in ``pyproject.toml``; this reads it at runtime so the
    API never duplicates (and drifts from) that single source. Falls back to
    ``"unknown"`` if the file cannot be read or parsed.
    """
    try:
        data = tomllib.loads(_pyproject_path().read_text(encoding="utf-8"))
        version = data["project"]["version"]
        return str(version) if version else "unknown"
    except (OSError, KeyError, TypeError, ValueError):
        return "unknown"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelDTO:
    """API-safe projection of one catalog :class:`ModelSpec`.

    Contains only static catalog metadata and the downloadability predicate
    from ``app.model_identity``. No paths, argv, environment or runtime
    objects are exposed.
    """

    model_id: str
    name: str
    provider: str
    family: str
    task: str
    architecture: str
    parameter_count_b: float | None
    context_length: int | None
    supported_runtimes: tuple[str, ...]
    supported_backends: tuple[str, ...]
    quantizations: tuple[str, ...]
    downloadable: bool
    download_source: str | None
    download_repository: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "provider": self.provider,
            "family": self.family,
            "task": self.task,
            "architecture": self.architecture,
            "parameter_count_b": self.parameter_count_b,
            "context_length": self.context_length,
            "supported_runtimes": list(self.supported_runtimes),
            "supported_backends": list(self.supported_backends),
            "quantizations": list(self.quantizations),
            "downloadable": self.downloadable,
            "download_source": self.download_source,
            "download_repository": self.download_repository,
        }


@dataclass(frozen=True)
class ArtifactDTO:
    """API-safe projection of one locally stored artifact.

    ``model_id``/``filename``/... are ``None`` for entries whose manifest
    could not be inspected. ``message`` only ever carries the store's own
    short, path-free inspection notes; entries with an unparseable manifest
    are collapsed to the generic ``"invalid manifest"`` note because their
    raw error text may embed absolute paths.
    """

    model_id: str | None
    filename: str | None
    quantization: str | None
    size_bytes: int | None
    state: str
    artifact_id: str | None
    message: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "filename": self.filename,
            "quantization": self.quantization,
            "size_bytes": self.size_bytes,
            "state": self.state,
            "artifact_id": self.artifact_id,
            "message": self.message,
        }


_RUN_REQUEST_FIELDS = frozenset(
    {"model_id", "prompt", "quantization", "filename", "timeout"}
)


@dataclass(frozen=True)
class RunRequestDTO:
    """Validated ``POST /v1/run`` input. Only process-safe selection fields."""

    model_id: str
    prompt: str
    quantization: str | None = None
    filename: str | None = None
    timeout: float | None = None


@dataclass(frozen=True)
class RunResponseDTO:
    """API-safe projection of a successful run (never argv/env/paths)."""

    model_id: str
    output: str
    exit_code: int | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "output": self.output,
            "exit_code": self.exit_code,
            "warnings": list(self.warnings),
        }


def parse_run_request(payload: object) -> RunRequestDTO:
    """Validate raw JSON into a :class:`RunRequestDTO` or raise ``ValueError``."""
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = sorted(set(payload) - _RUN_REQUEST_FIELDS)
    if unknown:
        raise ValueError(f"unknown field: {unknown[0]}")
    for required in ("model_id", "prompt"):
        if required not in payload:
            raise ValueError(f"missing required field: {required}")
    model_id = payload["model_id"]
    prompt = payload["prompt"]
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    quantization = payload.get("quantization")
    if quantization is not None and (
        not isinstance(quantization, str) or not quantization.strip()
    ):
        raise ValueError("quantization must be a non-empty string")
    filename = payload.get("filename")
    if filename is not None and (
        not isinstance(filename, str) or not filename.strip()
    ):
        raise ValueError("filename must be a non-empty string")
    timeout = payload.get("timeout")
    if timeout is not None:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout != timeout  # NaN
            or timeout in (float("inf"), float("-inf"))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive number")
        timeout = float(timeout)
    return RunRequestDTO(
        model_id=model_id,
        prompt=prompt,
        quantization=quantization,
        filename=filename,
        timeout=timeout,
    )


@dataclass(frozen=True)
class ChatSessionRequestDTO:
    """Validated ``POST /v1/chat/sessions`` payload (logical selectors only)."""

    model_id: str
    quantization: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class ChatSessionResponseDTO:
    """Safe session metadata; never carries paths, argv, env or processes."""

    session_id: str
    model_id: str
    status: str
    turn_count: int = 0

    def to_create_json(self) -> dict:
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "status": self.status,
        }

    def to_json(self) -> dict:
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "status": self.status,
            "turn_count": self.turn_count,
        }


@dataclass(frozen=True)
class ChatTurnRequestDTO:
    """Validated ``POST /v1/chat/sessions/{id}/turns`` payload.

    Deliberately minimal for this block: a single prompt, nothing else.
    """

    prompt: str


@dataclass(frozen=True)
class ChatTurnResponseDTO:
    """API-safe projection of one completed turn (never paths or processes)."""

    session_id: str
    response: str
    turn_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "response": self.response,
            "turn_count": self.turn_count,
        }


_CHAT_SESSION_ALLOWED_FIELDS = frozenset({"model_id", "quantization", "filename"})


def parse_chat_session_request(payload: object) -> ChatSessionRequestDTO:
    """Validate a chat-session creation payload with run-style strictness."""
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = sorted(set(payload) - _CHAT_SESSION_ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"unknown field: {unknown[0]}")
    model_id = payload.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    quantization = payload.get("quantization")
    if quantization is not None and (
        not isinstance(quantization, str) or not quantization.strip()
    ):
        raise ValueError("quantization must be a non-empty string when provided")
    filename = payload.get("filename")
    if filename is not None and (
        not isinstance(filename, str) or not filename.strip()
    ):
        raise ValueError("filename must be a non-empty string when provided")
    return ChatSessionRequestDTO(
        model_id=model_id.strip(),
        quantization=quantization.strip() if quantization is not None else None,
        filename=filename.strip() if filename is not None else None,
    )


_CHAT_TURN_ALLOWED_FIELDS = frozenset({"prompt"})


def parse_chat_turn_request(payload: object) -> ChatTurnRequestDTO:
    """Validate a chat-turn payload with the same run-style strictness.

    Only a single non-empty string ``prompt`` is accepted: no coercion (e.g.
    ``{"prompt": 123}`` is rejected, never stringified) and no unknown fields.
    """
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = sorted(set(payload) - _CHAT_TURN_ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"unknown field: {unknown[0]}")
    if "prompt" not in payload:
        raise ValueError("missing required field: prompt")
    prompt = payload["prompt"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    return ChatTurnRequestDTO(prompt=prompt)


def parse_session_id(raw: str) -> str:
    """Validate a ``{session_id}`` path segment as a server-issued UUID."""
    candidate = (raw or "").strip()
    if not candidate:
        raise ValueError("session_id must be a non-empty string")
    try:
        return str(uuid.UUID(candidate, version=4))
    except (ValueError, AttributeError, TypeError) as error:
        raise ValueError(f"invalid session_id: {raw!r}") from error


def _public_chat_status(session: Any) -> str:
    """Map the internal session state to the public lifecycle vocabulary."""
    state = getattr(session, "state", None)
    value = getattr(state, "value", state)
    text = str(value) if value is not None else ""
    mapping = {
        "starting": "starting",
        "ready": "ready",
        "generating": "generating",
        "cancelling": "canceling",
        "canceling": "canceling",
        "closed": "closed",
        "failed": "failed",
    }
    return mapping.get(text.strip().lower(), "ready")


def _session_turn_count(session: Any) -> int:
    turns = getattr(session, "turns", ())
    try:
        return int(len(turns))
    except TypeError:
        return 0


@dataclass
class _ChatSessionEntry:
    """One live session plus its per-session turn slot (Block 3.2).

    ``turn_lock`` provides the per-session mutual exclusion: at most one turn
    may generate on a session at a time. It is only acquired/released through
    the registry, never held across the registry lock, and it is independent
    per session (there is no server-wide turn lock).
    """

    session: Any
    model_id: str
    turn_lock: threading.Lock = field(default_factory=threading.Lock)


class _ChatSessionLimitReached(Exception):
    """Internal signal: the registry is at MAX_CHAT_SESSIONS."""


class _ChatSessionNotFound(Exception):
    """Internal signal: no live session is registered under that id."""


class _ChatSessionBusy(Exception):
    """Internal signal: the session is already processing a turn."""


class _ChatRegistryClosing(Exception):
    """Internal signal: shutdown started; no new session may be registered."""


class _ChatSessionRegistry:
    """Thread-safe in-memory store of live chat sessions (no persistence)."""

    def __init__(self, max_sessions: int = MAX_CHAT_SESSIONS) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _ChatSessionEntry] = {}
        self._max_sessions = max_sessions
        # Block 3.3 shutdown gate: flipped under ``self._lock`` by
        # ``close_all()`` and checked under the same lock by ``register()``,
        # so the gate and the drain are atomic with respect to registration.
        self._closing = False

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def is_full(self) -> bool:
        with self._lock:
            return len(self._sessions) >= self._max_sessions

    def is_closing(self) -> bool:
        """``True`` once shutdown has started (no new registrations accepted)."""
        with self._lock:
            return self._closing

    def register(self, session_id: str, entry: _ChatSessionEntry) -> None:
        """Register a freshly launched session, or raise.

        Raises :class:`_ChatRegistryClosing` once shutdown started (Block 3.3
        invariant 1) and :class:`_ChatSessionLimitReached` at capacity. In the
        shutdown case the caller must close the launched session immediately
        (see :meth:`close_all` for why no session can be orphaned either way).
        """
        with self._lock:
            if self._closing:
                raise _ChatRegistryClosing
            if len(self._sessions) >= self._max_sessions:
                raise _ChatSessionLimitReached
            self._sessions[session_id] = entry

    def get(self, session_id: str) -> _ChatSessionEntry | None:
        with self._lock:
            return self._sessions.get(session_id)

    def begin_turn(self, session_id: str) -> _ChatSessionEntry:
        """Claim the session's turn slot for one generation, or raise.

        The registry lock is held only for the non-blocking claim, so no
        thread ever waits on it while a generation runs and different sessions
        never influence each other. Raises :class:`_ChatSessionNotFound` for an
        unknown id and :class:`_ChatSessionBusy` when a turn is already in
        progress (the caller answers 409 immediately; there is no queue).

        The caller must always release the slot with :meth:`end_turn`.
        """
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                raise _ChatSessionNotFound(session_id)
            if not entry.turn_lock.acquire(blocking=False):
                raise _ChatSessionBusy(session_id)
            return entry

    def end_turn(self, entry: _ChatSessionEntry) -> None:
        """Release a claimed turn slot; never raises (safe on double release)."""
        try:
            entry.turn_lock.release()
        except RuntimeError as error:
            # Already released: never propagate, but leave a trace — a real
            # double release would be a bookkeeping bug worth noticing.
            _LOG.warning("end_turn released an unheld turn slot: %s", error)

    def claim_for_removal(self, session_id: str) -> _ChatSessionEntry:
        """Atomically unregister an idle session and return it.

        Uses the same per-session claim as :meth:`begin_turn`, so a session
        generating a turn is never removed/closed underneath it (the caller
        answers 409 for a busy session). Raises :class:`_ChatSessionNotFound`
        for an unknown id. The caller must call :meth:`end_turn` once the
        session has been closed.

        Close invariant (shared with :meth:`close_all`): the entry is deleted
        from the registry *before* ``session.close()`` runs, so
        ``session.close()`` is only ever invoked on sessions that are already
        unreachable by :meth:`begin_turn`. Preserve this order: closing a
        session that is still registered would race the session's own state
        machine in ``app.chat`` (``send()`` may set ``READY`` after
        ``close()`` set ``CLOSED``), so a future ``cancel``/force-delete must
        unregister first and close afterwards.
        """
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                raise _ChatSessionNotFound(session_id)
            if not entry.turn_lock.acquire(blocking=False):
                raise _ChatSessionBusy(session_id)
            # Unregister before returning: the caller closes the session only
            # after this point (see the close invariant above).
            del self._sessions[session_id]
            return entry

    def close_all(self) -> None:
        """Close every registered session; one bad session never blocks others.

        Ordering invariant shared with :meth:`claim_for_removal`: the map is
        cleared *before* any ``entry.session.close()`` is called, so every
        closed session has already been unregistered (``begin_turn`` can no
        longer reach it) and no close happens on a session that is still
        registered. Shutdown deliberately does not take the per-session turn
        slots: an in-flight turn is expected to fail on its own when its
        runtime disappears, and the API must not wait for it.

        Shutdown gate (Block 3.3): ``_closing`` is flipped inside the *same*
        critical section that drains the map. Because :meth:`register` checks
        the flag under that same lock, exactly one of two orderings is possible
        for a registration racing the drain:

        - the register wins: the entry is already in the map before the clear,
          so ``close_all`` closes it;
        - the drain wins: ``register`` sees ``_closing`` and raises
          :class:`_ChatRegistryClosing`, so the create handler closes the
          launched session immediately.

        Either way a session launched by a losing create request is closed
        exactly once and nothing can be registered after this method returns
        (invariants 1, 3, 12 and 13 of Block 3.3).
        """
        with self._lock:
            self._closing = True
            entries = list(self._sessions.items())
            self._sessions.clear()
        for session_id, entry in entries:
            try:
                entry.session.close()
            except Exception as error:
                # One bad session never blocks the others, but a close
                # failure may leave a runtime process alive: log it.
                _LOG.warning(
                    "close_all: closing chat session %s failed: %r",
                    session_id, error)


def run_response_from_outcome(outcome: RunOutcome) -> RunResponseDTO:
    """Project a :class:`RunOutcome` into its API-safe DTO."""
    return RunResponseDTO(
        model_id=outcome.model_id,
        output=outcome.output,
        exit_code=outcome.exit_code,
        warnings=tuple(outcome.warnings),
    )


def _model_dto(spec: ModelSpec) -> ModelDTO:
    locator = downloadable_locator(spec.model_id)
    downloadable = locator is not None
    source, repository = locator if locator else (None, None)
    return ModelDTO(
        model_id=spec.model_id,
        name=spec.name,
        provider=spec.provider,
        family=spec.family,
        task=spec.task,
        architecture=spec.architecture,
        parameter_count_b=spec.parameter_count_b,
        context_length=spec.context_length,
        supported_runtimes=tuple(spec.supported_runtimes),
        supported_backends=tuple(spec.supported_backends),
        quantizations=tuple(q.name for q in spec.quantizations),
        downloadable=downloadable,
        download_source=source,
        download_repository=repository,
    )


def _artifact_dto(entry: StoredArtifact) -> ArtifactDTO:
    artifact = entry.artifact
    if artifact is None:
        return ArtifactDTO(
            model_id=None,
            filename=None,
            quantization=None,
            size_bytes=None,
            state=entry.state.value,
            artifact_id=None,
            message="invalid manifest" if entry.message else None,
        )
    return ArtifactDTO(
        model_id=artifact.model_id,
        filename=artifact.filename,
        quantization=artifact.quantization,
        size_bytes=artifact.size_bytes,
        state=entry.state.value,
        artifact_id=artifact.artifact_id,
        message=entry.message,
    )


def list_model_dtos(catalog: tuple[ModelSpec, ...] | None = None) -> list[ModelDTO]:
    """Map the (static, offline) catalog into API DTOs."""
    specs = catalog if catalog is not None else get_catalog()
    return [_model_dto(spec) for spec in specs]


def list_artifact_dtos(store: ModelStore) -> list[ArtifactDTO]:
    """Map the local artifact store into deterministic API DTOs.

    Valid artifacts are sorted by ``(model_id, filename, artifact_id)``;
    invalid manifests are listed last, ordered by their (unexposed) manifest
    path so the result is fully deterministic.
    """
    entries = store.list_artifacts()
    valid = sorted(
        (entry for entry in entries if entry.artifact is not None),
        key=lambda e: (e.artifact.model_id, e.artifact.filename, e.artifact.artifact_id),
    )
    invalid = sorted(
        (entry for entry in entries if entry.artifact is None),
        key=lambda e: str(e.manifest_path),
    )
    return [_artifact_dto(entry) for entry in (*valid, *invalid)]


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

_JSON_CONTENT_TYPE = "application/json; charset=utf-8"


def _json_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")


def _make_handler(
    catalog: tuple[ModelSpec, ...],
    store: ModelStore,
    version: str,
    run_dependencies: RunDependencies | None,
    run_lock: threading.Lock,
    chat_dependencies: ChatDependencies | None = None,
    chat_registry: _ChatSessionRegistry | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Build a handler class with the injected core dependencies."""
    from urllib.parse import urlsplit

    sessions = chat_registry if chat_registry is not None else _ChatSessionRegistry()

    class APIRequestHandler(BaseHTTPRequestHandler):
        server_version = "CastleArq/" + version
        sys_version = ""

        def _send_json(
            self, status: int, payload: dict[str, object], *, allow: str | None = None
        ) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", _JSON_CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            if allow is not None:
                self.send_header("Allow", allow)
            self.end_headers()
            self.wfile.write(body)

        def _reject_body(self) -> bool:
            """GET carries no body in this block; enforce the request limit."""
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return False
            try:
                length = int(raw_length)
            except ValueError:
                length = -1
            if length > MAX_REQUEST_BODY_BYTES:
                self._send_json(413, {"error": "request body too large"})
                return True
            if length > 0:
                self._send_json(400, {"error": "GET requests must not include a body"})
                return True
            return False

        def _dispatch_get(self) -> None:
            path = urlsplit(self.path).path
            if path == "/health":
                self._send_json(200, {"status": "ok", "version": version})
            elif path == "/v1/models":
                payload = {"models": [dto.to_dict() for dto in list_model_dtos(catalog)]}
                self._send_json(200, payload)
            elif path == "/v1/artifacts":
                payload = {"artifacts": [dto.to_dict() for dto in list_artifact_dtos(store)]}
                self._send_json(200, payload)
            elif path.startswith("/v1/chat/sessions/"):
                remainder = path[len("/v1/chat/sessions/"):]
                if not remainder or "/" in remainder:
                    self._send_json(404, {"error": "not found"})
                    return
                try:
                    session_id = parse_session_id(remainder)
                except ValueError as error:
                    self._send_json(400, {"error": str(error)})
                    return
                entry = sessions.get(session_id)
                if entry is None:
                    self._send_json(404, {"error": "chat session not found"})
                    return
                dto = ChatSessionResponseDTO(
                    session_id=session_id,
                    model_id=entry.model_id,
                    status=_public_chat_status(entry.session),
                    turn_count=_session_turn_count(entry.session),
                )
                self._send_json(200, dto.to_json())
            else:
                self._send_json(404, {"error": "not found"})

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            try:
                if self._reject_body():
                    return
                self._dispatch_get()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:  # never leak details to the client
                self.log_error("internal error handling %s: %r", self.path, error)
                try:
                    self._send_json(500, {"error": "internal server error"})
                except OSError:
                    pass

        def _read_body(self) -> bytes | None:
            """Read the request body, enforcing the 1 MiB limit.

            Returns ``None`` when there is no body or when an error
            response was already sent (invalid/oversized Content-Length).
            In the latter case ``self._body_error_sent`` is set so
            ``_read_json_body`` does not send a second response.
            """
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None
            try:
                length = int(raw_length)
            except ValueError:
                self._body_error_sent = True
                self._send_json(400, {"error": "invalid Content-Length"})
                return None
            if length < 0:
                self._body_error_sent = True
                self._send_json(400, {"error": "invalid Content-Length"})
                return None
            if length > MAX_REQUEST_BODY_BYTES:
                self._body_error_sent = True
                self._send_json(413, {"error": "request body too large"})
                # Let the client finish its upload and read the 413 instead
                # of closing on its in-flight bytes (TCP RST → client-side
                # BrokenPipeError). Bounded; oversized beyond the cap closes
                # immediately without consuming abusive input.
                _drain_request_body(self.rfile, length)
                return None
            if length == 0:
                return None
            try:
                return self.rfile.read(length)
            except OSError:
                self._body_error_sent = True
                self._send_json(400, {"error": "could not read request body"})
                return None

        def _read_json_body(self) -> object | None:
            raw = self._read_body()
            if raw is None:
                # Deterministic answer for a request without a body: a missing
                # Content-Length and a ``Content-Length: 0`` are both an empty
                # body (Block 3.4), and the client always gets a 400 instead of
                # a silently closed connection. Nothing extra is sent when
                # ``_read_body`` already answered (invalid length / 413 / read
                # error).
                if not getattr(self, "_body_error_sent", False):
                    self._send_json(400, {"error": "request body is required"})
                return None
            if not raw.strip():
                self._send_json(400, {"error": "request body is required"})
                return None
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self._send_json(400, {"error": "invalid JSON"})
                return None

        def _handle_run(self) -> None:
            """Validate ``POST /v1/run`` and execute it under the global lock."""
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";")[0].strip().lower()
            if media_type != "application/json":
                self._send_json(
                    400, {"error": "Content-Type must be application/json"}
                )
                return
            payload = self._read_json_body()
            if payload is None:
                return
            try:
                request = parse_run_request(payload)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            if not run_lock.acquire(blocking=False):
                self._send_json(
                    409, {"error": "another execution is already running"}
                )
                return
            try:
                outcome = run_once(
                    request.model_id,
                    request.prompt,
                    quantization=request.quantization,
                    filename=request.filename,
                    timeout_seconds=request.timeout,
                    dependencies=run_dependencies,
                )
            except ModelNotFoundError as error:
                self._send_json(404, {"error": str(error)})
                return
            except RunPreparationFailedError as error:
                self._send_json(422, {"error": str(error)})
                return
            except RunExecutionFailedError as error:
                self._send_json(503, {"error": str(error)})
                return
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as error:  # never leak details to the client
                self.log_error("internal error handling %s: %r", self.path, error)
                try:
                    self._send_json(500, {"error": "internal server error"})
                except OSError:
                    pass
                return
            finally:
                run_lock.release()
            self._send_json(200, run_response_from_outcome(outcome).to_dict())

        def _handle_chat_create(self) -> None:
            """Validate ``POST /v1/chat/sessions`` and open one session."""
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";")[0].strip().lower()
            if media_type != "application/json":
                self._send_json(
                    400, {"error": "Content-Type must be application/json"}
                )
                return
            payload = self._read_json_body()
            if payload is None:
                return
            try:
                request = parse_chat_session_request(payload)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            if sessions.is_closing():
                # Block 3.3: a create request that arrives after shutdown has
                # started is answered deterministically instead of launching a
                # session that would race the registry drain.
                self._send_json(
                    503, {"error": "server is shutting down"})
                return
            if sessions.is_full():
                self._send_json(
                    409, {"error": "maximum chat sessions reached"}
                )
                return
            try:
                opened = open_chat_session(
                    request.model_id,
                    quantization=request.quantization,
                    filename=request.filename,
                    dependencies=chat_dependencies,
                )
            except ModelNotFoundError as error:
                self._send_json(404, {"error": str(error)})
                return
            except RunPreparationFailedError as error:
                self._send_json(422, {"error": str(error)})
                return
            except ChatLaunchFailedError as error:
                self.log_error("chat session launch failed: %r", error)
                self._send_json(503, {"error": "chat runtime failed to start"})
                return
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as error:  # never leak details to the client
                self.log_error("internal error handling %s: %r", self.path, error)
                try:
                    self._send_json(500, {"error": "internal server error"})
                except OSError:
                    pass
                return
            # Register only after a successful launch; never a partial entry.
            session_id = str(uuid.uuid4())
            try:
                sessions.register(
                    session_id,
                    _ChatSessionEntry(
                        session=opened.session, model_id=opened.model_id
                    ),
                )
            except _ChatSessionLimitReached:
                try:
                    opened.session.close()
                except Exception:
                    pass
                self._send_json(409, {"error": "maximum chat sessions reached"})
                return
            except _ChatRegistryClosing:
                # Block 3.3: shutdown drained the registry between the launch
                # and this registration. Close the launched session right here
                # (it exists only in this handler frame) so it cannot outlive
                # the shutdown as an orphan; the answer is deterministic 503.
                try:
                    opened.session.close()
                except Exception:
                    pass
                self.log_error(
                    "chat session creation raced shutdown; session discarded")
                self._send_json(503, {"error": "server is shutting down"})
                return
            dto = ChatSessionResponseDTO(
                session_id=session_id,
                model_id=opened.model_id,
                status=_public_chat_status(opened.session),
            )
            self._send_json(201, dto.to_create_json())

        def _handle_chat_delete(self, raw_id: str) -> None:
            """``DELETE /v1/chat/sessions/{id}`` contract (Blocks 3.1 + 3.2).

            - ``204``: the session exists and is idle. ``claim_for_removal``
              unregisters it and ``session.close()`` runs exactly once.
            - ``409``: the session is processing a turn, i.e. another request
              holds its per-session turn slot while the session is still
              registered. The session stays registered and usable, and the
              busy message is the same one the turn endpoint uses.
            - ``404``: no session is registered under that id.
            - ``400``: the ``session_id`` is not a valid session id.

            Two concurrent DELETEs cannot produce a 409: the winner
            unregisters the entry inside the same registry-lock section in
            which it claims the turn slot, so the loser sees the session
            already gone (404) and never closes it. Only an in-flight turn
            (which keeps the entry registered while holding the slot) can
            yield the 409 above.

            The session's turn slot is claimed first (same per-session
            exclusion as a turn), so a session that is generating is reported
            as busy instead of being closed underneath an in-flight turn. The
            session is always unregistered before it is closed (see the close
            invariant in :meth:`_ChatSessionRegistry.claim_for_removal`).
            """
            try:
                session_id = parse_session_id(raw_id)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            try:
                entry = sessions.claim_for_removal(session_id)
            except _ChatSessionNotFound:
                self._send_json(404, {"error": "chat session not found"})
                return
            except _ChatSessionBusy:
                self._send_json(
                    409, {"error": "chat session is already processing a turn"}
                )
                return
            try:
                try:
                    entry.session.close()
                except Exception as error:
                    self.log_error("chat session close failed: %r", error)
                    self._send_json(500, {"error": "internal server error"})
                    return
            finally:
                # Always release the slot: no lock may survive the request.
                sessions.end_turn(entry)
            self.send_response(204)
            self.end_headers()

        def _handle_chat_turn(self, raw_id: str) -> None:
            """Validate ``POST /v1/chat/sessions/{id}/turns`` and run one turn.

            The session's own ``send()`` owns the state machine (ready /
            generating / closed / failed); this handler only maps its outcome
            to HTTP. At most one turn per session may generate at a time: the
            turn slot is claimed non-blockingly, so a second concurrent turn
            for the same session is rejected immediately with 409 while other
            sessions keep running.
            """
            try:
                session_id = parse_session_id(raw_id)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";")[0].strip().lower()
            if media_type != "application/json":
                self._send_json(
                    400, {"error": "Content-Type must be application/json"}
                )
                return
            payload = self._read_json_body()
            if payload is None:
                return
            try:
                request = parse_chat_turn_request(payload)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            try:
                entry = sessions.begin_turn(session_id)
            except _ChatSessionNotFound:
                self._send_json(404, {"error": "chat session not found"})
                return
            except _ChatSessionBusy:
                self._send_json(
                    409, {"error": "chat session is already processing a turn"}
                )
                return
            try:
                try:
                    turn = entry.session.send(request.prompt)
                    # Count only completed generations, read from the
                    # session's own turn log (no parallel API counter).
                    turn_count = _session_turn_count(entry.session)
                except ChatSessionClosedError:
                    # Block 3.4: the message must match the session's
                    # observable state (GET reports ``status``), without
                    # inventing new states or codes. ``app.chat`` raises this
                    # exception for both CLOSED and FAILED sessions; the
                    # exception text itself is never echoed to the client.
                    if getattr(entry.session.state, "value", None) == "failed":
                        self._send_json(
                            409, {"error": "chat session has failed"})
                    else:
                        self._send_json(
                            409, {"error": "chat session is closed"})
                    return
                except ChatSessionError as error:
                    # Includes ChatProcessError: the runtime died or the turn
                    # timed out. Details stay in the server log.
                    self.log_error("chat turn failed: %r", error)
                    self._send_json(
                        503, {"error": "chat runtime failed to generate a response"}
                    )
                    return
                except (BrokenPipeError, ConnectionResetError):
                    # Expected client disconnect mid-generation: one log line
                    # for traceability (the generation result is lost), no
                    # prompt data, no second response attempt.
                    _LOG.info(
                        "client disconnected during chat turn %s", session_id)
                    return
                except Exception as error:  # never leak details to the client
                    self.log_error(
                        "internal error handling %s: %r", self.path, error
                    )
                    try:
                        self._send_json(500, {"error": "internal server error"})
                    except OSError:
                        pass
                    return
            finally:
                # Released on success, on failure and on client disconnect.
                sessions.end_turn(entry)
            dto = ChatTurnResponseDTO(
                session_id=session_id,
                response=turn.assistant,
                turn_count=turn_count,
            )
            self._send_json(200, dto.to_dict())

        def do_POST(self) -> None:  # noqa: N802 (http.server naming)
            try:
                path = urlsplit(self.path).path
                if path == "/v1/run":
                    self._handle_run()
                    return
                if path == "/v1/chat/sessions":
                    self._handle_chat_create()
                    return
                if path.startswith("/v1/chat/sessions/"):
                    remainder = path[len("/v1/chat/sessions/"):]
                    parts = remainder.split("/")
                    if len(parts) == 2 and parts[1] == "turns":
                        self._handle_chat_turn(parts[0])
                        return
                # POST is only defined for /v1/run, chat session creation and
                # chat turns; everything else keeps Block 1 behaviour (405).
                self._method_not_allowed()
                return
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:  # never leak details to the client
                self.log_error("internal error handling %s: %r", self.path, error)
                try:
                    self._send_json(500, {"error": "internal server error"})
                except OSError:
                    pass

        def _method_not_allowed(self) -> None:
            self._send_json(
                405, {"error": "method not allowed"}, allow="GET, POST"
            )

        def do_DELETE(self) -> None:  # noqa: N802 (http.server naming)
            try:
                path = urlsplit(self.path).path
                if path.startswith("/v1/chat/sessions/"):
                    remainder = path[len("/v1/chat/sessions/"):]
                    if not remainder or "/" in remainder:
                        self._send_json(404, {"error": "not found"})
                        return
                    self._handle_chat_delete(remainder)
                    return
                self._method_not_allowed()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:  # never leak details to the client
                self.log_error("internal error handling %s: %r", self.path, error)
                try:
                    self._send_json(500, {"error": "internal server error"})
                except OSError:
                    pass

        do_PUT = _method_not_allowed  # noqa: N802
        do_PATCH = _method_not_allowed  # noqa: N802
        do_HEAD = _method_not_allowed  # noqa: N802
        do_OPTIONS = _method_not_allowed  # noqa: N802

    return APIRequestHandler


# ---------------------------------------------------------------------------
# Server construction
# ---------------------------------------------------------------------------


class _APIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args: Any, chat_registry: _ChatSessionRegistry | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chat_registry = chat_registry

    def server_close(self) -> None:
        # Orderly shutdown: close every live chat session (each close is the
        # existing idempotent session.close(); one bad session never blocks
        # the others) before releasing the listening socket.
        registry = self._chat_registry
        if registry is not None:
            try:
                registry.close_all()
            except Exception as error:
                # Shutdown must never crash on registry cleanup, but a failed
                # cleanup can leave orphaned sessions/runtimes: log it.
                _LOG.warning(
                    "server_close: chat registry cleanup failed: %r", error)
        super().server_close()


def _validate_loopback_host(host: str) -> str:
    candidate = (host or "").strip()
    if not candidate:
        raise APIConfigurationError("host must not be empty")
    if candidate.lower() in _LOOPBACK_HOSTNAMES:
        return candidate
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as error:
        raise APIConfigurationError(
            f"host must be a loopback interface, got: {candidate!r}"
        ) from error
    if not address.is_loopback:
        raise APIConfigurationError(
            f"host must be a loopback interface, got: {candidate!r}"
        )
    return candidate


def build_server(
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    catalog: tuple[ModelSpec, ...] | None = None,
    model_store: ModelStore | None = None,
    run_dependencies: RunDependencies | None = None,
    chat_dependencies: ChatDependencies | None = None,
    chat_registry: _ChatSessionRegistry | None = None,
) -> ThreadingHTTPServer:
    """Build the API server (not yet serving).

    ``port=0`` binds an ephemeral loopback port, which is what tests use.
    Non-loopback hosts are rejected explicitly so the API cannot be exposed
    on a public interface accidentally in this block.
    """
    resolved_host = _validate_loopback_host(host)
    specs = tuple(catalog) if catalog is not None else get_catalog()
    store = model_store if model_store is not None else ModelStore()
    if run_dependencies is None:
        run_dependencies = RunDependencies(model_store=store, models=specs)
    if chat_registry is None:
        chat_registry = _ChatSessionRegistry()
    handler = _make_handler(
        specs, store, get_version(), run_dependencies, threading.Lock(),
        chat_dependencies, chat_registry,
    )
    return _APIServer((resolved_host, port), handler, chat_registry=chat_registry)


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    catalog: tuple[ModelSpec, ...] | None = None,
    model_store: ModelStore | None = None,
    run_dependencies: RunDependencies | None = None,
    chat_dependencies: ChatDependencies | None = None,
) -> int:
    """Run the API server until interrupted. Returns a process exit code."""
    server = build_server(
        host, port, catalog=catalog, model_store=model_store,
        run_dependencies=run_dependencies, chat_dependencies=chat_dependencies,
    )
    bound_host, bound_port = server.server_address[:2]
    print(f"CastleArq API listening on http://{bound_host}:{bound_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0