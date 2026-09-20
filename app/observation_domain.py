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

"""B9.11: observation domain contracts -- pure in-memory observed facts.

Establishes the immutable domain model for facts observed from the local
environment. This layer belongs strictly to OBSERVATION / CONTEXT ACQUISITION:

    OBSERVATION -> KNOWLEDGE -> EVALUATION -> DECISION -> EXECUTION

B9.11 contracts represent what a source observed, NOT what the system concludes:
- UNAVAILABLE != UNSUPPORTED
- ERROR != UNSUPPORTED
- UNKNOWN != FALSE

Ratified decisions enforced by this module:
- AD-01: a fact is ``OBSERVED`` only when positive verifiable evidence exists;
  absence of evidence is never turned into a negative fact.
- AD-04: coverage (whether a probe family was attempted at all) is a dimension
  separate from :class:`ObservationState`; there is no ``NOT_OBSERVED`` state.
- AD-05: :class:`ObservedValue` enforces its state/value/detail invariants in
  the constructor; ``value=None`` and an omitted value are the same domain fact.

Coverage takes precedence over state: when a family is ``NOT_OBSERVED`` every
fact of that family is unknown, whatever its ``ObservedValue`` state says.

No evaluation, no policy, no scoring, no recommendations, and no heuristics.
All dataclasses are frozen, all collections are tuples. Purity: zero I/O,
zero subprocess execution, and zero imports of evaluation/execution modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ObservationState(str, Enum):
    """Explicit epistemic state of an observed fact (Ratified Decision D-11.1).

    ``OBSERVED``: The value was successfully acquired from the source.
    ``UNAVAILABLE``: The required source/interface does not exist in the system.
    ``ERROR``: The source was attempted, but the acquisition failed (e.g. timeout, exit code).

    This enum has exactly three members: whether a family was probed at all is
    NOT represented here. It belongs to :class:`ObservationCoverage` (AD-04),
    so a collection that is empty because nothing was probed can never be read
    as "observed absence".
    """

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class CoverageState(str, Enum):
    """Whether a probe family was actually attempted (Ratified Decision AD-04).

    ``OBSERVED``: the probe attempted this family; the ``ObservedValue`` state of
    its facts then says whether evidence was returned.
    ``NOT_OBSERVED``: no probe attempted this family, so its facts carry no
    information at all.
    """

    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"


class ObservationFamily(str, Enum):
    """Probe families whose coverage is tracked independently of state."""

    PLATFORM = "platform"
    HARDWARE_MEMORY = "hardware_memory"
    HARDWARE_DEVICES = "hardware_devices"
    DEVICE_MEMORY = "device_memory"
    DEVICE_DRIVER = "device_driver"
    RUNTIME_DISCOVERY = "runtime_discovery"
    RUNTIME_VERSION = "runtime_version"
    RUNTIME_BACKENDS = "runtime_backends"


@dataclass(frozen=True)
class CoverageEntry:
    """Coverage of one probe family: the family and whether it was attempted."""

    family: ObservationFamily
    state: CoverageState

    def __post_init__(self) -> None:
        if not isinstance(self.family, ObservationFamily):
            raise ValueError("family must be an ObservationFamily enum")
        if not isinstance(self.state, CoverageState):
            raise ValueError("state must be a CoverageState enum")


@dataclass(frozen=True)
class ObservationCoverage:
    """Explicit coverage of the probe families of one observation (AD-04).

    A family absent from ``entries`` is ``NOT_OBSERVED``: a missing claim is
    never a claim of coverage, and an empty collection is never evidence of
    absence.
    """

    entries: tuple[CoverageEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        seen: set[ObservationFamily] = set()
        for entry in self.entries:
            if not isinstance(entry, CoverageEntry):
                raise ValueError("entries must contain CoverageEntry instances only")
            if entry.family in seen:
                raise ValueError(
                    f"duplicate coverage for family {entry.family.value!r}"
                )
            seen.add(entry.family)

    def state_for(self, family: ObservationFamily) -> CoverageState:
        """Coverage of ``family``; a family not listed is ``NOT_OBSERVED``."""
        if not isinstance(family, ObservationFamily):
            raise ValueError("family must be an ObservationFamily enum")
        for entry in self.entries:
            if entry.family is family:
                return entry.state
        return CoverageState.NOT_OBSERVED

    def is_observed(self, family: ObservationFamily) -> bool:
        """``True`` only when the family was explicitly reported as attempted."""
        return self.state_for(family) is CoverageState.OBSERVED


@dataclass(frozen=True)
class ObservedValue:
    """Atomic fact acquired from an environment source.

    ``state`` records whether acquisition succeeded, was unavailable, or errored.
    ``value`` holds the raw or structured value when state is OBSERVED (else None).
    ``source`` describes the observation origin (e.g. "file:/proc/meminfo").
    ``detail`` carries diagnostic or error information when state is not OBSERVED.
    """

    state: ObservationState
    value: Any = None
    source: str = ""
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ObservationState):
            raise ValueError("state must be an ObservationState enum")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        if self.detail is not None and (
            not isinstance(self.detail, str) or not self.detail.strip()
        ):
            raise ValueError("detail must be a non-empty string or None")
        # Ratified Decision AD-05: the epistemic state is part of the contract,
        # not a label. An omitted ``value`` and ``value=None`` are the same
        # domain fact (serialization decides how to render it).
        if self.state is ObservationState.OBSERVED:
            if self.value is None:
                raise ValueError("OBSERVED requires a non-None value")
        else:
            if self.value is not None:
                raise ValueError(
                    f"{self.state.value} must not carry a value "
                    f"(got {self.value!r})"
                )
            if self.detail is None:
                raise ValueError(
                    f"{self.state.value} requires a non-empty detail"
                )


@dataclass(frozen=True)
class PlatformObservation:
    """Observed facts about the operating platform.

    Contains only facts reported by platform probes; no compatibility inference.
    """

    os_family: ObservedValue
    os_release: ObservedValue
    architecture: ObservedValue
    distribution: ObservedValue

    def __post_init__(self) -> None:
        for name in ("os_family", "os_release", "architecture", "distribution"):
            val = getattr(self, name)
            if not isinstance(val, ObservedValue):
                raise ValueError(f"{name} must be an ObservedValue")


@dataclass(frozen=True)
class DeviceObservation:
    """Observed facts about a discrete hardware device (e.g. CPU or GPU).

    Vendor and device IDs preserve raw observed evidence (e.g. PCI hex strings).
    No semantic vendor fabrication or compatibility inference is performed.
    """

    device_type: str
    name: ObservedValue
    vendor_id: ObservedValue
    device_id: ObservedValue
    total_memory_bytes: ObservedValue
    driver_name: ObservedValue
    driver_version: ObservedValue
    coverage: ObservationCoverage = field(default_factory=ObservationCoverage)

    def __post_init__(self) -> None:
        if not isinstance(self.device_type, str) or not self.device_type.strip():
            raise ValueError("device_type must be a non-empty string")
        for name in (
            "name",
            "vendor_id",
            "device_id",
            "total_memory_bytes",
            "driver_name",
            "driver_version",
        ):
            val = getattr(self, name)
            if not isinstance(val, ObservedValue):
                raise ValueError(f"{name} must be an ObservedValue")
        if not isinstance(self.coverage, ObservationCoverage):
            raise ValueError("coverage must be an ObservationCoverage")


@dataclass(frozen=True)
class HardwareObservation:
    """Collection of observed hardware facts across memory and devices.

    ``devices`` holds only explicitly structured device evidence (display/GPU
    controllers parsed from ``lspci -nn``). System RAM (``memory_total_bytes``)
    is never duplicated as a synthetic CPU ``DeviceObservation``.

    ``acquisition_error`` is ``None`` on the success path (devices parsed, or
    zero display devices found). When ``lspci`` cannot be used it carries an
    explicit ``ObservedValue`` so callers can distinguish absence from failure:
    - ``UNAVAILABLE``: the ``lspci`` binary was not found (no device evidence).
    - ``ERROR``: ``lspci`` was attempted but failed (non-zero exit, timeout,
      or ``OSError`` while executing). ``devices`` stays empty in both cases.
    """

    memory_total_bytes: ObservedValue
    devices: tuple[DeviceObservation, ...] = ()
    acquisition_error: ObservedValue | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.memory_total_bytes, ObservedValue):
            raise ValueError("memory_total_bytes must be an ObservedValue")
        if not isinstance(self.devices, tuple):
            raise ValueError("devices must be a tuple")
        for d in self.devices:
            if not isinstance(d, DeviceObservation):
                raise ValueError("devices must contain DeviceObservation instances only")
        if self.acquisition_error is not None and not isinstance(
            self.acquisition_error, ObservedValue
        ):
            raise ValueError("acquisition_error must be an ObservedValue or None")


@dataclass(frozen=True)
class RuntimeObservation:
    """Observed facts regarding an installed runtime executable.

    ``canonical_id`` is the fixed identifier being probed (e.g. "llama.cpp", "ollama").
    No fuzzy alias resolution or compatibility scoring is performed.

    Facts and coverage are separate (AD-04):

    - ``executable_path`` carries the discovery outcome (``OBSERVED``,
      ``UNAVAILABLE`` when no candidate exists, ``ERROR`` when discovery failed).
    - ``raw_version`` carries the ``--version`` outcome, and is only probed when
      the executable was found (otherwise ``RUNTIME_VERSION`` is NOT_OBSERVED).
    - ``detected_backends`` holds only facts with positive verifiable evidence
      (AD-01); it is empty when nothing was probed *or* when the probe yielded no
      evidence, which ``coverage``/``backends_outcome`` disambiguate.
    - ``backends_outcome`` records a probed family that produced no positive
      evidence: ``UNAVAILABLE`` (probe ran, reported none) or ``ERROR`` (probe
      failed). It is ``None`` when the probe produced evidence, or when the
      family was never probed (see ``coverage``).
    """

    canonical_id: str
    executable_path: ObservedValue
    raw_version: ObservedValue
    detected_backends: tuple[ObservedValue, ...] = ()
    backends_outcome: ObservedValue | None = None
    coverage: ObservationCoverage = field(default_factory=ObservationCoverage)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_id, str) or not self.canonical_id.strip():
            raise ValueError("canonical_id must be a non-empty string")
        if not isinstance(self.executable_path, ObservedValue):
            raise ValueError("executable_path must be an ObservedValue")
        if not isinstance(self.raw_version, ObservedValue):
            raise ValueError("raw_version must be an ObservedValue")
        if not isinstance(self.detected_backends, tuple):
            raise ValueError("detected_backends must be a tuple")
        for b in self.detected_backends:
            if not isinstance(b, ObservedValue):
                raise ValueError(
                    "detected_backends must contain ObservedValue instances only"
                )
        if self.backends_outcome is not None and not isinstance(
            self.backends_outcome, ObservedValue
        ):
            raise ValueError("backends_outcome must be an ObservedValue or None")
        if not isinstance(self.coverage, ObservationCoverage):
            raise ValueError("coverage must be an ObservationCoverage")
        # AD-04: a probed family must state what happened. If the backend family
        # was attempted, either positive evidence exists or an outcome records
        # why it does not; an empty tuple alone is never a result.
        if (
            self.coverage.is_observed(ObservationFamily.RUNTIME_BACKENDS)
            and not self.detected_backends
            and self.backends_outcome is None
        ):
            raise ValueError(
                "a probed RUNTIME_BACKENDS family requires positive evidence "
                "or a backends_outcome fact"
            )


@dataclass(frozen=True)
class EnvironmentContext:
    """Immutable snapshot of the observed execution environment.

    ``timestamp`` is a declarative ISO-8601 string recording when the snapshot was taken.
    Contains no evaluation results, decisions, or runtime recommendations.

    ``coverage`` records which environment-level probe families were attempted
    (AD-04). Per-runtime families are recorded on each ``RuntimeObservation``
    and per-device families on each ``DeviceObservation``; coverage always takes
    precedence over the state of the facts it covers.
    """

    timestamp: str
    platform: PlatformObservation
    hardware: HardwareObservation
    runtimes: tuple[RuntimeObservation, ...] = ()
    coverage: ObservationCoverage = field(default_factory=ObservationCoverage)

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValueError("timestamp must be a non-empty string")
        if not isinstance(self.platform, PlatformObservation):
            raise ValueError("platform must be a PlatformObservation")
        if not isinstance(self.hardware, HardwareObservation):
            raise ValueError("hardware must be a HardwareObservation")
        if not isinstance(self.runtimes, tuple):
            raise ValueError("runtimes must be a tuple")
        for r in self.runtimes:
            if not isinstance(r, RuntimeObservation):
                raise ValueError("runtimes must contain RuntimeObservation instances only")
        if not isinstance(self.coverage, ObservationCoverage):
            raise ValueError("coverage must be an ObservationCoverage")
