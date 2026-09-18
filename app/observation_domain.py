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

No evaluation, no policy, no scoring, no recommendations, and no heuristics.
All dataclasses are frozen, all collections are tuples. Purity: zero I/O,
zero subprocess execution, and zero imports of evaluation/execution modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ObservationState(str, Enum):
    """Explicit epistemic state of an observed fact (Ratified Decision D-11.1).

    ``OBSERVED``: The value was successfully acquired from the source.
    ``UNAVAILABLE``: The required source/interface does not exist in the system.
    ``ERROR``: The source was attempted, but the acquisition failed (e.g. timeout, exit code).
    """

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


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
    """

    canonical_id: str
    executable_path: ObservedValue
    raw_version: ObservedValue
    detected_backends: tuple[ObservedValue, ...] = ()

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


@dataclass(frozen=True)
class EnvironmentContext:
    """Immutable snapshot of the observed execution environment.

    ``timestamp`` is a declarative ISO-8601 string recording when the snapshot was taken.
    Contains no evaluation results, decisions, or runtime recommendations.
    """

    timestamp: str
    platform: PlatformObservation
    hardware: HardwareObservation
    runtimes: tuple[RuntimeObservation, ...] = ()

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
