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

"""Pruebas unitarias para OpenVINOImportService.import_directory()."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from castlearq.conversion import OpenVINOImportService, ImportResult
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactState


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def _make_bundle(root: Path, with_tokenizer: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "openvino_model.xml").write_text("<model/>")
    (root / "openvino_model.bin").write_bytes(b"\x00\x01\x02\x03" * 10)
    if with_tokenizer:
        (root / "openvino_tokenizer.xml").write_text("<tok/>")
        (root / "openvino_tokenizer.bin").write_bytes(b"tok-bin")
        (root / "openvino_detokenizer.xml").write_text("<detok/>")
        (root / "openvino_detokenizer.bin").write_bytes(b"detok-bin")
    (root / "config.json").write_text("{}")
    return root


class OpenVINOImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ModelStore(self.root)

    def test_successful_import(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success, result.message)
        self.assertIsInstance(result, ImportResult)
        self.assertIsNotNone(result.artifact)
        self.assertIsNotNone(result.manifest_path)
        self.assertEqual(result.message, "Import completed")

    def test_manifest_fields(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.model_id, "qwen3-8b-int4")
        self.assertEqual(artifact.source, "openvino-import")
        self.assertEqual(artifact.filename, "openvino_model.xml")
        self.assertEqual(artifact.format, "OpenVINO IR")
        self.assertEqual(artifact.backend, "openvino")
        self.assertEqual(artifact.quantization, "INT4")
        self.assertIsNone(artifact.sha256)

    def test_aux_files_and_checksums_copied(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        expected_aux = sorted(
            {
                "openvino_model.bin",
                "openvino_tokenizer.xml",
                "openvino_tokenizer.bin",
                "openvino_detokenizer.xml",
                "openvino_detokenizer.bin",
                "config.json",
            }
        )
        self.assertEqual(sorted(artifact.files), expected_aux)
        managed = self.store.artifact_directory(artifact)
        for aux in artifact.files:
            aux_path = managed / aux
            self.assertTrue(aux_path.exists(), f"aux missing: {aux}")
            expected = artifact.file_checksums.get(aux)
            self.assertIsNotNone(expected, f"no checksum for {aux}")
            self.assertEqual(_sha256(aux_path), expected)

    def test_state_is_downloaded_not_verified(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        inspected = self.store.inspect_manifest(result.manifest_path)
        self.assertEqual(inspected.state, ArtifactState.DOWNLOADED)
        self.assertNotEqual(inspected.state, ArtifactState.VERIFIED)

    def test_source_directory_not_found(self):
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(self.root / "does-not-exist", "m")
        self.assertFalse(result.success)
        self.assertIn("Source directory not found", result.message)

    def test_missing_xml(self):
        src = self.root / "src-no-xml"
        src.mkdir(parents=True)
        (src / "openvino_model.bin").write_bytes(b"weights")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertFalse(result.success)
        self.assertIn("openvino_model.xml", result.message)

    def test_two_primary_xml_rejected(self):
        src = self.root / "src-two-primary"
        src.mkdir(parents=True)
        (src / "openvino_model.xml").write_text("<a/>")
        sub = src / "sub"
        sub.mkdir()
        (sub / "openvino_model.xml").write_text("<b/>")
        (src / "openvino_model.bin").write_bytes(b"w")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertFalse(result.success)
        self.assertIn("Expected exactly one openvino_model.xml", result.message)

    def test_missing_bin_rejected(self):
        src = self.root / "src-no-bin"
        src.mkdir(parents=True)
        (src / "openvino_model.xml").write_text("<model/>")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertFalse(result.success)
        self.assertIn("Missing required .bin weights", result.message)

    def test_symlink_rejected(self):
        src = self.root / "src-symlink"
        src.mkdir(parents=True)
        (src / "openvino_model.xml").write_text("<model/>")
        (src / "openvino_model.bin").write_bytes(b"w")
        target = src / "target.bin"
        target.write_bytes(b"x")
        (src / "link.bin").symlink_to(target)
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertFalse(result.success)
        self.assertIn("Symlink not allowed", result.message)

    def test_collision_not_overwritten(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(r1.success, r1.message)
        r2 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(r2.success)
        self.assertIn("already exists", r2.message)
        manifest = self.store.inspect_manifest(r1.manifest_path)
        self.assertEqual(manifest.state, ArtifactState.DOWNLOADED)
        self.assertEqual(manifest.artifact.model_id, "qwen3-8b-int4")

    def test_collision_different_model_id_allowed(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "model-a")
        self.assertTrue(r1.success, r1.message)
        r2 = svc.import_directory(src, "model-b")
        self.assertTrue(r2.success, r2.message)

    def test_artifact_catalog_listable(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success)
        entries = self.store.list_artifacts()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        artifact = entry.artifact
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.backend, "openvino")
        self.assertEqual(artifact.format, "OpenVINO IR")
        self.assertEqual(artifact.filename, "openvino_model.xml")

    def test_custom_precision(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m", precision="fp16")
        self.assertTrue(result.success, result.message)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact.quantization, "fp16")

    def test_revision_stored(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m", revision="abc123")
        self.assertTrue(result.success, result.message)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact.revision, "abc123")


def _make_bundle_with_git(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "openvino_model.xml").write_text("<model/>")
    (root / "openvino_model.bin").write_bytes(b"\x00\x01\x02\x03" * 10)
    (root / "config.json").write_text("{}")
    git_dir = root / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    objects_dir = git_dir / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    (objects_dir / "dummy.pack").write_bytes(b"\x00\x01\x02\x03")
    return root


class OpenVINOImportGitExclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ModelStore(self.root)

    def test_git_files_not_copied(self):
        src = _make_bundle_with_git(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success, result.message)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        managed = self.store.artifact_directory(artifact)
        git_files = list(managed.rglob(".git/*")) + list(managed.rglob("**/.git/*"))
        self.assertEqual(len(git_files), 0, f"Se copiaron archivos de .git: {git_files}")
        self.assertTrue((managed / "openvino_model.xml").exists())
        self.assertTrue((managed / "openvino_model.bin").exists())

    def test_git_not_in_files_or_checksums(self):
        src = _make_bundle_with_git(self.root / "src")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(result.success)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        for entry in artifact.files:
            self.assertFalse(entry.startswith(".git/"), f".git/ archivo inesperado en files: {entry}")
        for name in artifact.file_checksums:
            self.assertFalse(name.startswith(".git/"), f".git/ checksum inesperado: {name}")

    def test_hidden_non_git_files_are_not_excluded(self):
        src = self.root / "src-hidden"
        src.mkdir(parents=True)
        (src / "openvino_model.xml").write_text("<model/>")
        (src / "openvino_model.bin").write_bytes(b"\x00\x01\x02\x03" * 10)
        (src / ".legit-hidden-file").write_text("hidden metadata")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertTrue(result.success, result.message)
        artifact = result.artifact
        self.assertIsNotNone(artifact)
        self.assertIn(".legit-hidden-file", artifact.files)
        self.assertIn(".legit-hidden-file", artifact.file_checksums)


class OpenVINOImportDestinationProtectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ModelStore(self.root)

    def test_preexisting_destination_with_files_rejected(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(r1.success, r1.message)
        managed = self.store.artifact_directory(r1.artifact)
        target = managed / "openvino_model.bin"
        original_bytes = target.read_bytes()
        target.write_bytes(b"corrupted")

        r2 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(r2.success)
        self.assertIn("already exists", r2.message)
        # La importación rechazada no debe sobrescribir el archivo corrupto
        self.assertEqual(target.read_bytes(), b"corrupted")

    def test_preexisting_destination_without_manifest_rejected(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(r1.success, r1.message)
        managed = self.store.artifact_directory(r1.artifact)
        (managed / "manifest.json").unlink()

        r2 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(r2.success)
        self.assertIn("already exists", r2.message)

    def test_preexisting_empty_destination_rejected(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(r1.success, r1.message)
        managed = self.store.artifact_directory(r1.artifact)
        for p in managed.rglob("*"):
            if p.is_file():
                p.unlink()

        r2 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(r2.success)
        self.assertIn("already exists", r2.message)

    def test_conflict_leaves_no_new_files(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        r1 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertTrue(r1.success, r1.message)
        managed = self.store.artifact_directory(r1.artifact)
        files_before = set(p.relative_to(managed) for p in managed.rglob("*") if p.is_file())

        r2 = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(r2.success)
        files_after = set(p.relative_to(managed) for p in managed.rglob("*") if p.is_file())
        self.assertEqual(files_before, files_after, "El conflicto no debe crear ni modificar archivos")


class OpenVINOImportFailureCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ModelStore(self.root)

    def test_manifest_save_failure_returns_failure(self):
        src = _make_bundle(self.root / "src")
        svc = OpenVINOImportService(self.store)
        with unittest.mock.patch.object(self.store, "save_manifest", side_effect=RuntimeError("boom")):
            result = svc.import_directory(src, "qwen3-8b-int4")
        self.assertFalse(result.success)
        self.assertIn("boom", result.message)

    def test_no_xml_rejected(self):
        src = self.root / "src"
        src.mkdir()
        (src / "openvino_model.bin").write_bytes(b"x")
        svc = OpenVINOImportService(self.store)
        result = svc.import_directory(src, "m")
        self.assertFalse(result.success)

if __name__ == "__main__":
    unittest.main()