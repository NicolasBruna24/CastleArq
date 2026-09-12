import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.hardware import (
    LinuxHardwareDetector,
    parse_cpuinfo,
    parse_external_gpu_memory,
    parse_lspci,
    parse_meminfo,
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

    def test_parse_external_memory(self):
        observations = parse_external_gpu_memory(
            "Vulkan0: Intel Graphics (32656 MiB, 28996 MiB free)", "vulkan"
        )
        self.assertEqual(observations[0][0], "Intel Graphics")
        self.assertEqual(observations[0][1], 32656 * 1024**2)
        self.assertEqual(observations[0][2], 28996 * 1024**2)
        self.assertEqual(observations[0][3], "Vulkan")

    def test_gpu_vram_from_sysfs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            card = root / "class/drm/card0/device"
            card.mkdir(parents=True)
            (card / "mem_info_vram_total").write_text(str(32 * 1024**3))
            (card / "mem_info_vram_used").write_text(str(4 * 1024**3))
            snapshot = LinuxHardwareDetector(
                lambda command: (
                    "00:02.0 VGA compatible controller: Intel Corporation "
                    "Graphics [8086:e223]"
                    if command == ("lspci", "-nn")
                    else None
                ),
                root,
                root,
                lambda _: None,
            ).detect()
        self.assertEqual(snapshot.gpus[0].vram_bytes, 32 * 1024**3)
        self.assertEqual(snapshot.gpus[0].vram_available_bytes, 28 * 1024**3)
        self.assertEqual(snapshot.gpus[0].sources["vram"], "sysfs")

    def test_gpu_vram_from_vulkan_when_sysfs_is_unknown(self):
        def run(command):
            if command == ("lspci", "-nn"):
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


if __name__ == "__main__":
    unittest.main()
