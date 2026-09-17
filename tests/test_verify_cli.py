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

"""Block B7 tests: the CLI ``verify`` surface (observation only)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from app import main as cli
from app import session as ses
from app.gpu_setup import FunctionalCheck, GpuSoftwareStatus
from app.hardware import CPUInfo, HardwareSnapshot, MemoryInfo
from app.runtimes import BackendStatus, RuntimeStatus


def _hardware(operating_system: str = "Linux") -> HardwareSnapshot:
    return HardwareSnapshot(
        operating_system=operating_system,
        architecture="x86_64",
        cpu=CPUInfo(model="Test CPU"),
        memory=MemoryInfo(total_bytes=8 * 1024 ** 3),
        gpus=(),
    )


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


class VerifyCommandHarness(unittest.TestCase):
    """Runs ``diagnose``/``verify`` with injected detectors and a temp root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv, software):
        stdout, stderr = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", list(argv)))
            stack.enter_context(patch.object(sys, "stdout", new=stdout))
            stack.enter_context(patch.object(sys, "stderr", new=stderr))
            stack.enter_context(
                patch("app.main.detect_hardware", return_value=_hardware()))
            stack.enter_context(
                patch("app.main.detect_runtimes", return_value=_runtimes()))
            stack.enter_context(
                patch("app.main.detect_backends", return_value=_backends()))
            stack.enter_context(patch(
                "app.main.diagnose_gpu_software", return_value=software))
            stack.enter_context(patch(
                "app.session.session_root", return_value=self.root))
            try:
                code = cli.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0
        return code, stdout.getvalue(), stderr.getvalue()

    def test_verify_is_registered_in_help(self):
        buffer = io.StringIO()
        with patch.object(sys, "argv", ["castlearq", "--help"]), patch.object(
            sys, "stdout", new=buffer
        ):
            with self.assertRaises(SystemExit) as context:
                cli.main()
        self.assertEqual(context.exception.code, 0)
        self.assertIn("verify", buffer.getvalue())

    def test_verify_without_session_is_not_destructive(self):
        code, out, _ = self._run(("castlearq", "verify"), _software())
        self.assertEqual(code, 0)
        self.assertIn("No previous diagnosis session found", out)
        self.assertIn("diagnose", out)

    def test_diagnose_persists_a_session(self):
        code, out, _ = self._run(
            ("castlearq", "diagnose"), _software(True, True, False))
        self.assertEqual(code, 0)
        self.assertIn("Verification session saved", out)
        path = self.root / "gpu-remediation.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["original_status"], "missing_component")

    def test_full_cycle_reports_passed(self):
        self._run(("castlearq", "diagnose"), _software(True, True, False))
        code, out, _ = self._run(
            ("castlearq", "verify"), _software(True, True, True))
        self.assertEqual(code, 0)
        self.assertIn("Outcome: VERIFIED", out)
        self.assertIn("vulkan_functional: PASSED", out)
        self.assertIn("Original diagnosis: MISSING_COMPONENT", out)
        self.assertIn("Current diagnosis: READY", out)

    def test_full_cycle_reports_failed_when_still_missing(self):
        self._run(("castlearq", "diagnose"), _software(True, True, False))
        code, out, _ = self._run(
            ("castlearq", "verify"), _software(True, True, False))
        self.assertEqual(code, 0)
        self.assertIn("Outcome: NOT_VERIFIED", out)
        self.assertIn("vulkan_functional: FAILED", out)

    def test_full_cycle_reports_unknown_when_evidence_is_missing(self):
        self._run(("castlearq", "diagnose"), _software(True, True, False))
        code, out, _ = self._run(
            ("castlearq", "verify"), _software(None, None, None))
        self.assertEqual(code, 0)
        self.assertIn("Outcome: UNKNOWN", out)
        self.assertNotIn("PASSED", out)

    def test_verify_after_ready_diagnose_has_no_session(self):
        code, out, _ = self._run(
            ("castlearq", "diagnose"), _software(True, True, True))
        self.assertEqual(code, 0)
        self.assertNotIn("Verification session saved", out)
        code, out, _ = self._run(
            ("castlearq", "verify"), _software(True, True, True))
        self.assertEqual(code, 0)
        self.assertIn("No previous diagnosis session found", out)

    def test_corrupt_session_is_a_controlled_error(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "gpu-remediation.json").write_text("{not json")
        code, out, _ = self._run(("castlearq", "verify"), _software())
        self.assertEqual(code, 2)
        self.assertIn("unusable", out)

    def test_verify_never_executes_anything(self):
        def explode(*args, **kwargs):
            raise AssertionError("B7 must never execute anything")

        self._run(("castlearq", "diagnose"), _software(True, True, False))
        with patch("subprocess.run", side_effect=explode), patch(
            "subprocess.Popen", side_effect=explode
        ), patch("os.system", side_effect=explode), patch(
            "socket.socket", side_effect=explode
        ), patch("urllib.request.urlopen", side_effect=explode):
            code, out, _ = self._run(
                ("castlearq", "verify"), _software(True, True, True))
        self.assertEqual(code, 0)
        self.assertIn("Outcome: VERIFIED", out)


if __name__ == "__main__":
    unittest.main()
