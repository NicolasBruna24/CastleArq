"""Concrete one-shot model runners."""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import stat
import subprocess
from typing import Callable

from .execution import (
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from .runtimes import RuntimeCapability


RunProcess = Callable[..., subprocess.CompletedProcess[str]]


class ModelRunner(ABC):
    @abstractmethod
    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        """Run one validated artifact with one selected execution target."""
        raise NotImplementedError


class LlamaCppRunner(ModelRunner):
    """Run the detected llama.cpp CLI exactly once in one-shot mode."""

    def __init__(
        self,
        capability: RuntimeCapability,
        run_process: RunProcess | None = None,
    ) -> None:
        self.capability = capability
        self._run_process = run_process or subprocess.run

    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        validation_error = self._validate_inputs(
            executable_artifact, target, request
        )
        if validation_error is not None:
            return validation_error

        executable = self.capability.executable_path
        assert executable is not None
        device = self.capability.backend_argument(target.backend)
        assert device is not None
        argv = [
            executable,
            "cli",
            "--model",
            str(executable_artifact.path),
            "--device",
            device,
            "--prompt",
            request.prompt,
            "--single-turn",
        ]
        environment = {"PATH": os.defpath}
        try:
            completed = self._run_process(
                argv,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                env=environment,
                timeout=request.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return ExecutionResult(
                False,
                None,
                _output(error.stdout),
                _output(error.stderr),
                ExecutionErrorInfo(ExecutionErrorCode.TIMEOUT, "Execution timed out"),
            )
        except FileNotFoundError as error:
            return self._error_result(
                ExecutionErrorCode.EXECUTABLE_MISSING, str(error)
            )
        except PermissionError as error:
            return self._error_result(
                ExecutionErrorCode.PERMISSION_DENIED, str(error)
            )
        except OSError as error:
            return self._error_result(ExecutionErrorCode.LAUNCH_FAILED, str(error))

        if completed.returncode == 0:
            return ExecutionResult(
                True, completed.returncode, completed.stdout, completed.stderr
            )
        return ExecutionResult(
            False,
            completed.returncode,
            completed.stdout,
            completed.stderr,
            ExecutionErrorInfo(
                ExecutionErrorCode.PROCESS_FAILED,
                f"llama.cpp exited with status {completed.returncode}",
            ),
        )

    def _validate_inputs(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult | None:
        if request.artifact != executable_artifact.artifact:
            return self._error_result(
                ExecutionErrorCode.ARTIFACT_INVALID,
                "Execution request does not match the validated artifact",
            )
        if request.target is not None and request.target != target:
            return self._error_result(
                ExecutionErrorCode.INVALID_REQUEST,
                "Execution request target does not match the selected target",
            )
        if not self.capability.invocable:
            return self._error_result(
                ExecutionErrorCode.LAUNCH_FAILED,
                "llama.cpp capability is not invocable",
            )
        if not self.capability.supports_runtime_name(target.runtime):
            return self._error_result(
                ExecutionErrorCode.INVALID_REQUEST,
                "Execution target runtime does not match the capability",
            )
        device = self.capability.backend_argument(target.backend)
        if target.backend not in self.capability.supported_backends or device is None:
            return self._error_result(
                ExecutionErrorCode.INVALID_REQUEST,
                "Execution target backend is not supported",
            )
        if not os.path.isabs(executable_artifact.path):
            return self._error_result(
                ExecutionErrorCode.ARTIFACT_INVALID,
                "Validated artifact path must be absolute",
            )
        try:
            mode = os.lstat(executable_artifact.path).st_mode
        except FileNotFoundError:
            return self._error_result(
                ExecutionErrorCode.ARTIFACT_INVALID,
                "Validated artifact no longer exists",
            )
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            return self._error_result(
                ExecutionErrorCode.ARTIFACT_INVALID,
                "Validated artifact is not a regular non-symlink file",
            )
        if executable_artifact.path.name.endswith(".part"):
            return self._error_result(
                ExecutionErrorCode.ARTIFACT_INVALID,
                "Partial artifacts cannot be executed",
            )
        if not self.capability.executable_path:
            return self._error_result(
                ExecutionErrorCode.EXECUTABLE_MISSING,
                "llama.cpp executable path is unavailable",
            )
        try:
            executable_mode = os.lstat(self.capability.executable_path).st_mode
        except FileNotFoundError:
            return self._error_result(
                ExecutionErrorCode.EXECUTABLE_MISSING,
                "llama.cpp executable does not exist",
            )
        except PermissionError as error:
            return self._error_result(
                ExecutionErrorCode.PERMISSION_DENIED, str(error)
            )
        if (
            stat.S_ISLNK(executable_mode)
            or not stat.S_ISREG(executable_mode)
            or not os.access(self.capability.executable_path, os.X_OK)
        ):
            return self._error_result(
                ExecutionErrorCode.PERMISSION_DENIED,
                "llama.cpp executable is not a regular executable file",
            )
        return None

    @staticmethod
    def _error_result(code: ExecutionErrorCode, message: str) -> ExecutionResult:
        return ExecutionResult(False, None, "", "", ExecutionErrorInfo(code, message))


def _output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
