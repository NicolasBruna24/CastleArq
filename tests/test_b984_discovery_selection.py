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

"""B9.84: discovery-domain deterministic artifact selection.

All fixtures are constructed locally from the existing B9.80 constructors. No
network, no filesystem state, no provider code and no external service is
involved (section 21.5/21.6).
"""

import inspect
import unittest

from castlearq.acquisition_mapping import map_discovered_artifacts
from castlearq.artifact_selection import ArtifactSelectionError, select_artifact
from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelVariant,
)
from castlearq.discovery_selection import (
    DiscoveredSelectionError,
    select_discovered_artifact,
)
from castlearq.models import ArtifactSpec

REPO = "owner/repository"
REVISION = "a" * 40
OTHER_REVISION = "b" * 40


def artifact(
    filename="model-q4.gguf",
    quantization="Q4_K_M",
    revision=REVISION,
):
    """One declared remote artifact, exactly as B9.80 models it."""
    return DiscoveredArtifact(
        repository=REPO,
        filename=filename,
        format="GGUF",
        declared_quantization=quantization,
        model_id=None,
        source="huggingface",
        download_url=f"https://huggingface.co/{REPO}/resolve/{revision}/{filename}",
        declared_size=None,
        declared_sha256=None,
        revision=revision,
    )


def variant(artifacts, quantization="Q4_K_M"):
    """One declared grouping, exactly as B9.80 models it."""
    return ModelVariant(
        candidate=ModelCandidate(
            provider_id="huggingface",
            repository=REPO,
            has_gguf=True,
        ),
        declared_quantization=quantization,
        artifacts=tuple(artifacts),
    )


def identity_resolver(repository):
    """The caller-supplied resolver shape B9.82 already requires (D5)."""
    return f"local/{repository}"


class SuccessSelectionTests(unittest.TestCase):
    """1, 2, 4, 8, 10, 11, 16, 17, 19: successful, deterministic selection."""

    def test_single_variant_single_artifact_no_criteria(self):
        """1. The only candidate is selected without any criterion."""
        found = artifact()
        selected = select_discovered_artifact([variant([found])])
        self.assertIs(selected, found)

    def test_quantization_selection(self):
        """2. Quantization matches declared_quantization, case-insensitively."""
        found = artifact("model-q8.gguf", quantization="Q8_0")
        selected = select_discovered_artifact(
            [variant([found], quantization="Q8_0")], quantization="q8_0"
        )
        self.assertIs(selected, found)

    def test_exact_filename_selection(self):
        """4. Filename matches DiscoveredArtifact.filename exactly."""
        found = artifact("model-exact.gguf")
        selected = select_discovered_artifact(
            [variant([found])], filename="model-exact.gguf"
        )
        self.assertIs(selected, found)

    def test_revision_selection(self):
        """8. Revision is a first-class explicit criterion (D3)."""
        wanted = artifact("model-a.gguf", revision=REVISION)
        other = artifact("model-b.gguf", revision=OTHER_REVISION)
        selected = select_discovered_artifact(
            [variant([wanted, other])], revision=REVISION
        )
        self.assertIs(selected, wanted)

    def test_absent_revision_is_selectable_without_revision_criterion(self):
        """10. An absent revision stays None and is never defaulted to 'main'."""
        found = artifact("model-norev.gguf", revision=None)
        self.assertIsNone(found.revision)
        selected = select_discovered_artifact(
            [variant([found])], filename="model-norev.gguf"
        )
        self.assertIs(selected, found)
        self.assertIsNone(selected.revision)

    def test_combined_quantization_filename_and_revision(self):
        """11. Criteria combine cumulatively with logical AND."""
        wanted = artifact("target.gguf", quantization="Q4_K_M", revision=REVISION)
        noise = [
            artifact("target.gguf", quantization="Q8_0", revision=REVISION),
            artifact("target.gguf", quantization="Q4_K_M", revision=OTHER_REVISION),
            artifact("other.gguf", quantization="Q4_K_M", revision=REVISION),
        ]
        selected = select_discovered_artifact(
            [variant(noise + [wanted])],
            quantization="Q4_K_M",
            filename="target.gguf",
            revision=REVISION,
        )
        self.assertIs(selected, wanted)

    def test_filename_resolves_shard_ambiguity(self):
        """16. An exact filename selects one shard out of several."""
        shards = [
            artifact("model-q4-00001.gguf"),
            artifact("model-q4-00002.gguf"),
            artifact("model-q4-00003.gguf"),
        ]
        selected = select_discovered_artifact(
            [variant(shards)],
            quantization="Q4_K_M",
            filename="model-q4-00002.gguf",
        )
        self.assertIs(selected, shards[1])

    def test_multiple_variants_with_one_total_artifact(self):
        """17. Across several variants, exactly one candidate is selected."""
        wanted = artifact("only.gguf", quantization="Q8_0")
        variants = [
            variant([artifact("a.gguf", quantization="Q4_K_M")]),
            variant([wanted], quantization="Q8_0"),
        ]
        selected = select_discovered_artifact(variants, quantization="Q8_0")
        self.assertIs(selected, wanted)
        # Without a criterion the same two variants are ambiguous (D6).
        with self.assertRaises(DiscoveredSelectionError):
            select_discovered_artifact(variants)

    def test_result_is_independent_of_incidental_ordering(self):
        """19. Shuffled variants and shuffled artifacts give the same result."""
        a = artifact("model-a.gguf", quantization="Q4_K_M")
        b = artifact("model-b.gguf", quantization="Q8_0")
        forwards = [variant([a]), variant([b], quantization="Q8_0")]
        backwards = [variant([b], quantization="Q8_0"), variant([a])]

        # A criterion identifying exactly one candidate: same result either
        # way, whichever order the variants arrive in.
        for candidates in (forwards, backwards):
            with self.subTest(order=[v.declared_quantization for v in candidates]):
                selected = select_discovered_artifact(
                    candidates, quantization="Q4_K_M"
                )
                self.assertIs(selected, a)

        # Shuffling the artifacts inside one variant changes nothing.
        pair = [artifact("x.gguf"), artifact("y.gguf")]
        first = select_discovered_artifact([variant(pair)], filename="y.gguf")
        second = select_discovered_artifact(
            [variant(list(reversed(pair)))], filename="y.gguf"
        )
        self.assertIs(first, second)
        self.assertIs(first, pair[1])


