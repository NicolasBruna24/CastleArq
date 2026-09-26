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

"""B9.48 tests: compatibility evaluation explainability and error semantics.

Covers the four obligations of the block:

* the existing evaluation result is presented with its checks, reasons and
  evidence (P0-1);
* an evaluation that RAISED stays distinct from one that DENIED (P0-2);
* the read-only ``compatibility`` command answers without inference (P1-1);
* ``run``/``execute`` policy difference is explicit and protected (P1-2),
  and the CLI surface matches the help (P1-3).

The evaluation machinery itself is NOT re-tested here: it is covered by
``tests/test_evaluate_compatibility.py`` and ``tests/test_evaluation_*``.
"""

from __future__ import annotations

import io
import sys
import unittest
from unittest import mock
from unittest.mock import patch

from app.compatibility_domain import (
    CheckStatus,
    CompatibilityCheck,
    CompatibilityCondition,
    CompatibilityResult,
    CompatibilityStatus,
    EvidenceItem,
    EvidenceKind,
)
from app.compatibility_report import format_evaluation_report
from app.evaluate_compatibility import EvaluateModelCompatibilityResult
from app.execution import (
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionResult,
)
from app.gguf_reader import GGUFReadError
from app.models import ArtifactSpec


def _check(name, status, expected=None, observed=None, evidence=()):
    return CompatibilityCheck(
        name=name,
        status=status,
        expected=expected,
        observed=observed,
        evidence=tuple(evidence),
    )


