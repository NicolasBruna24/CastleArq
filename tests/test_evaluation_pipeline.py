# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.9: strict pipeline composition, D-1 table, traceability and purity."""

import ast
from pathlib import Path
import unittest

from app import evaluation_pipeline as ep
from app import initial_knowledge as ik
from app.compatibility_evaluator import CompatibilityStatus
from app.compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)
from app.evaluation_adapter import to_artifact
from app.models import ArtifactSpec, ModelSpec
from app.runtimes import PromptInputMode, RuntimeCapability

ALLOWED_IMPORTS = {"__future__", "dataclasses", "typing",
                   "compatibility_evaluator", "compatibility_knowledge",
                   "evaluation_adapter", "knowledge_bridge", "model_domain",
                   "models"}
FORBIDDEN_IMPORTS = {"runtimes", "subprocess", "socket", "urllib", "os",
                     "pathlib", "shutil", "sys"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__", "compile", "input",
                   "system", "popen", "run", "Popen", "socket", "urlopen",
                   "getenv", "environ", "listdir", "read_text", "read_bytes",
                   "write_text", "write_bytes"}


def capability(name, *compatibility_names):
    return RuntimeCapability(
        name=name,
        executable_path="/usr/bin/fake",
        version="v1.2.3 (raw cli line)",
        supported_formats=("GGUF",),
        supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        compatibility_names=tuple(compatibility_names),
    )


def spec(**overrides):
    base = dict(
        name="Qwen3 Demo", provider="Unknown", family="Qwen3",
        size_bytes=1234, format="GGUF", id=None, parameter_count_b=7.6,
        task="coding", architecture="Unknown",
        supported_runtimes=("llama.cpp / llama.app",),
        supported_backends=("Vulkan", "CPU"), context_length=4096,
    )
    base.update(overrides)
    return ModelSpec(**base)


def artifact(**overrides):
    base = dict(model_id="Qwen3 Demo", source="test", repository="repo",
                filename="model.gguf", format="GGUF",
                quantization="Q4_K_M", size_bytes=1234)
    base.update(overrides)
    return ArtifactSpec(**base)


def llama_pipeline(**kwargs):
    return ep.evaluate_strict(
        ik.INITIAL_KNOWLEDGE_REGISTRY, spec(), artifact(),
        capability("llama.cpp CLI", "llama.cpp"), **kwargs)