class NoMatchTests(unittest.TestCase):
    """3, 5, 6, 9, 12, 14: no-match failures stay distinct from other errors."""

    def test_quantization_no_match(self):
        """3. A quantization that no candidate declares is a no-match."""
        variants = [variant([artifact(quantization="Q4_K_M")])]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact(variants, quantization="Q2_K")
        self.assertIn("No discovered artifact matches quantization", str(ctx.exception))

    def test_filename_is_case_sensitive(self):
        """5. Filename matching is exact, so wrong case never matches."""
        variants = [variant([artifact("model-q4.gguf")])]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact(variants, filename="MODEL-Q4.GGUF")
        self.assertIn("No discovered artifact matches filename", str(ctx.exception))

    def test_filename_prefix_or_substring_never_matches(self):
        """6. Matching is exact: no fuzzy, prefix or partial selection."""
        variants = [variant([artifact("model-q4.gguf")])]
        for candidate in ("model", "model-q4", "model-q4.gguf.part", "q4.gguf"):
            with (
                self.subTest(candidate=candidate),
                self.assertRaises(DiscoveredSelectionError),
            ):
                select_discovered_artifact(variants, filename=candidate)

    def test_revision_mismatch(self):
        """9. A revision no candidate declares is a no-match, never a default."""
        variants = [variant([artifact(revision=REVISION)])]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact(variants, revision=OTHER_REVISION)
        self.assertIn("No discovered artifact matches revision", str(ctx.exception))

        with self.assertRaises(DiscoveredSelectionError):
            select_discovered_artifact(variants, revision="main")

    def test_combined_criteria_no_match(self):
        """12. AND semantics: every criterion must hold simultaneously."""
        variants = [variant([artifact("only.gguf", quantization="Q8_0")])]
        with self.assertRaises(DiscoveredSelectionError):
            select_discovered_artifact(
                variants, quantization="Q8_0", filename="other.gguf"
            )

    def test_no_match_on_non_empty_candidates_is_not_an_empty_set(self):
        """14. A populated collection matching nothing differs from empty."""
        variants = [variant([artifact("present.gguf")])]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact(variants, filename="absent.gguf")
        message = str(ctx.exception)
        self.assertIn("No discovered artifact matches filename", message)
        self.assertNotIn("No discovered GGUF artifacts found", message)


