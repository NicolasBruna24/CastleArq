# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application Use Case: Execute Model.

Thin, stateless coordinator of real execution, implementing the contract
ratified in ``docs/B9.19-execute-application-use-case-specification.md``:

    input -> resolve -> fresh capability -> admission (advisory)
      -> legacy compatibility gate -> artifact preflight -> target selection
      -> ExecutionRequest + validation -> ModelRunner -> ExecutionResult

The use case owns ordering and error mapping only: it implements no domain
rule, runs no subprocess, imports no CLI/HTTP, touches no evaluation code and
never builds an execution target itself (selection stays with
``RuntimeBackendSelector``). The runner is a ``ModelRunner`` abstraction
injected at the composition root; the concrete implementation is never named
here. Nothing is cached between invocations: every call re-resolves and
re-validates, so an earlier evaluation is never trusted as an execution
authority (B9.19 sections 7, 12 and 13).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .compatibility import (
    CompatibilityConfig,
    CompatibilityResult,
    CompatibilityStatus,
    assess_model,
)
from .execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    ExecutionRequest,
    ExecutionResult,
    validate_execution_request,
)
from .hardware import detect_hardware
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runner import ModelRunner
from .runtimes import (
    RuntimeCapability,
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
)
from .selection import RuntimeBackendSelector, RuntimeSelectionError

__all__ = [
    "DEFAULT_EXECUTION_TIMEOUT_SECONDS",
    "EvaluationAdmission",
    "ExecuteAdmissionDeniedError",
    "ExecuteModelDependencies",
    "ExecutePreparationError",
    "execute_model",
]

#: Default one-shot timeout, mirroring the legacy ``run_once`` default.
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0

#: Strict verdicts that allow an evaluated admission to proceed. Everything
#: else (incompatible, insufficient_evidence, missing) denies by default.
_ADMITTING_VERDICTS = frozenset({"compatible", "compatible_with_conditions"})

#: Legacy compatibility outcomes that stop a run before preflight, matching
#: the transitional gate in the legacy prepare sequence.
_REJECTING_COMPATIBILITY = frozenset(
    {CompatibilityStatus.INCOMPATIBLE, CompatibilityStatus.UNKNOWN}
)


@dataclass(frozen=True)
class EvaluationAdmission:
    """Advisory evaluation signal: a summary copy, never the result object.

    ``status`` is the B9.15/B9.16 outcome (``"evaluated"`` or ``"blocked"``)
    and ``verdict`` the strict verdict name. Admission can deny execution; it
    can never authorize it on its own (B9.19 section 7).
    """

    status: str
    verdict: str | None = None


class ExecutePreparationError(Exception):
    """Preparation failed; nothing was launched."""

    def __init__(self, message: str, warnings: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.warnings = tuple(warnings)


class ExecuteAdmissionDeniedError(ExecutePreparationError):
    """The evaluation admission gate denied execution."""


@dataclass(frozen=True)
class ExecuteModelDependencies:
    """Explicit injectable collaborators for the use case.

    Every field is optional and defaults to an existing contract; the runner
    has no production default because it is chosen at the composition root.
    """

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability_provider: Callable[[], RuntimeCapability] | None = None
    compatibility_provider: (
        Callable[[ModelSpec, RuntimeCapability], CompatibilityResult] | None
    ) = None
    preflight_factory: Callable[[ModelStore], Any] | None = None
    selector: Any | None = None
    runner: ModelRunner | None = None


def _runtime_status(capability: RuntimeCapability) -> RuntimeStatus:
    """Runtime facts for the transitional legacy gate.

    Mirrors the pure helper the legacy pipeline uses to project one detected
    capability into the runtime list ``assess_model`` consumes.
    """
    return RuntimeStatus(
        "llama.cpp / llama.app",
        installed=capability.executable_path is not None,
        available=capability.available,
        gpu_backend_detected=False,
        supported_backends=capability.supported_backends,
    )


def _legacy_compatibility(
    model: ModelSpec, capability: RuntimeCapability
) -> CompatibilityResult:
    """Transitional legacy compatibility gate (B9.19 sections 7 and 13).

    Composes existing domain/infrastructure contracts exactly like the legacy
    prepare sequence (hardware -> runtime status -> backend statuses ->
    ``assess_model``); it adds no rule of its own and is injectable so tests
    never probe the machine.
    """
    hardware = detect_hardware()
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)
    return assess_model(
        hardware,
        [_runtime_status(capability)],
        backends,
        model,
        config=CompatibilityConfig(),
    )


def _normalized_verdict(admission: Any) -> str:
    verdict = getattr(admission, "verdict", None)
    if verdict is None:
        return ""
    value = getattr(verdict, "value", verdict)
    return str(value).strip().lower().replace("-", "_")


def _check_admission(admission: EvaluationAdmission | None) -> None:
    """Advisory admission gate.

    ``None`` means the caller carries no evaluation signal, so the legacy gate
    alone applies. Otherwise the signal may only deny: it must be an
    ``evaluated`` outcome whose verdict is in the admitting set. ``blocked``
    never authorizes, and ``insufficient_evidence`` (or anything unknown)
    denies by default (B9.19 section 7).
    """
    if admission is None:
        return
    status = str(getattr(admission, "status", "")).strip().lower()
    if status != "evaluated":
        raise ExecuteAdmissionDeniedError(
            "Execution denied: evaluation did not produce an evaluated "
            f"outcome (status={status!r})"
        )
    verdict = _normalized_verdict(admission)
    if verdict in _ADMITTING_VERDICTS:
        return
    raise ExecuteAdmissionDeniedError(
        "Execution denied by evaluation admission; deny-by-default applies "
        f"(verdict={verdict or 'missing'!r})"
    )


