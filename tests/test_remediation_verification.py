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

"""Block B7 tests: pure remediation verification (never executes anything)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from app import remediation as rem
from app import remediation_verification as rv
from app.gpu_diagnosis import (
    DiagnosisStatus,
    GpuComponent,
    component_check,
    diagnose,
)
from app.gpu_recipes import GpuRecipe
from app.gpu_setup import FunctionalCheck, GpuSoftwareStatus


def _status(kernel, drm, vulkan) -> GpuSoftwareStatus:
    return GpuSoftwareStatus(
        kernel_driver=FunctionalCheck(kernel, "detail", "test"),
        drm_device=FunctionalCheck(drm, "detail", "test"),
        vulkan=FunctionalCheck(vulkan, "detail", "test"),
    )


def _diagnosis(kernel, drm, vulkan, *, backend="vulkan", platform="linux"):
    return diagnose(
        _status(kernel, drm, vulkan), "llama.cpp", backend, platform=platform)


def _recipe_lookup(runtime, backend, component, platform):
    return GpuRecipe(
        id=f"recipe-{component.value}",
        name=f"recipe {component.value}",
        runtime=runtime,
        backend=backend,
        component=component,
        description="test recipe",
        install_commands=(f"install {component.value}",),
        verify_commands=(f"verify {component.value}",),
        platforms=(platform or "linux",),
    )


def _plan(diagnosis):
    with patch("app.remediation.find_recipe", side_effect=_recipe_lookup):
        return rem.build_remediation_plan(diagnosis)


OUTCOME = rv.RemediationVerificationOutcome


class ComparisonSemanticsTests(unittest.TestCase):
    """MISSING → READY/MISSING/UNKNOWN per remediated component."""

    def _verify(self, before, after):
        original = _diagnosis(*before)
        return rv.verify_remediation(
            original, _plan(original), _diagnosis(*after), _status(*after))

    def test_missing_to_ready_is_passed(self):
        verification = self._verify((True, True, False), (True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.VERIFIED)
        result = verification.per_component[0]
        self.assertEqual(result.status, rv.VerificationStatus.PASSED)
        self.assertEqual(
            result.expected_status, DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(result.observed_status, DiagnosisStatus.READY)
        self.assertIsNotNone(result.evidence)

    def test_missing_to_missing_is_failed(self):
        verification = self._verify((True, True, False), (True, True, False))
        self.assertEqual(verification.outcome, OUTCOME.NOT_VERIFIED)
        self.assertEqual(
            verification.per_component[0].status,
            rv.VerificationStatus.FAILED)

    def test_missing_to_unknown_stays_unknown(self):
        original = _diagnosis(True, True, False)
        after_status = GpuSoftwareStatus(
            kernel_driver=FunctionalCheck(True, "d", "t"),
            drm_device=FunctionalCheck(True, "d", "t"),
            vulkan=FunctionalCheck(None, "not determined", "t"),
        )
        followup = diagnose(
            after_status, "llama.cpp", "vulkan", platform="linux")
        verification = rv.verify_remediation(
            original, _plan(original), followup, after_status)
        self.assertEqual(verification.outcome, OUTCOME.UNKNOWN)
        result = verification.per_component[0]
        self.assertEqual(result.status, rv.VerificationStatus.UNKNOWN)
        self.assertEqual(result.observed_status, DiagnosisStatus.UNKNOWN)


class UncertaintyTests(unittest.TestCase):
    def test_unknown_original_never_fabricates_expectations(self):
        original = _diagnosis(None, True, True)
        plan = _plan(original)
        self.assertEqual(
            plan.status, rem.RemediationStatus.NO_ACTION_REQUIRED_YET)
        verification = rv.verify_remediation(
            original, plan,
            _diagnosis(True, True, True), _status(True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.UNKNOWN)
        self.assertEqual(verification.per_component, ())
        self.assertIn(
            "no expectation can be verified", " ".join(verification.notes))

    def test_ready_original_is_not_attempted(self):
        original = _diagnosis(True, True, True)
        plan = _plan(original)
        self.assertEqual(plan.status, rem.RemediationStatus.NO_REMEDIATION)
        verification = rv.verify_remediation(
            original, plan, original, _status(True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.NOT_ATTEMPTED)
        self.assertEqual(verification.per_component, ())


class MultiComponentAggregationTests(unittest.TestCase):
    def _verify(self, before, after):
        original = _diagnosis(*before)
        return rv.verify_remediation(
            original, _plan(original), _diagnosis(*after), _status(*after))

    def test_all_passed_is_verified(self):
        verification = self._verify((False, False, False), (True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.VERIFIED)
        self.assertEqual(len(verification.per_component), 3)

    def test_any_failed_is_not_verified(self):
        verification = self._verify((False, False, False), (True, False, True))
        self.assertEqual(verification.outcome, OUTCOME.NOT_VERIFIED)

    def test_unknown_without_failure_is_unknown(self):
        original = _diagnosis(False, False, False)
        after_status = GpuSoftwareStatus(
            kernel_driver=FunctionalCheck(True, "d", "t"),
            drm_device=FunctionalCheck(None, "d", "t"),
            vulkan=FunctionalCheck(True, "d", "t"),
        )
        followup = diagnose(
            after_status, "llama.cpp", "vulkan", platform="linux")
        verification = rv.verify_remediation(
            original, _plan(original), followup, after_status)
        self.assertEqual(verification.outcome, OUTCOME.UNKNOWN)


class TraceabilityTests(unittest.TestCase):
    def test_recipe_ref_follows_the_plan_problem(self):
        original = _diagnosis(True, True, False)
        plan = _plan(original)
        verification = rv.verify_remediation(
            original, plan,
            _diagnosis(True, True, True), _status(True, True, True))
        by_component = {
            result.component: result for result in verification.per_component}
        for problem in plan.problems:
            result = by_component[problem.component]
            self.assertEqual(result.recipe_ref, problem.recipe_ref)
            self.assertEqual(
                result.recipe_ref, f"recipe-{problem.component.value}")

    def test_report_is_human_readable(self):
        original = _diagnosis(True, True, False)
        verification = rv.verify_remediation(
            original, _plan(original),
            _diagnosis(True, True, True), _status(True, True, True))
        text = rv.format_remediation_verification(verification)
        self.assertIn("Outcome: VERIFIED", text)
        self.assertIn("vulkan_functional: PASSED", text)
        self.assertIn("run manually", text)


class NoRecipeAndSpecialPlanTests(unittest.TestCase):
    def test_plan_without_recipes_is_not_attempted(self):
        original = _diagnosis(True, True, False, platform="openbsd")
        plan = rem.build_remediation_plan(original)
        self.assertEqual(plan.status, rem.RemediationStatus.NEEDS_RESEARCH)
        verification = rv.verify_remediation(
            original, plan,
            _diagnosis(True, True, True, platform="openbsd"),
            _status(True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.NOT_ATTEMPTED)
        self.assertEqual(verification.per_component, ())
        self.assertTrue(
            any("No local recipe" in note for note in verification.notes))

    def test_needs_research_partial_recipe_verifies_only_known(self):
        original = _diagnosis(False, True, False)
        with patch(
            "app.remediation.find_recipe",
            side_effect=lambda runtime, backend, component, platform: (
                _recipe_lookup(runtime, backend, component, platform)
                if component is GpuComponent.VULKAN_FUNCTIONAL else None
            ),
        ):
            plan = rem.build_remediation_plan(original)
        self.assertEqual(plan.status, rem.RemediationStatus.NEEDS_RESEARCH)
        verification = rv.verify_remediation(
            original, plan,
            _diagnosis(True, True, True), _status(True, True, True))
        self.assertEqual(len(verification.per_component), 1)
        self.assertEqual(
            verification.per_component[0].component,
            GpuComponent.VULKAN_FUNCTIONAL)
        self.assertTrue(
            any("No local recipe" in note for note in verification.notes))

    def test_context_change_skips_invalid_comparison(self):
        original = _diagnosis(True, True, False)
        followup = _diagnosis(True, True, True, backend="cpu")
        verification = rv.verify_remediation(
            original, _plan(original), followup, _status(True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.UNKNOWN)
        self.assertEqual(verification.per_component, ())
        self.assertTrue(
            any("backend changed" in warning
                for warning in verification.warnings))


class SafetySurfaceTests(unittest.TestCase):
    """B7 must have no execution, shell, network or recipe-execution surface."""

    def test_module_imports_are_pure(self):
        source = Path(rv.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "subprocess")
                self.assertNotEqual(node.module, "os")
                self.assertNotEqual(node.module, "socket")
                self.assertNotEqual(node.module, "urllib")

    def test_no_execution_helpers_exposed(self):
        for name in ("subprocess", "os", "shutil", "socket", "urllib"):
            self.assertFalse(hasattr(rv, name), name)

    def test_commands_from_recipes_are_never_executed(self):
        def explode(*args, **kwargs):
            raise AssertionError("B7 must never execute commands")

        original = _diagnosis(True, True, False)
        plan = _plan(original)
        with patch("subprocess.run", side_effect=explode), patch(
            "subprocess.Popen", side_effect=explode
        ), patch("os.system", side_effect=explode), patch(
            "socket.socket", side_effect=explode
        ), patch("builtins.eval", side_effect=explode), patch(
            "builtins.exec", side_effect=explode
        ):
            verification = rv.verify_remediation(
                original, plan,
                _diagnosis(True, True, True), _status(True, True, True))
        self.assertEqual(verification.outcome, OUTCOME.VERIFIED)


if __name__ == "__main__":
    unittest.main()
