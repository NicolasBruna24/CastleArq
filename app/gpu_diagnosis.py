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
support; no per-GPU attribution is attempted. When a component is
explicitly missing, :func:`recommend` resolves the declarative recipes in
:mod:`app.gpu_recipes` (by id) for the recorded
``runtime``/``backend``/``platform``; nothing is installed or executed here.
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
    """Deterministic outcome of :func:`diagnose`.

    ``runtime``/``backend`` hold the canonicalised keys and ``platform`` the
    case/space-normalised platform. They preserve the context needed by
    :func:`recommend` to resolve declarative recipes without re-deriving it.
    """

    status: DiagnosisStatus
    missing_components: tuple[MissingComponent, ...] = ()
    warnings: tuple[str, ...] = ()
    runtime: str = ""
    backend: str = ""
    platform: str = ""


@dataclass(frozen=True)
class Recommendation:
    """Conceptual action for a diagnosis: declarative recipe references.

    ``recipe_ref`` is the primary recipe id (for convenience) while
    ``recipe_refs`` lists every resolved recipe id in ``missing_components``
    order, so multiple missing components never lose information. No install
    content is provided and nothing is ever executed here.
    """

    status: DiagnosisStatus
    missing_components: tuple[MissingComponent, ...] = ()
    recipe_ref: str | None = None
    verify_commands: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recipe_refs: tuple[str, ...] = ()


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
    platform: str = "",
) -> DiagnosisResult:
    """Interpret detected facts without any side effect.

    ``software`` carries the already-probed ``True``/``False``/``None``
    facts; ``None`` as a whole simply means every capability is unknown.
    ``gpu`` is accepted as context only (H1: Vulkan evidence stays
    system-wide; no per-GPU attribution is attempted). ``platform`` is
    recorded context used later by :func:`recommend` to resolve a recipe;
    the default ``""`` means the platform is unknown, so no recipe is ever
    assumed (no operating system is baked in here). ``False`` evidence
    yields ``MISSING_COMPONENT``; ``None`` (unknown) never does — it yields
    ``UNKNOWN`` unless a ``False`` is also present.
    """
    _ = gpu
    runtime_key, backend_key = _canonical(runtime, backend)
    platform_key = platform.strip().lower()
    requirements = _REQUIREMENTS.get((runtime_key, backend_key))
    if requirements is None:
        return DiagnosisResult(
            status=DiagnosisStatus.UNKNOWN,
            warnings=(f"no requirement model for {runtime} + {backend}",),
            runtime=runtime_key,
            backend=backend_key,
            platform=platform_key,
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
            status=DiagnosisStatus.MISSING_COMPONENT,
            missing_components=tuple(missing),
            warnings=warnings,
            runtime=runtime_key,
            backend=backend_key,
            platform=platform_key,
        )
    if unknown:
        return DiagnosisResult(
            status=DiagnosisStatus.UNKNOWN,
            warnings=warnings,
            runtime=runtime_key,
            backend=backend_key,
            platform=platform_key,
        )
    return DiagnosisResult(
        status=DiagnosisStatus.READY,
        runtime=runtime_key,
        backend=backend_key,
        platform=platform_key,
    )


def recommend(diagnosis: DiagnosisResult) -> Recommendation:
    """Map a diagnosis to declarative recipes (never installs anything).

    Only ``MISSING_COMPONENT`` resolutions receive recipes. Every missing
    component is looked up independently so multiple absences keep their own
    recipe; ``READY`` and ``UNKNOWN`` never receive a recipe.
    """
    if diagnosis.status is not DiagnosisStatus.MISSING_COMPONENT:
        return Recommendation(
            status=diagnosis.status,
            missing_components=diagnosis.missing_components,
            recipe_ref=None,
            verify_commands=(),
            warnings=diagnosis.warnings,
            recipe_refs=(),
        )
    from .gpu_recipes import find_recipe
    refs: list[str] = []
    verify: list[str] = []
    for missing in diagnosis.missing_components:
        recipe = find_recipe(
            diagnosis.runtime,
            diagnosis.backend,
            missing.component,
            diagnosis.platform,
        )
        if recipe is None:
            continue
        refs.append(recipe.id)
        verify.extend(recipe.verify_commands)
    return Recommendation(
        status=diagnosis.status,
        missing_components=diagnosis.missing_components,
        recipe_ref=refs[0] if refs else None,
        verify_commands=tuple(verify),
        warnings=diagnosis.warnings,
        recipe_refs=tuple(refs),
    )