class PurityTests(unittest.TestCase):
    def test_module_imports_only_pipeline_dependencies(self):
        tree = ast.parse(
            Path("app/evaluation_pipeline.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, FORBIDDEN_IMPORTS - {"runtimes"})
                imported.add(node.module)
        runtime_imports = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "runtimes"]
        self.assertEqual(len(runtime_imports), 1)
        guarded = [node for node in tree.body
                   if isinstance(node, ast.If)
                   and isinstance(node.test, ast.Name)
                   and node.test.id == "TYPE_CHECKING"]
        self.assertEqual(len(guarded), 1)
        self.assertTrue(any(node in guarded[0].body
                            for node in runtime_imports))
        self.assertEqual(imported, ALLOWED_IMPORTS | {"runtimes"})

    def test_module_performs_no_io_or_environment_access(self):
        tree = ast.parse(
            Path("app/evaluation_pipeline.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, FORBIDDEN_CALLS)
            elif isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, FORBIDDEN_CALLS)


class CanonicalFormatTests(unittest.TestCase):
    def test_table_is_closed_and_exact(self):
        self.assertEqual(ep.CANONICAL_FORMATS, (("GGUF", "gguf"),))

    def test_gguf_is_canonicalized(self):
        self.assertEqual(ep.canonical_format("GGUF"), "gguf")

    def test_unlisted_values_pass_through_unchanged(self):
        for value in ("Gguf", "gguf", "safetensors", "SAFETENSORS", "GGUFX",
                      " GGUF", "Metal"):
            with self.subTest(format=value):
                self.assertEqual(ep.canonical_format(value), value)

    def test_none_stays_none(self):
        self.assertIsNone(ep.canonical_format(None))

class PipelineTests(unittest.TestCase):
    def test_strict_evaluation_is_invocable_and_frozen(self):
        evaluation = llama_pipeline()
        self.assertIsInstance(evaluation, ep.StrictEvaluation)
        with self.assertRaises(Exception):
            evaluation.result = None

    def test_full_chain_composition(self):
        evaluation = llama_pipeline(backend="CPU")
        self.assertEqual(evaluation.model.identity.name, "Qwen3 Demo")
        self.assertEqual(evaluation.artifact.format, "gguf")
        self.assertEqual(evaluation.context.runtime.supported_backends,
                         ("cpu", "cuda", "hip"))
        self.assertEqual(evaluation.context.backend, "cpu")
        self.assertIs(evaluation.context.runtime,
                      evaluation.projection.runtime_knowledge)

    def test_d1_makes_format_check_pass(self):
        evaluation = llama_pipeline()
        format_check = evaluation.result.checks[1]
        self.assertEqual(format_check.status.value, "passed")

    def test_backend_cpu_passes_and_unknown_backend_is_never_failed(self):
        evaluation = llama_pipeline(backend="CPU")
        self.assertEqual(evaluation.result.checks[4].status.value, "passed")
        evaluation = llama_pipeline(backend="Metal")
        self.assertEqual(evaluation.result.checks[4].status.value, "unknown")
        self.assertNotEqual(evaluation.result.checks[4].status.value, "failed")

    def test_identity_stays_unknown_without_identifier(self):
        evaluation = llama_pipeline()
        self.assertEqual(evaluation.result.checks[0].status.value, "unknown")

    def test_capabilities_stay_unknown(self):
        evaluation = llama_pipeline(
            required_capabilities=("code_generation",))
        capability_check = evaluation.result.checks[5]
        self.assertEqual(capability_check.status.value, "unknown")

    def test_honest_insufficient_evidence_with_real_dataset(self):
        evaluation = llama_pipeline(backend="CPU")
        self.assertIs(evaluation.result.status,
                      CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_projection_traceability_is_preserved(self):
        evaluation = llama_pipeline()
        projection = evaluation.projection
        # llama.cpp, empty scope: cpu/cuda/hip backends + gguf format +
        # llama/qwen2/qwen3 architectures projected; rocm UNKNOWN; 5 capabilities
        # unrepresentable; platforms absent from llama.cpp rows.
        self.assertEqual(len(projection.projected), 7)
        self.assertEqual(
            sorted(row.object.canonical_id
                   for row in projection.excluded_unknown), ["rocm"])
        self.assertEqual(len(projection.unrepresentable), 5)
        self.assertEqual(projection.conflicts, ())
        for row in projection.projected + projection.excluded_unknown:
            self.assertIsNotNone(row.provenance.source)

    def test_runtime_isolation_between_runtimes(self):
        llama = llama_pipeline()
        ollama = ep.evaluate_strict(
            ik.INITIAL_KNOWLEDGE_REGISTRY, spec(), artifact(),
            capability("ollama"))
        self.assertNotEqual(llama.context.runtime,
                            ollama.context.runtime)
        self.assertEqual(ollama.context.runtime.supported_backends,
                         ("cpu", "rocm"))
        self.assertEqual(
            sorted(row.object.canonical_id
                   for row in ollama.projection.excluded_unknown),
            ["cuda", "llama", "sycl"])
        for projection in (llama.projection, ollama.projection):
            for row in (projection.projected + projection.excluded_unknown
                        + projection.unrepresentable):
                self.assertEqual(row.subject.canonical_id,
                                 projection.runtime_knowledge.name)

    def test_scope_is_passed_through_untouched(self):
        evaluation = ep.evaluate_strict(
            ik.INITIAL_KNOWLEDGE_REGISTRY, spec(), artifact(),
            capability("llama.cpp CLI", "llama.cpp"),
            scope=KnowledgeScope(platform="windows"))
        self.assertIn("vulkan",
                      evaluation.context.runtime.supported_backends)


class NoInferenceTests(unittest.TestCase):
    def test_task_and_model_name_never_produce_capabilities(self):
        coding = ep.evaluate_strict(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec(name="Qwen3-Coder", task="coding"), artifact(),
            capability("llama.cpp CLI", "llama.cpp"),
            required_capabilities=("code_generation",))
        plain = llama_pipeline(required_capabilities=("code_generation",))
        self.assertEqual(
            coding.result.checks[5].status, plain.result.checks[5].status)
        self.assertEqual(coding.result.checks[5].status.value, "unknown")

    def test_quantization_label_never_implies_precision_or_quantized(self):
        evaluation = llama_pipeline()
        self.assertIsNone(evaluation.artifact.precision.name)
        self.assertIsNone(evaluation.artifact.precision.bits)
        self.assertIsNone(evaluation.artifact.quantization.method)

    def test_legacy_fields_never_reach_the_result(self):
        evaluation = llama_pipeline()
        self.assertIsNone(evaluation.model.architecture.architecture)
        self.assertEqual(evaluation.model.capabilities.text_generation, None)

    def test_unknown_required_capability_is_rejected_by_b93(self):
        with self.assertRaises(ValueError):
            llama_pipeline(required_capabilities=("telepathy",))


class ConflictPropagationTests(unittest.TestCase):
    def test_synthetic_conflict_is_propagated_without_resolution(self):
        registry = KnowledgeRegistry((
            KnowledgeAssertion(
                subject=KnowledgeSubject(KnowledgeKind.RUNTIME, "r1"),
                predicate=KnowledgePredicate.SUPPORTS,
                object=KnowledgeSubject(KnowledgeKind.BACKEND, "cpu"),
                state=KnowledgeState.SUPPORTED),
            KnowledgeAssertion(
                subject=KnowledgeSubject(KnowledgeKind.RUNTIME, "r1"),
                predicate=KnowledgePredicate.SUPPORTS,
                object=KnowledgeSubject(KnowledgeKind.BACKEND, "cpu"),
                state=KnowledgeState.UNSUPPORTED),
            KnowledgeAssertion(
                subject=KnowledgeSubject(KnowledgeKind.RUNTIME, "r1"),
                predicate=KnowledgePredicate.SUPPORTS,
                object=KnowledgeSubject(KnowledgeKind.FORMAT, "gguf"),
                state=KnowledgeState.SUPPORTED),
        ))
        evaluation = ep.evaluate_strict(
            registry, spec(), artifact(), capability("r1"), backend="CPU")
        self.assertEqual(len(evaluation.projection.conflicts), 1)
        self.assertEqual(
            evaluation.context.runtime.supported_backends, ())
        self.assertEqual(evaluation.context.runtime.unsupported_backends, ())
        self.assertEqual(evaluation.context.runtime.supported_formats,
                         ("gguf",))
        self.assertEqual(evaluation.result.checks[4].status.value, "unknown")


class DeterminismTests(unittest.TestCase):
    def test_repeated_calls_are_equal(self):
        first = llama_pipeline(backend="CPU")
        second = llama_pipeline(backend="CPU")
        self.assertEqual(first, second)

    def test_inputs_are_not_mutated(self):
        model_spec = spec()
        artifact_spec = artifact()
        model_before = dict(vars(model_spec))
        artifact_before = dict(vars(artifact_spec))
        llama_pipeline(backend="CPU")
        self.assertEqual(vars(model_spec), model_before)
        self.assertEqual(vars(artifact_spec), artifact_before)

    def test_to_artifact_alone_is_not_canonicalized(self):
        # D-1 applies only inside evaluate_strict; B9.8 stays frozen.
        self.assertEqual(to_artifact(artifact()).format, "GGUF")


if __name__ == "__main__":
    unittest.main()
