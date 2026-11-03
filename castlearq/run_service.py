# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reusable one-shot execution pipeline (shared by CLI and HTTP API).

This module owns the sequence CLI ``run`` has always used:

resolver -> compatibility -> preflight -> selection -> runner.

It executes no subprocess itself and prints nothing; it is a pure
domain/application layer. The HTTP API (``castlearq.api``) adapts this pipeline
over HTTP without calling the CLI or ``subprocess``.

Block 3.1 adds :func:`open_chat_session`, the session-opening counterpart
of ``run_once``: same resolver -> ``prepare`` sequence, but the final
step launches a persistent interactive session via ``castlearq.chat`` instead of
a one-shot runner. The HTTP layer calls this service; it never touches the
resolver, preflight, selector, argv or subprocess directly.
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
from .execute_model import ExecuteAdmissionDeniedError
from .execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionTarget,
)
from .execution_preparation import (
    AdmissionDeniedError,
    ExecutionPreparation,
    ExecutionPreparationDependencies,
    PreparationFailureError,
    detect_runtime_statuses,
    prepare_execution,
    require_evaluation_admission,
)
from .hardware import HardwareSnapshot, detect_hardware
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runner import ExecutionRunnerLike, LlamaCppRunner
from .runner_factory import (
    RunnerFactoryDependencies,
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
from .selection import RuntimeBackendSelector, RuntimeSelectionError

__all__ = [
    "ChatDependencies",
    "ChatLaunchFailedError",
    "ChatSessionOpened",
    "ExecutionPreparation",
    "PreparationError",
    "RunDependencies",
    "RunOutcome",
    "RunServiceError",
    "detect_runtime_statuses",
    "open_chat_session",
    "prepare",
    "run_once",
]


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
    """Resolution, selection, compatibility or preflight rejected the run.

    Optionally carries the structured warnings the preparation phase
    produced (Block 6.2-C: preserve internally, expose nothing new).
    """

    def __init__(
        self, message: str, *, warnings: tuple[str, ...] = ()
    ) -> None:
        super().__init__(message)
        self.warnings: tuple[str, ...] = tuple(warnings)


class RunExecutionFailedError(RunServiceError):
    """The runtime was launched (or attempted) and the run failed.

    Optionally carries the structured :class:`ExecutionErrorCode` from the
    failed ``ExecutionResult`` (Block 6.2-C: preserve internally, expose
    nothing new).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: ExecutionErrorCode | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        # B9.89 HADR Amendment A section 16.2: a failed runtime result also
        # carries stderr, and the CLI presented it before B9.89. Additive and
        # defaulted; ``message`` and ``error_code`` are unchanged.
        self.stderr = stderr


@dataclass(frozen=True)
class RunDependencies:
    """Injectable collaborators for :func:`run_once`."""

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability: RuntimeCapability | None = None
    runner: ExecutionRunnerLike | None = None


@dataclass(frozen=True)
class RunOutcome:
    """Safe, API-appropriate projection of a successful execution."""

    model_id: str
    output: str
    exit_code: int | None
    warnings: tuple[str, ...]
    # B9.89 HADR Amendment A section 16.2: the runtime's stderr is part of the
    # observable CLI contract and must cross this boundary. Additive and
    # defaulted, so existing construction sites are unaffected.
    stderr: str = ""


def _select_runner(
    capability: RuntimeCapability,
    target: ExecutionTarget,
    configured_runner: ExecutionRunnerLike | None = None,
) -> ExecutionRunnerLike:
    """Compatibility wrapper around the shared runner factory."""
    try:
        return create_runner(
            capability,
            target,
            configured_runner=configured_runner,
            dependencies=RunnerFactoryDependencies(
                llama_cpp_factory=lambda selected_capability: LlamaCppRunner(
                    selected_capability
                )
            ),
        )
    except RunnerFactoryError as error:
        raise RunPreparationFailedError(str(error)) from error


def _require_admission(admission: EvaluationAdmission | None) -> None:
    """B9.78 — the mandatory strict admission gate for the run/chat path.

    Mirrors ``execute_model._check_admission``: deny-only, and an absent signal
    is a denial rather than authorization. ``blocked``, any non-``evaluated``
    status, and any verdict outside the admitting set all deny; only
    ``compatible`` and ``compatible_with_conditions`` admit.
    """
    try:
        require_evaluation_admission(admission)
    except AdmissionDeniedError as error:
        raise ExecuteAdmissionDeniedError(error.message) from error


def _preparation_backend_provider(
    detected_gpu_backends: set[str],
) -> list[BackendStatus]:
    return detect_backends(detected_gpu_backends=detected_gpu_backends)


def _preparation_compatibility_provider(
    hardware: HardwareSnapshot,
    runtimes: list[RuntimeStatus],
    backends: list[BackendStatus],
    model: ModelSpec,
) -> CompatibilityResult:
    return assess_model(
        hardware, runtimes, backends, model, config=CompatibilityConfig()
    )


def prepare(
    model: ModelSpec,
    artifact: ArtifactSpec,
    capability: "RuntimeCapability",
    model_store: ModelStore,
    *,
    admission: EvaluationAdmission | None = None,
    requested_backend: str | None = None,
) -> ExecutionPreparation:
    """Resolve compatibility, preflight and selection without launching.

    B9.78 — legacy admission cutover. ``admission`` is the strict evaluation
    signal and is the MANDATORY gate for this path: it is checked before any
    preparation work, exactly as B9.19 section 7 places admission before the
    legacy prepare sequence. ``None`` is never authorization; an absent signal
    fails closed.

    The parameter is optional keyword-only so existing callers keep compiling
    while the active product paths migrate. Every active path (``run``, ``chat``)
    supplies a real admission.

    The legacy compatibility result below is retained ONLY as selection
    recommendation data (``recommended_runtime`` / ``recommended_backend``),
    per B9.78 decision D1-A. It can no longer refuse execution.
    """
    try:
        return prepare_execution(
            model,
            artifact,
            capability,
            model_store,
            admission=admission,
            requested_backend=requested_backend,
            dependencies=ExecutionPreparationDependencies(
                hardware_provider=detect_hardware,
                runtime_status_provider=detect_runtime_statuses,
                backend_provider=_preparation_backend_provider,
                compatibility_provider=_preparation_compatibility_provider,
                preflight_factory=ArtifactExecutionPreflight,
                selector_factory=RuntimeBackendSelector,
            ),
        )
    except AdmissionDeniedError as error:
        raise ExecuteAdmissionDeniedError(error.message) from error
    except PreparationFailureError as error:
        raise PreparationError(
            error.message,
            compatibility_warnings=error.compatibility_warnings,
            selection_warnings=error.selection_warnings,
        ) from error


_DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0


def run_once(
    model_id: str,
    prompt: str,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    timeout_seconds: float | None = None,
    dependencies: RunDependencies | None = None,
    admission: EvaluationAdmission | None = None,
    requested_backend: str | None = None,
) -> RunOutcome:
    """Execute one prompt through the shared pipeline.

    Same sequence CLI ``run`` uses (resolver -> ``prepare`` -> runner factory).
    Raises :class:`ModelNotFoundError` for unknown
    model ids, :class:`RunPreparationFailedError` when admission, selection or
    preflight rejects the run, and :class:`RunExecutionFailedError` on runtime
    failure. Never prints, never touches the CLI.

    B9.78: ``admission`` is the strict evaluation signal and is mandatory for
    this path. ``None`` is not authorization; it fails closed.
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
            resolved.model, resolved.artifact, capability, store,
            admission=admission, requested_backend=requested_backend,
        )
    except (PreparationError, ExecuteAdmissionDeniedError) as error:
        message = getattr(error, "message", None) or str(error)
        raise RunPreparationFailedError(
            message, warnings=getattr(error, "warnings", ())
        ) from error

    # Select the runner based on the preparation target backend
    target = preparation.target
    runner = _select_runner(capability, target, deps.runner if deps.runner is not None else None)
    request = ExecutionRequest(
        resolved.artifact,
        prompt,
        target=target,
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
            stderr=result.stderr,
        )
    detail = result.error.message if result.error is not None else "execution failed"
    raise RunExecutionFailedError(
        detail,
        error_code=result.error.code if result.error is not None else None,
        stderr=result.stderr,
    )


