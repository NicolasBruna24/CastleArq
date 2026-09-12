import unittest

from app.runtimes import (
    PromptInputMode,
    RuntimeCapability,
    RuntimeProbeResult,
    detect_llama_capability,
)


VERSION = "version: 0.4.0-dev (build 10909, commit abc123)"
HELP = """
-m, --model FNAME model path to load
-p, --prompt PROMPT prompt to start generation with
-f, --file FNAME a file containing the prompt
--device <dev1,dev2,..> devices to use
--list-devices print list of available devices and exit
"""


def successful_probe(command):
    if command[-1] == "--version":
        return RuntimeProbeResult(0, VERSION, "")
    if command[-1] == "--help":
        return RuntimeProbeResult(0, HELP, "")
    if command[-1] == "--list-devices":
        return RuntimeProbeResult(0, "Available devices:\n  Vulkan0: Intel GPU", "")
    raise AssertionError(command)


class RuntimeCapabilityTests(unittest.TestCase):
    def test_detects_available_llama_cli_capabilities(self):
        capability = detect_llama_capability(
            which=lambda name: "/opt/llama" if name == "llama" else None,
            run=successful_probe,
        )
        self.assertTrue(capability.available)
        self.assertEqual(capability.executable_path, "/opt/llama")
        self.assertEqual(capability.version, VERSION)
        self.assertEqual(capability.supported_formats, ("GGUF",))
        self.assertEqual(capability.supported_backends, ("CPU", "Vulkan"))
        self.assertEqual(
            capability.prompt_input_modes,
            (PromptInputMode.ARGUMENT, PromptInputMode.FILE),
        )
        self.assertTrue(capability.supports_one_shot)

    def test_missing_llama_is_unavailable(self):
        capability = detect_llama_capability(which=lambda _: None, run=successful_probe)
        self.assertFalse(capability.available)
        self.assertIsNone(capability.executable_path)
        self.assertEqual(capability.reason, "llama executable was not found")

    def test_failed_probe_is_unavailable(self):
        def failed_probe(command):
            return RuntimeProbeResult(1, "", "failed")

        capability = detect_llama_capability(
            which=lambda _: "/opt/llama", run=failed_probe
        )
        self.assertFalse(capability.available)
        self.assertEqual(capability.reason, "llama cli version/help probe failed")

    def test_missing_required_option_is_unavailable(self):
        capability = detect_llama_capability(
            which=lambda _: "/opt/llama",
            run=lambda command: RuntimeProbeResult(
                0, VERSION if command[-1] == "--version" else "usage", ""
            ),
        )
        self.assertFalse(capability.available)

    def test_available_capability_requires_complete_invocation_contract(self):
        with self.assertRaises(ValueError):
            RuntimeCapability(
                name="llama.cpp CLI",
                executable_path="/opt/llama",
                version=VERSION,
                supported_formats=("GGUF",),
                supported_backends=("CPU",),
                prompt_input_modes=(),
                supports_one_shot=True,
                available=True,
            )

    def test_capability_is_immutable(self):
        capability = detect_llama_capability(
            which=lambda name: "/opt/llama" if name == "llama" else None,
            run=successful_probe,
        )
        with self.assertRaises(AttributeError):
            capability.name = "other"

    def test_probe_does_not_receive_model_store_or_user_command(self):
        commands = []
        detect_llama_capability(
            which=lambda _: "/opt/llama",
            run=lambda command: (
                commands.append(command)
                or successful_probe(command)
            ),
        )
        self.assertEqual(
            commands,
            [
                ("/opt/llama", "cli", "--version"),
                ("/opt/llama", "cli", "--help"),
                ("/opt/llama", "cli", "--list-devices"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
