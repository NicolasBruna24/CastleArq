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

"""Block B9.1 tests: immutable compatibility-result domain (no engine)."""

from __future__ import annotations

import ast
import dataclasses
import unittest
from pathlib import Path
from unittest.mock import patch

from app import compatibility_domain as cd


STATUS = cd.CompatibilityStatus
CHECK = cd.CheckStatus
KIND = cd.EvidenceKind


def _evidence(**overrides):
    fields = {
        "source": "ModelArtifact.format",
        "value": "GGUF",
        "kind": KIND.OBSERVED,
        **overrides,
    }
    return cd.EvidenceItem(**fields)


def _check(**overrides):
    fields = {
        "name": "artifact format supported",
        "status": CHECK.PASSED,
        "expected": "GGUF",
        "observed": "GGUF",
        "evidence": (_evidence(),),
        **overrides,
    }
    return cd.CompatibilityCheck(**fields)


def _condition(**overrides):
    fields = {
        "name": "CPU offloading",
        "description": "CPU offloading may be required.",
        "evidence": (_evidence(
            source="HardwareSnapshot.gpus[0].vram",
            value=8 * 1024 ** 3,
            kind=KIND.OBSERVED,
        ),),
        **overrides,
    }
    return cd.CompatibilityCondition(**fields)


class CompatibilityStatusTests(unittest.TestCase):
    def test_exact_four_states(self):
        self.assertEqual(
            {item.value for item in STATUS},
            {"compatible", "compatible_with_conditions", "incompatible",
             "insufficient_evidence"})

    def test_no_arbitrary_states(self):
        with self.assertRaises(ValueError):
            STATUS("unknown")
        with self.assertRaises(ValueError):
            STATUS("compatible=true")


class CheckStatusTests(unittest.TestCase):
    def test_three_states(self):
        self.assertEqual(
            {item.value for item in CHECK}, {"passed", "failed", "unknown"})
        self.assertIsNotNone(CHECK("passed"))

    def test_status_is_never_none(self):
        with self.assertRaises(ValueError):
            _check(status=None)


class EvidenceKindTests(unittest.TestCase):
    def test_three_levels(self):
        self.assertEqual(
            {item.value for item in KIND},
            {"observed", "calculated", "inferred"})


class EvidenceTests(unittest.TestCase):
    def test_observed(self):
        item = _evidence(kind=KIND.OBSERVED)
        self.assertEqual(item.value, "GGUF")

    def test_calculated(self):
        item = _evidence(
            source="available_memory",
            value=24 * 1024 ** 3,
            kind=KIND.CALCULATED,
        )
        self.assertIs(item.kind, KIND.CALCULATED)

    def test_inferred_stays_inferred(self):
        item = _evidence(
            source="offloading analysis",
            value="CPU offloading may be required",
            kind=KIND.INFERRED,
        )
        self.assertIs(item.kind, KIND.INFERRED)
        self.assertIsNot(item.kind, KIND.OBSERVED)

    def test_unknown_value_allowed(self):
        self.assertIsNone(_evidence(value=None).value)

    def test_source_must_be_non_empty(self):
        for source in (None, "", "   ", 42):
            with self.assertRaises(ValueError):
                _evidence(source=source)

    def test_kind_must_be_valid(self):
        with self.assertRaises(ValueError):
            _evidence(kind="observed")
        with self.assertRaises(ValueError):
            _evidence(kind=None)

    def test_value_types(self):
        for value in ("x", 4, 4.5, True, None):
            self.assertEqual(_evidence(value=value).value, value)
        for value in ([1], {"a": 1}, (1,)):
            with self.assertRaises(ValueError):
                _evidence(value=value)

    def test_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            _evidence().value = "Q8"

    def test_no_secrets_helpers(self):
        self.assertFalse(hasattr(cd.EvidenceItem, "password"))


class CompatibilityCheckTests(unittest.TestCase):
    def test_valid_check(self):
        check = _check()
        self.assertIs(check.status, CHECK.PASSED)
        self.assertEqual(len(check.evidence), 1)

    def test_unknown_expected_observed(self):
        check = _check(expected=None, observed=None, status=CHECK.UNKNOWN)
        self.assertIsNone(check.expected)
        self.assertIsNone(check.observed)

    def test_name_must_be_non_empty(self):
        for name in (None, "", "  ", 7):
            with self.assertRaises(ValueError):
                _check(name=name)

    def test_evidence_members_must_be_items(self):
        with self.assertRaises(ValueError):
            _check(evidence=("ModelArtifact.format",))

    def test_list_evidence_frozen_into_tuple(self):
        check = _check(evidence=[_evidence()])
        self.assertIsInstance(check.evidence, tuple)

    def test_frozen_and_immutable_collection(self):
        check = _check()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            check.status = CHECK.FAILED
        with self.assertRaises(AttributeError):
            check.evidence.append(_evidence())


class CompatibilityConditionTests(unittest.TestCase):
    def test_valid_condition(self):
        condition = _condition()
        self.assertEqual(condition.name, "CPU offloading")

    def test_empty_description_rejected(self):
        for description in (None, "", "   "):
            with self.assertRaises(ValueError):
                _condition(description=description)

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            _condition(name=" ")

    def test_condition_carries_no_commands(self):
        condition = _condition()
        for forbidden in ("command", "shell_command", "install_command",
                          "execute", "action"):
            self.assertFalse(hasattr(condition, forbidden))
        self.assertNotIn("configure", condition.description.lower())

    def test_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            _condition().description = "other"


