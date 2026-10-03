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

"""B9.83 tests: revision-aware acquisition (AC1-AC14).

Covers the three contracts the block changes coherently: the shared artifact
domain type, the manifest read/write path, and the download URL contract —
plus the OD-1 identity decision, which is asserted directly against
``artifact_id`` rather than through dataclass equality.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castlearq.downloads.planner import DownloadPlanner, DownloadPlanStatus
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState
from castlearq.sources.huggingface import SourceError, _download_url

REPO = "owner/repository"
FILENAME = "model-Q4_K_M.gguf"
REVISION = "0" * 40
OTHER_REVISION = "1" * 40
CONTENT_ID = "c" * 64
DECLARED_SHA = "ab" * 32


def spec(**over) -> ArtifactSpec:
    base = {
        "model_id": "test-model",
        "source": "huggingface",
        "repository": REPO,
        "filename": FILENAME,
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "size_bytes": 1234,
        "sha256": DECLARED_SHA,
        "state": ArtifactState.NOT_DOWNLOADED,
        "revision": REVISION,
    }
    base.update(over)
    # The declared locator must correspond to the effective revision. An
    # explicit `download_url` always wins; otherwise it is derived, so a
    # revision-less artifact gets the unpinned `main` form.
    base.setdefault("download_url", _download_url(REPO, FILENAME, base["revision"]))
    return ArtifactSpec(**base)


class RevisionRepresentationTests(unittest.TestCase):
    """AC1, AC2: the shared domain type can represent an optional revision."""

    def test_revision_field_is_optional(self):
        self.assertIn("revision", ArtifactSpec.__dataclass_fields__)
        self.assertIsNone(ArtifactSpec.__dataclass_fields__["revision"].default)

    def test_absent_revision_is_none_not_main(self):
        self.assertIsNone(spec(revision=None).revision)
        # Absence is never invented and never defaulted to "main".
        self.assertNotEqual(spec().revision, "main")

    def test_declared_revision_is_preserved_exactly(self):
        self.assertEqual(spec().revision, REVISION)
        self.assertEqual(spec(revision=OTHER_REVISION).revision, OTHER_REVISION)

    def test_revision_is_not_a_content_or_integrity_claim(self):
        artifact = spec()
        # revision != content_id != verified content != integrity proof
        self.assertIsNone(artifact.content_id)
        self.assertNotEqual(artifact.revision, artifact.sha256)
        self.assertIs(artifact.state, ArtifactState.NOT_DOWNLOADED)


class IdentityTests(unittest.TestCase):
    """AC8 + OD-1: revision does NOT participate in artifact_id."""

    def test_revision_does_not_affect_provenance_identity(self):
        without = spec(revision=None)
        declared = spec(revision=REVISION)
        other = spec(revision=OTHER_REVISION)
        # Same source, repository, filename, quantization; different revision
        # -> same addressing identity. Asserted on artifact_id directly, not
        # through dataclass equality, because revision is legitimate domain
        # metadata and legitimately makes the instances unequal.
        self.assertEqual(without.artifact_id, declared.artifact_id)
        self.assertEqual(declared.artifact_id, other.artifact_id)

    def test_identity_inputs_still_determine_identity(self):
        base = spec()
        self.assertNotEqual(
            base.artifact_id, spec(quantization="Q8_0").artifact_id
        )
        self.assertNotEqual(
            base.artifact_id, spec(filename="other.gguf").artifact_id
        )
        self.assertNotEqual(
            base.artifact_id, spec(repository="owner/other").artifact_id
        )

    def test_content_id_short_circuit_is_unchanged(self):
        derived = spec(content_id=CONTENT_ID)
        self.assertEqual(derived.artifact_id, CONTENT_ID)
        # A revision does not perturb the content-derived identity either.
        self.assertEqual(
            derived.artifact_id,
            spec(content_id=CONTENT_ID, revision=OTHER_REVISION).artifact_id,
        )

    def test_revision_is_excluded_from_the_identity_formula(self):
        artifact = spec(revision=REVISION)
        self.assertNotIn(REVISION, artifact.artifact_id)
        self.assertEqual(artifact.artifact_id, spec().artifact_id)


class DownloadUrlTests(unittest.TestCase):
    """AC5, AC6: the URL contract is revision-aware and not weakened."""

    def test_declared_revision_pins_the_resolve_path(self):
        self.assertEqual(
            _download_url(REPO, FILENAME, REVISION),
            f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}",
        )

    def test_no_revision_preserves_the_existing_main_contract(self):
        self.assertEqual(
            _download_url(REPO, FILENAME),
            f"https://huggingface.co/{REPO}/resolve/main/{FILENAME}",
        )
        self.assertEqual(
            _download_url(REPO, FILENAME, None),
            f"https://huggingface.co/{REPO}/resolve/main/{FILENAME}",
        )

    def test_planner_accepts_a_revision_correspondent_url(self):
        with tempfile.TemporaryDirectory() as root:
            plan = DownloadPlanner(
                model_store=ModelStore(root=Path(root)),
                disk_usage_provider=lambda path: 10 ** 12,
            ).plan(spec())
        self.assertIs(plan.status, DownloadPlanStatus.READY)

    def test_planner_still_accepts_the_unpinned_form_without_revision(self):
        with tempfile.TemporaryDirectory() as root:
            plan = DownloadPlanner(
                model_store=ModelStore(root=Path(root)),
                disk_usage_provider=lambda path: 10 ** 12,
            ).plan(
                spec(
                    revision=None,
                    download_url=_download_url(REPO, FILENAME),
                )
            )
        self.assertIs(plan.status, DownloadPlanStatus.READY)

    def test_planner_canonicalizes_main_and_rejects_a_foreign_revision(self):
        # B9.90 (AC1) supersedes the pre-B9.90 terminal rejection: a declared
        # revision canonicalizes the provider's unpinned main locator into
        # /resolve/<revision>/ instead of rejecting the mismatch, and the
        # READY plan carries the canonical locator. A locator that declares a
        # *foreign* revision still fails: no validation bypass.
        with tempfile.TemporaryDirectory() as root:
            plan = DownloadPlanner(
                model_store=ModelStore(root=Path(root)),
                disk_usage_provider=lambda path: 10 ** 12,
            ).plan(spec(download_url=_download_url(REPO, FILENAME)))
        self.assertIs(plan.status, DownloadPlanStatus.READY)
        self.assertEqual(
            plan.artifact.download_url, _download_url(REPO, FILENAME, REVISION)
        )
        with tempfile.TemporaryDirectory() as root:
            plan = DownloadPlanner(
                model_store=ModelStore(root=Path(root)),
                disk_usage_provider=lambda path: 10 ** 12,
            ).plan(spec(download_url=_download_url(REPO, FILENAME, OTHER_REVISION)))
        self.assertIs(plan.status, DownloadPlanStatus.BLOCKED)
        self.assertTrue(plan.reasons)

    def test_existing_url_security_invariants_are_preserved(self):
        bad_urls = (
            f"http://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}",
            f"https://evil.example/{REPO}/resolve/{REVISION}/{FILENAME}",
            f"https://localhost/{REPO}/resolve/{REVISION}/{FILENAME}",
            f"https://user:pw@huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}",
            f"https://huggingface.co:8443/{REPO}/resolve/{REVISION}/{FILENAME}",
            f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}?x=1",
            f"https://huggingface.co/{REPO}/resolve/{REVISION}/other.gguf",
            f"https://huggingface.co/owner/other/resolve/{REVISION}/{FILENAME}",
        )
        for url in bad_urls:
            with tempfile.TemporaryDirectory() as root:
                plan = DownloadPlanner(
                    model_store=ModelStore(root=Path(root)),
                    disk_usage_provider=lambda path: 10 ** 12,
                ).plan(spec(download_url=url))
            self.assertIs(
                plan.status, DownloadPlanStatus.BLOCKED, f"URL not rejected: {url}"
            )

    def test_unsafe_revisions_are_rejected_at_construction(self):
        for revision in (
            "", ".", "..", "a/b", "a\\b", " main", "main ", 129 * "a", "a b",
        ):
            with self.assertRaises(SourceError):
                _download_url(REPO, FILENAME, revision)


class ManifestTests(unittest.TestCase):
    """AC3, AC4, AC7: revision round-trips without becoming derived state."""

    def test_declared_revision_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(root=Path(root))
            original = spec()
            path = store.save_manifest(original)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["revision"], REVISION)
            restored = store.inspect_manifest(path).artifact
        self.assertEqual(restored.revision, REVISION)
        # Identity is unchanged by the round trip (OD-1).
        self.assertEqual(restored.artifact_id, original.artifact_id)

    def test_absent_revision_round_trips_as_none(self):
        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(root=Path(root))
            original = spec(
                revision=None, download_url=_download_url(REPO, FILENAME)
            )
            path = store.save_manifest(original)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNone(payload["revision"])
            restored = store.inspect_manifest(path).artifact
        self.assertIsNone(restored.revision)

    def test_manifest_written_before_b983_remains_readable(self):
        # A legacy manifest with no `revision` key loads unchanged.
        payload = {
            "model_id": "legacy-model",
            "source": "huggingface",
            "repository": REPO,
            "filename": FILENAME,
            "format": "GGUF",
            "quantization": "Q4_K_M",
            "download_url": _download_url(REPO, FILENAME),
            "size_bytes": 1234,
            "sha256": DECLARED_SHA,
            "content_id": None,
            "downloaded_at": "2026-01-01T00:00:00+00:00",
        }
        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(root=Path(root))
            directory = store.root / "legacy-model" / ("legacy" * 16)
            directory.mkdir(parents=True)
            path = directory / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            restored = store.inspect_manifest(path).artifact
        self.assertIsNotNone(restored)
        self.assertIsNone(restored.revision)

    def test_revision_is_not_derived_state(self):
        # B9.41 still holds: state and verified are never persisted, and a
        # declared revision never promotes state to a verified claim.
        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(root=Path(root))
            path = store.save_manifest(spec())
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("state", payload)
        self.assertNotIn("verified", payload)
        self.assertIn("revision", payload)


if __name__ == "__main__":
    unittest.main()

