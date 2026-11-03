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

"""Focused tests for the unified SYCL runner dispatch (A2.6.5.11)."""

import os
import unittest
from unittest.mock import patch, MagicMock

from castlearq.execution import (
    ExecutableArtifact,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from castlearq.run_service import _select_runner, RunPreparationFailedError
from castlearq.runner import ModelRunner
from castlearq.runtimes import PromptInputMode, RuntimeCapability
from castlearq.sycl_runner import SyclLlamaRunner, build_sycl_runner


TARGET_CPU = ExecutionTarget(runtime="llama.cpp CLI", backend="CPU")
TARGET_VULKAN = ExecutionTarget(runtime="llama.cpp CLI", backend="Vulkan")
TARGET_SYCL = ExecutionTarget(runtime="llama.cpp SYCL", backend="SYCL")


def _capability(
    *,
    name="llama.cpp CLI",
    backends=("CPU", "Vulkan"),
    executable_path="/opt/llama",
    available=True,
):
    return RuntimeCapability(
        name=name,
        executable_path=executable_path,
        version="test",
        supported_formats=("GGUF",),
        supported_backends=backends,
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=available,
        available=available,
    )


class _FakeRunner(ModelRunner):
    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        return ExecutionResult(True, 0, "output", "")


class RunServiceRunnerDispatchTests(unittest.TestCase):
    def test_sycl_construye_sycl_runner(self):
        with patch("castlearq.sycl_runner.build_sycl_runner") as builder:
            builder.return_value = SyclLlamaRunner(
                "/sycl/llama", "/oneapi/setvars.sh"
            )
            capability = _capability(
                name="llama.cpp SYCL", backends=("SYCL",)
            )
            runner = _select_runner(
                capability, TARGET_SYCL, configured_runner=None
            )
            builder.assert_called_once()
            self.assertIs(runner, builder.return_value)

    def test_sycl_acepta_sycl_runner_inyectado(self):
        injected = SyclLlamaRunner(
            executable_path="/opt/llama-sycl", setvars_path="/opt/setvars.sh",
            env_provider=MagicMock(),
        )
        capability = _capability(name="llama.cpp SYCL", backends=("SYCL",))
        runner = _select_runner(
            capability, TARGET_SYCL, configured_runner=injected
        )
        self.assertIs(runner, injected)

    def test_sycl_rechaza_llama_cpp_inyectado(self):
        from castlearq.runner import LlamaCppRunner

        cap = _capability()
        injected = LlamaCppRunner(cap)
        sycl_capability = _capability(
            name="llama.cpp SYCL", backends=("SYCL",)
        )
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(
                sycl_capability, TARGET_SYCL, configured_runner=injected
            )

    def test_sycl_rechaza_runner_incompatible(self):
        injected = MagicMock()
        capability = _capability(name="llama.cpp SYCL", backends=("SYCL",))
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(
                capability, TARGET_SYCL, configured_runner=injected
            )

    def test_cpu_vulkan_conservan_inyeccion(self):
        injected = _FakeRunner()
        capability = _capability()
        self.assertIs(
            _select_runner(capability, TARGET_CPU, configured_runner=injected),
            injected,
        )
        self.assertIs(
            _select_runner(
                capability, TARGET_VULKAN, configured_runner=injected
            ),
            injected,
        )

    def test_backend_desconocido_error(self):
        target = ExecutionTarget(runtime="x", backend="CUDA")
        capability = _capability()
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(capability, target)


class BuildSyclRunnerTests(unittest.TestCase):
    def test_rechaza_capability_que_no_es_sycl(self):
        with self.assertRaises(ValueError):
            build_sycl_runner(_capability())
        with self.assertRaises(ValueError):
            build_sycl_runner(
                type(
                    "CapabilityLike",
                    (),
                    {"name": "llama.cpp SYCL", "supported_backends": ("SYCL",)},
                )()
            )

    def test_capability_executable_path_prioridad(self):
        cap = _capability(
            name="llama.cpp SYCL",
            backends=("SYCL",),
            executable_path="/cap/llama-sycl",
        )
        with patch.dict(os.environ, {"CASTLEARQ_SYCL_SETVARS": "/opt/setvars.sh"}, clear=False):
            with patch("castlearq.sycl_runner.SyclLlamaRunner") as cls:
                runner = build_sycl_runner(cap)
                cls.assert_called_once_with(
                    executable_path="/cap/llama-sycl",
                    setvars_path="/opt/setvars.sh",
                    runtime_version="test",
                )

    def test_env_var_fallback(self):
        cap = _capability(
            name="llama.cpp SYCL",
            backends=("SYCL",),
            executable_path=None,
            available=False,
        )
        with patch.dict(os.environ, {
            "CASTLEARQ_SYCL_RUNTIME": "/env/llama-sycl",
            "CASTLEARQ_SYCL_SETVARS": "/env/setvars.sh",
        }, clear=False):
            with patch("castlearq.sycl_runner.SyclLlamaRunner") as cls:
                runner = build_sycl_runner(cap)
                cls.assert_called_once_with(
                    executable_path="/env/llama-sycl",
                    setvars_path="/env/setvars.sh",
                    runtime_version="test",
                )

    def test_configuracion_ausente_error(self):
        cap = _capability(
            name="llama.cpp SYCL",
            backends=("SYCL",),
            executable_path=None,
            available=False,
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                build_sycl_runner(cap)

    def test_no_modifica_os_environ(self):
        cap = _capability(
            name="llama.cpp SYCL",
            backends=("SYCL",),
            executable_path="/cap/llama-sycl",
        )
        before = dict(os.environ)
        with patch.dict(os.environ, {"CASTLEARQ_SYCL_SETVARS": "/opt/setvars.sh"}, clear=False):
            with patch("castlearq.sycl_runner.SyclLlamaRunner"):
                build_sycl_runner(cap)
            # build_sycl_runner must not mutate os.environ beyond reading it
            self.assertEqual(os.environ.get("CASTLEARQ_SYCL_SETVARS"), "/opt/setvars.sh")
        # After the context exits, os.environ is restored (no pollution)
        self.assertEqual(os.environ.get("CASTLEARQ_SYCL_SETVARS"), before.get("CASTLEARQ_SYCL_SETVARS"))


if __name__ == "__main__":
    unittest.main()
