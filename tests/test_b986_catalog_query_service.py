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

"""B9.86: the application catalog / query boundary and its result contract.

All collaborators are local fakes: no network, no Hugging Face API, no
filesystem state and no production provider code.
"""

import inspect as _inspect
import pathlib
import unittest

from castlearq.catalog_query_service import (
    CatalogQueryError,
    CatalogQueryErrorCategory,
    CatalogQueryOutcome,
    ModelCatalogQueryService,
)
from castlearq.discovery import DiscoveryError, ModelCandidate

REPO_A = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
REPO_B = "meta-llama/Llama-3.1-8B-Instruct-GGUF"
REPO_C = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B-GGUF"

SERVICE_MODULE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "castlearq"
    / "catalog_query_service.py"
)


def candidate(repository=REPO_A, *, display_name=None, tags=(), has_gguf=True):
    """One declared remote candidate, exactly as B9.80 models it."""
    return ModelCandidate(
        provider_id="huggingface",
        repository=repository,
        display_name=display_name,
        author="someone",
        description="a description",
        tags=tuple(tags),
        declared_architecture="llama",
        has_gguf=has_gguf,
    )


class _RecordingDiscovery:
    """A B9.80 port fake that records how it was called."""

    def __init__(self, candidates=(), next_cursor=None, error=None):
        self._candidates = tuple(candidates)
        self._next_cursor = next_cursor
        self._error = error
        self.calls = []

    def search(self, query, *, limit=20, cursor=None):
        self.calls.append({"query": query, "limit": limit, "cursor": cursor})
        if self._error is not None:
            raise self._error
        return self._candidates, self._next_cursor

    def inspect(self, repository):  # pragma: no cover - not a B9.86 use case
        raise AssertionError("the query boundary must never call inspect()")


def _executable_source(path):
    """The module source with comments and docstrings removed.

    Prohibited concepts are named in this file's docstrings precisely in order
    to exclude them, so a raw substring scan would be a false positive. This
    strips documentation and keeps only executable code.
    """
    import ast
    import io
    import tokenize

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    docstring_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body:
                first = node.body[0]
                docstring_lines.update(
                    range(first.lineno, (first.end_lineno or first.lineno) + 1)
                )

    kept = []
    previous_end = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.start[0] in docstring_lines:
            continue
        if token.start[0] > previous_end:
            kept.append("\n" * (token.start[0] - previous_end))
        kept.append(token.string)
        previous_end = token.end[0]
    return "".join(kept)


def _service(**kwargs):
    discovery = _RecordingDiscovery(**kwargs)
    return ModelCatalogQueryService(discovery_provider=discovery), discovery


def _raising(exception):
    """A ``search`` replacement that always raises ``exception``.

    It is assigned to the fake provider *instance*, so it takes no ``self``.
    """

    def search(query, *, limit=20, cursor=None):
        raise exception

    return search


class HappyPathTests(unittest.TestCase):
    def test_candidates_are_returned_unchanged_by_identity(self):
        first, second = candidate(REPO_A), candidate(REPO_B)
        service, _ = _service(candidates=(first, second))

        outcome = service.query("llama")

        self.assertEqual(outcome.candidates[0], first)
        self.assertEqual(outcome.candidates[1], second)
        # Lossless: the very objects the provider returned, not copies.
        self.assertIs(outcome.candidates[0], first)
        self.assertIs(outcome.candidates[1], second)

    def test_candidate_metadata_is_preserved_losslessly(self):
        declared = candidate(REPO_A, display_name="Qwen", tags=("gguf", "code"))
        service, _ = _service(candidates=(declared,))

        returned = service.query("qwen").candidates[0]

        self.assertEqual(returned.provider_id, "huggingface")
        self.assertEqual(returned.repository, REPO_A)
        self.assertEqual(returned.display_name, "Qwen")
        self.assertEqual(returned.author, "someone")
        self.assertEqual(returned.description, "a description")
        self.assertEqual(returned.tags, ("gguf", "code"))
        self.assertEqual(returned.declared_architecture, "llama")
        self.assertTrue(returned.has_gguf)

    def test_candidate_order_is_preserved_and_never_sorted(self):
        # Deliberately NOT alphabetical: any sorting would reorder this.
        declared = (candidate(REPO_C), candidate(REPO_A), candidate(REPO_B))
        service, _ = _service(candidates=declared)

        repositories = [c.repository for c in service.query("x").candidates]

        self.assertEqual(repositories, [REPO_C, REPO_A, REPO_B])

    def test_next_cursor_is_preserved_verbatim(self):
        service, _ = _service(candidates=(candidate(),), next_cursor="opaque-token")

        self.assertEqual(service.query("x").next_cursor, "opaque-token")

    def test_none_next_cursor_is_preserved_as_none(self):
        service, _ = _service(candidates=(candidate(),), next_cursor=None)

        self.assertIsNone(service.query("x").next_cursor)

    def test_empty_candidate_tuple_is_a_valid_outcome_not_an_error(self):
        service, _ = _service(candidates=())

        outcome = service.query("nothing-matches")

        self.assertEqual(outcome.candidates, ())
        self.assertIsNone(outcome.next_cursor)

    def test_outcome_is_frozen(self):
        service, _ = _service(candidates=(candidate(),))

        outcome = service.query("x")

        with self.assertRaises(AttributeError):
            outcome.next_cursor = "mutated"

    def test_outcome_exposes_no_derived_pagination_or_ranking_fields(self):
        fields = set(CatalogQueryOutcome.__dataclass_fields__)

        self.assertEqual(fields, {"candidates", "next_cursor"})
        for forbidden in (
            "total",
            "has_next",
            "page",
            "offset",
            "rank",
            "score",
            "recommendation",
        ):
            self.assertNotIn(forbidden, fields)


