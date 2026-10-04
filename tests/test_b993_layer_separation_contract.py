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

"""B9.93 tests: multi-layer identity separation contract.

B9.93 ratifies Option D — Explicit Multi-Layer Identity Model — as an
architectural *conceptual* contract, with an INCREMENTAL / MINIMAL posture and
no behaviour change.

The multi-layer contract is documented in ``castlearq/model_identity.py``. These
tests pin the executable invariants that already exist, so a future refactor
cannot silently collapse one layer into another:

    logical model identity  !=  variant
    logical model identity  !=  artifact
    logical model identity  !=  revision
    logical model identity  !=  locator
    logical model identity  !=  storage identity

    No layer may substitute for or be silently promoted to another layer.

Every assertion here is behavioural and uses only already-existing public APIs.
Nothing is asserted about documentation text: the documentation establishes the
vocabulary, the tests establish the invariants. No test inspects a docstring,
no test reaches the network or the filesystem, and no test mutates the real
identity registry.
"""
from __future__ import annotations

import dataclasses
import unittest
from unittest import mock

from castlearq.discovery import DiscoveredArtifact
from castlearq.model_identity import (
    downloadable_locator,
    logical_model_id,
    source_repositories_for_logical_model,
)
from castlearq.models import ArtifactSpec

REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
LOGICAL_ID = "qwen2.5-coder-7b-instruct"
REVISION = "a" * 40
OTHER_REVISION = "b" * 40


def _spec(**overrides) -> ArtifactSpec:
    """A single artifact of one logical model, with overridable fields."""
    fields = {
        "model_id": LOGICAL_ID,
        "source": "huggingface",
        "repository": REPOSITORY,
        "filename": "model-Q4_K_M.gguf",
        "quantization": "Q4_K_M",
    }
    fields.update(overrides)
    return ArtifactSpec(**fields)


class LogicalModelIdentityTests(unittest.TestCase):
    """The Logical Model layer stays canonical and remains a plain string."""

    def test_logical_model_identity_remains_canonical_and_is_a_string(self):
        """AC1: `model_id` is the logical model identity, and stays a `str`."""
        resolved = logical_model_id("huggingface", REPOSITORY)

        self.assertEqual(resolved, LOGICAL_ID)
        # No nominal identity type is introduced by B9.93.
        self.assertIsInstance(resolved, str)

    def test_a_repository_is_never_promoted_into_a_logical_identity(self):
        """AC1/AC9: an unmapped repository yields no identity at all.

        The locator is a lookup key, never a fallback identity: no basename,
        substring or fuzzy inference may produce one.
        """
        self.assertIsNone(logical_model_id("huggingface", "owner/unknown"))
        self.assertIsNone(logical_model_id("ollama", "qwen2.5-coder:7b"))


class RevisionSeparationTests(unittest.TestCase):
    """Revision is declared provenance, never artifact or model identity."""

    def test_revision_does_not_redefine_artifact_identity(self):
        """AC4: OD-1 — `revision` is excluded from `artifact_id`."""
        base = _spec(revision=REVISION)
        other_revision = dataclasses.replace(base, revision=OTHER_REVISION)

        self.assertNotEqual(base.revision, other_revision.revision)
        self.assertEqual(base.artifact_id, other_revision.artifact_id)


class ArtifactLayerTests(unittest.TestCase):
    """Artifact metadata belongs to the Artifact layer, not to identity."""

    def test_artifact_metadata_participates_in_artifact_identity_only(self):
        """AC3: quantization shapes artifact identity, never logical identity.

        Two artifacts of the SAME logical model that differ only by
        quantization are genuinely different artifacts. This proves
        quantization is Artifact-layer metadata; it does not make quantization
        an identity, and `model_id` is unchanged across both.
        """
        base = _spec()
        other_quantization = dataclasses.replace(base, quantization="Q8_0")

        self.assertEqual(base.model_id, other_quantization.model_id)
        self.assertNotEqual(base.artifact_id, other_quantization.artifact_id)


class DiscoverySeparationTests(unittest.TestCase):
    """Discovery remains identity-free."""

    def test_a_discovered_artifact_carries_no_logical_identity(self):
        """AC7: `DiscoveredArtifact.model_id` is `None`; discovery has no say."""
        discovered = DiscoveredArtifact(repository=REPOSITORY, filename="model.gguf")

        self.assertIsNone(discovered.model_id)

    def test_provider_declared_metadata_is_not_authoritative_identity(self):
        """AC8: even a declared `model_id` never becomes the resolved identity.

        Identity is re-attached only through the explicit mapping boundary in
        the acquisition flow, never taken from discovery metadata.
        """
        declared = DiscoveredArtifact(
            repository=REPOSITORY, filename="model.gguf", model_id="declared-by-provider"
        )

        self.assertNotEqual(
            declared.model_id, logical_model_id("huggingface", REPOSITORY)
        )
        # The provider's declaration does not create a registry entry.
        self.assertEqual(source_repositories_for_logical_model("declared-by-provider"), ())


class LocatorLayerTests(unittest.TestCase):
    """A locator is an acquisition gate, not an identity."""

    def test_locator_resolves_a_supported_logical_model(self):
        """AC5: the supported logical model resolves to its single locator."""
        self.assertEqual(
            downloadable_locator(LOGICAL_ID), ("huggingface", REPOSITORY)
        )

    def test_unknown_logical_model_resolves_to_no_locator(self):
        """AC5/AC1: an unknown identity fails closed; it is never guessed."""
        self.assertIsNone(downloadable_locator("no-such-logical-model"))
        self.assertEqual(source_repositories_for_logical_model("no-such-logical-model"), ())

    def test_exactly_one_locator_is_required(self):
        """AC9: the 1-repository -> 1-logical-model gate is preserved.

        Zero and multiple locators both yield no downloadable locator. This is a
        regression test for the existing exactly-one rule; B9.93 introduces no
        1 -> N repository/model mapping. The substitution is confined to the
        in-memory mapping object and is restored automatically.
        """
        multi = {
            ("huggingface", "owner/mirror-a"): LOGICAL_ID,
            ("huggingface", "owner/mirror-b"): LOGICAL_ID,
        }
        with mock.patch.dict(
            "castlearq.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID",
            multi,
            clear=True,
        ):
            self.assertEqual(len(source_repositories_for_logical_model(LOGICAL_ID)), 2)
            self.assertIsNone(downloadable_locator(LOGICAL_ID))

        with mock.patch.dict(
            "castlearq.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID",
            {},
            clear=True,
        ):
            self.assertEqual(source_repositories_for_logical_model(LOGICAL_ID), ())
            self.assertIsNone(downloadable_locator(LOGICAL_ID))

        # Restored automatically by the patcher.
        self.assertEqual(downloadable_locator(LOGICAL_ID), ("huggingface", REPOSITORY))


if __name__ == "__main__":
    unittest.main()

