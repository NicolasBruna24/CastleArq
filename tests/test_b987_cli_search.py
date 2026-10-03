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

"""B9.87: the CLI ``search`` command, first production caller of B9.86.

Every collaborator here is a local fake. No test performs a network call and no
test constructs a production discovery provider: the command's dependency on the
provider is proven structurally, not by running one.
"""

import ast
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from castlearq import main as cli
from castlearq.catalog_query_service import (
    CatalogQueryError,
    CatalogQueryErrorCategory,
    CatalogQueryOutcome,
)
from castlearq.discovery import ModelCandidate

MAIN_PY = Path("castlearq/main.py")

QUERY = "qwen coder"
CURSOR = "eyJwYWdlIjoyfQ=="  # opaque by contract; never decoded by the CLI


def candidate(repository: str = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF") -> ModelCandidate:
    return ModelCandidate(
        provider_id="huggingface",
        repository=repository,
        display_name="Qwen2.5 Coder 7B Instruct",
        author="Qwen",
        description="A GGUF repository.",
        tags=("gguf", "code"),
        declared_architecture="qwen2",
        has_gguf=True,
    )


class RecordingQueryService:
    """A stand-in for ``ModelCatalogQueryService`` that records its calls."""

    def __init__(self, outcome=None, error=None):
        self.outcome = outcome
        self.error = error
        self.calls = []

    def query(self, query, *, limit=20, cursor=None):
        self.calls.append({"query": query, "limit": limit, "cursor": cursor})
        if self.error is not None:
            raise self.error
        return self.outcome


def run_search(*argv):
    """Run the real CLI dispatch for ``search`` and capture its streams."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["castlearq", "search", *argv]):
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main()
    return code, out.getvalue(), err.getvalue()


def outcome(candidates=(), next_cursor=None):
    return CatalogQueryOutcome(candidates=tuple(candidates), next_cursor=next_cursor)


class HappyPathTests(unittest.TestCase):
    def test_query_reaches_the_application_boundary_and_candidates_are_presented(self):
        service = RecordingQueryService(outcome([candidate()]))
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, err = run_search(QUERY)

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(service.calls[0]["query"], QUERY)
        self.assertIn("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", out)
        self.assertIn("Qwen2.5 Coder 7B Instruct", out)
        self.assertIn("Qwen", out)
        self.assertIn("qwen2", out)
        self.assertIn("gguf, code", out)
        self.assertIn("Next cursor: none", out)

    def test_limit_is_forwarded_only_when_supplied(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            run_search(QUERY)
            run_search(QUERY, "--limit", "7")

        # Omitted: the boundary's own default applies, not None and not a
        # CLI-invented value.
        self.assertEqual(service.calls[0]["limit"], 20)
        self.assertEqual(service.calls[1]["limit"], 7)

    def test_candidate_order_is_the_boundary_order(self):
        service = RecordingQueryService(
            outcome([candidate("org/first"), candidate("org/second")])
        )
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY)

        self.assertEqual(code, 0)
        self.assertLess(out.index("org/first"), out.index("org/second"))

class CursorTests(unittest.TestCase):
    def test_next_cursor_is_exposed_unchanged(self):
        service = RecordingQueryService(outcome([candidate()], next_cursor=CURSOR))
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY)

        self.assertEqual(code, 0)
        self.assertIn(f"Next cursor: {CURSOR}", out)

    def test_cursor_argument_is_forwarded_verbatim(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            run_search(QUERY, "--cursor", CURSOR)

        self.assertEqual(service.calls[0]["cursor"], CURSOR)

    def test_json_output_exposes_the_cursor_as_an_opaque_value(self):
        service = RecordingQueryService(outcome([candidate()], next_cursor=CURSOR))
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY, "--json")

        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(document["command"], "search")
        self.assertEqual(document["payload"]["next_cursor"], CURSOR)
        self.assertIsNone(document["error"])


class EmptyResultTests(unittest.TestCase):
    def test_empty_result_is_a_completed_query(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY)

        self.assertEqual(code, 0)
        self.assertIn("No candidates found.", out)

    def test_empty_json_result_is_not_an_error(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY, "--json")

        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(document["payload"]["candidates"], [])
        self.assertIsNone(document["payload"]["next_cursor"])
        self.assertIsNone(document["error"])


class ErrorPathTests(unittest.TestCase):
    @staticmethod
    def _error(category):
        return CatalogQueryError(category, "the provider refused the request")

    def test_discovery_failure_exits_one_with_context_preserved(self):
        service = RecordingQueryService(
            error=self._error(CatalogQueryErrorCategory.DISCOVERY_FAILED)
        )
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, err = run_search(QUERY)

        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Search error:", err)
        self.assertIn("the provider refused the request", err)

    def test_invalid_cursor_is_reported_under_its_own_category(self):
        service = RecordingQueryService(
            error=self._error(CatalogQueryErrorCategory.INVALID_CURSOR)
        )
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, _, err = run_search(QUERY, "--cursor", CURSOR)

        self.assertEqual(code, 1)
        self.assertIn("the provider refused the request", err)

    def test_json_error_uses_the_category_as_the_error_kind(self):
        service = RecordingQueryService(
            error=self._error(CatalogQueryErrorCategory.INVALID_CURSOR)
        )
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, _ = run_search(QUERY, "--json")

        document = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(document["error"]["kind"], "search_invalid_cursor")
        self.assertEqual(
            document["error"]["message"], "the provider refused the request"
        )
        self.assertEqual(document["payload"], {"query": QUERY})

    def test_missing_query_is_a_usage_error(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            code, out, err = run_search()

        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("Usage: castlearq search <query>", err)
        self.assertEqual(service.calls, [])

def _literal_assignment(name):
    """Read a module-level literal tuple out of ``castlearq/main.py``."""
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    return None


class DependencyBoundaryTests(unittest.TestCase):
    """The CLI reaches the provider only through the application boundary."""

    def test_cli_never_names_the_concrete_discovery_provider(self):
        source = MAIN_PY.read_text(encoding="utf-8")
        self.assertNotIn(
            "HuggingFaceDiscoveryProvider",
            source,
            "castlearq/main.py must not name the concrete discovery provider",
        )

    def test_search_command_calls_only_the_catalog_query_composition(self):
        tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("search_command", functions)
        names = {
            child.id
            for child in ast.walk(functions["search_command"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("compose_catalog_query_service", names)
        self.assertNotIn("compose_acquisition_service", names)
        self.assertNotIn("HuggingFaceSource", names)

    def test_default_service_comes_from_the_composition_root(self):
        service = RecordingQueryService(outcome())
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ) as compose:
            code, _, _ = run_search(QUERY)

        compose.assert_called_once_with()
        self.assertEqual(code, 0)

    def test_search_is_not_a_model_store_command(self):
        store_commands = _literal_assignment("store_commands")
        self.assertIsNotNone(store_commands)
        self.assertNotIn("search", store_commands)


class PublicSurfaceTests(unittest.TestCase):
    def test_help_documents_the_search_command(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit):
            with mock.patch.object(sys, "argv", ["castlearq", "--help"]):
                with redirect_stdout(out):
                    cli.main()
        self.assertIn("search <query>", out.getvalue())

    def test_search_is_in_the_json_surface(self):
        self.assertIn("search", cli._JSON_COMMANDS)

    def test_search_is_a_valid_command_choice(self):
        source = MAIN_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        choices = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(
                node.func, "attr", None
            ) == "add_argument":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if node.args[0].value == "command":
                        for keyword in node.keywords:
                            if keyword.arg == "choices":
                                choices = set(ast.literal_eval(keyword.value))
        self.assertIn("search", choices)

    def test_limit_and_cursor_are_rejected_for_other_commands(self):
        for argv in (
            ["models", "--limit", "5"],
            ["list", "--cursor", CURSOR],
            ["source", "huggingface", "org/repo", "--limit", "5"],
        ):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with self.assertRaises(SystemExit):
                    with mock.patch.object(sys, "argv", ["castlearq", *argv]):
                        with redirect_stderr(err):
                            cli.main()
                self.assertIn("is not valid for command", err.getvalue())

    def test_search_rejects_a_second_positional_value(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit):
            with mock.patch.object(
                sys, "argv", ["castlearq", "search", QUERY, "extra"]
            ):
                with redirect_stderr(err):
                    cli.main()
        self.assertIn("search accepts exactly one query", err.getvalue())


class ProductBoundaryTests(unittest.TestCase):
    """B9.87 is a pass-through adapter, not a second discovery domain."""

    def test_search_adds_no_field_beyond_the_discovery_domain(self):
        service = RecordingQueryService(outcome([candidate()]))
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            _, out, _ = run_search(QUERY, "--json")

        payload = json.loads(out)["payload"]
        self.assertEqual(set(payload), {"query", "candidates", "next_cursor"})
        self.assertEqual(
            set(payload["candidates"][0]),
            {
                "provider_id",
                "repository",
                "display_name",
                "author",
                "description",
                "tags",
                "declared_architecture",
                "has_gguf",
            },
        )

    def test_search_never_reorders_or_deduplicates(self):
        repeated = [candidate("org/b"), candidate("org/a"), candidate("org/b")]
        service = RecordingQueryService(outcome(repeated))
        with mock.patch.object(
            cli, "compose_catalog_query_service", return_value=service
        ):
            _, out, _ = run_search(QUERY, "--json")

        repositories = [
            entry["repository"]
            for entry in json.loads(out)["payload"]["candidates"]
        ]
        self.assertEqual(repositories, ["org/b", "org/a", "org/b"])