# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""B9.67 stage 4: the ``castlearq import`` CLI surface.

Every test points the CLI at a temporary ModelStore, so no test can ever write
into the developer's real store.
"""

from __future__ import annotations

import contextlib
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import main as cli
from app.importing import ImportStatus, LocalArtifactImporter
from app.model_store import ModelStore


def _gguf(architecture="qwen2") -> bytes:
    """Minimal GGUF the existing reader accepts."""
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    key = b"general.architecture"
    raw = architecture.encode("utf-8")
    data += struct.pack("<Q", len(key)) + key
    data += struct.pack("<I", 8)
    data += struct.pack("<Q", len(raw)) + raw
    return bytes(data)


MODEL = _gguf()


class _CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(self.root / "models")
        self.external = self.root / "external"
        self.external.mkdir()

    def _source(self, name="model.gguf", data=MODEL):
        path = self.external / name
        path.write_bytes(data)
        return path

    def _run(self, *argv):
        """Invoke the CLI with the store redirected to the temp directory.

        Usage errors go through ``parser.error``, which raises
        ``SystemExit(2)`` rather than returning. That is the existing CLI
        convention, so it is translated here into the same exit code the
        process would produce.
        """
        out = io.StringIO()
        with mock.patch.object(cli, "ModelStore", return_value=self.store):
            with contextlib.redirect_stdout(out):
                with contextlib.redirect_stderr(out):
                    with mock.patch.object(sys, "argv", ["castlearq", *argv]):
                        try:
                            code = cli.main()
                        except SystemExit as exit_error:
                            code = exit_error.code if exit_error.code is not None else 0
        return code, out.getvalue()

    def _import(self, *argv):
        return self._run("import", *argv)

    def _managed(self):
        return sorted(p for p in self.store.root.rglob("*.gguf") if p.is_file())



class HappyPathTests(_CliCase):
    def test_valid_import_exits_zero(self):
        code, _ = self._import(str(self._source()))
        self.assertEqual(code, 0)

    def test_output_reports_imported(self):
        _, out = self._import(str(self._source()))
        self.assertIn("Status: IMPORTED", out)

    def test_output_shows_the_content_id(self):
        import hashlib
        _, out = self._import(str(self._source()))
        self.assertIn(hashlib.sha256(MODEL).hexdigest(), out)

    def test_output_shows_the_architecture(self):
        _, out = self._import(str(self._source()))
        self.assertIn("Architecture: qwen2", out)

    def test_output_shows_the_storage_location(self):
        code, out = self._import(str(self._source()))
        self.assertIn("Storage:", out)
        self.assertIn(str(self.store.root), out)
        self.assertEqual(code, 0)

    def test_output_states_logical_identity_is_unknown(self):
        _, out = self._import(str(self._source()))
        self.assertIn("Logical identity: UNKNOWN", out)

    def test_output_states_integrity_and_memory_are_unknown(self):
        _, out = self._import(str(self._source()))
        self.assertIn("Integrity declaration: UNKNOWN", out)
        self.assertIn("Memory estimate: UNKNOWN", out)

    def test_content_id_is_not_presented_as_a_model_id(self):
        _, out = self._import(str(self._source()))
        self.assertNotIn("Model ID:", out)
        self.assertNotIn("model_id:", out)

    def test_managed_artifact_matches_the_store_layout(self):
        imported = LocalArtifactImporter(self.store).import_artifact(self._source())
        self.assertEqual(self._managed(), [imported.destination])
        expected = (
            self.store.root / imported.sanitized_label / imported.content_id
            / imported.filename
        )
        self.assertEqual(imported.destination, expected)

    def test_managed_content_matches_the_original(self):
        source = self._source()
        self._import(str(source))
        self.assertEqual(self._managed()[0].read_bytes(), MODEL)

    def test_original_source_is_never_modified(self):
        source = self._source()
        before = source.read_bytes()
        self._import(str(source))
        self.assertEqual(source.read_bytes(), before)

    def test_original_source_stays_outside_the_store(self):
        source = self._source()
        self._import(str(source))
        self.assertNotIn(str(source), str(self.store.root))
        self.assertNotEqual(self._managed()[0], source)

    def test_directory_is_rejected(self):
        code, out = self._import(str(self.external))
        self.assertEqual(code, 1)


class LabelTests(_CliCase):
    def test_label_reaches_the_importer(self):
        source = self._source()
        with mock.patch.object(
            LocalArtifactImporter, "import_artifact", return_value=_fake()
        ) as spy:
            self._import(str(source), "--label", "My Model")
        self.assertEqual(spy.call_args.kwargs["label"], "My Model")

    def test_label_defaults_to_none(self):
        source = self._source()
        with mock.patch.object(
            LocalArtifactImporter, "import_artifact", return_value=_fake()
        ) as spy:
            self._import(str(source))
        self.assertIsNone(spy.call_args.kwargs["label"])

    def test_output_shows_the_sanitized_label(self):
        _, out = self._import(str(self._source()), "--label", "My Local Model!")
        self.assertIn("Label: My_Local_Model_", out)

    def test_sanitized_label_is_used_for_addressing(self):
        _, out = self._import(str(self._source()), "--label", "My Local Model!")
        self.assertIn("My_Local_Model_", str(self._managed()[0].parent.parent))

    def test_label_is_not_a_logical_identity(self):
        code, out = self._import(str(self._source()), "--label", "My Local Model!")
        self.assertEqual(code, 0)
        self.assertIn("Logical identity: UNKNOWN", out)
        stored = self.store.list_artifacts()[0]
        self.assertIsNone(stored.artifact.sha256)
        self.assertIsNotNone(stored.artifact.content_id)

    def test_cli_does_not_accept_a_model_id_option(self):
        code, out = self._import(str(self._source()), "--model-id", "qwen2")
        self.assertEqual(code, 2)
        self.assertEqual(self._managed(), [])

    def test_cli_does_not_accept_quantization(self):
        code, _ = self._import(str(self._source()), "--quantization", "Q4_K_M")
        self.assertEqual(code, 2)


class ReuseTests(_CliCase):
    def test_second_import_of_same_content_exits_zero(self):
        source = self._source()
        first, _ = self._import(str(source))
        second, _ = self._import(str(source))
        self.assertEqual(first, 0)
        self.assertEqual(second, 0)

    def test_second_import_reports_reused(self):
        source = self._source()
        self._import(str(source))
        _, out = self._import(str(source))
        self.assertIn("Status: REUSED", out)

    def test_reuse_creates_no_second_copy(self):
        source = self._source()
        self._import(str(source))
        self._import(str(source))
        self.assertEqual(len(self._managed()), 1)
        self.assertEqual(len(self.store.list_artifacts()), 1)

    def test_reuse_under_a_different_label_still_reuses(self):
        self._import(str(self._source()), "--label", "alpha")
        _, out = self._import(str(self._source()), "--label", "beta")
        self.assertIn("Status: REUSED", out)
        self.assertEqual(len(self._managed()), 1)

    def test_reuse_reports_the_existing_location(self):
        source = self._source()
        _, first = self._import(str(source))
        _, second = self._import(str(source))
        storage_line = [l for l in first.splitlines() if "Storage:" in l]
        self.assertEqual(storage_line, [l for l in second.splitlines() if "Storage:" in l])

    def test_reuse_explains_the_existing_copy(self):
        source = self._source()
        self._import(str(source))
        _, out = self._import(str(source))
        self.assertIn("already managed", out)


class UsageTests(_CliCase):
    def test_import_without_path_exits_two(self):
        code, _ = self._import()
        self.assertEqual(code, 2)

    def test_import_with_extra_positional_exits_two(self):
        code, _ = self._import(str(self._source()), "extra.gguf")
        self.assertEqual(code, 2)
        self.assertEqual(self._managed(), [])

    def test_unknown_command_still_exits_two(self):
        code, _ = self._run("frobnicate")
        self.assertEqual(code, 2)

    def test_other_commands_still_work(self):
        code, out = self._run("models")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())


class DelegationTests(_CliCase):
    def test_cli_calls_the_importer_once_with_the_path(self):
        source = self._source()
        with mock.patch.object(
            LocalArtifactImporter, "import_artifact", return_value=_fake()
        ) as spy:
            self._import(str(source))
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(Path(spy.call_args.args[0]), source)

    def test_cli_does_not_invoke_any_runner(self):
        with mock.patch("app.execute_model.execute_model") as runner:
            self._import(str(self._source()))
        runner.assert_not_called()

    def test_cli_does_not_resolve_or_execute(self):
        with mock.patch("app.execute_model.execute_model") as execute:
            with mock.patch("app.main.run_model") as run:
                code, _ = self._import(str(self._source()))
        self.assertEqual(code, 0)
        execute.assert_not_called()
        run.assert_not_called()

    def test_cli_builds_no_artifact_of_its_own(self):
        with mock.patch("app.main.ArtifactSpec") as spec:
            code, _ = self._import(str(self._source()))
        self.assertEqual(code, 0)
        spec.assert_not_called()

    def test_failure_status_maps_to_exit_one(self):
        from app.importing import ImportResult
        failure = ImportResult(
            status=ImportStatus.FAILED, error="simulated importer failure"
        )
        with mock.patch.object(
            LocalArtifactImporter, "import_artifact", return_value=failure
        ):
            code, out = self._import(str(self._source()))
        self.assertEqual(code, 1)
        self.assertIn("simulated importer failure", out)

    def test_failure_never_becomes_a_warning(self):
        from app.importing import ImportResult
        failure = ImportResult(status=ImportStatus.FAILED, error="concrete failure")
        with mock.patch.object(
            LocalArtifactImporter, "import_artifact", return_value=failure
        ):
            code, out = self._import(str(self._source()))
        self.assertEqual(code, 1)
        self.assertNotIn("Warning:", out)


    def test_label_is_rejected_for_other_commands(self):
        code, _ = self._run("models", "--label", "x")
        self.assertEqual(code, 2)


class SourceRejectionTests(_CliCase):
    def test_directory_is_rejected(self):
        code, out = self._import(str(self.external))
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertEqual(self._managed(), [])

    def test_symlink_source_is_rejected(self):
        link = self.external / "link.gguf"
        link.symlink_to(self._source("real.gguf"))
        code, out = self._import(str(link))
        self.assertEqual(code, 1)
        self.assertIn("symbolic link", out)
        self.assertEqual(self._managed(), [])

    def test_invalid_gguf_is_rejected(self):
        code, out = self._import(str(self._source("bad.gguf", b"NOPE" + b"\x00" * 32)))
        self.assertEqual(code, 1)
        self.assertIn("not a valid GGUF", out)
        self.assertEqual(self._managed(), [])

    def test_missing_file_is_rejected(self):
        code, out = self._import(str(self.external / "absent.gguf"))
        self.assertEqual(code, 1)
        self.assertIn("does not exist", out)


def _fake():
    """A minimal successful ImportResult for delegation assertions."""
    from app.importing import ImportResult
    return ImportResult(status=ImportStatus.IMPORTED, content_id="0" * 64)