def _result(status, checks, *, conditions=(), warnings=(), model_id="m1"):
    strict = mock.Mock()
    strict.status = status
    strict.checks = tuple(checks)
    strict.conditions = tuple(conditions)
    strict.warnings = tuple(warnings)
    evaluation = mock.Mock(result=strict)
    return EvaluateModelCompatibilityResult(
        model_id=model_id,
        artifact=ArtifactSpec(
            model_id=model_id,
            source="huggingface",
            repository="org/repo",
            filename="model.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        ),
        runtime="llama.cpp CLI",
        capability=None,
        evaluation=evaluation,
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


def _cli(*argv):
    """Run ``main()`` with injected argv/streams; return (code, out, err)."""
    from app.main import main

    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", ["castlearq", *argv]), patch.object(
        sys, "stdout", new=stdout
    ), patch.object(sys, "stderr", new=stderr):
        try:
            code = main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0
    return code, stdout.getvalue(), stderr.getvalue()


class ExplanationTests(unittest.TestCase):
    """P0-1: the existing verdict becomes visible."""

    def test_passed_check_shows_status_expected_observed_and_evidence(self):
        result = _result(
            CompatibilityStatus.COMPATIBLE,
            [
                _check(
                    "artifact format support",
                    CheckStatus.PASSED,
                    expected="gguf",
                    observed="gguf",
                    evidence=[
                        EvidenceItem(
                            source="artifact.format",
                            value="gguf",
                            kind=EvidenceKind.OBSERVED,
                        )
                    ],
                )
            ],
        )
        text = format_evaluation_report(result)
        self.assertIn("Verdict: COMPATIBLE", text)
        self.assertIn("artifact format support: PASSED", text)
        self.assertIn("Expected: 'gguf'", text)
        self.assertIn("Observed: 'gguf'", text)
        self.assertIn("artifact.format = 'gguf'", text)

    def test_failed_check_is_named_so_the_user_knows_what_blocked(self):
        result = _result(
            CompatibilityStatus.INCOMPATIBLE,
            [
                _check(
                    "model architecture support",
                    CheckStatus.FAILED,
                    expected="llama",
                    observed="qwen2",
                )
            ],
        )
        text = format_evaluation_report(result)
        self.assertIn("Verdict: INCOMPATIBLE", text)
        self.assertIn("model architecture support: FAILED", text)
        self.assertIn("Expected: 'llama'", text)
        self.assertIn("Observed: 'qwen2'", text)

    def test_multiple_relevant_checks_are_all_shown(self):
        result = _result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [
                _check("a-check", CheckStatus.FAILED, expected="x", observed="y"),
                _check("b-check", CheckStatus.UNKNOWN),
                _check("c-check", CheckStatus.PASSED),
            ],
        )
        text = format_evaluation_report(result)
        for name in ("a-check", "b-check", "c-check"):
            self.assertIn(name, text)
        self.assertIn("a-check: FAILED", text)
        self.assertIn("b-check: UNKNOWN", text)
        self.assertIn("c-check: PASSED", text)

    def test_unknown_check_is_not_reported_as_failed(self):
        result = _result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [_check("runtime artifact support", CheckStatus.UNKNOWN)],
        )
        text = format_evaluation_report(result)
        self.assertIn("runtime artifact support: UNKNOWN", text)
        self.assertNotIn("runtime artifact support: FAILED", text)

    def test_blocked_result_shows_its_blocking_outcome(self):
        result = EvaluateModelCompatibilityResult(
            model_id="m1",
            artifact=None,
            runtime="llama.cpp CLI",
            capability=None,
            evaluation=None,
            integration=None,
            status="blocked",
            blocking_outcome="Model not found in the local catalog: m1",
        )
        text = format_evaluation_report(result)
        self.assertIn("Verdict: BLOCKED (not admitted)", text)
        self.assertIn("Model not found in the local catalog: m1", text)

    def test_conditions_and_warnings_survive_presentation(self):
        result = _result(
            CompatibilityStatus.COMPATIBLE,
            [_check("c", CheckStatus.PASSED)],
            conditions=[
                CompatibilityCondition(
                    name="backend", description="Vulkan is required"
                )
            ],
            warnings=["Model memory is an estimate."],
        )
        text = format_evaluation_report(result)
        self.assertIn("Condition: backend: Vulkan is required", text)
        self.assertIn("Warning: Model memory is an estimate", text)

    def test_none_result_does_not_raise(self):
        self.assertIn(
            "No compatibility evaluation result", format_evaluation_report(None)
        )

    def test_report_does_not_invent_a_reason_when_none_exists(self):
        result = _result(CompatibilityStatus.INSUFFICIENT_EVIDENCE, [])
        self.assertNotIn("Reason:", format_evaluation_report(result))

    def test_report_is_deterministic(self):
        result = _result(
            CompatibilityStatus.COMPATIBLE, [_check("c", CheckStatus.PASSED)]
        )
        self.assertEqual(
            format_evaluation_report(result), format_evaluation_report(result)
        )

    def test_real_compatibility_result_is_accepted(self):
        """The formatter works on genuine domain objects, not only mocks."""
        strict = CompatibilityResult(
            status=CompatibilityStatus.COMPATIBLE,
            checks=(
                CompatibilityCheck(
                    name="artifact format support",
                    status=CheckStatus.PASSED,
                    expected="gguf",
                    observed="gguf",
                ),
            ),
        )
        evaluation = mock.Mock(result=strict)
        result = EvaluateModelCompatibilityResult(
            model_id="m1",
            artifact=None,
            runtime="llama.cpp CLI",
            capability=None,
            evaluation=evaluation,
            integration=None,
            status="evaluated",
            blocking_outcome=None,
        )
        text = format_evaluation_report(result)
        self.assertIn("Verdict: COMPATIBLE", text)
        self.assertIn("artifact format support: PASSED", text)


