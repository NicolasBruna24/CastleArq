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

"""Tests for the B9.67 local artifact importer (physical core)."""

import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq.gguf_reader import GGUFReadError, read_architecture_evidence
from castlearq.importing import ImportStatus, LocalArtifactImporter
from castlearq.model_store import ModelStore, UnsafePathError
from castlearq.models import ArtifactSpec, ArtifactState


def _gguf(entries=(), *, version=3, magic=b"GGUF"):
    """Build a minimal GGUF header holding only string metadata entries."""
    data = bytearray(magic + struct.pack("<IQQ", version, 0, len(entries)))
    for key, value in entries:
        raw = value.encode("utf-8")
        data.extend(struct.pack("<Q", len(key.encode("utf-8"))))
        data.extend(key.encode("utf-8"))
        data.extend(struct.pack("<I", 8))
        data.extend(struct.pack("<Q", len(raw)))
        data.extend(raw)
    return bytes(data)


MODEL = _gguf((("general.architecture", "qwen2"),))
OTHER = _gguf((("general.architecture", "llama"),))


class _ImportCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(self.root / "models")
        self.importer = LocalArtifactImporter(self.store)
        self.sources = self.root / "sources"
        self.sources.mkdir()

    def _write(self, name, data=MODEL):
        path = self.sources / name
        path.write_bytes(data)
        return path

    def _stored_files(self, pattern="*.gguf"):
        """Only real files: a sanitized label may itself match the pattern."""
        return sorted(p for p in self.store.root.rglob(pattern) if p.is_file())

    def _parts(self):
        return [p for p in self.store.root.rglob("*.part") if p.is_file()]

    def _manifests(self):
        return [p for p in self.store.root.rglob("manifest.json") if p.is_file()]



class SourceValidationTests(_ImportCase):
    def test_valid_gguf_file_is_imported(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertIsNone(result.error)
        self.assertTrue(result.ok)

    def test_missing_path_fails(self):
        result = self.importer.import_artifact(self.sources / "absent.gguf")
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("does not exist", result.error)
        self.assertIsNone(result.content_id)

    def test_symlink_source_fails(self):
        target = self._write("real.gguf")
        link = self.sources / "link.gguf"
        link.symlink_to(target)
        result = self.importer.import_artifact(link)
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("symbolic link", result.error)

    def test_directory_source_fails(self):
        result = self.importer.import_artifact(self.sources)
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("directory", result.error)

    def test_non_regular_source_fails(self):
        path = self.sources / "fifo.gguf"
        try:
            os.mkfifo(path)
        except (AttributeError, OSError) as error:
            self.skipTest(f"environment cannot create a FIFO: {error}")
        result = self.importer.import_artifact(path)
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("not a regular file", result.error)

    def test_source_is_never_modified(self):
        path = self._write("stable.gguf")
        before = path.read_bytes()
        self.importer.import_artifact(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self._stored_files()), 1)

    def test_rejected_source_leaves_nothing_stored(self):
        self.importer.import_artifact(self.sources / "absent.gguf")
        self.importer.import_artifact(self.sources)
        self.assertEqual(self.store.list_artifacts(), [])


class GGUFValidationTests(_ImportCase):
    def test_invalid_gguf_fails_and_imports_nothing(self):
        result = self.importer.import_artifact(
            self._write("bad.gguf", b"NOTGGUF" + b"\x00" * 64)
        )
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("not a valid GGUF", result.error)
        self.assertEqual(self.store.list_artifacts(), [])
        self.assertEqual(self._stored_files(), [])

    def test_empty_file_fails_as_invalid_gguf(self):
        result = self.importer.import_artifact(self._write("empty.gguf", b""))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self._stored_files(), [])

    def test_architecture_is_observed(self):
        result = self.importer.import_artifact(self._write("arch.gguf"))
        self.assertEqual(result.architecture, "qwen2")

    def test_architecture_agrees_with_the_existing_reader(self):
        path = self._write("cross.gguf")
        result = self.importer.import_artifact(path)
        self.assertEqual(
            result.architecture, read_architecture_evidence(path).architecture_raw
        )

    def test_general_name_is_never_used_as_identity(self):
        data = _gguf((("general.name", "Some Official Model Name"),
                      ("general.architecture", "qwen2")))
        result = self.importer.import_artifact(self._write("named.gguf", data))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertNotIn("Some Official Model Name", result.artifact.model_id)
        self.assertIsNone(result.model.id)

    def test_missing_architecture_stays_unknown_with_a_warning(self):
        result = self.importer.import_artifact(
            self._write("bare.gguf", _gguf((("general.type", "model"),)))
        )
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertIsNone(result.architecture)
        self.assertTrue(any("UNKNOWN" in w for w in result.warnings))


