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

"""Block A tests: read-only GPU software probes (no real hardware needed)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from app import gpu_setup as gs

UBUNTU_RELEASE = """PRETTY_NAME="Ubuntu 24.04.1 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.1 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
"""

DEBIAN_RELEASE = """PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
VERSION="12 (bookworm)"
ID=debian
HOME_URL="https://www.debian.org/"
"""

MINIMAL_RELEASE = "NAME=Weird\n"


def _no_run(command):
    raise AssertionError(f"command must not run: {command}")


def _no_which(name):
    return None


class OsReleaseTests(unittest.TestCase):
    def test_ubuntu_parsing(self):
        info = gs.parse_os_release(UBUNTU_RELEASE)
        self.assertEqual(
            (info.id, info.version_id, info.id_like, info.pretty_name),
            ("ubuntu", "24.04", ("debian",), "Ubuntu 24.04.1 LTS"))

    def test_debian_like_parsing(self):
        info = gs.parse_os_release(DEBIAN_RELEASE)
        self.assertEqual(info.id, "debian")
        self.assertEqual(info.version_id, "12")
        self.assertEqual(info.id_like, ())
        self.assertIn("Debian", info.pretty_name or "")

    def test_missing_fields(self):
        info = gs.parse_os_release(MINIMAL_RELEASE)
        self.assertIsNone(info.id)
        self.assertIsNone(info.version_id)
        self.assertEqual(info.id_like, ())
        self.assertIsNone(info.pretty_name)
        self.assertEqual(gs.parse_os_release(""), gs.OsReleaseInfo())

    def test_read_failure_is_unknown(self):
        def boom(_path):
            raise OSError("nope")
        self.assertEqual(gs.read_os_release_info(read=boom), gs.OsReleaseInfo())
        info = gs.read_os_release_info(read=lambda _p: UBUNTU_RELEASE)
        self.assertEqual(info.id, "ubuntu")


class KernelDriverTests(unittest.TestCase):
    def test_driver_found(self):
        check = gs.probe_kernel_driver("xe")
        self.assertTrue(check.passed)
        self.assertIn("xe", check.detail)
        self.assertIn("sysfs", check.source)

    def test_driver_unknown(self):
        for value in (None, "", "Unknown"):
            check = gs.probe_kernel_driver(value)
            self.assertIsNone(check.passed)


class DrmTests(unittest.TestCase):
    def test_devices_exist(self):
        check = gs.probe_drm_devices(
            dri_entries=["by-path", "card0", "renderD128"])
        self.assertTrue(check.passed)
        self.assertIn("renderD128", check.detail)

    def test_devices_absent(self):
        check = gs.probe_drm_devices(dri_entries=["by-path"])
        self.assertFalse(check.passed)

    def test_unreadable_path_is_unknown(self):
        check = gs.probe_drm_devices(dri_path="/nonexistent-xyz")
        self.assertIsNone(check.passed)


class VulkanTests(unittest.TestCase):
    def test_icd_exists(self):
        self.assertEqual(
            gs.find_vulkan_icds(icd_files=["/usr/share/vulkan/icd.d/x.json"]),
            ("/usr/share/vulkan/icd.d/x.json",))

    def test_icd_absent(self):
        self.assertEqual(gs.find_vulkan_icds(icd_dirs=["/nonexistent-xyz"]), ())

    def test_icd_without_functional_evidence_is_unknown(self):
        check = gs.probe_vulkan(
            run=_no_run,
            which=_no_which,
            icd_files=["/usr/share/vulkan/icd.d/intel.json"],
            probe_llama=False,
        )
        self.assertIsNone(check.passed)
        self.assertIn("unknown", check.detail)

    def test_no_icd_no_probe_is_unknown(self):
        check = gs.probe_vulkan(
            run=_no_run, which=_no_which, icd_files=[], probe_llama=False)
        self.assertIsNone(check.passed)

    def test_llama_confirms_vulkan(self):
        check = gs.probe_vulkan(
            run=_no_run,
            which=_no_which,
            icd_files=[],
            llama_devices="Vulkan0: Intel(R) Graphics",
        )
        self.assertTrue(check.passed)
        self.assertIn("llama", check.source)

    def test_llama_without_vulkan_is_false(self):
        check = gs.probe_vulkan(
            run=_no_run,
            which=_no_which,
            icd_files=["/usr/share/vulkan/icd.d/x.json"],
            llama_devices="CPU0: cpu",
        )
        self.assertFalse(check.passed)

    def test_llama_unavailable_is_unknown(self):
        check = gs.probe_vulkan(
            run=_no_run, which=_no_which, icd_files=[], llama_devices=None)
        self.assertIsNone(check.passed)


class OpenClTests(unittest.TestCase):
    def test_clinfo_functional(self):
        check = gs.probe_opencl(
            run=lambda cmd: "Platform 0: Intel\n",
            which=lambda name: "/usr/bin/clinfo",
        )
        self.assertTrue(check.passed)

    def test_clinfo_absent_is_unknown(self):
        check = gs.probe_opencl(run=_no_run, which=_no_which)
        self.assertIsNone(check.passed)

    def test_clinfo_failure_is_unknown(self):
        check = gs.probe_opencl(
            run=lambda cmd: None, which=lambda name: "/usr/bin/clinfo")
        self.assertIsNone(check.passed)


class LevelZeroTests(unittest.TestCase):
    def test_level_zero_known(self):
        check = gs.probe_level_zero(
            run=_no_run,
            which=_no_which,
            libze_paths=["/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1"],
        )
        self.assertTrue(check.passed)

    def test_level_zero_unknown(self):
        check = gs.probe_level_zero(
            run=_no_run, which=_no_which, libze_paths=[])
        self.assertIsNone(check.passed)


class RobustnessTests(unittest.TestCase):
    B70_DEVICES = "Vulkan0: Intel(R) Arc Pro B70 Graphics [8086:e223]"

    def test_command_failure_does_not_crash(self):
        status = gs.diagnose_gpu_software(
            driver="xe",
            run=lambda cmd: None,
            which=_no_which,
            dri_entries=["card0", "renderD128"],
            icd_files=[],
            llama_devices=None,
            probe_llama=False,
            libze_paths=[],
        )
        self.assertTrue(status.kernel_driver.passed)
        self.assertTrue(status.drm_device.passed)
        self.assertIsNone(status.vulkan.passed)

    def test_b70_like_fixture_without_hardware(self):
        status = gs.diagnose_gpu_software(
            driver="xe",
            run=_no_run,
            which=_no_which,
            dri_entries=["card0", "renderD128"],
            icd_files=["/usr/share/vulkan/icd.d/intel_icd.x86_64.json"],
            llama_devices=self.B70_DEVICES,
            libze_paths=["/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1"],
        )
        self.assertTrue(status.kernel_driver.passed)
        self.assertTrue(status.drm_device.passed)
        self.assertTrue(status.vulkan.passed)
        self.assertTrue(status.level_zero.passed)

    def test_no_shell_execution(self):
        tree = ast.parse(Path(gs.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            self.assertFalse(
                isinstance(node, ast.Call)
                and getattr(getattr(node, "func", None), "attr", "") == "system",
                "os.system is forbidden",
            )
        source = Path(gs.__file__).read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertNotIn("sudo", source)
        self.assertNotIn("apt install", source)

    def test_no_mutation_primitives(self):
        source = Path(gs.__file__).read_text(encoding="utf-8")
        for banned in ("os.system", "shell=True", "sudo ", "apt ", "dnf ",
                       "pacman ", "curl | bash"):
            self.assertNotIn(banned, source)
        statuses = (
            gs.GpuSoftwareStatus(),
            gs.diagnose_gpu_software(
                run=lambda cmd: None, which=_no_which,
                dri_entries=[], icd_files=[], probe_llama=False,
                libze_paths=[]),
        )
        for status in statuses:
            self.assertIsInstance(status, gs.GpuSoftwareStatus)


if __name__ == "__main__":
    unittest.main()