class ChatLaunchFailedError(RunServiceError):
    """The artifact was prepared but the interactive runtime failed to launch."""


@dataclass(frozen=True)
class ChatDependencies:
    """Injectable collaborators for :func:`open_chat_session`."""

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability: RuntimeCapability | None = None
    session_factory: Callable[..., Any] | None = None


@dataclass(frozen=True)
class ChatSessionOpened:
    """A launched interactive session plus API-safe metadata (no paths)."""

    session: Any
    model_id: str
    # B9.88 human-approved clarification: the CLI chat caller must preserve the
    # pre-B9.88 successful-path selection warnings. These are the warnings the
    # existing preparation pipeline already computed; nothing is recomputed here.
    # Additive and defaulted, so every existing construction site is unchanged.
    warnings: tuple[str, ...] = ()


def open_chat_session(
    model_id: str,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    dependencies: ChatDependencies | None = None,
    admission: EvaluationAdmission | None = None,
    device: str = "CPU",
) -> ChatSessionOpened:
    """Resolve, prepare and launch one persistent interactive chat session.

    Same sequence CLI ``chat`` uses (resolver -> ``prepare`` ->
    ``start_chat_session``). Raises :class:`ModelNotFoundError` for unknown
    model ids, :class:`RunPreparationFailedError` when admission, selection or
    preflight rejects the request, and :class:`ChatLaunchFailedError` when the
    runtime subprocess cannot be started. Never prints, never touches the CLI.

    B9.78: ``admission`` is the strict evaluation signal and is mandatory for
    this path. ``None`` is not authorization; it fails closed.
    """
    from .chat import ChatSessionError, start_chat_session
    from .openvino_inference import OpenVINOInferenceService

    if not isinstance(device, str) or device not in {"CPU", "GPU"}:
        raise ValueError("device must be 'CPU' or 'GPU'")

    deps = dependencies or ChatDependencies()
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

    if getattr(resolved.artifact, "backend", None) == "openvino":
        try:
            from .execution import ArtifactExecutionPreflight
            executable_artifact = ArtifactExecutionPreflight(store).validate(resolved.artifact)
        except Exception as error:
            raise RunPreparationFailedError(str(error)) from error
        preparation = None
    else:
        try:
            preparation = prepare(
                resolved.model, resolved.artifact, capability, store,
                admission=admission,
            )
        except (PreparationError, ExecuteAdmissionDeniedError) as error:
            message = getattr(error, "message", None) or str(error)
            raise RunPreparationFailedError(
                message, warnings=getattr(error, "warnings", ())
            ) from error
        executable_artifact = preparation.executable_artifact

    backend = executable_artifact.artifact.backend
    if backend == "gguf":
        if preparation is None:
            raise RunPreparationFailedError(
                "GGUF chat preparation did not produce an execution target"
            )
        factory = deps.session_factory or start_chat_session
        try:
            session = factory(
                capability,
                preparation.executable_artifact,
                preparation.target,
            )
        except ChatSessionError as error:
            raise ChatLaunchFailedError(str(error)) from error
        return ChatSessionOpened(
            session=session,
            model_id=resolved.model.model_id,
            warnings=getattr(preparation, "selection_warnings", ()),
        )
    if backend == "openvino":
        service = OpenVINOInferenceService(store)
        try:
            model_dir = executable_artifact.path.parent
            spec = resolved.artifact
            service._validate_artifact_files(model_dir, spec)
            service._validate_integrated_tokenizer(model_dir, spec)
            from .chat import OpenVINOChatSession
            session = OpenVINOChatSession(
                executable_artifact.path.parent / "manifest.json",
                device=device,
                service=service,
            )
        except Exception as error:
            try:
                service.close()
            except Exception:
                pass
            raise ChatLaunchFailedError(str(error)) from error
        return ChatSessionOpened(
            session=session,
            model_id=resolved.model.model_id,
            warnings=getattr(preparation, "selection_warnings", ()),
        )
    raise RunPreparationFailedError(
        f"Unsupported or missing backend: {backend!r}"
    )
