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

"""Hermetic tests for B9.13 I1: Observation → Knowledge integration.

Covers the ratified B9.13 contract: mapped/unmapped/mixed/zero runtime
semantics, verbatim scope and identity pass-through from B9.12, verbatim
trace propagation, backend-evidence isolation, structural determinism,
mandatory registry, purity, and legacy/Evaluation isolation.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from app.boundary_adapter import MappingOutcome, translate
from app.compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)
from app.knowledge_bridge import KnowledgeProjection
from app.observation_domain import (
    CoverageEntry,
    CoverageState,
    EnvironmentContext,
    HardwareObservation,
    ObservationCoverage,
    ObservationFamily,
    ObservationState,
    ObservedValue,
    PlatformObservation,
    RuntimeObservation,
)
from app.observation_knowledge import (
    IntegrationResult,
    RuntimeIntegration,
    UnmappedRuntime,
    integrate,
)

OBSERVED = ObservationState.OBSERVED
UNAVAILABLE = ObservationState.UNAVAILABLE


def fact(state=OBSERVED, value=None, source="test", detail=None):
    if detail is None and state is not OBSERVED:
        detail = state.value
    return ObservedValue(state=state, value=value, source=source, detail=detail)


def runtime_observation(canonical_id):
    return RuntimeObservation(
        canonical_id=canonical_id,
        executable_path=fact(UNAVAILABLE),
        raw_version=fact(UNAVAILABLE),
        detected_backends=(),
        backends_outcome=None,
        coverage=ObservationCoverage(entries=(
            CoverageEntry(ObservationFamily.RUNTIME_DISCOVERY, CoverageState.OBSERVED),
        )),
    )


def environment(*runtimes):
    return EnvironmentContext(
        timestamp="2026-09-18T12:00:00Z",
        platform=PlatformObservation(
            os_family=fact(OBSERVED, "darwin"),
            os_release=fact(OBSERVED, "25.0.0"),
            architecture=fact(OBSERVED, "arm64"),
            distribution=fact(UNAVAILABLE),
        ),
        hardware=HardwareObservation(
            memory_total_bytes=fact(OBSERVED, 16 * 1024**3),
            devices=(),
            acquisition_error=None,
        ),
        runtimes=runtimes,
    )


def empty_registry():
    return KnowledgeRegistry(())


class SentinelRegistryTests(unittest.TestCase):
    """Contract checks via a registry that matches only the exact B9.12 output."""

    def _registry(self, canonical_id):
        assertion = KnowledgeAssertion(
            subject=KnowledgeSubject(
                kind=KnowledgeKind.RUNTIME, canonical_id=canonical_id
            ),
            predicate=KnowledgePredicate.SUPPORTS,
            object=KnowledgeSubject(
                kind=KnowledgeKind.BACKEND, canonical_id="cpu"
            ),
            state=KnowledgeState.SUPPORTED,
            scope=KnowledgeScope(),
        )
        return KnowledgeRegistry((assertion,))

    def test_project_knowledge_receives_b912_subject_and_scope_verbatim(self):
        # If the integrator rebuilt the identity or derived the scope,
        # this exact-scope row would not be projected (I-03, I-21, I-23).
        registry = self._registry("ollama")
        result = integrate(environment(runtime_observation("ollama")), registry)
        self.assertEqual(len(result.entries), 1)
        entry = result.entries[0]
        self.assertEqual(entry.observation_identity, "ollama")
        self.assertEqual(len(entry.knowledge.projected), 1)
        self.assertIn("cpu", entry.knowledge.runtime_knowledge.supported_backends)

    def test_aliases_are_never_used_as_lookup_identity(self):
        # An alias-named subject ("llamacpp") must not be resolved for the
        # mapped identity "llama.cpp" (I-05).
        assertion = KnowledgeAssertion(
            subject=KnowledgeSubject(
                kind=KnowledgeKind.RUNTIME, canonical_id="llamacpp"
            ),
            predicate=KnowledgePredicate.SUPPORTS,
            object=KnowledgeSubject(
                kind=KnowledgeKind.BACKEND, canonical_id="cpu"
            ),
            state=KnowledgeState.SUPPORTED,
            scope=KnowledgeScope(),
        )
        registry = KnowledgeRegistry((assertion,))
        result = integrate(environment(runtime_observation("llama.cpp")), registry)
        entry = result.entries[0]
        self.assertEqual(entry.knowledge.projected, ())
        self.assertEqual(entry.knowledge.runtime_knowledge.supported_backends, ())


class MappedRuntimeTests(unittest.TestCase):
    def test_mapped_runtime_produces_valid_knowledge_entry(self):
        result = integrate(
            environment(runtime_observation("llama.cpp")), empty_registry()
        )
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.unmapped, ())
        entry = result.entries[0]
        self.assertEqual(entry.observation_identity, "llama.cpp")
        self.assertIsInstance(entry.knowledge, KnowledgeProjection)
        self.assertEqual(
            entry.knowledge.runtime,
            KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp"),
        )
        self.assertEqual(entry.knowledge.scope, KnowledgeScope())
        self.assertEqual(entry.knowledge.projected, ())

    def test_empty_projection_is_propagated_not_error(self):
        result = integrate(environment(runtime_observation("ollama")), empty_registry())
        self.assertEqual(result.entries[0].knowledge.projected, ())


class UnmappedRuntimeTests(unittest.TestCase):
    def test_unmapped_runtime_becomes_data_entry_no_exception(self):
        result = integrate(
            environment(runtime_observation("llama.app")), empty_registry()
        )
        self.assertEqual(result.entries, ())
        self.assertEqual(len(result.unmapped), 1)
        item = result.unmapped[0]
        self.assertEqual(item.observation_identity, "llama.app")
        self.assertEqual(item.outcome, MappingOutcome.UNMAPPED)

    def test_unmapped_does_not_project_any_knowledge(self):
        result = integrate(
            environment(
                runtime_observation("llamacpp"), runtime_observation("ollama")
            ),
            empty_registry(),
        )
        self.assertEqual(
            [e.observation_identity for e in result.entries], ["ollama"]
        )
        self.assertEqual(
            [u.observation_identity for u in result.unmapped], ["llamacpp"]
        )

    def test_mapped_runtime_cannot_be_recorded_as_unmapped(self):
        with self.assertRaises(ValueError):
            UnmappedRuntime(
                observation_identity="ollama", outcome=MappingOutcome.MAPPED
            )


class MixedAndZeroRuntimeTests(unittest.TestCase):
    def test_mixed_runtimes_mapped_unmapped_mapped(self):
        result = integrate(
            environment(
                runtime_observation("llama.cpp"),
                runtime_observation("llama.app"),
                runtime_observation("ollama"),
            ),
            empty_registry(),
        )
        self.assertEqual(
            [e.observation_identity for e in result.entries],
            ["llama.cpp", "ollama"],
        )
        self.assertEqual(
            [u.observation_identity for u in result.unmapped], ["llama.app"]
        )
        self.assertEqual(
            len(result.entries) + len(result.unmapped), 3
        )

    def test_zero_runtimes(self):
        context = environment()
        result = integrate(context, empty_registry())
        self.assertEqual(result.entries, ())
        self.assertEqual(result.unmapped, ())
        self.assertEqual(result.trace, translate(context).trace)


class TraceAndDeterminismTests(unittest.TestCase):
    def test_trace_is_propagated_verbatim(self):
        context = environment(
            runtime_observation("llama.cpp"), runtime_observation("llama.app")
        )
        result = integrate(context, empty_registry())
        self.assertEqual(result.trace, translate(context).trace)
        # Nothing filtered: all runtime traces and context entries survive.
        self.assertEqual(len(result.trace.runtime_traces), 2)
        self.assertTrue(result.trace.context_entries)

    def test_determinism_structural_equality(self):
        context = environment(
            runtime_observation("llama.cpp"), runtime_observation("llama.app")
        )
        first = integrate(context, empty_registry())
        second = integrate(context, empty_registry())
        self.assertEqual(first, second)
        self.assertEqual(repr(first), repr(second))

    def test_result_is_frozen(self):
        result = integrate(environment(runtime_observation("ollama")), empty_registry())
        with self.assertRaises(FrozenInstanceError):
            result.entries = ()  # type: ignore[misc]

    def test_cardinality_invariant(self):
        context = environment(
            runtime_observation("llama.cpp"),
            runtime_observation("llama.app"),
        )
        result = integrate(context, empty_registry())
        self.assertEqual(
            len(result.entries) + len(result.unmapped), len(context.runtimes)
        )

    def test_no_backend_evidence_or_context_fields(self):
        result = integrate(environment(runtime_observation("ollama")), empty_registry())
        for forbidden in (
            "backend_evidence",
            "context",
            "registry",
            "environment",
        ):
            self.assertFalse(hasattr(result, forbidden), forbidden)
        for forbidden in ("compatible", "preferred", "selected", "score", "ranking"):
            self.assertFalse(hasattr(result, forbidden), forbidden)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            integrate("not a context", empty_registry())  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            integrate(environment(), "not a registry")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            integrate(environment(runtime_observation("ollama")), None)  # type: ignore[arg-type]


class PurityAndIsolationTests(unittest.TestCase):
    def _module_tree(self):
        source = (
            Path(__file__).resolve().parent.parent
            / "app" / "observation_knowledge.py"
        ).read_text(encoding="utf-8")
        return source, ast.parse(source)

    def test_no_legacy_evaluation_or_acquisition_imports(self):
        source, tree = self._module_tree()
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and not module:
                    continue
                imported.add(module)
        forbidden = {
            "app.platform", "app.hardware", "app.runtimes", "app.gpu_setup",
            "app.compatibility", "app.selection", "app.execution_service",
            "app.compatibility_evaluator", "app.evaluation_adapter",
            "app.evaluation_pipeline", "app.evaluation_policy",
            "app.execution", "app.runner", "app.main",
            "app.observation_probe",
            "subprocess", "os", "platform", "time", "random", "socket",
            "shutil",
        }
        self.assertFalse(imported & forbidden, sorted(imported & forbidden))

    def test_no_forbidden_attribute_calls(self):
        _, tree = self._module_tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr,
                    {"system", "popen", "run", "check_output", "getenv",
                     "time", "which", "read_text"},
                    node.func.attr,
                )

    def test_no_runtime_capability_or_resolve_runtime_usage(self):
        # Documentation may mention the forbidden route; the code must not
        # reference, import, or call it (checked on AST names, not text).
        _, tree = self._module_tree()
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
        for forbidden in (
            "resolve_runtime",
            "RuntimeCapability",
            "EvaluationContext",
            "build_evaluation_context",
            "evaluate_strict",
            "evaluate",
        ):
            self.assertNotIn(forbidden, names, forbidden)



if __name__ == "__main__":
    unittest.main()
