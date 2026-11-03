# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Neutral shared preparation for execution paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
    ExecutionTarget,
)
from .hardware import HardwareSnapshot, detect_hardware
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .runtimes import (
    BackendStatus,
    RuntimeCapability,
    RuntimeStatus,
    detect_backends,
)
from .selection import RuntimeBackendSelector, RuntimeSelectionError

__all__ = [
    "AdmissionDeniedError",
    "ExecutionPreparation",
    "ExecutionPreparationDependencies",
    "PreparationFailureError",
    "detect_runtime_statuses",
    "prepare_execution",
    "require_evaluation_admission",
]


@dataclass(frozen=True)
class ExecutionPreparation:
    """Validated inputs shared by one-shot run and interactive chat."""

    executable_artifact: ExecutableArtifact
    target: ExecutionTarget
    compatibility_warnings: tuple[str, ...]
    selection_warnings: tuple[str, ...]


class AdmissionDeniedError(Exception):
    """The evaluation admission gate denied execution."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PreparationFailureError(Exception):
    """Compatibility, preflight, or target selection prevented preparation."""

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


def detect_runtime_statuses(
    capability: RuntimeCapability,
) -> list[RuntimeStatus]:
    """Project a detected capability into the runtime status consumed by policy."""
    return [
        RuntimeStatus(
            "llama.cpp / llama.app",
            installed=capability.executable_path is not None,
            available=capability.available,
            gpu_backend_detected=False,
            supported_backends=capability.supported_backends,
        )
    ]


def _detect_backends(detected_gpu_backends: set[str]) -> list[BackendStatus]:
    return detect_backends(detected_gpu_backends=detected_gpu_backends)


def _assess_compatibility(
    hardware: HardwareSnapshot,
    runtimes: list[RuntimeStatus],
    backends: list[BackendStatus],
    model: ModelSpec,
) -> CompatibilityResult:
    return assess_model(
        hardware, runtimes, backends, model, config=CompatibilityConfig()
    )


@dataclass(frozen=True)
class ExecutionPreparationDependencies:
    """Typed providers used by :func:`prepare_execution`."""

    hardware_provider: Callable[[], HardwareSnapshot] = detect_hardware
    runtime_status_provider: (
        Callable[[RuntimeCapability], list[RuntimeStatus]]
    ) = detect_runtime_statuses
    backend_provider: Callable[[set[str]], list[BackendStatus]] = _detect_backends
    compatibility_provider: Callable[
        [
            HardwareSnapshot,
            list[RuntimeStatus],
            list[BackendStatus],
            ModelSpec,
        ],
        CompatibilityResult,
    ] = _assess_compatibility
    compatibility_result_provider: (
        Callable[[ModelSpec, RuntimeCapability], CompatibilityResult] | None
    ) = None
    preflight_factory: Callable[
        [ModelStore], ArtifactExecutionPreflight
    ] = ArtifactExecutionPreflight
    selector_factory: Callable[[], RuntimeBackendSelector] = RuntimeBackendSelector


def require_evaluation_admission(
    admission: EvaluationAdmission | None,
) -> None:
    """Reject missing, incomplete, or non-admitting evaluation signals."""
    if admission is None:
        raise AdmissionDeniedError(
            "Execution denied: no evaluation admission was supplied; "
            "deny-by-default applies"
        )
    status = str(getattr(admission, "status", "")).strip().lower()
    if status != "evaluated":
        raise AdmissionDeniedError(
            "Execution denied: evaluation did not produce an evaluated "
            f"outcome (status={status!r})"
        )
    verdict = getattr(admission, "verdict", None)
    value = getattr(verdict, "value", verdict)
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"compatible", "compatible_with_conditions"}:
        return
    raise AdmissionDeniedError(
        "Execution denied by evaluation admission; deny-by-default applies "
        f"(verdict={normalized or 'missing'!r})"
    )


def prepare_execution(
    model: ModelSpec,
    artifact: ArtifactSpec,
    capability: RuntimeCapability,
    model_store: ModelStore,
    *,
    admission: EvaluationAdmission | None = None,
    requested_backend: str | None = None,
    dependencies: ExecutionPreparationDependencies | None = None,
) -> ExecutionPreparation:
    """Admit and prepare an artifact without launching a runtime process."""
    deps = (
        dependencies
        if dependencies is not None
        else ExecutionPreparationDependencies()
    )
    require_evaluation_admission(admission)

    if deps.compatibility_result_provider is None:
        hardware = deps.hardware_provider()
        runtimes = deps.runtime_status_provider(capability)
        detected_gpu_backends = {
            backend for gpu in hardware.gpus for backend in gpu.backends
        }
        backends = deps.backend_provider(detected_gpu_backends)
        compatibility = deps.compatibility_provider(
            hardware, runtimes, backends, model
        )
    else:
        compatibility = deps.compatibility_result_provider(model, capability)

    preflight = deps.preflight_factory(model_store)
    try:
        executable_artifact = preflight.validate(artifact)
    except ArtifactPreflightError as error:
        raise PreparationFailureError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    selector = deps.selector_factory()
    try:
        if requested_backend is None:
            selection = selector.select(
                compatibility, capability, executable_artifact
            )
        else:
            selection = selector.select(
                compatibility,
                capability,
                executable_artifact,
                requested_backend=requested_backend,
            )
    except RuntimeSelectionError as error:
        raise PreparationFailureError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    return ExecutionPreparation(
        executable_artifact=executable_artifact,
        target=selection.target,
        compatibility_warnings=compatibility.warnings,
        selection_warnings=selection.warnings,
    )
