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

"""B9.10: application of EvaluationPolicy to the admission seam.

Adapts an ``EvaluateModelCompatibilityResult`` into an ``EvaluationAdmission``
by applying the operational policy (:func:`castlearq.evaluation_policy.decide`).
The decision produced by ``decide()`` prevails over the default verdict
projected by ``to_admission()`` when a valid evaluation exists.

Diagnostics of policy (``policy_id``, ``reasons``, ``evaluation``) remain
separate from ``EvaluationAdmission`` in :class:`PolicyDiagnostics`.  They are
never incorporated into the admission container nor into the HTTP rejection
body.

Purity: this module imports neither the CLI (``main``) nor the HTTP layer
(``api``) nor the execution use case (``execute_model``).  ``evaluation_policy``
and ``evaluate_compatibility`` do not import this module, so there are no
import cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .admission import EvaluationAdmission
from .evaluation_policy import (
    DecisionVerdict,
    EvaluationPolicyConfig,
    PolicyReason,
    decide,
)
from .evaluate_compatibility import (
    EvaluateModelCompatibilityResult,
    to_admission,
)
from .evaluation_pipeline import StrictEvaluation


@dataclass(frozen=True)
class PolicyDiagnostics:
    """Diagnostics of the policy decision, kept separate from admission.

    ``policy_id``, ``reasons`` and ``evaluation`` are not part of
    ``EvaluationAdmission`` and must never be incorporated into the admission
    container or into the HTTP rejection body.
    """

    policy_id: str
    reasons: tuple[PolicyReason, ...]
    evaluation: StrictEvaluation


@dataclass(frozen=True)
class PolicyAdmissionOutcome:
    """Result of applying the policy to one compatibility result."""

    admission: EvaluationAdmission
    policy_diagnostics: PolicyDiagnostics | None = None


def apply_policy_to_admission(
    result: EvaluateModelCompatibilityResult | None,
    policy: EvaluationPolicyConfig | None = None,
) -> PolicyAdmissionOutcome:
    """Apply the evaluation policy to one compatibility result.

    ``decide()`` is only invoked when the result carries a real evaluation:
    ``result is not None``, ``result.status == "evaluated"`` and
    ``result.evaluation is not None``. Blocked or unevaluated results keep
    their ``to_admission()`` projection (fail-closed) and are never
    rehabilitated by the policy.

    When a valid decision exists, its verdict prevails over the default
    verdict projected by ``to_admission()``:

    - ``ALLOW`` -> ``compatible_with_conditions`` when
      ``evaluation.result.conditions`` is non-empty, else ``compatible``.
    - ``DENY`` -> ``blocked``.
    - ``ESCALATE`` -> ``insufficient_evidence``.
    """
    # Fail-closed: no real evaluation -> no policy decision.
    if result is None:
        return PolicyAdmissionOutcome(
            admission=to_admission(None),
            policy_diagnostics=None,
        )

    status = getattr(result, "status", None)
    if status != "evaluated":
        return PolicyAdmissionOutcome(
            admission=to_admission(result),
            policy_diagnostics=None,
        )

    evaluation = getattr(result, "evaluation", None)
    if evaluation is None:
        return PolicyAdmissionOutcome(
            admission=to_admission(result),
            policy_diagnostics=None,
        )

    # Incomplete strict evaluation structure: if status="evaluated" but the
    # evaluation lacks required fields (projection or result) needed by decide(),
    # do NOT delegate permissively to to_admission() (which might produce
    # compatible). Mint a non-executable admission with insufficient_evidence
    # while preserving provenance.
    if not hasattr(evaluation, "projection") or not hasattr(evaluation, "result"):
        base = to_admission(result)
        return PolicyAdmissionOutcome(
            admission=replace(base, verdict="insufficient_evidence"),
            policy_diagnostics=None,
        )

    decision = decide(evaluation, policy)

    base = to_admission(result)  # provenance + status; verdict is default only

    if decision.verdict is DecisionVerdict.ALLOW:
        has_conditions = bool(decision.evaluation.result.conditions)
        final_verdict = (
            "compatible_with_conditions" if has_conditions else "compatible"
        )
    elif decision.verdict is DecisionVerdict.DENY:
        final_verdict = "blocked"
    else:  # DecisionVerdict.ESCALATE
        final_verdict = "insufficient_evidence"

    admission = replace(base, verdict=final_verdict)

    diagnostics = PolicyDiagnostics(
        policy_id=decision.policy_id,
        reasons=decision.reasons,
        evaluation=decision.evaluation,
    )
    return PolicyAdmissionOutcome(
        admission=admission,
        policy_diagnostics=diagnostics,
    )
