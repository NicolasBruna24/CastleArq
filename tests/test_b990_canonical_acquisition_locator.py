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

"""B9.90 tests: the production chain carries a canonical revision-aware locator.

Mandatory end-to-end coverage (AC1, AC5, AC7) for the actual production chain:

    HuggingFaceDiscoveryProvider   revision = genuine 40-hex, main-form URL
        -> B9.84 selection
        -> B9.82 acquisition mapper     revision and URL transported verbatim
        -> ArtifactSpec
        -> DownloadPlanner              CANONICALIZATION AUTHORITY
        -> READY plan carrying /resolve/<revision>/
        -> Downloader                   defensive validation, execution

Only the network transport is faked — at the provider's own transport seam
and at the downloader's opener seam. The provider, selection and mapper are
the production implementations and are consumed unchanged by B9.90.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castlearq.acquisition_mapping import map_discovered_artifacts
from castlearq.discovery_selection import select_discovered_artifact
from castlearq.downloads import (
    DownloadPlanStatus,
    DownloadPlanner,
    DownloadResultStatus,
    Downloader,
)
from castlearq.model_store import ModelStore
from castlearq.sources.huggingface_discovery import HuggingFaceDiscoveryProvider

REPO = "owner/repository"
FILENAME = "model-Q4_K_M.gguf"
# A genuine provider-produced revision: exactly 40 hexadecimal characters,
# as produced from the repository metadata ``sha`` by the B9.81 provider.
REVISION = "0123456789abcdef0123456789abcdef01234567"
MODEL_ID = "b990-e2e-model"
CONTENT = b"0123456789"
MAIN_URL = f"https://huggingface.co/{REPO}/resolve/main/{FILENAME}"
CANONICAL_URL = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}"


class _Response:
    """Minimal stand-in for the downloader opener's response object."""

    def __init__(self, chunks, status=200, headers=None):
        self._chunks = iter(chunks)
        self.status = status
        self.headers = headers or {}

    def read(self, _size):
        return next(self._chunks, b"")

    def close(self):
        pass


def make_provider(routes):
    """Build a provider with a recording fake transport.

    ``routes`` is an ordered list of ``(url_substring, payload)`` matched by
    first match — the same seam the B9.81 provider tests use.
    """

    def respond(url):
        for key, payload in routes:
            if key in url:
                return json.dumps(payload).encode("utf-8")
        raise AssertionError(f"unexpected url: {url}")

    calls: list[tuple[str, float]] = []

    def transport(url, timeout):
        calls.append((url, timeout))
        return respond(url)

    return HuggingFaceDiscoveryProvider(transport=transport), calls


class EndToEndRevisionPathTests(unittest.TestCase):
    def test_provider_revision_flows_to_a_canonical_ready_plan_and_download(self):
        provider, provider_calls = make_provider(
            [
                (
                    "/tree/",
                    [
                        {"path": FILENAME, "type": "file", "size": len(CONTENT)},
                    ],
                ),
                (
                    f"/models/{REPO}",
                    {"id": REPO, "sha": REVISION, "tags": ["gguf"]},
                ),
            ]
        )

        # --- provider: informational revision + main-form locator -----------
        variants = provider.inspect(REPO)
        self.assertTrue(provider_calls)
        selected = select_discovered_artifact(variants, quantization="Q4_K_M")
        self.assertEqual(selected.revision, REVISION)
        self.assertEqual(selected.download_url, MAIN_URL)

        # --- mapper: verbatim transport, no URL construction ----------------
        (spec,) = map_discovered_artifacts(
            [selected], identity_resolver=lambda repository: MODEL_ID
        )
        self.assertEqual(spec.revision, REVISION)
        self.assertEqual(spec.download_url, MAIN_URL)

        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(Path(root))

            # --- planner: canonicalization authority -> READY plan ----------
            plan = DownloadPlanner(store, lambda _path: 10 ** 12).plan(spec)
            self.assertIs(plan.status, DownloadPlanStatus.READY)
            self.assertEqual(plan.artifact.revision, REVISION)
            self.assertEqual(plan.artifact.download_url, CANONICAL_URL)
            # OD-1: canonicalization must not perturb identity, and the
            # revision never enters artifact_id.
            self.assertEqual(plan.artifact.artifact_id, spec.artifact_id)
            self.assertNotIn(REVISION, plan.artifact.artifact_id)

            # --- downloader: defensive validation + execution ---------------
            requested: list[str] = []

            def opener(url, _timeout):
                requested.append(url)
                return _Response([CONTENT])

            result = Downloader(store, opener=opener).download(plan)

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
        # The transfer happened against the canonical revision-aware locator,
        # not the provider's incoming main form.
        self.assertEqual(requested, [CANONICAL_URL])


if __name__ == "__main__":
    unittest.main()