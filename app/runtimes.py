
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

"""Detection of installed AI runtimes and locally usable backends."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from enum import Enum
import subprocess
from typing import Callable


@dataclass(frozen=True)
class RuntimeStatus:
    name: str
    installed: bool
    available: bool
    gpu_backend_detected: bool
    supported_backends: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.available:
            return "available"
        if self.installed:
            return "installed but not available"
        return "not installed"

    def supports_backend(self, backend: str) -> bool:
        return backend in self.supported_backends


@dataclass(frozen=True)
class BackendStatus:
    name: str
    available: bool


Which = Callable[[str], str | None]
Run = Callable[[tuple[str, ...]], "RuntimeProbeResult"]


class RuntimeAvailability(str, Enum):
    NOT_FOUND = "not_found"
    FOUND_UNUSABLE = "found_unusable"
    AVAILABLE = "available"
    PROBE_ERROR = "probe_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LlamaRuntimeIdentity:
    canonical_id: str
    executable_path: str | None
    executable_name: str | None
    version: str | None
    build_identifier: str | None
    availability: RuntimeAvailability
    reason: str | None = None


@dataclass(frozen=True)
class ResolvedLlamaRuntime:
    identity: LlamaRuntimeIdentity
    capability: RuntimeCapability | None


class PromptInputMode(str, Enum):
    ARGUMENT = "argument"
    FILE = "file"


@dataclass(frozen=True)
class RuntimeProbeResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RuntimeCapability:
    """Validated capabilities of a detected runtime executable."""

    name: str
    executable_path: str | None
    version: str | None
    supported_formats: tuple[str, ...]
    supported_backends: tuple[str, ...]
    prompt_input_modes: tuple[PromptInputMode, ...]
    supports_one_shot: bool
    available: bool
    reason: str | None = None
    compatibility_names: tuple[str, ...] = ()
    backend_arguments: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Runtime capability name is required")
        if self.available and not self.executable_path:
            raise ValueError("Available runtime requires an executable path")
        if self.available and not self.supports_one_shot:
            raise ValueError("Available runtime must support one-shot execution")
        if self.available and not self.supported_formats:
            raise ValueError("Available runtime requires a supported format")
        if self.available and not self.supported_backends:
            raise ValueError("Available runtime requires a supported backend")
        if self.available and not self.prompt_input_modes:
            raise ValueError("Available runtime requires a prompt input mode")

    @property
    def invocable(self) -> bool:
        return self.available and self.supports_one_shot

    def supports_runtime_name(self, name: str) -> bool:
        return name == self.name or name in self.compatibility_names

    def backend_argument(self, backend: str) -> str | None:
        return dict(self.backend_arguments).get(backend)


def query_llama_devices(executable: str, run: Run) -> str | None:
    """Query ``--list-devices`` output trying known llama subcommands.

    Tries, in order, ``cli --list-devices``, ``serve --list-devices`` and
    bare ``--list-devices``; only a probe with ``returncode == 0`` is
    accepted. Returns the combined ``stdout``/``stderr`` text of the first
    successful variant, or ``None`` when no variant works. Never raises for
    normal probe failures (a raising ``run`` propagates, as with every
    other probe caller). Read-only: delegates execution to ``run``.
    """
    for command in (
        (executable, "cli", "--list-devices"),
        (executable, "serve", "--list-devices"),
        (executable, "--list-devices"),
    ):
        result = run(command)
        if result.returncode == 0:
            return f"{result.stdout}\n{result.stderr}"
    return None


def _detect_llama_capability(
    which: Which = shutil.which,
    run: Run | None = None,
) -> RuntimeCapability:
    """Probe the fixed llama CLI entry point without loading a model."""

    executable = which("llama")
    if executable is None:
        return RuntimeCapability(
            name="llama.cpp CLI",
            executable_path=None,
            version=None,
            supported_formats=(),
            supported_backends=(),
            prompt_input_modes=(),
            supports_one_shot=False,
            available=False,
            reason="llama executable was not found",
        )

    probe = run or _run_runtime_probe
    version_result = probe((executable, "cli", "--version"))
    help_result = probe((executable, "cli", "--help"))
    if version_result.returncode != 0 or help_result.returncode != 0:
        reason = "llama cli version/help probe failed"
        return RuntimeCapability(
            name="llama.cpp CLI",
            executable_path=executable,
            version=_version_line(
                f"{version_result.stdout}\n{version_result.stderr}"
            ),
            supported_formats=(),
            supported_backends=(),
            prompt_input_modes=(),
            supports_one_shot=False,
            available=False,
            reason=reason,
        )

    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    required_options = ("--model", "--prompt")
    if not all(option in help_text for option in required_options):
        return RuntimeCapability(
            name="llama.cpp CLI",
            executable_path=executable,
            version=_version_line(
                f"{version_result.stdout}\n{version_result.stderr}"
            ),
            supported_formats=(),
            supported_backends=(),
            prompt_input_modes=(),
            supports_one_shot=False,
            available=False,
            reason="llama cli lacks required model or prompt options",
        )

    devices_text = query_llama_devices(executable, probe)
    if devices_text is None:
        devices_text = ""
    backends = ["CPU"]
    if "Vulkan" in devices_text:
        backends.append("Vulkan")
    prompt_modes = [PromptInputMode.ARGUMENT]
    if "--file" in help_text:
        prompt_modes.append(PromptInputMode.FILE)
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path=executable,
        version=_version_line(f"{version_result.stdout}\n{version_result.stderr}"),
        supported_formats=("GGUF",),
        supported_backends=tuple(backends),
        prompt_input_modes=tuple(prompt_modes),
        supports_one_shot=True,
        available=True,
        compatibility_names=("llama.cpp / llama.app", "llama.cpp"),
        backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
    )


def _version_line(output: str) -> str | None:
    for line in output.splitlines():
        if line.strip():
            return line.strip()
    return None


def detect_llama_capability(
    which: Which = shutil.which,
    run: Run | None = None,
) -> RuntimeCapability:
    """Compatibility entry point backed by the unified resolver."""
    resolved = resolve_llama_runtime(which=which, run=run)
    if resolved.capability is not None:
        return resolved.capability
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path=resolved.identity.executable_path,
        version=resolved.identity.version,
        supported_formats=(),
        supported_backends=(),
        prompt_input_modes=(),
        supports_one_shot=False,
        available=False,
        reason=resolved.identity.reason,
    )


def _build_identifier(version: str | None) -> str | None:
    if not version:
        return None
    match = re.search(r"build\s+([^\s,)]+)", version, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"commit\s+([0-9a-f]+)", version, re.IGNORECASE)
    return match.group(1) if match else None


def resolve_llama_runtime(
    which: Which = shutil.which,
    run: Run | None = None,
) -> ResolvedLlamaRuntime:
    """Resolve and validate the official ``llama`` launcher from PATH."""
    executable = which("llama")
    if executable is None:
        return ResolvedLlamaRuntime(
            LlamaRuntimeIdentity("llama.cpp", None, None, None, None,
                                 RuntimeAvailability.NOT_FOUND,
                                 "llama executable was not found"),
            None,
        )
    name = executable.rsplit("/", 1)[-1]
    if os.path.exists(executable) and not os.access(executable, os.X_OK):
        identity = LlamaRuntimeIdentity(
            "llama.cpp", executable, name, None, None,
            RuntimeAvailability.FOUND_UNUSABLE, "llama is not executable",
        )
        return ResolvedLlamaRuntime(identity, None)
    capability = _detect_llama_capability(which=lambda _: executable, run=run)
    version = capability.version
    availability = (
        RuntimeAvailability.AVAILABLE if capability.available
        else RuntimeAvailability.FOUND_UNUSABLE
    )
    identity = LlamaRuntimeIdentity(
        "llama.cpp", executable, name, version, _build_identifier(version),
        availability, capability.reason,
    )
    return ResolvedLlamaRuntime(identity, capability if capability.available else None)


def _run_runtime_probe(command: tuple[str, ...]) -> RuntimeProbeResult:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=5
        )
    except (OSError, subprocess.SubprocessError) as error:
        return RuntimeProbeResult(1, "", str(error))
    return RuntimeProbeResult(result.returncode, result.stdout, result.stderr)


def detect_runtimes(which: Which = shutil.which) -> list[RuntimeStatus]:
    llama_installed = any(
        which(binary) for binary in ("llama", "llama-cli", "llama-server", "llama.app")
    )
    ollama_path = which("ollama")
    ollama_available = False
    if ollama_path:
        ollama_available = _command_succeeds((ollama_path, "list"))
    return [
        RuntimeStatus(
            "llama.cpp / llama.app", llama_installed, llama_installed, False,
            ("Vulkan", "CPU"),
        ),
        RuntimeStatus("Ollama", bool(ollama_path), ollama_available, False, ()),
    ]


def detect_backends(
    which: Which = shutil.which,
    detected_gpu_backends: set[str] | None = None,
) -> list[BackendStatus]:
    checks = (
        ("Vulkan", "vulkaninfo"),
        ("OpenCL", "clinfo"),
        ("SYCL", "sycl-ls"),
        ("CUDA", "nvidia-smi"),
        ("ROCm", "rocminfo"),
    )
    detected_gpu_backends = detected_gpu_backends or set()
    return [
        *[
            BackendStatus(name, which(binary) is not None or name in detected_gpu_backends)
            for name, binary in checks
        ],
        BackendStatus("CPU", True),
    ]


def _command_succeeds(command: tuple[str, ...]) -> bool:
    import subprocess

    try:
        result = subprocess.run(command, capture_output=True, check=False, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def recommend(runtimes: list[RuntimeStatus], backends: list[BackendStatus]) -> tuple[str, str]:
    runtime = next((item.name for item in runtimes if item.available), "None detected")
    backend = next((item.name for item in backends if item.available), "None detected")
    return runtime, backend