class EmptyCandidateTests(unittest.TestCase):
    """13: D8, the empty candidate collection is its own explicit failure."""

    def test_empty_variant_collection_is_an_explicit_error(self):
        found = artifact()
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact([])
        message = str(ctx.exception)
        self.assertEqual(message, "No discovered GGUF artifacts found")

        # D8: distinguishable from a populated collection with no match.
        with self.assertRaises(DiscoveredSelectionError) as other:
            select_discovered_artifact([variant([found])], quantization="Q2_K")
        self.assertNotEqual(message, str(other.exception))

    def test_empty_input_is_an_error_even_with_selectors(self):
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact((), quantization="Q4_K_M")
        self.assertEqual(
            str(ctx.exception), "No discovered GGUF artifacts found"
        )

    def test_empty_input_never_returns_none_or_succeeds(self):
        # D8: never silently a success and never None.
        with self.assertRaises(DiscoveredSelectionError):
            select_discovered_artifact([])


class AmbiguityTests(unittest.TestCase):
    """15, 18: multiple matches fail; order never breaks the tie."""

    def test_ambiguity_across_shards_of_one_variant(self):
        """15. Several shards matching quantization alone is a failure."""
        shards = [
            artifact("model-q4-00001.gguf"),
            artifact("model-q4-00002.gguf"),
        ]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact([variant(shards)], quantization="Q4_K_M")
        message = str(ctx.exception)
        self.assertIn("Multiple discovered artifacts match", message)
        # The message names candidates, it does not pick one.
        self.assertIn("model-q4-00001.gguf", message)
        self.assertIn("model-q4-00002.gguf", message)

    def test_ambiguity_is_order_independent(self):
        """D6: shuffling never turns an ambiguity into a silent selection."""
        a = artifact("model-a.gguf")
        b = artifact("model-b.gguf")
        for order in ([a, b], [b, a]):
            with (
                self.subTest(order=[x.filename for x in order]),
                self.assertRaises(DiscoveredSelectionError),
            ):
                select_discovered_artifact([variant(order)])

    def test_multiple_variants_with_multiple_artifacts_and_no_criteria(self):
        """18. No criteria over several candidates fails rather than choosing."""
        variants = [
            variant([artifact("model-q4.gguf")]),
            variant([artifact("model-q8.gguf", quantization="Q8_0")],
                    quantization="Q8_0"),
        ]
        with self.assertRaises(DiscoveredSelectionError) as ctx:
            select_discovered_artifact(variants)
        self.assertIn("multiple discovered artifacts", str(ctx.exception))


class InvalidSelectorTests(unittest.TestCase):
    """7: unsafe and invalid selectors are their own failure category."""

    def setUp(self):
        self.variants = [variant([artifact("model-q4.gguf")])]

    def test_unsafe_filename_selectors_are_rejected(self):
        unsafe = [
            "", "   ", "/etc/passwd", "/model.gguf", "sub/model.gguf",
            "sub\\model.gguf", "..", ".", "../model.gguf", "./model.gguf",
            "model\x00.gguf", "model\n.gguf",
        ]
        for candidate in unsafe:
            with self.subTest(candidate=candidate):
                with self.assertRaises(DiscoveredSelectionError) as ctx:
                    select_discovered_artifact(self.variants, filename=candidate)
                self.assertIn(
                    "ilename selector", str(ctx.exception)
                )

    def test_empty_quantization_selector_is_rejected(self):
        for candidate in ("", "   "):
            with self.subTest(candidate=candidate):
                with self.assertRaises(DiscoveredSelectionError) as ctx:
                    select_discovered_artifact(
                        self.variants, quantization=candidate
                    )
                self.assertIn("Quantization selector", str(ctx.exception))

    def test_empty_revision_selector_is_rejected(self):
        for candidate in ("", "   "):
            with self.subTest(candidate=candidate):
                with self.assertRaises(DiscoveredSelectionError) as ctx:
                    select_discovered_artifact(self.variants, revision=candidate)
                self.assertIn("Revision selector", str(ctx.exception))

    def test_invalid_selector_is_distinct_from_no_match(self):
        with self.assertRaises(DiscoveredSelectionError) as invalid:
            select_discovered_artifact(self.variants, filename="../x.gguf")
        with self.assertRaises(DiscoveredSelectionError) as missing:
            select_discovered_artifact(self.variants, filename="absent.gguf")
        self.assertNotEqual(str(invalid.exception), str(missing.exception))

    def test_non_string_selectors_are_invalid_selectors(self):
        for kwargs in ({"quantization": 8}, {"filename": 8}, {"revision": 8}):
            with (
                    self.subTest(kwargs=kwargs),
                    self.assertRaises(DiscoveredSelectionError),
                ):
                    select_discovered_artifact(self.variants, **kwargs)

