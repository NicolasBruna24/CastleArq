import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from app.downloads import ArtifactCleanup, CleanupOperation, CleanupResult
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
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class ArtifactCleanupTests(unittest.TestCase):
    def setup_artifact(self, directory, spec=None):
        spec = spec or artifact()
        store = ModelStore(Path(directory))
        manifest = store.save_manifest(spec)
        return store, spec, manifest.parent

    def test_delete_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            partial = path / f"{spec.filename}.part"
            partial.write_bytes(b"partial")
            result = ArtifactCleanup(store).execute(
                spec, CleanupOperation.DELETE_PARTIAL
            )
            self.assertEqual(result, CleanupResult(
                CleanupOperation.DELETE_PARTIAL, True, True, "Cleanup target deleted"
            ))
            self.assertFalse(partial.exists())

    def test_delete_partial_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            result = ArtifactCleanup(store).execute(
                spec, CleanupOperation.DELETE_PARTIAL
            )
            self.assertTrue(result.success)
            self.assertFalse(result.changed)
            self.assertFalse((path / f"{spec.filename}.part").exists())

    def test_delete_partial_never_deletes_final(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            final = path / spec.filename
            final.write_bytes(b"final")
            ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_PARTIAL)
            self.assertEqual(final.read_bytes(), b"final")

    def test_delete_final(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            final = path / spec.filename
            final.write_bytes(b"final")
            result = ArtifactCleanup(store).execute(
                spec, CleanupOperation.DELETE_FINAL
            )
            self.assertTrue(result.success)
            self.assertTrue(result.changed)
            self.assertFalse(final.exists())

    def test_delete_final_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, _path = self.setup_artifact(directory)
            result = ArtifactCleanup(store).execute(
                spec, CleanupOperation.DELETE_FINAL
            )
            self.assertTrue(result.success)
            self.assertFalse(result.changed)

    def test_delete_final_never_deletes_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            partial = path / f"{spec.filename}.part"
            partial.write_bytes(b"partial")
            ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_FINAL)
            self.assertEqual(partial.read_bytes(), b"partial")

    def test_inconsistent_state_operations_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            final = path / spec.filename
            partial = path / f"{spec.filename}.part"
            final.write_bytes(b"final")
            partial.write_bytes(b"partial")
            ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_PARTIAL)
            self.assertTrue(final.exists())
            self.assertFalse(partial.exists())
            partial.write_bytes(b"partial")
            ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_FINAL)
            self.assertFalse(final.exists())
            self.assertTrue(partial.exists())

    def test_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            store, spec, path = self.setup_artifact(directory)
            target = Path(outside) / "target"
            partial = path / f"{spec.filename}.part"
            partial.symlink_to(target)
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_PARTIAL)
            partial.unlink()
            (path / spec.filename).symlink_to(target)
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_FINAL)

    def test_unsafe_paths_and_directories_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(store).execute(
                    artifact(model_id="../escape"), CleanupOperation.DELETE_FINAL
                )
            store, spec, path = self.setup_artifact(directory)
            (path / spec.filename).unlink(missing_ok=True)
            (path / spec.filename).mkdir()
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_FINAL)

    def test_root_model_and_artifact_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory) / "models"
            root.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(ModelStore(root)).execute(
                    artifact(), CleanupOperation.DELETE_FINAL
                )

    def test_model_and_artifact_directory_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            spec = artifact()
            model_link = root / "qwen__coder"
            model_link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(ModelStore(root)).execute(
                    spec, CleanupOperation.DELETE_FINAL
                )

            model_link.unlink()
            model_link.mkdir()
            artifact_link = model_link / spec.artifact_id
            artifact_link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(ModelStore(root)).execute(
                    spec, CleanupOperation.DELETE_FINAL
                )

    def test_manifest_and_spec_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, path = self.setup_artifact(directory)
            manifest = path / "manifest.json"
            before_manifest = manifest.read_bytes()
            before_spec = repr(spec)
            (path / f"{spec.filename}.part").write_bytes(b"partial")
            ArtifactCleanup(store).execute(spec, CleanupOperation.DELETE_PARTIAL)
            self.assertEqual(manifest.read_bytes(), before_manifest)
            self.assertEqual(repr(spec), before_spec)

    def test_manifest_filename_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            store, valid_spec, path = self.setup_artifact(directory)
            manifest = path / "manifest.json"
            before = manifest.read_bytes()
            malicious_spec = artifact(
                model_id=valid_spec.model_id,
                filename="manifest.json",
            )
            with self.assertRaises(UnsafePathError):
                ArtifactCleanup(store).execute(
                    malicious_spec,
                    CleanupOperation.DELETE_FINAL,
                )
            self.assertTrue(manifest.exists())
            self.assertEqual(manifest.read_bytes(), before)

    def test_result_is_frozen(self):
        result = CleanupResult(CleanupOperation.DELETE_FINAL, True, False, "unchanged")
        with self.assertRaises(FrozenInstanceError):
            result.changed = True

    def test_invalid_operation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, _path = self.setup_artifact(directory)
            with self.assertRaises(ValueError):
                ArtifactCleanup(store).execute(spec, "delete_final")

    def test_cleanup_does_not_access_network(self):
        with tempfile.TemporaryDirectory() as directory:
            store, spec, _path = self.setup_artifact(directory)
            result = ArtifactCleanup(store).execute(
                spec, CleanupOperation.DELETE_FINAL
            )
            self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
