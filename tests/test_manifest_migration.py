import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.manifest_migration import MigrationAction, migrate_model_store
from app.model_store import ModelStore
from app.models import ArtifactSpec, ArtifactState

QWEN_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
QWEN_LOGICAL_ID = "qwen2.5-coder-7b-instruct"
ARTIFACT_BYTES = b"model"
ARTIFACT_SHA256 = hashlib.sha256(ARTIFACT_BYTES).hexdigest()


def legacy_spec(**overrides) -> ArtifactSpec:
    values = {
        "model_id": QWEN_REPOSITORY,
        "source": "huggingface",
        "repository": QWEN_REPOSITORY,
        "filename": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "size_bytes": len(ARTIFACT_BYTES),
        "sha256": ARTIFACT_SHA256,
        "state": ArtifactState.VERIFIED,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class ManifestMigrationTestsBase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ModelStore(Path(self.tempdir.name) / "models")

    def tearDown(self):
        self.tempdir.cleanup()

    def store_legacy_artifact(self, spec=None):
        spec = spec or legacy_spec()
        manifest = self.store.save_manifest(spec)
        manifest.parent.joinpath(spec.filename).write_bytes(ARTIFACT_BYTES)
        return manifest

    def payload_of(self, manifest_path):
        return json.loads(manifest_path.read_text(encoding="utf-8"))


class LegacyManifestMigrationTests(ManifestMigrationTestsBase):
    def test_legacy_manifest_is_migrated_and_directory_renamed(self):
        manifest = self.store_legacy_artifact()
        artifact_id = legacy_spec().artifact_id
        report = migrate_model_store(self.store)
        self.assertEqual(report.migrated, 1)
        migrated_manifest = self.store.root / QWEN_LOGICAL_ID / artifact_id / "manifest.json"
        self.assertTrue(migrated_manifest.exists())
        self.assertFalse(manifest.exists())
        payload = self.payload_of(migrated_manifest)
        self.assertEqual(payload["model_id"], QWEN_LOGICAL_ID)
        self.assertEqual(payload["repository"], QWEN_REPOSITORY)
        self.assertEqual(payload["sha256"], ARTIFACT_SHA256)
        self.assertEqual(payload["state"], "verified")
        artifact_file = migrated_manifest.parent / payload["filename"]
        self.assertEqual(artifact_file.read_bytes(), ARTIFACT_BYTES)
        entry = self.store.list_artifacts()[0]
        self.assertEqual(entry.state, ArtifactState.VERIFIED)
        self.assertEqual(entry.artifact.model_id, QWEN_LOGICAL_ID)

    def test_migration_is_idempotent(self):
        self.store_legacy_artifact()
        migrate_model_store(self.store)
        before = {
            str(path): (path.exists(), path.stat().st_size if path.is_file() else None)
            for path in sorted(self.store.root.rglob("*"))
        }
        second = migrate_model_store(self.store)
        self.assertEqual(second.migrated, 0)
        self.assertEqual(second.unchanged, 1)
        after = {
            str(path): (path.exists(), path.stat().st_size if path.is_file() else None)
            for path in sorted(self.store.root.rglob("*"))
        }
        self.assertEqual(after, before)

    def test_artifact_identity_fields_are_preserved(self):
        spec = legacy_spec()
        self.store_legacy_artifact(spec)
        migrate_model_store(self.store)
        migrated = self.store.list_artifacts()[0].artifact
        self.assertEqual(migrated.artifact_id, spec.artifact_id)
        self.assertEqual(migrated.repository, spec.repository)
        self.assertEqual(migrated.filename, spec.filename)
        self.assertEqual(migrated.sha256, spec.sha256)
        self.assertEqual(migrated.size_bytes, spec.size_bytes)
        self.assertNotEqual(migrated.model_id, migrated.repository)


class UnmappedManifestTests(ManifestMigrationTestsBase):
    def test_unmapped_repository_is_not_touched(self):
        manifest = self.store_legacy_artifact(
            legacy_spec(
                model_id="unknown/model",
                repository="unknown/model",
                filename="other.gguf",
            )
        )
        before = manifest.read_text(encoding="utf-8")
        report = migrate_model_store(self.store)
        self.assertEqual(report.records[0].action, MigrationAction.UNMAPPED)
        self.assertEqual(manifest.read_text(encoding="utf-8"), before)
        self.assertTrue(manifest.exists())


class ConflictManifestTests(ManifestMigrationTestsBase):
    def test_existing_target_directory_is_reported_without_changes(self):
        manifest = self.store_legacy_artifact()
        target = self.store.root / QWEN_LOGICAL_ID
        target.mkdir()
        (target / "keep.txt").write_text("occupied")
        report = migrate_model_store(self.store)
        self.assertEqual(report.records[0].action, MigrationAction.CONFLICT)
        self.assertTrue(manifest.exists())
        self.assertEqual(self.payload_of(manifest)["model_id"], QWEN_REPOSITORY)


class InvalidManifestTests(ManifestMigrationTestsBase):
    def test_corrupt_manifest_is_reported_invalid(self):
        artifact_dir = self.store.root / "some-model" / "some-artifact"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "manifest.json").write_text("{invalid", encoding="utf-8")
        report = migrate_model_store(self.store)
        self.assertEqual(report.records[0].action, MigrationAction.INVALID)

    def test_missing_store_is_a_noop(self):
        report = migrate_model_store(ModelStore(Path(self.tempdir.name) / "absent"))
        self.assertEqual(report.records, ())


if __name__ == "__main__":
    unittest.main()
