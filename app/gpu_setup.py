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

"""Read-only functional probes for GPU software stacks (Block A).

This module answers *"what GPU-related software is verifiably present and
functional?"* while :mod:`app.hardware` keeps answering *"what hardware
exists"*. It produces facts (``True``/``False``/``None``) for a future
recommendation engine; it never recommends installations, never executes
anything that modifies the system, and never uses a shell.
"""

from __future__ import annotations

import glob
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from .hardware import CommandRunner, Which, default_command_runner

OS_RELEASE_PATH = Path("/etc/os-release")
DRI_PATH = Path("/dev/dri")
VULKAN_ICD_DIRS: tuple[str, ...] = (
    "/usr/share/vulkan/icd.d",
    "/etc/vulkan/icd.d",
    "/usr/local/share/vulkan/icd.d",
)
_LEVEL_ZERO_LIB_PATTERNS: tuple[str, ...] = (
    "/usr/lib/x86_64-linux-gnu/libze*.so*",
    "/usr/lib64/libze*.so*",
    "/usr/lib/libze*.so*",
)
_LLAMA_BINARIES: tuple[str, ...] = ("llama", "llama-cli", "llama.app")


@dataclass(frozen=True)
class FunctionalCheck:
    """Outcome of one read-only verification.

    ``passed`` is ``True`` when availability/functionality was confirmed,
    ``False`` when it was checked and found absent/non-functional, and
    ``None`` when it could not be determined with the available probes (a
    missing helper tool alone must never produce ``False``).
    """

    passed: bool | None
    detail: str
    source: str


@dataclass(frozen=True)
class OsReleaseInfo:
    """Structured identity fields from ``/etc/os-release``."""

    id: str | None = None
    version_id: str | None = None
    id_like: tuple[str, ...] = ()
    pretty_name: str | None = None


