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

"""Declarative GPU remediation planning (Block B5).

Turns a :class:`~app.gpu_diagnosis.DiagnosisResult` plus the declarative
recipe catalog into an ordered, non-executable :class:`RemediationPlan`.

This module performs no I/O: it never runs commands, never installs, never
downloads, never modifies the system and never performs web research.
Commands are data — they are carried in the plan, never executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gpu_diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    GpuComponent,
    MissingComponent,
)
from .gpu_recipes import GpuRecipe, find_recipe


class RemediationStatus(str, Enum):
    """Availability of a local, declarative remediation plan.

    ``READY`` means every missing component has a recipe with commands;
    ``PARTIAL`` means local recipes exist but lack commands; ``NEEDS_RESEARCH``
    means at least one missing component has no local recipe; ``NO_REMEDIATION``
    means the diagnosis is READY (nothing to do); and
    ``NO_ACTION_REQUIRED_YET`` means the diagnosis is UNKNOWN, so there is no
    confirmed problem and no repair is proposed until evidence confirms one.
    """

    READY = "ready"
    PARTIAL = "partial"
    NEEDS_RESEARCH = "needs_research"
    NO_REMEDIATION = "no_remediation"
    NO_ACTION_REQUIRED_YET = "no_action_required_yet"


class RemediationActionKind(str, Enum):
    """The kind of one declarative remediation step."""

    RESOLVE_COMPONENT = "resolve_component"
    VERIFY_COMPONENT = "verify_component"
    REDIAGNOSE = "rediagnose"


@dataclass(frozen=True)
class RemediationProblem:
    """One detected problem and the local remediation available for it."""

    component: GpuComponent
    required_by: str
    recipe_ref: str | None = None
    has_install_commands: bool = False
    has_verify_commands: bool = False


@dataclass(frozen=True)
class RemediationAction:
    """One ordered, declarative step; commands are data, never executed."""

    order: int
    kind: RemediationActionKind
    description: str
    component: GpuComponent | None = None
    recipe_ref: str | None = None
    commands: tuple[str, ...] = ()


COMPONENT_LABELS: dict[GpuComponent, str] = {
    GpuComponent.KERNEL_DRIVER: "Kernel driver",
    GpuComponent.DRM_DEVICE: "DRM render device",
    GpuComponent.VULKAN_FUNCTIONAL: "Vulkan runtime",
    GpuComponent.OPENCL: "OpenCL runtime",
    GpuComponent.LEVEL_ZERO: "Level Zero runtime",
}


@dataclass(frozen=True)
class RemediationPlan:
    """An ordered, declarative and strictly non-executable remediation plan."""

    status: RemediationStatus
    objective: str
    problems: tuple[RemediationProblem, ...] = ()
    actions: tuple[RemediationAction, ...] = ()
    install_commands: tuple[str, ...] = ()
    verify_commands: tuple[str, ...] = ()
    recipe_refs: tuple[str, ...] = ()
    requires_authorization: bool = False
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def _objective(diagnosis: DiagnosisResult) -> str:
    runtime = diagnosis.runtime or "unknown runtime"
    backend = diagnosis.backend or "unknown backend"
    platform = diagnosis.platform or "unknown platform"
    return f"Resolve GPU software required by {runtime} + {backend} on {platform}"


def _component_label(component: GpuComponent) -> str:
    return COMPONENT_LABELS.get(component, component.value)


def _no_remediation_plan(
    diagnosis: DiagnosisResult, objective: str
) -> RemediationPlan:
    """Represent a diagnosis that has no confirmed problem to repair.

    ``READY`` is final (``NO_REMEDIATION``); ``UNKNOWN`` keeps its uncertainty
    and is reported as ``NO_ACTION_REQUIRED_YET`` — no repair is proposed while
    evidence is missing.
    """
    if diagnosis.status is DiagnosisStatus.READY:
        status = RemediationStatus.NO_REMEDIATION
        note = "Diagnosis is READY; no remediation is required."
    else:
        status = RemediationStatus.NO_ACTION_REQUIRED_YET
        note = "Diagnosis is UNKNOWN; no confirmed problem to remediate yet."
    return RemediationPlan(
        status=status,
        objective=objective,
        warnings=diagnosis.warnings,
        notes=(note,),
    )


def _problems_and_recipes(
    diagnosis: DiagnosisResult,
) -> tuple[
    tuple[RemediationProblem, ...],
    tuple[tuple[MissingComponent, GpuRecipe], ...],
]:
    """Resolve each missing component against the local recipe catalog."""
    problems: list[RemediationProblem] = []
    planned: list[tuple[MissingComponent, GpuRecipe]] = []
    for missing in diagnosis.missing_components:
        recipe = find_recipe(
            diagnosis.runtime,
            diagnosis.backend,
            missing.component,
            diagnosis.platform,
        )
        problems.append(
            RemediationProblem(
                component=missing.component,
                required_by=missing.required_by,
                recipe_ref=recipe.id if recipe is not None else None,
                has_install_commands=bool(recipe and recipe.install_commands),
                has_verify_commands=bool(recipe and recipe.verify_commands),
            )
        )
        if recipe is not None:
            planned.append((missing, recipe))
    return tuple(problems), tuple(planned)


def build_remediation_plan(diagnosis: DiagnosisResult) -> RemediationPlan:
    """Build an ordered, declarative, non-executable plan from a diagnosis.

    Pure: it only reads the diagnosis and the local recipe catalog. It never
    runs commands, installs, downloads, modifies the system or performs web
    research. Missing components are grouped into a single plan; the order is
    deterministic (all resolve steps, then all verify steps, then rediagnosis).
    """
    objective = _objective(diagnosis)
    if diagnosis.status is not DiagnosisStatus.MISSING_COMPONENT:
        return _no_remediation_plan(diagnosis, objective)

    problems, planned = _problems_and_recipes(diagnosis)
    if not planned:
        return RemediationPlan(
            status=RemediationStatus.NEEDS_RESEARCH,
            objective=objective,
            problems=problems,
            warnings=diagnosis.warnings,
            notes=(
                "No local remediation available; external research is required.",
            ),
        )

    missing_recipe = any(problem.recipe_ref is None for problem in problems)
    lacks_commands = not all(recipe.install_commands for _, recipe in planned)
    if missing_recipe:
        status = RemediationStatus.NEEDS_RESEARCH
    elif lacks_commands:
        status = RemediationStatus.PARTIAL
    else:
        status = RemediationStatus.READY

    actions: list[RemediationAction] = []
    recipe_refs: list[str] = []
    install_commands: list[str] = []
    verify_commands: list[str] = []
    order = 1
    for missing, recipe in planned:
        recipe_refs.append(recipe.id)
        install_commands.extend(recipe.install_commands)
        actions.append(
            RemediationAction(
                order=order,
                kind=RemediationActionKind.RESOLVE_COMPONENT,
                description=f"Resolve {_component_label(missing.component)}",
                component=missing.component,
                recipe_ref=recipe.id,
                commands=recipe.install_commands,
            )
        )
        order += 1
    for missing, recipe in planned:
        verify_commands.extend(recipe.verify_commands)
        actions.append(
            RemediationAction(
                order=order,
                kind=RemediationActionKind.VERIFY_COMPONENT,
                description=f"Verify {_component_label(missing.component)}",
                component=missing.component,
                recipe_ref=recipe.id,
                commands=recipe.verify_commands,
            )
        )
        order += 1
    actions.append(
        RemediationAction(
            order=order,
            kind=RemediationActionKind.REDIAGNOSE,
            description="Re-run GPU diagnosis",
        )
    )

    notes: list[str] = []
    if missing_recipe:
        notes.append(
            "Some missing components have no local recipe; external research"
            " is required."
        )
    if lacks_commands:
        notes.append(
            "Some local recipes have no install commands yet; they are"
            " conceptual remediations only."
        )
    return RemediationPlan(
        status=status,
        objective=objective,
        problems=problems,
        actions=tuple(actions),
        install_commands=tuple(install_commands),
        verify_commands=tuple(verify_commands),
        recipe_refs=tuple(recipe_refs),
        requires_authorization=True,
        warnings=diagnosis.warnings,
        notes=tuple(notes),
    )
