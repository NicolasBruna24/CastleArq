"""Runtime and backend selection for validated local artifacts."""

from dataclasses import dataclass
from enum import Enum

from .compatibility import CompatibilityResult, CompatibilityStatus
from .execution import ExecutableArtifact, ExecutionTarget
from .runtimes import RuntimeCapability


class SelectionErrorCode(str, Enum):
    INCOMPATIBLE_MODEL = "incompatible_model"
    UNKNOWN_COMPATIBILITY = "unknown_compatibility"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
    RUNTIME_MISMATCH = "runtime_mismatch"
    FORMAT_UNSUPPORTED = "format_unsupported"
    BACKEND_UNSUPPORTED = "backend_unsupported"
    CPU_FALLBACK_UNAVAILABLE = "cpu_fallback_unavailable"


class RuntimeSelectionError(Exception):
    """Raised when compatibility cannot be satisfied by a runtime capability."""

    def __init__(self, code: SelectionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RuntimeSelection:
    target: ExecutionTarget
    warnings: tuple[str, ...] = ()


class RuntimeBackendSelector:
    """Combine compatibility facts with one detected runtime capability."""

    def select(
        self,
        compatibility: CompatibilityResult,
        capability: RuntimeCapability,
        executable_artifact: ExecutableArtifact,
        *,
        allow_cpu_fallback: bool = False,
    ) -> RuntimeSelection:
        self._validate_compatibility(compatibility)
        if not capability.invocable:
            raise RuntimeSelectionError(
                SelectionErrorCode.RUNTIME_UNAVAILABLE,
                "Selected runtime is not available for invocation",
            )
        if not capability.supports_runtime_name(
            compatibility.recommended_runtime or ""
        ):
            raise RuntimeSelectionError(
                SelectionErrorCode.RUNTIME_MISMATCH,
                "Compatibility recommendation does not match runtime capability",
            )
        if executable_artifact.artifact.format.upper() not in {
            value.upper() for value in capability.supported_formats
        }:
            raise RuntimeSelectionError(
                SelectionErrorCode.FORMAT_UNSUPPORTED,
                "Artifact format is not supported by the runtime",
            )

        recommended_backend = compatibility.recommended_backend
        if recommended_backend in capability.supported_backends:
            warnings = (
                ("Compatibility is marginal; execution may be resource constrained.",)
                if compatibility.status == CompatibilityStatus.MARGINAL
                else ()
            )
            return RuntimeSelection(
                ExecutionTarget(capability.name, recommended_backend),
                warnings,
            )

        if allow_cpu_fallback and "CPU" in capability.supported_backends:
            warning = (
                "Explicit CPU fallback selected because the recommended backend "
                "is unavailable."
            )
            return RuntimeSelection(
                ExecutionTarget(capability.name, "CPU"),
                (warning,),
            )
        raise RuntimeSelectionError(
            SelectionErrorCode.BACKEND_UNSUPPORTED,
            "Recommended backend is not supported by the runtime",
        )

    @staticmethod
    def _validate_compatibility(result: CompatibilityResult) -> None:
        if result.status == CompatibilityStatus.INCOMPATIBLE:
            raise RuntimeSelectionError(
                SelectionErrorCode.INCOMPATIBLE_MODEL,
                "Model compatibility is explicitly incompatible",
            )
        if result.status == CompatibilityStatus.UNKNOWN:
            raise RuntimeSelectionError(
                SelectionErrorCode.UNKNOWN_COMPATIBILITY,
                "Model compatibility is unknown",
            )