class IdentityTests(_ImportCase):
    def test_content_id_is_the_sha256_of_the_content(self):
        result = self.importer.import_artifact(self._write("id.gguf"))
        self.assertEqual(result.content_id, hashlib.sha256(MODEL).hexdigest())
        self.assertEqual(result.artifact.content_id, result.content_id)
        self.assertEqual(result.artifact_id, result.content_id)

    def test_computed_digest_is_not_copied_into_sha256(self):
        result = self.importer.import_artifact(self._write("decl.gguf"))
        self.assertIsNone(result.artifact.sha256)

    def test_unknown_declaration_is_not_reported_as_verified(self):
        result = self.importer.import_artifact(self._write("unver.gguf"))
        stored = self.store.inspect_manifest(
            self.store.artifact_directory(result.artifact) / "manifest.json"
        )
        self.assertEqual(stored.state, ArtifactState.DOWNLOADED)
        self.assertNotEqual(stored.state, ArtifactState.VERIFIED)

    def test_same_content_different_filename_is_reused(self):
        first = self.importer.import_artifact(self._write("one.gguf"))
        second = self.importer.import_artifact(self._write("two.gguf"))
        self.assertEqual(first.status, ImportStatus.IMPORTED)
        self.assertEqual(second.status, ImportStatus.REUSED)
        self.assertEqual(second.filename, "one.gguf")
        self.assertEqual(second.content_id, first.content_id)

    def test_same_content_different_label_is_reused(self):
        self.importer.import_artifact(self._write("a.gguf"), label="alpha")
        second = self.importer.import_artifact(self._write("b.gguf"), label="beta")
        self.assertEqual(second.status, ImportStatus.REUSED)
        self.assertEqual(second.sanitized_label, "alpha")

    def test_same_content_twice_keeps_exactly_one_copy(self):
        first = self.importer.import_artifact(self._write("dup.gguf"))
        second = self.importer.import_artifact(self._write("dup.gguf"))
        self.assertEqual(first.status, ImportStatus.IMPORTED)
        self.assertEqual(second.status, ImportStatus.REUSED)
        self.assertEqual(len(self._stored_files()), 1)
        self.assertEqual(len(self.store.list_artifacts()), 1)

    def test_identity_ignores_filename_and_label(self):
        first = self.importer.import_artifact(self._write("x.gguf"), label="one")
        second = self.importer.import_artifact(self._write("y.gguf"), label="two")
        self.assertEqual(first.content_id, second.content_id)

    def test_different_content_same_label_coexists(self):
        first = self.importer.import_artifact(self._write("one.gguf"), label="shared")
        second = self.importer.import_artifact(
            self._write("two.gguf", OTHER), label="shared"
        )
        self.assertEqual(first.status, ImportStatus.IMPORTED)
        self.assertEqual(second.status, ImportStatus.IMPORTED)
        self.assertNotEqual(first.content_id, second.content_id)
        self.assertEqual(len(self.store.list_artifacts()), 2)
        self.assertEqual(len(self._stored_files()), 2)

    def test_reuse_never_overwrites_the_existing_filename(self):
        first = self.importer.import_artifact(self._write("original.gguf"))
        self.importer.import_artifact(self._write("other.gguf"))
        self.assertTrue((first.destination.parent / "original.gguf").is_file())



