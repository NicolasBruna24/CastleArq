"""Domain types for one-shot model execution."""

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import math
import os
import stat
from datetime import datetime
from pathlib import Path

from .downloads.inspection import ArtifactFilesystemInspector, ArtifactFilesystemState
from .model_store import ModelStore, UnsafePathError
from .models import ArtifactSpec


class ExecutionError(Exception):
    """Base class for execution-domain errors."""


class InvalidExecutionRequestError(ExecutionError):
    """Raised when an execution request cannot be used safely."""


class PreflightErrorCode(str, Enum):
    MISSING_ARTIFACT = "missing_artifact"
    PARTIAL_ARTIFACT = "partial_artifact"
    INCONSISTENT_ARTIFACT = "inconsistent_artifact"
    UNSAFE_ARTIFACT = "unsafe_artifact"
    INVALID_ARTIFACT = "invalid_artifact"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"


class ArtifactPreflightError(ExecutionError):
    """Raised when an artifact cannot be safely prepared for execution."""

    def __init__(self, code: PreflightErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExecutionErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    COMPATIBILITY_REJECTED = "compatibility_rejected"
    PREFLIGHT_FAILED = "preflight_failed"
    SELECTION_FAILED = "selection_failed"
    EXECUTABLE_MISSING = "executable_missing"
    PERMISSION_DENIED = "permission_denied"
    ARTIFACT_INVALID = "artifact_invalid"
    LAUNCH_FAILED = "launch_failed"
    TIMEOUT = "timeout"
    PROCESS_FAILED = "process_failed"


@dataclass(frozen=True)
class ExecutionTarget:
    """A selected runtime and backend for an execution."""

    runtime: str
    backend: str


@dataclass(frozen=True)
class ExecutionRequest:
    """Input for a one-shot execution.

    The artifact is resolved by the execution layers from its domain identity;
    this request deliberately carries no filesystem path or subprocess data.
    """

    artifact: ArtifactSpec
    prompt: str
    target: ExecutionTarget | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ExecutionDiagnostics:
    """Measured facts from the controlled subprocess operation."""

    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    stdout_bytes: int
    stderr_bytes: int
    exit_code: int | None
    timed_out: bool
    terminated_normally: bool


def validate_execution_request(request: ExecutionRequest) -> None:
    """Reject process-affecting request values outside the execution contract."""
    if not isinstance(request, ExecutionRequest):
        raise InvalidExecutionRequestError("Execution request has an invalid type")
    if not isinstance(request.artifact, ArtifactSpec):
        raise InvalidExecutionRequestError("Execution request artifact is invalid")
    if not isinstance(request.prompt, str) or not request.prompt.strip():
        raise InvalidExecutionRequestError("Execution request prompt must not be empty")
    if request.target is not None:
        if (
            not isinstance(request.target, ExecutionTarget)
            or not isinstance(request.target.runtime, str)
            or not request.target.runtime
            or not isinstance(request.target.backend, str)
            or not request.target.backend
        ):
            raise InvalidExecutionRequestError("Execution request target is invalid")
    timeout = request.timeout_seconds
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise InvalidExecutionRequestError(
            "Execution request timeout must be finite and greater than zero"
        )


@dataclass(frozen=True)
class ExecutionErrorInfo:
    """Controlled error information returned by an execution."""

    code: ExecutionErrorCode
    message: str


@dataclass(frozen=True)
class ExecutionResult:
    """Result of a completed or failed one-shot execution."""

    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    error: ExecutionErrorInfo | None = None
    warnings: tuple[str, ...] = ()
    diagnostics: ExecutionDiagnostics | None = None


@dataclass(frozen=True)
class ExecutableArtifact:
    """A final artifact validated for a future runner."""

    artifact: ArtifactSpec
    path: Path
    size_verified: bool
    checksum_verified: bool


class ArtifactExecutionPreflight:
    """Read-only validation of an artifact resolved through ModelStore."""

    def __init__(self, model_store: ModelStore) -> None:
        self.model_store = model_store
        self.inspector = ArtifactFilesystemInspector(model_store)

    def validate(self, artifact: ArtifactSpec) -> ExecutableArtifact:
        inspection = self.inspector.inspect(artifact)

        errors = {
            ArtifactFilesystemState.CLEAN: (
                PreflightErrorCode.MISSING_ARTIFACT,
                "Final artifact does not exist",
            ),
            ArtifactFilesystemState.PARTIAL: (
                PreflightErrorCode.PARTIAL_ARTIFACT,
                "Partial artifact is not executable",
            ),
            ArtifactFilesystemState.INCONSISTENT: (
                PreflightErrorCode.INCONSISTENT_ARTIFACT,
                "Final and partial artifacts exist simultaneously",
            ),
        }
        if inspection.state in errors:
            code, message = errors[inspection.state]
            raise ArtifactPreflightError(code, message)

        root_fd = model_fd = artifact_fd = final_fd = None
        try:
            root_fd = self.model_store._open_root(create=False)
            model_fd = self.model_store._open_directory(
                root_fd,
                self.model_store._safe_model_id(artifact.model_id),
                create=False,
            )
            artifact_fd = self.model_store._open_directory(
                model_fd, artifact.artifact_id, create=False
            )
            filename = self.model_store._safe_filename(artifact.filename)
            mode = os.lstat(filename, dir_fd=artifact_fd).st_mode
            if stat.S_ISLNK(mode):
                raise ArtifactPreflightError(
                    PreflightErrorCode.UNSAFE_ARTIFACT,
                    "Final artifact is a symlink",
                )
            if not stat.S_ISREG(mode):
                raise ArtifactPreflightError(
                    PreflightErrorCode.INVALID_ARTIFACT,
                    "Final artifact is not a regular file",
                )
            final_fd = os.open(
                filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=artifact_fd
            )
            actual_size = os.fstat(final_fd).st_size
            size_verified = artifact.size_bytes is not None
            if size_verified and actual_size != artifact.size_bytes:
                raise ArtifactPreflightError(
                    PreflightErrorCode.SIZE_MISMATCH,
                    "Final artifact size differs from ArtifactSpec",
                )
            checksum_verified = False
            if artifact.sha256 is not None:
                digest = hashlib.sha256()
                with os.fdopen(final_fd, "rb") as stream:
                    final_fd = None
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if not hmac.compare_digest(
                    digest.hexdigest().lower(), artifact.sha256.lower()
                ):
                    raise ArtifactPreflightError(
                        PreflightErrorCode.CHECKSUM_MISMATCH,
                        "Final artifact SHA-256 differs from ArtifactSpec",
                    )
                checksum_verified = True
            return ExecutableArtifact(
                artifact=artifact,
                path=self.model_store._artifact_directory(artifact) / filename,
                size_verified=size_verified,
                checksum_verified=checksum_verified,
            )
        except FileNotFoundError as error:
            raise ArtifactPreflightError(
                PreflightErrorCode.MISSING_ARTIFACT,
                "Artifact disappeared during preflight",
            ) from error
        finally:
            for fd in (final_fd, artifact_fd, model_fd, root_fd):
                if fd is not None:
                    os.close(fd)
