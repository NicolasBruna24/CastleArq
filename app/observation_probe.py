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

"""B9.11: environment observation probes and parsers.

Provides pure parsing functions and injectable observation probes:
- Injected I/O: ``CommandRunner``, ``FileReader``, ``WhichFinder``, and ``TimestampProvider``.
- Pure parsers: ``parse_os_release``, ``parse_meminfo``, and ``parse_lspci_nn``.
- Explicit error semantics: non-zero exit, missing files, or timeouts produce
  ``ObservedValue`` with state ``UNAVAILABLE`` or ``ERROR``; they never raise
  and never imply ``UNSUPPORTED`` or ``FALSE``.
- Zero inference: no backend assumption, no GPU-Vulkan association, no synthetic
  vendor derivation.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform
import re
from typing import Callable, Sequence

from .observation_domain import (
    DeviceObservation,
    EnvironmentContext,
    HardwareObservation,
    ObservationState,
    ObservedValue,
    PlatformObservation,
    RuntimeObservation,
)


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution probe."""

    returncode: int
    stdout: str
    stderr: str
    error: str | None = None


# Injectable protocols / callables (Ratified Decision D-11.3)
CommandRunner = Callable[[Sequence[str], float], CommandResult]
FileReader = Callable[[str], str | None]
WhichFinder = Callable[[str], str | None]
TimestampProvider = Callable[[], str]


# Explicit llama.cpp backend evidence (no inference).
#
# A backend string (``vulkan``/``cuda``/``sycl``) counts as explicit evidence
# ONLY when it appears in one of these syntactic positions inside the
# ``--help`` output (case-insensitive):
#   1. A CLI flag token: ``--vulkan``, ``--cuda``, ``--sycl`` (also single-dash
#      ``-vulkan``), matched at a token boundary.
#   2. A backend enumeration: the word ``backend``/``backends`` followed by
#      ``:`` or ``=`` on the same line, with the backend name as a whole word
#      after it (e.g. ``backends: cuda, cpu``).
#   3. A build declaration: ``built with <backend>`` / ``build with <backend>``
#      / ``compiled with <backend>`` with the backend name as a whole word.
# Mere incidental mentions (e.g. "vulkan-like rendering", "cuda cores
# available on your GPU", prose without a flag/enumeration/build marker)
# are NOT evidence and produce no ``ObservedValue``.
_BACKEND_FLAG_RE = re.compile(r"(?im)(?:^|\s)--?(vulkan|cuda|sycl)\b")
_BACKEND_ENUM_RE = re.compile(r"(?im)\bbackends?\s*[:=][^\n]*\b(vulkan|cuda|sycl)\b")
_BACKEND_BUILD_RE = re.compile(
    r"(?im)\b(?:built|build|compiled)\s+with\b[^\n]*\b(vulkan|cuda|sycl)\b"
)


def detect_backend_evidence(help_text: str) -> tuple[str, ...]:
    """Return backends with explicit evidence in ``--help`` text, in order.

    Pure function (zero I/O). Checks each of ``vulkan``/``cuda``/``sycl``
    against the three explicit-evidence patterns above. Whole-word matching
    only; incidental prose never matches.
    """
    found: list[str] = []
    for match in _BACKEND_FLAG_RE.finditer(help_text):
        backend = match.group(1).lower()
        if backend not in found:
            found.append(backend)
    for match in _BACKEND_ENUM_RE.finditer(help_text):
        backend = match.group(1).lower()
        if backend not in found:
            found.append(backend)
    for match in _BACKEND_BUILD_RE.finditer(help_text):
        backend = match.group(1).lower()
        if backend not in found:
            found.append(backend)
    order = {"vulkan": 0, "cuda": 1, "sycl": 2}
    return tuple(sorted(found, key=lambda b: order[b]))


# ----------------------------------------------------------------------
# Pure Parsers (Zero I/O)
# ----------------------------------------------------------------------

def parse_os_release(text: str) -> dict[str, str]:
    """Pure parser for /etc/os-release contents.

    Strips surrounding quotes and boundary whitespace. Does not read files.
    """
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        fields[key] = val
    return fields