class ReadOnlyCompatibilityCommandTests(unittest.TestCase):
    """P1-1: ask the question without running inference."""

    def test_command_is_registered_and_dispatched(self):
        with patch("app.main.compatibility_command", return_value=0) as caller:
            code, _, _ = _cli("compatibility", "m1")
        self.assertEqual(code, 0)
        caller.assert_called_once_with("m1", quantization=None, filename=None)

    def test_missing_model_id_is_usage_error_without_evaluation(self):
        with patch("app.main.evaluate_model_compatibility") as evaluate:
            code, out, err = _cli("compatibility")
        self.assertEqual(code, 2)
        self.assertIn("Usage:", err)
        self.assertEqual(out, "")
        evaluate.assert_not_called()

    def test_extra_positional_is_rejected(self):
        code, _, _ = _cli("compatibility", "m1", "unexpected")
        self.assertEqual(code, 2)

    def test_it_reuses_the_same_use_case_and_runs_no_runtime(self):
        from app.main import compatibility_command

        result = _result(
            CompatibilityStatus.COMPATIBLE, [_check("c", CheckStatus.PASSED)]
        )
        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.evaluate_model_compatibility", return_value=result
        ) as evaluate, patch("app.main.LlamaCppRunner") as runner, patch(
            "app.main.execute_model"
        ) as execute, patch("app.main.run_model") as run:
            code = compatibility_command("m1", out=out, err=err)
        self.assertEqual(code, 0)
        evaluate.assert_called_once_with("m1", quantization=None, filename=None)
        runner.assert_not_called()
        execute.assert_not_called()
        run.assert_not_called()
        self.assertIn("Verdict: COMPATIBLE", out.getvalue())

    def test_it_does_not_download(self):
        from app.main import compatibility_command

        result = _result(
            CompatibilityStatus.COMPATIBLE, [_check("c", CheckStatus.PASSED)]
        )
        with patch(
            "app.main.evaluate_model_compatibility", return_value=result
        ), patch("app.main.run_download") as download:
            code = compatibility_command("m1", out=io.StringIO(), err=io.StringIO())
        self.assertEqual(code, 0)
        download.assert_not_called()

    def test_denied_evaluation_returns_one_and_still_explains(self):
        from app.main import compatibility_command

        result = _result(
            CompatibilityStatus.INCOMPATIBLE,
            [
                _check(
                    "model architecture support",
                    CheckStatus.FAILED,
                    expected="llama",
                    observed="qwen2",
                )
            ],
        )
        out = io.StringIO()
        with patch("app.main.evaluate_model_compatibility", return_value=result):
            code = compatibility_command("m1", out=out, err=io.StringIO())
        self.assertEqual(code, 1)
        self.assertIn("model architecture support: FAILED", out.getvalue())

    def test_insufficient_evidence_follows_the_existing_admission_policy(self):
        """The command reports; it never re-decides policy.

        ``to_admission`` maps INSUFFICIENT_EVIDENCE whose only UNKNOWN checks
        are the non-blocking runtime-artifact/backend pair to ``compatible``.
        The command therefore exits 0 here, exactly as ``execute`` would, and
        still shows the UNKNOWN checks truthfully.
        """
        from app.main import compatibility_command

        result = _result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [
                _check("runtime artifact support", CheckStatus.UNKNOWN),
                _check("runtime backend support", CheckStatus.UNKNOWN),
            ],
        )
        out = io.StringIO()
        with patch("app.main.evaluate_model_compatibility", return_value=result):
            code = compatibility_command("m1", out=out, err=io.StringIO())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("Verdict: INSUFFICIENT_EVIDENCE", text)
        self.assertIn("runtime artifact support: UNKNOWN", text)
        self.assertIn("runtime backend support: UNKNOWN", text)
        # UNKNOWN is never upgraded or downgraded by presentation.
        self.assertNotIn("FAILED", text)

    def test_insufficient_evidence_with_a_real_failure_is_reported_as_denied(self):
        from app.main import compatibility_command

        result = _result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [
                _check("model architecture support", CheckStatus.FAILED, expected="llama", observed="qwen2"),
                _check("runtime artifact support", CheckStatus.UNKNOWN),
            ],
        )
        out = io.StringIO()
        with patch("app.main.evaluate_model_compatibility", return_value=result):
            code = compatibility_command("m1", out=out, err=io.StringIO())
        self.assertEqual(code, 1)
        self.assertIn("model architecture support: FAILED", out.getvalue())


