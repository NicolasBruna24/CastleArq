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

"""B9.10: evaluation policy boundary -- pure operational decisions.

Establishes the boundary between factual compatibility evaluation
(:class:`~app.evaluation_pipeline.StrictEvaluation`) and operational
authorization (:class:`EvaluationDecision`).

The core architectural boundary is:
    Evaluation = "What does the available evidence say?"
    Policy     = "What operational decision should be made from that evidence?"

Ratified decisions:
- D-10.1: Default mapping:
    COMPATIBLE            -> ALLOW
    INCOMPATIBLE          -> DENY
    INSUFFICIENT_EVIDENCE -> ESCALATE
    CONFLICT              -> DENY
- D-10.2: Catalog models lack cryptographic hashes, causing
    "artifact-model identity" to evaluate to UNKNOWN. A policy configuration
    may explicitly declare ``allow_unknown_identity=True`` (waiver). The
    underlying evaluation check is NEVER modified (remains UNKNOWN); only the
    policy verdict yields ALLOW, recorded with reason ``WAIVER_IDENTITY_UNKNOWN``.
- D-10.3: Frozen configuration (:class:`EvaluationPolicyConfig`) + pure decision
    function (:func:`decide`), returning frozen :class:`EvaluationDecision`.
- D-10.4: ESCALATE is a terminal policy verdict. It performs no I/O, no retry,
    no user prompt, no override, and no execution.

Precedence:
    CONFLICT (DENY)
        > FAILED / INCOMPATIBLE (DENY)
        > UNKNOWN / INSUFFICIENT_EVIDENCE (ESCALATE, or ALLOW if explicitly waived)
        > COMPATIBLE (ALLOW)

Purity: zero I/O, zero subprocess, zero legacy imports, no mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .compatibility_domain import CheckStatus, CompatibilityStatus

if TYPE_CHECKING:  # pragma: no cover
    from .evaluation_pipeline import StrictEvaluation


class DecisionVerdict(str, Enum):
    """Operational verdict emitted by an evaluation policy."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


# Stable policy reason codes
REASON_COMPATIBLE_PASS = "COMPATIBLE_PASS"
REASON_UNSUPPORTED_CHECK = "UNSUPPORTED_CHECK"
REASON_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
REASON_BLOCKED_BY_CONFLICT = "BLOCKED_BY_CONFLICT"
REASON_WAIVER_IDENTITY_UNKNOWN = "WAIVER_IDENTITY_UNKNOWN"

#: Default name of the strict identity check in B9.3
IDENTITY_CHECK_NAME = "artifact-model identity"


@dataclass(frozen=True)
class PolicyReason:
    """Factual, immutable explanation for a policy verdict.

    Contains only declarative codes and messages; never runner instances,
    execution commands, or file system paths.
    """

    code: str
    message: str
    check_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("code must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        if self.check_name is not None and (
            not isinstance(self.check_name, str) or not self.check_name.strip()
        ):
            raise ValueError("check_name must be a non-empty string or None")


@dataclass(frozen=True)
class EvaluationPolicyConfig:
    """Frozen policy configuration governing the operational decision.

    Explicitly represents any policy toggles such as specific UNKNOWN waivers.
    """

    policy_id: str = "strict-v1-zero-tolerance"
    allow_unknown_identity: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id must be a non-empty string")
        if not isinstance(self.allow_unknown_identity, bool):
            raise ValueError("allow_unknown_identity must be a bool")


@dataclass(frozen=True)
class EvaluationDecision:
    """Frozen operational decision derived strictly from a StrictEvaluation.

    Preserves the complete upstream ``evaluation`` verbatim with full
    traceability. Contains no execution targets, no legacy score, and no
    heuristic recommendations.
    """

    verdict: DecisionVerdict
    evaluation: "StrictEvaluation"
    reasons: tuple[PolicyReason, ...]
    policy_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, DecisionVerdict):
            raise ValueError("verdict must be a DecisionVerdict")
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id must be a non-empty string")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be a tuple")
        for reason in self.reasons:
            if not isinstance(reason, PolicyReason):
                raise ValueError("reasons must contain PolicyReason instances only")


