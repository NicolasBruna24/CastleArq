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

"""Focused tests for SYCL runner dispatch in execute_model (A2.6.5.11-R1)."""

import unittest
from unittest.mock import patch, MagicMock

from castlearq.compatibility import CompatibilityResult, CompatibilityStatus
from castlearq.execution import ExecutionTarget, ExecutionResult
from castlearq.execute_model import execute_model, ExecutePreparationError
from castlearq.models import ModelSpec, ArtifactSpec
from castlearq.runtimes import RuntimeCapability, PromptInputMode
from castlearq.runner import ModelRunner, LlamaCppRunner
from castlearq.sycl_runner import SyclLlamaRunner


def _cap_syctl():
    return RuntimeCapability(
        name="llama.cpp SYCL", executable_path="/opt/llama-sycl", version="v",
        supported_formats=("GGUF",), supported_backends=("SYCL",),
        prompt_input_modes=(PromptInputMode.ARGUMENT,), supports_one_shot=True, available=True,
    )


def _cap_cpu():
    return RuntimeCapability(
        name="llama.cpp CLI", executable_path="/opt/llama", version="v",
        supported_formats=("GGUF",), supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,), supports_one_shot=True, available=True,
    )


def _compat(backend="SYCL"):
    return CompatibilityResult(
        model=ModelSpec(name="m1", supported_runtimes=("llama.cpp / llama.app",), supported_backends=("CPU", "Vulkan", "SYCL")),
        status=CompatibilityStatus.COMPATIBLE, score=50, reasons=(), warnings=(),
        estimated_memory_bytes=None, memory_is_estimate=True,
        recommended_quantization=None, recommended_runtime="llama.cpp / llama.app",
        recommended_backend=backend,
    )


def _artifact():
    return ArtifactSpec(model_id="m1", source="h", repository="r", filename="m.gguf", format="GGUF")


class _FakeRunner(ModelRunner):
    def __init__(self, result=None):
        self.result = result if result is not None else ExecutionResult(True, 0, "ok", "")
        self.calls = []

    def run(self, executable_artifact, target, request):
        self.calls.append((executable_artifact, target, request))
        return self.result
def _make_deps(target_backend="SYCL", runner=None, selector_target=None):
    from castlearq.execute_model import ExecuteModelDependencies

    if selector_target is None:
        selector_target = ExecutionTarget(runtime="llama.cpp SYCL", backend=target_backend)

    cap = _cap_syctl() if target_backend == "SYCL" else _cap_cpu()

    selector = MagicMock()
    selector.select.return_value = type("RS", (), {"target": selector_target, "warnings": ()})()

    compat = _compat(target_backend)

    preflight = MagicMock()
    preflight.validate.return_value = type("EA", (), {
        "artifact": _artifact(), "path": "/m/m.gguf",
        "size_verified": True, "checksum_verified": True,
    })()

    deps = ExecuteModelDependencies(
        model_store=MagicMock(),
        models=(ModelSpec(name="m1", supported_runtimes=("llama.cpp / llama.app",), supported_backends=("CPU", "Vulkan", "SYCL")),),
        capability_provider=lambda: cap,
        compatibility_provider=lambda model, capability: compat,
        preflight_factory=lambda store: preflight,
        selector=selector,
        runner=runner,
    )
    return deps, selector_target


    cap = _cap_syctl() if target_backend == "SYCL" else _cap_cpu()

    selector = MagicMock()
    selector.select.return_value = type("RS", (), {"target": selector_target, "warnings": ()})()

    compat = _compat(target_backend)

    preflight = MagicMock()
    preflight.validate.return_value = type("EA", (), {
        "artifact": _artifact(), "path": "/m/m.gguf",
        "size_verified": True, "checksum_verified": True,
    })()

    deps = ExecuteModelDependencies(
        model_store=MagicMock(),
        models=(ModelSpec(name="m1", supported_runtimes=("llama.cpp / llama.app",), supported_backends=("CPU", "Vulkan", "SYCL")),),
        capability_provider=lambda: cap,
        compatibility_provider=lambda model, capability: compat,
        preflight_factory=lambda store: preflight,
        selector=selector,
        runner=runner,
    )
    return deps, selector_target


