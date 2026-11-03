# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SYCL capability-detection tests with environment and device probes mocked."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from castlearq.compatibility import CompatibilityResult, CompatibilityStatus
from castlearq.execution import ExecutableArtifact
from castlearq.models import ArtifactSpec, ModelSpec
from castlearq.runner_factory import create_runner
from castlearq.runtimes import (
    PromptInputMode,
    RuntimeCapability,
    detect_llama_capability,
    detect_sycl_llama_capability,
)
from castlearq.selection import RuntimeBackendSelector
from castlearq.sycl_environment import SyclEnvironmentError, SyclEnvironmentProvider
from castlearq.sycl_runner import SyclLlamaRunner


class SyclDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "PATH": "/oneapi/bin",
            "LD_LIBRARY_PATH": "/oneapi/lib",
            "ONEAPI_ROOT": "/oneapi",
        }

    def test_sycl_disponible(self):
        with patch.object(
            SyclEnvironmentProvider, "load", return_value=self.environment
        ), patch(
            "castlearq.runtimes.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="SYCL device"),
        ) as probe:
            capability = detect_sycl_llama_capability(
                "/opt/llama-sycl", "/oneapi/setvars.sh"
            )
        self.assertTrue(capability.invocable)
        self.assertEqual(capability.supported_backends, ("SYCL",))
        self.assertEqual(
            capability.prompt_input_modes, (PromptInputMode.ARGUMENT,)
        )
        self.assertTrue(
            capability.supports_runtime_name("llama.cpp / llama.app")
        )
        self.assertEqual(capability.backend_argument("SYCL"), "SYCL0")
        probe.assert_called_once_with(
            ["sycl-ls"],
            capture_output=True,
            text=True,
            timeout=5,
            env=self.environment,
            check=False,
        )
        compatibility = CompatibilityResult(
            model=ModelSpec(
                name="SYCL model",
                supported_runtimes=("llama.cpp / llama.app",),
                supported_backends=("SYCL",),
            ),
            status=CompatibilityStatus.COMPATIBLE,
            score=100,
            reasons=(),
            warnings=(),
            estimated_memory_bytes=None,
            memory_is_estimate=False,
            recommended_quantization=None,
            recommended_runtime="llama.cpp / llama.app",
            recommended_backend="SYCL",
        )
        artifact = ArtifactSpec(
            model_id="sycl-model",
            source="test",
            repository="test/repo",
            filename="model.gguf",
            format="GGUF",
        )
        executable = ExecutableArtifact(
            artifact=artifact,
            path="/models/model.gguf",
            size_verified=False,
            checksum_verified=False,
        )
        target = RuntimeBackendSelector().select(
            compatibility, capability, executable
        ).target
        runner = SyclLlamaRunner(
            "/opt/llama-sycl", "/oneapi/setvars.sh"
        )
        self.assertEqual(target.backend, "SYCL")
        self.assertIs(
            create_runner(capability, target, configured_runner=runner),
            runner,
        )

    def test_sycl_no_configurado(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            ValueError, "CASTLEARQ_SYCL_RUNTIME"
        ):
            detect_sycl_llama_capability()

    def test_runtime_environment_unavailable(self):
        with patch.object(
            SyclEnvironmentProvider,
            "load",
            side_effect=SyclEnvironmentError("setvars.sh is missing"),
        ):
            capability = detect_sycl_llama_capability(
                "/opt/llama-sycl", "/oneapi/setvars.sh"
            )
        self.assertFalse(capability.invocable)
        self.assertEqual(capability.supported_backends, ())
        self.assertIn("setvars.sh is missing", capability.reason)

    def test_sycl0_ausente(self):
        with patch.object(
            SyclEnvironmentProvider, "load", return_value=self.environment
        ), patch(
            "castlearq.runtimes.subprocess.run",
            return_value=SimpleNamespace(returncode=1, stdout=""),
        ):
            capability = detect_sycl_llama_capability(
                "/opt/llama-sycl", "/oneapi/setvars.sh"
            )
        self.assertFalse(capability.invocable)
        self.assertEqual(capability.supported_backends, ())
        self.assertIn("SYCL device not detected", capability.reason)

    def test_cpu_vulkan_capability_is_unchanged(self):
        capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/opt/llama",
            version="test",
            supported_formats=("GGUF",),
            supported_backends=("CPU", "Vulkan"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp / llama.app", "llama.cpp"),
            backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
        )
        with patch(
            "castlearq.runtimes._detect_llama_capability",
            return_value=capability,
        ):
            detected = detect_llama_capability(which=lambda _: "/opt/llama")
        self.assertIs(detected, capability)
        self.assertEqual(detected.supported_backends, ("CPU", "Vulkan"))


if __name__ == "__main__":
    unittest.main()