def _mapped_identity(discovered):
    """The mapped identity, obtained without modifying B9.82."""
    (spec,) = map_discovered_artifacts(
        [discovered], identity_resolver=identity_resolver
    )
    return spec.artifact_id


class IdentityBoundaryTests(unittest.TestCase):
    """20, 21: D5 identity stays downstream; D3 identity is never influenced."""

    def test_no_identity_resolver_is_accepted(self):
        # D5: the signature must not grow an identity parameter.
        parameters = inspect.signature(select_discovered_artifact).parameters
        self.assertNotIn("identity_resolver", parameters)
        self.assertEqual(
            ["variants", "quantization", "filename", "revision"],
            list(parameters),
        )

    def test_selection_never_resolves_or_fabricates_model_id(self):
        found = artifact()
        self.assertIsNone(found.model_id)
        selected = select_discovered_artifact([variant([found])])
        self.assertIsNone(selected.model_id)

        declared = DiscoveredArtifact(
            repository=REPO,
            filename="declared.gguf",
            format="GGUF",
            declared_quantization="Q4_K_M",
            model_id="upstream/declared",
        )
        selected = select_discovered_artifact([variant([declared])])
        # Transported verbatim, never resolved and never replaced.
        self.assertEqual(selected.model_id, "upstream/declared")

    def test_selection_does_not_mutate_the_candidate(self):
        found = artifact(revision=REVISION)
        before = (
            found.filename,
            found.declared_quantization,
            found.revision,
            found.model_id,
        )
        select_discovered_artifact(
            [variant([found])],
            quantization="Q4_K_M",
            filename="model-q4.gguf",
            revision=REVISION,
        )
        after = (
            found.filename,
            found.declared_quantization,
            found.revision,
            found.model_id,
        )
        self.assertEqual(before, after)

    def test_revision_selection_does_not_alter_identity(self):
        """21. revision is a criterion, never an identity component."""
        one = artifact("same.gguf", revision=REVISION)
        two = artifact("same.gguf", revision=OTHER_REVISION)
        # Same filename and quantization: identity-relevant inputs are equal.
        self.assertEqual(one.filename, two.filename)
        self.assertEqual(one.declared_quantization, two.declared_quantization)

        selected = select_discovered_artifact(
            [variant([one, two])], revision=REVISION
        )
        self.assertEqual(selected.filename, two.filename)
        self.assertIsNone(selected.model_id)
        self.assertNotIn(
            REVISION,
            _mapped_identity(selected),
            "revision must never participate in identity (B9.83 OD-1)",
        )


class B982InteroperabilityTests(unittest.TestCase):
    """10, 22: B9.84 output feeds B9.82 unchanged."""

    def test_selected_artifact_is_the_original_discovered_object(self):
        found = artifact("model-q4.gguf")
        selected = select_discovered_artifact(
            [variant([found])], quantization="Q4_K_M"
        )
        self.assertIsInstance(selected, DiscoveredArtifact)
        self.assertIs(selected, found)
        self.assertNotIsInstance(selected, ArtifactSpec)

    def test_selected_artifact_maps_through_b982_unchanged(self):
        found = artifact("model-q4.gguf", revision=REVISION)
        selected = select_discovered_artifact(
            [variant([found])], quantization="Q4_K_M"
        )

        mapped = map_discovered_artifacts(
            [selected], identity_resolver=identity_resolver
        )
        self.assertEqual(len(mapped), 1)
        spec = mapped[0]
        self.assertEqual(spec.filename, found.filename)
        self.assertEqual(spec.quantization, found.declared_quantization)
        # Identity is injected downstream by the caller's resolver (D5).
        self.assertEqual(spec.model_id, f"local/{REPO}")
        # B9.83 transport is intact and untouched by B9.84.
        self.assertEqual(spec.revision, REVISION)

    def test_selection_precedes_mapping_in_the_recorded_flow(self):
        # D2: one artifact is chosen first, and the mapper then sees exactly
        # that one artifact -- never a set of alternatives to discard.
        found = artifact("model-q8.gguf", quantization="Q8_0")
        noise = artifact("model-q4.gguf", quantization="Q4_K_M")
        variants = [variant([noise]), variant([found], quantization="Q8_0")]
        selected = select_discovered_artifact(variants, quantization="Q8_0")
        mapped = map_discovered_artifacts(
            [selected], identity_resolver=identity_resolver
        )
        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0].filename, "model-q8.gguf")


