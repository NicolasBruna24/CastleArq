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

"""B9.24 tests for the ``execute`` Product Caller (``app/main.py``).

Observable behavior of the thin caller only: registration, usage exit 2
before composition, one composition per invocation, argument forwarding with
``admission=None``, ``ExecutionResult`` projection, preparation-error
projection, and the structural boundary of the new flow (no infrastructure
introduced by ``main.py``). The internals of ``execute_model()`` stay covered
by ``tests/test_execute_model.py`` and are not duplicated here.
"""

from __future__ import annotations

import ast
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.execute_model import ExecuteAdmissionDeniedError, ExecutePreparationError
from app.execution import ExecutionErrorCode, ExecutionErrorInfo, ExecutionResult

USAGE = "Usage: python3 -m app.main execute <model-id> <prompt>"


def _execute_command_node():
    tree = ast.parse(
        Path("app/main.py").read_text(encoding="utf-8"), filename="app/main.py"
    )
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "execute_command":
            return node
    raise AssertionError("execute_command not found in app/main.py")


def _referenced_names(node):
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _run_cli(*argv):
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


def _invoke(model_id, prompt, *, result=None, error=None, **forward):
    """Call ``execute_command`` with both Application seams patched.

    Returns (code, out, err, compose_mock, execute_mock).
    """
    from app.main import execute_command

    deps = object()
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "app.main.compose_execute_model_dependencies", return_value=deps
    ) as compose, patch(
        "app.main.execute_model", return_value=result, side_effect=error
    ) as execute:
        code = execute_command(model_id, prompt, out=out, err=err, **forward)
    return code, out.getvalue(), err.getvalue(), compose, execute


def _success_result(*, stdout="model output\n", warnings=()):
    return ExecutionResult(True, 0, stdout, "", warnings=tuple(warnings))


def _failure_result(*, stderr="runtime exploded\n", message="process failed"):
    return ExecutionResult(
        False,
        1,
        "",
        stderr,
        error=ExecutionErrorInfo(ExecutionErrorCode.PROCESS_FAILED, message),
    )


class RegistrationTests(unittest.TestCase):
    """T1: the ``execute`` command is registered in the CLI."""

    def test_execute_is_listed_in_help_choices(self):
        code, out, _ = _run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("run,execute,chat", out)

    def test_execute_dispatch_reaches_execute_command(self):
        with patch("app.main.execute_command", return_value=0) as caller:
            code, _, _ = _run_cli("execute", "m1", "hello")
        self.assertEqual(code, 0)
        caller.assert_called_once_with(
            "m1", "hello", quantization=None, filename=None
        )


class UsageValidationTests(unittest.TestCase):
    """T2/T3: model_id and prompt are required, before any composition."""

    def test_missing_model_id_exits_two_without_composition(self):  # T2
        with patch("app.main.compose_execute_model_dependencies") as compose:
            code, out, err = _run_cli("execute")
        self.assertEqual(code, 2)
        self.assertIn(USAGE, err)
        self.assertEqual(out, "")
        compose.assert_not_called()

        code, out, err, compose, _ = _invoke(None, "hello")
        self.assertEqual(code, 2)
        self.assertIn(USAGE, err)
        compose.assert_not_called()

    def test_missing_prompt_exits_two_without_composition(self):  # T3
        with patch("app.main.compose_execute_model_dependencies") as compose:
            code, _, err = _run_cli("execute", "m1")
        self.assertEqual(code, 2)
        self.assertIn(USAGE, err)
        compose.assert_not_called()

        for prompt in (None, "", "   "):
            with self.subTest(prompt=prompt):
                code, _, err, compose, _ = _invoke("m1", prompt)
                self.assertEqual(code, 2)
                self.assertIn(USAGE, err)
                compose.assert_not_called()


class ApplicationCallTests(unittest.TestCase):
    """T4-T8: forwarding, admission=None, composition, dependency identity."""

    def _through_cli(self, *argv):
        with patch(
            "app.main.compose_execute_model_dependencies"
        ) as compose, patch(
            "app.main.execute_model", return_value=_success_result()
        ) as execute:
            from app.main import main

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(sys, "argv", ["castlearq", *argv]), patch.object(
                sys, "stdout", new=stdout
            ), patch.object(sys, "stderr", new=stderr):
                code = main()
        return code, stdout.getvalue(), stderr.getvalue(), compose, execute

    def test_quantization_is_forwarded(self):  # T4
        code, _, _, _, execute = self._through_cli(
            "execute", "m1", "hi", "--quantization", "Q4_K_M"
        )
        self.assertEqual(code, 0)
        self.assertEqual(execute.call_args.kwargs["quantization"], "Q4_K_M")

    def test_filename_is_forwarded(self):  # T5
        code, _, _, _, execute = self._through_cli(
            "execute", "m1", "hi", "--filename", "a.gguf"
        )
        self.assertEqual(code, 0)
        self.assertEqual(execute.call_args.kwargs["filename"], "a.gguf")

    def test_composition_runs_once_per_invocation(self):  # T6
        from app.main import main

        counts = []
        with patch(
            "app.main.compose_execute_model_dependencies"
        ) as compose, patch(
            "app.main.execute_model", return_value=_success_result()
        ):
            for _ in range(2):
                with patch.object(
                    sys, "argv", ["castlearq", "execute", "m1", "hi"]
                ), patch.object(sys, "stdout", new=io.StringIO()), patch.object(
                    sys, "stderr", new=io.StringIO()
                ):
                    self.assertEqual(main(), 0)
                counts.append(compose.call_count)
        # Exactly one composition per invocation; the second invocation
        # composes again (never cached across calls).
        self.assertEqual(counts, [1, 2])

    def test_admission_is_always_none(self):  # T7
        code, _, _, _, execute = self._through_cli("execute", "m1", "hi")
        self.assertEqual(code, 0)
        self.assertIsNone(execute.call_args.kwargs["admission"])

    def test_dependencies_are_the_composed_value(self):  # T8
        with patch(
            "app.main.compose_execute_model_dependencies"
        ) as compose, patch(
            "app.main.execute_model", return_value=_success_result()
        ) as execute:
            from app.main import execute_command

            code = execute_command(
                "m1", "hi", out=io.StringIO(), err=io.StringIO()
            )
        self.assertEqual(code, 0)
        self.assertIs(
            execute.call_args.kwargs["dependencies"], compose.return_value
        )
        # Contract: model_id and prompt arrive as keywords, selectors intact.
        self.assertEqual(execute.call_args.args, ())
        self.assertEqual(execute.call_args.kwargs["model_id"], "m1")
        self.assertEqual(execute.call_args.kwargs["prompt"], "hi")


