
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

from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execution import ExecutableArtifact, ExecutionTarget
from app.models import ArtifactSpec, ModelSpec
from app.runtimes import (
    PromptInputMode,
    RuntimeCapability,
)
from app.selection import (
    RuntimeBackendSelector,
    RuntimeSelectionError,
    SelectionErrorCode,
)


def artifact(format="GGUF"):
    return ArtifactSpec(
        model_id="qwen/coder",
        source="huggingface",
        repository="owner/repository",
        filename="model.gguf",
        format=format,
    )


def capability(**overrides):
    values = {
        "name": "llama.cpp CLI",
        "executable_path": "/opt/llama",
        "version": "test",
        "supported_formats": ("GGUF",),
        "supported_backends": ("CPU", "Vulkan"),
        "prompt_input_modes": (PromptInputMode.ARGUMENT,),
        "supports_one_shot": True,
        "available": True,
        "compatibility_names": ("llama.cpp / llama.app",),
    }
    values.update(overrides)
    return RuntimeCapability(**values)


def compatibility(
    status=CompatibilityStatus.COMPATIBLE,
    runtime="llama.cpp / llama.app",
    backend="Vulkan",
):
    return CompatibilityResult(
        model=ModelSpec(name="test"),
        status=status,
        score=50,
        reasons=("reason",),
        warnings=(),
        estimated_memory_bytes=None,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime=runtime,
        recommended_backend=backend,
    )


def executable(format="GGUF"):
    return ExecutableArtifact(artifact(format=format), "/models/model.gguf", False, False)


class RuntimeBackendSelectorTests(unittest.TestCase):
    def setUp(self):
        self.selector = RuntimeBackendSelector()

    def test_compatible_supported_backend_selects_target(self):
        result = self.selector.select(compatibility(), capability(), executable())
        self.assertEqual(result.target, ExecutionTarget("llama.cpp CLI", "Vulkan"))
        self.assertEqual(result.warnings, ())

    def test_marginal_selection_reports_warning(self):
        result = self.selector.select(
            compatibility(CompatibilityStatus.MARGINAL), capability(), executable()
        )
        self.assertTrue(result.warnings)

    def test_incompatible_is_rejected(self):
        with self.assertRaisesRegex(RuntimeSelectionError, "incompatible"):
            self.selector.select(
                compatibility(CompatibilityStatus.INCOMPATIBLE),
                capability(),
                executable(),
            )

    def test_unknown_is_rejected(self):
        with self.assertRaises(RuntimeSelectionError) as context:
            self.selector.select(
                compatibility(CompatibilityStatus.UNKNOWN), capability(), executable()
            )
        self.assertEqual(context.exception.code, SelectionErrorCode.UNKNOWN_COMPATIBILITY)

    def test_unavailable_runtime_is_rejected(self):
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(
                compatibility(),
                capability(available=False, executable_path=None),
                executable(),
            )

    def test_incomplete_capability_is_rejected(self):
        incomplete = capability(supports_one_shot=False, available=False)
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(compatibility(), incomplete, executable())

    def test_unsupported_format_is_rejected(self):
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(compatibility(), capability(), executable("ONNX"))

    def test_unsupported_backend_is_rejected(self):
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(
                compatibility(backend="CUDA"), capability(), executable()
            )

    def test_cpu_recommendation_selects_cpu(self):
        result = self.selector.select(
            compatibility(backend="CPU"), capability(), executable()
        )
        self.assertEqual(result.target.backend, "CPU")

    def test_gpu_recommendation_does_not_silently_switch_to_cpu(self):
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(
                compatibility(backend="Vulkan"),
                capability(supported_backends=("CPU",)),
                executable(),
            )

    def test_explicit_cpu_fallback_is_reported(self):
        result = self.selector.select(
            compatibility(backend="Vulkan"),
            capability(supported_backends=("CPU",)),
            executable(),
            allow_cpu_fallback=True,
        )
        self.assertEqual(result.target.backend, "CPU")
        self.assertIn("Explicit CPU fallback", result.warnings[0])

    def test_runtime_name_mismatch_is_rejected(self):
        with self.assertRaises(RuntimeSelectionError):
            self.selector.select(
                compatibility(runtime="Ollama"), capability(), executable()
            )

    def test_types_are_immutable(self):
        result = self.selector.select(compatibility(), capability(), executable())
        with self.assertRaises(AttributeError):
            result.target.backend = "CPU"

    def test_selector_does_not_accept_process_configuration(self):
        self.assertFalse(hasattr(ExecutionTarget, "executable_path"))
        self.assertFalse(hasattr(ExecutionTarget, "command"))
        self.assertFalse(hasattr(ExecutionTarget, "environment"))

    def test_inputs_are_not_mutated(self):
        compatible = compatibility()
        runtime = capability()
        artifact_value = executable()
        self.selector.select(compatible, runtime, artifact_value)
        self.assertEqual(compatible.recommended_backend, "Vulkan")
        self.assertEqual(runtime.name, "llama.cpp CLI")
        self.assertEqual(artifact_value.artifact.format, "GGUF")


if __name__ == "__main__":
    unittest.main()