class LabelTests(_ImportCase):
    def test_explicit_label_is_sanitized(self):
        result = self.importer.import_artifact(
            self._write("l.gguf"), label="Qwen Coder 7B/ Instruct!"
        )
        self.assertEqual(result.label, "Qwen Coder 7B/ Instruct!")
        self.assertEqual(result.sanitized_label, "Qwen_Coder_7B___Instruct_")
        self.assertEqual(result.artifact.model_id, result.sanitized_label)

    def test_filename_is_the_label_fallback(self):
        result = self.importer.import_artifact(self._write("fallback.gguf"))
        self.assertEqual(result.label, "fallback.gguf")
        self.assertEqual(result.sanitized_label, "fallback.gguf")

    def test_sanitized_label_is_used_for_addressing(self):
        result = self.importer.import_artifact(
            self._write("addr.gguf"), label="odd name!"
        )
        self.assertEqual(result.destination.parent.parent.name, "odd_name_")
        self.assertTrue(str(result.destination).startswith(str(self.store.root)))

    def test_label_never_fills_model_id(self):
        result = self.importer.import_artifact(self._write("mid.gguf"), label="label")
        self.assertIsNone(result.model.id)
        self.assertNotEqual(result.model.id, result.sanitized_label)
        self.assertEqual(result.model.name, result.sanitized_label)

    def test_unsafe_label_fails(self):
        result = self.importer.import_artifact(self._write("unsafe.gguf"), label="..")
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("Unsafe", result.error)
        self.assertEqual(self.store.list_artifacts(), [])

    def test_unsafe_filename_fails(self):
        result = self.importer.import_artifact(self.sources / ".." / ".." / "x.gguf")
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self._stored_files(), [])


