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

from castlearq.execution import ExecutionTarget
from castlearq.run_service import _select_runner, RunPreparationFailedError
from castlearq.sycl_runner import SyclLlamaRunner, build_sycl_runner


TARGET_CPU = ExecutionTarget(runtime="llama.cpp CLI", backend="CPU")
TARGET_VULKAN = ExecutionTarget(runtime="llama.cpp CLI", backend="Vulkan")
TARGET_SYCL = ExecutionTarget(runtime="llama.cpp SYCL", backend="SYCL")


class RunServiceRunnerDispatchTests(unittest.TestCase):
    def test_sycl_construye_sycl_runner(self):
        with patch("castlearq.sycl_runner.build_sycl_runner") as builder:
            builder.return_value = MagicMock(spec=SyclLlamaRunner)
            runner = _select_runner(object(), TARGET_SYCL, configured_runner=None)
            builder.assert_called_once()
            self.assertIs(runner, builder.return_value)

    def test_sycl_acepta_sycl_runner_inyectado(self):
        injected = SyclLlamaRunner(
            executable_path="/opt/llama-sycl", setvars_path="/opt/setvars.sh",
            env_provider=MagicMock(),
        )
        runner = _select_runner(object(), TARGET_SYCL, configured_runner=injected)
        self.assertIs(runner, injected)

    def test_sycl_rechaza_llama_cpp_inyectado(self):
        from castlearq.runner import LlamaCppRunner
        from castlearq.runtimes import PromptInputMode, RuntimeCapability

        cap = RuntimeCapability(
            name="llama.cpp CLI", executable_path="/opt/llama", version="v",
            supported_formats=("GGUF",), supported_backends=("CPU", "Vulkan"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,), supports_one_shot=True, available=True,
        )
        injected = LlamaCppRunner(cap)
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(cap, TARGET_SYCL, configured_runner=injected)

    def test_sycl_rechaza_runner_incompatible(self):
        injected = MagicMock()
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(object(), TARGET_SYCL, configured_runner=injected)

    def test_cpu_vulkan_conservan_inyeccion(self):
        injected = MagicMock()
        self.assertIs(_select_runner(object(), TARGET_CPU, configured_runner=injected), injected)
        self.assertIs(_select_runner(object(), TARGET_VULKAN, configured_runner=injected), injected)

    def test_backend_desconocido_error(self):
        target = ExecutionTarget(runtime="x", backend="CUDA")
        with self.assertRaises(RunPreparationFailedError):
            _select_runner(object(), target)


class BuildSyclRunnerTests(unittest.TestCase):
    def test_capability_executable_path_prioridad(self):
        cap = type("C", (), {"executable_path": "/cap/llama-sycl"})()
        with patch.dict(os.environ, {"CASTLEARQ_SYCL_SETVARS": "/opt/setvars.sh"}, clear=False):
            with patch("castlearq.sycl_runner.SyclLlamaRunner") as cls:
                cls.return_value = MagicMock()
                runner = build_sycl_runner(cap)
                cls.assert_called_once_with(
                    executable_path="/cap/llama-sycl", setvars_path="/opt/setvars.sh"
                )

    def test_env_var_fallback(self):
        cap = type("C", (), {"executable_path": None})()
        with patch.dict(os.environ, {
            "CASTLEARQ_SYCL_RUNTIME": "/env/llama-sycl",
            "CASTLEARQ_SYCL_SETVARS": "/env/setvars.sh",
        }, clear=False):
            with patch("castlearq.sycl_runner.SyclLlamaRunner") as cls:
                cls.return_value = MagicMock()
                runner = build_sycl_runner(cap)
                cls.assert_called_once_with(
                    executable_path="/env/llama-sycl", setvars_path="/env/setvars.sh"
                )

    def test_configuracion_ausente_error(self):
        cap = type("C", (), {"executable_path": None})()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                build_sycl_runner(cap)

    def test_no_modifica_os_environ(self):
        cap = type("C", (), {"executable_path": "/cap/llama-sycl"})()
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
