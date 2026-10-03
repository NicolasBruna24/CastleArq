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

"""B9.91 focused tests: internal Dynamic Model Library capability.

These tests pin the ratified B9.91 contract:

- the capability composes the existing discovery port and nothing else;
- candidates, variants and artifacts are returned **by identity**;
- provider order, duplicates and the opaque cursor are preserved verbatim;
- selection is delegated to B9.84 and never reimplemented;
- the acquisition handoff value is the exact ``DiscoveredArtifact``;
- acquirability is unspecified: nothing is fabricated, filtered or exposed;
- discovery and selection failures are translated into a minimal
  application-level error with the original cause preserved;
- the capability is stateless and depends on nothing outside discovery,
  selection and the standard library.

No network access and no new test framework are used.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelDiscovery,
    ModelVariant,
)
from castlearq.discovery_selection import (
    DiscoveredSelectionError,
    select_discovered_artifact,
)
from castlearq.dynamic_model_library import (
    DynamicModelLibrary,
    DynamicModelLibraryError,
    DynamicModelLibraryErrorCategory,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "castlearq"
    / "dynamic_model_library.py"
)

REVISION = "a" * 40

FORBIDDEN_IMPORTS = (
    "models",
    "acquisition_mapping",
    "acquisition_service",
    "downloads",
    "model_store",
    "model_identity",
    "model_domain",
    "sources",
    "main",
    "api",
    "application_wiring",
)


def _candidate(repository: str = "org/model", **overrides) -> ModelCandidate:
    values = {
        "provider_id": "huggingface",
        "repository": repository,
        "display_name": "A Model",
        "author": "org",
        "description": "declared description",
        "tags": ("gguf", "text-generation"),
        "declared_architecture": "qwen2",
        "has_gguf": True,
    }
    values.update(overrides)
    return ModelCandidate(**values)


def _artifact(filename: str, quantization: str, **overrides) -> DiscoveredArtifact:
    values = {
        "repository": "org/model",
        "filename": filename,
        "format": "GGUF",
        "declared_quantization": quantization,
        "model_id": None,
        "source": "huggingface",
        "download_url": "https://huggingface.co/org/model/resolve/main/" + filename,
        "declared_size": 1024,
        "declared_sha256": "b" * 64,
        "revision": REVISION,
    }
    values.update(overrides)
    return DiscoveredArtifact(**values)


def _variants(candidate: ModelCandidate | None = None):
    """Provider-shaped variants: grouped by quantization, filename-ordered."""
    candidate = candidate if candidate is not None else _candidate()
    low = _artifact("model-q4_k_m.gguf", "Q4_K_M", revision=REVISION)
    high = _artifact("model-q8_0.gguf", "Q8_0", revision="b" * 40)
    unknown = _artifact(
        "model-experimental.gguf", "Unknown", format="Unknown", revision="c" * 40
    )
    return (
        ModelVariant(
            candidate=candidate, declared_quantization="Q4_K_M", artifacts=(low,)
        ),
        ModelVariant(
            candidate=candidate, declared_quantization="Q8_0", artifacts=(high,)
        ),
        ModelVariant(
            candidate=candidate, declared_quantization="Unknown", artifacts=(unknown,)
        ),
    )



class FakeDiscovery(ModelDiscovery):
    """Injected port implementation recording exactly what it was asked."""

    def __init__(self, candidates=(), variants=(), *, search_error=None, inspect_error=None):
        self.candidates = tuple(candidates)
        self.variants = tuple(variants)
        self.search_error = search_error
        self.inspect_error = inspect_error
        self.search_calls = []
        self.inspect_calls = []

    def search(self, query, *, limit=20, cursor=None):
        self.search_calls.append((query, limit, cursor))
        if self.search_error is not None:
            raise self.search_error
        return self.candidates, "opaque-cursor"

    def inspect(self, repository):
        self.inspect_calls.append(repository)
        if self.inspect_error is not None:
            raise self.inspect_error
        return self.variants


class SearchDelegationTests(unittest.TestCase):
    def test_search_reaches_the_injected_discovery_exactly_once(self):
        provider = FakeDiscovery(candidates=[_candidate()])
        DynamicModelLibrary(provider).search("qwen")
        self.assertEqual(len(provider.search_calls), 1)

    def test_query_limit_and_cursor_are_forwarded_verbatim(self):
        provider = FakeDiscovery(candidates=[_candidate()])
        DynamicModelLibrary(provider).search("qwen 7b", limit=7, cursor="opaque")
        self.assertEqual(provider.search_calls[0], ("qwen 7b", 7, "opaque"))

    def test_limit_is_forwarded_only_when_supplied(self):
        provider = FakeDiscovery(candidates=[_candidate()])
        DynamicModelLibrary(provider).search("qwen")
        self.assertEqual(provider.search_calls[0], ("qwen", 20, None))

    def test_next_cursor_is_returned_unchanged(self):
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=[_candidate()])).search("q")
        self.assertEqual(outcome.next_cursor, "opaque-cursor")

    def test_candidates_are_passed_through_by_identity_and_order(self):
        first, second = _candidate("org/a"), _candidate("org/b")
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=[first, second])).search("q")
        self.assertEqual(outcome.candidates, (first, second))
        for produced, supplied in zip(outcome.candidates, (first, second)):
            self.assertIs(produced, supplied)

    def test_duplicate_candidates_are_preserved(self):
        repeated = _candidate("org/dup")
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=[repeated, repeated])).search("q")
        self.assertEqual(len(outcome.candidates), 2)
        self.assertIs(outcome.candidates[0], outcome.candidates[1])

    def test_empty_search_result_is_a_completed_call(self):
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=())).search("nothing")
        self.assertEqual(outcome.candidates, ())
        self.assertEqual(outcome.next_cursor, "opaque-cursor")

    def test_the_capability_instantiates_no_provider_itself(self):
        library = DynamicModelLibrary(FakeDiscovery())
        self.assertIsInstance(library.discovery_provider, FakeDiscovery)
        self.assertNotIn("HuggingFaceDiscoveryProvider", MODULE_PATH.read_text("utf-8"))

    def test_candidate_metadata_is_not_transformed(self):
        candidate = _candidate()
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=[candidate])).search("q")
        produced = outcome.candidates[0]
        for field in (
            "provider_id", "repository", "display_name", "author",
            "description", "tags", "declared_architecture", "has_gguf",
        ):
            self.assertEqual(getattr(produced, field), getattr(candidate, field))

    def test_no_acquirability_annotation_is_exposed(self):
        outcome = DynamicModelLibrary(FakeDiscovery(candidates=[_candidate()])).search("q")
        for field in ("acquirable", "is_acquirable", "model_id", "logical_model_id"):
            self.assertFalse(hasattr(outcome, field), field)
            self.assertFalse(hasattr(outcome.candidates[0], field), field)


class InspectDelegationTests(unittest.TestCase):
    def test_the_candidates_repository_is_forwarded(self):
        provider = FakeDiscovery(variants=_variants())
        DynamicModelLibrary(provider).inspect(_candidate("org/specific"))
        self.assertEqual(provider.inspect_calls, ["org/specific"])

    def test_inspect_is_called_exactly_once_per_operation(self):
        provider = FakeDiscovery(variants=_variants())
        DynamicModelLibrary(provider).inspect(_candidate())
        self.assertEqual(len(provider.inspect_calls), 1)

    def test_variants_are_passed_through_by_identity_and_order(self):
        variants = _variants()
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(
            _candidate()
        )
        self.assertEqual(produced, variants)
        for produced_variant, supplied in zip(produced, variants):
            self.assertIs(produced_variant, supplied)

    def test_variant_candidate_is_never_replaced(self):
        candidate = _candidate()
        variants = _variants(candidate)
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(candidate)
        for variant in produced:
            self.assertIs(variant.candidate, candidate)

    def test_artifacts_are_passed_through_by_identity(self):
        variants = _variants()
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(
            _candidate()
        )
        for produced_variant, supplied in zip(produced, variants):
            for artifact, expected in zip(produced_variant.artifacts, supplied.artifacts):
                self.assertIs(artifact, expected)

    def test_declared_quantization_including_unknown_is_preserved(self):
        variants = _variants()
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(
            _candidate()
        )
        self.assertEqual(
            [variant.declared_quantization for variant in produced],
            ["Q4_K_M", "Q8_0", "Unknown"],
        )
        self.assertEqual(produced[2].artifacts[0].format, "Unknown")

    def test_artifact_metadata_is_not_transformed(self):
        variants = _variants()
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(
            _candidate()
        )
        supplied = variants[0].artifacts[0]
        artifact = produced[0].artifacts[0]
        for field in (
            "repository", "filename", "format", "declared_quantization", "model_id",
            "source", "download_url", "declared_size", "declared_sha256", "revision",
        ):
            self.assertEqual(getattr(artifact, field), getattr(supplied, field), field)

    def test_revision_survives_inspection_unchanged(self):
        variants = _variants()
        produced = DynamicModelLibrary(FakeDiscovery(variants=variants)).inspect(
            _candidate()
        )
        for produced_variant, supplied in zip(produced, variants):
            for artifact, expected in zip(produced_variant.artifacts, supplied.artifacts):
                self.assertEqual(artifact.revision, expected.revision)
        self.assertIn(
            REVISION, [a.revision for v in produced for a in v.artifacts]
        )

    def test_empty_inspection_result_is_returned_as_an_empty_tuple(self):
        produced = DynamicModelLibrary(FakeDiscovery(variants=())).inspect(_candidate())
        self.assertEqual(produced, ())

    def test_no_deduplication_of_variants(self):
        repeated = _variants()[0]
        produced = DynamicModelLibrary(
            FakeDiscovery(variants=(repeated, repeated))
        ).inspect(_candidate())
        self.assertEqual(len(produced), 2)
        self.assertIs(produced[0], produced[1])


class SelectionDelegationTests(unittest.TestCase):
    def test_the_default_delegate_is_the_b984_authority(self):
        library = DynamicModelLibrary(FakeDiscovery())
        self.assertIs(library.selection_delegate, select_discovered_artifact)

    def test_an_injected_delegate_is_invoked_exactly_once(self):
        calls = []

        def delegate(variants, **selectors):
            calls.append((variants, selectors))
            return variants[0].artifacts[0]

        variants = _variants()
        DynamicModelLibrary(FakeDiscovery(), selection_delegate=delegate).select(
            variants, quantization="Q4_K_M"
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], variants)

    def test_selectors_are_forwarded_unchanged(self):
        seen = {}

        def delegate(variants, **selectors):
            seen.update(selectors)
            return variants[0].artifacts[0]

        DynamicModelLibrary(FakeDiscovery(), selection_delegate=delegate).select(
            _variants(),
            quantization="Q8_0",
            filename="model-q8_0.gguf",
            revision=REVISION,
        )
        self.assertEqual(
            seen,
            {"quantization": "Q8_0", "filename": "model-q8_0.gguf", "revision": REVISION},
        )

    def test_no_selector_is_pre_validated(self):
        seen = {}

        def delegate(variants, **selectors):
            seen.update(selectors)
            return variants[0].artifacts[0]

        DynamicModelLibrary(FakeDiscovery(), selection_delegate=delegate).select(
            _variants(), quantization="  ", filename="../escape", revision="zz"
        )
        self.assertEqual(
            seen, {"quantization": "  ", "filename": "../escape", "revision": "zz"}
        )

    def test_the_selected_artifact_identity_is_preserved(self):
        variants = _variants()
        expected = variants[0].artifacts[0]
        outcome = DynamicModelLibrary(FakeDiscovery()).select(variants, quantization="Q4_K_M")
        self.assertIs(outcome.selected, expected)

    def test_selection_by_revision_returns_the_declared_revision(self):
        outcome = DynamicModelLibrary(FakeDiscovery()).select(_variants(), revision=REVISION)
        self.assertEqual(outcome.selected.revision, REVISION)

    def test_b984_ambiguity_remains_the_authority(self):
        with self.assertRaises(DynamicModelLibraryError) as raised:
            DynamicModelLibrary(FakeDiscovery()).select(_variants())
        self.assertEqual(
            raised.exception.category, DynamicModelLibraryErrorCategory.SELECTION_FAILED
        )

    def test_the_module_defines_no_selection_algorithm(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for forbidden in ("select_artifact", "match", "score", "rank", "compare", "normalize"):
            self.assertNotIn(forbidden, functions)

    def test_a_non_iterable_variants_argument_is_a_programming_error(self):
        with self.assertRaises(TypeError):
            DynamicModelLibrary(FakeDiscovery()).select(object())

    def test_a_wrongly_typed_variant_is_a_programming_error(self):
        with self.assertRaises(TypeError):
            DynamicModelLibrary(FakeDiscovery()).select([_candidate()])


class ErrorContractTests(unittest.TestCase):
    def test_search_failure_is_translated_with_the_cause_preserved(self):
        original = DiscoveryError("provider unavailable")
        provider = FakeDiscovery(search_error=original)
        with self.assertRaises(DynamicModelLibraryError) as raised:
            DynamicModelLibrary(provider).search("q")
        error = raised.exception
        self.assertEqual(error.category, DynamicModelLibraryErrorCategory.DISCOVERY_FAILED)
        self.assertIs(error.cause, original)
        self.assertIs(error.__cause__, original)

    def test_inspect_failure_is_translated_with_the_cause_preserved(self):
        original = DiscoveryError("tree unavailable")
        provider = FakeDiscovery(inspect_error=original)
        with self.assertRaises(DynamicModelLibraryError) as raised:
            DynamicModelLibrary(provider).inspect(_candidate())
        self.assertEqual(
            raised.exception.category, DynamicModelLibraryErrorCategory.DISCOVERY_FAILED
        )
        self.assertIs(raised.exception.cause, original)

    def test_selection_failure_is_translated_with_the_cause_preserved(self):
        def delegate(_variants, **_selectors):
            raise DiscoveredSelectionError("ambiguous")

        with self.assertRaises(DynamicModelLibraryError) as raised:
            DynamicModelLibrary(
                FakeDiscovery(), selection_delegate=delegate
            ).select(_variants())
        self.assertEqual(
            raised.exception.category, DynamicModelLibraryErrorCategory.SELECTION_FAILED
        )
        self.assertIsInstance(raised.exception.cause, DiscoveredSelectionError)

    def test_programming_errors_are_not_wrapped(self):
        library = DynamicModelLibrary(FakeDiscovery())
        with self.assertRaises(TypeError):
            library.inspect("org/not-a-candidate")
        with self.assertRaises(TypeError):
            DynamicModelLibrary(object())

    def test_the_error_category_vocabulary_is_exactly_two(self):
        self.assertEqual(
            [category.value for category in DynamicModelLibraryErrorCategory],
            ["discovery_failed", "selection_failed"],
        )

    def test_the_error_boundary_does_not_subclass_the_translated_types(self):
        for translated in (DiscoveryError, DiscoveredSelectionError):
            self.assertFalse(
                issubclass(DynamicModelLibraryError, translated), translated.__name__
            )


class StatelessnessTests(unittest.TestCase):
    def test_consecutive_calls_do_not_leak_state(self):
        first, second = _candidate("org/first"), _candidate("org/second")
        provider = FakeDiscovery(candidates=[first, second])
        library = DynamicModelLibrary(provider)

        library.search("first", limit=1, cursor="c1")
        outcome = library.search("second")

        self.assertEqual(provider.search_calls[0], ("first", 1, "c1"))
        self.assertEqual(provider.search_calls[1], ("second", 20, None))
        self.assertEqual(outcome.candidates, (first, second))

    def test_the_instance_retains_no_per_call_state(self):
        library = DynamicModelLibrary(FakeDiscovery(candidates=[_candidate()]))
        library.search("q")
        library.inspect(_candidate())
        library.select(_variants(), quantization="Q4_K_M")
        self.assertEqual(
            set(vars(library)), {"discovery_provider", "selection_delegate"}
        )

    def test_repeated_inspection_of_one_repository_is_not_memoized(self):
        provider = FakeDiscovery(variants=_variants())
        library = DynamicModelLibrary(provider)
        library.inspect(_candidate())
        library.inspect(_candidate())
        self.assertEqual(len(provider.inspect_calls), 2)


class IsolationTests(unittest.TestCase):
    def _module_imports(self) -> set:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.name)
                if node.level:
                    prefix = "." * node.level
                    imported.add(prefix + (node.module or ""))
                elif node.module:
                    imported.add(node.module)
        return imported

    def test_no_forbidden_module_is_imported(self):
        imported = self._module_imports()
        for forbidden in FORBIDDEN_IMPORTS:
            for name in imported:
                self.assertNotEqual(name, forbidden)
                self.assertNotEqual(name, f".{forbidden}")

    def test_the_module_imports_only_discovery_and_selection(self):
        relative = {name for name in self._module_imports() if name.startswith(".")}
        self.assertEqual(relative, {".discovery", ".discovery_selection"})

    def test_the_module_never_constructs_an_artifact_spec(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        self.assertNotIn("ArtifactSpec(", code)

    def test_no_library_hierarchy_type_is_defined(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        classes = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        for forbidden in (
            "LibraryModel", "LibraryVariant", "LibraryArtifact", "LibraryEntry",
            "ModelFamily", "ModelRecord", "ModelIdentity",
        ):
            self.assertNotIn(forbidden, classes)

    def test_the_capability_is_not_exported_from_the_package(self):
        init_source = (MODULE_PATH.parent / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("DynamicModelLibrary", init_source)

    def test_the_package_init_still_has_no_imports(self):
        init_path = MODULE_PATH.parent / "__init__.py"
        package = ast.parse(init_path.read_text(encoding="utf-8"))
        self.assertEqual(
            [n for n in package.body if isinstance(n, (ast.Import, ast.ImportFrom))], []
        )

    def test_no_presentation_surface_exists(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("print(", "argparse", "json.dumps", "FastAPI", "tkinter"):
            self.assertNotIn(forbidden, source)

    def test_the_module_never_mentions_acquisition_identity_modules(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        for forbidden in ("model_identity", "logical_model_id", "downloadable_locator"):
            self.assertNotIn(forbidden, names)


class CompositionTests(unittest.TestCase):
    def test_the_composition_factory_builds_one_capability(self):
        from castlearq.application_wiring import compose_dynamic_model_library

        provider = FakeDiscovery(candidates=[_candidate()])
        library = compose_dynamic_model_library(discovery_provider=provider)
        self.assertIsInstance(library, DynamicModelLibrary)
        self.assertIs(library.discovery_provider, provider)

    def test_the_composition_factory_is_not_cached(self):
        from castlearq.application_wiring import compose_dynamic_model_library

        self.assertIsNot(
            compose_dynamic_model_library(discovery_provider=FakeDiscovery()),
            compose_dynamic_model_library(discovery_provider=FakeDiscovery()),
        )

    def test_the_composition_factory_defaults_to_the_b984_authority(self):
        from castlearq.application_wiring import compose_dynamic_model_library

        library = compose_dynamic_model_library(discovery_provider=FakeDiscovery())
        self.assertIs(library.selection_delegate, select_discovered_artifact)

    def test_the_composition_factory_accepts_a_selection_delegate(self):
        from castlearq.application_wiring import compose_dynamic_model_library

        def delegate(variants, **_selectors):
            return variants[0].artifacts[0]

        library = compose_dynamic_model_library(
            discovery_provider=FakeDiscovery(), selection_delegate=delegate
        )
        self.assertIs(library.selection_delegate, delegate)


if __name__ == "__main__":  # pragma: no cover - manual execution convenience
    unittest.main()
