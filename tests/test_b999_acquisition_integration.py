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
"""B9.99 Option D: the real composition seam acquires an admitted model.

This is the integration test the B9.99 HADR requires. It exercises the exact
path the real-world drill failed on::

    compose_acquisition_service()
        -> real composition-root identity_resolver (admitted-aware)
        -> real ModelAcquisitionService.acquire()
        -> real acquisition_mapping identity resolution

The identity_resolver is NEVER injected by this test: it is the one the
composition root binds, so the B9.82 seam being corrected is the seam under
test. The final ArtifactSpec is produced by the real mapping boundary and
persisted by the real ``ModelStore.save_manifest`` inside ``acquire()``; no
manifest is written by hand as a substitute for acquisition.

Infrastructure is deterministic and local: a fake discovery port, the real
offline ``DownloadPlanner`` over a temporary store, and a local downloader
that writes fixed bytes to the planned destination. No Hugging Face network
access occurs. Admission, binding and locator resolution run against
temporary registry roots redirected through the established environment
overrides, so no real user registry is touched.
"""

import io
import os
import tempfile
import unittest
from pathlib import Path

from castlearq.acquisition_resolution import (
    resolve_acquisition_locator,
    resolve_binding,
)
from castlearq.acquisition_service import (
    AcquisitionStatus,
    ModelAcquisitionService,
)
from castlearq.admitted_commands import admit_command, bind_command
from castlearq.application_wiring import compose_acquisition_service
from castlearq.discovery import (
    DiscoveredArtifact,
    ModelCandidate,
    ModelVariant,
)
from castlearq.downloads.downloader import (
    DownloadResult,
    DownloadResultStatus,
)
from castlearq.downloads.planner import DownloadPlanner
from castlearq.identity_admission import lookup as admit_lookup
from castlearq.model_identity import logical_model_id, resolve_admitted_model_id
from castlearq.model_store import ModelStore

SRC = "huggingface"
#: Deliberately NOT a curated repository: the derived/admitted path is the
#: only way this repository can ever resolve an identity.
REPO = "someowner/b999-admitted-gguf"
FILENAME = "model-q4.gguf"
SIZE_BYTES = 10

#: A curated repository, used for the one-line curated regression anchor.
CURATED_REPO = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"

ENV_ROOTS = (
    "CASTLEARQ_ADMITTED_MODELS_ROOT",
    "CASTLEARQ_IDENTITY_ADMISSION_ROOT",
    "CASTLEARQ_ACQUISITION_BINDINGS_ROOT",
)


def _discovered_artifact() -> DiscoveredArtifact:
    """One declared remote artifact for the non-curated repository."""
    return DiscoveredArtifact(
        repository=REPO,
        filename=FILENAME,
        format="GGUF",
        declared_quantization="Q4_K_M",
        model_id=None,
        source=SRC,
        download_url=(
            f"https://huggingface.co/{REPO}/resolve/main/{FILENAME}"
        ),
        declared_size=SIZE_BYTES,
        declared_sha256=None,
        revision=None,
    )


def _discovery_variant() -> ModelVariant:
    """The declared grouping the fake inspection returns."""
    return ModelVariant(
        candidate=ModelCandidate(
            provider_id="huggingface",
            repository=REPO,
            has_gguf=True,
        ),
        declared_quantization="Q4_K_M",
        artifacts=(_discovered_artifact(),),
    )


class _FakeDiscovery:
    """A deterministic local B9.80 discovery port: no network, records calls."""

    def __init__(self):
        self.calls = []

    def inspect(self, repository):
        self.calls.append(repository)
        return (_discovery_variant(),)

    def search(self, query, *, limit=20, cursor=None):  # pragma: no cover
        raise AssertionError("acquisition must never call search()")


class _RecordingPlanner:
    """The real offline planner, recording every ArtifactSpec it is given.

    Delegation keeps planning behaviour (validation, canonical locator,
    destination derivation) exactly as production runs it; the recording only
    makes the mapped ArtifactSpec assertable at the composition boundary.
    """

    def __init__(self, inner: DownloadPlanner):
        self._inner = inner
        self.specs = []

    def plan(self, spec):
        self.specs.append(spec)
        return self._inner.plan(spec)


