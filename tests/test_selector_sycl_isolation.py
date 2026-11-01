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

"""Isolated selector tests for the SYCL backend contract (A2.6.5.3, section 4).

These tests exercise ``RuntimeBackendSelector`` with hand-built
``RuntimeCapability`` / ``CompatibilityResult`` / ``ExecutableArtifact``
values. No runtime probe, subprocess, runner or service is involved, and no
production code is modified. They are a selector-level contract check; they
do not replace an integrated SYCL execution run (A2.6.5.3, section 5).

The selector itself has no hardcoded notion of SYCL. Its contract is
generic: it honours ``compatibility.recommended_backend`` when that backend
is present in ``capability.supported_backends`` and maps it to the matching
device argument through ``capability.backend_arguments``. That is exactly
what makes SYCL representable without changing domain types.
"""

import unittest

from castlearq.compatibility import CompatibilityResult, CompatibilityStatus
from castlearq.execution import ExecutableArtifact, ExecutionTarget
from castlearq.models import ArtifactSpec, ModelSpec
from castlearq.runtimes import PromptInputMode, RuntimeCapability
from castlearq.selection import (
    RuntimeBackendSelector,
    RuntimeSelectionError,
    SelectionErrorCode,
)

SELECTOR = RuntimeBackendSelector()

_CANNED_ARTIFACT = ArtifactSpec(
    model_id="deepseek/coder",
    source="huggingface",
    repository="owner/repository",
    filename="model.gguf",
    format="GGUF",
)


def _executable(format="GGUF"):
    return ExecutableArtifact(_CANNED_ARTIFACT, "/models/model.gguf", False, False)


def _compatibility(*, status=CompatibilityStatus.COMPATIBLE, runtime="llama.cpp / llama.app", backend="Vulkan"):
    return CompatibilityResult(
        model=ModelSpec(name="test"),
        status=status,
        score=60,
        reasons=(),
        warnings=(),
        estimated_memory_bytes=None,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime=runtime,
        recommended_backend=backend,
    )


