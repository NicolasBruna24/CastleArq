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

"""Block B4 tests: the CLI ``diagnose`` surface (observation only)."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from app import gpu_diagnosis
from app import main as cli
from app.gpu_diagnosis import DiagnosisStatus
from app.gpu_recipes import recipes
from app.gpu_setup import FunctionalCheck, GpuSoftwareStatus
from app.hardware import (
    CPUInfo,
    GPUInfo,
    HardwareSnapshot,
    MemoryInfo,
    detect_platform,
)
from app.runtimes import BackendStatus, RuntimeStatus


def _hardware(operating_system: str = "Linux", gpus=()) -> HardwareSnapshot:
    return HardwareSnapshot(
        operating_system=operating_system,
        architecture="x86_64",
        cpu=CPUInfo(model="Test CPU"),
        memory=MemoryInfo(total_bytes=8 * 1024 ** 3),
        gpus=list(gpus),
    )


def _gpu(
    vendor: str = "Intel",
    name: str = "Arc B580",
    pci_id: str = "8086:e20b",
    driver: str = "xe",
) -> GPUInfo:
    return GPUInfo(name=name, vendor=vendor, pci_id=pci_id, driver=driver)


def _software(kernel=True, drm=True, vulkan=True) -> GpuSoftwareStatus:
    return GpuSoftwareStatus(
        kernel_driver=FunctionalCheck(kernel, "detail", "test"),
        drm_device=FunctionalCheck(drm, "detail", "test"),
        vulkan=FunctionalCheck(vulkan, "detail", "test"),
    )


def _runtimes():
    return [
        RuntimeStatus("llama.cpp / llama.app", True, True, False, ("Vulkan", "CPU"))
    ]


def _backends():
    return [BackendStatus("Vulkan", True), BackendStatus("CPU", True)]


class GpuDiagnosisPresentationTests(unittest.TestCase):
    def _report(
        self,
        software,
        *,
        runtime="llama.cpp / llama.app",
        backend="Vulkan",
        platform="linux",
        gpus=(),
    ) -> cli.GpuDiagnosisReport:
        return cli.build_gpu_diagnosis_report(
            hardware=_hardware(gpus=gpus),
            software=software,
            runtime=runtime,
            backend=backend,
            platform=platform,
        )

    def test_ready_is_presented(self):
        report = self._report(_software(True, True, True))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertEqual(report.diagnosis.status, DiagnosisStatus.READY)
        self.assertIn("Overall status: READY", text)
        self.assertIn("Kernel driver: READY", text)
        self.assertIn("DRM render device: READY", text)
        self.assertIn("Vulkan runtime: READY", text)
        self.assertIn("No remediation required.", text)

    def test_missing_component_is_presented_with_recipe(self):
        report = self._report(_software(True, True, False))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertEqual(report.diagnosis.status, DiagnosisStatus.MISSING_COMPONENT)
        self.assertIn("Overall status: MISSING_COMPONENT", text)
        self.assertIn("Vulkan runtime: MISSING", text)
        self.assertIn("linux-llama-cpp-vulkan", text)
        self.assertEqual(
            report.recommendation.recipe_refs, ("linux-llama-cpp-vulkan",))

    def test_unknown_component_is_presented_without_recipe(self):
        report = self._report(_software(True, True, None))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertEqual(report.diagnosis.status, DiagnosisStatus.UNKNOWN)
        self.assertIn("Overall status: UNKNOWN", text)
        self.assertIn("Vulkan runtime: UNKNOWN", text)
        self.assertNotIn("linux-llama-cpp-vulkan", text)
        self.assertEqual(report.recommendation.recipe_refs, ())

    def test_multiple_missing_components_keep_all_recipes(self):
        report = self._report(_software(False, False, False))
        recipe_refs = report.recommendation.recipe_refs
        self.assertEqual(len(recipe_refs), 3)
        self.assertEqual(len(set(recipe_refs)), 3)
        text = cli.format_gpu_diagnosis_report(report)
        for recipe_ref in recipe_refs:
            self.assertIn(recipe_ref, text)
        self.assertIn("Kernel driver: MISSING", text)
        self.assertIn("DRM render device: MISSING", text)
        self.assertIn("Vulkan runtime: MISSING", text)

    def test_gpu_details_are_shown_when_available(self):
        report = self._report(_software(True, True, True), gpus=(_gpu(),))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertIn("Arc B580", text)
        self.assertIn("Vendor: Intel", text)
        self.assertIn("Driver: xe", text)

    def test_no_gpu_is_reported_as_not_detected(self):
        report = self._report(_software(True, True, True))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertIn("Not detected", text)

    def test_unmodelled_pair_reports_no_requirement_model(self):
        report = self._report(
            _software(True, True, True), runtime="Ollama", backend="Vulkan")
        text = cli.format_gpu_diagnosis_report(report)
        self.assertEqual(report.diagnosis.status, DiagnosisStatus.UNKNOWN)
        self.assertIn(
            "No requirement model for this runtime/backend pair.", text)
        self.assertEqual(report.recommendation.recipe_refs, ())

    def test_unknown_platform_has_no_linux_recipe(self):
        report = self._report(_software(True, True, False), platform="")
        text = cli.format_gpu_diagnosis_report(report)
        self.assertEqual(report.diagnosis.status, DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(report.recommendation.recipe_refs, ())
        self.assertIn("No compatible recipe found for this platform.", text)
        self.assertNotIn("linux-llama-cpp-vulkan", text)


class VendorInvarianceTests(unittest.TestCase):
    """Vendor is context only: it must never change the diagnosis (H1)."""

    def test_vendor_does_not_change_diagnosis(self):
        software = _software(True, True, False)
        for vendor, name, pci_id, driver in (
            ("Intel", "Arc B580", "8086:e20b", "xe"),
            ("NVIDIA", "RTX 3060", "10de:2503", "nvidia"),
            ("AMD", "Radeon RX 6700", "1002:73df", "amdgpu"),
        ):
            with self.subTest(vendor=vendor):
                report = cli.build_gpu_diagnosis_report(
                    hardware=_hardware(
                        gpus=(_gpu(vendor, name, pci_id, driver),)),
                    software=software,
                    runtime="llama.cpp / llama.app",
                    backend="Vulkan",
                    platform="linux",
                )
                self.assertEqual(
                    report.diagnosis.status, DiagnosisStatus.MISSING_COMPONENT)
                self.assertEqual(
                    report.recommendation.recipe_refs,
                    ("linux-llama-cpp-vulkan",),
                )


class PlatformDetectionTests(unittest.TestCase):
    def test_markers_are_deterministic(self):
        for operating_system, expected in (
            ("Linux", "linux"),
            ("  LINUX  ", "linux"),
            ("Windows 11", "windows"),
            ("macOS Sonoma", "macos"),
            ("Darwin", "macos"),
        ):
            with self.subTest(operating_system=operating_system):
                self.assertEqual(detect_platform(operating_system), expected)

    def test_pretty_name_falls_back_to_system(self):
        with patch("app.hardware.platform.system", return_value="Linux"):
            self.assertEqual(detect_platform("Ubuntu 24.04.3 LTS"), "linux")

    def test_unknown_platform_is_never_linux(self):
        with patch("app.hardware.platform.system", return_value="Solaris"):
            self.assertEqual(detect_platform("Unknown OS"), "")


class DiagnoseCommandTests(unittest.TestCase):
    def _run_diagnose(
        self,
        argv=("castlearq", "diagnose"),
        *,
        hardware=None,
        software=None,
        extra_patches=(),
    ):
        hardware = hardware if hardware is not None else _hardware()
        software = (
            software if software is not None else _software(True, True, False)
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", list(argv)))
            stack.enter_context(patch.object(sys, "stdout", new=stdout))
            stack.enter_context(patch.object(sys, "stderr", new=stderr))
            stack.enter_context(
                patch("app.main.detect_hardware", return_value=hardware))
            stack.enter_context(
                patch("app.main.detect_runtimes", return_value=_runtimes()))
            stack.enter_context(
                patch("app.main.detect_backends", return_value=_backends()))
            stack.enter_context(
                patch("app.main.diagnose_gpu_software", return_value=software))
            for target, kwargs in extra_patches:
                stack.enter_context(patch(target, **kwargs))
            try:
                code = cli.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0
        return code, stdout.getvalue(), stderr.getvalue()

    def test_diagnose_is_registered_in_help(self):
        buffer = io.StringIO()
        with patch.object(sys, "argv", ["castlearq", "--help"]), patch.object(
            sys, "stdout", new=buffer
        ):
            with self.assertRaises(SystemExit) as context:
                cli.main()
        self.assertEqual(context.exception.code, 0)
        self.assertIn("diagnose", buffer.getvalue())

    def test_diagnose_runs_with_simulated_data(self):
        code, out, err = self._run_diagnose()
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("CastleArq — GPU diagnosis", out)
        self.assertIn("Overall status: MISSING_COMPONENT", out)
        self.assertIn("linux-llama-cpp-vulkan", out)

    def test_diagnose_rejects_extra_arguments(self):
        code, _, err = self._run_diagnose(argv=["castlearq", "diagnose", "extra"])
        self.assertEqual(code, 2)
        self.assertIn("diagnose takes no arguments", err)

    def test_diagnose_rejects_flags(self):
        code, _, err = self._run_diagnose(
            argv=["castlearq", "diagnose", "--prompt", "x"])
        self.assertEqual(code, 2)
        self.assertIn("--prompt is not valid for command 'diagnose'", err)

    def test_platform_flows_from_detection(self):
        code, out, _ = self._run_diagnose(
            hardware=_hardware("Linux"), software=_software(True, True, False))
        self.assertEqual(code, 0)
        self.assertIn("Platform: linux", out)
        self.assertIn("linux-llama-cpp-vulkan", out)

        code, out, _ = self._run_diagnose(
            hardware=_hardware("Windows 11"),
            software=_software(True, True, False),
        )
        self.assertEqual(code, 0)
        self.assertIn("Platform: windows", out)
        self.assertNotIn("linux-llama-cpp-vulkan", out)

    def test_diagnose_passes_canonical_runtime_and_platform(self):
        with patch(
            "app.main.gpu_diagnosis.diagnose", wraps=gpu_diagnosis.diagnose
        ) as spy:
            code, _, _ = self._run_diagnose()
        self.assertEqual(code, 0)
        spy.assert_called_once()
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs["runtime"], "llama.cpp")
        self.assertEqual(kwargs["backend"], "Vulkan")
        self.assertEqual(kwargs["platform"], "linux")


class ReadOnlyGuaranteesTests(unittest.TestCase):
    def test_diagnose_does_not_touch_execution_pipeline(self):
        with ExitStack() as stack:
            runner = stack.enter_context(patch("app.main.LlamaCppRunner"))
            chat = stack.enter_context(patch("app.main.start_chat_session"))
            run_model = stack.enter_context(patch("app.main.run_model"))
            chat_model = stack.enter_context(patch("app.main.chat_model"))
            run_download = stack.enter_context(patch("app.main.run_download"))
            stack.enter_context(
                patch("app.main.detect_hardware", return_value=_hardware()))
            stack.enter_context(
                patch("app.main.detect_runtimes", return_value=_runtimes()))
            stack.enter_context(
                patch("app.main.detect_backends", return_value=_backends()))
            stack.enter_context(
                patch(
                    "app.main.diagnose_gpu_software",
                    return_value=_software(True, True, True),
                )
            )
            stack.enter_context(
                patch.object(sys, "argv", ["castlearq", "diagnose"]))
            stack.enter_context(patch.object(sys, "stdout", new=io.StringIO()))
            self.assertEqual(cli.main(), 0)
        for mock in (runner, chat, run_model, chat_model, run_download):
            mock.assert_not_called()

    def test_only_read_only_detectors_are_used(self):
        with ExitStack() as stack:
            hardware = stack.enter_context(
                patch("app.main.detect_hardware", return_value=_hardware()))
            runtimes = stack.enter_context(
                patch("app.main.detect_runtimes", return_value=_runtimes()))
            backends = stack.enter_context(
                patch("app.main.detect_backends", return_value=_backends()))
            software = stack.enter_context(
                patch(
                    "app.main.diagnose_gpu_software",
                    return_value=_software(True, True, False),
                )
            )
            capability = stack.enter_context(
                patch("app.main.detect_llama_capability"))
            stack.enter_context(
                patch.object(sys, "argv", ["castlearq", "diagnose"]))
            stack.enter_context(patch.object(sys, "stdout", new=io.StringIO()))
            self.assertEqual(cli.main(), 0)
        hardware.assert_called_once()
        runtimes.assert_called_once()
        backends.assert_called_once()
        software.assert_called_once()
        capability.assert_not_called()

    def test_catalog_has_nothing_to_install(self):
        for recipe in recipes():
            self.assertEqual(recipe.install_commands, ())
            self.assertEqual(recipe.verify_commands, ())

    def test_diagnose_output_has_no_privileged_or_install_commands(self):
        report = cli.build_gpu_diagnosis_report(
            hardware=_hardware(),
            software=_software(False, False, False),
            runtime="llama.cpp / llama.app",
            backend="Vulkan",
            platform="linux",
        )
        text = cli.format_gpu_diagnosis_report(report).lower()
        for forbidden in ("sudo", "apt-get", "dnf", "pacman", "pip install"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
