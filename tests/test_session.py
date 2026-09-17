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

"""Block B7 tests: remediation session persistence (data, never executed)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import session as ses
from app.gpu_diagnosis import DiagnosisStatus


def _session() -> ses.DiagnosisSession:
    return ses.DiagnosisSession(
        schema_version=1,
        original_status=DiagnosisStatus.MISSING_COMPONENT,
        runtime="llama.cpp",
        backend="vulkan",
        platform="linux",
        missing=(
            ses.MissingComponentRecord(
                component="vulkan_functional",
                required_by="llama.cpp + Vulkan",
                detail="no functional Vulkan",
                source="probe",
            ),
        ),
    )


class SessionPathTests(unittest.TestCase):
    def test_default_root_is_the_user_space(self):
        self.assertEqual(
            ses.session_root(home=Path("/home/test")),
            Path("/home/test/.castlearq/sessions"))

    def test_environment_override_wins(self):
        root = ses.session_root(
            environ={"CASTLEARQ_SESSION_ROOT": "/tmp/override"})
        self.assertEqual(root, Path("/tmp/override"))

    def test_session_file_name(self):
        self.assertEqual(
            ses.session_path(Path("/tmp/root")),
            Path("/tmp/root/gpu-remediation.json"))


class SessionRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_then_load_roundtrip(self):
        path = ses.save_session(_session(), self.root)
        self.assertEqual(path, ses.session_path(self.root))
        self.assertTrue(path.exists())
        loaded = ses.load_session(self.root)
        self.assertEqual(loaded, _session())

    def test_save_creates_the_directory(self):
        nested = self.root / "a" / "b"
        ses.save_session(_session(), nested)
        self.assertTrue((nested / "gpu-remediation.json").exists())

    def test_load_without_session_returns_none(self):
        self.assertIsNone(ses.load_session(self.root))

    def test_clear_session(self):
        self.assertFalse(ses.clear_session(self.root))
        ses.save_session(_session(), self.root)
        self.assertTrue(ses.clear_session(self.root))
        self.assertFalse(ses.clear_session(self.root))

    def test_stored_payload_is_plain_data(self):
        path = ses.save_session(_session(), self.root)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["original_status"], "missing_component")
        self.assertEqual(
            payload["missing_components"][0]["component"],
            "vulkan_functional")


class CorruptSessionTests(unittest.TestCase):
    def _write(self, text: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "gpu-remediation.json"
        path.write_text(text, encoding="utf-8")
        return Path(tmp.name)

    def test_invalid_json_is_a_controlled_error(self):
        root = self._write("{not json")
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)

    def test_non_object_payload_is_rejected(self):
        root = self._write('["array"]')
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)

    def test_unknown_schema_version_is_rejected(self):
        root = self._write(json.dumps({"schema_version": 99}))
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)

    def test_invalid_status_is_rejected(self):
        root = self._write(json.dumps({
            "schema_version": 1,
            "original_status": "totally-broken",
        }))
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)

    def test_wrong_field_types_are_rejected(self):
        root = self._write(json.dumps({
            "schema_version": 1,
            "original_status": "ready",
            "runtime": 42,
        }))
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)

    def test_malformed_missing_component_is_rejected(self):
        root = self._write(json.dumps({
            "schema_version": 1,
            "original_status": "missing_component",
            "runtime": "llama.cpp",
            "backend": "vulkan",
            "platform": "linux",
            "missing_components": [{"component": 7}],
        }))
        with self.assertRaises(ses.SessionError):
            ses.load_session(root)


if __name__ == "__main__":
    unittest.main()
