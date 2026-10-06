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

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from castlearq.acquisition_service import AcquisitionStatus, ModelAcquisitionService
from castlearq.discovery import DiscoveredArtifact, ModelCandidate, ModelVariant
from castlearq.downloads import DownloadPlanStatus, DownloadPlanner
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState

MODEL_ID = "qwen/coder"
REPOSITORY = "owner/repository"
FILENAME = "model.Q4_K_M.gguf"
STORED_REVISION = "a" * 40
REQUESTED_REVISION = "b" * 40


def artifact(*, revision: str | None, **overrides) -> ArtifactSpec:
    values = {
        "model_id": MODEL_ID,
        "source": "huggingface",
        "repository": REPOSITORY,
        "filename": FILENAME,
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "download_url": (
            f"https://huggingface.co/{REPOSITORY}/resolve/"
            f"{revision or 'main'}/{FILENAME}"
        ),
        "size_bytes": 10,
        "revision": revision,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class _Discovery:
    def __init__(self, revision: str) -> None:
        self.variant = ModelVariant(
            candidate=ModelCandidate(
                provider_id="huggingface",
                repository=REPOSITORY,
                has_gguf=True,
            ),
            declared_quantization="Q4_K_M",
            artifacts=(
                DiscoveredArtifact(
                    repository=REPOSITORY,
                    filename=FILENAME,
                    format="GGUF",
                    declared_quantization="Q4_K_M",
                    source="huggingface",
                    download_url=(
                        f"https://huggingface.co/{REPOSITORY}/resolve/"
                        f"{revision}/{FILENAME}"
                    ),
                    declared_size=10,
                    revision=revision,
                ),
            ),
        )

    def inspect(self, _repository: str) -> tuple[ModelVariant, ...]:
        return (self.variant,)


class RevisionAwareLifecycleTests(unittest.TestCase):
    def _existing_artifact(
        self, root: Path, *, stored_revision: str | None
    ) -> tuple[ModelStore, ArtifactSpec, Path, bytes, bytes]:
        content = b"0123456789"
        store = ModelStore(root)
        stored_spec = artifact(
            revision=stored_revision,
            size_bytes=len(content),
            state=ArtifactState.DOWNLOADED,
        )
        manifest = store.save_manifest(stored_spec)
        artifact_path = manifest.parent / FILENAME
        artifact_path.write_bytes(content)
        return store, stored_spec, manifest, content, manifest.read_bytes()

    def test_same_known_revision_satisfies_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, _stored, manifest, content, manifest_before = (
                self._existing_artifact(
                    Path(directory), stored_revision=REQUESTED_REVISION
                )
            )
            artifact_path = manifest.parent / FILENAME
            plan = DownloadPlanner(store, lambda _path: 0).plan(
                artifact(revision=REQUESTED_REVISION)
            )

            self.assertIs(plan.status, DownloadPlanStatus.ALREADY_DOWNLOADED)
            self.assertEqual(artifact_path.read_bytes(), content)
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertFalse(artifact_path.with_name(FILENAME + ".part").exists())

    def test_different_known_revision_blocks_and_preserves_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, _stored, manifest, content, manifest_before = (
                self._existing_artifact(
                    Path(directory), stored_revision=STORED_REVISION
                )
            )
            artifact_path = manifest.parent / FILENAME
            plan = DownloadPlanner(store, lambda _path: 0).plan(
                artifact(revision=REQUESTED_REVISION)
            )

            self.assertIs(plan.status, DownloadPlanStatus.BLOCKED)
            self.assertIn("does not match", plan.reasons[0])
            self.assertIn("not acquired or replaced", plan.reasons[0])
            self.assertEqual(artifact_path.read_bytes(), content)
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertEqual(len(list(manifest.parent.iterdir())), 2)

    def test_unknown_stored_revision_blocks_known_request(self) -> None:
        for legacy_form in ("null", "missing"):
            with (
                self.subTest(legacy_form=legacy_form),
                tempfile.TemporaryDirectory() as directory,
            ):
                store, _stored, manifest, content, _ = self._existing_artifact(
                    Path(directory), stored_revision=None
                )
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if legacy_form == "missing":
                    payload.pop("revision")
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                manifest_before = manifest.read_bytes()
                artifact_path = manifest.parent / FILENAME

                plan = DownloadPlanner(store, lambda _path: 0).plan(
                    artifact(revision=REQUESTED_REVISION)
                )

                self.assertIs(plan.status, DownloadPlanStatus.BLOCKED)
                self.assertIn("revision is unknown", plan.reasons[0])
                self.assertIn("not acquired or replaced", plan.reasons[0])
                self.assertEqual(artifact_path.read_bytes(), content)
                self.assertEqual(manifest.read_bytes(), manifest_before)
                self.assertEqual(len(list(manifest.parent.iterdir())), 2)

    def test_unknown_requested_revision_preserves_existing_satisfaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, _stored, _manifest, _content, _before = self._existing_artifact(
                Path(directory), stored_revision=STORED_REVISION
            )

            plan = DownloadPlanner(store, lambda _path: 0).plan(
                artifact(revision=None)
            )

            self.assertIs(plan.status, DownloadPlanStatus.ALREADY_DOWNLOADED)

    def test_acquisition_reports_mismatch_as_blocked_not_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, stored, manifest, content, manifest_before = (
                self._existing_artifact(
                    Path(directory), stored_revision=STORED_REVISION
                )
            )
            downloader = Mock()
            service = ModelAcquisitionService(
                discovery_provider=_Discovery(REQUESTED_REVISION),
                identity_resolver=lambda _repository: MODEL_ID,
                locator_resolver=lambda _model_id: ("huggingface", REPOSITORY),
                planner=DownloadPlanner(store, lambda _path: 0),
                downloader=downloader,
                store=store,
            )

            outcome = service.acquire(MODEL_ID, revision=REQUESTED_REVISION)

            self.assertIs(outcome.status, AcquisitionStatus.BLOCKED)
            self.assertFalse(outcome.succeeded)
            self.assertIn("does not match", outcome.reasons[0])
            downloader.download.assert_not_called()
            requested = artifact(revision=REQUESTED_REVISION)
            self.assertEqual(stored.artifact_id, requested.artifact_id)
            self.assertEqual((manifest.parent / FILENAME).read_bytes(), content)
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertEqual(len(list(manifest.parent.iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
