# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Block 6.2-C: RunService preserves structured error semantics from the
# Execution domain (``ExecutionErrorCode`` / ``PreparationError.warnings``)
# internally, without changing any public HTTP/CLI contract.
from __future__ import annotations
import unittest
from types import SimpleNamespace
from unittest import mock

from castlearq.execution import (
    ExecutionErrorInfo,
    ExecutionErrorCode,
    ExecutionResult,
    ExecutionTarget,
)
from castlearq.run_service import (
    PreparationError,
    RunDependencies,
    RunExecutionFailedError,
    RunPreparationFailedError,
    run_once,
)
from castlearq.runner import ModelRunner
from castlearq.runtimes import PromptInputMode, RuntimeCapability


_TEST_CAPABILITY = RuntimeCapability(
    name="llama.cpp CLI",
    executable_path="/usr/bin/llama",
    version="test",
    supported_formats=("GGUF",),
    supported_backends=("CPU",),
    prompt_input_modes=(PromptInputMode.ARGUMENT,),
    supports_one_shot=True,
    available=True,
)


def _failed_result(code: ExecutionErrorCode, message: str) -> ExecutionResult:
    return ExecutionResult(
        success=False,
        exit_code=None,
        stdout="",
        stderr="",
        error=ExecutionErrorInfo(code, message),
    )


class _ResultRunner(ModelRunner):
    def __init__(self, result: ExecutionResult) -> None:
        self.result = result

    def run(self, executable_artifact, target, request):
        return self.result


class RunServiceErrorSemanticsTests(unittest.TestCase):
    """Block 6.2-C: structured error information survives RunService."""

    def _run_once_failure(self, *, runner_result=None, prepare_error=None):
        with mock.patch(
            "castlearq.run_service.ModelArtifactResolver"
        ) as resolver_cls, mock.patch(
            "castlearq.run_service.prepare"
        ) as prepare_mock:
            resolver_cls.return_value.resolve.return_value = SimpleNamespace(
                model=SimpleNamespace(model_id="m"),
                artifact=object(),
            )
            if prepare_error is not None:
                prepare_mock.side_effect = prepare_error
            else:
                prepare_mock.return_value = SimpleNamespace(
                    executable_artifact=object(),
                    target=ExecutionTarget("llama.cpp CLI", "CPU"),
                    compatibility_warnings=(),
                    selection_warnings=(),
                )
            deps = RunDependencies(
                capability=_TEST_CAPABILITY,
                runner=_ResultRunner(runner_result)
                if runner_result is not None
                else None
            )
            with self.assertRaises(BaseException) as ctx:
                run_once(
                    "m",
                    "prompt",
                    dependencies=deps,
                )
        return ctx.exception

    def test_backward_compatible_message_only_construction(self):
        execution_error = RunExecutionFailedError("boom")
        self.assertEqual(str(execution_error), "boom")
        self.assertIsNone(execution_error.error_code)
        preparation_error = RunPreparationFailedError("bad prep")
        self.assertEqual(str(preparation_error), "bad prep")
        self.assertEqual(preparation_error.warnings, ())

    def test_execution_error_code_preserved_timeout(self):
        error = self._run_once_failure(
            runner_result=_failed_result(
                ExecutionErrorCode.TIMEOUT, "Execution timed out"
            )
        )
        self.assertIsInstance(error, RunExecutionFailedError)
        self.assertEqual(str(error), "Execution timed out")
        self.assertEqual(error.error_code, ExecutionErrorCode.TIMEOUT)

    def test_execution_error_code_preserved_other_codes(self):
        for code in (
            ExecutionErrorCode.PROCESS_FAILED,
            ExecutionErrorCode.LAUNCH_FAILED,
            ExecutionErrorCode.EXECUTABLE_MISSING,
            ExecutionErrorCode.ARTIFACT_INVALID,
        ):
            with self.subTest(code=code):
                error = self._run_once_failure(
                    runner_result=_failed_result(code, "something failed")
                )
                self.assertIsInstance(error, RunExecutionFailedError)
                self.assertEqual(error.error_code, code)

    def test_execution_error_preserves_runtime_stderr(self):
        """B9.89 s16.2: a failed runtime's stderr crosses the boundary."""
        result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="runtime diagnostic\n",
            error=ExecutionErrorInfo(
                ExecutionErrorCode.PROCESS_FAILED, "process failed"
            ),
        )
        error = self._run_once_failure(runner_result=result)
        self.assertIsInstance(error, RunExecutionFailedError)
        self.assertEqual(error.stderr, result.stderr)
        # Defaulted when the runtime produced none (message-only construction).
        self.assertEqual(RunExecutionFailedError("boom").stderr, "")

    def test_preparation_warnings_preserved(self):
        error = self._run_once_failure(
            prepare_error=PreparationError(
                "incompatible",
                compatibility_warnings=("compat-a", "dup"),
                selection_warnings=("sel-a", "dup"),
            )
        )
        self.assertIsInstance(error, RunPreparationFailedError)
        # Exactly the deduplicated tuple PreparationError exposes — no
        # second dedup layer in run_service.
        self.assertEqual(error.warnings, PreparationError(
            "incompatible",
            compatibility_warnings=("compat-a", "dup"),
            selection_warnings=("sel-a", "dup"),
        ).warnings)
        self.assertIn("compat-a", error.warnings)
        self.assertIn("sel-a", error.warnings)
        self.assertEqual(str(error), "incompatible")

    def test_preparation_warnings_are_immutable_tuple(self):
        error = self._run_once_failure(
            prepare_error=PreparationError("bad", compatibility_warnings=("w",))
        )
        self.assertIsInstance(error.warnings, tuple)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