class CompatibilityResultTests(unittest.TestCase):
    def _result(self, **overrides):
        fields = {"status": STATUS.COMPATIBLE, **overrides}
        return cd.CompatibilityResult(**fields)

    def test_compatible_without_conditions(self):
        result = self._result(checks=(_check(),))
        self.assertIs(result.status, STATUS.COMPATIBLE)
        self.assertEqual(result.conditions, ())

    def test_compatible_rejects_conditions(self):
        with self.assertRaises(ValueError):
            self._result(conditions=(_condition(),))

    def test_compatible_with_conditions(self):
        result = self._result(
            status=STATUS.COMPATIBLE_WITH_CONDITIONS,
            checks=(
                _check(name="format"),
                _check(name="runtime"),
                _check(name="backend"),
                _check(name="memory", status=CHECK.UNKNOWN,
                       expected=None, observed=None),
            ),
            conditions=(_condition(
                name="CPU offloading",
                description="CPU offloading may be required.",
            ),),
            warnings=("Runtime memory estimation unavailable.",),
        )
        self.assertEqual(len(result.checks), 4)
        self.assertEqual(len(result.conditions), 1)

    def test_compatible_with_conditions_requires_conditions(self):
        with self.assertRaises(ValueError):
            self._result(status=STATUS.COMPATIBLE_WITH_CONDITIONS)

    def test_incompatible_requires_failed_check(self):
        result = self._result(
            status=STATUS.INCOMPATIBLE,
            checks=(_check(status=CHECK.FAILED, observed="ONNX"),),
        )
        self.assertIs(result.status, STATUS.INCOMPATIBLE)

    def test_incompatible_without_failed_check_rejected(self):
        with self.assertRaises(ValueError):
            self._result(status=STATUS.INCOMPATIBLE, checks=(_check(),))
        with self.assertRaises(ValueError):
            self._result(
                status=STATUS.INCOMPATIBLE,
                checks=(_check(status=CHECK.UNKNOWN),))

    def test_insufficient_evidence(self):
        result = self._result(
            status=STATUS.INSUFFICIENT_EVIDENCE,
            checks=(
                _check(status=CHECK.UNKNOWN, expected=None, observed=None),
                _check(status=CHECK.UNKNOWN, expected=None, observed=None),
            ),
            warnings=("Runtime memory estimation unavailable.",),
        )
        self.assertIs(result.status, STATUS.INSUFFICIENT_EVIDENCE)

    def test_no_compatible_bool(self):
        self.assertFalse(hasattr(cd.CompatibilityResult, "compatible"))
        self.assertFalse(hasattr(cd.CompatibilityResult, "can_run"))

    def test_no_memory_estimates(self):
        result = self._result()
        for field_name in ("estimated_vram", "estimated_ram",
                           "estimated_runtime_memory", "memory_formula"):
            self.assertFalse(hasattr(result, field_name))

    def test_no_storage_runtime_confusion(self):
        result = self._result()
        for field_name in ("storage_size_bytes", "runtime_memory"):
            self.assertFalse(hasattr(result, field_name))

    def test_warnings_must_be_non_empty_strings(self):
        with self.assertRaises(ValueError):
            self._result(warnings=("",))
        with self.assertRaises(ValueError):
            self._result(warnings=(42,))

    def test_frozen_with_immutable_collections(self):
        result = self._result(checks=[_check()], warnings=["careful"])
        self.assertIsInstance(result.checks, tuple)
        self.assertIsInstance(result.warnings, tuple)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.status = STATUS.INCOMPATIBLE
        with self.assertRaises(AttributeError):
            result.checks.append(_check())


class UnknownSemanticsTests(unittest.TestCase):
    """UNKNOWN never becomes FAILED or INCOMPATIBLE by itself."""

    def test_check_unknown_is_not_failed(self):
        check = _check(status=CHECK.UNKNOWN)
        self.assertNotEqual(check.status, CHECK.FAILED)
        self.assertNotEqual(check.status.value, CHECK.FAILED.value)

    def test_result_with_only_unknown_checks_is_not_incompatible(self):
        result = cd.CompatibilityResult(
            status=STATUS.INSUFFICIENT_EVIDENCE,
            checks=(_check(status=CHECK.UNKNOWN),),
        )
        self.assertNotEqual(result.status, STATUS.INCOMPATIBLE)

    def test_isolated_unknown_does_not_force_insufficient_evidence(self):
        """An isolated UNKNOWN next to PASSED checks is representable;
        sufficiency is the future engine's decision (no auto-aggregation)."""
        result = cd.CompatibilityResult(
            status=STATUS.COMPATIBLE,
            checks=(_check(name="format"),),
        )
        check = _check(name="temperature", status=CHECK.UNKNOWN,
                       expected=None, observed=None)
        self.assertIs(result.status, STATUS.COMPATIBLE)
        self.assertIs(check.status, CHECK.UNKNOWN)


class PurityTests(unittest.TestCase):
    """B9.1 must be a pure domain: no I/O, no execution surface."""

    def test_module_imports_are_pure(self):
        source = Path(cd.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"__future__", "dataclasses", "enum", "typing"}
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)

    def test_no_execution_surface(self):
        for name in ("subprocess", "socket", "urllib", "requests", "os",
                     "eval", "exec", "open"):
            self.assertFalse(hasattr(cd, name), name)

    def test_no_side_effects_when_building(self):
        def explode(*args, **kwargs):
            raise AssertionError("B9.1 must never execute anything")

        with patch("subprocess.run", side_effect=explode), patch(
            "socket.socket", side_effect=explode
        ):
            result = cd.CompatibilityResult(
                status=STATUS.COMPATIBLE, checks=(_check(),))
        self.assertIs(result.status, STATUS.COMPATIBLE)


if __name__ == "__main__":
    unittest.main()
