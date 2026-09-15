"""Local HTTP API (Fase 6.1, bloques 1-2).

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

Not implemented in this block (by design): chat HTTP, HTTP
sessions, streaming, OpenAI compatibility, downloads via
API, auth/TLS, persistence and Ollama integration.

Safety rules enforced here:

- The server only binds loopback interfaces (default ``127.0.0.1``);
  non-loopback hosts are rejected explicitly at construction time.
- DTOs never expose local paths, argv, environment or internal objects.
- Errors are reported as JSON without stack traces.
"""

from __future__ import annotations

import ipaddress
import json
import threading
import tomllib
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .model_catalog import get_catalog
from .model_identity import downloadable_locator
from .model_store import ModelStore, StoredArtifact
from .models import ModelSpec
from .run_service import (
    ModelNotFoundError,
    RunDependencies,
    RunExecutionFailedError,
    RunOutcome,
    RunPreparationFailedError,
    run_once,
)

__all__ = [
    "APIConfigurationError",
    "ArtifactDTO",
    "MAX_REQUEST_BODY_BYTES",
    "ModelDTO",
    "RunRequestDTO",
    "RunResponseDTO",
    "build_server",
    "get_version",
    "list_artifact_dtos",
    "list_model_dtos",
    "serve",
]

# Requests are GET-only in this block; a generous limit guards against
# oversized (or future) request bodies even though GET carries no body.
MAX_REQUEST_BODY_BYTES = 1024 * 1024

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
) -> type[BaseHTTPRequestHandler]:
    """Build a handler class with the injected core dependencies."""
    from urllib.parse import urlsplit

    class APIRequestHandler(BaseHTTPRequestHandler):
        server_version = "LocalAIHub/" + version
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
            """
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None
            try:
                length = int(raw_length)
            except ValueError:
                self._send_json(400, {"error": "invalid Content-Length"})
                return None
            if length < 0:
                self._send_json(400, {"error": "invalid Content-Length"})
                return None
            if length > MAX_REQUEST_BODY_BYTES:
                self._send_json(413, {"error": "request body too large"})
                return None
            if length == 0:
                return None
            try:
                return self.rfile.read(length)
            except OSError:
                self._send_json(400, {"error": "could not read request body"})
                return None

        def _read_json_body(self) -> object | None:
            raw = self._read_body()
            if raw is None:
                if self.headers.get("Content-Length") is None:
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

        def do_POST(self) -> None:  # noqa: N802 (http.server naming)
            try:
                if urlsplit(self.path).path != "/v1/run":
                    # POST is only defined for /v1/run; the GET-only
                    # resources keep their Block 1 behaviour (405).
                    self._method_not_allowed()
                    return
                self._handle_run()
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
        do_PUT = _method_not_allowed  # noqa: N802
        do_DELETE = _method_not_allowed  # noqa: N802
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
    handler = _make_handler(
        specs, store, get_version(), run_dependencies, threading.Lock()
    )
    return _APIServer((resolved_host, port), handler)


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    catalog: tuple[ModelSpec, ...] | None = None,
    model_store: ModelStore | None = None,
    run_dependencies: RunDependencies | None = None,
) -> int:
    """Run the API server until interrupted. Returns a process exit code."""
    server = build_server(
        host, port, catalog=catalog, model_store=model_store,
        run_dependencies=run_dependencies,
    )
    bound_host, bound_port = server.server_address[:2]
    print(f"LocalAI Hub API listening on http://{bound_host}:{bound_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0