class LegacySelectorIsolationTests(unittest.TestCase):
    """23: D4 -- the acquisition-domain selector stays untouched."""

    def test_b984_error_is_distinct_from_other_domain_errors(self):
        # D7: neither ArtifactSelectionError nor DiscoveryError is reused.
        self.assertFalse(
            issubclass(DiscoveredSelectionError, ArtifactSelectionError)
        )
        self.assertFalse(issubclass(DiscoveredSelectionError, DiscoveryError))
        self.assertTrue(issubclass(DiscoveredSelectionError, Exception))

    def test_b984_failure_is_not_catchable_as_a_legacy_selection_error(self):
        variants = [variant([artifact("model-q4.gguf")])]
        try:
            select_discovered_artifact(variants, quantization="Q2_K")
        except ArtifactSelectionError:  # pragma: no cover - must not happen
            self.fail("B9.84 must not raise ArtifactSelectionError")
        except DiscoveredSelectionError:
            pass

    def test_legacy_select_artifact_behaviour_is_unchanged(self):
        specs = [
            ArtifactSpec(
                model_id="owner/repository",
                source="huggingface",
                repository=REPO,
                filename="model-q4.gguf",
                format="GGUF",
                quantization="Q4_K_M",
            ),
            ArtifactSpec(
                model_id="owner/repository",
                source="huggingface",
                repository=REPO,
                filename="model-q8.gguf",
                format="GGUF",
                quantization="Q8_0",
            ),
        ]
        self.assertIs(select_artifact([specs[0]]), specs[0])
        self.assertIs(select_artifact(specs, quantization="Q8_0"), specs[1])
        with self.assertRaises(ArtifactSelectionError):
            select_artifact([])
        with self.assertRaises(ArtifactSelectionError):
            select_artifact(specs)

    def test_b984_module_does_not_import_the_legacy_selector(self):
        import castlearq.discovery_selection as module

        self.assertNotIn("select_artifact", vars(module))
        self.assertNotIn("ArtifactSelectionError", vars(module))

    def test_b984_module_declares_exactly_its_public_contract(self):
        import castlearq.discovery_selection as module

        self.assertEqual(
            sorted(module.__all__),
            ["DiscoveredSelectionError", "select_discovered_artifact"],
        )


class PurityTests(unittest.TestCase):
    """Purity, boundary placement and programming-error behaviour."""

    def test_wrongly_typed_variants_raise_plain_type_error(self):
        with self.assertRaises(TypeError):
            select_discovered_artifact(["not-a-variant"])
        with self.assertRaises(TypeError):
            select_discovered_artifact([artifact()])

    def test_wrongly_typed_containers_raise_plain_type_error(self):
        with self.assertRaises(TypeError):
            select_discovered_artifact(artifact())
        with self.assertRaises(TypeError):
            select_discovered_artifact("model-q4.gguf")

    def test_selection_requires_no_filesystem_or_network(self):
        # The module may not pull in network or filesystem machinery. Only
        # ``pathlib`` is permitted, and only for PurePosixPath selector
        # validation, which touches no disk.
        import castlearq.discovery_selection as module

        forbidden = {"socket", "urllib", "http", "os", "shutil", "tempfile"}
        imported = {
            name
            for name, value in vars(module).items()
            if getattr(value, "__class__", None).__name__ == "module"
        }
        self.assertFalse(
            {name for name in imported if name.split(".")[0] in forbidden}
        )

    def test_public_contract_is_importable_from_the_module(self):
        from castlearq.discovery_selection import (
            DiscoveredSelectionError as error_cls,
        )
        from castlearq.discovery_selection import (
            select_discovered_artifact as selector,
        )

        self.assertIs(error_cls, DiscoveredSelectionError)
        self.assertIs(selector, select_discovered_artifact)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
