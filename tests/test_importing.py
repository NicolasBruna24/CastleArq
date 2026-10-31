# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Tests for physical import of local GGUF artifacts (B9.67, A2.6.4)."""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from castlearq.execution import ArtifactExecutionPreflight
from castlearq.importing import ImportStatus, LocalArtifactImporter
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState


def _gguf(entries=(), *, version=3, magic=b"GGUF"):
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


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


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


class IntegrityImportTests(_ImportCase):
    def test_import_persists_content_id_and_sha256_equal(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertIsNotNone(result.content_id)
        self.assertEqual(result.artifact.content_id, result.content_id)
        self.assertEqual(result.artifact.sha256, result.content_id)

    def test_manifest_persists_both_values(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        manifests = list(self.store.root.rglob("manifest.json"))
        self.assertEqual(len(manifests), 1)
        payload = json.loads(manifests[0].read_text())
        self.assertEqual(payload["content_id"], result.content_id)
        self.assertEqual(payload["sha256"], result.content_id)

    def test_inspect_manifest_verified_if_unchanged(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        stored = self.store.list_artifacts()[0]
        inspected = self.store.inspect_manifest(stored.manifest_path, verify=True)
        self.assertEqual(inspected.state, ArtifactState.VERIFIED)

    def test_modified_content_produces_failed(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        stored = self.store.list_artifacts()[0]
        stored_file = stored.manifest_path.parent / stored.artifact.filename
        stored_file.write_bytes(b"tampered content")
        inspected = self.store.inspect_manifest(stored.manifest_path, verify=True)
        self.assertEqual(inspected.state, ArtifactState.FAILED)

    def test_preflight_rejects_modified_content(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        stored = self.store.list_artifacts()[0]
        stored_file = stored.manifest_path.parent / stored.artifact.filename
        original_size = stored_file.stat().st_size
        stored_file.write_bytes(b"X" * original_size)
        inspected = self.store.inspect_manifest(stored.manifest_path, verify=True)
        preflight = ArtifactExecutionPreflight(self.store)
        with self.assertRaises(Exception) as ctx:
            preflight.validate(inspected.artifact)
        self.assertIn("SHA-256", str(ctx.exception).upper())

    def test_same_size_replacement_detected(self):
        result = self.importer.import_artifact(self._write("model.gguf"))
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        stored = self.store.list_artifacts()[0]
        stored_file = stored.manifest_path.parent / stored.artifact.filename
        original_size = stored_file.stat().st_size
        replacement = b"X" * original_size
        stored_file.write_bytes(replacement)
        inspected = self.store.inspect_manifest(stored.manifest_path, verify=True)
        self.assertEqual(inspected.state, ArtifactState.FAILED)


class LegacyManifestTests(_ImportCase):
    def test_legacy_manifest_without_sha256_stays_downloaded(self):
        manifest_dir = self.store.root / "legacy_model" / "legacy_artifact"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        content = b"legacy content"
        (manifest_dir / "legacy.gguf").write_bytes(content)
        manifest = {
            "model_id": "legacy_model",
            "source": None,
            "repository": None,
            "filename": "legacy.gguf",
            "format": "GGUF",
            "quantization": "Unknown",
            "download_url": None,
            "size_bytes": len(content),
            "sha256": None,
            "content_id": "a" * 64,
            "revision": None,
            "files": [],
            "files_sha256": {},
        }
        (manifest_dir / "manifest.json").write_text(json.dumps(manifest))
        stored = self.store.inspect_manifest(manifest_dir / "manifest.json", verify=True)
        self.assertEqual(stored.state, ArtifactState.DOWNLOADED)


if __name__ == "__main__":
    unittest.main()