class ArgumentPassThroughTests(unittest.TestCase):
    def test_query_is_forwarded_unchanged(self):
        service, discovery = _service(candidates=())

        service.query("  Mixed Case QUERY  ")

        self.assertEqual(discovery.calls[0]["query"], "  Mixed Case QUERY  ")

    def test_limit_is_forwarded_unchanged(self):
        service, discovery = _service(candidates=())

        service.query("x", limit=7)

        self.assertEqual(discovery.calls[0]["limit"], 7)

    def test_cursor_is_forwarded_unchanged_and_not_rewritten(self):
        service, discovery = _service(candidates=())

        service.query("x", cursor="opaque::token==")

        self.assertEqual(discovery.calls[0]["cursor"], "opaque::token==")

    def test_out_of_range_limit_is_passed_through_and_never_clamped(self):
        # B9.81 owns validation. This boundary must not become a second
        # validation authority, so an out-of-range limit is forwarded verbatim
        # rather than clamped or rejected here.
        service, discovery = _service(candidates=())

        service.query("x", limit=999_999)
        service.query("x", limit=0)

        self.assertEqual(discovery.calls[0]["limit"], 999_999)
        self.assertEqual(discovery.calls[1]["limit"], 0)

    def test_defaults_match_the_discovery_port_defaults(self):
        service, discovery = _service(candidates=())

        service.query("x")

        self.assertEqual(discovery.calls[0]["limit"], 20)
        self.assertIsNone(discovery.calls[0]["cursor"])

    def test_a_cursor_is_not_pre_validated_by_the_application_layer(self):
        service, discovery = _service(candidates=())

        service.query("x", cursor="not-a-real-cursor")

        self.assertEqual(discovery.calls[0]["cursor"], "not-a-real-cursor")


class InvocationTests(unittest.TestCase):
    def test_search_is_called_exactly_once_per_query(self):
        service, discovery = _service(candidates=(candidate(),))

        service.query("llama")

        self.assertEqual(len(discovery.calls), 1)

    def test_each_query_call_performs_its_own_single_search(self):
        service, discovery = _service(candidates=(candidate(),))

        service.query("first")
        service.query("second")

        self.assertEqual(len(discovery.calls), 2)
        self.assertEqual(discovery.calls[0]["query"], "first")
        self.assertEqual(discovery.calls[1]["query"], "second")


class ErrorTranslationTests(unittest.TestCase):
    def test_discovery_error_becomes_an_application_error(self):
        original = DiscoveryError("metadata request failed")
        service, _ = _service(error=original)

        with self.assertRaises(CatalogQueryError) as caught:
            service.query("x")

        self.assertEqual(
            caught.exception.category,
            CatalogQueryErrorCategory.DISCOVERY_FAILED,
        )
        self.assertEqual(str(caught.exception), "metadata request failed")

    def test_original_is_preserved_as_cause_and_as_dunder_cause(self):
        original = DiscoveryError("boom")
        service, _ = _service(error=original)

        with self.assertRaises(CatalogQueryError) as caught:
            service.query("x")

        self.assertIs(caught.exception.cause, original)
        self.assertIs(caught.exception.__cause__, original)

    def test_a_refused_cursor_is_reported_under_its_own_category(self):
        service, _ = _service(error=DiscoveryError("Invalid discovery cursor"))

        with self.assertRaises(CatalogQueryError) as caught:
            service.query("x", cursor="bad")

        self.assertEqual(
            caught.exception.category,
            CatalogQueryErrorCategory.INVALID_CURSOR,
        )

    def test_application_error_is_not_a_lower_level_error(self):
        service, _ = _service(error=DiscoveryError("boom"))

        with self.assertRaises(CatalogQueryError) as caught:
            service.query("x")

        self.assertNotIsInstance(caught.exception, DiscoveryError)
        self.assertFalse(issubclass(CatalogQueryError, DiscoveryError))

    def test_error_categories_are_the_two_approved_ones(self):
        self.assertEqual(
            {c.value for c in CatalogQueryErrorCategory},
            {"discovery_failed", "invalid_cursor"},
        )


