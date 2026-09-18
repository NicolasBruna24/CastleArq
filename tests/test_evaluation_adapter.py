# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.8: domain adapter contracts, purity, no-inference and B9.6.1 round-trip."""

import ast
from pathlib import Path
import unittest

from app import evaluation_adapter as ea
from app import initial_knowledge as ik
from app.compatibility_evaluator import EvaluationContext, evaluate
from app.compatibility_knowledge import KnowledgeRegistry, KnowledgeScope
from app.models import ArtifactSpec, ModelSpec
from app.model_domain import Model, ModelArtifact, QuantizationStatus
from app.runtimes import PromptInputMode, RuntimeCapability

ALLOWED_IMPORTS = {"__future__", "typing", "compatibility_evaluator",
                   "compatibility_knowledge", "knowledge_bridge",
                   "model_domain", "models"}
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
        backend_arguments=(("CPU", "none"),),
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


class PurityTests(unittest.TestCase):
    def test_module_imports_only_pure_dependencies(self):
        tree = ast.parse(
            Path("app/evaluation_adapter.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, FORBIDDEN_IMPORTS - {"runtimes"})
                imported.add(node.module)
        # `runtimes` is allowed ONLY as a TYPE_CHECKING type hint import.
        runtime_imports = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "runtimes"]
        self.assertEqual(len(runtime_imports), 1)
        parent = tree.body
        guarded = [node for node in parent
                   if isinstance(node, ast.If)
                   and isinstance(node.test, ast.Name)
                   and node.test.id == "TYPE_CHECKING"]
        self.assertEqual(len(guarded), 1)
        in_guard = any(node in guarded[0].body for node in runtime_imports)
        self.assertTrue(in_guard)
        self.assertEqual(imported, ALLOWED_IMPORTS | {"runtimes"})

    def test_module_performs_no_io_or_environment_access(self):
        tree = ast.parse(
            Path("app/evaluation_adapter.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, FORBIDDEN_CALLS)
            elif isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, FORBIDDEN_CALLS)


class ModelAdapterTests(unittest.TestCase):
    def test_name_id_and_provider(self):
        model = ea.to_model(spec(id="qwen3-demo", provider="hf"))
        self.assertEqual(model.identity.name, "Qwen3 Demo")
        self.assertEqual(model.identity.model_id, "qwen3-demo")
        self.assertEqual(model.provenance.source, "hf")

    def test_missing_id_is_never_backfilled_from_name(self):
        model = ea.to_model(spec())
        self.assertIsNone(model.identity.model_id)
        self.assertNotEqual(model.identity.model_id, model.identity.name)

    def test_explicit_architecture_is_copied_verbatim(self):
        self.assertEqual(
            ea.to_model(spec(architecture="llama")).architecture.architecture,
            "llama")

    def test_unknown_and_empty_architecture_become_none(self):
        self.assertIsNone(
            ea.to_model(spec(architecture="Unknown")).architecture.architecture)
        self.assertIsNone(
            ea.to_model(spec(architecture="")).architecture.architecture)

    def test_model_type_and_active_parameters_stay_none(self):
        arch = ea.to_model(spec(parameter_count_b=7.6)).architecture
        self.assertIsNone(arch.model_type)
        self.assertIsNone(arch.active_parameters)

    def test_parameters_use_the_declared_arithmetic(self):
        self.assertEqual(
            ea.to_model(spec(parameter_count_b=7.6)).architecture.parameters,
            7_600_000_000)
        self.assertIsNone(
            ea.to_model(spec(parameter_count_b=None)).architecture.parameters)

    def test_context_length_is_copied(self):
        self.assertEqual(ea.to_model(spec()).max_context, 4096)

    def test_capabilities_are_all_unknown(self):
        capabilities = ea.to_model(spec()).capabilities
        for name in ("text_generation", "code_generation", "vision",
                     "embeddings", "tool_use"):
            self.assertIsNone(getattr(capabilities, name))

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            ea.to_model(spec(name="  "))

    def test_model_artifacts_stay_empty(self):
        self.assertEqual(ea.to_model(spec()).artifacts, ())

    def test_legacy_heuristics_are_never_copied(self):
        model = ea.to_model(spec())
        fields = {key for key in vars(model)
                  if key not in ("identity", "provenance", "architecture")}
        self.assertEqual(fields, {"max_context", "capabilities", "artifacts"})
        self.assertNotIn("task", vars(model))
        self.assertNotIn("supported_runtimes", vars(model))
        self.assertNotIn("supported_backends", vars(model))
        self.assertNotIn("quantizations", vars(model))
        self.assertNotEqual(model.identity.model_id, "Qwen3 Demo")

    def test_no_inference_from_model_name(self):
        model = ea.to_model(spec(name="Qwen3-Coder", architecture="Unknown"))
        self.assertIsNone(model.architecture.architecture)
        self.assertIsNone(model.capabilities.code_generation)

    def test_task_never_produces_a_capability(self):
        self.assertIsNone(ea.to_model(spec(task="coding"))
                          .capabilities.code_generation)


class ArtifactAdapterTests(unittest.TestCase):
    def test_explicit_format_is_copied(self):
        self.assertEqual(ea.to_artifact(artifact()).format, "GGUF")

    def test_unknown_or_empty_format_is_none(self):
        self.assertIsNone(ea.to_artifact(artifact(format="Unknown")).format)
        self.assertIsNone(ea.to_artifact(artifact(format="")).format)

    def test_identifier_is_always_none(self):
        adapted = ea.to_artifact(artifact(model_id="Qwen3 Demo"))
        self.assertIsNone(adapted.identifier)
        self.assertIsNone(ea.to_artifact(artifact()).identifier)

    def test_quantization_label_never_implies_precision(self):
        adapted = ea.to_artifact(artifact(quantization="Q4_K_M"))
        self.assertIsNone(adapted.precision.name)
        self.assertIsNone(adapted.precision.bits)
        self.assertIs(adapted.quantization.status, QuantizationStatus.UNKNOWN)
        self.assertIsNone(adapted.quantization.method)

    def test_size_bytes_is_copied_as_storage_only(self):
        self.assertEqual(ea.to_artifact(artifact()).storage_size_bytes, 1234)

    def test_format_is_never_inferred_from_quantization(self):
        self.assertIsNone(
            ea.to_artifact(artifact(format="Unknown",
                                    quantization="Q4_K_M")).format)


class RuntimeResolutionTests(unittest.TestCase):
    REGISTRY = ik.INITIAL_KNOWLEDGE_REGISTRY

    def test_llamacpp_resolves_by_exact_membership(self):
        subject = ea.resolve_runtime(
            self.REGISTRY,
            capability("llama.cpp CLI", "llama.cpp / llama.app", "llama.cpp"))
        self.assertIs(subject, ik.LLAMACPP)

    def test_ollama_resolves_by_exact_canonical_id(self):
        subject = ea.resolve_runtime(self.REGISTRY, capability("ollama"))
        self.assertIs(subject, ik.OLLAMA)

    def test_composite_alias_alone_never_resolves(self):
        with self.assertRaises(ValueError):
            ea.resolve_runtime(
                self.REGISTRY,
                capability("llama.cpp / llama.app"))

    def test_display_name_alone_never_resolves(self):
        with self.assertRaises(ValueError):
            ea.resolve_runtime(self.REGISTRY, capability("llama.cpp CLI"))

    def test_no_match_is_rejected(self):
        with self.assertRaises(ValueError):
            ea.resolve_runtime(self.REGISTRY, capability("vLLM", "vllm"))

    def test_multiple_matches_are_rejected(self):
        registry = KnowledgeRegistry(())
        with self.assertRaises(ValueError):
            ea.resolve_runtime(registry, capability("ollama"))

    def test_no_fuzzy_no_case_folding_no_substring(self):
        for name in ("LLAMA.CPP", "Llama.cpp", "llama", "lama.cpp", "ollama.",
                     "OLLAMA"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    ea.resolve_runtime(self.REGISTRY, capability(name))

    def test_registry_and_scope_stay_untouched(self):
        before = self.REGISTRY.entries
        ea.resolve_runtime(self.REGISTRY, capability("llama.cpp"))
        self.assertEqual(self.REGISTRY.entries, before)


class ScopeAndBackendTests(unittest.TestCase):
    def test_default_scope_is_exactly_empty(self):
        self.assertEqual(ea.runtime_scope(), KnowledgeScope())

    def test_explicit_scope_is_preserved_untouched(self):
        requested = KnowledgeScope(platform="linux")
        self.assertIs(ea.runtime_scope(requested), requested)

    def test_version_is_never_turned_into_scope(self):
        context, _ = ea.build_evaluation_context(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            capability("llama.cpp CLI", "llama.cpp"))
        self.assertEqual(context.runtime.name, "llama.cpp")

    def test_backend_table_is_exact_and_closed(self):
        for raw, canonical in ea.CANONICAL_BACKENDS:
            self.assertEqual(ea.canonize_backend(raw), canonical)
        self.assertEqual(ea.canonize_backend(None), None)
        for unknown in ("cpu", "CPUX", "cpu ", " Metal", "vulkan", "NVIDIA",
                        "opencl", "BLAS", "Cuda", "rocm-hip"):
            with self.subTest(backend=unknown):
                self.assertIsNone(ea.canonize_backend(unknown))


class ContextAssemblyTests(unittest.TestCase):
    REGISTRY = ik.INITIAL_KNOWLEDGE_REGISTRY

    def test_runtime_knowledge_comes_from_b97(self):
        context, projection = ea.build_evaluation_context(
            self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"))
        self.assertIs(context.runtime,
                      projection.runtime_knowledge)
        self.assertEqual(context.runtime.supported_backends,
                         ("cpu", "cuda", "hip"))
        self.assertEqual(context.runtime.supported_formats, ("gguf",))

    def test_backend_canonicalization_and_unknown(self):
        context, _ = ea.build_evaluation_context(
            self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"),
            backend="CPU")
        self.assertEqual(context.backend, "cpu")
        context, _ = ea.build_evaluation_context(
            self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"),
            backend="Metal")
        self.assertIsNone(context.backend)

    def test_required_capabilities_are_passed_through(self):
        context, _ = ea.build_evaluation_context(
            self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"),
            required_capabilities=("code_generation",))
        self.assertEqual(context.required_capabilities, ("code_generation",))

    def test_unknown_required_capability_is_rejected_by_b93(self):
        with self.assertRaises(ValueError):
            ea.build_evaluation_context(
                self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"),
                required_capabilities=("telepathy",))

    def test_hardware_is_always_none(self):
        context, _ = ea.build_evaluation_context(
            self.REGISTRY, capability("ollama"))
        self.assertIsNone(context.hardware)

    def test_projection_keeps_unknown_traceability(self):
        _, projection = ea.build_evaluation_context(
            self.REGISTRY, capability("ollama"))
        self.assertEqual(
            sorted(row.object.canonical_id
                   for row in projection.excluded_unknown),
            ["cuda", "llama", "sycl"])
        self.assertNotIn("cuda",
                         projection.runtime_knowledge.unsupported_backends)
        self.assertNotIn("cuda",
                         projection.runtime_knowledge.supported_backends)

    def test_runtime_capability_never_becomes_model_capability(self):
        model = ea.to_model(spec())
        for name in ("text_generation", "code_generation", "vision",
                     "embeddings", "tool_use"):
            self.assertIsNone(getattr(model.capabilities, name))

    def test_no_evaluate_call_during_build(self):
        self.assertEqual(ea.build_evaluation_context(
            self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"))[0],
            ea.build_evaluation_context(
                self.REGISTRY, capability("llama.cpp CLI", "llama.cpp"))[0])


class PostEvaluationTests(unittest.TestCase):
    def test_evaluate_is_invocable_and_deterministic(self):
        capability_ = capability("llama.cpp CLI", "llama.cpp")
        context, _ = ea.build_evaluation_context(
            ik.INITIAL_KNOWLEDGE_REGISTRY, capability_, backend="CPU")
        result = evaluate(ea.to_model(spec()), ea.to_artifact(artifact()),
                          context)
        again = evaluate(ea.to_model(spec()), ea.to_artifact(artifact()),
                         context)
        self.assertEqual(result, again)
        # Format is case-sensitively exact ("GGUF" != "gguf") → UNKNOWN; this
        # honest limitation is documented in the B9.8 design (§12).
        self.assertEqual(result.checks[1].status.value, "unknown")
        self.assertEqual(result.checks[4].status.value, "passed")
        # Honest degradation: identity/architecture/capabilities are unknown.
        self.assertEqual(result.status.value, "insufficient_evidence")

    def test_unknown_backend_degrades_without_unsupported(self):
        context, _ = ea.build_evaluation_context(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            capability("llama.cpp CLI", "llama.cpp"), backend="Metal")
        result = evaluate(ea.to_model(spec()), ea.to_artifact(artifact()),
                          context)
        backend_check = result.checks[4]
        self.assertEqual(backend_check.status.value, "unknown")
        self.assertNotEqual(backend_check.status.value, "failed")


class DeterminismAndImmutabilityTests(unittest.TestCase):
    def test_repeated_calls_are_equal(self):
        first = (ea.to_model(spec()), ea.to_artifact(artifact()))
        second = (ea.to_model(spec()), ea.to_artifact(artifact()))
        self.assertEqual(first, second)

    def test_outputs_are_frozen(self):
        model = ea.to_model(spec())
        adapted = ea.to_artifact(artifact())
        with self.assertRaises(Exception):
            model.max_context = 1
        with self.assertRaises(Exception):
            adapted.format = "X"

    def test_inputs_are_not_mutated(self):
        original = spec()
        before = dict(vars(original))
        artifact_spec = artifact()
        artifact_before = dict(vars(artifact_spec))
        ea.to_model(original)
        ea.to_artifact(artifact_spec)
        self.assertEqual(vars(original), before)
        self.assertEqual(vars(artifact_spec), artifact_before)


if __name__ == "__main__":
    unittest.main()
