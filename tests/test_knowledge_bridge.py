# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.7: projection contract, purity and B9.6.1 compatibility of the bridge."""

import ast
from pathlib import Path
import unittest

from app import initial_knowledge as ik
from app.compatibility_evaluator import RuntimeKnowledge
from app.compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeProvenance,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)
from app.knowledge_bridge import KnowledgeProjection, project_knowledge

STATE = KnowledgeState
KIND = KnowledgeKind

ALLOWED_IMPORTS = {"__future__", "dataclasses", "compatibility_evaluator",
                   "compatibility_knowledge"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__", "compile", "input",
                   "system", "popen", "run", "Popen", "socket", "urlopen",
                   "write_text", "write_bytes", "loads", "dump", "listdir",
                   "getenv", "environ", "read_text", "read_bytes"}

BACKEND_CPU = KnowledgeSubject(KIND.BACKEND, "cpu")
BACKEND_VULKAN = KnowledgeSubject(KIND.BACKEND, "vulkan")
BACKEND_HIP = KnowledgeSubject(KIND.BACKEND, "hip")
FORMAT_GGUF = KnowledgeSubject(KIND.FORMAT, "gguf")
ARCH_LLAMA = KnowledgeSubject(KIND.ARCHITECTURE, "llama")
CAP_CODE = KnowledgeSubject(KIND.CAPABILITY, "code_generation")
PLATFORM_LINUX = KnowledgeSubject(KIND.PLATFORM, "linux")


def runtime(subject_id: str) -> KnowledgeSubject:
    return KnowledgeSubject(KIND.RUNTIME, subject_id)


def assertion(subject_id, obj, state, scope=None):
    return KnowledgeAssertion(
        subject=runtime(subject_id),
        predicate=KnowledgePredicate.SUPPORTS,
        object=obj,
        state=state,
        scope=KnowledgeScope() if scope is None else scope,
        provenance=KnowledgeProvenance(source="test"),
    )