class ExecutionResultProjectionTests(unittest.TestCase):
    """T9-T11: success, warnings and failure projection."""

    def test_success_writes_output_to_stdout_and_exits_zero(self):  # T9
        code, out, err, _, _ = _invoke(
            "m1", "hi", result=_success_result(stdout="the answer\n")
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "the answer\n")
        self.assertEqual(err, "")

    def test_success_warnings_are_written_to_stderr(self):  # T10
        code, out, err, _, _ = _invoke(
            "m1",
            "hi",
            result=_success_result(stdout="the answer\n", warnings=("low memory",)),
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "the answer\n")
        self.assertIn("Warning: low memory", err)

    def test_failure_exits_one_with_execute_error_on_stderr(self):  # T11
        code, out, err, _, _ = _invoke("m1", "hi", result=_failure_result())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("runtime exploded", err)
        self.assertIn("Execute error: process failed", err)


class PreparationErrorProjectionTests(unittest.TestCase):
    """T12: preparation/admission errors project; surprises propagate."""

    def test_preparation_error_exits_one_on_stderr(self):
        error = ExecutePreparationError(
            "Model compatibility does not permit execution",
            warnings=("marginal",),
        )
        code, out, err, _, _ = _invoke("m1", "hi", error=error)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn(
            "Execute error: Model compatibility does not permit execution", err
        )
        self.assertIn("Warning: marginal", err)

    def test_admission_denied_exits_one_on_stderr(self):
        error = ExecuteAdmissionDeniedError(
            "Execution denied by evaluation admission; deny-by-default applies"
        )
        code, out, err, _, _ = _invoke("m1", "hi", error=error)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Execute error: Execution denied", err)

    def test_unexpected_exception_propagates_unchanged(self):
        with self.assertRaises(RuntimeError):
            _invoke("m1", "hi", error=RuntimeError("unexpected defect"))

    def test_no_generic_exception_handler_in_the_caller(self):
        node = _execute_command_node()
        banned = {"Exception", "BaseException"}
        for child in ast.walk(node):
            if not isinstance(child, ast.ExceptHandler):
                continue
            self.assertIsNotNone(child.type, "bare except is forbidden")
            types = (
                child.type.elts if isinstance(child.type, ast.Tuple) else [child.type]
            )
            for exc_type in types:
                self.assertNotIn(getattr(exc_type, "id", None), banned)


class StructuralBoundaryTests(unittest.TestCase):
    """§12: main.py introduces no infrastructure for the new flow."""

    SOURCE = Path("app/main.py").read_text(encoding="utf-8")

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(cls.SOURCE, filename="app/main.py")
        cls.execute_command = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "execute_command"
        )

    def test_execute_command_references_only_the_application_boundary(self):
        names = _referenced_names(self.execute_command)
        # The new flow must reach the boundary...
        self.assertIn("compose_execute_model_dependencies", names)
        self.assertIn("execute_model", names)
        # ...and nothing from the infrastructure it must not coordinate.
        for banned in (
            "LlamaCppRunner",
            "ModelStore",
            "RuntimeBackendSelector",
            "ArtifactExecutionPreflight",
            "RuntimeCapability",
            "ModelArtifactResolver",
            "ExecutionRequest",
            "ExecuteModelDependencies",
            "detect_llama_capability",
            "detect_hardware",
            "subprocess",
            "_prepare",
        ):
            self.assertNotIn(banned, names)

    def test_execute_command_introduces_no_imports(self):
        imports = [
            child
            for child in ast.walk(self.execute_command)
            if isinstance(child, (ast.Import, ast.ImportFrom))
        ]
        self.assertEqual(imports, [], "the caller body must not import anything")

    def test_new_flow_module_imports_are_exactly_the_two_allowed_modules(self):
        received = {}
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in (
                "application_wiring",
                "execute_model",
            ):
                received[node.module] = {alias.name for alias in node.names}
        self.assertEqual(
            received,
            {
                "application_wiring": {"compose_execute_model_dependencies"},
                "execute_model": {
                    "ExecuteAdmissionDeniedError",
                    "ExecutePreparationError",
                    "execute_model",
                },
            },
        )

    def test_module_never_imports_subprocess(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotEqual(alias.name, "subprocess")
            elif isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "subprocess")

    def test_manual_resolution_and_detection_are_absent_from_the_caller(self):
        names = _referenced_names(self.execute_command)
        for banned in (
            "resolve",
            "save_manifest",
            "list_artifacts",
            "backend_argument",
            "validate_execution_request",
        ):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
