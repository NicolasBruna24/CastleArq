import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.execution import (
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionTarget,
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
                str(self.executable), "cli", "--model", str(self.model),
                "--device", "Vulkan0", "--prompt", self.request.prompt,
                "--single-turn",
            ],
        )
        self.assertIs(process.call_args.kwargs["shell"], False)
        self.assertNotIsInstance(argv, str)

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
        self.assertIn("none", process.call_args.args[0])

    def test_backend_without_capability_is_rejected(self):
        runner, process = self.make_runner()
        target = ExecutionTarget("llama.cpp CLI", "CUDA")
        result = runner.run(self.artifact, target, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.INVALID_REQUEST)
        process.assert_not_called()

    def test_success_and_process_failure(self):
        success_runner, _ = self.make_runner(Mock(returncode=0, stdout="o", stderr="e"))
        self.assertTrue(success_runner.run(self.artifact, self.target, self.request).success)
        failure_runner, _ = self.make_runner(
            Mock(returncode=2, stdout="o", stderr="bad")
        )
        result = failure_runner.run(self.artifact, self.target, self.request)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.code, ExecutionErrorCode.PROCESS_FAILED)

    def test_timeout_is_mapped(self):
        process = Mock(side_effect=__import__("subprocess").TimeoutExpired("llama", 1))
        result = LlamaCppRunner(self.capability, process).run(
            self.artifact, self.target, self.request
        )
        self.assertEqual(result.error.code, ExecutionErrorCode.TIMEOUT)

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
