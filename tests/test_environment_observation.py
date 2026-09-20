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

"""Hermetic tests for B9.11: environment observation domain, probes, and rules."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from app.observation_domain import (
    CoverageEntry,
    CoverageState,
    DeviceObservation,
    EnvironmentContext,
    HardwareObservation,
    ObservationCoverage,
    ObservationFamily,
    ObservationState,
    ObservedValue,
    PlatformObservation,
    RuntimeObservation,
)
from app.observation_probe import (
    ACQUISITION_ERRORS,
    CommandResult,
    EnvironmentObserver,
    detect_backend_evidence,
    parse_lspci_nn,
    parse_meminfo,
    parse_os_release,
)


class FakeEnvironment:
    """Configurable test doubles for I/O injection."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        commands: dict[tuple[str, ...], CommandResult] | None = None,
        binaries: dict[str, str] | None = None,
        timestamp: str = "2026-09-18T12:00:00Z",
    ) -> None:
        self.files = files or {}
        self.commands = commands or {}
        self.binaries = binaries or {}
        self.timestamp = timestamp

    def read_file(self, path: str) -> str | None:
        return self.files.get(path)

    def run_cmd(self, command: tuple[str, ...], timeout: float) -> CommandResult:
        if tuple(command) in self.commands:
            return self.commands[tuple(command)]
        return CommandResult(
            returncode=127,
            stdout="",
            stderr="command not found",
            error="Command not found in fake environment",
        )

    def which(self, binary: str) -> str | None:
        return self.binaries.get(binary)

    def get_timestamp(self) -> str:
        return self.timestamp


# ----------------------------------------------------------------------
# 1. Domain Tests
# ----------------------------------------------------------------------

class DomainContractTests(unittest.TestCase):
    def test_observed_value_is_frozen(self) -> None:
        val = ObservedValue(
            state=ObservationState.OBSERVED,
            value=123,
            source="test",
        )
        with self.assertRaises(FrozenInstanceError):
            val.value = 456  # type: ignore[misc]

    def test_observed_value_validation(self) -> None:
        with self.assertRaises(ValueError):
            ObservedValue(state="invalid", source="test")  # type: ignore[arg-type]
        # Shape checks are independent of the AD-05 invariants: a value is
        # supplied so each failure is attributable to the field under test.
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.OBSERVED, value="x", source="")
        with self.assertRaises(ValueError):
            ObservedValue(
                state=ObservationState.OBSERVED, value="x", source="src", detail=""
            )

    def test_environment_context_immutability(self) -> None:
        obs_val = ObservedValue(state=ObservationState.OBSERVED, value="x", source="s")
        plat = PlatformObservation(
            os_family=obs_val,
            os_release=obs_val,
            architecture=obs_val,
            distribution=obs_val,
        )
        hw = HardwareObservation(memory_total_bytes=obs_val, devices=())
        ctx = EnvironmentContext(
            timestamp="2026-09-18T00:00:00Z",
            platform=plat,
            hardware=hw,
            runtimes=(),
        )
        with self.assertRaises(FrozenInstanceError):
            ctx.timestamp = "other"  # type: ignore[misc]
        self.assertIsInstance(ctx.runtimes, tuple)
        self.assertIsInstance(ctx.hardware.devices, tuple)


# ----------------------------------------------------------------------
# 2. Pure Parsers Tests
# ----------------------------------------------------------------------

