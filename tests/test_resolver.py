
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

import tempfile
import unittest
import hashlib
from dataclasses import replace
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

    def _artifact(self, *, filename="model.Q4_K_M.gguf", state=ArtifactState.NOT_DOWNLOADED):
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
        manifest = self.store.save_manifest(artifact)
        directory = manifest.parent
        if final:
            (directory / artifact.filename).write_bytes(b"model")
        if partial:
            (directory / f"{artifact.filename}.part").write_bytes(b"part")
        return manifest

    def test_resolves_logical_model_to_local_artifact(self):
        # B9.41: seeded VERIFIED in memory to prove it never round-trips —
        # new manifests persist declared metadata + acquisition only.
        artifact = self._artifact(state=ArtifactState.VERIFIED)
        manifest = self._store_artifact(artifact)

        result = ModelArtifactResolver(self.store).resolve(self.model.model_id)

        self.assertEqual(result.model, self.model)
        # Identity and declared metadata survive the persist/read round-trip
        # (artifact_id, repository, format, quantization, size, sha256…),
        # while the resolved spec carries the discovery default instead of the
        # seeded state: `state` is no longer part of the manifest schema.
        self.assertEqual(
            result.artifact,
            replace(artifact, state=ArtifactState.NOT_DOWNLOADED),
        )
        # The local state authority is the derivation over manifest
        # expectations + filesystem, never a persisted field.
        self.assertEqual(
            self.store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADED
        )

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

        with self.assertRaisesRegex(ModelArtifactResolutionError, "(?i)multiple"):
            ModelArtifactResolver(self.store).resolve(self.model.model_id)

    def test_multiple_usable_artifacts_quantization_selects_correct(self):
        q4 = self._artifact(filename="model.Q4_K_M.gguf")
        q8 = self._artifact(filename="model.Q8_0.gguf")
        self._store_artifact(q4)
        self._store_artifact(q8)

        result = ModelArtifactResolver(self.store).resolve(
            self.model.model_id, quantization="Q4_K_M"
        )
        self.assertEqual(result.artifact, q4)

        result8 = ModelArtifactResolver(self.store).resolve(
            self.model.model_id, quantization="q8_0"
        )
        self.assertEqual(result8.artifact, q8)

    def test_multiple_usable_artifacts_filename_selects_correct(self):
        q4 = self._artifact(filename="model.Q4_K_M.gguf")
        q8 = self._artifact(filename="model.Q8_0.gguf")
        self._store_artifact(q4)
        self._store_artifact(q8)

        result = ModelArtifactResolver(self.store).resolve(
            self.model.model_id, filename="model.Q8_0.gguf"
        )
        self.assertEqual(result.artifact, q8)

    def test_multiple_usable_artifacts_both_selectors_succeeds(self):
        q4 = self._artifact(filename="model.Q4_K_M.gguf")
        q8 = self._artifact(filename="model.Q8_0.gguf")
        self._store_artifact(q4)
        self._store_artifact(q8)

        result = ModelArtifactResolver(self.store).resolve(
            self.model.model_id, quantization="Q4_K_M", filename="model.Q4_K_M.gguf"
        )
        self.assertEqual(result.artifact, q4)

    def test_multiple_usable_artifacts_both_selectors_conflicting_raises(self):
        self._store_artifact(self._artifact(filename="model.Q4_K_M.gguf"))
        self._store_artifact(self._artifact(filename="model.Q8_0.gguf"))

        with self.assertRaisesRegex(ModelArtifactResolutionError, "No artifact matches both"):
            ModelArtifactResolver(self.store).resolve(
                self.model.model_id, quantization="Q4_K_M", filename="model.Q8_0.gguf"
            )

    def test_multiple_usable_artifacts_invalid_quantization_raises(self):
        self._store_artifact(self._artifact(filename="model.Q4_K_M.gguf"))

        with self.assertRaisesRegex(ModelArtifactResolutionError, "No artifact matches quantization"):
            ModelArtifactResolver(self.store).resolve(
                self.model.model_id, quantization="Q9_K_M"
            )

    def test_multiple_usable_artifacts_invalid_filename_raises(self):
        self._store_artifact(self._artifact(filename="model.Q4_K_M.gguf"))

        with self.assertRaisesRegex(ModelArtifactResolutionError, "No artifact matches filename"):
            ModelArtifactResolver(self.store).resolve(
                self.model.model_id, filename="missing.gguf"
            )

    def test_multiple_usable_artifacts_ambiguous_quantization_demands_filename(self):
        self._store_artifact(self._artifact(filename="shard1.Q4_K_M.gguf"))
        self._store_artifact(self._artifact(filename="shard2.Q4_K_M.gguf"))

        with self.assertRaisesRegex(ModelArtifactResolutionError, "--filename"):
            ModelArtifactResolver(self.store).resolve(
                self.model.model_id, quantization="Q4_K_M"
            )

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
