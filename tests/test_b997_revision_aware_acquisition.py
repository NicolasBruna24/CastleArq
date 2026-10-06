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

"""B9.97: dedicated verification tests for the service-level revision channel.

These tests cover the application-boundary responsibility added by the
Option C — Independent Revision Channel decision. The lower-layer planner and
selection tests already cover the syntax and URL semantics elsewhere; this file
focuses on the service-level contract: explicit caller revision authority,
identity isolation, fail-closed validation, and independence from the
``locator_resolver`` and acquisition-binding layers.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from castlearq.acquisition_mapping import map_discovered_artifacts
from castlearq.acquisition_resolution import bind, resolve_binding
from castlearq.acquisition_service import (
    AcquisitionError,
    AcquisitionErrorCategory,
    AcquisitionStatus,
    ModelAcquisitionService,
)
from castlearq.discovery import DiscoveredArtifact, ModelCandidate, ModelVariant
from castlearq.downloads.downloader import DownloadResult, DownloadResultStatus
from castlearq.downloads.planner import DownloadPlan, DownloadPlanStatus
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState

MODEL_ID = "qwen2.5-coder-7b-instruct"
REPO = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
DISCOVERED_REVISION = "a" * 40
CALLER_REVISION = "b" * 40
BAD_REVISION = "bad"


def _artifact(*, revision: str | None = DISCOVERED_REVISION, filename: str = "model-q4.gguf") -> DiscoveredArtifact:
    url = f"https://huggingface.co/{REPO}/resolve/{revision or 'main'}/{filename}"
    return DiscoveredArtifact(
        repository=REPO,
        filename=filename,
        format="GGUF",
        declared_quantization="Q4_K_M",
        model_id=None,
        source="huggingface",
        download_url=url,
        declared_size=10,
        declared_sha256="ab" * 32,
        revision=revision,
    )


def _variant(*artifacts: DiscoveredArtifact, quantization: str = "Q4_K_M") -> ModelVariant:
    return ModelVariant(
        candidate=ModelCandidate(
            provider_id="huggingface",
            repository=REPO,
            has_gguf=True,
        ),
        declared_quantization=quantization,
        artifacts=tuple(artifacts),
    )


def _plan_with_revision(revision: str | None = DISCOVERED_REVISION) -> DownloadPlan:
    artifact = ArtifactSpec(
        model_id=MODEL_ID,
        source="huggingface",
        repository=REPO,
        filename="model-q4.gguf",
        format="GGUF",
        quantization="Q4_K_M",
        download_url=(
            f"https://huggingface.co/{REPO}/resolve/{revision or 'main'}/model-q4.gguf"
        ),
        size_bytes=10,
        sha256="ab" * 32,
        state=ArtifactState.NOT_DOWNLOADED,
        revision=revision,
    )
    return DownloadPlan(
        artifact=artifact,
        destination=Path("/models/qwen2.5-coder-7b-instruct/model-q4.gguf"),
        status=DownloadPlanStatus.READY,
        reasons=(),
        available_bytes=100,
        required_bytes=10,
        existing=False,
    )


class _Discovery:
    def __init__(self, variants=()):
        self._variants = tuple(variants)
        self.calls: list[str] = []

    def inspect(self, repository: str):
        self.calls.append(repository)
        return self._variants


class B997RevisionServiceTests(unittest.TestCase):
    def _service(
        self,
        *,
        variants=(),
        planner: Mock | None = None,
        locator_resolver=None,
        root: str | None = None,
    ) -> ModelAcquisitionService:
        if root is None:
            root = tempfile.mkdtemp(prefix="b997-")
        if planner is None:
            planner = Mock()
            planner.plan.return_value = _plan_with_revision()
        if locator_resolver is None:
            locator_resolver = lambda model_id: ("huggingface", REPO)
        downloader = Mock()
        downloader.download.return_value = DownloadResult(
            True,
            DownloadResultStatus.SUCCESS,
            Path("/models/qwen2.5-coder-7b-instruct/model-q4.gguf"),
            10,
        )
        return ModelAcquisitionService(
            discovery_provider=_Discovery(variants),
            identity_resolver=lambda repository: MODEL_ID,
            locator_resolver=locator_resolver,
            planner=planner,
            downloader=downloader,
            store=ModelStore(Path(root) / "models"),
        )

    def test_a_explicit_caller_revision_reaches_the_acquisition_plan(self):
        planner = Mock()
        planner.plan.return_value = _plan_with_revision(CALLER_REVISION)
        service = self._service(
            variants=[
                _variant(
                    _artifact(revision=DISCOVERED_REVISION, filename="model-a.gguf"),
                    _artifact(revision=CALLER_REVISION, filename="model-b.gguf"),
                )
            ],
            planner=planner,
        )

        outcome = service.acquire(MODEL_ID, revision=CALLER_REVISION)

        self.assertIs(outcome.status, AcquisitionStatus.READY)
        planned = planner.plan.call_args[0][0]
        self.assertEqual(planned.revision, CALLER_REVISION)

    def test_b_caller_revision_overrides_discovered_revision(self):
        planner = Mock()
        planner.plan.return_value = _plan_with_revision(CALLER_REVISION)
        service = self._service(
            variants=[
                _variant(
                    _artifact(revision=DISCOVERED_REVISION, filename="model-a.gguf"),
                    _artifact(revision=CALLER_REVISION, filename="model-b.gguf"),
                )
            ],
            planner=planner,
        )

        service.acquire(MODEL_ID, revision=CALLER_REVISION)

        planned = planner.plan.call_args[0][0]
        self.assertEqual(planned.revision, CALLER_REVISION)
        self.assertNotEqual(planned.revision, DISCOVERED_REVISION)

    def test_c_malformed_caller_revision_fails_closed_before_acquisition(self):
        service = self._service(variants=[_variant(_artifact(revision=DISCOVERED_REVISION))])

        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID, revision=BAD_REVISION)

        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.PLANNING_FAILED)
        self.assertIn("40-character hexadecimal", str(ctx.exception))
        self.assertEqual(service.discovery_provider.calls, [])

    def test_d_revision_does_not_change_identity(self):
        baseline = map_discovered_artifacts(
            [_artifact(revision=None)],
            identity_resolver=lambda repository: MODEL_ID,
        )[0]
        revised = map_discovered_artifacts(
            [_artifact(revision=CALLER_REVISION)],
            identity_resolver=lambda repository: MODEL_ID,
        )[0]

        self.assertEqual(baseline.model_id, revised.model_id)
        self.assertEqual(baseline.artifact_id, revised.artifact_id)
        self.assertIsNone(baseline.revision)
        self.assertEqual(revised.revision, CALLER_REVISION)

    def test_e_revision_does_not_enter_acquisition_binding_identity(self):
        with tempfile.TemporaryDirectory() as root:
            previous = os.environ.get("CASTLEARQ_ACQUISITION_BINDINGS_ROOT")
            try:
                os.environ["CASTLEARQ_ACQUISITION_BINDINGS_ROOT"] = str(Path(root) / "bindings")
                bind(MODEL_ID, "huggingface", REPO)
                before = resolve_binding(MODEL_ID)

                service = self._service(
                    variants=[
                        _variant(
                            _artifact(revision=DISCOVERED_REVISION, filename="model-a.gguf"),
                            _artifact(revision=CALLER_REVISION, filename="model-b.gguf"),
                        )
                    ],
                )
                service.acquire(MODEL_ID, revision=CALLER_REVISION)

                after = resolve_binding(MODEL_ID)
                self.assertEqual(before, ("huggingface", REPO))
                self.assertEqual(after, ("huggingface", REPO))
            finally:
                if previous is None:
                    os.environ.pop("CASTLEARQ_ACQUISITION_BINDINGS_ROOT", None)
                else:
                    os.environ["CASTLEARQ_ACQUISITION_BINDINGS_ROOT"] = previous

    def test_f_locator_resolver_contract_remains_revision_independent(self):
        seen: list[str] = []

        def locator_resolver(model_id: str):
            seen.append(model_id)
            return ("huggingface", REPO)

        service = self._service(
            variants=[
                _variant(
                    _artifact(revision=DISCOVERED_REVISION, filename="model-a.gguf"),
                    _artifact(revision=CALLER_REVISION, filename="model-b.gguf"),
                )
            ],
            locator_resolver=locator_resolver,
        )

        service.acquire(MODEL_ID, revision=CALLER_REVISION)

        self.assertEqual(seen, [MODEL_ID])


if __name__ == "__main__":
    unittest.main()