@dataclass(frozen=True)
class GpuSoftwareStatus:
    """Verifiable GPU software facts, separate from ``GPUInfo``."""

    kernel_driver: FunctionalCheck = field(
        default_factory=lambda: FunctionalCheck(
            None, "kernel driver not determined", "sysfs"))
    drm_device: FunctionalCheck = field(
        default_factory=lambda: FunctionalCheck(
            None, "DRM devices not determined", "filesystem:/dev/dri"))
    vulkan: FunctionalCheck = field(
        default_factory=lambda: FunctionalCheck(
            None, "Vulkan status not determined", "probes"))
    opencl: FunctionalCheck = field(
        default_factory=lambda: FunctionalCheck(
            None, "OpenCL status not determined", "probes"))
    level_zero: FunctionalCheck = field(
        default_factory=lambda: FunctionalCheck(
            None, "Level Zero status not determined", "probes"))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_os_release(text: str) -> OsReleaseInfo:
    """Parse ``/etc/os-release`` content into structured fields."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            continue
        values[key.strip()] = _unquote(value)
    raw_like = values.get("ID_LIKE", "")
    id_like = tuple(item for item in raw_like.split() if item)
    return OsReleaseInfo(
        id=values.get("ID") or None,
        version_id=values.get("VERSION_ID") or None,
        id_like=id_like,
        pretty_name=values.get("PRETTY_NAME") or None,
    )


def read_os_release_info(
    read: Callable[[Path], str] | None = None,
) -> OsReleaseInfo:
    """Read structured OS identity; unknown fields stay ``None`` on failure."""
    try:
        if read is not None:
            text = read(OS_RELEASE_PATH)
        else:
            text = OS_RELEASE_PATH.read_text(encoding="utf-8")
    except OSError:
        return OsReleaseInfo()
    return parse_os_release(text)


def probe_kernel_driver(driver: str | None) -> FunctionalCheck:
    """Represent the sysfs kernel driver name as a functional check."""
    if not driver or driver == "Unknown":
        return FunctionalCheck(
            None, "kernel driver unknown", "sysfs:/sys/class/drm")
def probe_kernel_driver(driver: str | None) -> FunctionalCheck:
    """Represent the sysfs kernel driver name as a functional check."""
    if not driver or driver == "Unknown":
        return FunctionalCheck(
            None, "kernel driver unknown", "sysfs:/sys/class/drm")
    return FunctionalCheck(
        True, driver, "sysfs:/sys/class/drm/card/device/driver")


def probe_drm_devices(
    dri_path: Path | str = DRI_PATH,
    dri_entries: Sequence[str] | None = None,
) -> FunctionalCheck:
    """Check for DRM/render devices using the filesystem only (read-only)."""
    source = f"filesystem:{dri_path}"
    if dri_entries is None:
        try:
            entries = sorted(entry.name for entry in Path(dri_path).iterdir())
        except OSError:
            return FunctionalCheck(
                None, f"cannot list {dri_path}", source)
    else:
        entries = list(dri_entries)
    devices = sorted(
        name for name in entries
        if name.startswith("card") or name.startswith("renderD")
    )
    if devices:
        return FunctionalCheck(
            True, f"DRM devices present: {', '.join(devices)}", source)
    return FunctionalCheck(False, "no DRM/render devices found", source)


def find_vulkan_icds(
    icd_dirs: Sequence[str] = VULKAN_ICD_DIRS,
    icd_files: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """List Vulkan ICD manifests (``*.json``); never installs anything."""
    if icd_files is not None:
        return tuple(icd_files)
    found: list[str] = []
    for directory in icd_dirs:
        try:
            found.extend(
                sorted(path for path in glob.glob(f"{directory}/*.json")))
        except OSError:
            continue
    return tuple(found)


def _llama_devices_text(
    run: CommandRunner,
    which: Which,
    llama_devices: str | None,
    probe_llama: bool,
) -> str | None:
    """Return ``llama --list-devices`` output, or ``None`` when unavailable."""
    if llama_devices is not None:
        return llama_devices
    if not probe_llama:
        return None
    binary = next(
        (found for name in _LLAMA_BINARIES if (found := which(name))),
        None,
    )
    if binary is None:
        return None
    for command in ((binary, "--list-devices"), (binary, "serve", "--list-devices")):
        output = run(command)
        if output is not None:
            return output
    return None


def probe_vulkan(
    run: CommandRunner = default_command_runner,
    which: Which = shutil.which,
    icd_dirs: Sequence[str] = VULKAN_ICD_DIRS,
    icd_files: Sequence[str] | None = None,
    llama_devices: str | None = None,
    probe_llama: bool = True,
) -> FunctionalCheck:
    """Distinguish ICD presence from confirmed Vulkan functionality.

    ``vulkaninfo`` being absent never implies ``False``; only a runtime that
    was actually queried (llama.cpp device list, ``vulkaninfo --summary``)
    can confirm ``True``, and only a queried runtime reporting no Vulkan
    device yields ``False``.
    """
    icds = find_vulkan_icds(icd_dirs, icd_files)
    devices = _llama_devices_text(run, which, llama_devices, probe_llama)
    if devices is not None and "Vulkan" in devices:
        return FunctionalCheck(
            True,
            "llama runtime reports a Vulkan device",
            "llama --list-devices",
        )
    vulkaninfo = which("vulkaninfo")
    if vulkaninfo is not None:
        summary = run((vulkaninfo, "--summary"))
        if summary is not None and summary.strip():
            return FunctionalCheck(
                True,
                "vulkaninfo --summary succeeded",
                "vulkaninfo --summary",
            )
    if devices is not None:
        detail = "llama runtime reports no Vulkan device"
        if icds:
            detail += (
                f"; {len(icds)} ICD file(s) present"
                " but not confirmed functional"
            )
        return FunctionalCheck(False, detail, "llama --list-devices")
    if icds:
        return FunctionalCheck(
            None,
            f"{len(icds)} ICD file(s) found"
            f" ({icds[0]}); functional status unknown",
            "filesystem:icd.d",
        )
    return FunctionalCheck(
        None,
        "no ICD files found and no functional probe available",
        "filesystem:icd.d",
    )


def probe_opencl(
    run: CommandRunner = default_command_runner,
    which: Which = shutil.which,
) -> FunctionalCheck:
    """Secondary OpenCL check; ``clinfo`` presence alone is not enough."""
    clinfo = which("clinfo")
    if clinfo is None:
        return FunctionalCheck(
            None, "clinfo not installed; OpenCL status unknown", "which:clinfo")
    output = run((clinfo, "-l"))
    if output is None:
        return FunctionalCheck(
            None, "clinfo execution failed; OpenCL status unknown", "clinfo -l")
    if "Platform" in output:
        return FunctionalCheck(
            True, "clinfo reports an OpenCL platform", "clinfo -l")
    return FunctionalCheck(
        False, "clinfo reports no OpenCL platforms", "clinfo -l")


def probe_level_zero(
    run: CommandRunner = default_command_runner,
    which: Which = shutil.which,
    libze_paths: Sequence[str] | None = None,
) -> FunctionalCheck:
    """Basic Level Zero presence check from the local library cache."""
    if libze_paths is None:
        found: list[str] = []
        for pattern in _LEVEL_ZERO_LIB_PATTERNS:
            try:
                found.extend(sorted(glob.glob(pattern)))
            except OSError:
                continue
        libze_paths = tuple(found)
    if libze_paths:
        return FunctionalCheck(
            True,
            f"Level Zero loader library present: {libze_paths[0]}",
            "filesystem:libze",
        )
    ldconfig = which("ldconfig")
    cache = run((ldconfig, "-p")) if ldconfig is not None else None
    if cache is not None and "libze_" in cache:
        return FunctionalCheck(
            True,
            "Level Zero loader present in library cache",
            "ldconfig -p",
        )
    if cache is not None:
        return FunctionalCheck(
            False,
            "no Level Zero loader in library cache",
            "ldconfig -p",
        )
    return FunctionalCheck(
        None,
        "Level Zero status could not be determined",
        "ldconfig/filesystem",
    )


def diagnose_gpu_software(
    driver: str | None = "Unknown",
    *,
    run: CommandRunner = default_command_runner,
    which: Which = shutil.which,
    dri_path: Path | str = DRI_PATH,
    dri_entries: Sequence[str] | None = None,
    icd_dirs: Sequence[str] = VULKAN_ICD_DIRS,
    icd_files: Sequence[str] | None = None,
    llama_devices: str | None = None,
    probe_llama: bool = True,
    libze_paths: Sequence[str] | None = None,
) -> GpuSoftwareStatus:
    """Collect all Block A software facts for one GPU (read-only)."""
    return GpuSoftwareStatus(
        kernel_driver=probe_kernel_driver(driver),
        drm_device=probe_drm_devices(dri_path, dri_entries),
        vulkan=probe_vulkan(
            run, which, icd_dirs, icd_files, llama_devices, probe_llama),
        opencl=probe_opencl(run, which),
        level_zero=probe_level_zero(run, which, libze_paths),
    )


