
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
    InvalidExecutionRequestError,
    validate_execution_request,
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
        try:
            validate_execution_request(request)
        except InvalidExecutionRequestError as error:
            return self._failure(ExecutionErrorCode.INVALID_REQUEST, str(error), ())
        if request.artifact != artifact:
            return self._failure(
                ExecutionErrorCode.INVALID_REQUEST,
                "Execution request artifact does not match the execution artifact",
                (),
            )
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

        if request.target is not None and request.target != selection.target:
            return self._failure(
                ExecutionErrorCode.INVALID_REQUEST,
                "Execution request target does not match the selected target",
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
