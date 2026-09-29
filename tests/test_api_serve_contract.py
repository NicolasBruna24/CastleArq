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

"""B9.50 public-surface contract tests, updated by B9.51 and B9.52.

B9.50 existed because B9.48 wrote ``serve read-only HTTP API`` into ``--help``
and the README while ``POST /v1/run`` performs real inference. B9.50 also
declared the serve/execute divergence a *deliberate policy*; B9.51 reversed
that (OPTION A: HTTP shares strict admission) and deferred the implementation.
B9.52 implemented it, so the divergence is now closed in code, in the
documentation and in the tests.

The suite therefore pins four things that must agree:

    CODE  <->  POLICY  <->  DOCUMENTATION  <->  RATIFIED CONTRACT

* :class:`ReadmeCommandReferenceTests` -- every command documented in the
  README exists in the CLI (and vice versa), without line numbers.
* :class:`ServeIsNotReadOnlyTests` -- behavioural proof that ``serve``
  executes models, not a restatement of the README.
* :class:`ExecutionGatePolicyTests` -- the ratified policy (strict admission on
  HTTP) AND that the implementation actually reaches the gate. Both drift
  directions fail: removing the gate trips the name scan, reverting the flag
  trips the flag assertion.
* :class:`HttpAdmissionContractTests` -- the ratified HTTP contract itself
  (status mapping, rejection body, ``run_lock`` ordering), pinned against the
  decision document so the implementation cannot diverge from it silently.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from app.main import main

README = Path("README.md")
MAIN_PY = Path("app/main.py")
API_PY = Path("app/api.py")
DECISION_DOC = Path(
    "docs/B9.51-http-admission-contract-decision.md"
)

#: The B9.51 ratified policy: HTTP execution DOES share strict admission.
#: B9.50 set this to ``False`` and called the divergence deliberate; B9.51
#: reversed that judgement. The implementation still has the gap (see
#: :data:`HTTP_ADMISSION_IMPLEMENTED`), which is a deferred implementation,
#: not a second policy.
SERVE_USES_STRICT_ADMISSION = True

#: B9.51 ratified the contract and deferred the implementation to B9.52.
#: B9.52 implemented it, so the gap is closed. The flag stays as the explicit
#: switch between "policy only" and "policy + code": the gap assertions below
#: are written so that flipping either this or the code without the other
#: fails the suite, which is what makes the closure auditable.
HTTP_ADMISSION_IMPLEMENTED = True


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _relative_imports(path: Path) -> set[str]:
    """Package-relative modules imported by ``path``.

    Relative imports are resolved against the module's own package, so
    ``from .api import X`` inside ``app/execute_model.py`` is reported as
    ``app.api``. Absolute imports are reported verbatim. Only real import
    statements are considered: names appearing in docstrings, comments or
    string literals are deliberately ignored, because a module is allowed to
    *describe* another module without depending on it.
    """
    return {module for module, _ in _relative_import_names(path)}


def _package_parts(path: Path) -> tuple[str, ...]:
    """The dotted package the module lives in, derived from its path.

    ``app/downloads/downloader.py`` belongs to package ``app.downloads``;
    ``app/execute_compatibility.py`` belongs to ``app``. The file name is
    dropped, because a module is a member of its package, not the package.
    """
    return tuple(path.parent.parts)


def _resolve_relative(base: str, level: int, package: tuple[str, ...]) -> str:
    """Resolve a relative ``from ... import ...`` target.

    ``level`` counts the leading dots: ``level == 1`` is the module's own
    package, ``level == 2`` its parent, and so on. Truncating the package parts
    from the right is what makes ``from ..model_store import X`` inside
    ``app/downloads/`` resolve to ``app.model_store`` rather than to a name
    built from the leaf directory alone. A level that would walk past the
    package root is clamped to the root, because that is the only anchor
    available from the file path alone.
    """
    keep = max(len(package) - (level - 1), 0)
    prefix = ".".join(package[:keep])
    if not base:
        return prefix
    return f"{prefix}.{base}" if prefix else base


def _relative_import_names(path: Path) -> set[tuple[str, str]]:
    """``(module, imported_name)`` pairs for every import in ``path``.

    Relative imports are resolved against the importing module's package, so
    ``from .api import X`` inside ``app/execute_model.py`` is reported as
    ``app.api`` and ``from ..model_store import Y`` inside
    ``app/downloads/downloader.py`` is reported as ``app.model_store``.
    Absolute imports are reported verbatim.

    Only real import statements are considered: names appearing in docstrings,
    comments or string literals are deliberately ignored, because a module is
    allowed to *describe* another module without depending on it.

    The imported symbol is kept alongside the module, because the ratified
    entry points are identified by what ``app/api.py`` binds and from where,
    not merely by whether a name is spelled somewhere in the file.
    """
    tree = ast.parse(_read(path))
    package = _package_parts(path)
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pairs.add((alias.name, alias.asname or alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            resolved = _resolve_relative(base, node.level, package) if node.level else base
            for alias in node.names:
                pairs.add((resolved, alias.asname or alias.name))
    return pairs


def _http_transport_modules() -> frozenset[str]:
    """Standard-library modules that carry the HTTP request/response boundary.

    This set exists for one contract sentence. B9.51 §5.5 closes with "The
    only new code permitted is transport-level: ordering, lock scope, and the
    two response projections", so *transport* here means the HTTP
    request/response layer and nothing else.

    Each member is included because it is that layer:

    * ``http`` / ``http.server`` -- the HTTP protocol and the server the
      ``serve`` command starts;
    * ``socketserver`` -- the accept/serve loop the handler runs on;
    * ``socket`` -- the raw connection primitive underneath it.

    Two categories are deliberately **excluded**, because they are not the
    request/response boundary and conflating them would forbid legitimate work:

    * ``threading`` / ``asyncio`` -- concurrency. B9.51 §5.5 *permits* lock
      scope as transport-level new code, so treating concurrency as the
      transport would contradict the contract it is meant to encode.
    * ``urllib`` / ``urllib.request`` -- outbound URL access. Fetching a model
      over the network is the downloader's purpose, so forbidding it in the
      infrastructure layer would forbid the product.

    Network egress is therefore constrained by layering (nothing below the
    transport may import the HTTP surface), not by a flat module blacklist.
    """
    return frozenset(
        {
            "http",
            "http.server",
            "socketserver",
            "socket",
        }
    )


def _forbidden_upward_modules() -> tuple[str, ...]:
    """Modules the transport owns; nothing below it may import them.

    Kept separate from :func:`_http_transport_modules` on purpose. The first
    names the stdlib boundary, the second names the application boundary, and
    the layering rule holds in both directions of ownership without depending
    on which stdlib module happens to implement the transport.
    """
    return ("app.api", "app.main")


def _cli_choices() -> set[str]:
    """The command names the CLI actually accepts."""
    tree = ast.parse(_read(MAIN_PY))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "command"
        ):
            for keyword in node.keywords:
                if keyword.arg == "choices" and isinstance(
                    keyword.value, ast.Tuple
                ):
                    return {
                        element.value
                        for element in keyword.value.elts
                        if isinstance(element, ast.Constant)
                    }
    raise AssertionError("command choices tuple not found in app/main.py")


def _readme_commands() -> set[str]:
    """Command names documented in the README command-reference table.

    Parsed from the markdown table itself, so the test tracks the document
    instead of pinning line numbers.
    """
    text = _read(README)
    match = re.search(
        r"^##\s+Command reference\s*$(.*?)^##\s",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "README command reference section not found"
    section = match.group(1)
    names = set()
    for line in section.splitlines():
        # Rows look like:  | `command ARG` | description |
        # The command is the first token inside the first backticked span.
        row = re.match(r"^\|\s*`([a-z][a-z0-9]*)", line)
        if row:
            names.add(row.group(1))
    return names


def _help_text() -> str:
    """Render ``castlearq --help`` exactly as a user would see it."""
    import contextlib

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        with patch.object(sys, "argv", ["castlearq", "--help"]):
            with contextlib.suppress(SystemExit):
                main()
    return stdout.getvalue()


class ReadmeCommandReferenceTests(unittest.TestCase):
    """B9.50 section 7: README and CLI must not drift apart."""

    def test_every_documented_command_exists_in_the_cli(self):
        documented = _readme_commands()
        self.assertTrue(documented, "no commands parsed from the README table")
        missing = documented - _cli_choices()
        self.assertEqual(
            missing,
            set(),
            f"README documents commands the CLI does not accept: {sorted(missing)}",
        )

    def test_every_cli_command_is_documented(self):
        undocumented = _cli_choices() - _readme_commands()
        self.assertEqual(
            undocumented,
            set(),
            f"CLI accepts commands the README does not document: {sorted(undocumented)}",
        )

    def test_readme_table_is_not_empty_and_covers_the_surface(self):
        self.assertGreaterEqual(len(_readme_commands()), len(_cli_choices()))


class ServeIsNotReadOnlyTests(unittest.TestCase):
    """B9.50 section 8: behavioural proof, not a restatement of the README."""

    def test_serve_rejects_non_loopback_hosts(self):
        """Network exposure property: loopback only, enforced at construction."""
        from app.api import APIConfigurationError, serve

        with self.assertRaises(APIConfigurationError):
            serve(host="0.0.0.0", port=0)

    def test_run_handler_calls_the_execute_use_case(self):
        """``_handle_run`` must route to the gated execution use case."""
        source = _read(API_PY)
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("_handle_run", functions)
        names = {
            child.id
            for child in ast.walk(functions["_handle_run"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("execute_model", names)
        # And it must consult the gate before doing so. The gate is reached
        # through ``self``, so look for the attribute as well as a bare name.
        self.assertTrue(
            "_admit_or_respond" in names
            or "_admit_or_respond" in {
                child.attr for child in ast.walk(functions["_handle_run"])
                if isinstance(child, ast.Attribute)
            },
            "_handle_run does not consult the admission gate",
        )

    def test_api_module_does_not_expose_a_status_only_surface(self):
        """POST routes exist: the API is not read-only."""
        source = _read(API_PY)
        self.assertIn("do_POST", source)
        self.assertIn('path == "/v1/run"', source)

    def test_documentation_does_not_claim_serve_is_read_only(self):
        readme = _read(README)
        self.assertNotIn("API HTTP de solo lectura", readme)
        help_text = _help_text()
        self.assertNotIn("serve   read-only HTTP API", help_text)


class ExecutionGatePolicyTests(unittest.TestCase):
    """B9.51 §4: pin the ratified policy AND the labelled implementation gap.

    Ratified policy: ``serve`` execution DOES cross the strict admission gate,
    exactly like ``execute``. The implementation has not caught up yet; B9.51
    deferred it to B9.52. Both facts are asserted here so neither can drift
    alone: the policy cannot be quietly reverted to "deliberate legacy", and
    the gap cannot quietly become permanent.
    """

    def test_ratified_policy_is_strict_admission_on_http(self):
        self.assertTrue(
            SERVE_USES_STRICT_ADMISSION,
            "B9.51 ratified that HTTP execution shares strict admission. "
            "Reverting this requires a new ratified decision, not a code "
            "change; B9.50's Option B rationale was rejected on merit.",
        )

    def test_implementation_gap_is_closed_and_the_gate_is_reachable(self):
        """B9.52: the HTTP path now crosses the ratified gate.

        Inverted from the B9.51 version of this test, which asserted the
        absence of the gate. Both directions now fail loudly: if the code ever
        stops consulting the gate, the banned-name scan below trips; if the flag
        is flipped back while the code is still gated, the flag assertion
        trips.
        """
        self.assertTrue(
            HTTP_ADMISSION_IMPLEMENTED,
            "HTTP admission is implemented in app/api.py. The flag must not be "
            "reverted while the gate is reachable: the policy in B9.51 is "
            "OPTION A, so an ungated HTTP path is a defect, not a state.",
        )
        source = _read(API_PY)
        for required in (
            "evaluate_model_compatibility",
            "to_admission",
            "execute_model",
        ):
            self.assertIn(
                required,
                source,
                f"app/api.py no longer references {required}: HTTP execution "
                "stopped crossing the ratified admission gate",
            )

    def test_http_no_longer_uses_the_legacy_run_pipeline(self):
        """The ungated legacy path must not remain as an HTTP fallback.

        Checked on the CODE, not on the whole file: the module docstrings
        legitimately mention ``run_once`` to explain what ``/v1/run`` stopped
        calling. What must be absent is an actual reference to the legacy
        entry points.
        """
        tree = ast.parse(_read(API_PY))
        imported, called = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        for legacy in ("run_once", "RunOutcome", "run_dependencies"):
            self.assertNotIn(legacy, imported, f"app/api.py imports {legacy}")
            self.assertNotIn(legacy, called, f"app/api.py calls {legacy}")

    def test_documentation_no_longer_describes_a_transitional_gap(self):
        """The gap label is gone now that the gate is implemented."""
        readme = _read(README)
        self.assertNotIn("brecha conocida y transitoria", readme)
        self.assertNotIn("B9.52 requerido", readme)
        help_text = _help_text()
        self.assertNotIn("Known transitional gap", help_text)
        self.assertNotIn("does NOT apply that admission", help_text)

    def test_documentation_states_the_ratified_policy(self):
        readme = _read(README)
        # Compare on whitespace-normalised text: the README is hard-wrapped,
        # so a phrase can straddle a newline. B9.54 moved the public surface
        # to English (B9.53 section 10).
        flat = " ".join(readme.split())
        self.assertIn("same strict evaluation admission", flat)
        self.assertIn("403", readme)
        help_text = _help_text()
        self.assertIn("strict evaluation admission as execute", help_text)

    def test_execute_does_apply_strict_evaluation(self):
        """The contrast that makes the divergence meaningful."""
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        names = {
            child.id
            for child in ast.walk(functions["execute_command"])
            if isinstance(child, ast.Name)
        }
        self.assertIn("evaluate_model_compatibility", names)
        self.assertIn("to_admission", names)

    def test_documentation_states_the_implemented_policy_in_both_languages(self):
        """README and --help must both describe the gate as active.

        B9.54 moved the public surface to English, so the assertion follows.
        """
        readme = _read(README)
        self.assertIn("admission", readme)
        self.assertIn("serve", readme)
        help_text = _help_text()
        self.assertIn("same strict evaluation admission as execute", help_text)

    def test_documentation_separates_network_from_execution_policy(self):
        """B9.50 section 4: the two properties must not be conflated.

        B9.54 translated the README to the canonical English surface, so the
        marker is now the English phrase; the property under test is unchanged.
        """
        readme = _read(README)
        self.assertIn("network exposure", readme)
        self.assertIn("**Execution policy**", readme)

    #: B9.50 §3 and B9.51 §9: the decision blocks were scoped to the public
    #: surface. That scope is a dependency-direction property, and it is
    #: asserted on the code rather than on repository history: the evaluation
    #: core must not depend on the HTTP transport, and the transport must be
    #: the only layer that owns it.
    EVALUATION_CORE_MODULES = (
        "app/evaluate_compatibility.py",
        "app/evaluation_policy.py",
        "app/evaluation_pipeline.py",
        "app/compatibility_domain.py",
        "app/initial_knowledge.py",
    )

    def test_evaluation_core_does_not_depend_on_the_transport_layer(self):
        """The evaluation core must stay independent of the HTTP surface.

        B9.50 must not have modified the evaluation engine, and B9.51 §9
        required the decision block not to redesign it. Those are statements
        about committed history and cannot be re-verified from the current
        tree. What survives them, and is the property that still has force,
        is the dependency direction: the evaluation core is reached *by* the
        transport, it never reaches *out* to it. A later block that made the
        engine depend on ``http`` or on ``app.api`` would invert the layering
        this suite exists to protect, and this test fails on that change.

        Concurrency is deliberately not forbidden here: ``threading`` is not
        part of the HTTP boundary (see :func:`_http_transport_modules`), and an
        evaluation module that takes a lock is not violating this contract.
        """
        transport = _http_transport_modules()
        upward = _forbidden_upward_modules()
        for module in self.EVALUATION_CORE_MODULES:
            imports = _relative_imports(Path(module))
            leaked = sorted(
                name
                for name in imports
                if name in transport or name.startswith(upward)
            )
            self.assertEqual(
                leaked,
                [],
                f"{module} must not depend on the HTTP transport layer; "
                f"the HTTP surface adapts the evaluation core, not the "
                f"other way round",
            )

    def test_model_store_is_independent_of_the_transport_layer(self):
        """The store is an infrastructure port; it owns no HTTP transport.

        B9.50 also scoped itself away from the model store and the downloader.
        The durable property behind that scoping is that the store is reached
        by the download and evaluation layers but never reaches into the HTTP
        surface. This is asserted on the current imports, so it holds
        regardless of how clean the working tree happens to be when the suite
        runs.

        The two modules are held to different rules on purpose. The store is a
        local filesystem port: it must import no HTTP transport at all. The
        downloader performs network I/O by design -- it fetches model files --
        so it is held only to the layering rule. Forbidding ``urllib.request``
        there would forbid the product, not protect the architecture.
        """
        transport = _http_transport_modules()
        upward = _forbidden_upward_modules()
        store = _relative_imports(Path("app/model_store.py"))
        self.assertEqual(
            sorted(
                name
                for name in store
                if name in transport or name.startswith(upward)
            ),
            [],
            "app/model_store.py must not depend on the HTTP transport; it is a "
            "local filesystem port used by the evaluation and download layers",
        )
        downloader = _relative_imports(Path("app/downloads/downloader.py"))
        self.assertEqual(
            sorted(
                name
                for name in downloader
                if name.startswith(upward)
            ),
            [],
            "app/downloads/downloader.py must not depend on the HTTP surface; "
            "the download surface is adapted by the API, not the reverse. Its "
            "outbound network I/O is its purpose and is not constrained here.",
        )


class HttpAdmissionContractTests(unittest.TestCase):
    """B9.51 §5/§8: the ratified contract itself must exist and be complete.

    B9.51 ratified the contract without implementing it. That is only safe if
    the contract is pinned: the mapping, the rejection body and the lock
    ordering have to be present and unambiguous, and B9.52 has to be able to
    detect that it implemented something else.
    """

    def test_decision_document_exists(self):
        self.assertTrue(
            DECISION_DOC.exists(),
            f"the ratified HTTP admission contract is missing: {DECISION_DOC}",
        )

    def test_decision_is_option_a_not_a_hedge(self):
        text = _read(DECISION_DOC)
        self.assertIn("Decision: OPTION A — HTTP uses strict admission.", text)
        for hedge in ("probably A", "probably OPTION A", "maybe A"):
            self.assertNotIn(hedge, text)

    def test_status_mapping_is_complete(self):
        """Every ratified case carries an explicit status code."""
        text = _read(DECISION_DOC)
        self.assertIn("### 5.2 Status mapping (ratified, complete)", text)
        for token in ("**400**", "**404**", "**409**", "**403**", "**422**",
                      "**500**", "**503**", "**200**"):
            self.assertIn(token, text, f"status mapping lacks {token}")

    def test_denial_and_evaluation_error_are_distinguished(self):
        """B9.48 P0-2 must survive the projection: an error is not a denial."""
        text = _read(DECISION_DOC)
        self.assertIn("500 for an evaluation error, not 403", text)
        self.assertIn("403 for denial, not 422", text)

    def test_rejection_body_exposes_only_the_admission_summary(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.3 Rejection body (ratified)", text)
        self.assertIn("only** what `EvaluationAdmission` already carries", text)
        for leaked in ("checks", "evidence", "traceback"):
            self.assertIn(leaked, text)
        self.assertIn("not** exposed over HTTP", text)

    def test_run_lock_semantics_are_ratified(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.4 `run_lock` (ratified)", text)
        for token in ("**before** evaluation", "**409**", "released in `finally`"):
            self.assertIn(token, text)

    def test_reuse_constraint_forbids_a_second_admission_implementation(self):
        text = _read(DECISION_DOC)
        self.assertIn("### 5.5 Reuse", text)
        for banned in (
            "HttpEvaluationService",
            "HttpAdmissionManager",
            "ApiExecutionManager",
            "ExecutionPolicyV2",
            "ServePolicyEngine",
            "CompatibilityManager",
        ):
            self.assertIn(banned, text, f"reuse constraint omits {banned}")

    def test_backward_compatibility_is_documented_not_silent(self):
        text = _read(DECISION_DOC)
        self.assertIn("## 6. Backward Compatibility", text)
        self.assertIn("RunResponseDTO", text)
        self.assertIn("`GET /health`", text)

    def test_implementation_status_is_recorded(self):
        """B9.52 completed the deferral; the record must say so explicitly."""
        text = _read(DECISION_DOC)
        self.assertIn("DECISION RATIFIED", text)
        self.assertIn("COMPLETED IN B9.52", text)

    ADMISSION_CORE_MODULES = (
        "app/evaluate_compatibility.py",
        "app/evaluation_policy.py",
        "app/evaluation_pipeline.py",
        "app/compatibility_domain.py",
        "app/initial_knowledge.py",
        "app/execute_model.py",
        "app/run_service.py",
    )

    def test_admission_core_does_not_depend_on_the_transport_layer(self):
        """B9.51 §9, restated as a property that still has force.

        The decision block had to be implementable without redesigning the
        engine, and the implementation had to be able to detect if it had
        done so. Both halves are still checkable from the current tree, and
        this is the second one: the modules the HTTP gate consults must not
        have acquired a dependency on the transport, the run lock, or the
        request handler. If a future block made ``execute_model`` import
        ``app.api`` -- for instance to read a request flag -- the layering
        this suite pins would invert, and this test fails.
        """
        transport = _http_transport_modules()
        upward = _forbidden_upward_modules()
        for module in self.ADMISSION_CORE_MODULES:
            imports = _relative_imports(Path(module))
            leaked = sorted(
                name
                for name in imports
                if name in transport or name.startswith(upward)
            )
            self.assertEqual(
                leaked,
                [],
                f"{module} must not depend on the HTTP transport layer; the "
                f"HTTP gate is applied to the admission core, never the reverse",
            )

    def test_admission_is_consulted_through_the_ratified_entry_point(self):
        """B9.51 §5.5: the API must reuse the ratified admission symbols.

        §5.5 is a *reuse* constraint, and reuse is not the same as name
        presence. A local ``def to_admission(...)`` inside ``app/api.py`` would
        spell the right name and violate the contract outright, so this test
        distinguishes the two explicitly:

        * each of the four symbols §5.5 names must be **imported** by
          ``app/api.py`` from the module that owns it -- ``app.evaluate_compatibility``
          for the evaluation and admission conversion, ``app.execute_model`` for
          the use case and its admission type;
        * and none of them may be **defined** in ``app/api.py`` itself.

        All four symbols are checked because §5.5 names all four. Where one is
        reached indirectly rather than by a direct import, that would be a real
        change to how the API consumes admission and would need the contract
        revisited -- so requiring the import is the faithful reading, not an
        invented obligation.

        The "no equivalent second admission implementation" clause is enforced
        at its minimum honest strength: the six concrete names §5.5 enumerates,
        plus the check above, which is what makes an arbitrary re-implementation
        under a different name detectable. A universal clone detector is not
        attempted; that would be disproportionate to the contract.
        """
        tree = ast.parse(_read(API_PY))
        defined: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                defined.update(
                    target.id for target in node.targets
                    if isinstance(target, ast.Name)
                )
        imports = _relative_import_names(Path(API_PY))
        owners = {
            "evaluate_model_compatibility": "app.evaluate_compatibility",
            "to_admission": "app.evaluate_compatibility",
            "EvaluationAdmission": "app.execute_model",
            "execute_model": "app.execute_model",
        }
        for symbol, owner in owners.items():
            self.assertIn(
                (owner, symbol),
                imports,
                f"app/api.py must import {symbol} from {owner}: B9.51 §5.5 "
                f"requires reusing the ratified implementation, and a local "
                f"definition would be a second admission implementation",
            )
            self.assertNotIn(
                symbol,
                defined,
                f"app/api.py defines {symbol} itself; it must reuse the "
                f"ratified one from {owner} instead of forking it",
            )
        for banned in (
            "HttpEvaluationService",
            "HttpAdmissionManager",
            "ApiExecutionManager",
            "ExecutionPolicyV2",
            "ServePolicyEngine",
            "CompatibilityManager",
        ):
            self.assertNotIn(
                banned,
                defined,
                f"app/api.py defines {banned}: a second admission "
                f"implementation would fork the ratified contract",
            )


class RunIsOutOfScopeTests(unittest.TestCase):
    """B9.51 §4: `run` keeps its ratified legacy policy (no cutover)."""

    def test_run_still_uses_the_legacy_path_without_evaluation(self):
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        names = {
            child.id
            for child in ast.walk(functions["run_model"])
            if isinstance(child, ast.Name)
        }
        self.assertNotIn("evaluate_model_compatibility", names)
        self.assertNotIn("execute_model", names)

    def test_run_is_not_an_alias_of_execute(self):
        tree = ast.parse(_read(MAIN_PY))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("run_model", functions)
        self.assertIn("execute_command", functions)
        run_names = {
            child.id
            for child in ast.walk(functions["run_model"])
            if isinstance(child, ast.Name)
        }
        self.assertNotIn("execute_command", run_names)


if __name__ == "__main__":
    unittest.main()


