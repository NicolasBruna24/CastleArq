
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

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import castlearq.model_store
from castlearq.model_store import ModelStore, UnsafePathError, default_models_directory
from castlearq.models import ArtifactSpec, ArtifactState


def artifact(**kwargs) -> ArtifactSpec:
    values = {
        "model_id": "qwen/coder",
        "source": "huggingface",
        "repository": "owner/repository",
        "filename": "model-q4.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    }
    values.update(kwargs)
    return ArtifactSpec(**values)


class ModelStoreTests(unittest.TestCase):
    def test_default_directory_is_expanded(self):
        self.assertNotIn("~", str(default_models_directory()))

    def test_manifest_is_written_and_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact())
            self.assertTrue(manifest.exists())
            entries = store.list_artifacts()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].state, ArtifactState.NOT_DOWNLOADED)

    def test_saved_manifest_omits_state_and_verified(self):
        # B9.41: new manifests persist declared metadata + acquisition record
        # only; the in-memory state never leaks into the payload.
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(state=ArtifactState.VERIFIED)
            manifest = store.save_manifest(spec)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertNotIn("state", payload)
            self.assertNotIn("verified", payload)
            # The acquisition/registration timestamp remains.
            self.assertIn("downloaded_at", payload)
            datetime.fromisoformat(payload["downloaded_at"])
            # The declared metadata contract is intact.
            for key in (
                "model_id",
                "source",
                "repository",
                "filename",
                "format",
                "quantization",
                "download_url",
                "size_bytes",
                "sha256",
            ):
                self.assertIn(key, payload)

    def test_verified_artifact_requires_matching_size_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            content = b"model"
            checksum = hashlib.sha256(content).hexdigest()
            spec = artifact(size_bytes=len(content), sha256=checksum)
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename).write_bytes(content)
            entry = store.inspect_manifest(manifest)
            self.assertEqual(entry.state, ArtifactState.VERIFIED)

    def test_checksum_mismatch_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=5, sha256="0" * 64)
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename).write_bytes(b"model")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)

    def test_no_checksum_is_downloaded_not_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=5)
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename).write_bytes(b"model")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADED)

    def test_existing_partial_file_is_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact()
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename + ".part").write_bytes(b"part")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADING)

    def test_corrupt_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "model" / "artifact"
            root.mkdir(parents=True)
            manifest = root / "manifest.json"
            manifest.write_text("{invalid", encoding="utf-8")
            entry = ModelStore(Path(directory)).list_artifacts()[0]
            self.assertEqual(entry.state, ArtifactState.FAILED)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UnsafePathError):
                ModelStore(Path(directory)).save_manifest(artifact(model_id="../escape"))
            with self.assertRaises(UnsafePathError):
                ModelStore(Path(directory)).save_manifest(artifact(filename="../model.gguf"))

    def test_symlink_model_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / "qwen__coder").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                ModelStore(root).save_manifest(artifact())

    def test_symlink_artifact_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            spec = artifact()
            model_dir = root / "qwen__coder"
            model_dir.mkdir()
            (model_dir / spec.artifact_id).symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                ModelStore(root).save_manifest(spec)

    def test_symlink_manifest_and_temporary_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact())
            manifest.unlink()
            manifest.symlink_to(Path(outside) / "manifest.json")
            with self.assertRaises(UnsafePathError):
                store.save_manifest(artifact())
            manifest.unlink()
            temporary = manifest.with_name("manifest.json.part")
            temporary.symlink_to(Path(outside) / "manifest.part")
            with self.assertRaises(UnsafePathError):
                store.save_manifest(artifact())

    def test_symlink_artifact_files_are_failed(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact())
            target = Path(outside) / "model.gguf"
            target.write_bytes(b"model")
            final = manifest.parent / "model-q4.gguf"
            final.symlink_to(target)
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)
            final.unlink()
            partial = final.with_name(final.name + ".part")
            partial.symlink_to(target)
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)

    def test_internal_symlinks_are_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ModelStore(root)
            manifest = store.save_manifest(artifact())
            artifact_dir = manifest.parent
            other = root / "other"
            other.mkdir()
            (other / "manifest.json").write_text("{}", encoding="utf-8")
            (other / "model.gguf").write_bytes(b"model")
            (other / "model.gguf.part").write_bytes(b"part")

            manifest.unlink()
            manifest.symlink_to(other / "manifest.json")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)

            manifest.unlink()
            manifest.write_text(
                json.dumps({
                    "model_id": "qwen/coder",
                    "source": "huggingface",
                    "repository": "owner/repository",
                    "filename": "model-q4.gguf",
                }),
                encoding="utf-8",
            )
            final = artifact_dir / "model-q4.gguf"
            final.symlink_to(other / "model.gguf")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)
            final.unlink()
            partial = artifact_dir / "model-q4.gguf.part"
            partial.symlink_to(other / "model.gguf.part")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.FAILED)

    def test_internal_directory_symlinks_are_rejected_on_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ModelStore(root)
            other = root / "other"
            other.mkdir()
            model_link = root / "qwen__coder"
            model_link.symlink_to(other, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                store.save_manifest(artifact())

            model_link.unlink()
            model_link.mkdir()
            artifact_link = model_link / artifact().artifact_id
            artifact_link.symlink_to(other, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                store.save_manifest(artifact())

    def test_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as target:
            root = Path(directory) / "models"
            root.symlink_to(target, target_is_directory=True)
            store = ModelStore(root)
            with self.assertRaises(UnsafePathError):
                store.save_manifest(artifact())

    def test_normal_paths_still_work(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact())
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.NOT_DOWNLOADED)

    def test_manifest_state_is_recomputed_from_filesystem(self):
        # B9.41: new manifests no longer persist `state`, so the legacy field
        # is seeded by hand: even a manifest claiming VERIFIED is only an
        # expectation record — the derived state comes from the filesystem.
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact(size_bytes=5))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["state"] = ArtifactState.VERIFIED.value
            payload["verified"] = True
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            manifest.parent.joinpath("model-q4.gguf").write_bytes(b"model")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADED)

    def test_legacy_persisted_state_is_never_authoritative(self):
        # B9.41: legacy `state`/`verified` are read tolerantly but must never
        # become the source of truth, in either direction.
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            content = b"model"
            spec = artifact(
                size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest()
            )
            manifest = store.save_manifest(spec)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            # A legacy manifest claiming VERIFIED does not invent a file.
            payload["state"] = ArtifactState.VERIFIED.value
            payload["verified"] = True
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                store.inspect_manifest(manifest).state, ArtifactState.NOT_DOWNLOADED
            )
            # A legacy manifest claiming NOT_DOWNLOADED does not hide a file
            # that meets the declared expectations.
            manifest.parent.joinpath(spec.filename).write_bytes(content)
            payload["state"] = ArtifactState.NOT_DOWNLOADED.value
            payload["verified"] = False
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                store.inspect_manifest(manifest).state, ArtifactState.VERIFIED
            )

    def test_missing_directory_is_not_created_by_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            self.assertEqual(ModelStore(root).list_artifacts(), [])
            self.assertFalse(root.exists())

    def test_custom_tilde_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text('[models]\ndirectory = "~/localai-test"\n', encoding="utf-8")
            self.assertNotIn("~", str(default_models_directory(config)))

    def test_new_default_used_when_no_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            home = os.path.join(directory, "fake-home")
            os.makedirs(home)
            missing_config = Path(directory) / "does-not-exist.toml"
            with mock.patch(
                "castlearq.model_store.os.path.expanduser",
                lambda p: p.replace("~", home) if p.startswith("~") else p,
            ):
                result = default_models_directory(missing_config)
            self.assertIn("castlearq", str(result))
            self.assertNotIn("localai-hub", str(result))

    def test_fallback_to_legacy_when_new_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = os.path.join(directory, "fake-home")
            legacy = os.path.join(home, ".local", "share", "localai-hub", "models")
            os.makedirs(legacy)
            missing_config = Path(directory) / "does-not-exist.toml"
            with mock.patch(
                "castlearq.model_store.os.path.expanduser",
                lambda p: p.replace("~", home) if p.startswith("~") else p,
            ):
                result = default_models_directory(missing_config)
            self.assertIn("localai-hub", str(result))

    def test_new_takes_priority_over_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            home = os.path.join(directory, "fake-home")
            legacy = os.path.join(home, ".local", "share", "localai-hub", "models")
            new = os.path.join(home, ".local", "share", "castlearq", "models")
            os.makedirs(legacy)
            os.makedirs(new)
            missing_config = Path(directory) / "does-not-exist.toml"
            with mock.patch(
                "castlearq.model_store.os.path.expanduser",
                lambda p: p.replace("~", home) if p.startswith("~") else p,
            ):
                result = default_models_directory(missing_config)
            self.assertIn("castlearq", str(result))

    def test_manifest_is_json(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            manifest = store.save_manifest(artifact())
            self.assertIsInstance(json.loads(manifest.read_text()), dict)


class Sha256RecomputationTests(unittest.TestCase):
    """The SHA-256 recomputation performed by ``ModelStore``.

    B9.41 §6.1 ("Derived State Rules"), operative rule 1: the local artifact
    state is recomputed on every inspection and nothing caches it between
    invocations. The manifest supplies the *expectations* (size, sha256);
    the filesystem supplies the *observation*; the comparison yields the
    derived state. These tests therefore assert that the digest is
    recomputed on each inspection, that a changed file is observed as
    changed, and that a wrong checksum keeps failing. They deliberately
    assert no reuse: there is no in-memory SHA-256 cache in ``ModelStore``.

    This class replaces an uncommitted local ``Sha256CacheTests`` class
    that expected the second inspection to reuse a cached digest. That
    expectation contradicts B9.41 §6.1 rule 1 and the frozen pillar
    ``test_manifest_state_is_recomputed_from_filesystem`` (T-2), which is
    the normative guarantee that the derived state comes from the
    filesystem. No caching behaviour was introduced.
    """

    def _store_with_artifact(self, directory, content, **kwargs):
        store = ModelStore(Path(directory))
        spec = artifact(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), **kwargs)
        manifest = store.save_manifest(spec)
        manifest.parent.joinpath(spec.filename).write_bytes(content)
        return store, manifest, spec

    def test_first_inspection_computes_sha256(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"model"
            store, manifest, _ = self._store_with_artifact(directory, content)
            with mock.patch(
                "castlearq.model_store._sha256", wraps=castlearq.model_store._sha256
            ) as hashed:
                entry = store.inspect_manifest(manifest)
            self.assertEqual(entry.state, ArtifactState.VERIFIED)
            self.assertEqual(hashed.call_count, 1)

    def test_second_inspection_recomputes_the_digest(self):
        # B9.41 §6.1 rule 1: the state is derived on every inspection, so the
        # digest is recomputed rather than reused.
        with tempfile.TemporaryDirectory() as directory:
            content = b"model"
            store, manifest, _ = self._store_with_artifact(directory, content)
            with mock.patch(
                "castlearq.model_store._sha256", wraps=castlearq.model_store._sha256
            ) as hashed:
                store.inspect_manifest(manifest)
                store.inspect_manifest(manifest)
            self.assertEqual(hashed.call_count, 2)

    def test_changed_file_is_recomputed_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"model"
            store, manifest, spec = self._store_with_artifact(directory, content)
            with mock.patch(
                "castlearq.model_store._sha256", wraps=castlearq.model_store._sha256
            ) as hashed:
                store.inspect_manifest(manifest)
                # A detectable change: different bytes of the same length, so
                # the size matches but the content (and its timestamps) does
                # not.
                manifest.parent.joinpath(spec.filename).write_bytes(b"MODEL")
                entry = store.inspect_manifest(manifest)
            self.assertEqual(hashed.call_count, 2)
            self.assertEqual(entry.state, ArtifactState.FAILED)

    def test_wrong_checksum_still_fails_on_every_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"model"
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=len(content), sha256="0" * 64)
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename).write_bytes(content)
            first = store.inspect_manifest(manifest)
            second = store.inspect_manifest(manifest)
            self.assertEqual(first.state, ArtifactState.FAILED)
            self.assertEqual(second.state, ArtifactState.FAILED)
            self.assertEqual(first.message, "SHA-256 differs from manifest")
            self.assertEqual(second.message, "SHA-256 differs from manifest")

    def test_artifact_without_checksum_stays_downloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=len(b"model"))
            manifest = store.save_manifest(spec)
            manifest.parent.joinpath(spec.filename).write_bytes(b"model")
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADED)
            self.assertEqual(store.inspect_manifest(manifest).state, ArtifactState.DOWNLOADED)

    def test_each_store_instance_recomputes_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"model"
            store, manifest, _ = self._store_with_artifact(directory, content)
            other = ModelStore(store.root)
            with mock.patch(
                "castlearq.model_store._sha256", wraps=castlearq.model_store._sha256
            ) as hashed:
                store.inspect_manifest(manifest)
                other.inspect_manifest(manifest)
            self.assertEqual(hashed.call_count, 2)


if __name__ == "__main__":
    unittest.main()