class PureParsersTests(unittest.TestCase):
    def test_parse_os_release_ubuntu(self) -> None:
        sample = """
        NAME="Ubuntu"
        VERSION="24.04 LTS (Noble Numbat)"
        ID=ubuntu
        ID_LIKE=debian
        PRETTY_NAME="Ubuntu 24.04 LTS"
        """
        fields = parse_os_release(sample)
        self.assertEqual(fields.get("ID"), "ubuntu")
        self.assertEqual(fields.get("NAME"), "Ubuntu")
        self.assertEqual(fields.get("ID_LIKE"), "debian")

    def test_parse_os_release_arch(self) -> None:
        sample = 'NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\nID=arch\nBUILD_ID=rolling\n'
        fields = parse_os_release(sample)
        self.assertEqual(fields.get("ID"), "arch")

    def test_parse_os_release_malformed_and_empty(self) -> None:
        self.assertEqual(parse_os_release(""), {})
        self.assertEqual(parse_os_release("random text without equals"), {})
        self.assertEqual(parse_os_release("# Comment line\n=no_key\n"), {"": "no_key"})

    def test_parse_meminfo_valid(self) -> None:
        sample = """
        MemTotal:       32654848 kB
        MemFree:        21234560 kB
        MemAvailable:   27890123 kB
        """
        res = parse_meminfo(sample)
        self.assertEqual(res.bytes, 32654848 * 1024)
        self.assertIsNone(res.error_kind)

    def test_parse_meminfo_missing_or_malformed(self) -> None:
        # Absence: no MemTotal line at all.
        self.assertEqual(parse_meminfo("").error_kind, "absent")
        self.assertEqual(parse_meminfo("MemFree: 1024 kB\n").error_kind, "absent")
        # Invalid format: number not parseable -> bad_number, no value invented.
        bad_num = parse_meminfo("MemTotal: not_a_number kB\n")
        self.assertIsNone(bad_num.bytes)
        self.assertEqual(bad_num.error_kind, "bad_number")
        # Unrecognized unit: bare number with no explicit unit -> bad_unit.
        no_unit = parse_meminfo("MemTotal: 1024\n")
        self.assertIsNone(no_unit.bytes)
        self.assertEqual(no_unit.error_kind, "bad_unit")
        # Unrecognized unit: GB is not an accepted explicit unit.
        bad_unit = parse_meminfo("MemTotal: 16384 GB\n")
        self.assertIsNone(bad_unit.bytes)
        self.assertEqual(bad_unit.error_kind, "bad_unit")

    def test_parse_lspci_nn_intel_arc(self) -> None:
        sample = (
            "00:02.0 VGA compatible controller [0300]: Intel Corporation Device [8086:e223] (rev 08)\n"
            "00:1f.3 Audio device [0403]: Intel Corporation Device [8086:7f50] (rev 11)\n"
        )
        devices = parse_lspci_nn(sample)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["vendor_id"], "8086")
        self.assertEqual(devices[0]["device_id"], "e223")
        self.assertIn("Intel Corporation Device", devices[0]["name"] or "")

    def test_parse_lspci_nn_nvidia_and_amd(self) -> None:
        sample = """
        01:00.0 3D controller [0302]: NVIDIA Corporation AD104 [GeForce RTX 4070] [10de:2786] (rev a1)
        06:00.0 Display controller [0380]: Advanced Micro Devices, Inc. [AMD/ATI] Navi 31 [1002:7448] (rev c8)
        """
        devices = parse_lspci_nn(sample)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["vendor_id"], "10de")
        self.assertEqual(devices[0]["device_id"], "2786")
        self.assertEqual(devices[1]["vendor_id"], "1002")
        self.assertEqual(devices[1]["device_id"], "7448")

    def test_parse_lspci_nn_unknown_vendor_not_fabricated(self) -> None:
        sample = "03:00.0 VGA compatible controller [0300]: Custom Vendor Device [9999:aaaa] (rev 01)"
        devices = parse_lspci_nn(sample)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["vendor_id"], "9999")
        self.assertEqual(devices[0]["device_id"], "aaaa")


# ----------------------------------------------------------------------
# 3. Effectful Observer with Injected I/O Tests
# ----------------------------------------------------------------------