class PurityTests(unittest.TestCase):
    def test_module_imports_only_bridge_dependencies(self):
        tree = ast.parse(
            Path("app/knowledge_bridge.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, ALLOWED_IMPORTS)

    def test_module_performs_no_io_or_environment_access(self):
        tree = ast.parse(
            Path("app/knowledge_bridge.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, FORBIDDEN_CALLS)
            elif isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, FORBIDDEN_CALLS)

class SyntheticProjectionTests(unittest.TestCase):
    def test_invalid_runtime_subject_is_rejected(self):
        for wrong_kind in (KIND.BACKEND, KIND.FORMAT, KIND.ARCHITECTURE,
                           KIND.CAPABILITY, KIND.PLATFORM):
            with self.subTest(kind=wrong_kind):
                subject = KnowledgeSubject(wrong_kind, "cpu")
                with self.assertRaises(ValueError):
                    project_knowledge(KnowledgeRegistry(()), subject)

    def test_empty_registry_yields_valid_empty_knowledge(self):
        projection = project_knowledge(KnowledgeRegistry(()), runtime("r"))
        rk = projection.runtime_knowledge
        self.assertEqual(rk.name, "r")
        self.assertEqual(rk.supported_formats, ())
        self.assertEqual(rk.unsupported_formats, ())
        self.assertEqual(rk.supported_architectures, ())
        self.assertEqual(rk.unsupported_architectures, ())
        self.assertEqual(rk.supported_model_types, ())
        self.assertEqual(rk.unsupported_model_types, ())
        self.assertEqual(rk.supported_backends, ())
        self.assertEqual(rk.unsupported_backends, ())
        self.assertIsNone(rk.supports_artifact)
        self.assertEqual(projection.projected, ())
        self.assertEqual(projection.excluded_unknown, ())
        self.assertEqual(projection.unrepresentable, ())
        self.assertEqual(projection.conflicts, ())

    def test_supported_states_map_to_supported_lists(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.SUPPORTED),
            assertion("r", FORMAT_GGUF, STATE.SUPPORTED),
            assertion("r", ARCH_LLAMA, STATE.SUPPORTED),
        ))
        rk = project_knowledge(registry, runtime("r")).runtime_knowledge
        self.assertEqual(rk.supported_backends, ("cpu",))
        self.assertEqual(rk.supported_formats, ("gguf",))
        self.assertEqual(rk.supported_architectures, ("llama",))

    def test_unsupported_states_map_to_unsupported_lists(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.UNSUPPORTED),
            assertion("r", FORMAT_GGUF, STATE.UNSUPPORTED),
            assertion("r", ARCH_LLAMA, STATE.UNSUPPORTED),
        ))
        rk = project_knowledge(registry, runtime("r")).runtime_knowledge
        self.assertEqual(rk.unsupported_backends, ("cpu",))
        self.assertEqual(rk.unsupported_formats, ("gguf",))
        self.assertEqual(rk.unsupported_architectures, ("llama",))

    def test_explicit_unknown_enters_neither_list(self):
        row = assertion("r", BACKEND_CPU, STATE.UNKNOWN)
        projection = project_knowledge(
            KnowledgeRegistry((row,)), runtime("r"))
        rk = projection.runtime_knowledge
        self.assertNotIn("cpu", rk.supported_backends)
        self.assertNotIn("cpu", rk.unsupported_backends)
        self.assertEqual(projection.excluded_unknown, (row,))

    def test_absence_is_not_invented_as_unknown_or_unsupported(self):
        projection = project_knowledge(
            KnowledgeRegistry((assertion("r", BACKEND_CPU, STATE.SUPPORTED),)),
            runtime("r"))
        self.assertNotIn("vulkan",
                         projection.runtime_knowledge.supported_backends)
        self.assertNotIn("vulkan",
                         projection.runtime_knowledge.unsupported_backends)
        self.assertEqual(projection.excluded_unknown, ())


    def test_exact_scope_only(self):
        linux = KnowledgeScope(platform="linux")
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_VULKAN, STATE.SUPPORTED, linux),
            assertion("r", BACKEND_HIP, STATE.SUPPORTED),
        ))
        empty = project_knowledge(registry, runtime("r"))
        self.assertEqual(empty.runtime_knowledge.supported_backends, ("hip",))
        linux_projection = project_knowledge(registry, runtime("r"), linux)
        self.assertEqual(linux_projection.runtime_knowledge.supported_backends,
                         ("vulkan",))
        windows = project_knowledge(registry, runtime("r"),
                                    KnowledgeScope(platform="windows"))
        self.assertEqual(windows.runtime_knowledge.supported_backends, ())
        self.assertEqual(windows.projected, ())

    def test_capabilities_and_platforms_are_unrepresentable(self):
        registry = KnowledgeRegistry((
            assertion("r", CAP_CODE, STATE.SUPPORTED),
            assertion("r", PLATFORM_LINUX, STATE.SUPPORTED),
        ))
        projection = project_knowledge(registry, runtime("r"))
        self.assertEqual(len(projection.unrepresentable), 2)
        self.assertEqual(projection.runtime_knowledge, RuntimeKnowledge(
            name="r", supports_artifact=None))
        self.assertEqual(projection.projected, ())

    def test_conflict_is_reported_and_not_projected(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.SUPPORTED),
            assertion("r", BACKEND_CPU, STATE.UNSUPPORTED),
            assertion("r", FORMAT_GGUF, STATE.SUPPORTED),
        ))
        projection = project_knowledge(registry, runtime("r"))
        self.assertEqual(len(projection.conflicts), 1)
        self.assertEqual(len(projection.conflicts[0].assertions), 2)
        self.assertEqual(projection.runtime_knowledge.supported_backends, ())
        self.assertEqual(projection.runtime_knowledge.unsupported_backends, ())
        self.assertEqual(projection.runtime_knowledge.supported_formats,
                         ("gguf",))

    def test_conflict_does_not_affect_independent_relations(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.SUPPORTED),
            assertion("r", BACKEND_CPU, STATE.UNSUPPORTED),
            assertion("r", BACKEND_HIP, STATE.SUPPORTED),
        ))
        projection = project_knowledge(registry, runtime("r"))
        self.assertEqual(len(projection.conflicts), 1)
        self.assertEqual(projection.runtime_knowledge.supported_backends,
                         ("hip",))

    def test_alias_and_display_name_are_never_lookup_keys(self):
        subject = KnowledgeSubject(KIND.RUNTIME, "llama.cpp",
                                   display_name="llama.cpp",
                                   aliases=("llamacpp", "llama.app"))
        registry = KnowledgeRegistry((assertion("llama.cpp", BACKEND_CPU,
                                                STATE.SUPPORTED),))
        self.assertEqual(project_knowledge(registry, subject)
                         .runtime_knowledge.supported_backends, ("cpu",))
        by_alias = KnowledgeSubject(KIND.RUNTIME, "llamacpp")
        self.assertEqual(project_knowledge(registry, by_alias)
                         .runtime_knowledge.supported_backends, ())
        self.assertEqual(project_knowledge(registry, by_alias).projected, ())

    def test_projection_is_deterministic_and_registry_untouched(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.SUPPORTED),
            assertion("r", BACKEND_HIP, STATE.UNSUPPORTED),
            assertion("r", FORMAT_GGUF, STATE.SUPPORTED),
        ))
        first = project_knowledge(registry, runtime("r"))
        reversed_registry = KnowledgeRegistry(tuple(reversed(registry.entries)))
        second = project_knowledge(reversed_registry, runtime("r"))
        self.assertEqual(first, second)
        self.assertEqual(first.runtime_knowledge, second.runtime_knowledge)
        self.assertEqual(registry.entries, tuple(sorted(
            registry.entries, key=repr)))
        self.assertEqual(len(registry.entries), 3)

    def test_projection_output_is_frozen(self):
        projection = project_knowledge(
            KnowledgeRegistry((assertion("r", BACKEND_CPU, STATE.SUPPORTED),)),
            runtime("r"))
        self.assertIsInstance(projection, KnowledgeProjection)
        with self.assertRaises(Exception):
            projection.projected = ()
        with self.assertRaises(Exception):
            projection.runtime_knowledge.supported_backends = ("x",)

    def test_supports_artifact_stays_none(self):
        projection = project_knowledge(
            KnowledgeRegistry((assertion("r", FORMAT_GGUF, STATE.SUPPORTED),)),
            runtime("r"))
        self.assertIsNone(projection.runtime_knowledge.supports_artifact)

    def test_no_inference_between_kinds_or_values(self):
        registry = KnowledgeRegistry((
            assertion("r", BACKEND_CPU, STATE.SUPPORTED),
            assertion("r", CAP_CODE, STATE.SUPPORTED),
        ))
        rk = project_knowledge(registry, runtime("r")).runtime_knowledge
        self.assertEqual(rk.supported_backends, ("cpu",))
        self.assertEqual(rk.supported_formats, ())
        self.assertEqual(rk.unsupported_backends, ())
        self.assertEqual(rk.supported_architectures, ())
        self.assertEqual(rk.unsupported_architectures, ())



