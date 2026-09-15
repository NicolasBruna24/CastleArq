"""Reusable one-shot execution pipeline (shared by CLI and HTTP API).

This module owns the sequence CLI ``run`` has always used:

resolver -> compatibility -> preflight -> selection -> runner.

It executes no subprocess itself and prints nothing; it is a pure
domain/application layer. The HTTP API (``app.api``) adapts this pipeline
over HTTP without calling the CLI or ``subprocess``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .compatibility import CompatibilityConfig, CompatibilityStatus, assess_model
from .execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    ExecutionRequest,
    ExecutableArtifact,
    ExecutionTarget,
)
from .hardware import detect_hardware
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runner import LlamaCppRunner
from .runtimes import (
    RuntimeCapability,
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
)
from .selection import RuntimeBackendSelector, RuntimeSelectionError

__all__ = [
    "ExecutionPreparation",
    "PreparationError",
    "RunDependencies",
    "RunOutcome",
    "RunServiceError",
    "detect_runtime_statuses",
    "prepare",
    "run_once",
]


@dataclass(frozen=True)
class ExecutionPreparation:
    """Inputs shared by one-shot run and interactive chat.

    Minimal and immutable: only what both execution paths need AFTER
    resolution but BEFORE any runtime process is launched.
    """

    executable_artifact: ExecutableArtifact
    target: ExecutionTarget
    compatibility_warnings: tuple[str, ...]
    selection_warnings: tuple[str, ...]


class PreparationError(Exception):
    """Raised when an artifact cannot be prepared for any execution path."""

    def __init__(
        self,
        message: str,
        compatibility_warnings: tuple[str, ...] = (),
        selection_warnings: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.compatibility_warnings = compatibility_warnings
        self.selection_warnings = selection_warnings

    @property
    def warnings(self) -> tuple[str, ...]:
        """Merged warnings, deduplicated."""
        return tuple(
            dict.fromkeys(
                (*self.compatibility_warnings, *self.selection_warnings)
            )
        )


class RunServiceError(Exception):
    """Base class for errors raised by :func:`run_once`."""


class ModelNotFoundError(RunServiceError):
    """The requested ``model_id`` is not in the catalog."""


class RunPreparationFailedError(RunServiceError):
    """Resolution, selection, compatibility or preflight rejected the run."""


class RunExecutionFailedError(RunServiceError):
    """The runtime was launched (or attempted) and the run failed."""


@dataclass(frozen=True)
class RunDependencies:
    """Injectable collaborators for :func:`run_once`."""

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability: RuntimeCapability | None = None
    runner: LlamaCppRunner | None = None


@dataclass(frozen=True)
class RunOutcome:
    """Safe, API-appropriate projection of a successful execution."""

    model_id: str
    output: str
    exit_code: int | None
    warnings: tuple[str, ...]


def detect_runtime_statuses(
    capability: RuntimeCapability,
) -> list[RuntimeStatus]:
    """Build the runtime list that both run and chat construct inline."""
    return [
        RuntimeStatus(
            "llama.cpp / llama.app",
            installed=capability.executable_path is not None,
            available=capability.available,
            gpu_backend_detected=False,
            supported_backends=capability.supported_backends,
        )
    ]


def prepare(
    model: ModelSpec,
    artifact: ArtifactSpec,
    capability: "RuntimeCapability",
    model_store: ModelStore,
) -> ExecutionPreparation:
    """Resolve compatibility, preflight and selection without launching."""
    hardware = detect_hardware()
    runtimes = detect_runtime_statuses(capability)
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)

    compatibility = assess_model(
        hardware, runtimes, backends, model, config=CompatibilityConfig()
    )
    if compatibility.status in {
        CompatibilityStatus.INCOMPATIBLE,
        CompatibilityStatus.UNKNOWN,
    }:
        raise PreparationError(
            "Model compatibility does not permit execution",
            compatibility_warnings=compatibility.warnings,
        )

    try:
        executable_artifact = ArtifactExecutionPreflight(
            model_store
        ).validate(artifact)
    except ArtifactPreflightError as error:
        raise PreparationError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    try:
        selection = RuntimeBackendSelector().select(
            compatibility, capability, executable_artifact
        )
    except RuntimeSelectionError as error:
        raise PreparationError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    return ExecutionPreparation(
        executable_artifact=executable_artifact,
        target=selection.target,
        compatibility_warnings=compatibility.warnings,
        selection_warnings=selection.warnings,
    )


_DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0


def run_once(
    model_id: str,
    prompt: str,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    timeout_seconds: float | None = None,
    dependencies: RunDependencies | None = None,
) -> RunOutcome:
    """Execute one prompt through the shared pipeline.

    Same sequence CLI ``run`` uses (resolver -> ``prepare`` ->
    ``LlamaCppRunner``). Raises :class:`ModelNotFoundError` for unknown
    model ids, :class:`RunPreparationFailedError` when selection/preflight
    rejects the run, and :class:`RunExecutionFailedError` on runtime
    failure. Never prints, never touches the CLI.
    """
    deps = dependencies or RunDependencies()
    store = deps.model_store if deps.model_store is not None else ModelStore()
    models = deps.models if deps.models is not None else get_catalog()
    capability = (
        deps.capability if deps.capability is not None else detect_llama_capability()
    )

    resolver = ModelArtifactResolver(store, models=models)
    try:
        resolved = resolver.resolve(
            model_id, quantization=quantization, filename=filename
        )
    except ModelArtifactResolutionError as error:
        message = str(error)
        if message.startswith("Model not found in the local catalog:"):
            raise ModelNotFoundError(message) from error
        raise RunPreparationFailedError(message) from error

    try:
        preparation = prepare(
            resolved.model, resolved.artifact, capability, store
        )
    except PreparationError as error:
        raise RunPreparationFailedError(error.message) from error

    runner = deps.runner if deps.runner is not None else LlamaCppRunner(capability)
    request = ExecutionRequest(
        resolved.artifact,
        prompt,
        target=preparation.target,
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else _DEFAULT_EXECUTION_TIMEOUT_SECONDS
        ),
    )
    result = runner.run(
        preparation.executable_artifact, preparation.target, request
    )
    if result.success:
        warnings = tuple(
            dict.fromkeys(
                (
                    *preparation.compatibility_warnings,
                    *preparation.selection_warnings,
                    *result.warnings,
                )
            )
        )
        return RunOutcome(
            model_id=resolved.model.model_id,
            output=result.stdout,
            exit_code=result.exit_code,
            warnings=warnings,
        )
    detail = result.error.message if result.error is not None else "execution failed"
    raise RunExecutionFailedError(detail)
