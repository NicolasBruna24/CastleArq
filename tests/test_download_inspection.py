import tempfile
import unittest
from pathlib import Path

from app.downloads import (
    ArtifactFilesystemInspector,
    ArtifactFilesystemState,
)
from app.model_store import ModelStore, UnsafePathError
from app.models import ArtifactSpec


def artifact(**overrides) -> ArtifactSpec:
    values = {
        "model_id": "qwen/coder",
        "source": "huggingface",
        "repository": "owner/repository",
        "filename": "model.Q4_K_M.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "download_url": (
            "https://huggingface.co/owner/repository/resolve/main/"
            "model.Q4_K_M.gguf"
        ),
        "size_bytes": 10,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class ArtifactFilesystemInspectorTests(unittest.TestCase):
    def make_store(self, directory):
        return ModelStore(Path(directory))

    def create_artifact_directory(self, store, spec):
        manifest = store.save_manifest(spec)
        return manifest.parent

    def test_clean_state_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "models"
            store = self.make_store(root)
            spec = artifact()
            result = ArtifactFilesystemInspector(store).inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.CLEAN)
            self.assertFalse(result.final_exists)
            self.assertFalse(result.partial_exists)
            self.assertFalse(root.exists())

    def test_partial_only(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact()
            artifact_directory = self.create_artifact_directory(
                self.make_store(Path(directory)), spec
            )
            (artifact_directory / f"{spec.filename}.part").write_bytes(b"part")
            result = ArtifactFilesystemInspector(
                self.make_store(Path(directory))
            ).inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.PARTIAL)
            self.assertFalse(result.final_exists)
            self.assertTrue(result.partial_exists)

    def test_final_only(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact()
            artifact_directory = self.create_artifact_directory(
                self.make_store(Path(directory)), spec
            )
            (artifact_directory / spec.filename).write_bytes(b"final")
            result = ArtifactFilesystemInspector(
                self.make_store(Path(directory))
            ).inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.FINAL_EXISTS)
            self.assertTrue(result.final_exists)
            self.assertFalse(result.partial_exists)

    def test_final_and_partial_are_inconsistent(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact()
            artifact_directory = self.create_artifact_directory(
                self.make_store(Path(directory)), spec
            )
            final = artifact_directory / spec.filename
            partial = artifact_directory / f"{spec.filename}.part"
            final.write_bytes(b"final")
            partial.write_bytes(b"partial")
            result = ArtifactFilesystemInspector(
                self.make_store(Path(directory))
            ).inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.INCONSISTENT)
            self.assertEqual(final.read_bytes(), b"final")
            self.assertEqual(partial.read_bytes(), b"partial")

    def test_final_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            spec = artifact()
            artifact_directory = self.create_artifact_directory(
                self.make_store(Path(directory)), spec
            )
            (artifact_directory / spec.filename).symlink_to(
                Path(outside) / "final"
            )
            with self.assertRaises(UnsafePathError):
                ArtifactFilesystemInspector(
                    self.make_store(Path(directory))
                ).inspect(spec)

    def test_partial_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            spec = artifact()
            artifact_directory = self.create_artifact_directory(
                self.make_store(Path(directory)), spec
            )
            (artifact_directory / f"{spec.filename}.part").symlink_to(
                Path(outside) / "partial"
            )
            with self.assertRaises(UnsafePathError):
                ArtifactFilesystemInspector(
                    self.make_store(Path(directory))
                ).inspect(spec)

    def test_inspection_does_not_modify_files_or_spec(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact()
            store = self.make_store(Path(directory))
            artifact_directory = self.create_artifact_directory(store, spec)
            final = artifact_directory / spec.filename
            partial = artifact_directory / f"{spec.filename}.part"
            final.write_bytes(b"final")
            partial.write_bytes(b"partial")
            manifest = artifact_directory / "manifest.json"
            before_manifest = manifest.read_bytes()
            before_spec = repr(spec)
            result = ArtifactFilesystemInspector(store).inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.INCONSISTENT)
            self.assertEqual(final.read_bytes(), b"final")
            self.assertEqual(partial.read_bytes(), b"partial")
            self.assertEqual(manifest.read_bytes(), before_manifest)
            self.assertEqual(repr(spec), before_spec)

    def test_inspection_does_not_open_http(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact()
            inspector = ArtifactFilesystemInspector(self.make_store(Path(directory)))
            result = inspector.inspect(spec)
            self.assertEqual(result.state, ArtifactFilesystemState.CLEAN)

    def test_unsafe_artifact_identifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UnsafePathError):
                ArtifactFilesystemInspector(self.make_store(Path(directory))).inspect(
                    artifact(model_id="../escape")
                )


if __name__ == "__main__":
    unittest.main()
