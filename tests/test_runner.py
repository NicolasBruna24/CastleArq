
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

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.execution import (
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionTarget,
    RuntimeMetricSource,
)
from app.models import ArtifactSpec, ArtifactState
from app.runner import LlamaCppRunner
from app.runtimes import PromptInputMode, RuntimeCapability


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.executable = root / "llama"
        self.executable.write_text("test executable")
        self.executable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        self.model = root / "model.gguf"
        self.model.write_bytes(b"model")
        self.spec = ArtifactSpec(
            model_id="model",
            source="huggingface",
            repository="owner/repo",
            filename="model.gguf",
            format="GGUF",
            state=ArtifactState.VERIFIED,
        )
        self.artifact = ExecutableArtifact(self.spec, self.model, False, False)
        self.capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path=str(self.executable),
            version="test",
            supported_formats=("GGUF",),
            supported_backends=("CPU", "Vulkan"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp / llama.app",),
            backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
        )
        self.target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        self.request = ExecutionRequest(self.spec, "hello; touch /tmp/pwned", self.target)

    def tearDown(self):
        self.tempdir.cleanup()

    def make_runner(self, completed=None):
        process = Mock(return_value=completed)
        return LlamaCppRunner(self.capability, process), process

    def test_builds_safe_vulkan_argv(self):
        completed = Mock(returncode=0, stdout="out", stderr="")
        runner, process = self.make_runner(completed)
        result = runner.run(self.artifact, self.target, self.request)
        self.assertTrue(result.success)
        argv = process.call_args.args[0]
        self.assertEqual(
            argv,
            [
                str(self.executable), "cli", "--simple-io", "--model", str(self.model),
                "--device", "Vulkan0", "--prompt", self.request.prompt,
                "--single-turn",
            ],
        )
        self.assertIs(process.call_args.kwargs["shell"], False)
        self.assertNotIsInstance(argv, str)
        self.assertEqual(
            argv[8],
            "hello; touch /tmp/pwned",
        )
        self.assertNotIn("--show-timings", argv)
        self.assertNotIn("--perf", argv)
        self.assertNotIn("--log-jsonl", argv)
        self.assertNotIn("--output", argv)

    def test_builds_cpu_argv_without_automatic_fallback(self):
        completed = Mock(returncode=0, stdout="", stderr="")
        runner, process = self.make_runner(completed)
        target = ExecutionTarget("llama.cpp CLI", "CPU")
        result = runner.run(
            self.artifact, target, ExecutionRequest(self.spec, "hello", target)
        )
        self.assertTrue(result.success)
        self.assertEqual(
            process.call_args.args[0][-3:],
            ["--prompt", "hello", "--single-turn"],
        )
        self.assertIn("--simple-io", process.call_args.args[0])
        self.assertIn("none", process.call_args.args[0])

    def test_backend_without_capability_is_rejected(self):
        runner, process = self.make_runner()
        target = ExecutionTarget("llama.cpp CLI", "CUDA")
        result = runner.run(self.artifact, target, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.INVALID_REQUEST)
        process.assert_not_called()

    def test_success_and_process_failure(self):
        success_runner, _ = self.make_runner(Mock(returncode=0, stdout=b"o", stderr=b"e"))
        success = success_runner.run(self.artifact, self.target, self.request)
        self.assertTrue(success.success)
        self.assertEqual(success.stdout, "o")
        self.assertEqual(success.diagnostics.stdout_bytes, 1)
        self.assertEqual(success.diagnostics.stderr_bytes, 1)
        self.assertEqual(success.diagnostics.exit_code, 0)
        self.assertFalse(success.diagnostics.timed_out)
        self.assertTrue(success.diagnostics.terminated_normally)
        self.assertGreaterEqual(success.diagnostics.elapsed_seconds, 0)
        self.assertLessEqual(
            success.diagnostics.started_at, success.diagnostics.finished_at
        )
        failure_runner, _ = self.make_runner(
            Mock(returncode=2, stdout=b"o", stderr=b"bad")
        )
        result = failure_runner.run(self.artifact, self.target, self.request)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.code, ExecutionErrorCode.PROCESS_FAILED)
        self.assertEqual(result.diagnostics.exit_code, 2)
        self.assertFalse(result.diagnostics.timed_out)
        self.assertTrue(result.diagnostics.terminated_normally)
        self.assertIsNone(result.runtime_metrics)

    def test_success_parses_runtime_metrics_from_stdout(self):
        completed = Mock(
            returncode=0,
            stdout=b"response\n[ Prompt: 100 t/s | Generation: 42 t/s ]\n",
            stderr=b"diagnostic",
        )
        runner, process = self.make_runner(completed)
        result = runner.run(self.artifact, self.target, self.request)

        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, completed.stdout.decode())
        self.assertEqual(result.stderr, "diagnostic")
        self.assertEqual(result.diagnostics.stdout_bytes, len(completed.stdout))
        self.assertTrue(result.diagnostics.terminated_normally)
        self.assertEqual(result.runtime_metrics.prompt_tokens_per_second, 100.0)
        self.assertEqual(result.runtime_metrics.generation_tokens_per_second, 42.0)
        self.assertEqual(
            result.runtime_metrics.source,
            RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
        )
        self.assertEqual(process.call_count, 1)

    def test_success_without_runtime_metrics_returns_none(self):
        runner, _ = self.make_runner(
            Mock(returncode=0, stdout=b"plain response", stderr=b"")
        )
        result = runner.run(self.artifact, self.target, self.request)
        self.assertTrue(result.success)
        self.assertIsNone(result.runtime_metrics)

    def test_metrics_are_parsed_only_from_stdout(self):
        runner, _ = self.make_runner(
            Mock(
                returncode=0,
                stdout=b"plain response",
                stderr=b"[ Prompt: 100 t/s | Generation: 42 t/s ]",
            )
        )
        result = runner.run(self.artifact, self.target, self.request)
        self.assertTrue(result.success)
        self.assertIsNone(result.runtime_metrics)

    def test_success_preserves_partial_runtime_metrics(self):
        runner, _ = self.make_runner(
            Mock(returncode=0, stdout=b"[ Prompt: 100 t/s | ]", stderr=b"")
        )
        result = runner.run(self.artifact, self.target, self.request)
        self.assertTrue(result.success)
        self.assertEqual(result.runtime_metrics.prompt_tokens_per_second, 100.0)
        self.assertIsNone(result.runtime_metrics.generation_tokens_per_second)

    def test_process_failure_remains_failure_with_runtime_metrics(self):
        runner, _ = self.make_runner(
            Mock(
                returncode=2,
                stdout=b"[ Prompt: 100 t/s | Generation: 42 t/s ]",
                stderr=b"bad",
            )
        )
        result = runner.run(self.artifact, self.target, self.request)
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, ExecutionErrorCode.PROCESS_FAILED)
        self.assertEqual(result.runtime_metrics.prompt_tokens_per_second, 100.0)
        self.assertEqual(result.runtime_metrics.generation_tokens_per_second, 42.0)

    def test_timeout_is_mapped(self):
        error = subprocess.TimeoutExpired(
            "llama", 1, output=b"out", stderr=b"err"
        )
        process = Mock(side_effect=error)
        result = LlamaCppRunner(self.capability, process).run(
            self.artifact, self.target, self.request
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.TIMEOUT)
        self.assertEqual(result.diagnostics.stdout_bytes, 3)
        self.assertEqual(result.diagnostics.stderr_bytes, 3)
        self.assertTrue(result.diagnostics.timed_out)
        self.assertFalse(result.diagnostics.terminated_normally)
        self.assertIsNone(result.diagnostics.exit_code)

    def test_invalid_timeout_is_rejected_before_subprocess(self):
        for timeout in (0, -1, float("nan"), float("inf"), True, "30"):
            with self.subTest(timeout=timeout):
                process = Mock()
                request = ExecutionRequest(
                    self.spec, "hello", self.target, timeout
                )
                result = LlamaCppRunner(self.capability, process).run(
                    self.artifact, self.target, request
                )
                self.assertEqual(result.error.code, ExecutionErrorCode.INVALID_REQUEST)
                process.assert_not_called()

    def test_empty_prompt_is_rejected_before_subprocess(self):
        process = Mock()
        request = ExecutionRequest(self.spec, "   ", self.target)
        result = LlamaCppRunner(self.capability, process).run(
            self.artifact, self.target, request
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.INVALID_REQUEST)
        process.assert_not_called()

    def test_missing_and_permission_errors_are_mapped(self):
        for error, code in (
            (FileNotFoundError("missing"), ExecutionErrorCode.EXECUTABLE_MISSING),
            (PermissionError("denied"), ExecutionErrorCode.PERMISSION_DENIED),
        ):
            process = Mock(side_effect=error)
            result = LlamaCppRunner(self.capability, process).run(
                self.artifact, self.target, self.request
            )
            self.assertEqual(result.error.code, code)

    def test_missing_capability_executable_is_rejected_before_launch(self):
        capability = RuntimeCapability(
            name=self.capability.name,
            executable_path=str(Path(self.tempdir.name) / "missing-llama"),
            version=self.capability.version,
            supported_formats=self.capability.supported_formats,
            supported_backends=self.capability.supported_backends,
            prompt_input_modes=self.capability.prompt_input_modes,
            supports_one_shot=True,
            available=True,
            compatibility_names=self.capability.compatibility_names,
            backend_arguments=self.capability.backend_arguments,
        )
        process = Mock()
        result = LlamaCppRunner(capability, process).run(
            self.artifact, self.target, self.request
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.EXECUTABLE_MISSING)
        process.assert_not_called()

    def test_request_cannot_supply_command_environment_or_executable(self):
        self.assertFalse(hasattr(ExecutionRequest, "command"))
        self.assertFalse(hasattr(ExecutionRequest, "environment"))
        self.assertFalse(hasattr(ExecutionRequest, "executable"))

    def test_artifact_mismatch_and_partial_are_rejected(self):
        runner, process = self.make_runner(Mock(returncode=0, stdout="", stderr=""))
        other = ArtifactSpec(
            model_id="other", source="huggingface", repository="owner/repo",
            filename="model.gguf", format="GGUF",
        )
        result = runner.run(
            ExecutableArtifact(other, self.model, False, False),
            self.target,
            self.request,
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.ARTIFACT_INVALID)
        process.assert_not_called()
        partial = self.model.with_name("model.gguf.part")
        partial.write_bytes(b"part")
        result = runner.run(
            ExecutableArtifact(self.spec, partial, False, False),
            self.target,
            self.request,
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.ARTIFACT_INVALID)

    def test_manifest_and_artifact_spec_state_are_unchanged(self):
        before = self.spec
        runner, _ = self.make_runner(Mock(returncode=0, stdout="", stderr=""))
        runner.run(self.artifact, self.target, self.request)
        self.assertEqual(self.spec, before)
        self.assertEqual(self.spec.state, ArtifactState.VERIFIED)

    def test_runner_is_single_synchronous_invocation(self):
        completed = Mock(returncode=0, stdout="", stderr="")
        runner, process = self.make_runner(completed)
        runner.run(self.artifact, self.target, self.request)
        self.assertEqual(process.call_count, 1)

    def test_environment_is_controlled(self):
        completed = Mock(returncode=0, stdout="", stderr="")
        runner, process = self.make_runner(completed)
        runner.run(self.artifact, self.target, self.request)
        environment = process.call_args.kwargs["env"]
        self.assertEqual(environment, {"PATH": os.defpath})
        for name in ("LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME"):
            self.assertNotIn(name, environment)


if __name__ == "__main__":
    unittest.main()
