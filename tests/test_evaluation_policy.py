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

"""Tests for B9.10: evaluation policy boundary, contracts, and purity."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from app.compatibility_domain import (
    CheckStatus,
    CompatibilityCheck,
    CompatibilityResult,
    CompatibilityStatus,
)
from app.compatibility_evaluator import EvaluationContext, RuntimeKnowledge
from app.compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeConflict,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)
from app.evaluation_pipeline import StrictEvaluation
from app.evaluation_policy import (
    IDENTITY_CHECK_NAME,
    REASON_BLOCKED_BY_CONFLICT,
    REASON_COMPATIBLE_PASS,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_UNSUPPORTED_CHECK,
    REASON_WAIVER_IDENTITY_UNKNOWN,
    DecisionVerdict,
    EvaluationDecision,
    EvaluationPolicyConfig,
    PolicyReason,
    decide,
)
from app.knowledge_bridge import KnowledgeProjection
from app.model_domain import (
    Model,
    ModelArchitecture,
    ModelArtifact,
    ModelCapabilities,
    ModelIdentity,
    ModelPrecision,
    ModelQuantization,
    QuantizationStatus,
)


def _dummy_evaluation(
    status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE,
    checks: tuple[CompatibilityCheck, ...] = (),
    conflicts: tuple[KnowledgeConflict, ...] = (),
) -> StrictEvaluation:
    model = Model(
        identity=ModelIdentity(name="Demo", model_id="demo"),
        architecture=ModelArchitecture(architecture="Transformer"),
        capabilities=ModelCapabilities(),
    )
    artifact = ModelArtifact(
        identifier="demo",
        format="gguf",
        precision=ModelPrecision(),
        quantization=ModelQuantization(QuantizationStatus.UNKNOWN),
    )
    context = EvaluationContext(runtime=RuntimeKnowledge(name="llama.cpp"))
    projection = KnowledgeProjection(
        runtime=KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp"),
        scope=KnowledgeScope(),
        runtime_knowledge=context.runtime,
        conflicts=conflicts,
    )
    result = CompatibilityResult(status=status, checks=checks)
    return StrictEvaluation(
        model=model,
        artifact=artifact,
        context=context,
        projection=projection,
        result=result,
    )


def _check(name: str, status: CheckStatus) -> CompatibilityCheck:
    return CompatibilityCheck(
        name=name,
        status=status,
        expected="val",
        observed="val" if status is CheckStatus.PASSED else None,
        evidence=(),
    )


class ContractAndImmutabilityTests(unittest.TestCase):
    def test_decision_is_frozen(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(_check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),),
        )
        decision = decide(eval_obj)
        self.assertIsInstance(decision, EvaluationDecision)
        with self.assertRaises(FrozenInstanceError):
            decision.verdict = DecisionVerdict.DENY  # type: ignore[misc]

    def test_policy_config_is_frozen(self) -> None:
        cfg = EvaluationPolicyConfig()
        with self.assertRaises(FrozenInstanceError):
            cfg.allow_unknown_identity = True  # type: ignore[misc]

    def test_policy_reason_is_frozen(self) -> None:
        reason = PolicyReason(code="TEST", message="msg")
        with self.assertRaises(FrozenInstanceError):
            reason.code = "OTHER"  # type: ignore[misc]

    def test_evaluation_preserved_verbatim(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(_check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),),
        )
        decision = decide(eval_obj)
        self.assertIs(decision.evaluation, eval_obj)
        self.assertEqual(decision.policy_id, "strict-v1-zero-tolerance")

    def test_invalid_construction_raises(self) -> None:
        with self.assertRaises(ValueError):
            PolicyReason(code="", message="msg")
        with self.assertRaises(ValueError):
            EvaluationPolicyConfig(policy_id="")
        with self.assertRaises(ValueError):
            EvaluationDecision(
                verdict="allow",  # type: ignore[arg-type]
                evaluation=_dummy_evaluation(),
                reasons=(),
                policy_id="test",
            )


class VerdictDerivationTests(unittest.TestCase):
    def test_compatible_yields_allow(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),
                _check("artifact format support", CheckStatus.PASSED),
            ),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.ALLOW)
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reasons[0].code, REASON_COMPATIBLE_PASS)

    def test_incompatible_yields_deny(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INCOMPATIBLE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),
                _check("artifact format support", CheckStatus.FAILED),
            ),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reasons[0].code, REASON_UNSUPPORTED_CHECK)
        self.assertEqual(decision.reasons[0].check_name, "artifact format support")

    def test_insufficient_evidence_yields_escalate(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.PASSED),
            ),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.ESCALATE)
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reasons[0].code, REASON_INSUFFICIENT_EVIDENCE)
        self.assertEqual(decision.reasons[0].check_name, IDENTITY_CHECK_NAME)

    def test_conflict_yields_deny(self) -> None:
        subj = KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp")
        obj = KnowledgeSubject(kind=KnowledgeKind.BACKEND, canonical_id="cuda")
        conflict = KnowledgeConflict(
            assertions=(
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.SUPPORTED,
                ),
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.UNSUPPORTED,
                ),
            )
        )
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(_check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),),
            conflicts=(conflict,),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reasons[0].code, REASON_BLOCKED_BY_CONFLICT)


class PrecedenceAndWaiverTests(unittest.TestCase):
    def test_conflict_precedes_failed_and_unknown(self) -> None:
        subj = KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp")
        obj = KnowledgeSubject(kind=KnowledgeKind.BACKEND, canonical_id="cuda")
        conflict = KnowledgeConflict(
            assertions=(
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.SUPPORTED,
                ),
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.UNSUPPORTED,
                ),
            )
        )
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INCOMPATIBLE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.FAILED),
            ),
            conflicts=(conflict,),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(decision.reasons[0].code, REASON_BLOCKED_BY_CONFLICT)

    def test_failed_precedes_unknown(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INCOMPATIBLE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.FAILED),
            ),
        )
        decision = decide(eval_obj)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(decision.reasons[0].code, REASON_UNSUPPORTED_CHECK)

    def test_identity_waiver_enabled_allows_when_only_identity_unknown(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.PASSED),
            ),
        )
        policy = EvaluationPolicyConfig(
            policy_id="test-waiver-policy",
            allow_unknown_identity=True,
        )
        decision = decide(eval_obj, policy=policy)
        self.assertEqual(decision.verdict, DecisionVerdict.ALLOW)
        self.assertEqual(decision.policy_id, "test-waiver-policy")
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reasons[0].code, REASON_WAIVER_IDENTITY_UNKNOWN)
        # Crucial: underlying evaluation check remains UNKNOWN!
        self.assertEqual(decision.evaluation.result.checks[0].status, CheckStatus.UNKNOWN)

    def test_identity_waiver_does_not_override_additional_unknown_checks(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.UNKNOWN),
            ),
        )
        policy = EvaluationPolicyConfig(allow_unknown_identity=True)
        decision = decide(eval_obj, policy=policy)
        self.assertEqual(decision.verdict, DecisionVerdict.ESCALATE)
        self.assertTrue(
            any(r.check_name == "artifact format support" for r in decision.reasons)
        )

    def test_identity_waiver_does_not_override_failed_check(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INCOMPATIBLE,
            checks=(
                _check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),
                _check("artifact format support", CheckStatus.FAILED),
            ),
        )
        policy = EvaluationPolicyConfig(allow_unknown_identity=True)
        decision = decide(eval_obj, policy=policy)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(decision.reasons[0].code, REASON_UNSUPPORTED_CHECK)

    def test_identity_waiver_does_not_override_conflict(self) -> None:
        subj = KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp")
        obj = KnowledgeSubject(kind=KnowledgeKind.BACKEND, canonical_id="cuda")
        conflict = KnowledgeConflict(
            assertions=(
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.SUPPORTED,
                ),
                KnowledgeAssertion(
                    subject=subj,
                    predicate=KnowledgePredicate.SUPPORTS,
                    object=obj,
                    state=KnowledgeState.UNSUPPORTED,
                ),
            )
        )
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            checks=(_check(IDENTITY_CHECK_NAME, CheckStatus.UNKNOWN),),
            conflicts=(conflict,),
        )
        policy = EvaluationPolicyConfig(allow_unknown_identity=True)
        decision = decide(eval_obj, policy=policy)
        self.assertEqual(decision.verdict, DecisionVerdict.DENY)
        self.assertEqual(decision.reasons[0].code, REASON_BLOCKED_BY_CONFLICT)


class DeterminismAndPurityTests(unittest.TestCase):
    def test_repeated_evaluations_are_equal(self) -> None:
        eval_obj = _dummy_evaluation(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(_check(IDENTITY_CHECK_NAME, CheckStatus.PASSED),),
        )
        policy = EvaluationPolicyConfig()
        d1 = decide(eval_obj, policy)
        d2 = decide(eval_obj, policy)
        self.assertEqual(d1, d2)

    def test_static_ast_purity(self) -> None:
        policy_file = Path(__file__).resolve().parent.parent / "app" / "evaluation_policy.py"
        tree = ast.parse(policy_file.read_text(encoding="utf-8"))

        forbidden_imports = {
            "os",
            "sys",
            "subprocess",
            "socket",
            "urllib",
            "pathlib",
            "shutil",
            "app.compatibility",
            "app.selection",
            "app.execution_service",
            "app.run_service",
            "app.runtimes",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden_imports)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertNotIn(module, forbidden_imports)
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    self.assertNotIn(full_name, forbidden_imports)


if __name__ == "__main__":
    unittest.main()