def _capability(*, name="llama.cpp CLI", backends=("CPU", "Vulkan"), backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")), runtime_name="llama.cpp / llama.app"):
    return RuntimeCapability(
        name=name,
        executable_path="/opt/llama",
        version="0.4.0-dev",
        supported_formats=("GGUF",),
        supported_backends=backends,
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        backend_arguments=backend_arguments,
        compatibility_names=(runtime_name,),
    )


def _target(backend, *, backends=("CPU", "Vulkan"), backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")), runtime_name="llama.cpp / llama.app", status=CompatibilityStatus.COMPATIBLE):
    return SELECTOR.select(
        _compatibility(status=status, backend=backend),
        _capability(backends=backends, backend_arguments=backend_arguments, runtime_name=runtime_name),
        _executable(),
    ).target

class RuntimeBackendSelectorSyclIsolationTests(unittest.TestCase):
    def test_cpu_predeterminado_selects_cpu(self):
        target = _target("CPU")
        self.assertEqual(target.backend, "CPU")
        self.assertEqual(target.requested_backend, "CPU")
        self.assertEqual(target.requested_device_argument, "none")

    def test_cpu_explicit_selects_cpu(self):
        target = _target("CPU")
        self.assertEqual(target.backend, "CPU")
        self.assertEqual(target.requested_backend, "CPU")

    def test_vulkan_explicit_selects_vulkan(self):
        target = _target("Vulkan")
        self.assertEqual(target.backend, "Vulkan")
        self.assertEqual(target.requested_backend, "Vulkan")
        self.assertEqual(target.requested_device_argument, "Vulkan0")

    def test_sycl_explicit_y_disponible_selects_sycl0(self):
        target = _target("SYCL", backends=("SYCL",), backend_arguments=(("SYCL", "SYCL0"),))
        self.assertEqual(target.backend, "SYCL")
        self.assertEqual(target.requested_backend, "SYCL")
        self.assertEqual(target.requested_device_argument, "SYCL0")


    def test_sycl_explicit_con_runtime_name_llama_app(self):
        # A2.6.5.7.4: the SYCL capability must recognise the contractual
        # runtime name produced by assess_model ("llama.cpp / llama.app") so
        # the selector does not raise RUNTIME_MISMATCH.
        capability = _capability(
            backends=("SYCL",),
            backend_arguments=(("SYCL", "SYCL0"),),
            name="llama.cpp SYCL",
            runtime_name="llama.cpp / llama.app",
        )
        # Override compatibility_names to mirror the production SYCL capability.
        capability = RuntimeCapability(
            name=capability.name,
            executable_path=capability.executable_path,
            version=capability.version,
            supported_formats=capability.supported_formats,
            supported_backends=capability.supported_backends,
            prompt_input_modes=capability.prompt_input_modes,
            supports_one_shot=capability.supports_one_shot,
            available=capability.available,
            reason=capability.reason,
            compatibility_names=("llama.cpp / llama.app", "llama.cpp"),
            backend_arguments=capability.backend_arguments,
        )
        result = SELECTOR.select(
            _compatibility(
                status=CompatibilityStatus.COMPATIBLE,
                runtime="llama.cpp / llama.app",
                backend="SYCL",
            ),
            capability,
            _executable(),
        )
        self.assertEqual(result.target.backend, "SYCL")
        self.assertEqual(result.target.requested_device_argument, "SYCL0")

    def test_sycl_explicit_y_no_disponible_no_debe_fallar_a_cpu(self):
        with self.assertRaises(RuntimeSelectionError) as ctx:
            _target("SYCL", backends=("Vulkan",))
        self.assertEqual(ctx.exception.code, SelectionErrorCode.BACKEND_UNSUPPORTED)

    def test_sycl_zero_ausente_no_sustituye_el_argumento(self):
        target = _target("SYCL", backends=("SYCL",), backend_arguments=(("SYCL", None),))
        self.assertEqual(target.backend, "SYCL")
        self.assertEqual(target.requested_backend, "SYCL")
        self.assertIsNone(target.requested_device_argument)

    def test_backend_desconocido_lanza(self):
        with self.assertRaises(RuntimeSelectionError) as ctx:
            _target("CUDA", backends=("Vulkan",))
        self.assertEqual(ctx.exception.code, SelectionErrorCode.BACKEND_UNSUPPORTED)

    def test_ausencia_de_fallback_no_inventa_un_backend(self):
        target = _target("Vulkan")
        self.assertEqual(target.backend, "Vulkan")
        self.assertIsNotNone(target.requested_device_argument)

    def test_preserva_todos_los_campos_de_execution_target(self):
        target = _target("SYCL", backends=("SYCL",), backend_arguments=(("SYCL", "SYCL0"),))
        self.assertEqual(target.runtime, "llama.cpp CLI")
        self.assertEqual(target.backend, "SYCL")
        self.assertEqual(target.requested_backend, "SYCL")
        self.assertEqual(target.requested_device_argument, "SYCL0")
        self.assertIsInstance(target, ExecutionTarget)
        with self.assertRaises(AttributeError):
            target.runtime = "other"
        with self.assertRaises(AttributeError):
            target.backend = "CPU"
        with self.assertRaises(AttributeError):
            target.requested_backend = "Vulkan"

    def test_falla_cuando_no_hay_backend_solicitado(self):
        # "Sin backend solicitado" no es un valor default del selector; el
        # selector se niega a fabricar uno. La regla de ausencia de fallback
        # se cumple: no se sustituye por CPU.
        with self.assertRaises(RuntimeSelectionError) as ctx:
            _target(None)
        self.assertEqual(ctx.exception.code, SelectionErrorCode.BACKEND_UNSUPPORTED)

    def test_predeterminado_cpu_no_se_altera_por_sincronizacion_sycl(self):
        # Garantiza que la disponibilidad de SYCL no modifica ningún default:
        # un target CPU explícito sigue siendo CPU.
        capability = _capability(backends=("CPU", "SYCL"), backend_arguments=(("CPU", "none"), ("SYCL", "SYCL0"),))
        target = SELECTOR.select(_compatibility(backend="CPU"), capability, _executable()).target
        self.assertEqual(target.backend, "CPU")
        self.assertEqual(target.requested_device_argument, "none")

    def test_cpu_fallback_retenido_sin_cambios_funcionales(self):
        # El fallback explícito CPU sigue disponible; no es un cambio
        # funcional del selector en esta etapa.
        target = SELECTOR.select(
            _compatibility(backend="Vulkan"),
            _capability(backends=("CPU",)),
            _executable(),
            allow_cpu_fallback=True,
        )
        self.assertEqual(target.target.backend, "CPU")
        self.assertIn("Explicit CPU fallback", target.warnings[0])


if __name__ == "__main__":
    unittest.main()