class EnvironmentObserverTests(unittest.TestCase):
    def test_observe_platform_success(self) -> None:
        fake = FakeEnvironment(
            files={"/etc/os-release": "ID=fedora\nVERSION_ID=40\n"}
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        platform_info = obs.observe_platform()
        self.assertEqual(platform_info.distribution.state, ObservationState.OBSERVED)
        self.assertEqual(platform_info.distribution.value, "fedora")
        self.assertEqual(platform_info.distribution.source, "file:/etc/os-release")

    def test_observe_platform_missing_os_release(self) -> None:
        fake = FakeEnvironment(files={})
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        platform_info = obs.observe_platform()
        self.assertEqual(platform_info.distribution.state, ObservationState.UNAVAILABLE)
        self.assertIsNone(platform_info.distribution.value)

    def test_observe_hardware_with_lspci(self) -> None:
        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 16384 kB\n"},
            binaries={"lspci": "/usr/bin/lspci"},
            commands={
                ("/usr/bin/lspci", "-nn"): CommandResult(
                    returncode=0,
                    stdout="00:02.0 VGA compatible controller [0300]: Intel Device [8086:56a0] (rev 08)\n",
                    stderr="",
                )
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        hw = obs.observe_hardware()
        self.assertEqual(hw.memory_total_bytes.state, ObservationState.OBSERVED)
        self.assertEqual(hw.memory_total_bytes.value, 16384 * 1024)
        self.assertEqual(len(hw.devices), 1)
        self.assertEqual(hw.devices[0].vendor_id.value, "8086")
        self.assertEqual(hw.devices[0].device_id.value, "56a0")

    def test_observe_hardware_lspci_missing(self) -> None:
        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 8192 kB\n"},
            binaries={},  # no lspci
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        hw = obs.observe_hardware()
        self.assertEqual(hw.memory_total_bytes.state, ObservationState.OBSERVED)
        # No structured CPU device is fabricated: system RAM is not a
        # CPU DeviceObservation; absence of lspci means zero devices plus
        # an explicit UNAVAILABLE acquisition error.
        self.assertEqual(hw.devices, ())
        self.assertIsNotNone(hw.acquisition_error)
        assert hw.acquisition_error is not None
        self.assertEqual(hw.acquisition_error.state, ObservationState.UNAVAILABLE)
        self.assertEqual(hw.acquisition_error.source, "which:lspci")

    def test_observe_hardware_lspci_timeout_or_error(self) -> None:
        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 8192 kB\n"},
            binaries={"lspci": "/usr/bin/lspci"},
            commands={
                ("/usr/bin/lspci", "-nn"): CommandResult(
                    returncode=1,
                    stdout="",
                    stderr="permission denied",
                    error="Command exited with 1",
                )
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        hw = obs.observe_hardware()
        # Failure is explicit: devices stay empty AND an ERROR
        # acquisition_error is recorded (never silently discarded).
        self.assertEqual(hw.devices, ())
        self.assertIsNotNone(hw.acquisition_error)
        assert hw.acquisition_error is not None
        self.assertEqual(hw.acquisition_error.state, ObservationState.ERROR)
        self.assertIn("1", hw.acquisition_error.detail or "")

    def test_observe_hardware_lspci_raises_oserror_maps_to_error(self) -> None:
        def raising_runner(
            command: tuple[str, ...], timeout: float
        ) -> CommandResult:
            raise OSError("lspci exploded")

        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 8192 kB\n"},
            binaries={"lspci": "/usr/bin/lspci"},
        )
        obs = EnvironmentObserver(
            raising_runner, fake.read_file, fake.which, fake.get_timestamp
        )
        hw = obs.observe_hardware()
        self.assertEqual(hw.devices, ())
        self.assertIsNotNone(hw.acquisition_error)
        assert hw.acquisition_error is not None
        self.assertEqual(hw.acquisition_error.state, ObservationState.ERROR)

    def test_observe_runtimes_llama_and_ollama_present(self) -> None:
        fake = FakeEnvironment(
            binaries={
                "llama-cli": "/opt/bin/llama-cli",
                "ollama": "/usr/local/bin/ollama",
            },
            commands={
                ("/opt/bin/llama-cli", "--version"): CommandResult(
                    returncode=0, stdout="version b3560 (commit 1234)\n", stderr=""
                ),
                ("/opt/bin/llama-cli", "--help"): CommandResult(
                    returncode=0,
                    stdout="usage: llama-cli [options]\n  --vulkan device\n",
                    stderr="",
                ),
                ("/usr/local/bin/ollama", "--version"): CommandResult(
                    returncode=0, stdout="ollama version is 0.3.10\n", stderr=""
                ),
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        runtimes = obs.observe_runtimes()
        self.assertEqual(len(runtimes), 2)

        # llama.cpp checks
        llama = next(r for r in runtimes if r.canonical_id == "llama.cpp")
        self.assertEqual(llama.executable_path.state, ObservationState.OBSERVED)
        self.assertEqual(llama.executable_path.value, "/opt/bin/llama-cli")
        self.assertEqual(llama.raw_version.state, ObservationState.OBSERVED)
        self.assertIn("b3560", llama.raw_version.value or "")
        # Vulkan backend was explicitly reported in help
        self.assertEqual(len(llama.detected_backends), 1)
        self.assertEqual(llama.detected_backends[0].value, "vulkan")

        # ollama checks
        ollama = next(r for r in runtimes if r.canonical_id == "ollama")
        self.assertEqual(ollama.executable_path.state, ObservationState.OBSERVED)
        self.assertEqual(ollama.executable_path.value, "/usr/local/bin/ollama")
        self.assertEqual(ollama.raw_version.state, ObservationState.OBSERVED)
        self.assertIn("0.3.10", ollama.raw_version.value or "")

    def test_observe_runtimes_absent(self) -> None:
        fake = FakeEnvironment(binaries={})
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        runtimes = obs.observe_runtimes()
        for r in runtimes:
            self.assertEqual(r.executable_path.state, ObservationState.UNAVAILABLE)
            self.assertEqual(r.raw_version.state, ObservationState.UNAVAILABLE)
            self.assertEqual(r.detected_backends, ())

    def test_observe_runtime_probe_fails(self) -> None:
        fake = FakeEnvironment(
            binaries={"llama-cli": "/usr/bin/llama-cli"},
            commands={
                ("/usr/bin/llama-cli", "--version"): CommandResult(
                    returncode=1,
                    stdout="",
                    stderr="Segmentation fault",
                    error="Crash",
                ),
                ("/usr/bin/llama-cli", "--help"): CommandResult(
                    returncode=1, stdout="", stderr="Error"
                ),
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        runtimes = obs.observe_runtimes()
        llama = next(r for r in runtimes if r.canonical_id == "llama.cpp")
        self.assertEqual(llama.executable_path.state, ObservationState.OBSERVED)
        self.assertEqual(llama.raw_version.state, ObservationState.ERROR)
        self.assertEqual(llama.raw_version.detail, "Crash")

    def test_capture_context_determinism(self) -> None:
        fake = FakeEnvironment(
            timestamp="2026-09-18T15:30:00Z",
            files={"/etc/os-release": "ID=ubuntu\n"},
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        ctx1 = obs.capture_context()
        ctx2 = obs.capture_context()
        self.assertEqual(ctx1, ctx2)
        self.assertEqual(ctx1.timestamp, "2026-09-18T15:30:00Z")


# ----------------------------------------------------------------------
# 4. No-Inference & Purity Rules Tests
# ----------------------------------------------------------------------

class NoInferenceAndPurityTests(unittest.TestCase):
    def test_unknown_pci_vendor_is_never_fabricated(self) -> None:
        fake = FakeEnvironment(
            binaries={"lspci": "/usr/bin/lspci"},
            commands={
                ("/usr/bin/lspci", "-nn"): CommandResult(
                    returncode=0,
                    stdout="00:02.0 VGA compatible controller [0300]: Mystery Chip [7777:8888] (rev 01)\n",
                    stderr="",
                )
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        hw = obs.observe_hardware()
        self.assertEqual(len(hw.devices), 1)
        self.assertEqual(hw.devices[0].vendor_id.value, "7777")
        self.assertNotIn("Intel", hw.devices[0].vendor_id.value or "")
        self.assertNotIn("NVIDIA", hw.devices[0].vendor_id.value or "")

    def test_backend_evidence_criterion_exact(self) -> None:
        # Explicit evidence forms each count.
        self.assertEqual(
            detect_backend_evidence("usage: llama-cli\n  --vulkan device\n"),
            ("vulkan",),
        )
        self.assertEqual(
            detect_backend_evidence("supported backends: cuda, cpu\n"),
            ("cuda",),
        )
        self.assertEqual(
            detect_backend_evidence("llama.cpp built with sycl support\n"),
            ("sycl",),
        )
        # Incidental prose never counts: no flag, no enumeration, no build
        # declaration -> no evidence, no inference.
        self.assertEqual(
            detect_backend_evidence(
                "this vulkan-like renderer mentions cuda cores "
                "and sycl concepts in prose\n"
            ),
            (),
        )
        self.assertEqual(
            detect_backend_evidence("plain help without backends\n"), ()
        )

    def test_backend_incidental_word_is_not_evidence(self) -> None:
        # "vulcans" / "cudas" must not match whole-word backend names.
        fake = FakeEnvironment(
            binaries={"llama-cli": "/usr/bin/llama-cli"},
            commands={
                ("/usr/bin/llama-cli", "--version"): CommandResult(
                    returncode=0, stdout="b100\n", stderr=""
                ),
                ("/usr/bin/llama-cli", "--help"): CommandResult(
                    returncode=0,
                    stdout="supports vulcans and cuda cores in prose\n",
                    stderr="",
                ),
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        runtimes = obs.observe_runtimes()
        llama = next(r for r in runtimes if r.canonical_id == "llama.cpp")
        self.assertEqual(llama.detected_backends, ())

    def test_runtime_presence_never_infers_backend(self) -> None:
        # Runtime help output has NO backend mentions
        fake = FakeEnvironment(
            binaries={"llama-cli": "/usr/bin/llama-cli"},
            commands={
                ("/usr/bin/llama-cli", "--version"): CommandResult(
                    returncode=0, stdout="b100\n", stderr=""
                ),
                ("/usr/bin/llama-cli", "--help"): CommandResult(
                    returncode=0, stdout="plain help without backends\n", stderr=""
                ),
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        runtimes = obs.observe_runtimes()
        llama = next(r for r in runtimes if r.canonical_id == "llama.cpp")
        # CPU or Vulkan MUST NOT be inferred!
        self.assertEqual(llama.detected_backends, ())

    def test_unavailable_is_not_unsupported(self) -> None:
        val = ObservedValue(
            state=ObservationState.UNAVAILABLE,
            source="test",
            detail="Tool not present",
        )
        # Verify it has no concept of unsupported
        self.assertFalse(hasattr(val, "unsupported"))
        self.assertNotEqual(val.state, "unsupported")

    def test_error_is_not_unsupported(self) -> None:
        val = ObservedValue(
            state=ObservationState.ERROR,
            source="test",
            detail="Process timed out",
        )
        self.assertNotEqual(val.state, "unsupported")

    def test_ast_purity_observation_domain(self) -> None:
        domain_file = Path(__file__).resolve().parent.parent / "app" / "observation_domain.py"
        tree = ast.parse(domain_file.read_text(encoding="utf-8"))

        forbidden_imports = {
            "os",
            "sys",
            "subprocess",
            "socket",
            "urllib",
            "pathlib",
            "app.compatibility",
            "app.compatibility_evaluator",
            "app.evaluation_pipeline",
            "app.evaluation_policy",
            "app.selection",
            "app.execution_service",
            "app.run_service",
            "app.runtimes",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden_imports)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertNotIn(module, forbidden_imports)
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    self.assertNotIn(full_name, forbidden_imports)


# ----------------------------------------------------------------------
# 5. AD-05: ObservedValue invariants
# ----------------------------------------------------------------------

class ObservedValueInvariantTests(unittest.TestCase):
    """The epistemic state is part of the contract, not a label (AD-05)."""

    def test_observed_requires_a_non_none_value(self) -> None:
        val = ObservedValue(state=ObservationState.OBSERVED, value="x", source="s")
        self.assertEqual(val.value, "x")
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.OBSERVED, source="s")
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.OBSERVED, value=None, source="s")

    def test_unavailable_accepts_none_with_detail(self) -> None:
        val = ObservedValue(
            state=ObservationState.UNAVAILABLE,
            value=None,
            source="s",
            detail="interface does not exist",
        )
        self.assertIsNone(val.value)

    def test_unavailable_rejects_value_and_missing_detail(self) -> None:
        with self.assertRaises(ValueError):
            ObservedValue(
                state=ObservationState.UNAVAILABLE,
                value="x",
                source="s",
                detail="d",
            )
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.UNAVAILABLE, source="s")
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.UNAVAILABLE, source="s", detail="")

    def test_error_accepts_none_with_detail(self) -> None:
        val = ObservedValue(
            state=ObservationState.ERROR, source="s", detail="timeout: 2s"
        )
        self.assertIsNone(val.value)

    def test_error_rejects_value_and_missing_detail(self) -> None:
        with self.assertRaises(ValueError):
            ObservedValue(
                state=ObservationState.ERROR, value="x", source="s", detail="d"
            )
        with self.assertRaises(ValueError):
            ObservedValue(state=ObservationState.ERROR, source="s")

    def test_omitted_value_equals_explicit_none(self) -> None:
        omitted = ObservedValue(
            state=ObservationState.UNAVAILABLE, source="s", detail="d"
        )
        explicit = ObservedValue(
            state=ObservationState.UNAVAILABLE, value=None, source="s", detail="d"
        )
        self.assertEqual(omitted, explicit)

    def test_observation_state_has_no_not_observed_member(self) -> None:
        # Coverage is a separate dimension (AD-04), never a fourth state.
        self.assertFalse(hasattr(ObservationState, "NOT_OBSERVED"))
        self.assertEqual(
            [state.value for state in ObservationState],
            ["observed", "unavailable", "error"],
        )


# ----------------------------------------------------------------------
# 6. AD-01: positive backend evidence only
# ----------------------------------------------------------------------

class BackendEvidenceContractTests(unittest.TestCase):
    """``OBSERVED`` requires positive evidence under a closed syntactic form."""

    def test_positive_forms_are_detected(self) -> None:
        self.assertEqual(detect_backend_evidence("backend: CUDA"), ("cuda",))
        self.assertEqual(detect_backend_evidence("  --vulkan device"), ("vulkan",))
        self.assertEqual(
            detect_backend_evidence("usage: llama-cli\n  -vulkan\n"), ("vulkan",)
        )
        self.assertEqual(detect_backend_evidence("backend = sycl"), ("sycl",))
        self.assertEqual(
            detect_backend_evidence("supported backends: cuda, cpu"), ("cuda",)
        )
        self.assertEqual(detect_backend_evidence("compiled with cuda"), ("cuda",))
        self.assertEqual(
            detect_backend_evidence("backends: cpu cuda vulkan"), ("vulkan", "cuda")
        )

    def test_negations_and_incidental_prose_are_never_evidence(self) -> None:
        for text in (
            "backends: cpu only, cuda not compiled in",
            "backend: CPU (CUDA disabled)",
            "built with care; vulkan unsupported",
            "llama.cpp built with tests; sycl is not available",
            "backends: cpu  # do not enable cuda",
            "backend: cudagraph mode",
            "backends: vulkan-like",
            "supports vulcans and cuda cores in prose",
            "plain help without backends",
            "--vulkaninfo tool",
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_backend_evidence(text), ())

    def test_negated_help_produces_no_observed_backend(self) -> None:
        fake = FakeEnvironment(
            binaries={"llama-cli": "/usr/bin/llama-cli"},
            commands={
                ("/usr/bin/llama-cli", "--version"): CommandResult(
                    returncode=0, stdout="b100\n", stderr=""
                ),
                ("/usr/bin/llama-cli", "--help"): CommandResult(
                    returncode=0,
                    stdout=(
                        "backends: cpu only, cuda not compiled in\n"
                        "backend: CPU (CUDA disabled)\n"
                        "built with care; vulkan unsupported\n"
                    ),
                    stderr="",
                ),
            },
        )
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        llama = next(
            r for r in obs.observe_runtimes() if r.canonical_id == "llama.cpp"
        )
        self.assertEqual(llama.detected_backends, ())
        # Probed with no positive evidence: an explicit outcome, never a bare
        # empty tuple that could be read as "no backend exists".
        self.assertIsNotNone(llama.backends_outcome)
        assert llama.backends_outcome is not None
        self.assertEqual(
            llama.backends_outcome.state, ObservationState.UNAVAILABLE
        )


# ----------------------------------------------------------------------
# 7. AD-02: provenance describes the operation that actually ran
# ----------------------------------------------------------------------

class ProvenanceContractTests(unittest.TestCase):
    """Provenance names the real operation, never the technology concept."""

    def _run(self, fake: FakeEnvironment) -> tuple[RuntimeObservation, ...]:
        obs = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )
        return obs.observe_runtimes()

    def test_resolved_candidate_is_named_verbatim(self) -> None:
        # Only ``llama`` exists: ``which llama`` is the operation that ran.
        fake = FakeEnvironment(
            binaries={"llama": "/opt/bin/llama"},
            commands={
                ("/opt/bin/llama", "--version"): CommandResult(
                    returncode=0, stdout="version b3560\n", stderr=""
                ),
                ("/opt/bin/llama", "--help"): CommandResult(
                    returncode=0, stdout="  --vulkan device\n", stderr=""
                ),
            },
        )
        llama = next(
            r for r in self._run(fake) if r.canonical_id == "llama.cpp"
        )
        self.assertEqual(llama.executable_path.source, "which:llama")
        self.assertEqual(llama.raw_version.source, "command:/opt/bin/llama --version")
        self.assertEqual(len(llama.detected_backends), 1)
        self.assertEqual(
            llama.detected_backends[0].source, "command:/opt/bin/llama --help"
        )

    def test_second_candidate_is_reported_when_it_is_the_one_found(self) -> None:
        fake = FakeEnvironment(
            binaries={"llama.app": "/Applications/llama.app/bin/llama"},
            commands={
                ("/Applications/llama.app/bin/llama", "--version"): CommandResult(
                    returncode=0, stdout="b100\n", stderr=""
                ),
                ("/Applications/llama.app/bin/llama", "--help"): CommandResult(
                    returncode=0, stdout="plain help\n", stderr=""
                ),
            },
        )
        llama = next(
            r for r in self._run(fake) if r.canonical_id == "llama.cpp"
        )
        self.assertEqual(llama.executable_path.source, "which:llama.app")

    def test_absent_runtime_never_records_a_command_that_did_not_run(self) -> None:
        runtimes = self._run(FakeEnvironment(binaries={}))
        llama = next(r for r in runtimes if r.canonical_id == "llama.cpp")
        ollama = next(r for r in runtimes if r.canonical_id == "ollama")
        # The operation that ran was the candidate search, in both facts.
        self.assertEqual(
            llama.executable_path.source, "which:llama-cli,llama,llama.app"
        )
        self.assertEqual(
            llama.raw_version.source, "which:llama-cli,llama,llama.app"
        )
        self.assertNotIn("--version", llama.raw_version.source)
        self.assertEqual(llama.raw_version.state, ObservationState.UNAVAILABLE)
        self.assertEqual(ollama.executable_path.source, "which:ollama")
        self.assertEqual(ollama.raw_version.source, "which:ollama")
        self.assertNotIn("--version", ollama.raw_version.source)

    def test_ollama_version_uses_the_real_operation_when_present(self) -> None:
        fake = FakeEnvironment(
            binaries={"ollama": "/usr/local/bin/ollama"},
            commands={
                ("/usr/local/bin/ollama", "--version"): CommandResult(
                    returncode=0, stdout="ollama version is 0.3.10\n", stderr=""
                )
            },
        )
        ollama = next(
            r for r in self._run(fake) if r.canonical_id == "ollama"
        )
        self.assertEqual(ollama.executable_path.source, "which:ollama")
        self.assertEqual(
            ollama.raw_version.source, "command:/usr/local/bin/ollama --version"
        )


# ----------------------------------------------------------------------
# 8. AD-04: coverage is a separate dimension
# ----------------------------------------------------------------------

class CoverageContractTests(unittest.TestCase):
    """An empty collection is never evidence: coverage says what was probed."""

    def _observer(self, fake: FakeEnvironment) -> EnvironmentObserver:
        return EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        )

    def _llama(self, help_result: CommandResult) -> RuntimeObservation:
        fake = FakeEnvironment(
            binaries={"llama-cli": "/usr/bin/llama-cli"},
            commands={
                ("/usr/bin/llama-cli", "--version"): CommandResult(
                    returncode=0, stdout="b100\n", stderr=""
                ),
                ("/usr/bin/llama-cli", "--help"): help_result,
            },
        )
        return next(
            r
            for r in self._observer(fake).observe_runtimes()
            if r.canonical_id == "llama.cpp"
        )

    def test_unlisted_family_is_not_observed(self) -> None:
        coverage = ObservationCoverage()
        family = ObservationFamily.RUNTIME_BACKENDS
        self.assertEqual(coverage.state_for(family), CoverageState.NOT_OBSERVED)
        self.assertFalse(coverage.is_observed(family))

    def test_duplicate_family_and_invalid_entries_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ObservationCoverage(entries=(
                CoverageEntry(ObservationFamily.PLATFORM, CoverageState.OBSERVED),
                CoverageEntry(
                    ObservationFamily.PLATFORM, CoverageState.NOT_OBSERVED
                ),
            ))
        with self.assertRaises(ValueError):
            ObservationCoverage(entries=(("platform", "observed"),))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            CoverageEntry(
                family="platform",  # type: ignore[arg-type]
                state=CoverageState.OBSERVED,
            )

    def test_case_a_backends_never_probed(self) -> None:
        # llama absent: the backend family was never attempted.
        absent = next(
            r
            for r in self._observer(FakeEnvironment(binaries={})).observe_runtimes()
            if r.canonical_id == "llama.cpp"
        )
        self.assertEqual(
            absent.coverage.state_for(ObservationFamily.RUNTIME_BACKENDS),
            CoverageState.NOT_OBSERVED,
        )
        self.assertIsNone(absent.backends_outcome)
        # ollama present: its backends are still never probed.
        ollama = next(
            r
            for r in self._observer(FakeEnvironment(
                binaries={"ollama": "/usr/bin/ollama"},
                commands={
                    ("/usr/bin/ollama", "--version"): CommandResult(
                        returncode=0, stdout="0.3.10\n", stderr=""
                    )
                },
            )).observe_runtimes()
            if r.canonical_id == "ollama"
        )
        self.assertEqual(ollama.detected_backends, ())
        self.assertEqual(
            ollama.coverage.state_for(ObservationFamily.RUNTIME_BACKENDS),
            CoverageState.NOT_OBSERVED,
        )
        self.assertIsNone(ollama.backends_outcome)

    def test_case_b_backends_probed_without_evidence(self) -> None:
        llama = self._llama(
            CommandResult(returncode=0, stdout="plain help\n", stderr="")
        )
        self.assertTrue(
            llama.coverage.is_observed(ObservationFamily.RUNTIME_BACKENDS)
        )
        self.assertEqual(llama.detected_backends, ())
        assert llama.backends_outcome is not None
        self.assertEqual(llama.backends_outcome.state, ObservationState.UNAVAILABLE)
        self.assertIsNone(llama.backends_outcome.value)

    def test_case_c_backends_probed_with_error(self) -> None:
        llama = self._llama(
            CommandResult(returncode=1, stdout="", stderr="boom", error="Crash")
        )
        self.assertTrue(
            llama.coverage.is_observed(ObservationFamily.RUNTIME_BACKENDS)
        )
        self.assertEqual(llama.detected_backends, ())
        assert llama.backends_outcome is not None
        self.assertEqual(llama.backends_outcome.state, ObservationState.ERROR)
        self.assertEqual(llama.backends_outcome.detail, "Crash")

    def test_case_d_backends_probed_with_positive_evidence(self) -> None:
        llama = self._llama(
            CommandResult(returncode=0, stdout="  --vulkan device\n", stderr="")
        )
        self.assertTrue(
            llama.coverage.is_observed(ObservationFamily.RUNTIME_BACKENDS)
        )
        self.assertEqual(len(llama.detected_backends), 1)
        self.assertIsNone(llama.backends_outcome)

    def test_the_four_cases_are_mutually_distinguishable(self) -> None:
        not_probed = self._observer(
            FakeEnvironment(binaries={})
        ).observe_runtimes()[0]
        no_evidence = self._llama(
            CommandResult(returncode=0, stdout="plain\n", stderr="")
        )
        failed = self._llama(
            CommandResult(returncode=1, stdout="", stderr="", error="Crash")
        )
        positive = self._llama(
            CommandResult(returncode=0, stdout="--vulkan\n", stderr="")
        )
        signatures = {
            (
                observation.coverage.state_for(ObservationFamily.RUNTIME_BACKENDS),
                observation.detected_backends,
                (
                    observation.backends_outcome.state
                    if observation.backends_outcome is not None
                    else None
                ),
            )
            for observation in (not_probed, no_evidence, failed, positive)
        }
        self.assertEqual(len(signatures), 4)


class CoverageApplicationTests(unittest.TestCase):
    """Coverage applied to the families that were previously ambiguous."""

    def test_context_reports_the_attempted_environment_families(self) -> None:
        fake = FakeEnvironment(
            files={"/etc/os-release": "ID=ubuntu\n", "/proc/meminfo": "MemTotal: 8192 kB\n"},
            binaries={},
        )
        ctx = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        ).capture_context()
        for family in (
            ObservationFamily.PLATFORM,
            ObservationFamily.HARDWARE_MEMORY,
            ObservationFamily.HARDWARE_DEVICES,
        ):
            with self.subTest(family=family.value):
                self.assertTrue(ctx.coverage.is_observed(family))
        # Coverage is a domain dimension, not an ObservationState member.
        self.assertNotIn(
            "not_observed", [state.value for state in ObservationState]
        )

    def test_device_memory_and_driver_families_are_not_observed(self) -> None:
        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 16384 kB\n"},
            binaries={"lspci": "/usr/bin/lspci"},
            commands={
                ("/usr/bin/lspci", "-nn"): CommandResult(
                    returncode=0,
                    stdout=(
                        "00:02.0 VGA compatible controller [0300]: "
                        "Intel Device [8086:56a0] (rev 08)\n"
                    ),
                    stderr="",
                )
            },
        )
        hw = EnvironmentObserver(
            fake.run_cmd, fake.read_file, fake.which, fake.get_timestamp
        ).observe_hardware()
        device = hw.devices[0]
        self.assertEqual(
            device.coverage.state_for(ObservationFamily.DEVICE_MEMORY),
            CoverageState.NOT_OBSERVED,
        )
        self.assertEqual(
            device.coverage.state_for(ObservationFamily.DEVICE_DRIVER),
            CoverageState.NOT_OBSERVED,
        )
        # The facts still say "no evidence"; coverage explains that no method
        # was attempted at all (AD-04), instead of implying the source is absent.
        self.assertEqual(
            device.total_memory_bytes.state, ObservationState.UNAVAILABLE
        )
        self.assertEqual(device.driver_name.state, ObservationState.UNAVAILABLE)

    def test_probed_backend_family_requires_evidence_or_an_outcome(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeObservation(
                canonical_id="llama.cpp",
                executable_path=ObservedValue(
                    state=ObservationState.OBSERVED,
                    value="/bin/llama",
                    source="which:llama",
                ),
                raw_version=ObservedValue(
                    state=ObservationState.UNAVAILABLE,
                    source="which:llama",
                    detail="binary unavailable",
                ),
                detected_backends=(),
                coverage=ObservationCoverage(entries=(
                    CoverageEntry(
                        ObservationFamily.RUNTIME_BACKENDS,
                        CoverageState.OBSERVED,
                    ),
                )),
            )


class AcquisitionErrorBoundaryTests(unittest.TestCase):
    """Only failures of the external operation become ERROR observations."""

    def _hardware_with_runner(self, runner) -> HardwareObservation:
        fake = FakeEnvironment(
            files={"/proc/meminfo": "MemTotal: 8192 kB\n"},
            binaries={"lspci": "/usr/bin/lspci"},
        )
        obs = EnvironmentObserver(
            runner, fake.read_file, fake.which, fake.get_timestamp
        )
        return obs.observe_hardware()

    def test_timeout_is_an_acquisition_error(self) -> None:
        def runner(command, timeout):
            raise TimeoutError("no answer within 2s")

        hw = self._hardware_with_runner(runner)
        self.assertEqual(hw.devices, ())
        self.assertIsNotNone(hw.acquisition_error)
        assert hw.acquisition_error is not None
        self.assertEqual(hw.acquisition_error.state, ObservationState.ERROR)
        self.assertIn("timeout", hw.acquisition_error.detail or "")

    def test_oserror_is_an_acquisition_error(self) -> None:
        def runner(command, timeout):
            raise OSError("permission denied")

        hw = self._hardware_with_runner(runner)
        self.assertIsNotNone(hw.acquisition_error)
        assert hw.acquisition_error is not None
        self.assertEqual(hw.acquisition_error.state, ObservationState.ERROR)
        self.assertIn("os error", hw.acquisition_error.detail or "")

    def test_programming_defects_propagate(self) -> None:
        for error in (
            TypeError("bad arity"),
            AttributeError("missing attribute"),
            KeyError("missing key"),
            AssertionError("invariant broken"),
            NotImplementedError("not implemented"),
        ):
            with self.subTest(error=type(error).__name__):

                def runner(command, timeout, failure=error):
                    raise failure

                with self.assertRaises(type(error)):
                    self._hardware_with_runner(runner)

    def test_acquisition_errors_contract_is_closed(self) -> None:
        self.assertEqual(ACQUISITION_ERRORS, (TimeoutError, OSError))
        for defect in (TypeError, AttributeError, KeyError, AssertionError):
            self.assertNotIn(defect, ACQUISITION_ERRORS)


class ObservationImportBoundaryTests(unittest.TestCase):
    """AD-06: Observation stays autonomous; legacy modules are never imported."""

    _FORBIDDEN = (
        "app.hardware",
        "app.runtimes",
        "app.gpu_setup",
        "app.platform",
        "app.compatibility",
        "app.compatibility_domain",
        "app.compatibility_evaluator",
        "app.compatibility_knowledge",
        "app.evaluation_adapter",
        "app.evaluation_pipeline",
        "app.evaluation_policy",
        "app.knowledge_bridge",
        "app.initial_knowledge",
        "app.model_domain",
        "app.selection",
        "app.execution",
        "app.execution_service",
        "app.run_service",
        "app.runner",
        "app.chat",
        "app.main",
        "app.api",
    )

    def test_observation_modules_import_no_project_module(self) -> None:
        app_dir = Path(__file__).resolve().parent.parent / "app"
        for filename in ("observation_domain.py", "observation_probe.py"):
            tree = ast.parse((app_dir / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        with self.subTest(module=filename, imported=alias.name):
                            self.assertNotIn(alias.name, self._FORBIDDEN)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    target = f"app.{module}" if node.level else module
                    with self.subTest(module=filename, imported=target):
                        self.assertNotIn(target, self._FORBIDDEN)

    def test_stdlib_platform_is_not_confused_with_app_platform(self) -> None:
        # ``import platform`` (stdlib, used by the platform probe) is allowed;
        # ``from .platform import ...`` (legacy module) is forbidden.
        app_dir = Path(__file__).resolve().parent.parent / "app"
        for filename in ("observation_domain.py", "observation_probe.py"):
            tree = ast.parse((app_dir / filename).read_text(encoding="utf-8"))
            relative_modules = {
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.level
            }
            plain_imports = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            with self.subTest(module=filename):
                self.assertNotIn("platform", relative_modules)
                self.assertNotIn("app.platform", plain_imports)
                # Every relative import stays inside the observation package.
                for module in relative_modules:
                    self.assertEqual(module, "observation_domain")
        probe_tree = ast.parse(
            (app_dir / "observation_probe.py").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Import)
                and any(alias.name == "platform" for alias in node.names)
                for node in ast.walk(probe_tree)
            )
        )


if __name__ == "__main__":
    unittest.main()
