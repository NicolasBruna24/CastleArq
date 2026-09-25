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

"""B9.50 public-surface contract tests, updated by B9.51.

B9.50 existed because B9.48 wrote ``serve read-only HTTP API`` into ``--help``
and the README while ``POST /v1/run`` performs real inference. Nothing tested
the claim, so it shipped. B9.50 also declared the serve/execute divergence a
*deliberate policy*; B9.51 (which closes B9.23 section 13 K-3) reversed that:

    the RATIFIED policy is that HTTP execution DOES share strict admission;
    the current implementation is a KNOWN, LABELLED transitional gap whose
    closure is deferred to B9.52.

The suite therefore pins four things that must agree with each other:

    CODE  <->  POLICY  <->  DOCUMENTATION  <->  RATIFIED CONTRACT

* :class:`ReadmeCommandReferenceTests` -- every command documented in the
  README exists in the CLI (and vice versa), without depending on line
  numbers.
* :class:`ServeIsNotReadOnlyTests` -- behavioural proof that ``serve``
  executes models, not a restatement of the README.
* :class:`ExecutionGatePolicyTests` -- the ratified policy (strict admission on
  HTTP) and, separately, the existence and labelling of the implementation
  gap, asserted against the real call graph and the real documentation.
* :class:`HttpAdmissionContractTests` -- the ratified HTTP contract itself
  (status mapping, rejection body, ``run_lock`` ordering), pinned against the
  decision document so B9.52 cannot implement a different contract silently.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from app.main import main

README = Path("README.md")
MAIN_PY = Path("app/main.py")
API_PY = Path("app/api.py")
DECISION_DOC = Path(
    "docs/B9.51-http-admission-contract-decision.md"
)

#: The B9.51 ratified policy: HTTP execution DOES share strict admission.
#: B9.50 set this to ``False`` and called the divergence deliberate; B9.51
#: reversed that judgement. The implementation still has the gap (see
#: :data:`HTTP_ADMISSION_IMPLEMENTED`), which is a deferred implementation,
#: not a second policy.
SERVE_USES_STRICT_ADMISSION = True

#: B9.51 ratified the contract and DEFERRED the implementation to B9.52.
#: While this is ``False`` the gap is expected; when it is flipped to ``True``
#: the gap assertions below must be inverted in the same commit, otherwise
#: this suite fails and the drift cannot pass silently.
HTTP_ADMISSION_IMPLEMENTED = False


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cli_choices() -> set[str]:
    """The command names the CLI actually accepts."""
    tree = ast.parse(_read(MAIN_PY))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "command"
        ):
            for keyword in node.keywords:
                if keyword.arg == "choices" and isinstance(
                    keyword.value, ast.Tuple
                ):
                    return {
                        element.value
                        for element in keyword.value.elts
                        if isinstance(element, ast.Constant)
                    }
    raise AssertionError("command choices tuple not found in app/main.py")


def _readme_commands() -> set[str]:
    """Command names documented in the README command-reference table.

    Parsed from the markdown table itself, so the test tracks the document
    instead of pinning line numbers.
    """
    text = _read(README)
    match = re.search(
        r"^##\s+Command reference\s*$(.*?)^##\s",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "README command reference section not found"
    section = match.group(1)
    names = set()
    for line in section.splitlines():
        # Rows look like:  | `command ARG` | description |
        # The command is the first token inside the first backticked span.
        row = re.match(r"^\|\s*`([a-z][a-z0-9]*)", line)
        if row:
            names.add(row.group(1))
    return names


def _help_text() -> str:
    """Render ``castlearq --help`` exactly as a user would see it."""
    import contextlib

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with patch.object(sys, "argv", ["castlearq", "--help"]):
            with contextlib.suppress(SystemExit):
                main()
    return stdout.getvalue()


class ReadmeCommandReferenceTests(unittest.TestCase):
    """B9.50 section 7: README and CLI must not drift apart."""

    def test_every_documented_command_exists_in_the_cli(self):
        documented = _readme_commands()
        self.assertTrue(documented, "no commands parsed from the README table")
        missing = documented - _cli_choices()
        self.assertEqual(
            missing,
            set(),
            f"README documents commands the CLI does not accept: {sorted(missing)}",
        )

    def test_every_cli_command_is_documented(self):
        undocumented = _cli_choices() - _readme_commands()
        self.assertEqual(
            undocumented,
            set(),
            f"CLI accepts commands the README does not document: {sorted(undocumented)}",
        )

    def test_readme_table_is_not_empty_and_covers_the_surface(self):
        self.assertGreaterEqual(len(_readme_commands()), len(_cli_choices()))


class ServeIsNotReadOnlyTests(unittest.TestCase):
    """B9.50 section 8: behavioural proof, not a restatement of the README."""

    def test_serve_rejects_non_loopback_hosts(self):
        """Network exposure property: loopback only, enforced at construction."""
        from app.api import APIConfigurationError, serve

        with self.assertRaises(APIConfigurationError):
            serve(host="0.0.0.0", port=0)

    def test_run_handler_calls_run_once(self):
        """``_handle_run`` must route to the shared execution service."""
        source = _read(API_PY)
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("_handle_run", functions)
        names = {
            child.id
            for child in ast.walk(functions["_handle_run"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("run_once", names)

    def test_api_module_does_not_expose_a_status_only_surface(self):
        """POST routes exist: the API is not read-only."""
        source = _read(API_PY)
        self.assertIn("do_POST", source)
        self.assertIn('path == "/v1/run"', source)

    def test_documentation_does_not_claim_serve_is_read_only(self):
        readme = _read(README)
        self.assertNotIn("API HTTP de solo lectura", readme)
        help_text = _help_text()
        self.assertNotIn("serve   read-only HTTP API", help_text)


class ExecutionGatePolicyTests(unittest.TestCase):
    """B9.51 §4: pin the ratified policy AND the labelled implementation gap.

    Ratified policy: ``serve`` execution DOES cross the strict admission gate,
    exactly like ``execute``. The implementation has not caught up yet; B9.51
    deferred it to B9.52. Both facts are asserted here so neither can drift
    alone: the policy cannot be quietly reverted to "deliberate legacy", and
    the gap cannot quietly become permanent.
    """

    def test_ratified_policy_is_strict_admission_on_http(self):
        self.assertTrue(
            SERVE_USES_STRICT_ADMISSION,
            "B9.51 ratified that HTTP execution shares strict admission. "
            "Reverting this requires a new ratified decision, not a code "
            "change; B9.50's Option B rationale was rejected on merit.",
        )

    def test_implementation_gap_is_still_open_and_labelled(self):
        """The gap is expected (B9.52 closes it) but must be explicit."""
        self.assertFalse(
            HTTP_ADMISSION_IMPLEMENTED,
            "HTTP admission is implemented. Flip the gap assertions in this "
            "class in the same commit: app/api.py must now consult the gate.",
        )
        source = _read(API_PY)
        for banned in (
            "evaluate_model_compatibility",
            "to_admission",
            "execute_model",
        ):
            self.assertNotIn(
                banned,
                source,
                f"app/api.py now references {banned}: the deferred B9.52 "
                "implementation landed, so HTTP_ADMISSION_IMPLEMENTED and "
                "the gap assertions in this class must be updated together",
            )

    def test_documentation_labels_the_gap_as_transitional(self):
        """A known gap must be named as a gap, not justified as a policy."""
        readme = _read(README)
        self.assertIn("brecha conocida y transitoria", readme)
        self.assertIn("B9.51", readme)
        help_text = _help_text()
        self.assertIn("Ratified policy (B9.51)", help_text)
        self.assertIn("Known transitional gap", help_text)
        self.assertIn("does NOT apply that admission", help_text)

    def test_documentation_states_the_ratified_contract(self):
        """The ratified mapping must be discoverable by a user of ``serve``."""
        readme = _read(README)
        for token in ("403", "500", "422", "503"):
            self.assertIn(token, readme)

    def test_execute_does_apply_strict_evaluation(self):
        """The contrast that makes the divergence meaningful."""
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        names = {
            child.id
            for child in ast.walk(functions["execute_command"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("evaluate_model_compatibility", names)
        self.assertIn("to_admission", names)

    def test_documentation_states_the_transitional_gap_in_both_languages(self):
        """B9.51: the divergence is documented as a gap, in README and --help."""
        readme = _read(README)
        self.assertIn("no aplica la", readme)
        self.assertIn("admisión por evaluación estricta", readme)
        self.assertIn("serve", readme)
        help_text = _help_text()
        self.assertIn("does NOT apply that admission", help_text)

    def test_documentation_separates_network_from_execution_policy(self):
        """B9.50 section 4: the two properties must not be conflated."""
        readme = _read(README)
        self.assertIn("exposición de red", readme)
        self.assertIn("política de ejecución", readme.lower())

    def test_evaluation_core_is_untouched_by_this_block(self):
        """B9.50 must not have modified the evaluation engine."""
        import subprocess

        for module in (
            "app/evaluate_compatibility.py",
            "app/evaluation_policy.py",
            "app/evaluation_pipeline.py",
            "app/compatibility_domain.py",
            "app/initial_knowledge.py",
        ):
            result = subprocess.run(
                ["git", "diff", "--name-only", "--", module],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.stdout.strip(),
                "",
                f"B9.50 must not modify {module}",
            )

    def test_model_store_is_untouched_by_this_block(self):
        import subprocess

        for module in ("app/model_store.py", "app/downloads/downloader.py"):
            result = subprocess.run(
                ["git", "diff", "--name-only", "--", module],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.stdout.strip(), "", f"B9.50 must not modify {module}"
            )


class HttpAdmissionContractTests(unittest.TestCase):
    """B9.51 §5/§8: the ratified contract itself must exist and be complete.

    B9.51 ratified the contract without implementing it. That is only safe if
    the contract is pinned: the mapping, the rejection body and the lock
    ordering have to be present and unambiguous, and B9.52 has to be able to
    detect that it implemented something else.
    """

    def test_decision_document_exists(self):
        self.assertTrue(
            DECISION_DOC.exists(),
            f"the ratified HTTP admission contract is missing: {DECISION_DOC}",
        )

    def test_decision_is_option_a_not_a_hedge(self):
        text = _read(DECISION_DOC)
        self.assertIn("Decision: OPTION A — HTTP uses strict admission.", text)
        for hedge in ("probably A", "probably OPTION A", "maybe A"):
            self.assertNotIn(hedge, text)

    def test_status_mapping_is_complete(self):
        """Every ratified case carries an explicit status code."""
        text = _read(DECISION_DOC)
        self.assertIn("### 5.2 Status mapping (ratified, complete)", text)
        for token in ("**400**", "**404**", "**409**", "**403**", "**422**",
                      "**500**", "**503**", "**200**"):
            self.assertIn(token, text, f"status mapping lacks {token}")

    def test_denial_and_evaluation_error_are_distinguished(self):
        """B9.48 P0-2 must survive the projection: an error is not a denial."""
        text = _read(DECISION_DOC)
        self.assertIn("500 for an evaluation error, not 403", text)
        self.assertIn("403 for denial, not 422", text)

    def test_rejection_body_exposes_only_the_admission_summary(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.3 Rejection body (ratified)", text)
        self.assertIn("only** what `EvaluationAdmission` already carries", text)
        for leaked in ("checks", "evidence", "traceback"):
            self.assertIn(leaked, text)
        self.assertIn("not** exposed over HTTP", text)

    def test_run_lock_semantics_are_ratified(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.4 `run_lock` (ratified)", text)
        for token in ("**before** evaluation", "**409**", "released in `finally`"):
            self.assertIn(token, text)

    def test_reuse_constraint_forbids_a_second_admission_implementation(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.5 Reuse", text)
        for banned in (
            "HttpEvaluationService",
            "HttpAdmissionManager",
            "ApiExecutionManager",
            "ExecutionPolicyV2",
            "ServePolicyEngine",
            "CompatibilityManager",
        ):
            self.assertIn(banned, text, f"reuse constraint omits {banned}")

    def test_backward_compatibility_is_documented_not_silent(self):
        text = _read(DECISION_DOC)
        self.assertIn("## 6. Backward Compatibility", text)
        self.assertIn("RunResponseDTO", text)
        self.assertIn("`GET /health`", text)

    def test_implementation_deferral_is_explicit(self):
        text = _read(DECISION_DOC)
        self.assertIn("DECISION RATIFIED", text)
        self.assertIn("IMPLEMENTATION DEFERRED TO B9.52", text)

    def test_evaluation_core_is_untouched_by_this_block(self):
        """B9.51 §9: a decision block must not redesign the engine."""
        import subprocess

        for module in (
            "app/evaluate_compatibility.py",
            "app/evaluation_policy.py",
            "app/evaluation_pipeline.py",
            "app/compatibility_domain.py",
            "app/initial_knowledge.py",
            "app/execute_model.py",
            "app/run_service.py",
        ):
            result = subprocess.run(
                ["git", "diff", "--name-only", "--", module],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.stdout.strip(),
                "",
                f"B9.51 must not modify {module}",
            )


class RunIsOutOfScopeTests(unittest.TestCase):
    """B9.51 §4: `run` keeps its ratified legacy policy (no cutover)."""

    def test_run_still_uses_the_legacy_path_without_evaluation(self):
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        names = {
            child.id
            for child in ast.walk(functions["run_model"])
            if isinstance(child, ast.Name)
        }
        self.assertNotIn("evaluate_model_compatibility", names)
        self.assertNotIn("execute_model", names)

    def test_run_is_not_an_alias_of_execute(self):
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("run_model", functions)
        self.assertIn("execute_command", functions)
        run_names = {
            child.id
            for child in ast.walk(functions["run_model"])
            if isinstance(child, ast.Name)
        }
        self.assertNotIn("execute_command", run_names)


if __name__ == "__main__":
    unittest.main()