class _LocalDownloader:
    """A deterministic local transfer: writes fixed bytes, never the network."""

    def download(self, plan):
        destination = plan.destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = b"0123456789"
        destination.write_bytes(payload)
        return DownloadResult(
            True,
            DownloadResultStatus.SUCCESS,
            destination,
            len(payload),
        )


class AdmittedNonCuratedAcquisitionTests(unittest.TestCase):
    """The composed service acquires an admitted non-curated model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._previous = {key: os.environ.get(key) for key in ENV_ROOTS}
        for key in ENV_ROOTS:
            os.environ[key] = str(Path(self.tmp.name) / key.lower())
        self.addCleanup(self._restore_env)

        self.mid = resolve_admitted_model_id(SRC, REPO)
        self.store = ModelStore(Path(self.tmp.name) / "store")

        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(admit_command(SRC, REPO, out=out, err=err), 0)
        self.assertEqual(bind_command(self.mid, SRC, REPO, out=out, err=err), 0)

        self.discovery = _FakeDiscovery()
        self.planner = _RecordingPlanner(
            DownloadPlanner(model_store=self.store)
        )
        self.service = compose_acquisition_service(
            discovery_provider=self.discovery,
            model_store=self.store,
            planner_factory=lambda: self.planner,
            downloader_factory=lambda store: _LocalDownloader(),
        )

    def _restore_env(self):
        for key, previous in self._previous.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def test_admission_and_binding_are_explicit_and_forward_consistent(self):
        # Admission: the non-curated repository is explicitly admitted and
        # lookup agrees with the admission authority.
        self.assertIsNone(logical_model_id(SRC, REPO))
        self.assertEqual(admit_lookup(SRC, REPO), self.mid)

        # Binding: the existing B9.96 mechanism holds, forward-validated.
        self.assertEqual(resolve_binding(self.mid), (SRC, REPO))
        self.assertEqual(
            resolve_acquisition_locator(self.mid), (SRC, REPO)
        )

    def test_composition_binds_the_admitted_aware_identity_resolver(self):
        # Option D itself: the composed resolver is admitted-aware. Under the
        # pre-correction binding this returned None for REPO.
        self.assertIsInstance(self.service, ModelAcquisitionService)
        self.assertIsNotNone(self.service.identity_resolver(REPO))
        self.assertEqual(self.service.identity_resolver(REPO), self.mid)

        # Curated regression anchor: the same composed resolver still returns
        # the curated identity unchanged.
        self.assertEqual(
            self.service.identity_resolver(CURATED_REPO),
            logical_model_id(SRC, CURATED_REPO),
        )

    def test_real_composition_acquires_the_admitted_model(self):
        outcome = self.service.acquire(self.mid)

        # The real locator/selection/mapping path ran exactly once.
        self.assertEqual(self.discovery.calls, [REPO])

        # Acquisition completion through the actual service path: no
        # "Identity could not be resolved for repository" failure occurred.
        self.assertIs(outcome.status, AcquisitionStatus.READY)
        self.assertTrue(outcome.succeeded)
        self.assertEqual(outcome.model_id, self.mid)
        self.assertIsNotNone(outcome.manifest_path)

        # Identity: the mapped ArtifactSpec carries the admitted model ID.
        self.assertEqual(len(self.planner.specs), 1)
        mapped = self.planner.specs[0]
        self.assertEqual(mapped.model_id, self.mid)
        self.assertEqual(mapped.repository, REPO)

        # The spec persisted by the real save_manifest inside acquire()
        # carries the same identity, and the transferred bytes are local.
        stored = self.store.inspect_manifest(Path(outcome.manifest_path))
        self.assertIsNotNone(stored.artifact)
        self.assertEqual(stored.artifact.model_id, self.mid)
        destination = Path(outcome.destination)
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), b"0123456789")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()