"""Hardware detection with Linux-specific implementations."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


CommandRunner = Callable[[Sequence[str]], str | None]


@dataclass(frozen=True)
class CPUInfo:
    model: str = "Unknown"
    architecture: str = "Unknown"
    cores: int | None = None


@dataclass(frozen=True)
class MemoryInfo:
    total_bytes: int | None = None

    @property
    def total_gib(self) -> float | None:
        return self.total_bytes / (1024**3) if self.total_bytes is not None else None


@dataclass(frozen=True)
class GPUInfo:
    name: str = "Unknown"
    vendor: str = "Unknown"
    vram_bytes: int | None = None
    driver: str = "Unknown"

    @property
    def vram_gib(self) -> float | None:
        return self.vram_bytes / (1024**3) if self.vram_bytes is not None else None


@dataclass(frozen=True)
class HardwareSnapshot:
    operating_system: str
    architecture: str
    cpu: CPUInfo
    memory: MemoryInfo
    gpus: list[GPUInfo] = field(default_factory=list)


def default_command_runner(command: Sequence[str]) -> str | None:
    """Run a command without raising when it is absent or fails."""
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def parse_cpuinfo(text: str, architecture: str | None = None) -> CPUInfo:
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in {"model name", "Hardware", "Processor"}:
            values.setdefault(key.strip(), value.strip())
    model = values.get("model name") or values.get("Hardware") or values.get("Processor") or "Unknown"
    cores = len(re.findall(r"^processor\s*:", text, re.MULTILINE)) or None
    return CPUInfo(model=model, architecture=architecture or platform.machine() or "Unknown", cores=cores)


def parse_meminfo(text: str) -> MemoryInfo:
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", text, re.MULTILINE)
    return MemoryInfo(total_bytes=int(match.group(1)) * 1024 if match else None)


def parse_lspci(text: str) -> list[GPUInfo]:
    """Parse display/3D controllers from lspci -mm output or normal lspci output."""
    gpus: list[GPUInfo] = []
    for line in text.splitlines():
        if not re.search(r"(VGA compatible controller|3D controller|Display controller)", line, re.I):
            continue
        if '"' in line:
            fields = re.findall(r'"([^"]*)"', line)
            name = fields[-1] if fields else line
        else:
            name = line.split(":", 2)[-1].strip()
            name = re.sub(r"^(VGA compatible controller|3D controller|Display controller):\s*", "", name, flags=re.I)
        lower = name.lower()
        vendor = "NVIDIA" if "nvidia" in lower else "AMD" if any(x in lower for x in ("amd", "radeon", "advanced micro")) else "Intel" if "intel" in lower else "Unknown"
        gpus.append(GPUInfo(name=name or "Unknown", vendor=vendor))
    return gpus


class LinuxHardwareDetector:
    def __init__(
        self,
        command_runner: CommandRunner = default_command_runner,
        proc_root: Path = Path("/proc"),
        sys_root: Path = Path("/sys"),
    ) -> None:
        self._run = command_runner
        self._proc_root = proc_root
        self._sys_root = sys_root

    def detect(self) -> HardwareSnapshot:
        architecture = platform.machine() or "Unknown"
        cpu_text = self._read(self._proc_root / "cpuinfo")
        mem_text = self._read(self._proc_root / "meminfo")
        lspci = self._run(("lspci", "-nn"))
        gpus = parse_lspci(lspci or "")
        vram = self._read_int(self._sys_root / "class/drm/card0/device/mem_info_vram_total")
        if vram is not None and len(gpus) == 1:
            gpus[0] = GPUInfo(
                name=gpus[0].name,
                vendor=gpus[0].vendor,
                vram_bytes=vram,
                driver=gpus[0].driver,
            )
        return HardwareSnapshot(
            operating_system=self._detect_os(),
            architecture=architecture,
            cpu=parse_cpuinfo(cpu_text, architecture),
            memory=parse_meminfo(mem_text),
            gpus=gpus,
        )

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _read_int(self, path: Path) -> int | None:
        value = self._read(path).strip()
        try:
            return int(value) if value else None
        except ValueError:
            return None

    def _detect_os(self) -> str:
        release = self._read(Path("/etc/os-release"))
        match = re.search(r'^PRETTY_NAME="?(.*?)"?$', release, re.MULTILINE)
        return match.group(1) if match else platform.system() or "Unknown"


def detect_hardware() -> HardwareSnapshot:
    if platform.system() == "Linux":
        return LinuxHardwareDetector().detect()
    return HardwareSnapshot(
        operating_system=platform.system() or "Unknown",
        architecture=platform.machine() or "Unknown",
        cpu=CPUInfo(architecture=platform.machine() or "Unknown"),
        memory=MemoryInfo(),
    )
