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

"""Pure diagnosis + recommendation over GPU software facts (Block B2).

Detection lives in :mod:`app.gpu_setup` (facts: ``True``/``False``/``None``).
This module only *interprets* already-built, in-memory objects: it never
probes hardware, never runs commands, never touches the filesystem or the
network, and never installs anything. ``vulkan_functional`` is interpreted
as system-wide evidence — the system/runtime reports functional Vulkan
support; no per-GPU attribution is attempted. ``recipe_ref`` stays
``None`` until Block B3 defines installation recipes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gpu_setup import FunctionalCheck, GpuSoftwareStatus
from .hardware import GPUInfo


class GpuComponent(str, Enum):
    """Concrete software capability that can be required."""

    KERNEL_DRIVER = "kernel_driver"
    DRM_DEVICE = "drm_device"
    VULKAN_FUNCTIONAL = "vulkan_functional"
    OPENCL = "opencl"
    LEVEL_ZERO = "level_zero"


class DiagnosisStatus(str, Enum):
    """Explicit diagnosis outcome (no lifecycle states beyond these)."""

    READY = "ready"
    MISSING_COMPONENT = "missing_component"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SoftwareRequirement:
    """One capability required to run a (runtime, backend) pair."""

    component: GpuComponent
    required_for: str
    why: str


@dataclass(frozen=True)
class MissingComponent:
    """A requirement with explicit evidence of absence (``False`` only)."""

    component: GpuComponent
    evidence: FunctionalCheck
    required_by: str

    def __post_init__(self) -> None:
        if self.evidence.passed is not False:
            raise ValueError(
                "MissingComponent requires explicit absence evidence"
                " (evidence.passed is False); unknown evidence (None) must"
                " never become a missing component")


@dataclass(frozen=True)
class DiagnosisResult:
    """Deterministic outcome of :func:`diagnose`."""

    status: DiagnosisStatus
    missing_components: tuple[MissingComponent, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    """Conceptual action for a diagnosis; no install content yet (Block B3)."""

    status: DiagnosisStatus
    missing_components: tuple[MissingComponent, ...] = ()
    recipe_ref: str | None = None
    verify_commands: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


# Data-driven requirement matrix keyed by canonical (runtime, backend).
# Only llama.cpp pairs are modelled; anything else resolves to UNKNOWN
# without inventing requirements or missing components.
_REQUIREMENTS: dict[tuple[str, str], tuple[SoftwareRequirement, ...]] = {
    ("llama.cpp", "vulkan"): (
        SoftwareRequirement(
            GpuComponent.KERNEL_DRIVER,
            "llama.cpp + Vulkan",
            "a kernel GPU driver must bind the device",
        ),
        SoftwareRequirement(
            GpuComponent.DRM_DEVICE,
            "llama.cpp + Vulkan",
            "a DRM/render device must be visible to userspace",
        ),
        SoftwareRequirement(
            GpuComponent.VULKAN_FUNCTIONAL,
            "llama.cpp + Vulkan",
            "the system/runtime reports functional Vulkan evidence",
        ),
    ),
    ("llama.cpp", "cpu"): (),
}

# Requirement component -> capability check on GpuSoftwareStatus.
_CAPABILITY: dict[GpuComponent, str] = {
    GpuComponent.KERNEL_DRIVER: "kernel_driver",
    GpuComponent.DRM_DEVICE: "drm_device",
    GpuComponent.VULKAN_FUNCTIONAL: "vulkan",
    GpuComponent.OPENCL: "opencl",
    GpuComponent.LEVEL_ZERO: "level_zero",
}


def _canonical(runtime: str, backend: str) -> tuple[str, str]:
    """Normalize a (runtime, backend) pair for data-driven lookups."""
    return runtime.strip().lower(), backend.strip().lower()


def requirements_for(runtime: str, backend: str) -> tuple[SoftwareRequirement, ...] | None:
    """Return the modelled requirements, or ``None`` when unmodelled."""
    return _REQUIREMENTS.get(_canonical(runtime, backend))


def diagnose(
    software: GpuSoftwareStatus | None,
    runtime: str,
    backend: str,
    gpu: GPUInfo | None = None,
) -> DiagnosisResult:
    """Interpret detected facts without any side effect.

    ``software`` carries the already-probed ``True``/``False``/``None``
    facts; ``None`` as a whole simply means every capability is unknown.
    ``gpu`` is accepted as context only (H1: Vulkan evidence stays
    system-wide; no per-GPU attribution is attempted). ``False`` evidence
    yields ``MISSING_COMPONENT``; ``None`` (unknown) never does — it yields
    ``UNKNOWN`` unless a ``False`` is also present.
    """
    _ = gpu
    requirements = requirements_for(runtime, backend)
    if requirements is None:
        return DiagnosisResult(
            DiagnosisStatus.UNKNOWN,
            (),
            (f"no requirement model for {runtime} + {backend}",),
        )
    missing: list[MissingComponent] = []
    unknown: list[str] = []
    for requirement in requirements:
        check = (
            None
            if software is None
            else getattr(software, _CAPABILITY[requirement.component])
        )
        if check is not None and check.passed is False:
            missing.append(
                MissingComponent(
                    requirement.component, check, requirement.required_for))
        elif check is None or check.passed is None:
            unknown.append(requirement.component.value)
    warnings = tuple(f"{name} status unknown" for name in unknown)
    if missing:
        return DiagnosisResult(
            DiagnosisStatus.MISSING_COMPONENT, tuple(missing), warnings)
    if unknown:
        return DiagnosisResult(DiagnosisStatus.UNKNOWN, (), warnings)
    return DiagnosisResult(DiagnosisStatus.READY, (), ())


def recommend(diagnosis: DiagnosisResult) -> Recommendation:
    """Map a diagnosis to its conceptual action (recipes arrive in B3)."""
    return Recommendation(
        status=diagnosis.status,
        missing_components=diagnosis.missing_components,
        recipe_ref=None,
        verify_commands=(),
        warnings=diagnosis.warnings,
    )
