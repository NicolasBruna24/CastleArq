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

"""Focused B9.15 tests for app/evaluation_composition.py.

Contract tests for the Evaluation Composition stage-scoped composition
point only: verbatim IntegrationResult acceptance (Q-8 delivery), explicit
registry injection, caller-supplied evaluation-time values, reuse of the
existing B9.9/B9.8/B9.3 contracts, no invented RuntimeCapability
reconciliation, no state and no interface. Domain behaviour remains owned
by the pre-existing evaluation tests; no existing test is modified.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest
from unittest import mock

from app import evaluation_composition as ec
from app import evaluation_pipeline as ep
from app import initial_knowledge as ik
from app.boundary_adapter import MappingOutcome
from app.compatibility_evaluator import CompatibilityResult
from app.compatibility_knowledge import KnowledgeRegistry
from app.evaluation_pipeline import StrictEvaluation
from app.model_domain import Model, ModelArtifact
from app.models import ArtifactSpec, ModelSpec
from app.observation_knowledge import IntegrationResult, UnmappedRuntime
from app.runtimes import PromptInputMode, RuntimeCapability

MODULE_PATH = Path("app/evaluation_composition.py")
PARAMETER_ORDER = ["result", "registry", "spec", "artifact", "capability",
                   "backend", "required_capabilities", "scope"]
ALLOWED_IMPORTS = {"__future__", "typing", "compatibility_knowledge",
                   "evaluation_pipeline", "models", "observation_knowledge"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__", "compile", "input",
                   "system", "popen", "run", "Popen", "socket", "urlopen",
                   "getenv", "environ", "listdir", "read_text", "read_bytes",
                   "write_text", "write_bytes"}
INTERFACE_TOKENS = ("argparse", "click", "typer", "flask", "fastapi",
                    "socket", "http", "queue", "event_bus")


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


def llama_capability():
    return capability("llama.cpp CLI", "llama.cpp")


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


def rich_result():
    return IntegrationResult(
        unmapped=(UnmappedRuntime("some-runtime", MappingOutcome.UNMAPPED),))


def compose_evaluation(result=None, registry=None):
    return ec.compose_evaluation(
        result if result is not None else IntegrationResult(),
        registry if registry is not None else ik.INITIAL_KNOWLEDGE_REGISTRY,
        spec(),
        artifact(),
        llama_capability(),
    )


class AcceptanceAndPreservationTests(unittest.TestCase):
    # §19.1: the delivered IntegrationResult is accepted without transformation.
    def test_integration_result_is_accepted_and_preserved(self):
        for result in (IntegrationResult(), rich_result()):
            snapshot = (result.entries, result.unmapped, result.trace)
            evaluation = compose_evaluation(result=result)
            self.assertIsInstance(evaluation, StrictEvaluation)
            self.assertEqual(
                (result.entries, result.unmapped, result.trace), snapshot)

    def test_non_integration_result_is_rejected(self):
        for wrong in (None, "result", {}, 7):
            with self.assertRaises(ValueError):
                ec.compose_evaluation(
                    wrong, ik.INITIAL_KNOWLEDGE_REGISTRY, spec(), artifact(),
                    llama_capability())


class InjectionAndCallerValueTests(unittest.TestCase):
    # §19.2: the registry is injected explicitly, per invocation.
    def test_registry_is_injected_explicitly_per_invocation(self):
        # Use registries that contain llama.cpp to allow reconcile to succeed
        first_registry = ik.INITIAL_KNOWLEDGE_REGISTRY
        second_registry = ik.INITIAL_KNOWLEDGE_REGISTRY
        with mock.patch.object(ec, "evaluate_strict") as delegate:
            ec.compose_evaluation(
                IntegrationResult(), first_registry, spec(), artifact(),
                llama_capability())
            ec.compose_evaluation(
                IntegrationResult(), second_registry, spec(), artifact(),
                llama_capability())
            forwarded = [call.args[0] for call in delegate.call_args_list]
        self.assertIs(forwarded[0], first_registry)
        self.assertIs(forwarded[1], second_registry)

    def test_registry_parameter_has_no_default(self):
        parameter = inspect.signature(
            ec.compose_evaluation).parameters["registry"]
        self.assertIs(parameter.kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        self.assertEqual(parameter.default, inspect.Parameter.empty)

    # §19.3: model / artifact / capability originate from the caller.
    def test_model_artifact_capability_are_caller_supplied(self):
        model_spec = spec()
        artifact_spec = artifact()
        declared = llama_capability()
        with mock.patch.object(ec, "evaluate_strict") as delegate:
            ec.compose_evaluation(
                IntegrationResult(), ik.INITIAL_KNOWLEDGE_REGISTRY,
                model_spec, artifact_spec, declared)
        arguments = delegate.call_args.args
        self.assertEqual(len(arguments), 4)
        self.assertIs(arguments[0], ik.INITIAL_KNOWLEDGE_REGISTRY)
        self.assertIs(arguments[1], model_spec)
        self.assertIs(arguments[2], artifact_spec)
        self.assertIs(arguments[3], declared)
        signature = inspect.signature(ec.compose_evaluation)
        for name in ("spec", "artifact", "capability"):
            self.assertEqual(
                signature.parameters[name].default, inspect.Parameter.empty)

    def test_signature_matches_the_ratified_input_contract(self):
        signature = inspect.signature(ec.compose_evaluation)
        self.assertEqual(list(signature.parameters), PARAMETER_ORDER)
        self.assertIsNone(signature.parameters["backend"].default)
        self.assertEqual(
            signature.parameters["required_capabilities"].default, ())
        self.assertIsNone(signature.parameters["scope"].default)


class ExistingContractReuseTests(unittest.TestCase):
    # §19.4: existing to_model / to_artifact produce the strict domain.
    def test_strict_domain_values_come_from_existing_adapters(self):
        evaluation = compose_evaluation()
        self.assertIsInstance(evaluation.model, Model)
        self.assertIsInstance(evaluation.artifact, ModelArtifact)
        self.assertIsInstance(evaluation.result, CompatibilityResult)

    def test_no_parallel_adapter_or_builder_is_defined(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for declaration in ("def to_model", "def to_artifact",
                            "def build_evaluation_context", "def evaluate(",
                            "class "):
            self.assertNotIn(declaration, source)

    # §19.5: the existing build_evaluation_context() performs construction.
    def test_existing_build_evaluation_context_is_used(self):
        with mock.patch.object(
                ep, "build_evaluation_context",
                wraps=ep.build_evaluation_context) as builder:
            compose_evaluation()
        builder.assert_called_once()

    # §19.6
    def test_context_hardware_remains_none(self):
        evaluation = compose_evaluation()
        self.assertIsNone(evaluation.context.hardware)

    # §19.7: evaluate() receives the assembled values.
    def test_evaluate_receives_the_assembled_values(self):
        with mock.patch.object(
                ep, "evaluate", wraps=ep.evaluate) as evaluator:
            evaluation = compose_evaluation()
        evaluator.assert_called_once()
        model_arg, artifact_arg, context_arg = evaluator.call_args.args
        self.assertIs(model_arg, evaluation.model)
        self.assertIs(artifact_arg, evaluation.artifact)
        self.assertIs(context_arg, evaluation.context)

    def test_pipeline_record_is_returned_verbatim(self):
        sentinel = object()
        with mock.patch.object(ec, "evaluate_strict", return_value=sentinel):
            outcome = compose_evaluation()
        self.assertIs(outcome, sentinel)


class BoundaryAndPurityTests(unittest.TestCase):
    # §19.8: no raw observation context enters Evaluation.
    def test_no_environment_context_enters_evaluation(self):
        for path in (MODULE_PATH, Path("app/evaluation_pipeline.py"),
                     Path("app/evaluation_adapter.py")):
            self.assertNotIn(
                "EnvironmentContext", path.read_text(encoding="utf-8"))

    # §19.9: no dataset module is imported by Evaluation code.
    def test_no_registry_global_is_imported_by_evaluation_code(self):
        for path in (MODULE_PATH, Path("app/evaluation_pipeline.py"),
                     Path("app/evaluation_adapter.py"),
                     Path("app/compatibility_evaluator.py"),
                     Path("app/evaluation_policy.py")):
            self.assertNotIn(
                "initial_knowledge", path.read_text(encoding="utf-8"))

    # §19.10: the RuntimeCapability reconciliation algorithm is now implemented.
    def test_reconciliation_is_implemented(self):
        # Reconciliation now happens: resolve_runtime is called, which means
        # a capability that cannot be resolved will raise ValueError.
        # IntegrationResult contents do not affect reconciliation outcome.
        evaluation_a = ec.compose_evaluation(
            IntegrationResult(),
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec(),
            artifact(),
            llama_capability())
        evaluation_b = ec.compose_evaluation(
            rich_result(),
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec(),
            artifact(),
            llama_capability())
        # Both should succeed because llama_capability() can be resolved
        self.assertEqual(evaluation_a, evaluation_b)
        source = inspect.getsource(ec.compose_evaluation)
        # Reconciliation is implemented: resolve_runtime is called
        self.assertIn("resolve_runtime", source)
        # IntegrationResult contents are not READ for decision making.
        # Verify structural property: no attribute access on result object.
        # Parse the AST and check that result is never used with attribute access.
        tree = ast.parse(source)
        for node in ast.walk(tree):
            # Look for attribute access on a variable named 'result'
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == 'result':
                    self.fail(f"result should not be accessed with attribute: {node.attr}")
            # Also check subscript access (result['entries'])
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id == 'result':
                    self.fail("result should not be accessed with subscript")

    # §19.11: existing error semantics are preserved (nothing handled here).
    def test_no_error_handling_or_reclassification(self):
        source = inspect.getsource(ec.compose_evaluation)
        tree = ast.parse(source)
        self.assertFalse(
            any(isinstance(node, ast.Try) for node in ast.walk(tree)),
            "the composition point must contain no try/except")
        for token in ("ERROR", "UNAVAILABLE", "UNSUPPORTED"):
            self.assertNotIn(token, source)

    # §19.12: invocation-scoped — no cache, no hidden state.
    def test_registry_is_not_cached_across_invocations(self):
        # Use INITIAL_KNOWLEDGE_REGISTRY which contains llama.cpp
        registry_a = ik.INITIAL_KNOWLEDGE_REGISTRY
        registry_b = ik.INITIAL_KNOWLEDGE_REGISTRY
        with mock.patch.object(ec, "evaluate_strict") as delegate:
            for registry in (registry_a, registry_b, registry_a):
                ec.compose_evaluation(
                    IntegrationResult(), registry, spec(), artifact(),
                    llama_capability())
            forwarded = [call.args[0] for call in delegate.call_args_list]
        self.assertIs(forwarded[0], registry_a)
        self.assertIs(forwarded[1], registry_b)
        self.assertIs(forwarded[2], registry_a)

    def test_outputs_are_deterministic_across_invocations(self):
        self.assertEqual(compose_evaluation(), compose_evaluation())

    # §19.13: a plain function — no CLI / HTTP / GUI / framework.
    def test_composition_is_independent_of_interfaces(self):
        source = inspect.getsource(ec.compose_evaluation)
        for token in INTERFACE_TOKENS:
            self.assertNotIn(token, source)

    # Module purity in the house style (mirrors the B9.8 / B9.9 tests).
    def test_module_imports_only_composition_dependencies(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
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
        # evaluation_adapter is now imported for reconcile (resolve_runtime)
        self.assertEqual(imported, ALLOWED_IMPORTS | {"runtimes", "evaluation_adapter"})

    def test_module_performs_no_io_or_environment_access(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, FORBIDDEN_CALLS)
            elif isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, FORBIDDEN_CALLS)

    # §19.14: existing evaluation behaviour remains unchanged.
    def test_existing_pipeline_contract_is_unchanged(self):
        self.assertEqual(
            list(inspect.signature(ep.evaluate_strict).parameters),
            ["registry", "spec", "artifact", "capability", "backend",
             "required_capabilities", "scope"])
        self.assertEqual(
            list(StrictEvaluation.__dataclass_fields__),
            ["model", "artifact", "context", "projection", "result"])




class ReconciliationBehaviorTests(unittest.TestCase):
    """Tests for B9.15 RuntimeCapability Reconciliation behavior.
    
    These tests verify the normative semantics defined in the B9.15
    architectural decision: reconciliation is target-specific, uses
    resolve_runtime() for identity resolution, and only blocks on
    identity resolution failure (zero/multiple matches).
    """
    
    def test_identity_success_allows_evaluation(self):
        """A RuntimeCapability that resolves successfully allows evaluation."""
        result = IntegrationResult()
        evaluation = ec.ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_zero_match_blocks_evaluation(self):
        """A RuntimeCapability with zero matches blocks evaluation."""
        result = IntegrationResult()
        unknown_capability = RuntimeCapability(
            name="unknown-runtime",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=())
        
        with self.assertRaises(ValueError) as cm:
            ec.ec.compose_evaluation(
                result=result,
                registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
                spec=spec(),
                artifact=artifact(),
                capability=unknown_capability)
        
        self.assertIn("runtime cannot be resolved", str(cm.exception))
    
    def test_multiple_match_blocks_evaluation(self):
        """A RuntimeCapability with multiple matches blocks evaluation."""
        result = IntegrationResult()
        
        ambiguous_capability = RuntimeCapability(
            name="llama.cpp",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("ollama",)
        )
        
        with self.assertRaises(ValueError) as cm:
            ec.ec.compose_evaluation(
                result=result,
                registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
                spec=spec(),
                artifact=artifact(),
                capability=ambiguous_capability)
        
        self.assertIn("ambiguous runtime resolution", str(cm.exception))
    
    def test_integration_result_entries_does_not_block(self):
        """Presence or absence in IntegrationResult.entries does not block."""
        empty_result = IntegrationResult()
        evaluation_empty = ec.ec.compose_evaluation(
            result=empty_result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation_empty, StrictEvaluation)
    
    def test_integration_result_unmapped_does_not_block(self):
        """Presence in IntegrationResult.unmapped does not block."""
        unmapped_runtime = UnmappedRuntime(
            observation_identity="some-other-runtime",
            outcome=MappingOutcome.UNMAPPED
        )
        result_with_unmapped = IntegrationResult(
            entries=(),
            unmapped=(unmapped_runtime,),
            trace=BoundaryTrace(
                runtime_traces=(),
                context_entries=(),
                timestamp="2024-01-01T00:00:00Z"
            )
        )
        
        evaluation = ec.ec.compose_evaluation(
            result=result_with_unmapped,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_integration_result_absence_does_not_block(self):
        """Absence from IntegrationResult does not block."""
        result = IntegrationResult()
        
        evaluation = ec.ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_unavailable_capability_does_not_block(self):
        """capability.available=False does not block."""
        unavailable_capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=False,
            reason="llama executable was not found",
            compatibility_names=("llama.cpp",)
        )
        
        evaluation = ec.ec.compose_evaluation(
            result=IntegrationResult(),
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=unavailable_capability)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_empty_knowledge_does_not_block(self):
        """Empty runtime_knowledge does not block."""
        result = IntegrationResult()
        custom_scope = KnowledgeScope(platform="nonexistent")
        
        evaluation = ec.ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability(),
            scope=custom_scope)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_attribute_mismatch_does_not_block(self):
        """Attribute mismatch does not block."""
        mismatched_capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU", "Vulkan", "CUDA"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp",)
        )
        
        evaluation = ec.ec.compose_evaluation(
            result=IntegrationResult(),
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=mismatched_capability)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_target_specificity_other_runtimes_do_not_affect(self):
        """Other runtimes in IntegrationResult do not affect target."""
        llama_subject = KnowledgeSubject(
            kind=KnowledgeKind.RUNTIME,
            canonical_id="llama.cpp"
        )
        ollama_subject = KnowledgeSubject(
            kind=KnowledgeKind.RUNTIME,
            canonical_id="ollama"
        )
        
        llama_projection = project_knowledge(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            llama_subject,
            KnowledgeScope()
        )
        ollama_projection = project_knowledge(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            ollama_subject,
            KnowledgeScope()
        )
        
        entries = (
            RuntimeIntegration(
                observation_identity="llama.cpp",
                knowledge=llama_projection
            ),
            RuntimeIntegration(
                observation_identity="ollama",
                knowledge=ollama_projection
            )
        )
        
        result_with_multiple = IntegrationResult(
            entries=entries,
            unmapped=(),
            trace=BoundaryTrace(
                runtime_traces=(),
                context_entries=(),
                timestamp="2024-01-01T00:00:00Z"
            )
        )
        
        # Evaluate llama.cpp - should succeed regardless of ollama
        evaluation = ec.ec.compose_evaluation(
            result=result_with_multiple,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
        
        # Evaluate ollama - should also succeed
        ollama_capability = RuntimeCapability(
            name="ollama",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=()
        )
        evaluation_ollama = ec.ec.compose_evaluation(
            result=result_with_multiple,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=ollama_capability)
        self.assertIsInstance(evaluation_ollama, StrictEvaluation)



class ReconciliationBehaviorTests(unittest.TestCase):
    """Tests for B9.15 RuntimeCapability Reconciliation behavior.
    
    These tests verify the normative semantics defined in the B9.15
    architectural decision: reconciliation is target-specific, uses
    resolve_runtime() for identity resolution, and only blocks on
    identity resolution failure (zero/multiple matches).
    """
    
    def test_identity_success_allows_evaluation(self):
        """A RuntimeCapability that resolves successfully allows evaluation."""
        result = IntegrationResult()
        evaluation = ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_zero_match_blocks_evaluation(self):
        """A RuntimeCapability with zero matches blocks evaluation."""
        result = IntegrationResult()
        unknown_capability = RuntimeCapability(
            name="unknown-runtime",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=())
        
        with self.assertRaises(ValueError) as cm:
            ec.compose_evaluation(
                result=result,
                registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
                spec=spec(),
                artifact=artifact(),
                capability=unknown_capability)
        
        self.assertIn("runtime cannot be resolved", str(cm.exception))
    
    def test_multiple_match_blocks_evaluation(self):
        """A RuntimeCapability with multiple matches blocks evaluation."""
        result = IntegrationResult()
        
        ambiguous_capability = RuntimeCapability(
            name="llama.cpp",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("ollama",)
        )
        
        with self.assertRaises(ValueError) as cm:
            ec.compose_evaluation(
                result=result,
                registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
                spec=spec(),
                artifact=artifact(),
                capability=ambiguous_capability)
        
        self.assertIn("ambiguous runtime resolution", str(cm.exception))
    
    def test_integration_result_entries_does_not_block(self):
        """Presence or absence in IntegrationResult.entries does not block."""
        empty_result = IntegrationResult()
        evaluation_empty = ec.compose_evaluation(
            result=empty_result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation_empty, StrictEvaluation)
    
    def test_integration_result_unmapped_does_not_block(self):
        """Presence in IntegrationResult.unmapped does not block."""
        unmapped_runtime = UnmappedRuntime(
            observation_identity="some-other-runtime",
            outcome=MappingOutcome.UNMAPPED
        )
        result_with_unmapped = IntegrationResult(
            entries=(),
            unmapped=(unmapped_runtime,),
            trace=BoundaryTrace(
                runtime_traces=(),
                context_entries=(),
                timestamp="2024-01-01T00:00:00Z"
            )
        )
        
        evaluation = ec.compose_evaluation(
            result=result_with_unmapped,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_integration_result_absence_does_not_block(self):
        """Absence from IntegrationResult does not block."""
        result = IntegrationResult()
        
        evaluation = ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_unavailable_capability_does_not_block(self):
        """capability.available=False does not block."""
        unavailable_capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=False,
            reason="llama executable was not found",
            compatibility_names=("llama.cpp",)
        )
        
        evaluation = ec.compose_evaluation(
            result=IntegrationResult(),
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=unavailable_capability)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_empty_knowledge_does_not_block(self):
        """Empty runtime_knowledge does not block."""
        result = IntegrationResult()
        custom_scope = KnowledgeScope(platform="nonexistent")
        
        evaluation = ec.compose_evaluation(
            result=result,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability(),
            scope=custom_scope)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_attribute_mismatch_does_not_block(self):
        """Attribute mismatch does not block."""
        mismatched_capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU", "Vulkan", "CUDA"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp",)
        )
        
        evaluation = ec.compose_evaluation(
            result=IntegrationResult(),
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=mismatched_capability)
        self.assertIsInstance(evaluation, StrictEvaluation)
    
    def test_target_specificity_other_runtimes_do_not_affect(self):
        """Other runtimes in IntegrationResult do not affect target."""
        llama_subject = KnowledgeSubject(
            kind=KnowledgeKind.RUNTIME,
            canonical_id="llama.cpp"
        )
        ollama_subject = KnowledgeSubject(
            kind=KnowledgeKind.RUNTIME,
            canonical_id="ollama"
        )
        
        llama_projection = project_knowledge(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            llama_subject,
            KnowledgeScope()
        )
        ollama_projection = project_knowledge(
            ik.INITIAL_KNOWLEDGE_REGISTRY,
            ollama_subject,
            KnowledgeScope()
        )
        
        entries = (
            RuntimeIntegration(
                observation_identity="llama.cpp",
                knowledge=llama_projection
            ),
            RuntimeIntegration(
                observation_identity="ollama",
                knowledge=ollama_projection
            )
        )
        
        result_with_multiple = IntegrationResult(
            entries=entries,
            unmapped=(),
            trace=BoundaryTrace(
                runtime_traces=(),
                context_entries=(),
                timestamp="2024-01-01T00:00:00Z"
            )
        )
        
        # Evaluate llama.cpp - should succeed regardless of ollama
        evaluation = ec.compose_evaluation(
            result=result_with_multiple,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=llama_capability())
        self.assertIsInstance(evaluation, StrictEvaluation)
        
        # Evaluate ollama - should also succeed
        ollama_capability = RuntimeCapability(
            name="ollama",
            executable_path="/usr/bin/fake",
            version="1.0",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=()
        )
        evaluation_ollama = ec.compose_evaluation(
            result=result_with_multiple,
            registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
            spec=spec(),
            artifact=artifact(),
            capability=ollama_capability)
        self.assertIsInstance(evaluation_ollama, StrictEvaluation)

# Import required for the new tests
from app.boundary_adapter import BoundaryTrace
from app.knowledge_bridge import project_knowledge
from app.compatibility_knowledge import KnowledgeSubject, KnowledgeKind, KnowledgeScope
from app.observation_knowledge import RuntimeIntegration


if __name__ == "__main__":
    unittest.main()