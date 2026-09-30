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

"""B9.76.4 tests: ``castlearq import --json`` and its UNKNOWN evidence.

The decisive assertions are the ones that keep two identities apart. An
imported artifact HAS a physical content identity (``content_id``) and does
NOT have a logical model identity or an integrity declaration, and the JSON
must say exactly that: a computed digest, and explicit UNKNOWN structures
with their reasons, never a synthesized ``model_id`` and never a ``"Unknown"``
datum.

Every test points the CLI at a temporary store, so no test can ever write
into the developer's real model store.
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import main as cli
from app.model_store import ModelStore

ENVELOPE_KEYS = {
    "schema",
    "schema_version",
    "command",
    "exit_code",
    "payload",
    "warnings",
    "error",
}

UNKNOWN_NOT_DECLARED = {
    "value": None,
    "status": "unknown",
    "reason": "not_declared",
}
UNKNOWN_NO_CATALOG = {
    "value": None,
    "status": "unknown",
    "reason": "no_catalog_evidence",
}
UNKNOWN_NOT_OBSERVED = {
    "value": None,
    "status": "unknown",
    "reason": "not_observed",
}


def _gguf(architecture: str | None = "qwen2") -> bytes:
    """Minimal GGUF the existing reader accepts."""
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 0 if architecture is None else 1))
    if architecture is not None:
        key = b"general.architecture"
        raw = architecture.encode("utf-8")
        data += struct.pack("<Q", len(key)) + key
        data += struct.pack("<I", 8)
        data += struct.pack("<Q", len(raw)) + raw
    return bytes(data)


MODEL = _gguf()
BROKEN = b"this is definitely not a GGUF file"


def run_cli(*argv):
    """Run ``main()`` with injected argv/streams; return (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["castlearq", *argv]), mock.patch.object(
        sys, "stdout", new=out
    ), mock.patch.object(sys, "stderr", new=err):
        try:
            code = cli.main()
        except SystemExit as exit_error:
            code = exit_error.code if isinstance(exit_error.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def one_json_document(stdout: str) -> dict:
    """Parse ``stdout`` as exactly one JSON document (trailing data fails)."""
    if not stdout.strip():
        raise AssertionError("stdout is empty; JSON mode must print a document")
    document = json.loads(stdout)
    if not isinstance(document, dict):
        raise AssertionError("the document must be a JSON object")
    return document


class _ImportCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = ModelStore(self.root / "models")
        self.external = self.root / "external"
        self.external.mkdir()

    def _source(self, name="model.gguf", data=MODEL):
        path = self.external / name
        path.write_bytes(data)
        return path

    def _import(self, *argv, json_mode=False):
        args = ["import", *argv, "--model-store", str(self.store.root)]
        if json_mode:
            args.append("--json")
        return run_cli(*args)

    def _managed(self):
        return sorted(
            path
            for path in self.store.root.rglob("*")
            if path.is_file() and path.suffix == ".gguf"
        )

    def assert_envelope(self, document, *, exit_code, command="import"):
        self.assertEqual(set(document), ENVELOPE_KEYS)
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], command)
        self.assertEqual(document["exit_code"], exit_code)


class ImportedJsonTests(_ImportCase):
    """A. Imported: exit 0, correct envelope, UNKNOWN evidence intact."""

    def test_imported_payload_reports_every_observed_and_unknown_field(self):
        source = self._source()
        code, out, _ = self._import(str(source), json_mode=True)
        self.assertEqual(code, 0)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=0)
        self.assertIsNone(document["error"])
        self.assertEqual(document["warnings"], [])

        payload = document["payload"]
        self.assertEqual(payload["status"], "imported")
        self.assertEqual(payload["label"], "model.gguf")
        self.assertEqual(
            payload["content_id"], hashlib.sha256(MODEL).hexdigest()
        )
        self.assertEqual(payload["format"], {"value": "GGUF", "status": "known"})
        self.assertEqual(
            payload["architecture"], {"value": "qwen2", "status": "known"}
        )
        self.assertEqual(payload["logical_identity"], UNKNOWN_NO_CATALOG)
        self.assertEqual(payload["integrity"], UNKNOWN_NOT_DECLARED)
        self.assertEqual(payload["memory_estimate"], UNKNOWN_NOT_OBSERVED)

    def test_storage_names_the_managed_location_and_never_a_partial(self):
        source = self._source()
        _, out, _ = self._import(str(source), json_mode=True)
        payload = one_json_document(out)["payload"]
        storage = payload["storage"]
        self.assertEqual(storage["filename"], "model.gguf")
        self.assertTrue(storage["path"].startswith(str(self.store.root)))
        self.assertTrue(storage["path"].endswith("model.gguf"))
        self.assertNotIn(".part", storage["path"])
        self.assertEqual(
            Path(storage["path"]), self._managed()[0]
        )

    def test_label_option_reaches_the_payload(self):
        source = self._source()
        _, out, _ = self._import(
            str(source), "--label", "My Local Model!", json_mode=True
        )
        payload = one_json_document(out)["payload"]
        self.assertEqual(payload["label"], "My_Local_Model_")
        self.assertEqual(payload["logical_identity"], UNKNOWN_NO_CATALOG)

    def test_missing_architecture_is_unknown_not_inferred(self):
        source = self._source("bare.gguf", _gguf(architecture=None))
        code, out, _ = self._import(str(source), json_mode=True)
        self.assertEqual(code, 0)
        document = one_json_document(out)
        payload = document["payload"]
        self.assertEqual(payload["architecture"], UNKNOWN_NOT_OBSERVED)
        # The importer's own warning is preserved, not converted to an error.
        self.assertTrue(document["warnings"])
        self.assertIsNone(document["error"])


