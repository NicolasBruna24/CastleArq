# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.6.1: dataset shape, evidence discipline and B9.5 boundary of the initial KB.

The dataset module is expected to be declarative data only, so these tests check
both its contents (states, scopes, entity separation, deliberate UNKNOWN rows)
and its nature (no logic, no I/O, no network, no execution).
"""

import ast
from contextlib import ExitStack
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

from app import compatibility_knowledge as ck
from app import initial_knowledge as ik


STATE = ck.KnowledgeState
KIND = ck.KnowledgeKind
PREDICATE = ck.KnowledgePredicate
SCOPE = ck.KnowledgeScope

REGISTRY = ik.INITIAL_KNOWLEDGE_REGISTRY
ALL_ASSERTIONS = ik.INITIAL_KNOWLEDGE

ALLOWED_RUNTIMES = {"llama.cpp", "ollama"}
ALLOWED_BACKENDS = {"cpu", "vulkan", "cuda", "rocm", "hip", "sycl"}
ALLOWED_PLATFORMS = {"linux", "windows", "macos"}
ALLOWED_CAPABILITIES = {"text_generation", "code_generation", "vision",
                        "embeddings", "tool_use"}
ALLOWED_ARCHITECTURES = {"llama", "qwen2", "qwen3"}
VENDOR_IDS = {"nvidia", "amd", "intel", "arc", "b580", "level_zero", "apple",
              "metal", "cuda-backend", "hip7"}
DATASET_CONSTRUCTORS = {"KnowledgeSubject", "KnowledgeScope", "KnowledgeProvenance",
                        "KnowledgeAssertion", "KnowledgeRegistry"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__", "compile", "input",
                   "system", "popen", "run", "Popen", "socket", "urlopen",
                   "write_text", "write_bytes", "loads", "dump"}


def state_of(subject, obj, scope=None):
    return REGISTRY.state_for(subject, obj, scope=scope if scope is not None else SCOPE())


def rows_for(subject, obj, scope=None):
    return REGISTRY.query(subject, obj, scope=scope if scope is not None else SCOPE())


def endpoints(assertion):
    return (assertion.subject, assertion.object)


class ModulePurityTests(unittest.TestCase):
    def test_module_is_declarative_data_only(self):
        tree = ast.parse(Path(ik.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for kind in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                         ast.Lambda, ast.If, ast.For, ast.While, ast.Try,
                         ast.With, ast.ListComp, ast.DictComp, ast.SetComp,
                         ast.GeneratorExp):
                self.assertNotIsInstance(node, kind)
        for node in tree.body:
            self.assertIsInstance(node, (ast.Expr, ast.ImportFrom, ast.Assign,
                                         ast.AnnAssign))

    def test_imports_only_future_and_b95_module(self):
        tree = ast.parse(Path(ik.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"__future__", "compatibility_knowledge"})

    def test_only_b95_constructors_are_called(self):
        tree = ast.parse(Path(ik.__file__).read_text(encoding="utf-8"))
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self.assertIsInstance(node.func, ast.Name)
                calls.add(node.func.id)
                self.assertNotIn(node.func.id, FORBIDDEN_CALLS)
        self.assertLessEqual(calls, DATASET_CONSTRUCTORS)

    def test_importing_the_module_has_no_external_effects(self):
        # Importing a module legitimately reads its own source file, so `open` is
        # deliberately not blocked here; only process/network/eval effects are.
        # `exec` is not blocked either: the import machinery executes module code
        # through it by design, so patching it would fail the reload itself. The
        # module's freedom from eval/exec/__import__ calls is proven statically by
        # ModulePurityTests instead.
        targets = ("subprocess.run", "subprocess.Popen", "os.system",
                   "socket.socket", "socket.create_connection",
                   "urllib.request.urlopen", "builtins.eval")
        patches = [patch(target, side_effect=AssertionError("external effect"))
                   for target in targets]
        # Resolve imported targets before starting the patches.
        import subprocess
        import socket
        import urllib.request

        self.assertIsNotNone((subprocess, socket, urllib.request))
        with ExitStack() as stack:
            mocks = [stack.enter_context(context) for context in patches]
            reloaded = importlib.reload(ik)
        self.assertEqual(len(reloaded.INITIAL_KNOWLEDGE), len(ALL_ASSERTIONS))
        for mocked in mocks:
            self.assertFalse(mocked.called)

    def test_dataset_queries_have_no_external_effects(self):
        targets = ("subprocess.run", "subprocess.Popen", "os.system",
                   "socket.socket", "socket.create_connection",
                   "urllib.request.urlopen", "builtins.open", "builtins.eval",
                   "builtins.exec")
        patches = [patch(target, side_effect=AssertionError("external effect"))
                   for target in targets]
        # Resolve imported targets before starting the patches.
        import subprocess
        import socket
        import urllib.request

        self.assertIsNotNone((subprocess, socket, urllib.request))
        with ExitStack() as stack:
            for context in patches:
                stack.enter_context(context)
            self.assertEqual(state_of(ik.LLAMACPP, ik.BACKEND_CPU), STATE.SUPPORTED)
            self.assertEqual(rows_for(ik.OLLAMA, ik.BACKEND_ROCM),
                             (ik.OLLAMA_SUPPORTS_ROCM,))
            self.assertEqual(REGISTRY.conflicts(), ())
            self.assertEqual(len(REGISTRY.entries), len(ALL_ASSERTIONS))


class DatasetShapeTests(unittest.TestCase):
    def test_size_within_spec_range(self):
        self.assertIsInstance(ALL_ASSERTIONS, tuple)
        self.assertGreaterEqual(len(ALL_ASSERTIONS), 20)
        self.assertLessEqual(len(ALL_ASSERTIONS), 40)

    def test_every_row_is_a_b95_assertion(self):
        for assertion in ALL_ASSERTIONS:
            self.assertIs(type(assertion), ck.KnowledgeAssertion)
            self.assertIs(type(assertion.subject), ck.KnowledgeSubject)
            self.assertIs(type(assertion.object), ck.KnowledgeSubject)
            self.assertIs(type(assertion.scope), ck.KnowledgeScope)
            self.assertIs(type(assertion.provenance), ck.KnowledgeProvenance)

    def test_single_implemented_predicate_is_used(self):
        for assertion in ALL_ASSERTIONS:
            self.assertIs(assertion.predicate, PREDICATE.SUPPORTS)

    def test_states_are_supported_or_unknown_only(self):
        counts = {}
        for assertion in ALL_ASSERTIONS:
            counts[assertion.state] = counts.get(assertion.state, 0) + 1
        self.assertEqual(set(counts), {STATE.SUPPORTED, STATE.UNKNOWN})
        self.assertNotIn(STATE.UNSUPPORTED, counts)
        self.assertGreaterEqual(counts[STATE.SUPPORTED], 20)
        self.assertEqual(counts[STATE.UNKNOWN], len(ik.DELIBERATE_UNKNOWN_ROWS))

    def test_all_six_kinds_are_covered(self):
        kinds = set()
        for assertion in ALL_ASSERTIONS:
            kinds.add(assertion.subject.kind)
            kinds.add(assertion.object.kind)
        self.assertEqual(kinds, set(KIND))

    def test_subjects_are_the_two_declared_runtimes(self):
        for assertion in ALL_ASSERTIONS:
            self.assertIs(assertion.subject.kind, KIND.RUNTIME)
            self.assertIn(assertion.subject.canonical_id, ALLOWED_RUNTIMES)

    def test_objects_stay_inside_the_declared_taxonomy(self):
        allowed = {
            KIND.BACKEND: ALLOWED_BACKENDS,
            KIND.PLATFORM: ALLOWED_PLATFORMS,
            KIND.CAPABILITY: ALLOWED_CAPABILITIES,
            KIND.ARCHITECTURE: ALLOWED_ARCHITECTURES,
            KIND.FORMAT: {"gguf"},
        }
        for assertion in ALL_ASSERTIONS:
            kind = assertion.object.kind
            with self.subTest(subject=assertion.subject.canonical_id,
                              object=assertion.object.canonical_id):
                self.assertIn(kind, allowed)
                self.assertIn(assertion.object.canonical_id, allowed[kind])

    def test_no_vendor_hardware_or_third_runtime_entities(self):
        for assertion in ALL_ASSERTIONS:
            for endpoint in endpoints(assertion):
                self.assertNotIn(endpoint.canonical_id.lower(), VENDOR_IDS)
                self.assertNotIn(endpoint.canonical_id.lower(),
                                 {"opencl", "metal", "blas", "musa", "vllm",
                                  "llama.app", "docker", "android"})

    def test_every_row_carries_traceable_provenance(self):
        for assertion in ALL_ASSERTIONS:
            provenance = assertion.provenance
            with self.subTest(row=assertion.subject.canonical_id,
                              object=assertion.object.canonical_id):
                for value in (provenance.source, provenance.source_type,
                              provenance.reference):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip())
                self.assertEqual(provenance.observed_at, ik.OBSERVED_AT)
                self.assertIsNone(provenance.published_at)

    def test_provenance_uses_no_scoring_vocabulary(self):
        forbidden = {"confidence", "trust", "score", "ranking", "rank",
                     "weight", "priority", "level 1", "level 2"}
        for assertion in ALL_ASSERTIONS:
            text = " ".join(str(value) for value in vars(assertion.provenance).values())
            for word in forbidden:
                self.assertNotIn(word, text.lower())

    def test_registry_matches_dataset_without_duplicates(self):
        self.assertIsInstance(REGISTRY, ck.KnowledgeRegistry)
        self.assertEqual(len(REGISTRY.entries), len(ALL_ASSERTIONS))
        self.assertEqual(set(REGISTRY.entries), set(ALL_ASSERTIONS))

    def test_registry_order_is_independent_of_insertion(self):
        reversed_registry = ck.KnowledgeRegistry(tuple(reversed(ALL_ASSERTIONS)))
        rotated = ck.KnowledgeRegistry(ALL_ASSERTIONS[7:] + ALL_ASSERTIONS[:7])
        self.assertEqual(reversed_registry.entries, REGISTRY.entries)
        self.assertEqual(rotated.entries, REGISTRY.entries)

    def test_registry_add_is_non_mutating(self):
        extra = ck.KnowledgeSubject(KIND.BACKEND, "future-backend")
        extended = REGISTRY.add(ck.KnowledgeAssertion(
            ik.LLAMACPP, PREDICATE.SUPPORTS, extra, STATE.UNKNOWN))
        self.assertEqual(len(extended.entries), len(ALL_ASSERTIONS) + 1)
        self.assertEqual(REGISTRY.entries, tuple(sorted(
            ALL_ASSERTIONS, key=repr)))
        self.assertEqual(extended.state_for(ik.LLAMACPP, extra), STATE.UNKNOWN)
        self.assertEqual(state_of(ik.LLAMACPP, extra), STATE.UNKNOWN)

    def test_no_conflicts_between_rows(self):
        self.assertEqual(REGISTRY.conflicts(), ())
        for assertion in ALL_ASSERTIONS:
            self.assertFalse(REGISTRY.has_conflict(
                assertion.subject, assertion.object, scope=assertion.scope))

    def test_each_row_is_reachable_by_exact_query(self):
        for assertion in ALL_ASSERTIONS:
            with self.subTest(row=assertion.state,
                              object=assertion.object.canonical_id):
                self.assertEqual(
                    state_of(assertion.subject, assertion.object, assertion.scope),
                    assertion.state)
                self.assertIn(assertion, rows_for(
                    assertion.subject, assertion.object, assertion.scope))


class CodeGenerationAdjudicationTests(unittest.TestCase):
    """B9.6.0 §7 (reformed): capability states track verified evidence.

    Both runtime/code_generation relations were re-adjudicated with primary
    runtime evidence (B8.1 §3.7 includes code completion, infilling and FIM),
    so no capability UNKNOWN is stored; the UNKNOWN demonstration rests on the
    backend and architecture rows (B9.6.0 §4, §21).
    """

    def test_llamacpp_code_generation_is_supported(self):
        self.assertEqual(state_of(ik.LLAMACPP, ik.CAPABILITY_CODE_GENERATION),
                         STATE.SUPPORTED)
        self.assertEqual(len(rows_for(ik.LLAMACPP,
                                      ik.CAPABILITY_CODE_GENERATION)), 1)
        provenance = rows_for(ik.LLAMACPP,
                              ik.CAPABILITY_CODE_GENERATION)[0].provenance
        self.assertIn("tools/server/README.md", provenance.source)

    def test_ollama_code_generation_is_supported(self):
        self.assertEqual(state_of(ik.OLLAMA, ik.CAPABILITY_CODE_GENERATION),
                         STATE.SUPPORTED)
        self.assertEqual(len(rows_for(ik.OLLAMA,
                                      ik.CAPABILITY_CODE_GENERATION)), 1)
        provenance = rows_for(ik.OLLAMA,
                              ik.CAPABILITY_CODE_GENERATION)[0].provenance
        self.assertIn("suffix", provenance.source)

    def test_no_capability_unknown_is_stored(self):
        for assertion in ALL_ASSERTIONS:
            if assertion.object.kind == KIND.CAPABILITY:
                self.assertIs(assertion.state, STATE.SUPPORTED,
                              msg=assertion.object.canonical_id)

    def test_unknown_demonstration_rests_on_backend_and_architecture(self):
        kinds = {assertion.object.kind
                 for assertion in ik.DELIBERATE_UNKNOWN_ROWS}
        self.assertEqual(kinds, {KIND.BACKEND, KIND.ARCHITECTURE})
        self.assertEqual(len(ik.DELIBERATE_UNKNOWN_ROWS), 4)
        self.assertEqual(len(ALL_ASSERTIONS), 39)
        for assertion in ALL_ASSERTIONS:
            self.assertIsNotNone(assertion.provenance)
        self.assertEqual(REGISTRY.conflicts(), ())
        self.assertEqual(len(REGISTRY.entries), len(ALL_ASSERTIONS))
