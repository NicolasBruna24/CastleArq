
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
from unittest import mock

from app.runtimes import (
    PromptInputMode,
    RuntimeCapability,
    RuntimeProbeResult,
    detect_llama_capability,
    query_llama_devices,
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

    def test_resolver_reports_not_found(self):
        from app.runtimes import RuntimeAvailability, resolve_llama_runtime

        resolved = resolve_llama_runtime(which=lambda _: None, run=successful_probe)
        self.assertIs(resolved.identity.availability, RuntimeAvailability.NOT_FOUND)
        self.assertIsNone(resolved.capability)
        self.assertEqual(resolved.identity.canonical_id, "llama.cpp")

    def test_resolver_reports_found_unusable_for_non_executable(self):
        from app.runtimes import RuntimeAvailability, resolve_llama_runtime
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "llama"
            path.write_text("not executable", encoding="utf-8")
            path.chmod(0o644)
            resolved = resolve_llama_runtime(
                which=lambda name: str(path) if name == "llama" else None,
                run=successful_probe,
            )
        self.assertIs(resolved.identity.availability, RuntimeAvailability.FOUND_UNUSABLE)
        self.assertIsNone(resolved.capability)

    def test_resolver_preserves_probe_failure_without_claiming_success(self):
        from app.runtimes import RuntimeAvailability, resolve_llama_runtime

        with mock.patch("app.runtimes.os.access", return_value=True):
            resolved = resolve_llama_runtime(
                which=lambda name: "/opt/llama" if name == "llama" else None,
                run=lambda command: RuntimeProbeResult(1, "", "probe failed"),
            )
        self.assertIs(resolved.identity.availability, RuntimeAvailability.FOUND_UNUSABLE)
        self.assertIsNone(resolved.capability)
        self.assertEqual(resolved.identity.reason, "llama cli version/help probe failed")

    def test_resolver_reports_identity_and_capability(self):
        from app.runtimes import RuntimeAvailability, resolve_llama_runtime

        with mock.patch("app.runtimes.os.access", return_value=True):
            resolved = resolve_llama_runtime(
                which=lambda name: "/opt/llama" if name == "llama" else None,
                run=successful_probe,
            )
        self.assertIs(resolved.identity.availability, RuntimeAvailability.AVAILABLE)
        self.assertEqual(resolved.identity.executable_name, "llama")
        self.assertEqual(resolved.identity.version, VERSION)
        self.assertEqual(resolved.identity.build_identifier, "10909")
        self.assertIsNotNone(resolved.capability)
        self.assertIn("GGUF", resolved.capability.supported_formats)
        self.assertIn("CPU", resolved.capability.supported_backends)

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

    def test_devices_query_tries_cli_then_serve_then_bare_in_order(self):
        calls = []

        def run(command):
            calls.append(command)
            if command == ("/opt/llama", "serve", "--list-devices"):
                return RuntimeProbeResult(0, "Vulkan0: Intel GPU", "")
            return RuntimeProbeResult(1, "", "nope")

        text = query_llama_devices("/opt/llama", run)
        self.assertEqual(text, "Vulkan0: Intel GPU\n")
        self.assertEqual(
            calls,
            [
                ("/opt/llama", "cli", "--list-devices"),
                ("/opt/llama", "serve", "--list-devices"),
            ],
        )

    def test_devices_query_falls_back_to_bare_variant(self):
        calls = []

        def run(command):
            calls.append(command)
            if command == ("/opt/llama", "--list-devices"):
                return RuntimeProbeResult(0, "Vulkan0: Intel GPU", "")
            return RuntimeProbeResult(1, "", "nope")

        text = query_llama_devices("/opt/llama", run)
        self.assertEqual(text, "Vulkan0: Intel GPU\n")
        self.assertEqual(
            calls,
            [
                ("/opt/llama", "cli", "--list-devices"),
                ("/opt/llama", "serve", "--list-devices"),
                ("/opt/llama", "--list-devices"),
            ],
        )

    def test_devices_query_returns_none_when_all_variants_fail(self):
        text = query_llama_devices(
            "/opt/llama",
            lambda command: RuntimeProbeResult(1, "", "nope"),
        )
        self.assertIsNone(text)

    def test_devices_query_rejects_nonzero_returncode_with_stdout(self):
        def run(command):
            if command == ("/opt/llama", "--list-devices"):
                return RuntimeProbeResult(0, "Vulkan0: Intel GPU", "")
            return RuntimeProbeResult(1, "Vulkan0: Intel GPU", "")

        text = query_llama_devices("/opt/llama", run)
        # First success wins: cli variant returns stdout despite rc != 0 is
        # rejected only when it is the failing one; here cli fails with
        # stdout and bare succeeds.
        self.assertEqual(text, "Vulkan0: Intel GPU\n")

    def test_devices_query_ignores_stdout_on_failure(self):
        text = query_llama_devices(
            "/opt/llama",
            lambda command: RuntimeProbeResult(1, "Vulkan0: Intel GPU", ""),
        )
        self.assertIsNone(text)

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
