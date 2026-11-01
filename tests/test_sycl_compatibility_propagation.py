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

"""Propagation tests for an explicit SYCL backend request (A2.6.5.4, section 5).

These tests exercise :func:`castlearq.compatibility.assess_model` directly with
hand-built ``RuntimeCapability`` / ``RuntimeStatus`` / ``HardwareSnapshot`` values
(mocked). They verify that an explicit backend request is preserved and never
silently substituted by CPU/Vulkan, while the default (no request) keeps the
previous behaviour.
"""

import unittest

from castlearq.compatibility import (
    assess_model,
    CompatibilityResult,
    CompatibilityStatus,
)
from castlearq.execution import ExecutionTarget
from castlearq.models import ModelSpec
from castlearq.runtimes import (
    PromptInputMode,
    RuntimeCapability,
    RuntimeStatus,
)

CPU_VULKAN = RuntimeCapability(
    name="llama.cpp CLI",
    executable_path="/opt/llama",
    version="0.4.0-dev",
    supported_formats=("GGUF",),
    supported_backends=("CPU", "Vulkan"),
    prompt_input_modes=(PromptInputMode.ARGUMENT,),
    supports_one_shot=True,
    available=True,
    reason=None,
    compatibility_names=("llama.cpp / llama.app",),
)

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
    compatibility_names=("llama.cpp",),
    backend_arguments=(("SYCL", "SYCL0"),),
)

MODEL = ModelSpec(
    name="test",
    supported_backends=("CPU", "Vulkan", "SYCL"),
    supported_runtimes=("llama.cpp / llama.app",),
)


def _hardware() -> object:
    # Minimal object the recommend path touches; compatibility logic here only
    # needs a non-None value to avoid the memory/unknown path.
    return type(
        "HardwareSnapshot",
        (),
        {
            "operating_system": "linux",
            "architecture": "x86_64",
            "cpu": type("CPUInfo", (), {"model": "x86_64", "architecture": "x86_64", "cores": 8})(),
            "memory": type(
                "MemoryInfo", (), {"total_bytes": 1024 * 1024 * 1024}
            )(),
            "gpus": [],
        },
    )()


def _runtimes(capability: RuntimeCapability) -> list[RuntimeStatus]:
    return [
        RuntimeStatus(
            "llama.cpp / llama.app",
            installed=capability.executable_path is not None,
            available=capability.available,
            gpu_backend_detected=False,
            supported_backends=capability.supported_backends,
        )
    ]


def _backends_for(capability: RuntimeCapability | None = None) -> list:
    # Mirrors detect_backends(): Vulkan, OpenCL, SYCL, CUDA, ROCm, CPU.
    from castlearq.runtimes import BackendStatus

    return [
        BackendStatus("Vulkan", True),
        BackendStatus("OpenCL", False),
        BackendStatus(
            "SYCL", capability is not None and "SYCL" in capability.supported_backends
        ),
        BackendStatus("CUDA", False),
        BackendStatus("ROCm", False),
        BackendStatus("CPU", True),
    ]


def _result(requested_backend=None, capability=None):
    cap = capability or CPU_VULKAN
    runtimes = _runtimes(cap)
    backends = _backends_for(cap)
    return assess_model(_hardware(), runtimes, backends, MODEL, requested_backend=requested_backend)


class SyclExplicitRequestTests(unittest.TestCase):
    def test_solicitud_explicit_sycl_produce_sycl(self):
        capability = SYCL_CAPABILITY
        result = _result(requested_backend="SYCL", capability=capability)
        # Memory may be unknowable in this isolated model, but the request
        # itself must be honoured and never silently swapped to CPU/Vulkan.
        self.assertEqual(result.recommended_backend, "SYCL")
        self.assertEqual(result.recommended_runtime, "llama.cpp / llama.app")


    def test_solicitud_cpu(self):
        result = _result(requested_backend="CPU")
        self.assertEqual(result.recommended_backend, "CPU")

    def test_solicitud_vulkan(self):
        result = _result(requested_backend="Vulkan")
        self.assertEqual(result.recommended_backend, "Vulkan")

    def test_ausencia_de_solicitud_conserva_default(self):
        # No request must keep the existing default behaviour.
        result = _result()
        # No request: keep the detection default (Vulkan in this lab),
        # never a SYCL substitution.
        self.assertEqual(result.recommended_backend, "Vulkan")
        self.assertNotEqual(result.recommended_backend, "SYCL")

    def test_sycl_solicitado_pero_no_disponible_diagnostico_explicito(self):
        # SYCL requested, capability supports CPU+Vulkan only -> INCOMPATIBLE
        # with an explicit reason, never a silent swap to CPU.
        result = _result(requested_backend="SYCL", capability=CPU_VULKAN)
        self.assertEqual(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(result.recommended_backend, "SYCL")
        self.assertIn("not supported", str(result.reasons[0]))

    def test_no_fallback_silencioso_a_cpu(self):
        # A SYCL request must not be turned into CPU when SYCL is unavailable.
        result = _result(requested_backend="SYCL")
        self.assertEqual(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(result.recommended_backend, "SYCL")
        self.assertNotEqual(result.recommended_backend, "CPU")

    def test_selector_puro_no_cambia(self):
        # Regression: RuntimeBackendSelector keeps its contract.
        from castlearq.selection import RuntimeBackendSelector

        selector = RuntimeBackendSelector()
        self.assertTrue(callable(getattr(selector, "select", None)))


if __name__ == "__main__":
    unittest.main()
