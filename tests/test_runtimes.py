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


if __name__ == "__main__":
    unittest.main()
