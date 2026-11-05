import json
import tempfile
import unittest
from pathlib import Path

from castlearq.model_store import ModelStore, UnsafePathError
from castlearq.models import ArtifactSpec, ArtifactState


class RepairLegacyOpenVINOTests(unittest.TestCase):
    def test_external_manifest_is_rejected(self):
        # A. Path security: a manifest living outside the store root must be
        # rejected by the public read-only inspection API. The store owns the
        # root; a foreign manifest path escapes the namespace.
        with tempfile.TemporaryDirectory() as store_dir, tempfile.TemporaryDirectory() as manifest_dir:
            store = ModelStore(Path(store_dir))
            manifest_path = Path(manifest_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "model_id": "test-model",
                        "filename": "model.xml",
                    }
                ),
                encoding="utf-8",
            )
            entry = store.inspect_manifest(manifest_path)
            self.assertEqual(entry.state, ArtifactState.FAILED)
            self.assertIn("escapes", entry.message)

    def test_content_id_mismatch_fails_inspection(self):
        # B. Integrity guarantee B9.67: a manifest that declares a content_id
        # deliberately inconsistent with the physical bytes must fail
        # verification. The policy is content-based, not field-based: the
        # presence of `content_id` alone is insufficient -- it must match the
        # observed bytes.
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = ArtifactSpec(
                model_id="test-model",
                source="test",
                repository="test/repo",
                filename="model.xml",
                format="OPENVINO",
                backend="openvino",
                content_id="wrong-content-id-0123456789abcdef",
            )
            manifest = store.save_manifest(spec)
            # The real artifact file must exist at the expected managed path.
            artifact_dir = store.artifact_directory(spec)
            (artifact_dir / "model.xml").write_bytes(b"real file content")
            entry = store.inspect_manifest(manifest, verify=True)
            self.assertEqual(entry.state, ArtifactState.FAILED)
            self.assertIn("content_id", entry.message)

    def test_symlinked_artifact_file_is_rejected(self):
        # C. Symlink safety: an artifact that resolves through a symlink must
        # be refused, even when the link target lives outside the store. The
        # check runs through the public inspection API, not a raw os.lstat.
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = ArtifactSpec(
                model_id="test-model",
                source="test",
                repository="test/repo",
                filename="model.xml",
                format="OPENVINO",
                backend="openvino",
            )
            manifest = store.save_manifest(spec)
            managed_dir = store.artifact_directory(spec)
            # Target file outside the managed directory.
            target = Path(directory) / "link-target"
            target.write_bytes(b"target content")
            # Replace the expected artifact with a symlink to the external target.
            link = managed_dir / spec.filename
            if link.exists():
                link.unlink()
            link.symlink_to(target)
            entry = store.inspect_manifest(manifest, verify=True)
            self.assertEqual(entry.state, ArtifactState.FAILED)
            self.assertIn("symlink", entry.message.lower())


if __name__ == "__main__":
    unittest.main()