def _fresh_capability(deps: ExecuteModelDependencies) -> RuntimeCapability:
    provider = deps.capability_provider or detect_llama_capability
    return provider()


def _invocable_capability(capability: RuntimeCapability) -> RuntimeCapability:
    if capability is None:
        raise ExecutePreparationError(
            "Runtime capability is not available for execution"
        )
    if capability.invocable is not True or not capability.executable_path:
        detail = capability.reason or "runtime is not invocable"
        raise ExecutePreparationError(
            "Runtime capability is not available for execution: " + detail
        )
    return capability


def _compatibility(
    deps: ExecuteModelDependencies,
    model: ModelSpec,
    capability: RuntimeCapability,
) -> CompatibilityResult:
    provider = deps.compatibility_provider or _legacy_compatibility
    return provider(model, capability)


def _preflight(deps: ExecuteModelDependencies, store: ModelStore) -> Any:
    factory = deps.preflight_factory or ArtifactExecutionPreflight
    return factory(store)


def _selector(deps: ExecuteModelDependencies) -> Any:
    return deps.selector if deps.selector is not None else RuntimeBackendSelector()


def _require_runner(deps: ExecuteModelDependencies) -> ModelRunner:
    runner = deps.runner
    if runner is None:
        raise ExecutePreparationError("A ModelRunner is required to execute")
    if not isinstance(runner, ModelRunner):
        raise ExecutePreparationError("runner must be a ModelRunner implementation")
    return runner


def execute_model(
    model_id: str,
    prompt: str,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    timeout_seconds: float | None = None,
    backend_preference: str | None = None,
    admission: EvaluationAdmission | None = None,
    dependencies: ExecuteModelDependencies | None = None,
) -> ExecutionResult:
    """Execute one prompt for one resolved model artifact.

    Returns the runner's :class:`ExecutionResult` verbatim when preparation emits
    no warnings. Preparation warnings are prepended to runner warnings while all
    other runner result fields are preserved. Raises
    :class:`ExecutePreparationError` when nothing could be launched, and
    :class:`ExecuteAdmissionDeniedError` when the advisory admission gate
    denied execution.
    """
    if not isinstance(model_id, str) or not model_id.strip():
        raise ExecutePreparationError("model_id must be a non-empty string")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ExecutePreparationError("prompt must be a non-empty string")
    deps = dependencies if dependencies is not None else ExecuteModelDependencies()
    timeout = (
        DEFAULT_EXECUTION_TIMEOUT_SECONDS
        if timeout_seconds is None
        else timeout_seconds
    )

    store = deps.model_store if deps.model_store is not None else ModelStore()
    models = deps.models if deps.models is not None else get_catalog()

    # 1. Re-resolution: a previous evaluation is never an execution authority.
    resolver = ModelArtifactResolver(store, models=models)
    try:
        resolved = resolver.resolve(
            model_id, quantization=quantization, filename=filename
        )
    except ModelArtifactResolutionError as error:
        raise ExecutePreparationError(str(error)) from error
    except Exception as error:  # any resolution failure is a preparation failure
        raise ExecutePreparationError(str(error)) from error
    model: ModelSpec = resolved.model
    artifact: ArtifactSpec = resolved.artifact

    # 2. Fresh capability, detected per invocation (never cached).
    capability = _invocable_capability(_fresh_capability(deps))

    # 3. Admission: advisory only, denied before any validation work.
    _check_admission(admission)

    # 4. Transitional legacy gate: compatibility -> preflight -> selection, in
    #    the legacy prepare order, always fully revalidated. Admission=None
    #    means this gate is the only gate (B9.19 section 7).
    compatibility = _compatibility(deps, model, capability)
    compatibility_warnings = tuple(compatibility.warnings)
    if compatibility.status in _REJECTING_COMPATIBILITY:
        raise ExecutePreparationError(
            "Model compatibility does not permit execution",
            warnings=compatibility_warnings,
        )

    preflight = _preflight(deps, store)
    try:
        executable_artifact = preflight.validate(artifact)
    except ArtifactPreflightError as error:
        raise ExecutePreparationError(
            error.message, warnings=compatibility_warnings
        ) from error

    selector = _selector(deps)
    try:
        selection = selector.select(compatibility, capability, executable_artifact)
    except RuntimeSelectionError as error:
        raise ExecutePreparationError(
            error.message, warnings=compatibility_warnings
        ) from error
    target = selection.target
    warnings = (*compatibility_warnings, *selection.warnings)

    # 5. Caller preference: a wish about the selector's outcome, never a
    #    target of our own and never a silent override of the selection.
    if backend_preference is not None and target.backend != backend_preference:
        raise ExecutePreparationError(
            "Backend preference is not satisfied by the selected target: "
            f"requested={backend_preference!r} selected={target.backend!r}",
            warnings=warnings,
        )

    request = ExecutionRequest(
        artifact,
        prompt,
        target=target,
        timeout_seconds=timeout,
    )
    try:
        validate_execution_request(request)
    except Exception as error:
        raise ExecutePreparationError(str(error), warnings=warnings) from error

    runner = _require_runner(deps)
    result = runner.run(executable_artifact, target, request)
    if not warnings:
        return result
    return ExecutionResult(
        success=result.success,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.error,
        warnings=(*warnings, *result.warnings),
        diagnostics=result.diagnostics,
        runtime_metrics=result.runtime_metrics,
    )
