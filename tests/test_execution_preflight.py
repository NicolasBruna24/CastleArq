
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
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from castlearq.execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    PreflightErrorCode,
)
from castlearq.model_store import ModelStore, UnsafePathError
from castlearq.models import ArtifactSpec


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
        # Provide sha256 so artifacts can be validated (B9.67 contract)
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        self.spec = artifact(sha256=content_sha256)
        self.directory = self.store.save_manifest(self.spec).parent
        self.final = self.directory / self.spec.filename
        self.partial = self.directory / f"{self.spec.filename}.part"
        self.preflight = ArtifactExecutionPreflight(self.store)

    def tearDown(self):
        self.tempdir.cleanup()

    def _openvino_artifact(self, content_id="correct", sha256="correct"):
        from castlearq.importing import _compute_content_id

        source = Path(tempfile.mkdtemp(prefix="openvino-source-", dir=self.tempdir.name))
        (source / "openvino_model.xml").write_bytes(b"<model/>")
        auxiliary = b'{"model":true}'
        (source / "config.json").write_bytes(auxiliary)
        actual_content_id = _compute_content_id(source)
        actual_sha256 = hashlib.sha256(b"<model/>").hexdigest()
        declared_content_id = (
            actual_content_id if content_id == "correct"
            else "0" * 64 if content_id == "wrong"
            else None
        )
        declared_sha256 = (
            actual_sha256 if sha256 == "correct"
            else "0" * 64 if sha256 == "wrong"
            else None
        )
        spec = artifact(
            filename="openvino_model.xml",
            format="OpenVINO IR",
            backend="openvino",
            content_id=declared_content_id,
            sha256=declared_sha256,
            files=("config.json",),
            file_checksums={
                "config.json": hashlib.sha256(auxiliary).hexdigest(),
            },
        )
        manifest = self.store.save_manifest(spec)
        for path in source.iterdir():
            (manifest.parent / path.name).write_bytes(path.read_bytes())
        return spec

    def test_valid_final_artifact(self):
        # Provide sha256 so artifact can be validated
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        self.final.write_bytes(content)
        result = self.preflight.validate(artifact(sha256=content_sha256))
        self.assertEqual(result.path, self.final)
        # With sha256 matching, checksum_verified should be True
        self.assertTrue(result.checksum_verified)

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
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        # Provide sha256 in both validations
        self.preflight.validate(artifact(sha256=content_sha256, size_bytes=5))
        result = self.preflight.validate(artifact(sha256=content_sha256, size_bytes=5))
        self.assertTrue(result.size_verified)

    def test_incorrect_size_is_rejected(self):
        self.final.write_bytes(b"model")
        with self.assertRaises(ArtifactPreflightError):
            self.preflight.validate(artifact(size_bytes=4))

    def test_unknown_size_is_allowed(self):
        content = b"model"
        spec = artifact(content_id=hashlib.sha256(content).hexdigest())
        manifest = self.store.save_manifest(spec)
        (manifest.parent / spec.filename).write_bytes(content)
        result = self.preflight.validate(spec)
        self.assertFalse(result.size_verified)
        self.assertTrue(result.checksum_verified)

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

    def test_content_id_is_sufficient_without_sha256(self):
        content = b"model"
        spec = artifact(content_id=hashlib.sha256(content).hexdigest())
        manifest = self.store.save_manifest(spec)
        (manifest.parent / spec.filename).write_bytes(content)
        result = self.preflight.validate(spec)
        self.assertTrue(result.checksum_verified)
        self.assertIsNone(result.artifact.sha256)

    def test_manifest_and_spec_remain_unchanged(self):
        self.final.write_bytes(b"model")
        # Provide sha256 so preflight can verify integrity
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        manifest = self.directory / "manifest.json"
        before = manifest.read_bytes()
        self.preflight.validate(artifact(sha256=content_sha256))
        self.assertEqual(manifest.read_bytes(), before)
        # Compare specs - both have sha256 now due to setUp update
        self.assertEqual(self.spec, artifact(sha256=content_sha256))

    def test_preflight_does_not_delete_or_create_directories(self):
        self.final.write_bytes(b"model")
        # Provide sha256 so preflight can verify integrity
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        before = {path for path in self.store.root.rglob("*")}
        self.preflight.validate(artifact(sha256=content_sha256))
        self.assertEqual({path for path in self.store.root.rglob("*")}, before)

    def test_missing_preflight_does_not_create_model_store_directories(self):
        root = Path(self.tempdir.name) / "missing-models"
        store = ModelStore(root)
        with self.assertRaises(ArtifactPreflightError):
            ArtifactExecutionPreflight(store).validate(self.spec)
        self.assertFalse(root.exists())

    def test_preflight_does_not_access_network(self):
        # Provide sha256 so preflight can verify integrity without network access
        content = b"model"
        content_sha256 = hashlib.sha256(content).hexdigest()
        self.final.write_bytes(b"model")
        with patch("urllib.request.urlopen") as urlopen:
            self.preflight.validate(artifact(sha256=content_sha256))
        urlopen.assert_not_called()



    def test_without_identifiers_is_rejected(self):
        # B9.67: artifact without content_id nor sha256 must be rejected
        # by the execution preflight.
        content = b"model"
        self.final.write_bytes(content)
        # Artifact with neither content_id nor sha256
        spec = artifact()  # default: content_id=None, sha256=None
        with self.assertRaises(ArtifactPreflightError) as ctx:
            self.preflight.validate(spec)
        self.assertEqual(
            ctx.exception.code,
            PreflightErrorCode.MISSING_INTEGRITY_IDENTIFIERS,
        )
        self.assertIn(
            "No integrity identifiers",
            ctx.exception.message,
        )

    def test_openvino_preflight_verifies_each_identifier_contract(self):
        cases = (
            ("content_id only", "correct", None, None),
            ("sha256 only", None, "correct", None),
            ("both correct", "correct", "correct", None),
            ("content_id mismatch", "wrong", None, PreflightErrorCode.CHECKSUM_MISMATCH),
            ("sha256 mismatch", None, "wrong", PreflightErrorCode.CHECKSUM_MISMATCH),
        )
        for name, content_id, sha256, expected_error in cases:
            with self.subTest(identifiers=name):
                spec = self._openvino_artifact(content_id, sha256)
                if expected_error is None:
                    result = self.preflight.validate(spec)
                    self.assertTrue(result.checksum_verified)
                else:
                    with self.assertRaises(ArtifactPreflightError) as context:
                        self.preflight.validate(spec)
                    self.assertEqual(context.exception.code, expected_error)

    def test_openvino_content_identity_covers_auxiliary_files(self):
        spec = self._openvino_artifact()
        package = self.store.artifact_directory(spec)
        (package / "config.json").write_bytes(b'{"changed":true}')

        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(spec)
        self.assertEqual(context.exception.code, PreflightErrorCode.CHECKSUM_MISMATCH)

    def test_openvino_sha256_only_rejects_modified_auxiliary_file(self):
        spec = self._openvino_artifact(content_id=None)
        package = self.store.artifact_directory(spec)
        (package / "config.json").write_bytes(b'{"changed":true}')

        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(spec)
        self.assertEqual(context.exception.code, PreflightErrorCode.CHECKSUM_MISMATCH)

    def test_openvino_sha256_only_rejects_missing_auxiliary_file(self):
        spec = self._openvino_artifact(content_id=None)
        package = self.store.artifact_directory(spec)
        (package / "config.json").unlink()

        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(spec)
        self.assertEqual(context.exception.code, PreflightErrorCode.MISSING_ARTIFACT)

    def test_openvino_preflight_rejects_missing_identifiers(self):
        spec = self._openvino_artifact(content_id=None, sha256=None)
        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(spec)
        self.assertEqual(
            context.exception.code,
            PreflightErrorCode.MISSING_INTEGRITY_IDENTIFIERS,
        )

    def test_openvino_preflight_rejects_symlinked_package_entry(self):
        from castlearq.importing import _compute_content_id

        source = Path(self.tempdir.name) / "openvino-symlink-source"
        source.mkdir()
        (source / "openvino_model.xml").write_bytes(b"<model/>")
        (source / "config.json").write_bytes(b"{}")
        content_id = _compute_content_id(source)
        spec = artifact(
            filename="openvino_model.xml",
            format="OpenVINO IR",
            backend="openvino",
            content_id=content_id,
        )
        manifest = self.store.save_manifest(spec)
        for path in source.iterdir():
            (manifest.parent / path.name).write_bytes(path.read_bytes())
        target = manifest.parent / "outside"
        target.write_bytes(b"outside")
        (manifest.parent / "linked.json").symlink_to(target)

        with self.assertRaises(ArtifactPreflightError) as context:
            self.preflight.validate(spec)
        self.assertEqual(context.exception.code, PreflightErrorCode.UNSAFE_ARTIFACT)


if __name__ == "__main__":
    unittest.main()