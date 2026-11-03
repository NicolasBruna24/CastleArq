# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application Use Case: Execute Model.

Thin, stateless coordinator of real execution, implementing the contract
ratified in ``docs/B9.19-execute-application-use-case-specification.md``
and finalized by the B9.78 legacy admission cutover ("
docs/roadmap-register-and-numbering-policy.md", "refactor: complete B9.78
legacy admission cutover"):

    input -> resolve -> fresh capability detection -> mandatory admission
      -> compatibility (selection recommendation only) -> artifact preflight
      -> target selection -> ExecutionRequest + validation -> ModelRunner
      -> ExecutionResult

The use case owns ordering and error mapping only: it implements no domain
rule, runs no subprocess, imports no CLI/HTTP or evaluation machinery, and
never builds an execution target itself (selection stays with
``RuntimeBackendSelector``). The runner is a ``ModelRunner`` abstraction,
injected at the composition root or created by the shared runner factory.
Nothing is cached between invocations: every call re-resolves and
re-validates, so an earlier evaluation is never trusted as an execution
authority. Admission is mandatory and deny-only (B9.78); an absent or
non-evaluated signal is a denial, never authorization (B9.19 section 7 was
advisory only and is superseded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .admission import EvaluationAdmission
from .compatibility import (
    CompatibilityConfig,
    CompatibilityResult,
    assess_model,
)
from .execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionRequest,
    ExecutionResult,
    validate_execution_request,
)
from .execution_preparation import (
    AdmissionDeniedError,
    ExecutionPreparation,
    ExecutionPreparationDependencies,
    PreparationFailureError,
    prepare_execution,
    require_evaluation_admission,
)
from .hardware import HardwareSnapshot, detect_hardware
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runner_factory import (
    ExecutionRunner,
    RunnerFactoryError,
    create_runner,
)
from .runtimes import (
    BackendStatus,
    RuntimeCapability,
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
)
from .selection import RuntimeBackendSelector

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

# B9.78 removed ``_REJECTING_COMPATIBILITY``: the legacy INCOMPATIBLE/UNKNOWN
# outcomes no longer stop a run. Strict admission is the only admission gate.


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

    Every field is optional and defaults to an existing contract. A runner can
    be injected by the composition root or constructed for the selected target.
    """

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability_provider: Callable[[], RuntimeCapability] | None = None
    compatibility_provider: (
        Callable[[ModelSpec, RuntimeCapability], CompatibilityResult] | None
    ) = None
    preflight_factory: Callable[[ModelStore], Any] | None = None
    selector: Any | None = None
    runner: ExecutionRunner | None = None


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


def _check_admission(admission: EvaluationAdmission | None) -> None:
    """Mandatory admission gate (B9.78 — legacy admission cutover).

    B9.19 section 7 made this advisory: ``None`` meant "no evaluation signal",
    so the legacy compatibility gate alone applied. That transitional rule is
    the rule B9.78 completes and replaces, so ``None`` is no longer a way
    through. Admission is now the sole authority for whether execution may
    proceed, and an absent signal is a denial, never authorization.

    The deny-only semantics are unchanged: the signal must be an ``evaluated``
    outcome whose verdict is in the admitting set. ``blocked`` never
    authorizes, and ``insufficient_evidence`` (or anything unknown) denies by
    default.
    """
    try:
        require_evaluation_admission(admission)
    except AdmissionDeniedError as error:
        raise ExecuteAdmissionDeniedError(error.message) from error


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


def _preflight(deps: ExecuteModelDependencies, store: ModelStore) -> Any:
    factory = deps.preflight_factory or ArtifactExecutionPreflight
    return factory(store)


def _selector(deps: ExecuteModelDependencies) -> Any:
    return deps.selector if deps.selector is not None else RuntimeBackendSelector()


def _detect_backends(detected_gpu_backends: set[str]) -> list[BackendStatus]:
    return detect_backends(detected_gpu_backends=detected_gpu_backends)


def _assess_compatibility(
    hardware: HardwareSnapshot,
    runtimes: list[RuntimeStatus],
    backends: list[BackendStatus],
    model: ModelSpec,
) -> CompatibilityResult:
    return assess_model(
        hardware,
        runtimes,
        backends,
        model,
        config=CompatibilityConfig(),
        # B9.66: imported artifacts with unknown model size proceed as MARGINAL;
        # catalog artifacts keep the existing blocking behavior.
        allow_unknown_memory=model.id is None,
    )


def _preparation_dependencies(
    deps: ExecuteModelDependencies,
) -> ExecutionPreparationDependencies:
    compatibility_provider = deps.compatibility_provider
    return ExecutionPreparationDependencies(
        hardware_provider=detect_hardware,
        runtime_status_provider=lambda capability: [_runtime_status(capability)],
        backend_provider=_detect_backends,
        compatibility_provider=_assess_compatibility,
        compatibility_result_provider=(
            (lambda model, capability: compatibility_provider(model, capability))
            if compatibility_provider
            else None
        ),
        preflight_factory=lambda store: _preflight(deps, store),
        selector_factory=lambda: _selector(deps),
    )


def _require_runner(
    deps: ExecuteModelDependencies,
    capability: RuntimeCapability,
    preparation: ExecutionPreparation,
) -> ExecutionRunner:
    try:
        runner = create_runner(
            capability,
            preparation.target,
            configured_runner=deps.runner,
        )
    except RunnerFactoryError as error:
        raise ExecutePreparationError(str(error)) from error
    if not isinstance(runner, ExecutionRunner):
        raise ExecutePreparationError(
            "ExecuteModel requires an ExecutionRunner implementation"
        )
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

    # B9.67: an imported artifact must carry a verified managed path before
    # anything else happens. Resolution already proved the file is inside the
    # store, is a regular file and is not a symlink; this refuses to continue
    # if that proof is ever absent. There is no fallback to the original
    # import source, to a path rebuilt from the label, or to any user-supplied
    # path: an import without a managed location simply does not execute.
    if resolved.imported and resolved.path is None:
        raise ExecutePreparationError(
            "Imported artifact has no verified managed path in the model store"
        )

    # 2. Fresh capability, detected per invocation (never cached).
    capability = _invocable_capability(_fresh_capability(deps))

    try:
        preparation = prepare_execution(
            model,
            artifact,
            capability,
            store,
            admission=admission,
            dependencies=_preparation_dependencies(deps),
        )
    except AdmissionDeniedError as error:
        raise ExecuteAdmissionDeniedError(error.message) from error
    except PreparationFailureError as error:
        raise ExecutePreparationError(
            error.message,
            warnings=(
                *error.compatibility_warnings,
                *error.selection_warnings,
            ),
        ) from error

    executable_artifact = preparation.executable_artifact
    target = preparation.target
    warnings = (
        *preparation.compatibility_warnings,
        *preparation.selection_warnings,
    )

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

    runner = _require_runner(deps, capability, preparation)
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
        offload_evidence=result.offload_evidence,
    )
