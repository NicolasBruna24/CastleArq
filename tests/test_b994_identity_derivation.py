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

"""B9.94 Increment 1: CastleArq-owned logical identity derivation.

This module covers the pure derivation half of Identity Admission:

    derive_model_id(source, repository)  -> a deterministic logical model_id

and the admission resolver that prefers a curated identity and only derives
on a curated miss:

    resolve_admitted_model_id(source, repository)

The contract under test, in the words of the ratified decision:

- Derivation depends on exactly ``(source, repository)``. Nothing else -- no
  filename, quantization, revision, URL, artifact identity, download state or
  storage path -- may influence the result, and the two-argument signature
  makes that structurally true rather than merely conventional.
- Curated identities remain authoritative and are never regenerated.
- ``logical_model_id`` stays the curated-ONLY lookup: an unknown repository
  still yields ``None`` there, which is what keeps every legacy gate
  (manifest migration, the legacy ``ModelSource``, ``plan``) closed.
- A derived identity is forward-resolvable only. It never enters
  ``SOURCE_REPOSITORY_TO_MODEL_ID``, so it is not reverse-resolvable and not
  downloadable in this increment.

The store sanitizer is imported here, from the TEST side only. Production
derivation must never consult it: it is a filesystem sanitizer, not an
identity policy, and ``model_identity`` must not depend on ``model_store``.
"""

import inspect
import re
import unittest

from castlearq.model_identity import (
    DERIVED_IDENTITY_DIGEST_LENGTH,
    SOURCE_REPOSITORY_TO_MODEL_ID,
    DerivedIdentityError,
    derive_model_id,
    downloadable_locator,
    logical_model_id,
    resolve_admitted_model_id,
    source_repositories_for_logical_model,
)
from castlearq.model_store import ModelStore

#: The curated identity that must survive Increment 1 byte-for-byte.
CURATED_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
CURATED_MODEL_ID = "qwen2.5-coder-7b-instruct"

#: A repository with no curated entry.
UNKNOWN_REPOSITORY = "owner/unknown"

#: The alphabet every derived identity must be composed of.
DERIVED_ALPHABET = re.compile(r"^[a-z0-9-]+$")

#: A readable fixture: owner ``acme``, name ``widget-7b`` -> ``acme-widget-7b``.
READABLE_REPOSITORY = "Acme/Widget-7B"

#: The store's own sanitizer, used only to assert the fixpoint property.
SAFE_MODEL_ID = ModelStore._safe_model_id

#: A representative spread of real-world locator shapes, shared by the
#: property classes below so every invariant is asserted over the same corpus.
REPOSITORIES = (
    "Qwen/Qwen3-8B-GGUF",
    "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
    READABLE_REPOSITORY,
    "some-org/My_Model.v2+beta",
    "a/b",
    "org-name.with.dots/model_name--with__separators",
    "UPPER/ALL-CAPS",
)


class DerivationShapeTests(unittest.TestCase):
    """I2 -- every generated identity obeys the CastleArq-owned alphabet."""

    def test_every_derived_id_matches_the_allowed_alphabet(self):
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                self.assertRegex(
                    derive_model_id("huggingface", repository), DERIVED_ALPHABET
                )

    def test_derived_id_is_never_empty_or_a_bare_separator(self):
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                derived = derive_model_id("huggingface", repository)
                self.assertTrue(derived)
                self.assertNotEqual(derived, "-")
                self.assertNotEqual(derived, "--")

    def test_a_dot_identity_can_never_be_produced(self):
        """`.` and `..` are not in the alphabet, so they cannot survive."""
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                derived = derive_model_id("huggingface", repository)
                self.assertNotIn(".", derived)
                self.assertNotIn(derived, {".", ".."})

    def test_dot_only_components_fail_closed(self):
        """A component that normalizes to nothing is refused, not emitted."""
        for repository in (".", "..", "org/..", "./.", "../..", "./model"):
            with self.subTest(repository=repository):
                with self.assertRaises(DerivedIdentityError):
                    derive_model_id("huggingface", repository)
class DeterminismTests(unittest.TestCase):
    """I1 -- the same locator always yields the same identity."""

    def test_repeated_calls_agree(self):
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                first = derive_model_id("huggingface", repository)
                second = derive_model_id("huggingface", repository)
                third = derive_model_id("huggingface", repository)
                self.assertEqual(first, second)
                self.assertEqual(second, third)

    def test_derivation_is_stable_across_both_paths(self):
        """Both paths agree for an unknown repository."""
        self.assertEqual(
            derive_model_id("huggingface", UNKNOWN_REPOSITORY),
            resolve_admitted_model_id("huggingface", UNKNOWN_REPOSITORY),
        )