class EvaluationErrorSemanticsTests(unittest.TestCase):
    """P0-2: a raised evaluation is not a policy denial."""

    def test_compatibility_command_reports_error_not_verdict(self):
        from app.main import compatibility_command

        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.evaluate_model_compatibility",
            side_effect=GGUFReadError("truncated header"),
        ):
            code = compatibility_command("m1", out=out, err=err)
        self.assertEqual(code, 1)
        text = err.getvalue()
        self.assertIn("Compatibility evaluation error:", text)
        self.assertIn("GGUFReadError", text)
        self.assertIn("truncated header", text)
        # It must not masquerade as a policy decision.
        self.assertNotIn("Verdict:", text)
        self.assertNotIn("deny-by-default", text)
        self.assertEqual(out.getvalue(), "")

    def test_execute_reports_error_and_stays_fail_closed(self):
        from app.execute_model import ExecuteAdmissionDeniedError
        from app.main import execute_command

        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.compose_execute_model_dependencies", return_value=object()
        ), patch(
            "app.main.evaluate_model_compatibility",
            side_effect=ValueError("corrupt gguf"),
        ), patch("app.main.execute_model") as execute:
            execute.side_effect = ExecuteAdmissionDeniedError(
                "Execution denied by evaluation admission; deny-by-default applies"
            )
            code = execute_command("m1", "hi", out=out, err=err)
        self.assertEqual(code, 1)
        text = err.getvalue()
        self.assertIn("Compatibility evaluation error:", text)
        self.assertIn("ValueError", text)
        self.assertIn("corrupt gguf", text)
        # Fail-closed is preserved: execution was reached with a blocked
        # admission, so the gate refused and nothing ran.
        admission = execute.call_args.kwargs["admission"]
        self.assertEqual(admission.status, "blocked")
        self.assertIsNone(admission.verdict)
        # The failure is attributed to the evaluation, not to the policy.
        self.assertNotIn("Verdict:", text)

    def test_resolution_error_is_not_reported_as_a_verdict(self):
        from app.main import compatibility_command
        from app.resolver import ModelArtifactResolutionError

        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.evaluate_model_compatibility",
            side_effect=ModelArtifactResolutionError("no such model"),
        ):
            code = compatibility_command("m1", out=out, err=err)
        self.assertEqual(code, 1)
        self.assertIn("Compatibility evaluation error:", err.getvalue())
        self.assertNotIn("Verdict:", err.getvalue())

    def test_os_error_is_not_reported_as_a_verdict(self):
        from app.main import compatibility_command

        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.evaluate_model_compatibility",
            side_effect=OSError("store unreadable"),
        ):
            code = compatibility_command("m1", out=out, err=err)
        self.assertEqual(code, 1)
        self.assertIn("Compatibility evaluation error:", err.getvalue())
        self.assertNotIn("not admitted", err.getvalue())


class AdmissionExplanationTests(unittest.TestCase):
    """P0-1 on the execute path: the denial shows its checks."""

    def test_admission_denial_message_is_kept_and_explained(self):
        from app.execute_model import ExecuteAdmissionDeniedError
        from app.main import execute_command

        result = _result(
            CompatibilityStatus.INCOMPATIBLE,
            [_check("a", CheckStatus.FAILED, expected="x", observed="y")],
        )
        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.compose_execute_model_dependencies", return_value=object()
        ), patch(
            "app.main.evaluate_model_compatibility", return_value=result
        ), patch(
            "app.main.execute_model",
            side_effect=ExecuteAdmissionDeniedError(
                "Execution denied by evaluation admission; deny-by-default applies"
            ),
        ):
            code = execute_command("m1", "hi", out=out, err=err)
        self.assertEqual(code, 1)
        text = err.getvalue()
        self.assertIn("Execution denied by evaluation admission", text)
        self.assertIn("Verdict: INCOMPATIBLE", text)
        self.assertIn("a: FAILED", text)
        self.assertIn("Observed: 'y'", text)

    def test_no_report_is_repeated_when_the_evaluation_raised(self):
        from app.execute_model import ExecuteAdmissionDeniedError
        from app.main import execute_command

        out, err = io.StringIO(), io.StringIO()
        with patch(
            "app.main.compose_execute_model_dependencies", return_value=object()
        ), patch(
            "app.main.evaluate_model_compatibility",
            side_effect=RuntimeError("boom"),
        ), patch(
            "app.main.execute_model",
            side_effect=ExecuteAdmissionDeniedError("Execution denied"),
        ):
            code = execute_command("m1", "hi", out=out, err=err)
        self.assertEqual(code, 1)
        self.assertEqual(err.getvalue().count("Compatibility evaluation error:"), 1)

    def test_successful_execution_is_unchanged(self):
        from app.main import execute_command

        result = _result(
            CompatibilityStatus.COMPATIBLE, [_check("c", CheckStatus.PASSED)]
        )
        out, err = io.StringIO(), io.StringIO()
        success = ExecutionResult(True, 0, "model output\n", "")
        with patch(
            "app.main.compose_execute_model_dependencies", return_value=object()
        ), patch(
            "app.main.evaluate_model_compatibility", return_value=result
        ), patch("app.main.execute_model", return_value=success):
            code = execute_command("m1", "hi", out=out, err=err)
        self.assertEqual(code, 0)
        self.assertIn("model output", out.getvalue())
        # A successful run must not print an evaluation report.
        self.assertNotIn("Compatibility evaluation", out.getvalue())


