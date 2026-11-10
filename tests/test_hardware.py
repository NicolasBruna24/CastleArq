
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
from pathlib import Path
from tempfile import TemporaryDirectory

from castlearq.hardware import (
    GPUInfo,
    LinuxHardwareDetector,
    parse_cpuinfo,
    parse_external_gpu_memory,
    parse_lspci,
    parse_meminfo,
    _normalize_pci_address,
)


class HardwareTests(unittest.TestCase):
    def test_parse_cpuinfo(self):
        info = parse_cpuinfo("model name\t: Test CPU\nprocessor\t: 0\nprocessor\t: 1\n", "x86_64")
        self.assertEqual(info.model, "Test CPU")
        self.assertEqual(info.cores, 2)

    def test_parse_meminfo(self):
        self.assertEqual(parse_meminfo("MemTotal:       49152000 kB\n").total_bytes, 49152000 * 1024)

    def test_parse_lspci(self):
        gpus = parse_lspci(
            "00:02.0 VGA compatible controller: Intel Corporation "
            "Battlemage G31 [8086:e223]"
        )
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].vendor, "Intel")
        self.assertEqual(gpus[0].pci_id, "8086:e223")
        self.assertEqual(
            gpus[0].name, "Intel Corporation Battlemage G31"
        )

    def test_parse_lspci_explicit_domain_with_class_id(self):
        gpus = parse_lspci(
            "0000:03:00.0 VGA compatible controller [0300]: Intel Corporation "
            "Battlemage G31 [Intel Graphics] [8086:e223]"
        )
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].vendor, "Intel")
        self.assertEqual(gpus[0].pci_id, "8086:e223")
        self.assertEqual(
            gpus[0].name, "Intel Corporation Battlemage G31 [Intel Graphics]"
        )
        self.assertEqual(gpus[0].pci_address, "0000:03:00.0")

    def test_parse_lspci_3d_controller(self):
        gpus = parse_lspci(
            "0000:01:00.0 3D controller: NVIDIA Corporation GA102 [10de:2204]"
        )
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].vendor, "NVIDIA")
        self.assertEqual(gpus[0].pci_id, "10de:2204")
        self.assertEqual(gpus[0].name, "NVIDIA Corporation GA102")

    def test_parse_lspci_display_controller(self):
        gpus = parse_lspci(
            "0000:02:00.0 Display controller: AMD Corporation Device [1002:7df0]"
        )
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].vendor, "AMD")
        self.assertEqual(gpus[0].pci_id, "1002:7df0")
        self.assertEqual(gpus[0].name, "AMD Corporation Device")

    def test_parse_lspci_quoted_mm_format(self):
        gpus = parse_lspci(
            '00:02.0 VGA compatible controller [0300]: Intel Corporation '
            '"Battlemage G31" [8086:e223]'
        )
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].name, "Battlemage G31")

    def test_parse_external_memory(self):
        observations = parse_external_gpu_memory(
            "Vulkan0: Intel Graphics (32656 MiB, 28996 MiB free)", "vulkan"
        )
        self.assertEqual(observations[0][0], "Intel Graphics")
        self.assertEqual(observations[0][1], 32656 * 1024**2)
        self.assertEqual(observations[0][2], 28996 * 1024**2)
        self.assertEqual(observations[0][3], "Vulkan")

    def test_gpu_vram_from_sysfs_matches_by_pci_address(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card = drm / "card0"
            card.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (device_dir / "mem_info_vram_total").write_text(str(32 * 1024**3))
            (device_dir / "mem_info_vram_used").write_text(str(4 * 1024**3))
            # ``card0/device`` is a symlink to the PCI device directory whose
            # name is the PCI address; correlation must use the address, never
            # the card index.
            (card / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation "
                    "Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.pci_address, "0000:00:02.0")
        self.assertEqual(gpu.vram_bytes, 32 * 1024**3)
        self.assertEqual(gpu.vram_available_bytes, 28 * 1024**3)
        self.assertEqual(gpu.sources["vram"], "sysfs")

    def test_gpu_vram_from_vulkan_when_sysfs_is_unknown(self):
        def run(command):
            if command == ("lspci", "-D", "-nn"):
                return "00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
            if command == ("vulkaninfo", "--summary"):
                return "Vulkan0: Intel Graphics (32656 MiB, 28996 MiB free)"
            return None

        with TemporaryDirectory() as directory:
            snapshot = LinuxHardwareDetector(
                run, Path(directory), Path(directory),
                lambda name: "/usr/bin/vulkaninfo" if name == "vulkaninfo" else None,
            ).detect()
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.sources["vram"], "vulkan")
        self.assertIn("Vulkan", gpu.backends)

    def test_detector_handles_missing_commands_and_proc_files(self):
        with TemporaryDirectory() as directory:
            snapshot = LinuxHardwareDetector(lambda _: None, Path(directory), Path(directory)).detect()
        self.assertEqual(snapshot.cpu.model, "Unknown")
        self.assertIsNone(snapshot.memory.total_bytes)
        self.assertEqual(snapshot.gpus, [])

    def test_invalid_outputs_are_safe(self):
        self.assertEqual(parse_lspci("invalid output"), [])
        self.assertIsNone(parse_meminfo("MemTotal: invalid").total_bytes)

    def test_external_command_error_is_safe(self):
        with TemporaryDirectory() as directory:
            snapshot = LinuxHardwareDetector(
                lambda _: None, Path(directory), Path(directory), lambda _: "/bin/tool"
            ).detect()
        self.assertEqual(snapshot.gpus, [])

    def test_vendor_detection_for_nvidia_and_amd(self):
        self.assertEqual(parse_lspci("01:00.0 VGA compatible controller: Device [10de:1234]")[0].vendor, "NVIDIA")
        self.assertEqual(parse_lspci("02:00.0 VGA compatible controller: Device [1002:5678]")[0].vendor, "AMD")

    def test_parse_lspci_explicit_pci_domain(self):
        gpus = parse_lspci("0000:01:00.0 VGA compatible controller: NVIDIA Corporation GK107 [10de:0fea]")
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].pci_address, "0000:01:00.0")
        self.assertEqual(gpus[0].pci_id, "10de:0fea")
        self.assertEqual(gpus[0].device_id, "0fea")
        self.assertEqual(gpus[0].vendor, "NVIDIA")

    def test_parse_lspci_omitted_domain_is_normalized(self):
        gpus = parse_lspci("01:00.0 VGA compatible controller: NVIDIA Corporation GK107 [10de:0fea]")
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].pci_address, "0000:01:00.0")

    def test_apply_sysfs_intel_gpu(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card = drm / "card0"
            card.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (card / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.pci_address, "0000:00:02.0")
        self.assertEqual(gpu.vendor, "Intel")
        self.assertIsNone(gpu.vram_bytes)

    def test_apply_sysfs_correlates_by_address_not_by_index(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"

            def make_card(card_name, address, total):
                card = drm / card_name
                card.mkdir(parents=True)
                device_dir = root / "devices" / "pci0000:01" / address
                device_dir.mkdir(parents=True)
                (device_dir / "mem_info_vram_total").write_text(str(total))
                (card / "device").symlink_to(device_dir)

            make_card("card0", "0000:01:00.0", 16 * 1024**3)
            make_card("card1", "0000:00:02.0", 8 * 1024**3)

            def lspci(command):
                if command != ("lspci", "-D", "-nn"):
                    return None
                return (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]\n"
                    "0000:01:00.0 VGA compatible controller: NVIDIA Corporation GK107 [10de:0fea]\n"
                )

            snapshot = LinuxHardwareDetector(lspci, root, root, lambda _: None).detect()

        self.assertEqual(len(snapshot.gpus), 2)
        by_address = {gpu.pci_address: gpu for gpu in snapshot.gpus}
        intel = by_address["0000:00:02.0"]
        nvidia = by_address["0000:01:00.0"]
        self.assertEqual(intel.vendor, "Intel")
        self.assertEqual(nvidia.vendor, "NVIDIA")
        self.assertEqual(intel.vram_bytes, 8 * 1024**3)
        self.assertEqual(nvidia.vram_bytes, 16 * 1024**3)
        self.assertEqual(intel.sources["vram"], "sysfs")
        self.assertEqual(nvidia.sources["vram"], "sysfs")

    def test_apply_sysfs_intel_and_nvidia(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            for card_name, address in (("card0", "0000:00:02.0"), ("card1", "0000:01:00.0")):
                card = drm / card_name
                card.mkdir(parents=True)
                device_dir = root / "devices" / "pci0000:01" / address
                device_dir.mkdir(parents=True)
                (card / "device").symlink_to(device_dir)
            lines = [
                "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]",
                "0000:01:00.0 VGA compatible controller: NVIDIA Corporation GK107 [10de:0fea]",
            ]
            snapshot = LinuxHardwareDetector(
                lambda command: "\n".join(lines) if command == ("lspci", "-D", "-nn") else None,
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 2)
        by_address = {gpu.pci_address: gpu for gpu in snapshot.gpus}
        self.assertEqual(by_address["0000:00:02.0"].vendor, "Intel")
        self.assertEqual(by_address["0000:01:00.0"].vendor, "NVIDIA")

    def test_apply_sysfs_drm_without_lspci_match_is_ignored(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card = drm / "card0"
            card.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:01" / "0000:03:00.0"
            device_dir.mkdir(parents=True)
            (device_dir / "mem_info_vram_total").write_text(str(16 * 1024**3))
            (card / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        self.assertEqual(snapshot.gpus[0].pci_address, "0000:00:02.0")
        self.assertIsNone(snapshot.gpus[0].vram_bytes)
        self.assertEqual(snapshot.gpus[0].sources, {"gpu": "lspci"})

    def test_apply_sysfs_missing_or_invalid_device_link_is_safe(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card0 = drm / "card0"
            card0.mkdir(parents=True)
            card1 = drm / "card1"
            card1.mkdir(parents=True)
            (card1 / "device").symlink_to(root / "devices" / "does-not-exist")
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        self.assertIsNone(snapshot.gpus[0].vram_bytes)

    def test_apply_sysfs_ignores_non_card_drm_entries(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            for name in ("renderD128", "controlD64", "card1"):
                (drm / name).mkdir(parents=True)
            card0 = drm / "card0"
            card0.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (card0 / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        self.assertEqual(snapshot.gpus[0].pci_address, "0000:00:02.0")

    def test_apply_sysfs_incomplete_vram_is_safe(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card = drm / "card0"
            card.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (device_dir / "mem_info_vram_total").write_text(str(8 * 1024**3))
            (card / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.vram_bytes, 8 * 1024**3)
        self.assertIsNone(gpu.vram_available_bytes)

    def test_with_gpu_preserves_pci_address(self):
        original = GPUInfo(
            name="Test",
            vendor="Intel",
            pci_id="8086:e223",
            device_id="e223",
            pci_address="0000:00:02.0",
        )
        updated = LinuxHardwareDetector._with_gpu(
            original,
            vram_bytes=8 * 1024**3,
            source="sysfs",
            driver="i915",
        )
        self.assertEqual(updated.pci_address, "0000:00:02.0")
        self.assertEqual(updated.vram_bytes, 8 * 1024**3)
        self.assertEqual(updated.driver, "i915")
        self.assertEqual(updated.pci_id, "8086:e223")
        self.assertEqual(updated.device_id, "e223")

    def test_gpu_info_positional_construction_still_works(self):
        gpu = GPUInfo(
            "Intel Graphics",
            "Intel",
            "8086:e223",
            "e223",
            8 * 1024**3,
            None,
            {"gpu": "lspci"},
            [],
            "i915",
        )
        self.assertEqual(gpu.name, "Intel Graphics")
        self.assertEqual(gpu.vram_bytes, 8 * 1024**3)
        self.assertEqual(gpu.driver, "i915")
        self.assertIsNone(gpu.pci_address)

    def test_apply_sysfs_broken_symlink_to_detected_pci_address_is_safe(self):
        """Symlink roto que apunta a una dirección PCI detectada por lspci:
        no se asignan VRAM ni controlador desde ese enlace."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card0 = drm / "card0"
            card0.mkdir(parents=True)
            # El destino NO existe: symlink roto/dangling.
            target = root / "devices" / "pci0000:00" / "0000:00:02.0"
            (card0 / "device").symlink_to(target)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation "
                    "Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.pci_address, "0000:00:02.0")
        self.assertIsNone(gpu.vram_bytes)
        self.assertIsNone(gpu.vram_available_bytes)
        self.assertEqual(gpu.driver, "Unknown")
        self.assertEqual(gpu.sources, {"gpu": "lspci"})

    def test_apply_sysfs_duplicate_gpu_pci_address_is_not_assigned(self):
        """lspci reporta dos GPU con la misma dirección PCI: ambigüedad,
        no se asigna información de sysfs."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card0 = drm / "card0"
            card0.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (device_dir / "mem_info_vram_total").write_text(str(16 * 1024**3))
            (card0 / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "\n".join(
                        [
                            "0000:00:02.0 VGA compatible controller: Intel Corporation "
                            "Graphics [8086:e223]",
                            "0000:00:02.0 VGA compatible controller: Intel Corporation "
                            "Graphics [8086:e223]",
                        ]
                    )
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 2)
        for gpu in snapshot.gpus:
            self.assertIsNone(gpu.vram_bytes)
            self.assertIsNone(gpu.vram_available_bytes)
            self.assertEqual(gpu.driver, "Unknown")
            self.assertEqual(gpu.sources, {"gpu": "lspci"})

    def test_apply_sysfs_duplicate_drm_addresses_do_not_overwrite(self):
        """card0 y card1 resuelven al mismo BDF: no se asigna información de
        sysfs a esa GPU (ni VRAM, ni controlador, ni fuente sysfs)."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drm = root / "class/drm"
            card0 = drm / "card0"
            card1 = drm / "card1"
            card0.mkdir(parents=True)
            card1.mkdir(parents=True)
            device_dir = root / "devices" / "pci0000:00" / "0000:00:02.0"
            device_dir.mkdir(parents=True)
            (device_dir / "mem_info_vram_total").write_text(str(16 * 1024**3))
            (card0 / "device").symlink_to(device_dir)
            (card1 / "device").symlink_to(device_dir)
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "0000:00:02.0 VGA compatible controller: Intel Corporation "
                    "Graphics [8086:e223]"
                    if command == ("lspci", "-D", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(len(snapshot.gpus), 1)
        gpu = snapshot.gpus[0]
        self.assertEqual(gpu.pci_address, "0000:00:02.0")
        self.assertIsNone(gpu.vram_bytes)
        self.assertIsNone(gpu.vram_available_bytes)
        self.assertEqual(gpu.driver, "Unknown")
        self.assertEqual(gpu.sources, {"gpu": "lspci"})

    def test_normalize_pci_address_valid_ranges(self):
        self.assertEqual(_normalize_pci_address("0000:00:02.0"), "0000:00:02.0")
        self.assertEqual(_normalize_pci_address("FFFF:FF:1F.7"), "ffff:ff:1f.7")
        self.assertEqual(_normalize_pci_address("0000:00:00.0"), "0000:00:00.0")
        self.assertEqual(_normalize_pci_address("00:02.0"), "0000:00:02.0")

    def test_normalize_pci_address_invalid_ranges(self):
        self.assertIsNone(_normalize_pci_address("10000:00:02.0"))  # domain > FFFF
        self.assertIsNone(_normalize_pci_address("0000:100:02.0"))  # bus > FF
        self.assertIsNone(_normalize_pci_address("0000:00:20.0"))   # device > 1F
        self.assertIsNone(_normalize_pci_address("0000:00:00.8"))   # function > 7
        self.assertIsNone(_normalize_pci_address("0000:00:02"))     # missing function
        self.assertIsNone(_normalize_pci_address("not-a-pci-address"))


if __name__ == "__main__":
    unittest.main()