class ExecuteModelRunnerDispatchTests(unittest.TestCase):
    def test_sycl_construye_sycl_runner(self):
        from unittest.mock import patch, MagicMock
        deps, target = _make_deps("SYCL", runner=None)
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            with patch("castlearq.execute_model.detect_sycl_llama_capability") as mock_detect:
                mock_detect.return_value = _cap_syctl()
                with patch("castlearq.sycl_runner.build_sycl_runner") as builder:
                    fake_runner = MagicMock(run=lambda ea, t, r: MagicMock(success=True, exit_code=0, stdout="ok", stderr="", warnings=(), error=None))
                    builder.return_value = fake_runner
                    result = execute_model("m1", "hello", backend_preference="SYCL",
                                          admission=MagicMock(status="evaluated", verdict="compatible"),
                                          dependencies=deps)
                    builder.assert_called_once()
                    self.assertTrue(result.success)

    def test_sycl_acepta_sycl_runner_inyectado(self):
        from unittest.mock import patch, MagicMock
        injected = SyclLlamaRunner(executable_path="/opt/llama-sycl", setvars_path="/opt/setvars.sh", env_provider=MagicMock())
        injected.run = MagicMock(return_value=MagicMock(success=True, exit_code=0, stdout="ok", stderr="", warnings=(), error=None))
        deps, target = _make_deps("SYCL", runner=injected)
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            with patch("castlearq.execute_model.detect_sycl_llama_capability") as mock_detect:
                mock_detect.return_value = _cap_syctl()
                result = execute_model("m1", "hello", backend_preference="SYCL",
                                      admission=MagicMock(status="evaluated", verdict="compatible"),
                                      dependencies=deps)
                self.assertTrue(injected.run.called)

    def test_sycl_rechaza_llama_cpp_inyectado(self):
        from unittest.mock import patch, MagicMock
        injected = LlamaCppRunner(_cap_cpu())
        deps, target = _make_deps("SYCL", runner=injected)
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            with patch("castlearq.execute_model.detect_sycl_llama_capability") as mock_detect:
                mock_detect.return_value = _cap_syctl()
                with self.assertRaises(ExecutePreparationError):
                    execute_model("m1", "hello", backend_preference="SYCL",
                                  admission=MagicMock(status="evaluated", verdict="compatible"),
                                  dependencies=deps)

    def test_sycl_rechaza_runner_incompatible(self):
        from unittest.mock import patch, MagicMock
        deps, target = _make_deps("SYCL", runner=MagicMock())
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            with patch("castlearq.execute_model.detect_sycl_llama_capability") as mock_detect:
                mock_detect.return_value = _cap_syctl()
                with self.assertRaises(ExecutePreparationError):
                    execute_model("m1", "hello", backend_preference="SYCL",
                                  admission=MagicMock(status="evaluated", verdict="compatible"),
                                  dependencies=deps)

    def test_cpu_vulkan_conservan_inyeccion(self):
        from unittest.mock import patch, MagicMock
        fake_runner = _FakeRunner(result=MagicMock(success=True, exit_code=0, stdout="ok", stderr="", warnings=(), error=None))
        deps, target = _make_deps("CPU", runner=fake_runner)
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            result = execute_model("m1", "hello", admission=MagicMock(status="evaluated", verdict="compatible"),
                                  dependencies=deps)
            self.assertTrue(result.success)
            self.assertTrue(len(fake_runner.calls) > 0)

    def test_backend_desconocido_error(self):
        from unittest.mock import patch, MagicMock
        deps, target = _make_deps("SYCL", runner=None)
        deps.selector.select.return_value = type("RS", (), {
            "target": ExecutionTarget(runtime="x", backend="UNKNOWN"), "warnings": ()
        })()
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver_cls:
            resolver_cls.return_value.resolve.return_value = MagicMock(model=deps.models[0], artifact=_artifact())
            with patch("castlearq.execute_model.detect_sycl_llama_capability") as mock_detect:
                mock_detect.return_value = _cap_syctl()
                with self.assertRaises(ExecutePreparationError):
                    execute_model("m1", "hello", backend_preference="SYCL",
                                  admission=MagicMock(status="evaluated", verdict="compatible"),
                                  dependencies=deps)


if __name__ == "__main__":
    unittest.main()

    pass