def decide(
    evaluation: "StrictEvaluation",
    policy: EvaluationPolicyConfig | None = None,
) -> EvaluationDecision:
    """Apply an operational policy to a StrictEvaluation deterministically.

    Pure: does not mutate ``evaluation``, performs no I/O, and enforces
    deterministic precedence:
        1. CONFLICT in knowledge projection -> DENY (BLOCKED_BY_CONFLICT)
        2. Any check FAILED -> DENY (UNSUPPORTED_CHECK)
        3. Checks UNKNOWN:
           - If allow_unknown_identity is True AND the ONLY unknown check is
             'artifact-model identity', emit ALLOW with WAIVER_IDENTITY_UNKNOWN.
           - Otherwise, emit ESCALATE with INSUFFICIENT_EVIDENCE.
        4. All checks PASSED -> ALLOW (COMPATIBLE_PASS)
    """
    if policy is None:
        policy = EvaluationPolicyConfig()

    reasons: list[PolicyReason] = []

    # 1. CONFLICT check (highest precedence)
    if evaluation.projection.conflicts:
        reasons.append(
            PolicyReason(
                code=REASON_BLOCKED_BY_CONFLICT,
                message=(
                    f"Operational authorization denied: knowledge projection carries "
                    f"{len(evaluation.projection.conflicts)} conflicting assertion(s)."
                ),
            )
        )
        return EvaluationDecision(
            verdict=DecisionVerdict.DENY,
            evaluation=evaluation,
            reasons=tuple(reasons),
            policy_id=policy.policy_id,
        )

    # Inspect individual checks from CompatibilityResult
    failed_checks = tuple(
        c for c in evaluation.result.checks if c.status is CheckStatus.FAILED
    )
    unknown_checks = tuple(
        c for c in evaluation.result.checks if c.status is CheckStatus.UNKNOWN
    )

    # 2. FAILED checks -> DENY
    if failed_checks:
        for check in failed_checks:
            reasons.append(
                PolicyReason(
                    code=REASON_UNSUPPORTED_CHECK,
                    message=f"Check failed: {check.name} (observed: {check.observed!r}, expected: {check.expected!r})",
                    check_name=check.name,
                )
            )
        return EvaluationDecision(
            verdict=DecisionVerdict.DENY,
            evaluation=evaluation,
            reasons=tuple(reasons),
            policy_id=policy.policy_id,
        )

    # 3. UNKNOWN checks -> ESCALATE (or ALLOW if explicitly waived)
    if unknown_checks:
        # Check if ONLY the identity check is unknown and policy permits waiver
        if (
            policy.allow_unknown_identity
            and len(unknown_checks) == 1
            and unknown_checks[0].name == IDENTITY_CHECK_NAME
        ):
            reasons.append(
                PolicyReason(
                    code=REASON_WAIVER_IDENTITY_UNKNOWN,
                    message=(
                        f"Permitted execution under policy waiver for check "
                        f"'{IDENTITY_CHECK_NAME}' (observed: None). Evaluator status "
                        f"remains UNKNOWN."
                    ),
                    check_name=IDENTITY_CHECK_NAME,
                )
            )
            return EvaluationDecision(
                verdict=DecisionVerdict.ALLOW,
                evaluation=evaluation,
                reasons=tuple(reasons),
                policy_id=policy.policy_id,
            )

        # Otherwise, insufficient evidence escalates
        for check in unknown_checks:
            reasons.append(
                PolicyReason(
                    code=REASON_INSUFFICIENT_EVIDENCE,
                    message=f"Check has insufficient evidence (unknown): {check.name}",
                    check_name=check.name,
                )
            )
        return EvaluationDecision(
            verdict=DecisionVerdict.ESCALATE,
            evaluation=evaluation,
            reasons=tuple(reasons),
            policy_id=policy.policy_id,
        )

    # 4. All checks PASSED and COMPATIBLE -> ALLOW
    reasons.append(
        PolicyReason(
            code=REASON_COMPATIBLE_PASS,
            message="All compatibility checks passed with sufficient evidence.",
        )
    )
    return EvaluationDecision(
        verdict=DecisionVerdict.ALLOW,
        evaluation=evaluation,
        reasons=tuple(reasons),
        policy_id=policy.policy_id,
    )
