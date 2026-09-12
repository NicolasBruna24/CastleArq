"""Application orchestration for validated model execution."""

from dataclasses import replace
from typing import Callable

from .compatibility import CompatibilityResult, CompatibilityStatus
from .execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
)
from .models import ArtifactSpec, ModelSpec
from .runner import ModelRunner
from .selection import RuntimeBackendSelector, RuntimeSelectionError
from .runtimes import RuntimeCapability


CompatibilityEvaluator = Callable[[ModelSpec], CompatibilityResult]


class ModelExecutionService:
    """Coordinate compatibility, artifact preflight, selection, and execution."""

    def __init__(
        self,
        compatibility_evaluator: CompatibilityEvaluator,
        preflight: ArtifactExecutionPreflight,
        selector: RuntimeBackendSelector,
        capability: RuntimeCapability,
        runner: ModelRunner,
    ) -> None:
        self.compatibility_evaluator = compatibility_evaluator
        self.preflight = preflight
        self.selector = selector
        self.capability = capability
        self.runner = runner

    def execute(
        self,
        model: ModelSpec,
        artifact: ArtifactSpec,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        compatibility = self.compatibility_evaluator(model)
        if compatibility.status in {
            CompatibilityStatus.INCOMPATIBLE,
            CompatibilityStatus.UNKNOWN,
        }:
            return self._failure(
                ExecutionErrorCode.COMPATIBILITY_REJECTED,
                "Model compatibility does not permit execution",
                compatibility.warnings,
            )

        try:
            executable_artifact = self.preflight.validate(artifact)
        except ArtifactPreflightError as error:
            return self._failure(
                ExecutionErrorCode.PREFLIGHT_FAILED,
                error.message,
                compatibility.warnings,
            )

        try:
            selection = self.selector.select(
                compatibility,
                self.capability,
                executable_artifact,
            )
        except RuntimeSelectionError as error:
            return self._failure(
                ExecutionErrorCode.SELECTION_FAILED,
                error.message,
                compatibility.warnings,
            )

        result = self.runner.run(executable_artifact, selection.target, request)
        warnings = _merge_warnings(
            compatibility.warnings, selection.warnings, result.warnings
        )
        return result if warnings == result.warnings else replace(result, warnings=warnings)

    @staticmethod
    def _failure(
        code: ExecutionErrorCode,
        message: str,
        warnings: tuple[str, ...],
    ) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            error=ExecutionErrorInfo(code, message),
            warnings=warnings,
        )


def _merge_warnings(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for warning in group:
            if warning not in merged:
                merged.append(warning)
    return tuple(merged)
