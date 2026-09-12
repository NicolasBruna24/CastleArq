"""Detection of installed AI runtimes and locally usable backends."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
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
