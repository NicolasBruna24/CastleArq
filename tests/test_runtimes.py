
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

from app.runtimes import detect_backends, detect_runtimes


class RuntimeTests(unittest.TestCase):
    def test_runtime_detection_distinguishes_missing_and_installed(self):
        paths = {"llama-cli": "/usr/bin/llama-cli", "ollama": "/usr/bin/ollama"}
        runtimes = detect_runtimes(paths.get)
        self.assertTrue(runtimes[0].installed)
        self.assertTrue(runtimes[0].available)
        self.assertTrue(runtimes[1].installed)
        self.assertFalse(runtimes[1].available)

    def test_runtime_detection_handles_missing_commands(self):
        runtimes = detect_runtimes(lambda _: None)
        self.assertTrue(all(not runtime.installed for runtime in runtimes))

    def test_backend_detection_uses_command_presence(self):
        backends = detect_backends(lambda name: "/bin/tool" if name == "vulkaninfo" else None)
        self.assertTrue(backends[0].available)
        self.assertFalse(backends[1].available)

    def test_backend_detection_accepts_gpu_evidence(self):
        backends = detect_backends(lambda _: None, {"Vulkan"})
        self.assertTrue(backends[0].available)


if __name__ == "__main__":
    unittest.main()