class ContractErrorTests(unittest.TestCase):
    """TypeError and ValueError are caller-contract violations, not expected
    operational failures. They must propagate unchanged, never translated."""

    def test_provider_type_error_propagates_unchanged(self):
        service, _ = _service()
        service.discovery_provider.search = _raising(
            TypeError("query must be a string")
        )

        with self.assertRaises(TypeError) as caught:
            service.query(123)

        self.assertEqual(str(caught.exception), "query must be a string")

    def test_provider_value_error_propagates_unchanged(self):
        service, _ = _service()
        service.discovery_provider.search = _raising(
            ValueError("limit must be an int between 1 and 1000")
        )

        with self.assertRaises(ValueError) as caught:
            service.query("x", limit=0)

        self.assertEqual(
            str(caught.exception), "limit must be an int between 1 and 1000"
        )

    def test_contract_errors_are_not_wrapped_in_an_application_error(self):
        service, _ = _service()
        service.discovery_provider.search = _raising(TypeError("bad type"))

        with self.assertRaises(TypeError):
            try:
                service.query(123)
            except CatalogQueryError:  # pragma: no cover - must not happen
                self.fail("TypeError must not be translated")


class DependencyInjectionTests(unittest.TestCase):
    def test_service_uses_the_injected_provider(self):
        discovery = _RecordingDiscovery(candidates=(candidate(),))
        service = ModelCatalogQueryService(discovery_provider=discovery)

        self.assertIs(service.discovery_provider, discovery)

    def test_service_constructor_only_accepts_the_discovery_provider(self):
        parameters = [
            name
            for name in _inspect.signature(ModelCatalogQueryService.__init__).parameters
            if name != "self"
        ]

        self.assertEqual(parameters, ["discovery_provider"])

    def test_service_does_not_construct_any_provider(self):
        service, _ = _service(candidates=())

        service.query("x")

        self.assertIsInstance(service.discovery_provider, _RecordingDiscovery)

    def test_service_module_imports_no_concrete_provider_or_forbidden_module(self):
        text = SERVICE_MODULE.read_text(encoding="utf-8")

        for forbidden in (
            "huggingface_discovery",
            "HuggingFaceDiscoveryProvider",
            "from .main",
            "from .api",
            "model_identity",
            "model_store",
            "acquisition_service",
        ):
            self.assertNotIn(forbidden, text)


class IsolationTests(unittest.TestCase):
    def test_service_does_not_depend_on_the_acquisition_service(self):
        service, _ = _service(candidates=(candidate(),))

        outcome = service.query("x")

        self.assertNotIn("Acquisition", type(outcome).__name__)
        self.assertFalse(hasattr(service, "acquisition"))

    def test_query_boundary_never_calls_inspect(self):
        service, discovery = _service(candidates=(candidate(),))

        service.query("x")

        # The fake's inspect() raises AssertionError; reaching this assertion
        # proves only search() was used.
        self.assertEqual(len(discovery.calls), 1)

    def test_acquisition_service_still_uses_inspect_and_not_search(self):
        from castlearq.acquisition_service import ModelAcquisitionService

        source = _inspect.getsource(ModelAcquisitionService)

        self.assertIn(".inspect(", source)
        self.assertNotIn(".search(", source)


class NoProductSemanticsTests(unittest.TestCase):
    """The boundary exposes discovery capability; it must not become a product
    surface nor add ranking or caching semantics."""

    def test_module_contains_no_ranking_or_caching_logic(self):
        # Executable code only: docstrings and comments legitimately name the
        # prohibited concepts in order to exclude them.
        code = _executable_source(SERVICE_MODULE)

        for forbidden in (
            "sorted(",
            ".sort(",
            "rank",
            "recommend",
            "fuzzy",
            "lru_cache",
            "dedup",
            "cache",
        ):
            self.assertNotIn(forbidden, code)

    def test_no_state_is_retained_between_queries(self):
        service, _ = _service(candidates=(candidate(),))

        first = service.query("x")
        second = service.query("x")

        self.assertIsNot(first, second)
        self.assertEqual(first, second)


class CompositionTests(unittest.TestCase):
    def test_compose_returns_the_application_service(self):
        from castlearq.application_wiring import compose_catalog_query_service

        service = compose_catalog_query_service(
            discovery_provider=_RecordingDiscovery()
        )

        self.assertIsInstance(service, ModelCatalogQueryService)

    def test_compose_binds_the_exact_injected_provider(self):
        from castlearq.application_wiring import compose_catalog_query_service

        discovery = _RecordingDiscovery(candidates=(candidate(),))

        service = compose_catalog_query_service(discovery_provider=discovery)

        self.assertIs(service.discovery_provider, discovery)

    def test_compose_default_provider_is_the_hugging_face_discovery_provider(self):
        from castlearq.application_wiring import compose_catalog_query_service
        from castlearq.sources.huggingface_discovery import (
            HuggingFaceDiscoveryProvider,
        )

        service = compose_catalog_query_service()

        self.assertIsInstance(
            service.discovery_provider, HuggingFaceDiscoveryProvider
        )

    def test_composed_service_queries_through_its_provider(self):
        from castlearq.application_wiring import compose_catalog_query_service

        discovery = _RecordingDiscovery(
            candidates=(candidate(),), next_cursor="cursor-1"
        )

        outcome = compose_catalog_query_service(
            discovery_provider=discovery
        ).query("llama")

        self.assertEqual(len(outcome.candidates), 1)
        self.assertEqual(outcome.next_cursor, "cursor-1")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