class ExecutionPolicyTests(unittest.TestCase):
    """P1-2: the run/execute difference is explicit and protected."""

    def test_run_does_not_apply_strict_evaluation_admission(self):
        """`run` stays the legacy path; this pins the documented difference."""
        import ast
        from pathlib import Path

        tree = ast.parse(Path("app/main.py").read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        run_refs = {
            child.id
            for child in ast.walk(functions["run_model"])
            if isinstance(child, ast.Name)
        }
        self.assertNotIn("evaluate_model_compatibility", run_refs)
        self.assertNotIn("to_admission", run_refs)

        execute_refs = {
            child.id
            for child in ast.walk(functions["execute_command"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("evaluate_model_compatibility", execute_refs)
        self.assertIn("to_admission", execute_refs)

    def test_both_commands_still_exist_and_are_not_renamed(self):
        code, out, _ = _cli("--help")
        self.assertEqual(code, 0)
        for command in ("run", "execute"):
            self.assertIn(command, out)

    def test_help_documents_the_policy_difference(self):
        _, out, _ = _cli("--help")
        self.assertIn("execute is the recommended command", out)
        self.assertIn("NOT apply the strict evaluation admission", out)

    def test_run_still_reaches_the_legacy_runtime_path(self):
        """`run` keeps working: it is not removed, only documented."""
        from app.main import run_model

        self.assertTrue(callable(run_model))


class CliSurfaceTests(unittest.TestCase):
    """P1-3: the help matches the real surface."""

    def test_help_lists_compatibility_and_execute(self):
        code, out, _ = _cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("compatibility", out)
        self.assertIn("execute", out)

    def test_usage_flow_recommends_execute_and_compatibility(self):
        _, out, _ = _cli("--help")
        self.assertIn("castlearq execute qwen2.5-coder-7b-instruct", out)
        self.assertIn("castlearq compatibility", out)

    def test_help_mentions_every_command_the_binary_exposes(self):
        _, out, _ = _cli("--help")
        for command in (
            "detect",
            "diagnose",
            "verify",
            "models",
            "list",
            "runtime",
            "source",
            "plan",
            "compatibility",
            "download",
            "run",
            "execute",
            "chat",
            "serve",
        ):
            self.assertIn(command, out)

    def test_help_clarifies_verify_is_environment_not_artifact(self):
        _, out, _ = _cli("--help")
        self.assertIn("ENVIRONMENT, not artifact integrity", out)


class NoNewArchitectureTests(unittest.TestCase):
    """B9.48 section 13: no new layer was introduced."""

    def test_report_module_has_no_io_and_no_evaluation(self):
        from app import compatibility_report

        with open(compatibility_report.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for banned in (
            "subprocess",
            "urllib",
            "requests",
            "ModelStore",
            "evaluate_model_compatibility",
            "to_admission",
        ):
            self.assertNotIn(banned, source)

    def test_to_admission_keeps_its_fail_closed_contract(self):
        from app.evaluate_compatibility import to_admission

        self.assertEqual(to_admission(None).status, "blocked")
        self.assertIsNone(to_admission(None).verdict)

    def test_no_new_service_or_registry_module_was_added(self):
        from pathlib import Path

        banned = {
            "evaluation_service",
            "compatibility_manager",
            "diagnostic_registry",
            "evaluation_store",
            "policy_engine",
        }
        present = {p.stem for p in Path("app").glob("*.py")}
        self.assertEqual(present & banned, set())


if __name__ == "__main__":
    unittest.main()





