import tempfile
import unittest
import hashlib
from pathlib import Path

from app.model_catalog import get_catalog
from app.model_store import ModelStore
from app.models import ArtifactSpec, ArtifactState
from app.resolver import ModelArtifactResolutionError, ModelArtifactResolver


class ModelArtifactResolverTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ModelStore(Path(self.tempdir.name) / "models")
        self.model = get_catalog()[0]

    def tearDown(self):
        self.tempdir.cleanup()

    def _artifact(self, *, filename="model.Q4_K_M.gguf", state=ArtifactState.VERIFIED):
        return ArtifactSpec(
            model_id=self.model.model_id,
            source="huggingface",
            repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            filename=filename,
            format="GGUF",
            quantization=filename.removesuffix(".gguf").rsplit(".", 1)[-1],
            state=state,
        )

    def _store_artifact(self, artifact, *, final=True, partial=False):
        directory = self.store.save_manifest(artifact).parent
        if final:
            (directory / artifact.filename).write_bytes(b"model")
        if partial:
            (directory / f"{artifact.filename}.part").write_bytes(b"part")

    def test_resolves_logical_model_to_local_artifact(self):
        artifact = self._artifact()
        self._store_artifact(artifact)

        result = ModelArtifactResolver(self.store).resolve(self.model.model_id)

        self.assertEqual(result.model, self.model)
        self.assertEqual(result.artifact, artifact)

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ModelArtifactResolutionError, "not found"):
            ModelArtifactResolver(self.store).resolve("unknown-model")

    def test_repository_id_is_not_a_canonical_model_id(self):
        self._store_artifact(self._artifact())
        with self.assertRaisesRegex(ModelArtifactResolutionError, "not found"):
            ModelArtifactResolver(self.store).resolve(
                "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
            )

    def test_artifacts_of_other_logical_models_do_not_match(self):
        artifact = self._artifact()
        artifact = ArtifactSpec(
            **{**artifact.__dict__, "model_id": "other/unrelated-model"}
        )
        self._store_artifact(artifact)
        with self.assertRaisesRegex(ModelArtifactResolutionError, "No local artifact"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_repository_name_similarity_does_not_create_identity(self):
        artifact = self._artifact()
        artifact = ArtifactSpec(
            **{
                **artifact.__dict__,
                "model_id": "other/model",
                "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            }
        )
        self._store_artifact(artifact)
        with self.assertRaisesRegex(ModelArtifactResolutionError, "No local artifact"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_missing_artifact_is_rejected(self):
        artifact = self._artifact()
        self._store_artifact(artifact, final=False)

        with self.assertRaisesRegex(ModelArtifactResolutionError, "not available"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_partial_artifact_is_rejected(self):
        artifact = self._artifact()
        self._store_artifact(artifact, final=False, partial=True)

        with self.assertRaisesRegex(ModelArtifactResolutionError, "incomplete"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_final_and_partial_artifacts_are_rejected(self):
        artifact = self._artifact()
        self._store_artifact(artifact, partial=True)

        with self.assertRaisesRegex(ModelArtifactResolutionError, "incomplete"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_corrupt_artifact_is_rejected(self):
        artifact = self._artifact()
        artifact = ArtifactSpec(
            **{
                **artifact.__dict__,
                "size_bytes": 10,
                "sha256": hashlib.sha256(b"expected").hexdigest(),
            }
        )
        self._store_artifact(artifact)

        with self.assertRaisesRegex(ModelArtifactResolutionError, "invalid"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_multiple_usable_artifacts_are_rejected(self):
        self._store_artifact(self._artifact(filename="model.Q4_K_M.gguf"))
        self._store_artifact(self._artifact(filename="model.Q8_0.gguf"))

        with self.assertRaisesRegex(ModelArtifactResolutionError, "Multiple"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_arbitrary_path_is_not_a_model_identity(self):
        with self.assertRaises(ModelArtifactResolutionError):
            ModelArtifactResolver(self.store).resolve("/home/user/model.gguf")

    def test_resolution_does_not_create_or_modify_store(self):
        before = set(self.store.root.rglob("*")) if self.store.root.exists() else set()
        with self.assertRaises(ModelArtifactResolutionError):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)
        after = set(self.store.root.rglob("*")) if self.store.root.exists() else set()
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
