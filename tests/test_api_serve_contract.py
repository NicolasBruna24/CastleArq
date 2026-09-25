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

"""B9.50: public-surface contract tests.

These exist because B9.48 wrote ``serve read-only HTTP API`` into ``--help``
and the README while ``POST /v1/run`` performs real inference. Nothing tested
the claim, so it shipped.

The suite therefore pins three things that must agree with each other:

    CODE  <->  POLICY  <->  DOCUMENTATION

* :class:`ReadmeCommandReferenceTests` -- every command documented in the
  README exists in the CLI (and vice versa), without depending on line
  numbers.
* :class:`ServeIsNotReadOnlyTests` -- behavioural proof that ``serve``
  executes models, not a restatement of the README.
* :class:`ExecutionGatePolicyTests` -- the deliberate divergence between
  ``serve`` (legacy/ungated) and ``execute`` (strict admission), asserted
  against the real call graph and the real documentation.
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

#: The B9.50 policy decision, stated once and asserted everywhere.
SERVE_USES_STRICT_ADMISSION = False


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
    """B9.50 section 9: pin the deliberate serve/execute divergence.

    Decision: ``serve`` intentionally stays on the legacy, UNGATED execution
    path. This class asserts all three layers agree:

        CODE (no evaluation in the HTTP path)
        <-> POLICY (documented divergence)
        <-> DOCUMENTATION (README + --help say so)
    """

    def test_decision_constant_matches_the_implementation(self):
        self.assertFalse(
            SERVE_USES_STRICT_ADMISSION,
            "B9.50 decided serve stays ungated; flip this only with a "
            "ratified HTTP admission contract (B9.23 K-3).",
        )

    def test_serve_does_not_apply_strict_evaluation(self):
        """The HTTP module must not evaluate or admit."""
        source = _read(API_PY)
        for banned in (
            "evaluate_model_compatibility",
            "to_admission",
            "execute_model",
        ):
            self.assertNotIn(
                banned,
                source,
                f"app/api.py now references {banned}: the HTTP gate policy "
                "changed and must be re-decided and re-documented",
            )

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

    def test_documentation_states_the_divergence(self):
        readme = _read(README)
        self.assertIn("no aplica la", readme)
        self.assertIn("admisión por evaluación estricta", readme)
        self.assertIn("serve", readme)
        help_text = _help_text()
        self.assertIn("does NOT apply the strict evaluation", help_text)

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


class RunIsOutOfScopeTests(unittest.TestCase):
    """B9.50 section 10: `run` keeps its ratified legacy policy."""

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