@dataclass(frozen=True)
class ParseMemResult:
    """Result of parsing /proc/meminfo.

    Exactly one of ``bytes`` or ``error_kind`` is set:
    - ``bytes``: parsed total bytes (when parsing succeeded).
    - ``error_kind``: one of ``"absent"`` (no MemTotal line),
      ``"bad_number"`` (numeric field absent/unparseable/negative), or
      ``"bad_unit"`` (unit missing or not an explicit kb/b/mb spelling).
    """

    bytes: int | None = None
    error_kind: str | None = None


def parse_meminfo(text: str) -> ParseMemResult:
    """Pure parser for /proc/meminfo to extract MemTotal in bytes.

    Returns a ``ParseMemResult`` that distinguishes three failure modes:
    - ``error_kind="absent"``: no MemTotal line present (absence).
    - ``error_kind="bad_number"``: MemTotal line found but the numeric field
      is absent or not a non-negative integer (invalid format). No value
      is invented.
    - ``error_kind="bad_unit"``: number is valid but the unit is missing or
      not one of kb/b/mb (unrecognized unit). Conversion requires an
      explicit unit; a bare number never implies bytes.

    Does not infer, does not raise.
    """
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("MemTotal:"):
            continue
        parts = line.split()
        # Expect format: MemTotal: <number> <unit>
        if len(parts) < 2:
            # "MemTotal:" with no numeric field at all.
            return ParseMemResult(error_kind="bad_number")
        try:
            num = int(parts[1])
        except ValueError:
            return ParseMemResult(error_kind="bad_number")
        if num < 0:
            return ParseMemResult(error_kind="bad_number")
        if len(parts) < 3:
            # Number present but unit absent -> unrecognized unit.
            return ParseMemResult(error_kind="bad_unit")
        unit = parts[2].lower()
        if unit in ("kb", "k", "kib"):
            # /proc/meminfo uses "kB" (decimal kB = 1024 bytes); accept
            # common kB spellings explicitly, nothing else.
            return ParseMemResult(bytes=num * 1024)
        if unit == "b":
            return ParseMemResult(bytes=num)
        if unit in ("mb", "mib"):
            return ParseMemResult(bytes=num * 1024 * 1024)
        return ParseMemResult(error_kind="bad_unit")
    return ParseMemResult(error_kind="absent")


_LSPCI_LINE_RE = re.compile(
    r"^[0-9a-fA-F:\.]+\s+([^\[:]+):\s+(.*)$"
)
_PCI_ID_RE = re.compile(r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]")


