from __future__ import annotations

import os
import shlex
import subprocess
from typing import Callable


class SyclEnvironmentError(RuntimeError):
    pass


class SyclEnvironmentProvider:
    def __init__(self, setvars_path=None, timeout_seconds=10.0, run_process=None):
        self.setvars_path = setvars_path
        self.timeout_seconds = timeout_seconds
        self._run_process = run_process or subprocess.run

    def load(self) -> dict[str, str]:
        if not self.setvars_path:
            raise SyclEnvironmentError("oneAPI setvars.sh path is not configured")
        if not os.path.isfile(self.setvars_path):
            raise SyclEnvironmentError("oneAPI setvars.sh does not exist")
        if not os.access(self.setvars_path, os.R_OK):
            raise SyclEnvironmentError("oneAPI setvars.sh is not readable")
        command = (
            "bash",
            "-c",
            f"source {shlex.quote(self.setvars_path)} >/dev/null 2>&1 && env -0",
        )
        try:
            completed = self._run_process(
                command,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise SyclEnvironmentError(f"failed to execute setvars.sh: {error}") from error
        if getattr(completed, "returncode", 1) != 0:
            raise SyclEnvironmentError(
                f"setvars.sh failed with exit code {getattr(completed, 'returncode', None)}"
            )
        stdout = getattr(completed, "stdout", b"")
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if not stdout:
            raise SyclEnvironmentError("setvars.sh produced no environment")
        environment = {}
        for entry in stdout.split(b"\x00"):
            if not entry:
                continue
            if b"=" not in entry:
                raise SyclEnvironmentError("malformed environment entry")
            key, value = entry.split(b"=", 1)
            environment[key.decode("utf-8", errors="replace")] = value.decode("utf-8", errors="replace")
        for required in ("PATH", "LD_LIBRARY_PATH", "ONEAPI_ROOT"):
            if required not in environment:
                raise SyclEnvironmentError(f"missing required variable: {required}")
        return environment
