import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.hardware import LinuxHardwareDetector, parse_cpuinfo, parse_lspci, parse_meminfo


class HardwareTests(unittest.TestCase):
    def test_parse_cpuinfo(self):
        info = parse_cpuinfo("model name\t: Test CPU\nprocessor\t: 0\nprocessor\t: 1\n", "x86_64")
        self.assertEqual(info.model, "Test CPU")
        self.assertEqual(info.cores, 2)

    def test_parse_meminfo(self):
        self.assertEqual(parse_meminfo("MemTotal:       49152000 kB\n").total_bytes, 49152000 * 1024)

    def test_parse_lspci(self):
        gpus = parse_lspci('00:02.0 "VGA compatible controller" "Intel Corporation" "Intel Arc Graphics"')
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0].vendor, "Intel")

    def test_detector_handles_missing_commands_and_proc_files(self):
        with TemporaryDirectory() as directory:
            snapshot = LinuxHardwareDetector(lambda _: None, Path(directory), Path(directory)).detect()
        self.assertEqual(snapshot.cpu.model, "Unknown")
        self.assertIsNone(snapshot.memory.total_bytes)
        self.assertEqual(snapshot.gpus, [])

    def test_invalid_outputs_are_safe(self):
        self.assertEqual(parse_lspci("invalid output"), [])
        self.assertIsNone(parse_meminfo("MemTotal: invalid").total_bytes)


if __name__ == "__main__":
    unittest.main()
