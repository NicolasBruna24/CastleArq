import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    PreflightErrorCode,
)
from app.model_store import ModelStore, UnsafePathError
from app.models import ArtifactSpec


def artifact(**overrides) -> ArtifactSpec:
    values = {
        "model_id": "qwen/coder",
        "source": "huggingface",
        "repository": "owner/repository",
        "filename": "model.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class ArtifactExecutionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ModelStore(Path(self.tempdir.name) / "models")
        self.spec = artifact()
        self.directory = self.store.save_manifest(self.spec).parent
        self.final = self.directory / self.spec.filename
        self.partial = self.directory / f"{self.spec.filename}.part"
        self.preflight = ArtifactExecutionPreflight(self.store)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_valid_final_artifact(self):
        self.final.write_bytes(b"model")
        result = self.preflight.validate(self.spec)
        self.assertEqual(result.path, self.final)
        self.assertFalse(result.size_verified)
        self.assertFalse(result.checksum_verified)

    def test_missing_artifact(self):
        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(self.spec)
        self.assertEqual(context.exception.code, PreflightErrorCode.MISSING_ARTIFACT)

    def test_only_partial_is_rejected(self):
        self.partial.write_bytes(b"part")
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(self.spec)

    def test_final_and_partial_are_inconsistent(self):
        self.final.write_bytes(b"final")
        self.partial.write_bytes(b"part")
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(self.spec)

    def test_final_symlink_is_rejected(self):
        self.final.symlink_to(self.directory / "outside")
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(self.spec)

    def test_partial_symlink_is_rejected(self):
        self.partial.symlink_to(self.directory / "outside")
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(self.spec)

    def test_final_directory_is_rejected(self):
        self.final.mkdir()
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(self.spec)

    def test_unsafe_identifiers_are_rejected(self):
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(artifact(model_id="../escape"))
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(artifact(filename="../escape.gguf"))

    def test_model_directory_symlink_is_rejected(self):
        model_dir = self.store.root / "qwen__coder"
        moved = Path(self.tempdir.name) / "moved-model"
        os.rename(model_dir, moved)
        model_dir.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(self.spec)

    def test_artifact_directory_symlink_is_rejected(self):
        artifact_dir = self.directory
        moved = Path(self.tempdir.name) / "moved-artifact"
        os.rename(artifact_dir, moved)
        artifact_dir.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(UnsafePathError):
            self.preflight.validate(self.spec)

    def test_known_size_is_verified(self):
        self.final.write_bytes(b"model")
        result = self.preflight.validate(artifact(size_bytes=5))
        self.assertTrue(result.size_verified)

    def test_incorrect_size_is_rejected(self):
        self.final.write_bytes(b"model")
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(artifact(size_bytes=4))

    def test_unknown_size_is_allowed(self):
        self.final.write_bytes(b"model")
        self.assertFalse(self.preflight.validate(self.spec).size_verified)

    def test_known_checksum_is_verified(self):
        content = b"model"
        self.final.write_bytes(content)
        result = self.preflight.validate(
            artifact(sha256=hashlib.sha256(content).hexdigest())
        )
        self.assertTrue(result.checksum_verified)

    def test_incorrect_checksum_is_rejected(self):
        self.final.write_bytes(b"model")
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(artifact(sha256="0" * 64))

    def test_unknown_checksum_is_allowed(self):
        self.final.write_bytes(b"model")
        self.assertFalse(self.preflight.validate(self.spec).checksum_verified)

    def test_manifest_and_spec_remain_unchanged(self):
        self.final.write_bytes(b"model")
        manifest = self.directory / "manifest.json"
        before = manifest.read_bytes()
        self.preflight.validate(self.spec)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(self.spec, artifact())

    def test_preflight_does_not_delete_or_create_directories(self):
        self.final.write_bytes(b"model")
        before = {path for path in self.store.root.rglob("*")}
        self.preflight.validate(self.spec)
        self.assertEqual({path for path in self.store.root.rglob("*")}, before)

    def test_missing_preflight_does_not_create_model_store_directories(self):
        root = Path(self.tempdir.name) / "missing-models"
        store = ModelStore(root)
        with self.assertRaises(ArtifactPreflightError):
            ArtifactExecutionPreflight(store).validate(self.spec)
        self.assertFalse(root.exists())

    def test_preflight_does_not_access_network(self):
        self.final.write_bytes(b"model")
        with patch("urllib.request.urlopen") as urlopen:
            self.preflight.validate(self.spec)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
