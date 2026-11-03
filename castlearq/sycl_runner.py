from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone

from .execution import (
    ExecutableArtifact,
    ExecutionDiagnostics,
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from .offload_evidence import assess_gpu_offload
from .runner import ExecutionRunner
from .runtimes import RuntimeCapability
from .sycl_environment import SyclEnvironmentError, SyclEnvironmentProvider


def build_sycl_runner(
    capability: RuntimeCapability,
    runtime_version: str | None = None,
) -> SyclLlamaRunner:
    """Build a ``SyclLlamaRunner`` from a capability and/or environment.

    Resolution precedence for the executable:
    1. ``capability.executable_path`` (when the capability carries it).
    2. ``CASTLEARQ_SYCL_RUNTIME`` environment variable.

    ``setvars.sh`` is always resolved from ``CASTLEARQ_SYCL_SETVARS``.

    Raises ``ValueError`` when configuration is missing, so callers can
    convert it to their own error type.
    """
    if (
        not isinstance(capability, RuntimeCapability)
        or capability.name != "llama.cpp SYCL"
        or "SYCL" not in capability.supported_backends
    ):
        raise ValueError(
            "SYCL runner requires a llama.cpp SYCL capability that supports SYCL"
        )

    executable_path = capability.executable_path
    if not executable_path:
        executable_path = os.environ.get("CASTLEARQ_SYCL_RUNTIME")
    if not executable_path:
        raise ValueError(
            "SYCL runner is not configured: set CASTLEARQ_SYCL_RUNTIME to "
            "the SYCL llama executable path"
        )
    setvars_path = os.environ.get("CASTLEARQ_SYCL_SETVARS")
    if not setvars_path:
        raise ValueError(
            "SYCL runner is not configured: set CASTLEARQ_SYCL_SETVARS to "
            "the oneAPI setvars.sh path"
        )
    # Extract version from capability when provided; takes priority over
    # the explicit runtime_version parameter so that a detected version
    # is never silently overridden.
    detected_version = capability.version
    runtime_version_final = (
        detected_version
        if detected_version is not None
        else runtime_version
    )
    kwargs = {
        "executable_path": executable_path,
        "setvars_path": setvars_path,
    }
    if runtime_version_final is not None:
        kwargs["runtime_version"] = runtime_version_final
    return SyclLlamaRunner(**kwargs)
class SyclLlamaRunner(ExecutionRunner):


    def __init__(self, executable_path, setvars_path, env_provider=None, run_process=None,
                 gpu_layers=999, ctx_size=2048, n_predict=64, timeout_seconds=120.0, runtime_version=None):
        self.executable_path = executable_path
        self.setvars_path = setvars_path
        self.env_provider = env_provider or SyclEnvironmentProvider(setvars_path)
        self._run_process = run_process or subprocess.run
        self.gpu_layers = gpu_layers
        self.ctx_size = ctx_size
        self.n_predict = n_predict
        self.runtime_version = runtime_version
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget | None = None,
        request: ExecutionRequest | None = None,
    ) -> ExecutionResult:
        # request may be object with prompt, timeout_seconds
        prompt = getattr(request, "prompt", "") if request is not None else ""
        timeout = getattr(request, "timeout_seconds", None) if request is not None else None
        timeout = timeout or self.timeout_seconds
        try:
            environment = self.env_provider.load()
        except SyclEnvironmentError as error:
            return ExecutionResult(False, None, "", "", ExecutionErrorInfo(ExecutionErrorCode.EXECUTABLE_MISSING, str(error)))
        argv = [
            self.executable_path,
            "-m", str(getattr(executable_artifact, "path", executable_artifact)),
            "--device", "SYCL0",
            "-ngl", str(self.gpu_layers),
            "-c", str(self.ctx_size),
            "-n", str(self.n_predict),
            "-p", prompt,
            "--single-turn",
            "-v",
        ]
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        try:
            completed = self._run_process(
                argv,
                capture_output=True,
                text=False,
                check=False,
                shell=False,
                env=environment,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, (bytes, bytearray)) else (error.stdout or "")
            stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, (bytes, bytearray)) else (error.stderr or "")
            return ExecutionResult(
                False, None, stdout, stderr,
                ExecutionErrorInfo(ExecutionErrorCode.TIMEOUT, "Execution timed out"),
                diagnostics=ExecutionDiagnostics(
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    elapsed_seconds=time.monotonic()-started_monotonic,
                    stdout_bytes=len(stdout.encode()),
                    stderr_bytes=len(stderr.encode()),
                    exit_code=None,
                    timed_out=True,
                    terminated_normally=False,
                ),
                offload_evidence=assess_gpu_offload(stdout, stderr, None, timed_out=True, backend="SYCL"),
            )
        except (OSError, subprocess.SubprocessError) as error:
            return ExecutionResult(False, None, "", "", ExecutionErrorInfo(ExecutionErrorCode.EXECUTABLE_MISSING, str(error)))
        stdout = completed.stdout.decode(errors="replace") if isinstance(completed.stdout, (bytes, bytearray)) else str(completed.stdout or "")
        stderr = completed.stderr.decode(errors="replace") if isinstance(completed.stderr, (bytes, bytearray)) else str(completed.stderr or "")
        success = completed.returncode == 0
        evidence = assess_gpu_offload(stdout, stderr, completed.returncode, runtime_version=getattr(self, "runtime_version", None), backend="SYCL")
        error_info = None if success else ExecutionErrorInfo(ExecutionErrorCode.INVALID_REQUEST, "SYCL runtime failed")
        return ExecutionResult(
            success,
            completed.returncode,
            stdout,
            stderr,
            error_info,
            diagnostics=ExecutionDiagnostics(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                elapsed_seconds=time.monotonic()-started_monotonic,
                stdout_bytes=len(stdout.encode()),
                stderr_bytes=len(stderr.encode()),
                exit_code=completed.returncode,
                timed_out=False,
                terminated_normally=success,
            ),
            offload_evidence=evidence,
        )
