
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
import tempfile
import unittest
from pathlib import Path

from app.downloads import DownloadPlanStatus, DownloadPlanner
from app.model_store import ModelStore, UnsafePathError
from app.models import ArtifactSpec, ArtifactState


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
        "sha256": None,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class DownloadPlannerTests(unittest.TestCase):
    def planner(self, root, available=100):
        return DownloadPlanner(ModelStore(Path(root)), lambda _path: available)

    def test_ready_plan_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "models"
            plan = self.planner(root).plan(artifact())
            self.assertEqual(plan.status, DownloadPlanStatus.READY)
            self.assertFalse(plan.existing)
            self.assertFalse(root.exists())

    def test_unknown_when_size_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.planner(directory).plan(artifact(size_bytes=None))
            self.assertEqual(plan.status, DownloadPlanStatus.UNKNOWN)
            self.assertIn("size is unknown", plan.reasons[0])

    def test_insufficient_space_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.planner(directory, available=9).plan(artifact())
            self.assertEqual(plan.status, DownloadPlanStatus.BLOCKED)
            self.assertIn("Insufficient", plan.reasons[0])

    def test_existing_downloaded_and_verified_are_already_downloaded(self):
        content = b"0123456789"
        for checksum in (None, hashlib.sha256(content).hexdigest()):
            with self.subTest(checksum=checksum):
                with tempfile.TemporaryDirectory() as directory:
                    spec = artifact(sha256=checksum)
                    store = ModelStore(Path(directory))
                    manifest = store.save_manifest(spec)
                    manifest.parent.joinpath(spec.filename).write_bytes(content)
                    plan = DownloadPlanner(store, lambda _path: 0).plan(spec)
                    self.assertEqual(plan.status, DownloadPlanStatus.ALREADY_DOWNLOADED)

    def test_invalid_metadata_is_blocked(self):
        cases = (
            {"source": "other"},
            {"repository": "../bad/repository"},
            {"filename": "../model.gguf"},
            {"filename": "/absolute.gguf"},
            {"filename": r"dir\model.gguf"},
            {"download_url": "http://huggingface.co/owner/repository/resolve/main/model.Q4_K_M.gguf"},
            {"download_url": "https://evil.example/owner/repository/resolve/main/model.Q4_K_M.gguf"},
            {"download_url": "https://localhost/owner/repository/resolve/main/model.Q4_K_M.gguf"},
            {"download_url": "file:///owner/repository/model.Q4_K_M.gguf"},
            {"download_url": None},
            {"format": "safetensors"},
            {"size_bytes": -1},
            {"size_bytes": True},
            {"size_bytes": "10"},
            {"sha256": "bad"},
        )
        with tempfile.TemporaryDirectory() as directory:
            for overrides in cases:
                with self.subTest(overrides=overrides):
                    plan = self.planner(directory).plan(artifact(**overrides))
                    self.assertEqual(plan.status, DownloadPlanStatus.BLOCKED)

    def test_sha256_uppercase_is_validated_without_mutation(self):
        checksum = "A" * 64
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact(sha256=checksum)
            plan = self.planner(directory).plan(spec)
            self.assertEqual(plan.status, DownloadPlanStatus.READY)
            self.assertEqual(plan.artifact.sha256, checksum)

    def test_url_must_match_repository_and_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.planner(directory).plan(
                artifact(download_url="https://huggingface.co/owner/repository/resolve/main/other.gguf")
            )
            self.assertEqual(plan.status, DownloadPlanStatus.BLOCKED)

    def test_partial_file_is_ready_for_resume_without_removing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact()
            manifest = store.save_manifest(spec)
            partial = manifest.parent / f"{spec.filename}.part"
            partial.write_bytes(b"partial")
            plan = DownloadPlanner(store, lambda _path: 100).plan(spec)
            self.assertEqual(plan.status, DownloadPlanStatus.READY)
            self.assertTrue(partial.exists())

    def test_corrupt_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "qwen__coder" / artifact().artifact_id
            root.mkdir(parents=True)
            (root / "manifest.json").write_text("{bad", encoding="utf-8")
            plan = self.planner(directory).plan(artifact())
            self.assertEqual(plan.status, DownloadPlanStatus.BLOCKED)

    def test_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            store = ModelStore(root)
            (root / "qwen__coder").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(UnsafePathError):
                DownloadPlanner(store, lambda _path: 100).plan(artifact())

    def test_disk_provider_is_injected_and_called(self):
        calls = []

        def provider(path):
            calls.append(path)
            return 100

        with tempfile.TemporaryDirectory() as directory:
            plan = DownloadPlanner(ModelStore(Path(directory)), provider).plan(artifact())
            self.assertEqual(plan.status, DownloadPlanStatus.READY)
            self.assertEqual(calls, [Path(directory)])

    def test_planning_does_not_modify_manifest_or_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact()
            manifest = store.save_manifest(spec)
            before = manifest.read_bytes()
            plan = DownloadPlanner(store, lambda _path: 100).plan(spec)
            self.assertEqual(plan.status, DownloadPlanStatus.READY)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(spec.state, ArtifactState.NOT_DOWNLOADED)
            self.assertFalse(manifest.parent.joinpath(f"{spec.filename}.part").exists())


if __name__ == "__main__":
    unittest.main()