class ProvenanceTests(_ImportCase):
    def test_local_import_fabricates_no_provenance(self):
        result = self.importer.import_artifact(self._write("prov.gguf"))
        self.assertIsNone(result.artifact.source)
        self.assertIsNone(result.artifact.repository)
        self.assertIsNone(result.artifact.download_url)

    def test_manifest_persists_unknown_provenance(self):
        result = self.importer.import_artifact(self._write("prov2.gguf"))
        payload = json.loads(
            (result.destination.parent / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(payload["source"])
        self.assertIsNone(payload["repository"])
        self.assertIsNone(payload["download_url"])
        self.assertEqual(payload["content_id"], result.content_id)

    def test_manifest_round_trips_through_inspection(self):
        result = self.importer.import_artifact(self._write("rt.gguf"))
        stored = self.store.inspect_manifest(
            self.store.artifact_directory(result.artifact) / "manifest.json"
        )
        self.assertIsNone(stored.artifact.source)
        self.assertEqual(stored.artifact.content_id, result.content_id)

    def test_no_remote_vendor_is_invented(self):
        result = self.importer.import_artifact(self._write("v.gguf"))
        blob = json.dumps(
            [result.artifact.__dict__, result.model.__dict__], default=str
        ).lower()
        for vendor in ("huggingface", "github", "http://", "https://"):
            self.assertNotIn(vendor, blob)


class StorageTests(_ImportCase):
    def test_artifact_lives_inside_the_model_store(self):
        result = self.importer.import_artifact(self._write("in.gguf"))
        self.assertTrue(
            str(result.destination).startswith(str(self.store.root.resolve()))
        )

    def test_external_path_is_never_the_destination(self):
        source = self._write("ext.gguf")
        result = self.importer.import_artifact(source)
        self.assertNotEqual(result.destination, source)
        self.assertNotEqual(result.destination.resolve(), source.resolve())

    def test_final_file_exists_with_the_source_bytes(self):
        result = self.importer.import_artifact(self._write("fin.gguf"))
        self.assertTrue(result.destination.is_file())
        self.assertEqual(result.destination.read_bytes(), MODEL)

    def test_layout_is_label_content_filename(self):
        result = self.importer.import_artifact(self._write("lay.gguf"), label="lab")
        directory = result.destination.parent
        self.assertEqual(directory.name, result.content_id)
        self.assertEqual(directory.parent.name, "lab")

    def test_manifest_exists_after_publication(self):
        result = self.importer.import_artifact(self._write("man.gguf"))
        self.assertTrue((result.destination.parent / "manifest.json").is_file())
        self.assertTrue(result.destination.is_file())

    def test_manifest_is_not_written_before_the_final_file(self):
        observed = {}
        original = self.store.save_manifest

        def spy(artifact):
            published = self.store.artifact_directory(artifact) / artifact.filename
            observed["file_existed"] = published.is_file()
            return original(artifact)

        self.store.save_manifest = spy
        result = self.importer.import_artifact(self._write("order.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertTrue(observed["file_existed"])

    def test_store_reports_the_imported_artifact_as_downloaded(self):
        result = self.importer.import_artifact(self._write("state.gguf"))
        stored = self.store.list_artifacts()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].artifact.content_id, result.content_id)
        self.assertEqual(stored[0].state, ArtifactState.DOWNLOADED)

    def test_find_by_content_id_finds_the_import(self):
        result = self.importer.import_artifact(self._write("find.gguf"))
        found = self.store.find_by_content_id(result.content_id)
        self.assertEqual(found.artifact.content_id, result.content_id)

    def test_find_by_content_id_ignores_catalog_artifacts(self):
        catalog = ArtifactSpec(
            model_id="m", source="huggingface", repository="o/r", filename="c.gguf"
        )


class AtomicityTests(_ImportCase):
    def _fail_after_writes(self, allowed=0):
        """Simulate a copy that dies part-way through the bytes.

        ``os.write`` is patched only for the import's own file descriptor
        work by wrapping the importer's writer, so nothing else in the
        process (tempfile cleanup, fsync, the test runner) is disturbed.
        """
        real = os.write
        state = {"n": 0}

        def flaky(fd, data):
            if state["n"] >= allowed:
                raise OSError("simulated write failure")
            state["n"] += 1
            return real(fd, data)

        return mock.patch.object(os, "write", side_effect=flaky)

    def test_interrupted_copy_produces_no_complete_artifact(self):
        with self._fail_after_writes():
            result = self.importer.import_artifact(self._write("trunc.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self._stored_files(), [])
        self.assertEqual(self.store.list_artifacts(), [])

    def test_interrupted_copy_leaves_no_part_file(self):
        with self._fail_after_writes():
            self.importer.import_artifact(self._write("nopart.gguf"))
        self.assertEqual(self._parts(), [])

    def test_failed_copy_never_publishes_a_manifest(self):
        with self._fail_after_writes():
            result = self.importer.import_artifact(self._write("inc.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self._manifests(), [])

    def test_part_file_is_never_the_published_name(self):
        observed = {}
        real = os.link

        def spy(src, dst, *args, **kwargs):
            # At publication time the bytes still live only in the `.part`.
            observed["part_present"] = bool(self._parts())
            return real(src, dst, *args, **kwargs)

        with mock.patch.object(os, "link", side_effect=spy):
            result = self.importer.import_artifact(self._write("part.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertTrue(observed["part_present"])
        self.assertEqual(self._parts(), [])

    def test_a_stale_part_is_never_treated_as_complete(self):
        result = self.importer.import_artifact(self._write("stale.gguf"))
        directory = result.destination.parent
        # Simulate an interrupted earlier import: half a file, no manifest.
        (directory / "half.gguf.part").write_bytes(MODEL[: len(MODEL) // 2])
        (directory / "manifest.json").unlink()
        result.destination.unlink()

        again = self.importer.import_artifact(self._write("stale.gguf"))
        self.assertEqual(again.status, ImportStatus.IMPORTED)
        self.assertEqual(again.destination.read_bytes(), MODEL)
        # The importer's own `.part` is gone; an unrelated partial left by
        # another flow is not this stage's to reclaim, and crucially it was
        # never mistaken for the published artifact.
        self.assertFalse((directory / "stale.gguf.part").exists())
        self.assertEqual(
            again.destination, result.destination, "partial became the artifact"
        )

    def test_stale_part_does_not_suppress_a_different_import(self):
        self.importer.import_artifact(self._write("one.gguf"))
        directory = next(self.store.root.rglob("manifest.json")).parent
        (directory / "junk.gguf.part").write_bytes(b"partial")
        again = self.importer.import_artifact(self._write("two.gguf", OTHER))
        self.assertEqual(again.status, ImportStatus.IMPORTED)

    def test_copy_verification_failure_publishes_nothing(self):
        with mock.patch.object(
            LocalArtifactImporter, "_partial_digest",
            side_effect=OSError("digest read failed"),
        ):
            result = self.importer.import_artifact(self._write("vd.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self._stored_files(), [])
        self.assertEqual(self._parts(), [])

    def test_digest_mismatch_of_the_copy_is_refused(self):
        with mock.patch.object(
            LocalArtifactImporter, "_partial_digest", return_value="0" * 64
        ):
            result = self.importer.import_artifact(self._write("dm.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("digest", result.error)
        self.assertEqual(self._stored_files(), [])
        self.assertEqual(self._manifests(), [])

    def test_publication_failure_registers_no_manifest(self):
        with mock.patch.object(os, "link", side_effect=OSError("link failed")):
            result = self.importer.import_artifact(self._write("pub.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertEqual(self.store.list_artifacts(), [])
        self.assertEqual(self._manifests(), [])

    def test_manifest_failure_is_reported_as_failed(self):
        with mock.patch.object(
            ModelStore, "save_manifest", side_effect=OSError("disk full")
        ):
            result = self.importer.import_artifact(self._write("mfail.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("manifest", result.error)
        self.assertEqual(self.store.list_artifacts(), [])

    def test_destination_escape_is_refused(self):
        with mock.patch.object(
            ModelStore, "_reject_symlink_components",
            side_effect=UnsafePathError("Path escapes model store"),
        ):
            result = self.importer.import_artifact(self._write("esc.gguf"))
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("escapes", result.error)
        self.assertEqual(self._stored_files(), [])

    def test_symlink_at_the_destination_is_refused(self):
        result = self.importer.import_artifact(self._write("sl.gguf"))
        directory = result.destination.parent
        outside = self.root / "outside.gguf"
        outside.write_bytes(b"x")
        result.destination.unlink()
        result.destination.symlink_to(outside)
        (directory / "manifest.json").unlink()

        again = self.importer.import_artifact(self._write("sl.gguf"))
        self.assertEqual(again.status, ImportStatus.FAILED)
        self.assertIn("Symlink", again.error)
        self.assertEqual(outside.read_bytes(), b"x")


class ResultTypeTests(_ImportCase):
    def test_status_vocabulary_is_its_own(self):
        self.assertEqual(
            {status.value for status in ImportStatus},
            {"imported", "reused", "failed"},
        )

    def test_result_exposes_the_fields_later_stages_need(self):
        result = self.importer.import_artifact(self._write("fields.gguf"), label="f")
        for name in ("status", "content_id", "artifact_id", "label",
                     "sanitized_label", "filename", "destination",
                     "architecture", "error", "warnings"):
            self.assertTrue(hasattr(result, name), name)

    def test_failure_always_carries_a_concrete_reason(self):
        result = self.importer.import_artifact(self.sources / "nope.gguf")
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertTrue(result.error)
        self.assertFalse(result.ok)

    def test_importer_and_reader_agree_on_invalid_gguf(self):
        path = self._write("reader.gguf", b"")
        with self.assertRaises(GGUFReadError):
            read_architecture_evidence(path)
        self.assertEqual(
            self.importer.import_artifact(path).status, ImportStatus.FAILED
        )