def parse_lspci_nn(text: str) -> tuple[dict[str, str | None], ...]:
    """Pure parser for `lspci -nn` output lines for display/3D controllers.

    Extracts verbatim:
    - raw_device_class: e.g. "VGA compatible controller"
    - name: device description string verbatim
    - vendor_id: 4-digit hex string (without synthetic vendor name conversion)
    - device_id: 4-digit hex string
    """
    devices: list[dict[str, str | None]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not re.search(
            r"(VGA compatible controller|3D controller|Display controller)",
            line,
            re.IGNORECASE,
        ):
            continue

        pci_match = _PCI_ID_RE.search(line)
        vendor_id = pci_match.group(1).lower() if pci_match else None
        device_id = pci_match.group(2).lower() if pci_match else None

        # Clean description
        desc = line
        # Strip slot if present (e.g. "00:02.0 ")
        slot_match = re.match(r"^[0-9a-fA-F:\.]+\s+(.*)$", line)
        if slot_match:
            desc = slot_match.group(1).strip()

        devices.append(
            {
                "name": desc,
                "vendor_id": vendor_id,
                "device_id": device_id,
            }
        )
    return tuple(devices)


# ----------------------------------------------------------------------
# Probe Components (Effectful with Injected I/O)
# ----------------------------------------------------------------------

class EnvironmentObserver:
    """Acquires environment observations with injected dependencies."""

    def __init__(
        self,
        command_runner: CommandRunner,
        file_reader: FileReader,
        which_finder: WhichFinder,
        timestamp_provider: TimestampProvider,
    ) -> None:
        self._run_cmd = command_runner
        self._read_file = file_reader
        self._which = which_finder
        self._timestamp = timestamp_provider

    def observe_platform(self) -> PlatformObservation:
        """Observe OS family, release, architecture, and distribution.

        Empty or whitespace-only ``platform.system()`` / ``release()`` /
        ``machine()`` values carry no observed fact: they map to
        ``UNAVAILABLE`` with ``value=None`` (never the invented string
        ``"unknown"``).
        """
        os_sys = (platform.system() or "").strip()
        if os_sys:
            os_family = ObservedValue(
                state=ObservationState.OBSERVED,
                value=os_sys.lower(),
                source="python:platform.system",
            )
        else:
            os_family = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="python:platform.system",
                detail="platform.system() returned empty string",
            )
        os_rel = (platform.release() or "").strip()
        if os_rel:
            os_release = ObservedValue(
                state=ObservationState.OBSERVED,
                value=os_rel,
                source="python:platform.release",
            )
        else:
            os_release = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="python:platform.release",
                detail="platform.release() returned empty string",
            )
        mach = (platform.machine() or "").strip()
        if mach:
            architecture = ObservedValue(
                state=ObservationState.OBSERVED,
                value=mach,
                source="python:platform.machine",
            )
        else:
            architecture = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="python:platform.machine",
                detail="platform.machine() returned empty string",
            )

        os_release_text = self._read_file("/etc/os-release")
        if os_release_text is None:
            distribution = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="file:/etc/os-release",
                detail="/etc/os-release not accessible or not found",
            )
        else:
            fields = parse_os_release(os_release_text)
            dist_id = fields.get("ID")
            if dist_id:
                distribution = ObservedValue(
                    state=ObservationState.OBSERVED,
                    value=dist_id,
                    source="file:/etc/os-release",
                )
            else:
                distribution = ObservedValue(
                    state=ObservationState.UNAVAILABLE,
                    value=None,
                    source="file:/etc/os-release",
                    detail="ID field absent in /etc/os-release",
                )

        return PlatformObservation(
            os_family=os_family,
            os_release=os_release,
            architecture=architecture,
            distribution=distribution,
        )

    def _safe_run(self, command: Sequence[str], timeout: float) -> CommandResult:
        """Execute ``command_runner`` without ever raising.

        A runner signalling failure via ``returncode != 0`` or ``error`` is
        passed through. A runner *raising* ``OSError``/``TimeoutError`` (or
        any ``Exception`` from the injected double) is converted into an
        ERROR ``CommandResult`` so no failure is silently discarded.
        """
        try:
            return self._run_cmd(tuple(command), timeout)
        except TimeoutError as exc:
            return CommandResult(
                returncode=-1, stdout="", stderr="", error=f"timeout: {exc}"
            )
        except OSError as exc:
            return CommandResult(
                returncode=-1, stdout="", stderr="", error=f"os error: {exc}"
            )
        except Exception as exc:  # defensive: injected doubles must not crash probes
            return CommandResult(
                returncode=-1, stdout="", stderr="", error=f"probe failed: {exc}"
            )

    def observe_hardware(self) -> HardwareObservation:
        """Observe system memory and display/GPU devices.

        When ``lspci`` is absent: memory is recorded normally; ``devices``
        is empty (no structured device evidence exists) and
        ``acquisition_error`` is an UNAVAILABLE-state ``ObservedValue``.

        When ``lspci`` is present but exits non-zero, times out, or raises
        ``OSError``: ``devices`` is empty AND ``acquisition_error`` records
        the failure as an ERROR-state ``ObservedValue`` so callers can
        detect the difference from a system with no display devices.
        Nothing is silently discarded with ``pass``.
        """
        # 1. Memory — use ParseMemResult to distinguish absence from errors
        mem_text = self._read_file("/proc/meminfo")
        if mem_text is None:
            memory_val = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="file:/proc/meminfo",
                detail="/proc/meminfo not accessible or absent",
            )
        else:
            mem_result = parse_meminfo(mem_text)
            if mem_result.bytes is not None:
                memory_val = ObservedValue(
                    state=ObservationState.OBSERVED,
                    value=mem_result.bytes,
                    source="file:/proc/meminfo",
                )
            elif mem_result.error_kind == "absent":
                memory_val = ObservedValue(
                    state=ObservationState.UNAVAILABLE,
                    value=None,
                    source="file:/proc/meminfo",
                    detail="MemTotal line not found in /proc/meminfo",
                )
            else:
                # bad_number or bad_unit
                memory_val = ObservedValue(
                    state=ObservationState.ERROR,
                    value=None,
                    source="file:/proc/meminfo",
                    detail=f"MemTotal parse failed ({mem_result.error_kind})",
                )

        # 2. Devices via lspci
        devices: list[DeviceObservation] = []
        acquisition_error: ObservedValue | None = None

        lspci_path = self._which("lspci")
        if not lspci_path:
            # lspci binary absent — no device evidence; devices stays empty.
            # No spurious CPU record: system RAM != CPU device memory.
            # Represent the absence explicitly as UNAVAILABLE.
            acquisition_error = ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value=None,
                source="which:lspci",
                detail="lspci binary not found in PATH",
            )
        else:
            cmd_res = self._safe_run((lspci_path, "-nn"), 2.0)
            if cmd_res.returncode != 0 or cmd_res.error is not None:
                # Record the failure explicitly instead of silently discarding it.
                error_detail = (
                    cmd_res.error
                    or f"lspci exited with returncode {cmd_res.returncode}"
                )
                acquisition_error = ObservedValue(
                    state=ObservationState.ERROR,
                    value=None,
                    source="command:lspci -nn",
                    detail=error_detail,
                )
            else:
                parsed_devs = parse_lspci_nn(cmd_res.stdout)
                for d in parsed_devs:
                    dev_name = ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=d["name"],
                        source="command:lspci -nn",
                    )
                    v_id = (
                        ObservedValue(
                            state=ObservationState.OBSERVED,
                            value=d["vendor_id"],
                            source="command:lspci -nn",
                        )
                        if d["vendor_id"] is not None
                        else ObservedValue(
                            state=ObservationState.UNAVAILABLE,
                            value=None,
                            source="command:lspci -nn",
                            detail="vendor_id absent in lspci line",
                        )
                    )
                    d_id = (
                        ObservedValue(
                            state=ObservationState.OBSERVED,
                            value=d["device_id"],
                            source="command:lspci -nn",
                        )
                        if d["device_id"] is not None
                        else ObservedValue(
                            state=ObservationState.UNAVAILABLE,
                            value=None,
                            source="command:lspci -nn",
                            detail="device_id absent in lspci line",
                        )
                    )
                    devices.append(
                        DeviceObservation(
                            device_type="gpu",
                            name=dev_name,
                            vendor_id=v_id,
                            device_id=d_id,
                            total_memory_bytes=ObservedValue(
                                state=ObservationState.UNAVAILABLE,
                                source="command:lspci -nn",
                                detail="VRAM byte count not provided by lspci -nn",
                            ),
                            driver_name=ObservedValue(
                                state=ObservationState.UNAVAILABLE,
                                source="command:lspci -nn",
                                detail="Kernel driver not probed by basic lspci -nn",
                            ),
                            driver_version=ObservedValue(
                                state=ObservationState.UNAVAILABLE,
                                source="command:lspci -nn",
                                detail="Driver version not probed by basic lspci -nn",
                            ),
                        )
                    )

        return HardwareObservation(
            memory_total_bytes=memory_val,
            devices=tuple(devices),
            acquisition_error=acquisition_error,
        )

    def observe_runtimes(self) -> tuple[RuntimeObservation, ...]:
        """Observe installed runtimes: restricted strictly to llama.cpp and ollama."""
        observations: list[RuntimeObservation] = []

        # 1. llama.cpp
        llama_candidates = ("llama-cli", "llama", "llama.app")
        llama_path: str | None = None
        for cand in llama_candidates:
            found = self._which(cand)
            if found:
                llama_path = found
                break

        if not llama_path:
            observations.append(
                RuntimeObservation(
                    canonical_id="llama.cpp",
                    executable_path=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source="which:llama-cli",
                        detail="No llama.cpp binary found in PATH",
                    ),
                    raw_version=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source="command:llama-cli --version",
                        detail="Cannot probe version because binary is unavailable",
                    ),
                    detected_backends=(),
                )
            )
        else:
            # Probe version
            res_ver = self._safe_run((llama_path, "--version"), 2.0)
            if res_ver.returncode == 0 and not res_ver.error:
                ver_text = res_ver.stdout.strip() or res_ver.stderr.strip()
                if ver_text:
                    ver_val = ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=ver_text,
                        source=f"command:{llama_path} --version",
                    )
                else:
                    ver_val = ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        value=None,
                        source=f"command:{llama_path} --version",
                        detail="--version produced no output",
                    )
            else:
                ver_val = ObservedValue(
                    state=ObservationState.ERROR,
                    value=None,
                    source=f"command:{llama_path} --version",
                    detail=res_ver.error or f"Exited with returncode {res_ver.returncode}",
                )

            # Probe backends via help: explicit syntactic evidence only.
            # Criterion (documented in detect_backend_evidence): a backend
            # counts ONLY as CLI flag (--vulkan), backend enumeration
            # (backends: cuda), or build declaration (built with sycl).
            # Incidental prose never counts. No inference.
            res_help = self._safe_run((llama_path, "--help"), 2.0)
            backends: list[ObservedValue] = []
            if res_help.returncode == 0 and not res_help.error:
                help_text = f"{res_help.stdout}\n{res_help.stderr}"
                for backend in detect_backend_evidence(help_text):
                    backends.append(
                        ObservedValue(
                            state=ObservationState.OBSERVED,
                            value=backend,
                            source=f"command:{llama_path} --help",
                        )
                    )

            observations.append(
                RuntimeObservation(
                    canonical_id="llama.cpp",
                    executable_path=ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=llama_path,
                        source="which:llama-cli",
                    ),
                    raw_version=ver_val,
                    detected_backends=tuple(backends),
                )
            )

        # 2. Ollama
        ollama_path = self._which("ollama")
        if not ollama_path:
            observations.append(
                RuntimeObservation(
                    canonical_id="ollama",
                    executable_path=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source="which:ollama",
                        detail="ollama binary not found in PATH",
                    ),
                    raw_version=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source="command:ollama --version",
                        detail="Cannot probe version because binary is unavailable",
                    ),
                    detected_backends=(),
                )
            )
        else:
            res_ollama = self._safe_run((ollama_path, "--version"), 2.0)
            if res_ollama.returncode == 0 and not res_ollama.error:
                ollama_text = res_ollama.stdout.strip() or res_ollama.stderr.strip()
                if ollama_text:
                    ver_val = ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=ollama_text,
                        source=f"command:{ollama_path} --version",
                    )
                else:
                    ver_val = ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        value=None,
                        source=f"command:{ollama_path} --version",
                        detail="--version produced no output",
                    )
            else:
                ver_val = ObservedValue(
                    state=ObservationState.ERROR,
                    value=None,
                    source=f"command:{ollama_path} --version",
                    detail=res_ollama.error or f"Exited with returncode {res_ollama.returncode}",
                )

            observations.append(
                RuntimeObservation(
                    canonical_id="ollama",
                    executable_path=ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=ollama_path,
                        source="which:ollama",
                    ),
                    raw_version=ver_val,
                    detected_backends=(),
                )
            )

        return tuple(observations)

    def capture_context(self) -> EnvironmentContext:
        """Snapshot complete environment observations."""
        ts = self._timestamp()
        platform_obs = self.observe_platform()
        hardware_obs = self.observe_hardware()
        runtimes_obs = self.observe_runtimes()
        return EnvironmentContext(
            timestamp=ts,
            platform=platform_obs,
            hardware=hardware_obs,
            runtimes=runtimes_obs,
        )
