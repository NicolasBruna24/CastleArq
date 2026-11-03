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

"""Explicit backend selection tests through RuntimeBackendSelector."""

import unittest

from castlearq.compatibility import assess_model
from castlearq.execution import ExecutableArtifact
from castlearq.models import ArtifactSpec, ModelSpec
from castlearq.runtimes import (
    PromptInputMode,
    RuntimeCapability,
    RuntimeStatus,
)
from castlearq.selection import (
    RuntimeBackendSelector,
    RuntimeSelectionError,
    SelectionErrorCode,
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
    compatibility_names=("llama.cpp / llama.app", "llama.cpp"),
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


_ARTIFACT = ArtifactSpec(
    model_id="test",
    source="test",
    repository="test/repo",
    filename="model.gguf",
    format="GGUF",
)
_EXECUTABLE = ExecutableArtifact(
    artifact=_ARTIFACT,
    path="/models/model.gguf",
    size_verified=False,
    checksum_verified=False,
)


def _selection(requested_backend=None, capability=None):
    cap = capability or CPU_VULKAN
    runtimes = _runtimes(cap)
    backends = _backends_for(cap)
    compatibility = assess_model(_hardware(), runtimes, backends, MODEL)
    return RuntimeBackendSelector().select(
        compatibility,
        cap,
        _EXECUTABLE,
        requested_backend=requested_backend,
    )


class SyclExplicitRequestTests(unittest.TestCase):
    def test_solicitud_explicit_sycl_produce_sycl(self):
        capability = SYCL_CAPABILITY
        selection = _selection(requested_backend="SYCL", capability=capability)
        self.assertEqual(selection.target.backend, "SYCL")
        self.assertEqual(selection.target.runtime, "llama.cpp SYCL")
        self.assertEqual(selection.target.requested_device_argument, "SYCL0")


    def test_solicitud_cpu(self):
        selection = _selection(requested_backend="CPU")
        self.assertEqual(selection.target.backend, "CPU")

    def test_solicitud_vulkan(self):
        selection = _selection(requested_backend="Vulkan")
        self.assertEqual(selection.target.backend, "Vulkan")

    def test_ausencia_de_solicitud_conserva_default(self):
        # No request must keep the existing default behaviour.
        selection = _selection()
        # No request: keep the detection default (Vulkan in this lab),
        # never a SYCL substitution.
        self.assertEqual(selection.target.backend, "Vulkan")
        self.assertNotEqual(selection.target.backend, "SYCL")

    def test_sycl_solicitado_pero_no_disponible_diagnostico_explicito(self):
        # A request unsupported by the detected capability fails selection.
        with self.assertRaises(RuntimeSelectionError) as caught:
            _selection(requested_backend="SYCL", capability=CPU_VULKAN)
        self.assertIs(caught.exception.code, SelectionErrorCode.BACKEND_UNSUPPORTED)
        self.assertIn("not supported", caught.exception.message)

    def test_no_fallback_silencioso_a_cpu(self):
        # A SYCL request must not be turned into CPU when SYCL is unavailable.
        with self.assertRaises(RuntimeSelectionError) as caught:
            _selection(requested_backend="SYCL")
        self.assertIs(caught.exception.code, SelectionErrorCode.BACKEND_UNSUPPORTED)
        self.assertIn("not supported", caught.exception.message)

    def test_selector_puro_no_cambia(self):
        # Regression: RuntimeBackendSelector keeps its contract.
        from castlearq.selection import RuntimeBackendSelector

        selector = RuntimeBackendSelector()
        self.assertTrue(callable(getattr(selector, "select", None)))


if __name__ == "__main__":
    unittest.main()
