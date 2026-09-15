
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

import unittest

from app.compatibility import (
    CompatibilityConfig,
    CompatibilityStatus,
    assess_model,
    estimate_memory_bytes,
    recommend_models,
)
from app.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from app.models import ModelSpec, Quantization
from app.runtimes import BackendStatus, RuntimeStatus


def hardware(vram_gib: int | None, ram_gib: int = 32) -> HardwareSnapshot:
    return HardwareSnapshot(
        "Test", "x86_64", CPUInfo("CPU", "x86_64"),
        MemoryInfo(ram_gib * 1024**3),
        [GPUInfo("Test GPU", "Intel", vram_bytes=vram_gib * 1024**3)]
        if vram_gib is not None else [],
    )


def model(parameters: float) -> ModelSpec:
    return ModelSpec(
        id="test", name="Test model", parameter_count_b=parameters,
        supported_runtimes=("llama.cpp / llama.app",),
        supported_backends=("Vulkan", "CPU"),
        quantizations=(
            Quantization("Q4", 4, 3),
            Quantization("Q8", 8, 6),
        ),
    )


RUNTIMES = [
    RuntimeStatus("llama.cpp / llama.app", True, True, True, ("Vulkan", "CPU"))
]
BACKENDS = [BackendStatus("Vulkan", True), BackendStatus("CPU", True)]


class CompatibilityTests(unittest.TestCase):
    def test_small_model_with_vram_is_compatible(self):
        result = assess_model(hardware(16), RUNTIMES, BACKENDS, model(7))
        self.assertEqual(result.status, CompatibilityStatus.COMPATIBLE)

    def test_large_model_with_little_memory_is_incompatible(self):
        result = assess_model(hardware(2, 4), RUNTIMES, BACKENDS, model(70))
        self.assertEqual(result.status, CompatibilityStatus.INCOMPATIBLE)

    def test_low_margin_is_marginal(self):
        result = assess_model(hardware(8, 32), RUNTIMES, BACKENDS, model(14))
        self.assertEqual(result.status, CompatibilityStatus.MARGINAL)

    def test_higher_quantization_requires_more_memory(self):
        config = CompatibilityConfig()
        self.assertGreater(
            estimate_memory_bytes(model(7), model(7).quantizations[1], config),
            estimate_memory_bytes(model(7), model(7).quantizations[0], config),
        )

    def test_unknown_vram_uses_known_ram_without_crashing(self):
        result = assess_model(hardware(None, 32), RUNTIMES, BACKENDS, model(7))
        self.assertEqual(result.status, CompatibilityStatus.MARGINAL)

    def test_zero_vram_is_not_unknown(self):
        result = assess_model(hardware(0, 4), RUNTIMES, BACKENDS, model(7))
        self.assertNotEqual(result.status, CompatibilityStatus.UNKNOWN)

    def test_multiple_gpus_are_not_combined(self):
        snapshot = HardwareSnapshot(
            "Test", "x86_64", CPUInfo("CPU", "x86_64"),
            MemoryInfo(16 * 1024**3),
            [
                GPUInfo("GPU 1", "Intel", vram_bytes=4 * 1024**3),
                GPUInfo("GPU 2", "Intel", vram_bytes=4 * 1024**3),
            ],
        )
        result = assess_model(snapshot, RUNTIMES, BACKENDS, model(8))
        self.assertEqual(result.status, CompatibilityStatus.MARGINAL)

    def test_cpu_requires_explicit_runtime_and_backend_support(self):
        cpu_runtime = [RuntimeStatus("llama.cpp / llama.app", True, True, False, ("CPU",))]
        result = assess_model(hardware(None, 32), cpu_runtime, [BackendStatus("CPU", True)], model(7))
        self.assertEqual(result.status, CompatibilityStatus.MARGINAL)

    def test_unknown_memory_metadata_is_unknown(self):
        result = assess_model(hardware(16), RUNTIMES, BACKENDS, ModelSpec(name="Incomplete"))
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)

    def test_backend_incompatible(self):
        result = assess_model(
            hardware(16), RUNTIMES, [BackendStatus("CUDA", True)], model(7)
        )
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)

    def test_unknown_runtime_backend_combination_is_not_selected(self):
        ollama_model = ModelSpec(
            name="Ollama model",
            parameter_count_b=7,
            supported_runtimes=("Ollama",),
            supported_backends=("Vulkan",),
            quantizations=model(7).quantizations,
        )
        result = assess_model(
            hardware(16), [RuntimeStatus("Ollama", True, True, False, ())],
            [BackendStatus("Vulkan", True)], ollama_model
        )
        self.assertEqual(result.status, CompatibilityStatus.UNKNOWN)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            CompatibilityConfig(safety_margin=0)
        with self.assertRaises(ValueError):
            CompatibilityConfig(ram_offload_factor=-1)
        with self.assertRaises(ValueError):
            CompatibilityConfig(model_overhead=0)

    def test_empty_catalog(self):
        self.assertEqual(recommend_models(hardware(16), RUNTIMES, BACKENDS, []), [])


if __name__ == "__main__":
    unittest.main()