class ReadabilityTests(unittest.TestCase):
    """I4 -- both repository components reach the readable base."""

    def test_owner_and_repository_name_are_both_present(self):
        derived = derive_model_id("huggingface", READABLE_REPOSITORY)

        self.assertEqual(derived.rsplit("-", 1)[0], "acme-widget-7b")

    def test_owner_contributes_to_the_base(self):
        """Different owners, same name -> different readable bases."""
        first = derive_model_id("huggingface", "acme/Widget")
        second = derive_model_id("huggingface", "other/Widget")

        self.assertNotEqual(first.rsplit("-", 1)[0], second.rsplit("-", 1)[0])

    def test_repository_name_contributes_to_the_base(self):
        """Different names, same owner -> different readable bases."""
        first = derive_model_id("huggingface", "acme/widget")
        second = derive_model_id("huggingface", "acme/gadget")

        self.assertNotEqual(first.rsplit("-", 1)[0], second.rsplit("-", 1)[0])

    def test_normalization_collapses_case_and_punctuation(self):
        """Case and punctuation runs normalize to the same base.

        ``Acme/Widget-7B`` -> ``acme-widget-7b`` and
        ``ACME/widget..7b`` -> ``acme-widget-7-b`` differ because the ``-``
        inside ``Widget-7B`` is a retained separator while the ``..`` run
        collapses to one. The shared prefix proves case folding.
        """
        first = derive_model_id("huggingface", "Acme/Widget-7B").rsplit("-", 1)[0]
        second = derive_model_id("huggingface", "acme/widget-7B").rsplit("-", 1)[0]

        self.assertEqual(first, second)
        self.assertEqual(first, "acme-widget-7b")

    def test_unsupported_runs_become_a_single_separator(self):
        """A punctuation run collapses to exactly one ``-``, not one each."""
        base = derive_model_id("huggingface", "acme/widget..7b").rsplit("-", 1)[0]

        self.assertEqual(base, "acme-widget-7b")
        self.assertNotIn("--", base)
        self.assertNotIn("..", base)

    def test_repeated_separators_collapse_and_edges_are_trimmed(self):
        derived = derive_model_id("huggingface", "-a--b-/--c-")

        self.assertNotIn("--", derived)
        self.assertFalse(derived.startswith("-"))
        self.assertFalse(derived.endswith("-"))


class CollisionResistanceTests(unittest.TestCase):
    """I2/I5/I6 -- distinct locators never collapse to one identity."""

    def test_same_repository_name_under_different_owners_is_distinct(self):
        """The brief's motivating example."""
        first = derive_model_id("huggingface", "Qwen/Foo-GGUF")
        second = derive_model_id("huggingface", "someone/Foo-GGUF")
        third = derive_model_id("huggingface", "another-org/Foo-GGUF")

        self.assertEqual(len({first, second, third}), 3)

    def test_same_basename_variants_are_distinct(self):
        self.assertNotEqual(
            derive_model_id("huggingface", "Qwen/Foo-GGUF"),
            derive_model_id("huggingface", "Other/Foo-GGUF"),
        )

    def test_source_sensitivity_separates_providers(self):
        """I6 -- the raw source participates in the digest."""
        self.assertNotEqual(
            derive_model_id("huggingface", "owner/repository"),
            derive_model_id("other-source", "owner/repository"),
        )

    def test_readable_bases_may_match_while_identities_do_not(self):
        """Names that normalize to one base still separate by digest.

        ``a-b/c`` and ``a/b-c`` normalize to the same readable base; the
        digest is taken over the RAW locator, so they remain distinct. This is
        why the suffix must not be computed over the normalized base.
        """
        first = derive_model_id("huggingface", "a-b/c")