class ReusedJsonTests(_ImportCase):
    """B. Reused: same bytes, same managed artifact, no second copy."""

    def test_second_import_of_the_same_bytes_reports_reused(self):
        source = self._source()
        first_code, first_out, _ = self._import(str(source), json_mode=True)
        second_code, second_out, _ = self._import(str(source), json_mode=True)
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        first = one_json_document(first_out)["payload"]
        second = one_json_document(second_out)["payload"]
        self.assertEqual(first["status"], "imported")
        self.assertEqual(second["status"], "reused")
        self.assertEqual(second["content_id"], first["content_id"])
        self.assertEqual(second["storage"]["path"], first["storage"]["path"])
        self.assertEqual(len(self._managed()), 1)
        self.assertEqual(self._managed()[0].read_bytes(), MODEL)

    def test_reuse_keeps_the_existing_copy_warning_in_the_envelope(self):
        source = self._source()
        self._import(str(source))
        code, out, _ = self._import(str(source), json_mode=True)
        self.assertEqual(code, 0)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=0)
        self.assertIsNone(document["error"])
        self.assertTrue(
            any("already managed" in warning for warning in document["warnings"])
        )

    def test_reuse_under_a_different_label_still_reuses(self):
        self._import(str(self._source()), "--label", "alpha")
        code, out, _ = self._import(
            str(self._source()), "--label", "beta", json_mode=True
        )
        self.assertEqual(code, 0)
        self.assertEqual(one_json_document(out)["payload"]["status"], "reused")
        self.assertEqual(len(self._managed()), 1)


class FailedImportJsonTests(_ImportCase):
    """C. Failed import: exit 1, structured error, nothing but JSON on stdout."""

    def test_invalid_gguf_is_a_structured_import_error(self):
        source = self._source("broken.gguf", BROKEN)
        code, out, _ = self._import(str(source), json_mode=True)
        self.assertEqual(code, 1)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=1)
        self.assertEqual(document["payload"], {})
        self.assertEqual(document["error"]["kind"], "import_error")
        self.assertIn("not a valid GGUF file", document["error"]["message"])
        self.assertEqual(self._managed(), [])

    def test_missing_source_is_a_structured_import_error(self):
        code, out, _ = self._import(
            str(self.external / "absent.gguf"), json_mode=True
        )
        self.assertEqual(code, 1)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=1)
        self.assertEqual(document["error"]["kind"], "import_error")
        self.assertIn("does not exist", document["error"]["message"])

    def test_no_traceback_and_no_human_text_ever_reach_stdout(self):
        for source in (
            self._source("broken.gguf", BROKEN),
            self.external / "absent.gguf",
            self.external,
        ):
            with self.subTest(source=source.name):
                code, out, _ = self._import(str(source), json_mode=True)
                self.assertEqual(code, 1)
                one_json_document(out)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("Status:", out)
                self.assertNotIn("CastleArq -", out)

    def test_usage_without_a_path_keeps_exit_two(self):
        human_code, _, _ = run_cli("import", "--model-store", str(self.store.root))
        json_code, out, err = run_cli(
            "import", "--json", "--model-store", str(self.store.root)
        )
        self.assertEqual(human_code, 2)
        self.assertEqual(json_code, human_code)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=2)
        self.assertEqual(document["error"]["kind"], "usage_error")
        # The usage line moved to stderr so stdout stays a single document.
        self.assertIn("Usage: python3 -m app.main import", err)


