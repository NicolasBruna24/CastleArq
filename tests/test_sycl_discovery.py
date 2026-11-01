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

"""Discovery tests for the SYCL capability entry point (A2.6.5.4, section 5).

These tests exercise the SYCL discovery integration without running inference
or subprocess probes: they monkeypatch the probe layer and assert the
availability states and diagnostics that :func:`castlearq.runtimes
.detect_sycl_llama_capability` and :func:`discover_sycl_llama_runtime` expose.
"""

import unittest
import castlearq
from unittest.mock import patch

from castlearq.runtimes import (
    LlamaRuntimeIdentity,
    PromptInputMode,
    RuntimeAvailability,
    RuntimeCapability,
    ResolvedLlamaRuntime,
    detect_llama_capability,
    detect_sycl_llama_capability,
)

DISCOVER = "castlearq.runtimes.discover_sycl_llama_runtime"


SYCL_CAPABILITY = RuntimeCapability(
    name="llama.cpp SYCL",
    executable_path="/opt/llama-sycl",
    version="0.4.0-dev",
    supported_formats=("GGUF",),
    supported_backends=("SYCL",),
    prompt_input_modes=(PromptInputMode.ARGUMENT,),
    supports_one_shot=True,
    available=True,
    reason=None,
    compatibility_names=("llama.cpp / llama.app", "llama.cpp"),
    backend_arguments=(("SYCL", "SYCL0"),),
)


def _available_sycl_resolved() -> ResolvedLlamaRuntime:
    identity = LlamaRuntimeIdentity(
        "llama.cpp",
        "/opt/llama-sycl",
        "llama-sycl",
        "0.4.0-dev",
        "12345",
        RuntimeAvailability.AVAILABLE,
        None,
    )
    return ResolvedLlamaRuntime(identity, SYCL_CAPABILITY)


class SyclDiscoveryTests(unittest.TestCase):
        def test_sycl_disponible(self):
            with patch(
                "castlearq.runtimes.discover_sycl_llama_runtime",
                return_value=_available_sycl_resolved(),
            ):
                capability = detect_sycl_llama_capability()
            self.assertTrue(capability.available)
            self.assertEqual(capability.name, "llama.cpp SYCL")
            self.assertEqual(capability.executable_path, "/opt/llama-sycl")
            self.assertEqual(capability.supported_formats, ("GGUF",))
            self.assertEqual(capability.supported_backends, ("SYCL",))
            self.assertEqual(capability.backend_arguments, (("SYCL", "SYCL0"),))
            self.assertTrue(capability.supports_runtime_name("llama.cpp / llama.app"))
            self.assertTrue(capability.supports_runtime_name("llama.cpp"))
            self.assertIsNone(capability.reason)

        def test_sycl_no_configurado(self):
            with patch(
                "castlearq.runtimes.discover_sycl_llama_runtime",
                return_value=ResolvedLlamaRuntime(
                    LlamaRuntimeIdentity(
                        "llama.cpp", None, None, None, None,
                        RuntimeAvailability.NOT_FOUND,
                        "SYCL runtime path is not configured",
                    ),
                    None,
                ),
            ):
                capability = detect_sycl_llama_capability()
            self.assertFalse(capability.available)
            self.assertIsNone(capability.executable_path)
            self.assertEqual(capability.supported_backends, ())
            self.assertIn("not configured", capability.reason)

        def test_runtime_no_disponible(self):
            with patch(
                "castlearq.runtimes.discover_sycl_llama_runtime",
                return_value=ResolvedLlamaRuntime(
                    LlamaRuntimeIdentity(
                        "llama.cpp", "/opt/llama-sycl", "llama-sycl", None, None,
                        RuntimeAvailability.NOT_FOUND, "SYCL runtime does not exist",
                    ),
                    None,
                ),
            ):
                result = castlearq.runtimes.discover_sycl_llama_runtime(executable_path="/opt/llama-sycl")
            self.assertEqual(result.identity.availability, RuntimeAvailability.NOT_FOUND)
            self.assertIsNone(result.capability)

        def test_sycl0_ausente(self):
            with patch(
                "castlearq.runtimes.discover_sycl_llama_runtime",
                return_value=ResolvedLlamaRuntime(
                    LlamaRuntimeIdentity(
                        "llama.cpp", "/opt/llama-sycl", "llama-sycl", None, None,
                        RuntimeAvailability.FOUND_UNUSABLE,
                        "SYCL0 device is not available",
                    ),
                    None,
                ),
            ):
                result = castlearq.runtimes.discover_sycl_llama_runtime(executable_path="/opt/llama-sycl")
            self.assertEqual(result.identity.availability, RuntimeAvailability.FOUND_UNUSABLE)
            self.assertIsNone(result.capability)
            self.assertIn("SYCL0 device is not available", result.identity.reason)

        def test_cpu_vulkan_preserved(self):
            # The SYCL entry point must not disturb CPU/Vulkan discovery.
            capability = detect_llama_capability()
            self.assertEqual(capability.name, "llama.cpp CLI")
            self.assertIn("CPU", capability.supported_backends)
            self.assertIn("Vulkan", capability.supported_backends)


if __name__ == "__main__":
    unittest.main()
