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

"""Verification of a declarative remediation plan (Block B7).

Closes the remediation cycle without ever executing anything: given the
original :class:`~app.gpu_diagnosis.DiagnosisResult`, the declarative
:class:`~app.remediation.RemediationPlan` and a *fresh* diagnosis of the
current state, this module compares what was expected with what is now
observed and reports the outcome.

This module is pure: it never runs commands, never installs, never downloads,
never touches the filesystem or the network, and never executes the
``install_commands``/``verify_commands`` carried by recipes — those strings
remain data for the user. Observation of the fresh state is done upstream by
the existing read-only probes (``app.gpu_setup``) and interpreted by the
existing :func:`app.gpu_diagnosis.diagnose`; there is no second diagnosis
implementation here.

Semantics (per remediated component, never invented):

* expected ``MISSING_COMPONENT`` + observed ``READY``             → ``PASSED``
* expected ``MISSING_COMPONENT`` + observed ``MISSING_COMPONENT`` → ``FAILED``
* expected ``MISSING_COMPONENT`` + observed ``UNKNOWN``           → ``UNKNOWN``

``UNKNOWN`` is never converted into ``FAILED`` nor ``READY``: without real
evidence there is no verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gpu_diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    GpuComponent,
    component_check,
)
from .gpu_setup import FunctionalCheck, GpuSoftwareStatus
from .remediation import RemediationPlan, RemediationStatus


class VerificationStatus(str, Enum):
    """Outcome of verifying one remediated component."""

    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RemediationVerificationOutcome(str, Enum):
    """Global outcome of the remediation verification.

    ``VERIFIED`` requires every remediated component to have passed;
    ``NOT_VERIFIED`` means at least one failed; ``UNKNOWN`` means uncertainty
    without any failure; ``NOT_ATTEMPTED`` means there was nothing verifiable
    (no recipe-backed remediation, or the original diagnosis was READY).
    """

    NOT_ATTEMPTED = "not_attempted"
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VerificationResult:
    """One remediated component compared against the fresh diagnosis."""

    component: GpuComponent
    expected_status: DiagnosisStatus
    observed_status: DiagnosisStatus
    status: VerificationStatus
    recipe_ref: str | None = None
    evidence: FunctionalCheck | None = None
    message: str = ""


@dataclass(frozen=True)
class RemediationVerification:
    """Complete, deterministic result of verifying a remediation plan."""

    original_status: DiagnosisStatus
    plan_status: RemediationStatus
    followup_status: DiagnosisStatus
    per_component: tuple[VerificationResult, ...] = ()
    outcome: RemediationVerificationOutcome = (
        RemediationVerificationOutcome.NOT_ATTEMPTED)
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def _observed_status(check: FunctionalCheck | None) -> DiagnosisStatus:
    """Project one ``FunctionalCheck`` onto the diagnosis vocabulary."""
    if check is None or check.passed is None:
        return DiagnosisStatus.UNKNOWN
    if check.passed is False:
        return DiagnosisStatus.MISSING_COMPONENT
    return DiagnosisStatus.READY


def _verification_status(observed: DiagnosisStatus) -> VerificationStatus:
    """Expected ``MISSING_COMPONENT`` vs observed → verification status.

    ``UNKNOWN`` stays ``UNKNOWN``: it is never a failure and never a pass.
    """
    if observed is DiagnosisStatus.READY:
        return VerificationStatus.PASSED
    if observed is DiagnosisStatus.MISSING_COMPONENT:
        return VerificationStatus.FAILED
    return VerificationStatus.UNKNOWN


def _component_message(
    component: GpuComponent, status: VerificationStatus
) -> str:
    label = component.value
    if status is VerificationStatus.PASSED:
        return f"{label} is now present and functional."
    if status is VerificationStatus.FAILED:
        return f"{label} is still missing or non-functional."
    return f"{label} status could not be determined; no verdict."


def _aggregate(
    results: tuple[VerificationResult, ...],
) -> RemediationVerificationOutcome:
    """Deterministic aggregation over per-component results."""
    if not results:
        return RemediationVerificationOutcome.NOT_ATTEMPTED
    if any(result.status is VerificationStatus.FAILED for result in results):
        return RemediationVerificationOutcome.NOT_VERIFIED
    if any(result.status is VerificationStatus.UNKNOWN for result in results):
        return RemediationVerificationOutcome.UNKNOWN
    return RemediationVerificationOutcome.VERIFIED


def _context_changed(
    original: DiagnosisResult, followup: DiagnosisResult
) -> tuple[bool, tuple[str, ...]]:
    """Whether runtime/backend changed enough to make comparison unreliable."""
    warnings: list[str] = []
    if followup.runtime != original.runtime:
        warnings.append(
            f"runtime changed from {original.runtime!r} to"
            f" {followup.runtime!r}; the comparison is not reliable"
        )
    if followup.backend != original.backend:
        warnings.append(
            f"backend changed from {original.backend!r} to"
            f" {followup.backend!r}; the comparison is not reliable"
        )
    return bool(warnings), tuple(warnings)


def verify_remediation(
    original: DiagnosisResult,
    plan: RemediationPlan,
    followup: DiagnosisResult,
    followup_software: GpuSoftwareStatus | None,
) -> RemediationVerification:
    """Compare the original diagnosis with the fresh one (pure, no I/O).

    Only components backed by a local recipe in the plan are verified;
    components without a recipe are reported as notes — no expectation and no
    verification is invented for them. The comparison is anchored to the
    original (runtime, backend) context: if the fresh diagnosis was produced
    under a different context, the outcome degrades to ``UNKNOWN`` with a
    warning instead of producing an invalid comparison.
    """
    base_warnings = tuple(followup.warnings)
    if original.status is not DiagnosisStatus.MISSING_COMPONENT:
        if plan.status is RemediationStatus.NO_REMEDIATION:
            return RemediationVerification(
                original_status=original.status,
                plan_status=plan.status,
                followup_status=followup.status,
                outcome=RemediationVerificationOutcome.NOT_ATTEMPTED,
                warnings=base_warnings,
                notes=(
                    "Original diagnosis is READY; no remediation was needed"
                    " and there is nothing to verify.",
                ),
            )
        return RemediationVerification(
            original_status=original.status,
            plan_status=plan.status,
            followup_status=followup.status,
            outcome=RemediationVerificationOutcome.UNKNOWN,
            warnings=base_warnings,
            notes=(
                "Original diagnosis had no confirmed missing component;"
                " no expectation can be verified without one.",
            ),
        )

    context_changed, context_warnings = _context_changed(original, followup)
    warnings = base_warnings + context_warnings
    if context_changed:
        return RemediationVerification(
            original_status=original.status,
            plan_status=plan.status,
            followup_status=followup.status,
            outcome=RemediationVerificationOutcome.UNKNOWN,
            warnings=warnings,
            notes=(
                "Runtime/backend context changed since the original"
                " diagnosis; the comparison was skipped to avoid an invalid"
                " result.",
            ),
        )

    remediated = tuple(
        problem for problem in plan.problems if problem.recipe_ref is not None
    )
    unremediated = tuple(
        problem.component.value
        for problem in plan.problems
        if problem.recipe_ref is None
    )
    notes: list[str] = []
    if plan.status is RemediationStatus.NEEDS_RESEARCH:
        notes.append(
            "The plan requires external research; only components with a"
            " local recipe are verified."
        )
    if unremediated:
        notes.append(
            "No local recipe for: " + ", ".join(unremediated)
            + "; no verification is attempted for them."
        )
    if not remediated:
        notes.append(
            "No local remediation was available; there is nothing to verify."
        )
        return RemediationVerification(
            original_status=original.status,
            plan_status=plan.status,
            followup_status=followup.status,
            outcome=RemediationVerificationOutcome.NOT_ATTEMPTED,
            warnings=warnings,
            notes=tuple(notes),
        )

    results = tuple(
        _verify_component(followup_software, problem)
        for problem in remediated
    )
    return RemediationVerification(
        original_status=original.status,
        plan_status=plan.status,
        followup_status=followup.status,
        per_component=results,
        outcome=_aggregate(results),
        warnings=warnings,
        notes=tuple(notes),
    )


def _verify_component(
    followup_software: GpuSoftwareStatus | None,
    problem,
) -> VerificationResult:
    """Verify one recipe-backed remediated component against fresh evidence."""
    check = component_check(followup_software, problem.component)
    observed = _observed_status(check)
    status = _verification_status(observed)
    return VerificationResult(
        component=problem.component,
        expected_status=DiagnosisStatus.MISSING_COMPONENT,
        observed_status=observed,
        status=status,
        recipe_ref=problem.recipe_ref,
        evidence=check,
        message=_component_message(problem.component, status),
    )


def format_remediation_verification(
    verification: RemediationVerification,
    extra_warnings: tuple[str, ...] = (),
) -> str:
    """Render a verification result as human-readable text (never executed)."""
    lines = [
        "CastleArq — Remediation verification",
        "====================================",
        "",
        "Original diagnosis: "
        f"{verification.original_status.value.upper()}",
        "Remediation plan: "
        f"{verification.plan_status.value.upper()}",
        "Current diagnosis: "
        f"{verification.followup_status.value.upper()}",
        "",
        "Outcome: "
        f"{verification.outcome.value.upper()}",
        "",
        "Components",
    ]
    if verification.per_component:
        for result in verification.per_component:
            lines.append(
                f"  {result.component.value}: {result.status.value.upper()}"
                f" (expected {result.expected_status.value.upper()},"
                f" observed {result.observed_status.value.upper()})"
            )
            lines.append(f"    {result.message}")
            if result.evidence is not None:
                lines.append(
                    f"    Evidence: {result.evidence.detail}"
                    f" [{result.evidence.source}]"
                )
    else:
        lines.append("  No components were verified.")
    all_warnings = verification.warnings + tuple(extra_warnings)
    if all_warnings:
        lines.extend(("", "Warnings"))
        lines.extend(f"  - {warning}" for warning in all_warnings)
    if verification.notes:
        lines.extend(("", "Notes"))
        lines.extend(f"  - {note}" for note in verification.notes)
    lines.extend(
        (
            "",
            "Commands in the remediation plan are data for you to review and"
            " run manually; CastleArq never executed them and verified the"
            " current state with its own read-only probes.",
        )
    )
    return "\n".join(lines)