class ExitParityTests(_ImportCase):
    """D. The JSON run returns exactly the human exit code."""

    def test_parity_for_imported_reused_and_failed(self):
        source = self._source()
        broken = self._source("broken.gguf", BROKEN)

        human_imported = self._import(str(source))[0]
        json_imported = self._import(str(source), json_mode=True)[0]
        self.assertEqual(human_imported, 0)
        self.assertEqual(json_imported, human_imported)

        human_reused = self._import(str(source))[0]
        json_reused = self._import(str(source), json_mode=True)[0]
        self.assertEqual(human_reused, 0)
        self.assertEqual(json_reused, human_reused)

        human_failed = self._import(str(broken))[0]
        json_failed = self._import(str(broken), json_mode=True)[0]
        self.assertEqual(human_failed, 1)
        self.assertEqual(json_failed, human_failed)

    def test_human_report_is_unchanged_without_json(self):
        code, out, _ = self._import(str(self._source()))
        self.assertEqual(code, 0)
        self.assertIn("CastleArq - Local artifact import", out)
        self.assertIn("Status: IMPORTED", out)
        self.assertIn(f"Content ID: {hashlib.sha256(MODEL).hexdigest()}", out)
        self.assertIn("Architecture: qwen2", out)
        self.assertIn("Logical identity: UNKNOWN", out)
        self.assertIn("Integrity declaration: UNKNOWN", out)
        self.assertIn("Memory estimate: UNKNOWN", out)


class StdoutPurityTests(_ImportCase):
    """E. ``--json`` stdout is exactly one JSON document and nothing else."""

    def test_json_stdout_has_no_human_lines(self):
        _, out, _ = self._import(str(self._source()), json_mode=True)
        one_json_document(out)
        for human_line in (
            "CastleArq - Local artifact import",
            "Status:",
            "Label:",
            "Content ID:",
            "Format:",
            "Architecture:",
            "Storage:",
            "Logical identity:",
            "Integrity declaration:",
            "Memory estimate:",
            "Warning:",
            "Nothing was imported",
        ):
            self.assertNotIn(human_line, out)

    def test_repeated_runs_report_the_same_content_identity(self):
        source = self._source()
        _, first, _ = self._import(str(source), json_mode=True)
        _, second, _ = self._import(str(source), json_mode=True)
        self.assertEqual(
            one_json_document(first)["payload"]["content_id"],
            one_json_document(second)["payload"]["content_id"],
        )
        self.assertEqual(json.loads(first)["schema"], "castlearq.cli")


class IdentitySeparationTests(_ImportCase):
    """F/G. Content identity is not integrity; a label is not an identity."""

    def test_content_id_is_present_while_integrity_stays_unknown(self):
        digest = hashlib.sha256(MODEL).hexdigest()
        _, out, _ = self._import(str(self._source()), json_mode=True)
        payload = one_json_document(out)["payload"]
        self.assertEqual(payload["content_id"], digest)
        self.assertEqual(payload["integrity"], UNKNOWN_NOT_DECLARED)
        self.assertIsNone(payload["integrity"]["value"])
        # The computed digest was never promoted into a checksum declaration.
        self.assertNotIn("sha256", payload)
        stored = self.store.list_artifacts()[0]
        self.assertEqual(stored.artifact.content_id, digest)
        self.assertIsNone(stored.artifact.sha256)

    def test_logical_identity_is_unknown_and_no_model_id_is_invented(self):
        _, out, _ = self._import(
            str(self._source()), "--label", "alpha", json_mode=True
        )
        payload = one_json_document(out)["payload"]
        self.assertEqual(payload["logical_identity"], UNKNOWN_NO_CATALOG)
        self.assertIsNone(payload["logical_identity"]["value"])
        self.assertNotIn("model_id", payload)
        self.assertEqual(
            set(payload),
            {
                "status",
                "label",
                "content_id",
                "format",
                "architecture",
                "storage",
                "logical_identity",
                "integrity",
                "memory_estimate",
            },
        )
        # The label is addressing and presentation only.
        self.assertEqual(payload["label"], "alpha")
        self.assertNotEqual(payload["logical_identity"]["value"], "alpha")
        self.assertNotEqual(
            payload["logical_identity"]["value"], payload["content_id"]
        )

    def test_unknown_values_are_never_the_string_unknown(self):
        source = self._source("bare.gguf", _gguf(architecture=None))
        _, out, _ = self._import(str(source), json_mode=True)
        payload = one_json_document(out)["payload"]
        self.assertNotIn("Unknown", out)
        self.assertEqual(payload["architecture"]["status"], "unknown")
        self.assertEqual(payload["integrity"]["status"], "unknown")
        self.assertEqual(payload["memory_estimate"]["status"], "unknown")

    def test_json_flag_is_still_rejected_for_every_other_command(self):
        for command in ("models", "runtime", "plan", "detect", "execute", "serve"):
            with self.subTest(command=command):
                code, out, err = run_cli(command, "--json")
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn(
                    f"--json is not valid for command '{command}'", err
                )

    def test_import_json_never_writes_when_the_source_is_a_directory(self):
        code, out, _ = self._import(str(self.external), json_mode=True)
        self.assertEqual(code, 1)
        document = one_json_document(out)
        self.assert_envelope(document, exit_code=1)
        self.assertEqual(document["error"]["kind"], "import_error")
        self.assertEqual(self._managed(), [])


if __name__ == "__main__":
    unittest.main()