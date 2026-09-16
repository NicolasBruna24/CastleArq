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

"""Tests for the B6 platform detection domain (``app.platform``)."""

import ast
import unittest
from pathlib import Path

from app.platform import PlatformInfo, detect_platform_info


UBUNTU = (
    'PRETTY_NAME="Ubuntu 26.04.1 LTS"\n'
    "ID=ubuntu\n"
    'VERSION_ID="26.04"\n'
    "ID_LIKE=debian\n"
)
DEBIAN = (
    'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n'
    "ID=debian\n"
    'VERSION_ID="12"\n'
)
FEDORA = (
    'NAME="Fedora Linux"\n'
    "ID=fedora\n"
    'VERSION_ID="40"\n'
    'PRETTY_NAME="Fedora Linux 40 (Container Image)"\n'
)
ARCH = (
    'PRETTY_NAME="Arch Linux"\n'
    "ID=arch\n"
    "BUILD_ID=rolling\n"
)
MINT = (
    'PRETTY_NAME="Linux Mint 22"\n'
    "ID=linuxmint\n"
    'VERSION_ID="22"\n'
    'ID_LIKE="debian ubuntu"\n'
)
EXOTIC = (
    'PRETTY_NAME="MysteryOS 1.0"\n'
    "ID=mysteryos\n"
    'VERSION_ID="1.0"\n'
)
MINIMAL = "ID=mysteryos\n"


def _release_reader(text: str):
    def read(_path: Path) -> str:
        return text
    return read


def _linux(**kwargs):
    kwargs.setdefault("system", "Linux")
    kwargs.setdefault("machine", "x86_64")
    return detect_platform_info(**kwargs)


class LinuxDistributionTests(unittest.TestCase):
    def test_ubuntu(self):
        info = _linux(read=_release_reader(UBUNTU))
        self.assertEqual(
            info,
            PlatformInfo(
                platform="linux",
                distribution="ubuntu",
                distribution_version="26.04",
                architecture="x86_64",
                pretty_name="Ubuntu 26.04.1 LTS",
            ),
        )

    def test_debian(self):
        info = _linux(read=_release_reader(DEBIAN))
        self.assertEqual(info.platform, "linux")
        self.assertEqual(info.distribution, "debian")
        self.assertEqual(info.distribution_version, "12")

    def test_fedora(self):
        info = _linux(read=_release_reader(FEDORA))
        self.assertEqual(info.distribution, "fedora")
        self.assertEqual(info.distribution_version, "40")

    def test_arch_without_version(self):
        info = _linux(read=_release_reader(ARCH))
        self.assertEqual(info.distribution, "arch")
        self.assertEqual(info.distribution_version, "")

    def test_alias_uses_id_like_family(self):
        info = _linux(read=_release_reader(MINT))
        self.assertEqual(info.distribution, "debian")

    def test_unknown_distribution_is_never_assumed(self):
        info = _linux(read=_release_reader(EXOTIC))
        self.assertEqual(info.distribution, "")
        self.assertEqual(info.distribution_version, "1.0")

    def test_missing_fields_stay_empty(self):
        info = _linux(read=_release_reader(MINIMAL))
        self.assertEqual(info.distribution, "")
        self.assertEqual(info.distribution_version, "")
        self.assertEqual(info.pretty_name, "")



class UnknownEvidenceTests(unittest.TestCase):
    def test_missing_os_release_is_all_unknown(self):
        def boom(_path):
            raise OSError("nope")
        info = _linux(read=boom)
        self.assertEqual(
            info,
            PlatformInfo(platform="linux", architecture="x86_64"),
        )

    def test_unknown_platform_is_never_linux(self):
        info = detect_platform_info(
            operating_system="Unknown OS",
            system="Solaris",
            machine="sun4v",
        )
        self.assertEqual(info, PlatformInfo(architecture="sun4v"))

    def test_empty_platform_is_not_assumed_linux(self):
        info = detect_platform_info(
            operating_system="", system="", machine="arm64")
        self.assertEqual(info, PlatformInfo(architecture="arm64"))


class WindowsMacOSTests(unittest.TestCase):
    def test_windows(self):
        info = detect_platform_info(
            system="Windows", machine="AMD64", operating_system="Windows 11")
        self.assertEqual(info.platform, "windows")
        self.assertEqual(info.distribution, "")
        self.assertEqual(info.distribution_version, "")
        self.assertEqual(info.pretty_name, "")

    def test_macos_from_darwin(self):
        info = detect_platform_info(
            system="Darwin", machine="arm64", operating_system="")
        self.assertEqual(info.platform, "macos")
        self.assertEqual(info.distribution, "")


class VersionAndPrettyNameTests(unittest.TestCase):
    def test_version_id_is_kept_verbatim(self):
        info = _linux(read=_release_reader(UBUNTU))
        self.assertEqual(info.distribution_version, "26.04")

    def test_pretty_name_missing_is_empty(self):
        info = _linux(read=_release_reader("ID=ubuntu\nVERSION_ID=26.04\n"))
        self.assertEqual(info.pretty_name, "")


class ArchitectureTests(unittest.TestCase):
    def test_existing_convention_is_reused(self):
        info = detect_platform_info(
            system="Linux", machine="x86_64", read=_release_reader(UBUNTU))
        self.assertEqual(info.architecture, "x86_64")

    def test_unknown_machine_follows_existing_unknown_convention(self):
        info = detect_platform_info(system="Linux", machine="")
        self.assertEqual(info.architecture, "Unknown")


class DeterminismAndImmutabilityTests(unittest.TestCase):
    def test_same_input_same_model(self):
        first = _linux(read=_release_reader(UBUNTU))
        second = _linux(read=_release_reader(UBUNTU))
        self.assertEqual(first, second)

    def test_model_is_frozen(self):
        info = _linux(read=_release_reader(UBUNTU))
        with self.assertRaises(Exception):
            info.platform = "windows"


class SafetyTests(unittest.TestCase):
    def test_module_does_not_execute_commands_or_network(self):
        source = Path("app/platform.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        banned = {"subprocess", "socket", "urllib", "http", "shutil"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], banned)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                self.assertNotIn((node.module or "").split(".")[0], banned)
        self.assertNotIn("shell=", source)

    def test_os_release_is_only_read_on_linux(self):
        calls = []

        def spy(_path):
            calls.append(_path)
            return UBUNTU

        detect_platform_info(system="Windows", machine="AMD64", read=spy)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
