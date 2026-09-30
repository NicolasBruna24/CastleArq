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

Ratified contracts enforced here:
- AD-01 (positive evidence only): a fact is ``OBSERVED`` only under one of the
  closed syntactic forms documented on :func:`detect_backend_evidence`. The mere
  presence of a backend word -- in prose, in a negation, or anywhere else on a
  marked line -- is never evidence.
- AD-02 (provenance is the real operation): every ``source`` names the operation
  that actually produced the fact; no hypothetical command is ever recorded.
- AD-04 (coverage): every observation reports which probe families were
  attempted, so an empty collection is never read as observed absence.
- Acquisition vs defect: only failures of the *external operation*
  (:data:`ACQUISITION_ERRORS`) become ``ERROR`` observations. Defects of the
  observer itself (``TypeError``, ``AttributeError``, ``KeyError``,
  ``AssertionError``, ...) propagate instead of being disguised as environment
  errors.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform
import re
from typing import Callable, Sequence

from .observation_domain import (
    CoverageEntry,
    CoverageState,
    DeviceObservation,
    EnvironmentContext,
    HardwareObservation,
    ObservationCoverage,
    ObservationFamily,
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

#: Failures of the *external operation*, and only those, become an ERROR
#: ``CommandResult`` (and therefore an ``ObservedValue`` in state ``ERROR``).
#: Anything else raised by the injected runner -- ``TypeError``,
#: ``AttributeError``, ``KeyError``, ``AssertionError``,
#: ``NotImplementedError``, ... -- is a defect of the observer or of the runner
#: itself and propagates: a programming bug must never be recorded as an
#: environment observation error. Runners that surface ``subprocess`` failures
#: must translate them to ``OSError``/``TimeoutError`` or report them through
#: ``CommandResult.error``.
ACQUISITION_ERRORS: tuple[type[Exception], ...] = (TimeoutError, OSError)

#: Coverage of the per-device families of every ``DeviceObservation``: B9.11
#: parses what ``lspci -nn`` reports and never inspects sysfs, so per-device
#: memory and driver facts are NOT_OBSERVED, never "observed but unavailable"
#: (AD-04). Coverage takes precedence over the state of those facts.
_DEVICE_COVERAGE = ObservationCoverage(entries=(
    CoverageEntry(ObservationFamily.DEVICE_MEMORY, CoverageState.NOT_OBSERVED),
    CoverageEntry(ObservationFamily.DEVICE_DRIVER, CoverageState.NOT_OBSERVED),
))

#: Coverage of the environment families that ``capture_context`` always
#: attempts, whatever their outcome (AD-04).
_CONTEXT_COVERAGE = ObservationCoverage(entries=(
    CoverageEntry(ObservationFamily.PLATFORM, CoverageState.OBSERVED),
    CoverageEntry(ObservationFamily.HARDWARE_MEMORY, CoverageState.OBSERVED),
    CoverageEntry(ObservationFamily.HARDWARE_DEVICES, CoverageState.OBSERVED),
))


# Explicit llama.cpp backend evidence (Ratified Decision AD-01: positive
# evidence only). A backend string (``vulkan``/``cuda``/``sycl``) counts as
# evidence ONLY under one of these closed, verifiable syntactic forms inside
# the ``--help`` output (case-insensitive):
#   1. Flag token: ``--vulkan`` / ``-vulkan`` standing as a whole token.
#   2. Item list: the word ``backend``/``backends`` followed by ``:`` or ``=``
#      and then a list made EXCLUSIVELY of known backend-ish tokens
#      (e.g. ``backends: cuda, cpu``). Any other word on that line makes the
#      line prose, which is what rejects ``backends: cpu only, cuda not
#      compiled in`` and ``backend: CPU (CUDA disabled)``.
#   3. Build clause: ``built|build|compiled with <backend>`` with the backend
#      name IMMEDIATELY after ``with``, which is what rejects
#      ``built with care; vulkan unsupported``.
# Mere incidental mentions ("vulkan-like rendering", "cuda cores available on
# your GPU"), negations, and words placed elsewhere on a marked line are NOT
# evidence and produce no ``ObservedValue``. No NLP, no proximity search, no
# scoring, no heuristic interpretation.
_BACKEND_NAMES = ("vulkan", "cuda", "sycl")
_BACKEND_FLAG_RE = re.compile(r"(?im)(?:^|[\s,])--?(vulkan|cuda|sycl)(?=[\s,=]|$)")
_BACKEND_ENUM_MARKER_RE = re.compile(r"(?im)\bbackends?\s*[:=](?P<items>[^\n]*)$")
_BACKEND_BUILD_RE = re.compile(
    r"(?im)\b(?:built|build|compiled)\s+with\s+(vulkan|cuda|sycl)\b"
)
#: Tokens accepted as items of a ``backend(s):`` enumeration. Anything outside
#: this closed vocabulary turns the line into prose, and prose is not evidence.
_BACKEND_ITEM_TOKENS = frozenset({
    "cpu", "gpu", "vulkan", "cuda", "sycl", "opencl", "rocm", "hip",
    "metal", "kompute", "blas", "none", "all", "auto", "default",
})
_BACKEND_ITEM_SPLIT_RE = re.compile(r"[\s,|/]+")


def _enumeration_backends(help_text: str) -> tuple[str, ...]:
    """Backends declared by a pure ``backend(s):`` item list (AD-01).

    Pure function. The remainder of the marker line must be a list built
    exclusively from :data:`_BACKEND_ITEM_TOKENS`; if any other word appears the
    line is prose and yields no evidence at all.
    """
    found: list[str] = []
    for match in _BACKEND_ENUM_MARKER_RE.finditer(help_text):
        raw_items = match.group("items").strip()
        if not raw_items:
            continue
        tokens = [
            token
            for token in _BACKEND_ITEM_SPLIT_RE.split(raw_items.lower())
            if token
        ]
        if not tokens or any(
            token not in _BACKEND_ITEM_TOKENS for token in tokens
        ):
            continue
        for token in tokens:
            if token in _BACKEND_NAMES and token not in found:
                found.append(token)
    return tuple(found)


def detect_backend_evidence(help_text: str) -> tuple[str, ...]:
    """Return backends with positive evidence in ``--help`` text (AD-01).

    Pure function (zero I/O). Only the three closed syntactic forms documented
    above count: a bare mention, a negation, incidental prose, or a backend word
    placed elsewhere on a marked line are NOT evidence. The result is ordered
    canonically (``vulkan``, ``cuda``, ``sycl``) so identical input always
    yields an identical tuple.
    """
    found: list[str] = []
    for match in _BACKEND_FLAG_RE.finditer(help_text):
        backend = match.group(1).lower()
        if backend not in found:
            found.append(backend)
    for backend in _enumeration_backends(help_text):
        if backend not in found:
            found.append(backend)
    for match in _BACKEND_BUILD_RE.finditer(help_text):
        backend = match.group(1).lower()
        if backend not in found:
            found.append(backend)
    order = {name: index for index, name in enumerate(_BACKEND_NAMES)}
    return tuple(sorted(found, key=lambda backend: order[backend]))


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
        """Execute ``command_runner``, converting acquisition failures only.

        A runner signalling failure via ``returncode != 0`` or ``error`` is
        passed through. A runner *raising* a failure of the external operation
        (:data:`ACQUISITION_ERRORS`) becomes an ERROR ``CommandResult``, so no
        acquisition failure is silently discarded. Any other exception
        propagates: a programming defect is not an environment observation.
        """
        try:
            return self._run_cmd(tuple(command), timeout)
        except ACQUISITION_ERRORS as exc:
            kind = "timeout" if isinstance(exc, TimeoutError) else "os error"
            return CommandResult(
                returncode=-1, stdout="", stderr="", error=f"{kind}: {exc}"
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
                            coverage=_DEVICE_COVERAGE,
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
        llama_candidate: str | None = None
        for cand in llama_candidates:
            found = self._which(cand)
            if found:
                llama_path = found
                llama_candidate = cand
                break

        if not llama_path:
            # AD-02: provenance names the operation that actually ran -- the
            # ``which`` search over the real candidate list -- and never a
            # ``--version`` invocation that was not executed. The version fact
            # is produced by the failed discovery, so it carries that source.
            search_source = f"which:{','.join(llama_candidates)}"
            observations.append(
                RuntimeObservation(
                    canonical_id="llama.cpp",
                    executable_path=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source=search_source,
                        detail="No llama.cpp binary found in PATH",
                    ),
                    raw_version=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source=search_source,
                        detail="Cannot probe version because binary is unavailable",
                    ),
                    detected_backends=(),
                    coverage=ObservationCoverage(entries=(
                        CoverageEntry(
                            ObservationFamily.RUNTIME_DISCOVERY,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_VERSION,
                            CoverageState.NOT_OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_BACKENDS,
                            CoverageState.NOT_OBSERVED,
                        ),
                    )),
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

            # Probe backends via help: positive syntactic evidence only.
            # Criterion (documented in detect_backend_evidence): a backend
            # counts ONLY as a flag token (--vulkan), a pure backend item list
            # (backends: cuda, cpu), or a build clause (built with sycl).
            # Prose, negations and incidental mentions never count. No inference.
            res_help = self._safe_run((llama_path, "--help"), 2.0)
            backends: list[ObservedValue] = []
            backends_outcome: ObservedValue | None = None
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
                if not backends:
                    # Probed, and the source reported no backend evidence:
                    # an explicit UNAVAILABLE outcome, never a silent empty tuple
                    # that a reader could mistake for "nothing exists".
                    backends_outcome = ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source=f"command:{llama_path} --help",
                        detail="--help reported no backend evidence",
                    )
            else:
                backends_outcome = ObservedValue(
                    state=ObservationState.ERROR,
                    source=f"command:{llama_path} --help",
                    detail=(
                        res_help.error
                        or f"Exited with returncode {res_help.returncode}"
                    ),
                )

            observations.append(
                RuntimeObservation(
                    canonical_id="llama.cpp",
                    executable_path=ObservedValue(
                        state=ObservationState.OBSERVED,
                        value=llama_path,
                        # AD-02: the candidate that ``which`` actually resolved.
                        source=f"which:{llama_candidate}",
                    ),
                    raw_version=ver_val,
                    detected_backends=tuple(backends),
                    backends_outcome=backends_outcome,
                    coverage=ObservationCoverage(entries=(
                        CoverageEntry(
                            ObservationFamily.RUNTIME_DISCOVERY,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_VERSION,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_BACKENDS,
                            CoverageState.OBSERVED,
                        ),
                    )),
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
                    # AD-02: no ``ollama --version`` was executed, so the version
                    # fact carries the discovery operation that produced it.
                    raw_version=ObservedValue(
                        state=ObservationState.UNAVAILABLE,
                        source="which:ollama",
                        detail="Cannot probe version because binary is unavailable",
                    ),
                    detected_backends=(),
                    coverage=ObservationCoverage(entries=(
                        CoverageEntry(
                            ObservationFamily.RUNTIME_DISCOVERY,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_VERSION,
                            CoverageState.NOT_OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_BACKENDS,
                            CoverageState.NOT_OBSERVED,
                        ),
                    )),
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
                    # Ollama backends are never probed in B9.11: the empty tuple
                    # means NOT_OBSERVED, not "no backends exist" (AD-04).
                    detected_backends=(),
                    coverage=ObservationCoverage(entries=(
                        CoverageEntry(
                            ObservationFamily.RUNTIME_DISCOVERY,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_VERSION,
                            CoverageState.OBSERVED,
                        ),
                        CoverageEntry(
                            ObservationFamily.RUNTIME_BACKENDS,
                            CoverageState.NOT_OBSERVED,
                        ),
                    )),
                )
            )

        return tuple(observations)

    def capture_context(self) -> EnvironmentContext:
        """Snapshot complete environment observations.

        All three environment families are attempted on every snapshot, so their
        coverage is reported explicitly (AD-04); per-runtime and per-device
        coverage travels with each of those observations.
        """
        ts = self._timestamp()
        platform_obs = self.observe_platform()
        hardware_obs = self.observe_hardware()
        runtimes_obs = self.observe_runtimes()
        return EnvironmentContext(
            timestamp=ts,
            platform=platform_obs,
            hardware=hardware_obs,
            runtimes=runtimes_obs,
            coverage=_CONTEXT_COVERAGE,
        )
