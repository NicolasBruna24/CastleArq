
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

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.compatibility import (
    CompatibilityConfig,
    CompatibilityStatus,
    assess_model,
)
from app.downloads import ArtifactFilesystemState
from app.execution import (
    ArtifactExecutionPreflight,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from app.execution_service import ModelExecutionService
from app.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from app.model_catalog import get_catalog
from app.model_store import ModelStore
from app.models import ArtifactSpec, ArtifactState, ModelSpec
from app.runner import ModelRunner
from app.runtimes import (
    BackendStatus,
    PromptInputMode,
    RuntimeCapability,
    RuntimeStatus,
)
from app.selection import RuntimeBackendSelector


class FakeModelRunner(ModelRunner):
    def __init__(self, result: ExecutionResult) -> None:
        self.result = result
        self.calls: list[tuple[ExecutableArtifact, ExecutionTarget, ExecutionRequest]] = []

    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        self.calls.append((executable_artifact, target, request))
        return self.result


class ExecutionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ModelStore(Path(self.tempdir.name) / "models")
        self.model = get_catalog()[0]
        self.artifact = ArtifactSpec(
            model_id=self.model.model_id,
            source="huggingface",
            repository="owner/repository",
            filename="model.Q4_K_M.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        )
        manifest = self.store.save_manifest(self.artifact)
        self.artifact_path = manifest.parent / self.artifact.filename
        self.content = b"synthetic GGUF integration artifact"
        self.artifact_path.write_bytes(self.content)
        self.artifact = ArtifactSpec(
            **{
                **self.artifact.__dict__,
                "size_bytes": len(self.content),
                "sha256": hashlib.sha256(self.content).hexdigest(),
                "state": ArtifactState.DOWNLOADED,
            }
        )
        # The manifest remains the original fixture metadata; preflight uses
        # the immutable ArtifactSpec supplied by the application.
        self.request = ExecutionRequest(self.artifact, "integration prompt")
        self.capability = self._capability(("CPU", "Vulkan"))
        self.runner = FakeModelRunner(ExecutionResult(True, 0, "fake output", ""))
        self.preflight = ArtifactExecutionPreflight(self.store)
        self.selector = RuntimeBackendSelector()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _capability(self, backends: tuple[str, ...]) -> RuntimeCapability:
        arguments = tuple(
            (backend, "Vulkan0" if backend == "Vulkan" else "none")
            for backend in backends
        )
        return RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/test-only/llama",
            version="test",
            supported_formats=("GGUF",),
            supported_backends=backends,
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp / llama.app",),
            backend_arguments=arguments,
        )

    def _hardware(self, *, vram: int | None, ram: int) -> HardwareSnapshot:
        gpus = (
            [
                GPUInfo(
                    name="Test Vulkan GPU",
                    vendor="Test",
                    vram_bytes=vram,
                    vram_available_bytes=vram,
                    backends=["Vulkan"],
                )
            ]
            if vram is not None
            else []
        )
        return HardwareSnapshot(
            operating_system="test",
            architecture="x86_64",
            cpu=CPUInfo(model="test"),
            memory=MemoryInfo(total_bytes=ram),
            gpus=gpus,
        )

    def _service(self, hardware: HardwareSnapshot, capability=None, runner=None):
        runtimes = [
            RuntimeStatus(
                "llama.cpp / llama.app",
                installed=True,
                available=True,
                gpu_backend_detected=bool(hardware.gpus),
                supported_backends=("Vulkan", "CPU"),
            )
        ]
        backends = [
            BackendStatus("Vulkan", bool(hardware.gpus)),
            BackendStatus("CPU", True),
        ]
        evaluator = lambda model: assess_model(
            hardware,
            runtimes,
            backends,
            model,
            config=CompatibilityConfig(),
        )
        return ModelExecutionService(
            evaluator,
            self.preflight,
            self.selector,
            capability or self.capability,
            runner or self.runner,
        )

    def test_real_end_to_end_pipeline_uses_fake_runner(self):
        service = self._service(self._hardware(vram=32 * 1024**3, ram=48 * 1024**3))
        manifest_before = (self.artifact_path.parent / "manifest.json").read_bytes()
        result = service.execute(self.model, self.artifact, self.request)

        self.assertTrue(result.success)
        self.assertEqual(result.stdout, "fake output")
        self.assertEqual(len(self.runner.calls), 1)
        executable, target, request = self.runner.calls[0]
        self.assertEqual(executable.artifact, self.artifact)
        self.assertEqual(executable.path, self.artifact_path)
        self.assertTrue(executable.size_verified)
        self.assertTrue(executable.checksum_verified)
        self.assertEqual(target, ExecutionTarget("llama.cpp CLI", "Vulkan"))
        self.assertEqual(request, self.request)
        self.assertEqual(
            self.preflight.inspector.inspect(self.artifact).state,
            ArtifactFilesystemState.FINAL_EXISTS,
        )
        self.assertEqual(
            (self.artifact_path.parent / "manifest.json").read_bytes(),
            manifest_before,
        )

    def test_marginal_compatibility_warning_is_preserved(self):
        runner = FakeModelRunner(ExecutionResult(True, 0, "ok", ""))
        service = self._service(
            self._hardware(vram=None, ram=64 * 1024**3),
            capability=self._capability(("CPU",)),
            runner=runner,
        )
        result = service.execute(self.model, self.artifact, self.request)
        self.assertTrue(result.success)
        self.assertTrue(any("RAM" in warning for warning in result.warnings))
        self.assertEqual(runner.calls[0][1].backend, "CPU")

    def test_incompatible_compatibility_stops_pipeline(self):
        service = self._service(self._hardware(vram=1, ram=1))
        result = service.execute(self.model, self.artifact, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.COMPATIBILITY_REJECTED)
        self.assertEqual(self.runner.calls, [])

    def test_unknown_compatibility_stops_pipeline(self):
        service = self._service(self._hardware(vram=None, ram=0))
        result = service.execute(self.model, self.artifact, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.COMPATIBILITY_REJECTED)
        self.assertEqual(self.runner.calls, [])

    def test_invalid_preflight_stops_pipeline(self):
        self.artifact_path.unlink()
        service = self._service(self._hardware(vram=32 * 1024**3, ram=48 * 1024**3))
        result = service.execute(self.model, self.artifact, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.PREFLIGHT_FAILED)
        self.assertEqual(self.runner.calls, [])

    def test_selection_failure_stops_pipeline(self):
        service = self._service(
            self._hardware(vram=32 * 1024**3, ram=48 * 1024**3),
            capability=self._capability(("CPU",)),
        )
        result = service.execute(self.model, self.artifact, self.request)
        self.assertEqual(result.error.code, ExecutionErrorCode.SELECTION_FAILED)
        self.assertEqual(self.runner.calls, [])

    def test_integration_does_not_execute_subprocess(self):
        service = self._service(self._hardware(vram=32 * 1024**3, ram=48 * 1024**3))
        with patch("subprocess.run") as run:
            service.execute(self.model, self.artifact, self.request)
        run.assert_not_called()

    def test_artifact_spec_and_state_remain_unchanged(self):
        before = self.artifact
        state = self.artifact.state
        service = self._service(self._hardware(vram=32 * 1024**3, ram=48 * 1024**3))
        service.execute(self.model, self.artifact, self.request)
        self.assertEqual(self.artifact, before)
        self.assertEqual(self.artifact.state, state)


if __name__ == "__main__":
    unittest.main()
