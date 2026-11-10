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

"""Tests for ``castlearq.evaluation_admission`` (Milestone 2.6/2.7/2.8).

Covers the policy-to-admission adapter: mapping of ``DecisionVerdict`` to
admission verdicts, fail-closed behaviour for blocked/unevaluated results,
separation of policy diagnostics, provenance preservation and import purity.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError
from unittest import mock

from castlearq.admission import EvaluationAdmission, _STRICT_EVALUATION_TOKEN
from castlearq.compatibility_domain import CheckStatus, CompatibilityStatus
from castlearq.evaluation_admission import (
    PolicyAdmissionOutcome,
    PolicyDiagnostics,
    apply_policy_to_admission,
)
from castlearq.evaluation_policy import (
    DecisionVerdict,
    EvaluationPolicyConfig,
    PolicyReason,
    REASON_COMPATIBLE_PASS,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_WAIVER_IDENTITY_UNKNOWN,
    decide,
)
from castlearq.evaluate_compatibility import EvaluateModelCompatibilityResult
from castlearq.evaluation_pipeline import StrictEvaluation


def _make_result(
    status: str = "evaluated",
    evaluation: object = None,
    imported: bool = False,
    blocking_outcome: str | None = None,
) -> EvaluateModelCompatibilityResult:
    return EvaluateModelCompatibilityResult(
        model_id="m1",
        artifact=None,
        runtime=None,
        capability=None,
        evaluation=evaluation,
        integration=None,
        status=status,
        blocking_outcome=blocking_outcome,
        imported=imported,
    )


def _strict_eval(
    *,
    result_status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE,
    checks: tuple = (),
    conditions: tuple = (),
    conflicts: tuple = (),
) -> object:
    """Build a duck-typed StrictEvaluation with the fields ``decide()`` reads."""
    eval_obj = mock.Mock()
    eval_obj.projection = mock.Mock()
    eval_obj.projection.conflicts = conflicts
    eval_obj.result = mock.Mock()
    eval_obj.result.status = result_status
    eval_obj.result.checks = checks
    eval_obj.result.conditions = conditions
    return eval_obj


def _check(name: str, status: CheckStatus) -> mock.Mock:
    check = mock.Mock()
    check.name = name
    check.status = status
    check.expected = "val"
    check.observed = "val" if status is CheckStatus.PASSED else None
    check.evidence = ()
    return check


class ContractTests(unittest.TestCase):
    def test_outcome_is_frozen(self) -> None:
        outcome = PolicyAdmissionOutcome(
            admission=EvaluationAdmission("evaluated", "compatible"),
        )
        with self.assertRaises(FrozenInstanceError):
            outcome.admission = EvaluationAdmission("blocked", None)  # type: ignore[misc]

    def test_diagnostics_is_frozen(self) -> None:
        diag = PolicyDiagnostics(
            policy_id="strict-v1-zero-tolerance",
            reasons=(),
            evaluation=mock.Mock(),
        )
        with self.assertRaises(FrozenInstanceError):
            diag.policy_id = "other"  # type: ignore[misc]

    def test_no_cycles_of_imports(self) -> None:
        # Isolated subprocess checks:
        # 1. Importing evaluation_admission must not import CLI (main) or HTTP layer (api).
        # 2. Neither evaluation_policy nor evaluate_compatibility imports evaluation_admission.
        # Legitimate transitive dependencies such as castlearq.execute_model are permitted.
        def _run_isolated_check(code: str) -> None:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Isolated check failed (code {proc.returncode}):\n{proc.stdout}\n{proc.stderr}",
            )

        # Check 1: evaluation_admission does not import main or api
        _run_isolated_check(
            "import sys\n"
            "import castlearq.evaluation_admission\n"
            "assert 'castlearq.main' not in sys.modules, 'castlearq.main unexpectedly imported'\n"
            "assert 'castlearq.api' not in sys.modules, 'castlearq.api unexpectedly imported'\n"
        )

        # Check 2: evaluation_policy does not import evaluation_admission
        _run_isolated_check(
            "import sys\n"
            "import castlearq.evaluation_policy\n"
            "assert 'castlearq.evaluation_admission' not in sys.modules, "
            "'castlearq.evaluation_admission unexpectedly imported by evaluation_policy'\n"
        )

        # Check 3: evaluate_compatibility does not import evaluation_admission
        _run_isolated_check(
            "import sys\n"
            "import castlearq.evaluate_compatibility\n"
            "assert 'castlearq.evaluation_admission' not in sys.modules, "
            "'castlearq.evaluation_admission unexpectedly imported by evaluate_compatibility'\n"
        )

    def test_to_admission_remains_the_factory(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.COMPATIBLE,
                checks=(_check("artifact-model identity", CheckStatus.PASSED),),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertIsInstance(outcome.admission, EvaluationAdmission)
        self.assertIs(
            outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN
        )


class FailClosedTests(unittest.TestCase):
    def test_none_result_keeps_blocked(self) -> None:
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(None)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission, EvaluationAdmission("blocked", None))
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_result_without_status_attribute_fails_closed(self) -> None:
        # 1. Resultado sin atributo status
        result = mock.Mock(spec=[])  # no status attribute
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "blocked")
        self.assertIsNone(outcome.admission.verdict)
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_blocked_result_keeps_blocked(self) -> None:
        # 2. Resultado con status distinto de "evaluated"
        result = _make_result(status="blocked")
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "blocked")
        self.assertIsNone(outcome.admission.verdict)
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_evaluated_without_evaluation_keeps_blocked(self) -> None:
        # 3. Resultado evaluado sin atributo evaluation
        result = _make_result(status="evaluated", evaluation=None)
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertIsNone(outcome.admission.verdict)
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_evaluated_evaluation_without_projection_yields_insufficient_evidence(self) -> None:
        # 4. Evaluacion sin projection: nunca obtiene admision ejecutable
        eval_obj = mock.Mock(spec=["result"])
        eval_obj.result = mock.Mock(status=CompatibilityStatus.COMPATIBLE, conditions=(), checks=())
        result = _make_result(status="evaluated", evaluation=eval_obj)
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(outcome.admission.verdict, "insufficient_evidence")
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_evaluated_evaluation_without_result_yields_insufficient_evidence(self) -> None:
        # 5. Evaluacion sin result: nunca obtiene admision ejecutable
        eval_obj = mock.Mock(spec=["projection"])
        eval_obj.projection = mock.Mock(conflicts=())
        result = _make_result(status="evaluated", evaluation=eval_obj)
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(outcome.admission.verdict, "insufficient_evidence")
        self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
        self.assertIsNone(outcome.policy_diagnostics)

    def test_complete_evaluation_invokes_decide(self) -> None:
        # 6. Evaluacion completa que si pasa por decide()
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.COMPATIBLE,
                checks=(_check("artifact-model identity", CheckStatus.PASSED),),
            ),
        )
        with mock.patch("castlearq.evaluation_admission.decide", side_effect=decide) as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_called_once()
        self.assertEqual(outcome.admission.verdict, "compatible")
        self.assertIsNotNone(outcome.policy_diagnostics)

    def test_incomplete_evaluation_never_produces_executable_admission(self) -> None:
        # 7. Evaluacion incompleta que nunca obtiene admision ejecutable
        incomplete_evals = [
            mock.Mock(spec=[]),
            mock.Mock(spec=["projection"]),
            mock.Mock(spec=["result"]),
        ]
        for eval_obj in incomplete_evals:
            result = _make_result(status="evaluated", evaluation=eval_obj)
            outcome = apply_policy_to_admission(result)
            self.assertNotEqual(outcome.admission.verdict, "compatible")
            self.assertNotEqual(outcome.admission.verdict, "compatible_with_conditions")
            self.assertEqual(outcome.admission.verdict, "insufficient_evidence")
            self.assertIs(outcome.admission._admission_provenance, _STRICT_EVALUATION_TOKEN)
            self.assertIsNone(outcome.policy_diagnostics)

    def test_blocked_result_with_evaluation_never_decides(self) -> None:
        # Representable state: status blocked but evaluation present. Must not
        # call decide(); the block must be preserved.
        result = _make_result(
            status="blocked",
            evaluation=_strict_eval(result_status=CompatibilityStatus.COMPATIBLE),
        )
        with mock.patch("castlearq.evaluation_admission.decide") as decide_mock:
            outcome = apply_policy_to_admission(result)
        decide_mock.assert_not_called()
        self.assertEqual(outcome.admission.status, "blocked")
        self.assertIsNone(outcome.policy_diagnostics)


class MappingTests(unittest.TestCase):
    def test_allow_projects_compatible(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.COMPATIBLE,
                checks=(_check("artifact-model identity", CheckStatus.PASSED),),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(outcome.admission.verdict, "compatible")

    def test_allow_with_conditions_projects_compatible_with_conditions(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.COMPATIBLE,
                checks=(_check("artifact-model identity", CheckStatus.PASSED),),
                conditions=(
                    mock.Mock(name="memory headroom", description="..."),
                ),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(
            outcome.admission.verdict, "compatible_with_conditions"
        )

    def test_deny_projects_blocked(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.INCOMPATIBLE,
                checks=(_check("artifact format support", CheckStatus.FAILED),),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(outcome.admission.verdict, "blocked")

    def test_escalate_projects_insufficient_evidence(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
                checks=(_check("artifact-model identity", CheckStatus.UNKNOWN),),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertEqual(outcome.admission.status, "evaluated")
        self.assertEqual(
            outcome.admission.verdict, "insufficient_evidence"
        )

    def test_waiver_identity_is_not_a_technical_condition(self) -> None:
        # Waiver of unknown identity yields ALLOW but, without technical
        # conditions, the verdict is plain ``compatible``.
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
                checks=(_check("artifact-model identity", CheckStatus.UNKNOWN),),
            ),
        )
        policy = EvaluationPolicyConfig(allow_unknown_identity=True)
        outcome = apply_policy_to_admission(result, policy=policy)
        self.assertEqual(outcome.admission.verdict, "compatible")
        self.assertEqual(
            outcome.policy_diagnostics.reasons[0].code,
            REASON_WAIVER_IDENTITY_UNKNOWN,
        )
        # The evaluation itself remains UNKNOWN; it is not promoted.
        self.assertIs(
            outcome.policy_diagnostics.evaluation.result.status,
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
        )

    def test_waiver_with_technical_conditions_is_compatible_with_conditions(
        self,
    ) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
                checks=(_check("artifact-model identity", CheckStatus.UNKNOWN),),
                conditions=(mock.Mock(name="memory headroom", description="..."),),
            ),
        )
        policy = EvaluationPolicyConfig(allow_unknown_identity=True)
        outcome = apply_policy_to_admission(result, policy=policy)
        self.assertEqual(
            outcome.admission.verdict, "compatible_with_conditions"
        )
        self.assertEqual(
            outcome.policy_diagnostics.reasons[0].code,
            REASON_WAIVER_IDENTITY_UNKNOWN,
        )

    def test_decision_prevails_over_to_admission_default(self) -> None:
        # to_admission would project "compatible" (non-blocking UNKNOWNs), but
        # decide() yields ESCALATE; the policy verdict must prevail.
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
                checks=(
                    _check("runtime artifact support", CheckStatus.UNKNOWN),
                ),
            ),
            imported=False,
        )
        outcome = apply_policy_to_admission(result)
        self.assertEqual(outcome.admission.verdict, "insufficient_evidence")

    def test_diagnostics_match_decision(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(
                result_status=CompatibilityStatus.COMPATIBLE,
                checks=(_check("artifact-model identity", CheckStatus.PASSED),),
            ),
        )
        outcome = apply_policy_to_admission(result)
        self.assertIsNotNone(outcome.policy_diagnostics)
        self.assertEqual(
            outcome.policy_diagnostics.policy_id,
            "strict-v1-zero-tolerance",
        )
        self.assertEqual(
            outcome.policy_diagnostics.reasons[0].code, REASON_COMPATIBLE_PASS
        )
        # The evaluation is preserved verbatim (same object).
        self.assertIs(
            outcome.policy_diagnostics.evaluation, result.evaluation
        )


class DecisionUsageTests(unittest.TestCase):
    def test_decide_is_called_exactly_once_when_evaluation_exists(self) -> None:
        result = _make_result(
            status="evaluated",
            evaluation=_strict_eval(result_status=CompatibilityStatus.COMPATIBLE),
        )
        with mock.patch("castlearq.evaluation_admission.decide", side_effect=decide) as decide_mock:
            apply_policy_to_admission(result)
        decide_mock.assert_called_once()

    def test_decide_is_not_called_when_no_evaluation(self) -> None:
        with mock.patch("castlearq.evaluation_admission.decide", side_effect=decide) as decide_mock:
            apply_policy_to_admission(_make_result(status="evaluated", evaluation=None))
        decide_mock.assert_not_called()


if __name__ == "__main__":
    import sys  # noqa: E402 (needed by ContractTests.test_no_cycles_of_imports)

    unittest.main()