class DatasetB961Tests(unittest.TestCase):
    """The real B9.6.1 dataset (38 assertions) through the bridge."""

    def test_llamacpp_empty_scope_projection(self):
        projection = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY,
                                       ik.LLAMACPP)
        rk = projection.runtime_knowledge
        self.assertEqual(rk.name, "llama.cpp")
        self.assertEqual(rk.supported_backends, ("cpu", "cuda", "hip"))
        self.assertEqual(rk.unsupported_backends, ())
        self.assertEqual(rk.supported_formats, ("gguf",))
        self.assertEqual(rk.unsupported_formats, ())
        self.assertEqual(rk.supported_architectures, ("llama", "qwen2", "qwen3"))
        self.assertEqual(rk.unsupported_architectures, ())
        self.assertIsNone(rk.supports_artifact)
        self.assertEqual([row.object.canonical_id
                          for row in projection.excluded_unknown],
                         ["rocm"])
        self.assertEqual(projection.conflicts, ())
        unrepresentable = {row.object.canonical_id
                           for row in projection.unrepresentable}
        self.assertEqual(unrepresentable, {"text_generation",
                                           "code_generation", "vision",
                                           "embeddings", "tool_use"})

    def test_ollama_empty_scope_projection(self):
        projection = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY,
                                       ik.OLLAMA)
        rk = projection.runtime_knowledge
        self.assertEqual(rk.name, "ollama")
        self.assertEqual(rk.supported_backends, ("cpu", "rocm"))
        self.assertEqual(rk.unsupported_backends, ())
        self.assertEqual(rk.supported_formats, ("gguf",))
        self.assertEqual(rk.unsupported_formats, ())
        self.assertEqual(rk.supported_architectures, ())
        self.assertEqual(rk.unsupported_architectures, ())
        self.assertIsNone(rk.supports_artifact)
        self.assertEqual(sorted(row.object.canonical_id
                                for row in projection.excluded_unknown),
                         ["cuda", "llama", "sycl"])
        self.assertEqual(projection.conflicts, ())
        unrepresentable = {row.object.canonical_id
                           for row in projection.unrepresentable}
        self.assertEqual(unrepresentable, {"text_generation",
                                           "code_generation", "vision",
                                           "embeddings", "tool_use",
                                           "linux", "windows", "macos"})

    def test_rocm_is_not_unsupported_for_llamacpp(self):
        projection = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY,
                                       ik.LLAMACPP)
        self.assertNotIn("rocm",
                         projection.runtime_knowledge.unsupported_backends)
        self.assertNotIn("rocm",
                         projection.runtime_knowledge.supported_backends)

    def test_code_generation_isolation_between_runtimes(self):
        llamacpp = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY,
                                     ik.LLAMACPP)
        ollama = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY, ik.OLLAMA)
        llamacpp_code = [row for row in llamacpp.unrepresentable
                         if row.object is ik.CAPABILITY_CODE_GENERATION]
        ollama_code = [row for row in ollama.unrepresentable
                       if row.object is ik.CAPABILITY_CODE_GENERATION]
        self.assertEqual(len(llamacpp_code), 1)
        self.assertEqual(len(ollama_code), 1)
        self.assertIsNot(llamacpp_code[0], ollama_code[0])
        self.assertIsNot(llamacpp_code[0].subject, ollama_code[0].subject)
        self.assertEqual(llamacpp_code[0].subject.canonical_id, "llama.cpp")
        self.assertEqual(ollama_code[0].subject.canonical_id, "ollama")
        for projection in (llamacpp, ollama):
            expected = projection.runtime.canonical_id
            for row in (projection.projected + projection.excluded_unknown
                        + projection.unrepresentable):
                self.assertEqual(row.subject.canonical_id, expected)

    def test_scoped_rows_stay_out_of_the_empty_scope_projection(self):
        projection = project_knowledge(ik.INITIAL_KNOWLEDGE_REGISTRY,
                                       ik.LLAMACPP)
        projected_ids = [row.object.canonical_id
                         for row in projection.projected]
        self.assertNotIn("vulkan", projected_ids)
        self.assertNotIn("sycl", projected_ids)
        for row in projection.projected:
            self.assertEqual(row.scope, KnowledgeScope())

    def test_platform_scope_projection_for_llamacpp(self):
        projection = project_knowledge(
            ik.INITIAL_KNOWLEDGE_REGISTRY, ik.LLAMACPP,
            KnowledgeScope(platform="windows"))
        self.assertIn("vulkan", projection.runtime_knowledge.supported_backends)
        self.assertIn("hip", projection.runtime_knowledge.supported_backends)
        self.assertNotIn("cpu", projection.runtime_knowledge.supported_backends)


if __name__ == "__main__":
    unittest.main()