class PurityTests(unittest.TestCase):
    """I7 -- derivation performs no I/O, randomness or mutable-state access."""

    def test_derivation_does_not_mutate_the_curated_registry(self):
        before = dict(SOURCE_REPOSITORY_TO_MODEL_ID)

        derive_model_id("huggingface", READABLE_REPOSITORY)
        resolve_admitted_model_id("huggingface", UNKNOWN_REPOSITORY)

        self.assertEqual(SOURCE_REPOSITORY_TO_MODEL_ID, before)

    def test_admission_resolver_does_not_mutate_the_curated_registry(self):
        before = dict(SOURCE_REPOSITORY_TO_MODEL_ID)

        resolve_admitted_model_id("huggingface", UNKNOWN_REPOSITORY)

        self.assertEqual(SOURCE_REPOSITORY_TO_MODEL_ID, before)

    def test_derivation_does_not_import_or_reference_the_model_store(self):
        """The store sanitizer must stay out of production derivation.

        The check is made against the parsed code, not the raw source: the
        module's prose legitimately NAMES ``ModelStore`` and
        ``_safe_model_id`` while explaining that derivation does not use them.
        Only a real import or attribute reference would be a coupling.
        """
        import ast

        import castlearq.model_identity as module

        tree = ast.parse(inspect.getsource(module))
        imported = set()
        referenced = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        self.assertNotIn("model_store", imported)
        self.assertNotIn("ModelStore", referenced)
        self.assertNotIn("_safe_model_id", referenced)

    def test_derivation_performs_no_filesystem_access(self):
        """Derivation must not create or read anything on disk."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            derive_model_id("huggingface", READABLE_REPOSITORY)
            self.assertEqual(set(Path(directory).iterdir()), before)


class LayerExclusionTests(unittest.TestCase):
    """I8 -- unrelated identity layers cannot reach the derivation."""

    def test_derivation_accepts_exactly_two_parameters(self):
        """Non-participation is structural, not conventional."""
        signature = inspect.signature(derive_model_id)

        self.assertEqual(list(signature.parameters), ["source", "repository"])
        for forbidden in (
            "filename",
            "quantization",
            "revision",
            "download_url",
            "artifact_id",
            "content_id",
            "state",
            "path",
        ):
            self.assertNotIn(forbidden, signature.parameters)

    def test_derivation_does_not_reference_artifacts_or_discovery_objects(self):
        """No artifact, variant or plan type is imported or referenced.

        Parsed rather than grepped, for the same reason as above: the module
        prose names these types to explain why they are excluded, and only a
        real import or attribute reference would constitute coupling.
        """
        import ast

        import castlearq.model_identity as module

        tree = ast.parse(inspect.getsource(module))
        imported = set()
        referenced = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        for forbidden in (
            "ArtifactSpec",
            "DiscoveredArtifact",
            "ModelVariant",
            "ModelCandidate",
            "ArtifactState",
            "DownloadPlan",
            "ModelStore",
        ):
            with self.subTest(symbol=forbidden):
                self.assertNotIn(forbidden, imported)
                self.assertNotIn(forbidden, referenced)

    def test_revision_and_artifact_concerns_cannot_change_the_identity(self):
        """Two artifacts of one repository share the model's identity.

        Revision, filename and quantization differ between them, yet the
        repository locator -- the only input -- determines the identity. This
        mirrors OD-1, which excludes revision from artifact identity for the
        same reason.
        """
        from dataclasses import replace

        from castlearq.models import ArtifactSpec

        base = ArtifactSpec(
            model_id=derive_model_id("huggingface", READABLE_REPOSITORY),
            source="huggingface",
            repository=READABLE_REPOSITORY,
            filename="widget-q4_k_m.gguf",
            revision="a" * 40,
        )
        other = replace(
            base,
            filename="widget-q8_0.gguf",
            revision="b" * 40,
            quantization="Q8_0",
        )

        self.assertNotEqual(base.filename, other.filename)
        self.assertNotEqual(base.revision, other.revision)
        self.assertEqual(
            base.model_id, derive_model_id("huggingface", READABLE_REPOSITORY)
        )


class CuratedPrecedenceTests(unittest.TestCase):
    """I7 -- curated identities remain authoritative and unchanged."""

    def test_curated_lookup_is_unchanged(self):
        self.assertEqual(
            logical_model_id("huggingface", CURATED_REPOSITORY), CURATED_MODEL_ID
        )

    def test_admission_resolver_prefers_the_curated_identity(self):
        self.assertEqual(
            resolve_admitted_model_id("huggingface", CURATED_REPOSITORY),
            CURATED_MODEL_ID,
        )

    def test_admission_returns_curated_not_a_derived_value(self):
        resolved = resolve_admitted_model_id("huggingface", CURATED_REPOSITORY)
        derived = derive_model_id("huggingface", CURATED_REPOSITORY)

        self.assertNotEqual(resolved, derived)
        self.assertEqual(resolved, CURATED_MODEL_ID)

    def test_admission_resolver_never_returns_none(self):
        for repository in REPOSITORIES + (UNKNOWN_REPOSITORY,):
            with self.subTest(repository=repository):
                self.assertIsInstance(
                    resolve_admitted_model_id("huggingface", repository), str
                )


class LegacyGateRegressionTests(unittest.TestCase):
    """Option A's whole purpose: unknown repositories stay closed.

    ``logical_model_id`` remains the curated-ONLY lookup, so every legacy gate
    that depends on its ``None`` answer keeps its existing behaviour.
    """

    def test_unknown_repository_has_no_curated_identity(self):
        self.assertIsNone(logical_model_id("huggingface", UNKNOWN_REPOSITORY))

    def test_unknown_repository_is_derived_only_by_the_admission_resolver(self):
        self.assertIsNone(logical_model_id("huggingface", UNKNOWN_REPOSITORY))
        self.assertIsNotNone(
            resolve_admitted_model_id("huggingface", UNKNOWN_REPOSITORY)
        )

    def test_an_unsupported_source_still_has_no_curated_identity(self):
        self.assertIsNone(logical_model_id("ollama", "qwen2.5-coder:7b"))


class ReverseResolutionClosureTests(unittest.TestCase):
    """The mandatory safety property of Increment 1.

    A derived identity exists, but it must not become reverse-resolvable or
    downloadable. Otherwise Increment 1 would silently widen acquisition,
    which is explicitly out of scope.
    """

    def test_derived_id_resolves_to_no_downloadable_locator(self):
        self.assertIsNone(
            downloadable_locator(derive_model_id("huggingface", READABLE_REPOSITORY))
        )

    def test_derived_id_has_no_source_repositories(self):
        self.assertEqual(
            source_repositories_for_logical_model(
                derive_model_id("huggingface", READABLE_REPOSITORY)
            ),
            (),
        )

    def test_derived_ids_never_enter_the_curated_registry(self):
        curated_values = {
            logical for _, logical in SOURCE_REPOSITORY_TO_MODEL_ID.items()
        }
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                derived = derive_model_id("huggingface", repository)
                self.assertNotIn(derived, curated_values)

    def test_admission_of_an_unknown_repository_does_not_open_acquisition(self):
        """Resolving through admission must not mutate the acquisition gate."""
        before_locator = downloadable_locator(CURATED_MODEL_ID)
        before_registry = dict(SOURCE_REPOSITORY_TO_MODEL_ID)

        derived = resolve_admitted_model_id("huggingface", UNKNOWN_REPOSITORY)

        self.assertIsNone(downloadable_locator(derived))
        self.assertEqual(source_repositories_for_logical_model(derived), ())
        self.assertEqual(SOURCE_REPOSITORY_TO_MODEL_ID, before_registry)
        self.assertEqual(downloadable_locator(CURATED_MODEL_ID), before_locator)

    def test_every_derived_id_stays_non_downloadable(self):
        for repository in REPOSITORIES:
            with self.subTest(repository=repository):
                self.assertIsNone(
                    downloadable_locator(derive_model_id("huggingface", repository))
                )

    def test_the_curated_model_remains_downloadable(self):
        """The gate still works for the curated entry, unchanged."""
        self.assertEqual(
            downloadable_locator(CURATED_MODEL_ID),
            ("huggingface", CURATED_REPOSITORY),
        )


class FailClosedTests(unittest.TestCase):
    """Unrepresentable input is refused, never coerced into an identity."""

    def test_invalid_repositories_raise(self):
        for repository in ("", "   ", "no-slash", "Qwen/", "/GGUF", "///", "@@@/###"):
            with self.subTest(repository=repository):
                with self.assertRaises(DerivedIdentityError):
                    derive_model_id("huggingface", repository)

    def test_invalid_source_raises(self):
        for source in ("", "   ", None):
            with self.subTest(source=source):
                with self.assertRaises(DerivedIdentityError):
                    derive_model_id(source, READABLE_REPOSITORY)

    def test_derived_identity_error_is_independent(self):
        """It is a boundary error, not a provider or discovery error."""
        from castlearq.discovery import DiscoveryError
        from castlearq.sources.huggingface import SourceError

        self.assertFalse(issubclass(DerivedIdentityError, DiscoveryError))
        self.assertFalse(issubclass(DerivedIdentityError, SourceError))

    def test_the_admission_resolver_propagates_the_failure(self):
        with self.assertRaises(DerivedIdentityError):
            resolve_admitted_model_id("huggingface", "no-slash")


if __name__ == "__main__":
    unittest.main()
