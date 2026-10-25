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

"""Pruebas del punto de entrada CLI ``import-openvino``."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq import main as cli
from castlearq.conversion import ImportResult


def _make_bundle(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "openvino_model.xml").write_text("<model/>")
    (root / "openvino_model.bin").write_bytes(b"\x00\x01\x02\x03" * 10)
    (root / "config.json").write_text("{}")
    return root


class ImportOpenVINOCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = mock.Mock()

    def test_missing_source_is_usage_error(self):
        code = cli.import_openvino_command(None, "m", model_store=self.store)
        self.assertEqual(code, 2)

    def test_missing_model_id_is_usage_error(self):
        src = _make_bundle(self.root / "src")
        code = cli.import_openvino_command(str(src), "", model_store=self.store)
        self.assertEqual(code, 2)

    def test_dispatch_invokes_service(self):
        src = _make_bundle(self.root / "src")
        ok = ImportResult(
            success=True,
            artifact=None,
            manifest_path=None,
            message="Import completed",
        )
        with mock.patch("castlearq.main.OpenVINOImportService") as svc_cls:
            svc_cls.return_value.import_directory.return_value = ok
            code = cli.import_openvino_command(
                str(src), "m", model_store=self.store
            )
        self.assertEqual(code, 0)
        svc_cls.assert_called_once_with(self.store)
        svc_cls.return_value.import_directory.assert_called_once_with(
            Path(str(src)).expanduser(), "m", precision="INT4", revision=None
        )

    def test_custom_precision_and_revision(self):
        src = _make_bundle(self.root / "src")
        ok = ImportResult(
            success=True,
            artifact=None,
            manifest_path=None,
            message="Import completed",
        )
        with mock.patch("castlearq.main.OpenVINOImportService") as svc_cls:
            svc_cls.return_value.import_directory.return_value = ok
            code = cli.import_openvino_command(
                str(src), "m", precision="fp16", revision="abc",
                model_store=self.store,
            )
        self.assertEqual(code, 0)
        svc_cls.return_value.import_directory.assert_called_once_with(
            Path(str(src)).expanduser(), "m", precision="fp16", revision="abc"
        )

    def test_failure_returns_nonzero(self):
        src = _make_bundle(self.root / "src")
        bad = ImportResult(
            success=False,
            artifact=None,
            manifest_path=None,
            message="boom",
        )
        with mock.patch("castlearq.main.OpenVINOImportService") as svc_cls:
            svc_cls.return_value.import_directory.return_value = bad
            code = cli.import_openvino_command(
                str(src), "m", model_store=self.store
            )
        self.assertEqual(code, 1)

    def test_json_success(self):
        src = _make_bundle(self.root / "src")
        artifact = mock.Mock()
        artifact.model_id = "m"
        artifact.filename = "openvino_model.xml"
        artifact.format = "OpenVINO IR"
        artifact.backend = "openvino"
        artifact.quantization = "INT4"
        artifact.content_id = "deadbeef"
        ok = ImportResult(
            success=True,
            artifact=artifact,
            manifest_path=Path("/store/m/abc/manifest.json"),
            message="Import completed",
        )
        out = io.StringIO()
        with mock.patch("castlearq.main.OpenVINOImportService") as svc_cls, \
             mock.patch("sys.stdout", out):
            svc_cls.return_value.import_directory.return_value = ok
            code = cli.import_openvino_command(
                str(src), "m", model_store=self.store, as_json=True
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["command"], "import-openvino")
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["payload"]["artifact"]["backend"], "openvino")
        self.assertEqual(data["payload"]["artifact"]["format"], "OpenVINO IR")
        self.assertEqual(data["payload"]["artifact"]["filename"], "openvino_model.xml")


if __name__ == "__main__":
    unittest.main()