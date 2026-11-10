
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

"""Hardware detection with Linux-specific implementations."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from .runtimes import RuntimeProbeResult, query_llama_devices
from pathlib import Path
from typing import Callable, Sequence


CommandRunner = Callable[[Sequence[str]], str | None]
Which = Callable[[str], str | None]


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
    pci_id: str | None = None
    device_id: str | None = None
    vram_bytes: int | None = None
    vram_available_bytes: int | None = None
    sources: dict[str, str] = field(default_factory=dict)
    backends: list[str] = field(default_factory=list)
    driver: str = "Unknown"
    pci_address: str | None = None

    @property
    def vram_gib(self) -> float | None:
        return self.vram_bytes / (1024**3) if self.vram_bytes is not None else None

    @property
    def vram_available_gib(self) -> float | None:
        return (
            self.vram_available_bytes / (1024**3)
            if self.vram_available_bytes is not None
            else None
        )


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


_HEX_DIGITS = frozenset("0123456789abcdef")


def _normalize_pci_address(address: str | None) -> str | None:
    """Normalize a PCI address to the ``0000:00:02.0`` form with explicit domain.

    Accepts both ``0000:00:02.0`` (explicit domain) and ``00:02.0`` (domain
    omitted by ``lspci``). Returns ``None`` when the text is not a usable PCI
    address.
    """
    if not address:
        return None
    address = address.strip().lower()
    parts = address.split(":")
    if len(parts) == 3:
        domain, bus, slot_func = parts
    elif len(parts) == 2:
        domain, bus, slot_func = "0000", parts[0], parts[1]
    else:
        return None
    slot, separator, func = slot_func.partition(".")
    if not separator or not (len(domain) == 4 and len(bus) == 2 and len(slot) == 2 and len(func) == 1):
        return None
    if not all(character in _HEX_DIGITS for character in domain + bus + slot + func):
        return None
    domain_value = int(domain, 16)
    bus_value = int(bus, 16)
    device_value = int(slot, 16)
    function_value = int(func, 16)
    if not (0 <= domain_value <= 0xFFFF):
        return None
    if not (0 <= bus_value <= 0xFF):
        return None
    if not (0 <= device_value <= 0x1F):
        return None
    if not (0 <= function_value <= 0x7):
        return None
    return f"{domain}:{bus}:{slot}.{func}"


def parse_lspci(text: str) -> list[GPUInfo]:
    """Parse display/3D controllers from lspci -mm output or normal lspci output."""
    gpus: list[GPUInfo] = []
    for line in text.splitlines():
        if not re.search(r"(VGA compatible controller|3D controller|Display controller)", line, re.I):
            continue
        pci_address = _normalize_pci_address(line.split(None, 1)[0] if line.split() else None)
        pci_match = re.search(r"\[([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\]", line)
        pci_id = pci_match.group(1).lower() if pci_match else None
        device_id = pci_id.split(":", 1)[1] if pci_id else None
        if '"' in line:
            fields = re.findall(r'"([^"]*)"', line)
            name = fields[-1] if fields else line
        else:
            remainder = line.split(None, 1)[1] if line.split(None, 1) else line
            name = remainder.strip()
            name = re.sub(
                r"^(VGA compatible controller|3D controller|Display controller)\s*(?:\[\d+\])?:\s*",
                "",
                name,
                flags=re.I,
            )
        name = re.sub(r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]\s*$", "", name).strip()
        lower = name.lower()
        vendor = (
            "NVIDIA" if "nvidia" in lower else
            "AMD" if any(x in lower for x in ("amd", "radeon", "advanced micro")) else
            "Intel" if "intel" in lower else
            _vendor_from_pci(pci_id)
        )
        gpus.append(
            GPUInfo(
                name=name or "Unknown",
                vendor=vendor,
                pci_id=pci_id,
                device_id=device_id,
                pci_address=pci_address,
                sources={"gpu": "lspci"},
            )
        )
    return gpus


def parse_external_gpu_memory(
    text: str, source: str
) -> list[tuple[str, int, int | None, str | None]]:
    """Parse common Vulkan/llama device lines into name, total and available bytes."""
    observations: list[tuple[str, int, int | None, str | None]] = []
    for line in text.splitlines():
        if not re.search(r"(device\s*name|vulkan\d+|gpu)", line, re.I):
            continue
        name_match = re.search(r"(?:device\s*name|vulkan\d+)\s*[:=]\s*(.+?)(?=\s*\(|$)", line, re.I)
        if not name_match:
            name_match = re.search(r"(?:device\s*name|vulkan\d+)\s*[:=]\s*(.+)$", line, re.I)
        memory = re.search(r"([\d.]+)\s*(MiB|GiB|MB|GB)\b(?:[^\d]+([\d.]+)\s*(?:MiB|GiB|MB|GB)\s*free)?", line, re.I)
        if not name_match or not memory:
            continue
        name = name_match.group(1).strip().rstrip(")")
        total = _memory_to_bytes(float(memory.group(1)), memory.group(2))
        available = (
            _memory_to_bytes(float(memory.group(3)), memory.group(2))
            if memory.group(3)
            else None
        )
        backend = "Vulkan" if re.search(r"vulkan\d+", line, re.I) else None
        observations.append((name, total, available, backend))
    return observations


class LinuxHardwareDetector:
    def __init__(
        self,
        command_runner: CommandRunner = default_command_runner,
        proc_root: Path = Path("/proc"),
        sys_root: Path = Path("/sys"),
        which: Which = shutil.which,
    ) -> None:
        self._run = command_runner
        self._proc_root = proc_root
        self._sys_root = sys_root
        self._which = which

    def detect(self) -> HardwareSnapshot:
        architecture = platform.machine() or "Unknown"
        cpu_text = self._read(self._proc_root / "cpuinfo")
        mem_text = self._read(self._proc_root / "meminfo")
        lspci = self._run(("lspci", "-D", "-nn"))
        gpus = parse_lspci(lspci or "")
        self._apply_sysfs(gpus)
        self._apply_external_memory(gpus)
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

    def _apply_sysfs(self, gpus: list[GPUInfo]) -> None:
        drm_dir = self._sys_root / "class/drm"
        if not drm_dir.is_dir():
            return
        # Primera pasada: recopilar las tarjetas DRM válidas con su dirección PCI.
        drm_cards: list[tuple[Path, str]] = []
        for entry in sorted(drm_dir.iterdir()):
            # Only real DRM cards participate. Render nodes, control devices and
            # other connectors do not match ``cardN`` and must be ignored.
            if not re.match(r"^card\d+$", entry.name):
                continue
            device_link = entry / "device"
            try:
                resolved = device_link.resolve(strict=True)
            except (OSError, RuntimeError):
                # Missing, dangling or invalid symlink: no reliable PCI address,
                # no VRAM or driver is assigned from it.
                continue
            if not resolved.is_dir():
                # The resolved target is not a directory: not a PCI device.
                continue
            address = _normalize_pci_address(resolved.name)
            if address is None:
                continue
            drm_cards.append((resolved, address))
        # Segunda pasada: agrupar por BDF y procesar únicamente direcciones con
        # exactamente una tarjeta DRM asociada. Dos o más tarjetas con el mismo
        # BDF impiden cualquier asignación de sysfs para esa dirección.
        bdf_counts: dict[str, int] = {}
        for _, address in drm_cards:
            bdf_counts[address] = bdf_counts.get(address, 0) + 1
        for resolved, address in drm_cards:
            if bdf_counts[address] != 1:
                # Dos o más tarjetas DRM comparten el mismo BDF: no asignar
                # información de sysfs a esa GPU (evita asociaciones ambiguas ni
                # sobrescrituras silenciosas).
                continue
            matches = [
                candidate for candidate in gpus if candidate.pci_address == address
            ]
            if len(matches) != 1:
                # Zero matches: no GPU seen by lspci with this address.
                # More than one: ambiguous PCI identity, do not invent an
                # association.
                continue
            gpu = matches[0]
            total = self._read_int(resolved / "mem_info_vram_total")
            used = self._read_int(resolved / "mem_info_vram_used")
            available = max(total - used, 0) if total is not None and used is not None else None
            index = gpus.index(gpu)
            gpus[index] = self._with_gpu(
                gpu,
                vram_bytes=total,
                vram_available_bytes=available,
                source="sysfs",
                driver=self._driver_name(resolved),
            )

    def _apply_external_memory(self, gpus: list[GPUInfo]) -> None:
        commands = []
        vulkan = self._which("vulkaninfo")
        if vulkan:
            commands.append((("vulkaninfo", "--summary"), "vulkan"))
        llama = next((self._which(name) for name in ("llama", "llama.app", "llama-cli") if self._which(name)), None)
        if llama:
            def _probe(command: Sequence[str]) -> RuntimeProbeResult:
                output = self._run(tuple(command))
                if output is None:
                    return RuntimeProbeResult(1, "", "")
                return RuntimeProbeResult(0, output, "")

            devices = query_llama_devices(llama, _probe)
            if devices is not None:
                commands.append((devices, "llama.app"))
        for command, source in commands:
            if isinstance(command, str):
                text = command
            else:
                text = self._run(command) or ""
            observations = parse_external_gpu_memory(text, source)
            for name, total, available, backend in observations:
                gpu = self._match_gpu(gpus, name)
                if gpu is not None:
                    index = gpus.index(gpu)
                    gpus[index] = self._with_gpu(
                        gpu,
                        vram_bytes=total if gpu.vram_bytes is None else gpu.vram_bytes,
                        vram_available_bytes=available,
                        source=source,
                        backend=backend,
                    )

    def _match_gpu(self, gpus: list[GPUInfo], external_name: str) -> GPUInfo | None:
        name = external_name.lower()
        for gpu in gpus:
            if gpu.name.lower() in name or name in gpu.name.lower():
                return gpu
        return gpus[0] if len(gpus) == 1 else None

    def _driver_name(self, device: Path) -> str:
        try:
            return (device / "driver").resolve().name or "Unknown"
        except OSError:
            return "Unknown"

    @staticmethod
    def _with_gpu(
        gpu: GPUInfo,
        *,
        vram_bytes: int | None = None,
        vram_available_bytes: int | None = None,
        source: str | None = None,
        backend: str | None = None,
        driver: str | None = None,
    ) -> GPUInfo:
        sources = dict(gpu.sources)
        if source:
            sources["vram"] = source
        backends = list(gpu.backends)
        if backend and backend not in backends:
            backends.append(backend)
        return GPUInfo(
            name=gpu.name,
            vendor=gpu.vendor,
            pci_id=gpu.pci_id,
            device_id=gpu.device_id,
            pci_address=gpu.pci_address,
            vram_bytes=vram_bytes if vram_bytes is not None else gpu.vram_bytes,
            vram_available_bytes=(
                vram_available_bytes
                if vram_available_bytes is not None
                else gpu.vram_available_bytes
            ),
            sources=sources,
            backends=backends,
            driver=driver if driver and driver != "Unknown" else gpu.driver,
        )

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


_PLATFORM_MARKERS: tuple[tuple[str, str], ...] = (
    ("linux", "linux"),
    ("windows", "windows"),
    ("mac os", "macos"),
    ("macos", "macos"),
    ("darwin", "macos"),
)
_PLATFORM_TOKENS: dict[str, str] = {
    "linux": "linux",
    "windows": "windows",
    "darwin": "macos",
}


def detect_platform(
    operating_system: str | None = None,
    *,
    system: str | None = None,
) -> str:
    """Canonical platform token used to match platform-specific recipes.

    Prefers the OS text the project already detected
    (``HardwareSnapshot.operating_system``). When that text does not name a
    known family (e.g. a distro pretty name such as ``"Ubuntu 24.04"``), it
    falls back to the same ``platform.system()`` primitive the hardware
    detector uses (or the explicitly injected ``system`` text, for
    deterministic tests). Unknown platforms yield ``""`` and Linux is never
    assumed.
    """
    text = (operating_system or "").strip().lower()
    for marker, token in _PLATFORM_MARKERS:
        if marker in text:
            return token
    system_text = (system if system is not None else platform.system())
    return _PLATFORM_TOKENS.get(system_text.strip().lower(), "")


def _vendor_from_pci(pci_id: str | None) -> str:
    vendors = {"10de": "NVIDIA", "1002": "AMD", "8086": "Intel"}
    return vendors.get(pci_id.split(":", 1)[0].lower(), "Unknown") if pci_id else "Unknown"


def _memory_to_bytes(value: float, unit: str) -> int:
    multiplier = 1024**2 if unit.lower() in {"mib", "mb"} else 1024**3
    return int(value * multiplier)
