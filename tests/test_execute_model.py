# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application tests for the Execute Model use case.

Every collaborator is a double: resolver, capability provider, compatibility
provider, preflight, selector and ModelRunner. No model runs, no artifact is
downloaded and no real hardware probe happens.
"""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path
from unittest import mock

from app import execute_model as em
from app.compatibility import CompatibilityResult, CompatibilityStatus
from app.execution import (
    ArtifactPreflightError,
    ExecutableArtifact,
    ExecutionErrorCode,
    ExecutionErrorInfo,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
    PreflightErrorCode,
)
from app.models import ArtifactSpec, ModelSpec
from app.runner import ModelRunner
from app.runtimes import PromptInputMode, RuntimeCapability
from app.selection import (
    RuntimeSelection,
    RuntimeSelectionError,
    SelectionErrorCode,
)

SOURCE = Path("app/execute_model.py").read_text(encoding="utf-8")


def _capability(**overrides):
    base = dict(
        name="llama.cpp CLI",
        executable_path="/usr/bin/fake",
        version="v1",
        supported_formats=("GGUF",),
        supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        reason=None,
        compatibility_names=("llama.cpp / llama.app",),
    )
    base.update(overrides)
    return RuntimeCapability(**base)


def _model(**overrides):
    base = dict(id="m1", name="M1")
    base.update(overrides)
    return ModelSpec(**base)


def _artifact(**overrides):
    base = dict(model_id="m1", source="hf", repository="repo", filename="a.gguf")
    base.update(overrides)
    return ArtifactSpec(**base)


def _compat(
    status=CompatibilityStatus.COMPATIBLE,
    warnings=(),
    backend="CPU",
    runtime="llama.cpp / llama.app",
):
    return CompatibilityResult(
        model=_model(),
        status=status,
        score=90,
        reasons=(),
        warnings=tuple(warnings),
        estimated_memory_bytes=None,
        memory_is_estimate=True,
        recommended_quantization=None,
        recommended_runtime=runtime,
        recommended_backend=backend,
    )


def _executable(artifact):
    return ExecutableArtifact(
        artifact=artifact,
        path=Path("/tmp/fake.gguf"),
        size_verified=True,
        checksum_verified=False,
    )



class _FakePreflight:
    def __init__(self, executable=None, error=None, order=None):
        self.executable = executable
        self.error = error
        self.calls = []
        self.order = order

    def validate(self, artifact):
        self.calls.append(artifact)
        if self.order is not None:
            self.order.append("preflight")
        if self.error is not None:
            raise self.error
        return self.executable


class _FakeSelector:
    def __init__(self, target=None, error=None, warnings=(), order=None):
        self.target = target or ExecutionTarget("llama.cpp CLI", "CPU")
        self.error = error
        self.warnings = tuple(warnings)
        self.calls = []
        self.order = order

    def select(self, compatibility, capability, executable_artifact):
        self.calls.append((compatibility, capability, executable_artifact))
        if self.order is not None:
            self.order.append("select")
        if self.error is not None:
            raise self.error
        return RuntimeSelection(self.target, self.warnings)


class _FakeRunner(ModelRunner):
    def __init__(self, result=None, order=None):
        self.result = (
            result if result is not None else ExecutionResult(True, 0, "ok", "")
        )
        self.calls = []
        self.order = order

    def run(self, executable_artifact, target, request):
        self.calls.append((executable_artifact, target, request))
        if self.order is not None:
            self.order.append("run")
        return self.result


class _Harness:
    """Wires every collaborator as a double and records the call order."""

    def __init__(
        self,
        *,
        model=None,
        artifact=None,
        capability=None,
        compatibility=None,
        preflight=None,
        selector=None,
        runner=None,
        resolution_error=None,
        deps_overrides=None,
    ):
        self.order = []
        self.model = model if model is not None else _model()
        self.artifact = artifact if artifact is not None else _artifact()
        self.resolution_error = resolution_error

        self.resolver = mock.Mock()
        self.resolver.resolve.side_effect = self._resolve

        self.capability = capability if capability is not None else _capability()
        self.capability_calls = []

        self.compatibility = (
            compatibility if compatibility is not None else _compat()
        )
        self.compatibility_calls = []

        self.preflight = (
            preflight
            if preflight is not None
            else _FakePreflight(_executable(self.artifact), order=self.order)
        )
        self.selector = (
            selector if selector is not None else _FakeSelector(order=self.order)
        )
        self.runner = runner if runner is not None else _FakeRunner(order=self.order)

        deps_kwargs = dict(
            model_store=mock.Mock(),
            models=(self.model,),
            capability_provider=self._capability_provider,
            compatibility_provider=self._compatibility_provider,
            preflight_factory=lambda store: self.preflight,
            selector=self.selector,
            runner=self.runner,
        )
        deps_kwargs.update(deps_overrides or {})
        self.deps = em.ExecuteModelDependencies(**deps_kwargs)

    def _resolve(self, model_id, **kwargs):
        self.order.append("resolve")
        self.resolve_kwargs = dict(kwargs, model_id=model_id)
        if self.resolution_error is not None:
            raise self.resolution_error
        return mock.Mock(model=self.model, artifact=self.artifact)

    def _capability_provider(self):
        self.order.append("capability")
        self.capability_calls.append(True)
        return self.capability

    def _compatibility_provider(self, model, capability):
        self.order.append("compatibility")
        self.compatibility_calls.append((model, capability))
        return self.compatibility

    def run(self, **kwargs):
        call_kwargs = {"model_id": "m1", "prompt": "hello"}
        call_kwargs.update(kwargs)
        with mock.patch.object(
            em, "ModelArtifactResolver", return_value=self.resolver
        ):
            return em.execute_model(dependencies=self.deps, **call_kwargs)

    def run_error(self, **kwargs):
        try:
            self.run(**kwargs)
        except Exception as error:  # noqa: BLE001 - contract assertion
            return error
        return None


class InputContractTests(unittest.TestCase):
    def test_signature_and_defaults(self):
        sig = inspect.signature(em.execute_model)
        self.assertEqual(
            list(sig.parameters)[:2], ["model_id", "prompt"]
        )
        for name in ("model_id", "prompt"):
            self.assertIs(sig.parameters[name].default, inspect.Parameter.empty)
            self.assertEqual(
                sig.parameters[name].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD
            )
        for name in (
            "quantization",
            "filename",
            "timeout_seconds",
            "backend_preference",
            "admission",
            "dependencies",
        ):
            self.assertEqual(
                sig.parameters[name].kind, inspect.Parameter.KEYWORD_ONLY
            )
            self.assertIsNone(sig.parameters[name].default)
        self.assertEqual(em.DEFAULT_EXECUTION_TIMEOUT_SECONDS, 600.0)

    def test_empty_model_id_rejected(self):
        for value in ("", "   ", None, 7):
            with self.subTest(value=value):
                h = _Harness()
                error = h.run_error(model_id=value)
                self.assertIsInstance(error, em.ExecutePreparationError)
                self.assertEqual(h.runner.calls, [])

    def test_empty_prompt_rejected(self):
        for value in ("", "   ", None, 7):
            with self.subTest(value=value):
                h = _Harness()
                error = h.run_error(prompt=value)
                self.assertIsInstance(error, em.ExecutePreparationError)
                self.assertEqual(h.runner.calls, [])

    def test_input_is_validated_before_any_collaborator(self):
        h = _Harness()
        h.run_error(prompt="  ")
        self.assertEqual(h.order, [])


class ResolutionTests(unittest.TestCase):
    def test_selectors_are_forwarded_to_resolver(self):
        h = _Harness()
        h.run(quantization="Q4_K_M", filename=None)
        self.assertEqual(
            h.resolve_kwargs,
            {"model_id": "m1", "quantization": "Q4_K_M", "filename": None},
        )

    def test_resolution_failure_is_preparation_failure(self):
        from app.resolver import ModelArtifactResolutionError

        h = _Harness(resolution_error=ModelArtifactResolutionError("no model"))
        error = h.run_error()
        self.assertIsInstance(error, em.ExecutePreparationError)
        self.assertEqual(str(error), "no model")
        self.assertEqual(h.runner.calls, [])
        self.assertEqual(h.capability_calls, [])

    def test_resolved_model_artifact_are_the_domain_inputs(self):
        h = _Harness()
        h.run()
        model, capability = h.compatibility_calls[0]
        self.assertIs(model, h.model)
        self.assertIs(capability, h.capability)
        self.assertIs(h.preflight.calls[0], h.artifact)

    def test_order_is_resolve_then_capability_then_gate(self):
        h = _Harness()
        h.run()
        self.assertEqual(
            h.order,
            ["resolve", "capability", "compatibility", "preflight", "select", "run"],
        )


class CapabilityTests(unittest.TestCase):
    def test_unavailable_capability_fails_closed(self):
        h = _Harness(capability=_capability(available=False, reason="not found"))
        error = h.run_error()
        self.assertIsInstance(error, em.ExecutePreparationError)
        self.assertIn("not found", str(error))
        self.assertEqual(h.compatibility_calls, [])
        self.assertEqual(h.runner.calls, [])

    def test_capability_without_executable_is_rejected(self):
        h = _Harness(
            capability=_capability(executable_path=None, available=False),
        )
        self.assertIsInstance(h.run_error(), em.ExecutePreparationError)

    def test_missing_capability_is_rejected(self):
        h = _Harness(capability=None)
        h.capability = None
        self.assertIsInstance(h.run_error(), em.ExecutePreparationError)

    def test_capability_is_fresh_per_invocation(self):
        h = _Harness()
        h.run()
        h.run()
        self.assertEqual(len(h.capability_calls), 2)
        self.assertEqual(len(h.preflight.calls), 2)
        self.assertEqual(len(h.runner.calls), 2)

    def test_admission_denial_happens_after_resolution(self):
        h = _Harness()
        error = h.run_error(
            admission=em.EvaluationAdmission(status="evaluated", verdict="incompatible")
        )
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)
        self.assertEqual(h.order, ["resolve", "capability"])


class AdmissionTests(unittest.TestCase):
    def test_no_admission_means_legacy_gate_applies(self):
        h = _Harness()
        result = h.run()
        self.assertTrue(result.success)
        self.assertEqual(len(h.compatibility_calls), 1)
        self.assertEqual(len(h.preflight.calls), 1)
        self.assertEqual(len(h.selector.calls), 1)
        self.assertEqual(len(h.runner.calls), 1)

    def test_evaluated_compatible_proceeds(self):
        h = _Harness()
        result = h.run(
            admission=em.EvaluationAdmission(status="evaluated", verdict="compatible")
        )
        self.assertTrue(result.success)
        self.assertEqual(len(h.runner.calls), 1)

    def test_evaluated_with_conditions_proceeds(self):
        h = _Harness()
        result = h.run(
            admission=em.EvaluationAdmission(
                status="evaluated", verdict="compatible_with_conditions"
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(len(h.runner.calls), 1)

    def test_verdict_enum_and_case_are_normalized(self):
        h = _Harness()
        result = h.run(
            admission=em.EvaluationAdmission(status="EVALUATED", verdict="Compatible")
        )
        self.assertTrue(result.success)

    def test_duck_typed_summary_is_accepted(self):
        h = _Harness()
        signal = mock.Mock(status="evaluated", verdict="compatible")
        result = h.run(admission=signal)
        self.assertTrue(result.success)

    def test_incompatible_denied(self):
        h = _Harness()
        error = h.run_error(
            admission=em.EvaluationAdmission(status="evaluated", verdict="incompatible")
        )
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)
        self.assertIsInstance(error, em.ExecutePreparationError)
        self.assertEqual(h.compatibility_calls, [])
        self.assertEqual(h.runner.calls, [])

    def test_insufficient_evidence_denies_by_default(self):
        h = _Harness()
        error = h.run_error(
            admission=em.EvaluationAdmission(
                status="evaluated", verdict="insufficient_evidence"
            )
        )
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)
        self.assertIn("insufficient_evidence", str(error))
        self.assertEqual(h.runner.calls, [])

    def test_missing_verdict_denies_by_default(self):
        h = _Harness()
        error = h.run_error(
            admission=em.EvaluationAdmission(status="evaluated")
        )
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)

    def test_blocked_never_authorizes(self):
        h = _Harness()
        error = h.run_error(admission=em.EvaluationAdmission(status="blocked"))
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)
        self.assertEqual(h.compatibility_calls, [])
        self.assertEqual(h.runner.calls, [])

    def test_unknown_status_denies(self):
        h = _Harness()
        error = h.run_error(
            admission=em.EvaluationAdmission(status="pending", verdict="compatible")
        )
        self.assertIsInstance(error, em.ExecuteAdmissionDeniedError)

    def test_admission_never_skips_revalidation(self):
        h = _Harness()
        h.run(
            admission=em.EvaluationAdmission(status="evaluated", verdict="compatible")
        )
        self.assertEqual(
            h.order,
            ["resolve", "capability", "compatibility", "preflight", "select", "run"],
        )


class LegacyCompatibilityGateTests(unittest.TestCase):
    def test_compatible_status_proceeds(self):
        h = _Harness(compatibility=_compat(CompatibilityStatus.COMPATIBLE))
        self.assertTrue(h.run().success)

    def test_marginal_status_proceeds(self):
        h = _Harness(compatibility=_compat(CompatibilityStatus.MARGINAL))
        self.assertTrue(h.run().success)

    def test_incompatible_status_stops_before_preflight(self):
        h = _Harness(
            compatibility=_compat(
                CompatibilityStatus.INCOMPATIBLE, warnings=("low memory",)
            )
        )
        error = h.run_error()
        self.assertIsInstance(error, em.ExecutePreparationError)
        self.assertEqual(error.warnings, ("low memory",))
        self.assertEqual(h.preflight.calls, [])
        self.assertEqual(h.selector.calls, [])
        self.assertEqual(h.runner.calls, [])

    def test_unknown_status_stops_before_preflight(self):
        h = _Harness(compatibility=_compat(CompatibilityStatus.UNKNOWN))
        self.assertIsInstance(h.run_error(), em.ExecutePreparationError)
        self.assertEqual(h.preflight.calls, [])


class PreflightTests(unittest.TestCase):
    def test_preflight_validates_the_freshly_resolved_artifact(self):
        h = _Harness()
        h.run()
        self.assertEqual(h.preflight.calls, [h.artifact])
        self.assertIs(h.runner.calls[0][0], h.preflight.executable)

    def test_preflight_failure_is_preparation_failure_with_warnings(self):
        error = ArtifactPreflightError(
            PreflightErrorCode.CHECKSUM_MISMATCH, "checksum mismatch"
        )
        h = _Harness(
            compatibility=_compat(warnings=("marginal memory",)),
            preflight=_FakePreflight(error=error),
        )
        raised = h.run_error()
        self.assertIsInstance(raised, em.ExecutePreparationError)
        self.assertEqual(str(raised), "checksum mismatch")
        self.assertEqual(raised.warnings, ("marginal memory",))
        self.assertEqual(h.selector.calls, [])
        self.assertEqual(h.runner.calls, [])

    def test_preflight_runs_on_every_invocation(self):
        h = _Harness()
        h.run()
        h.run()
        self.assertEqual(len(h.preflight.calls), 2)


class SelectionTests(unittest.TestCase):
    def test_selector_receives_compatibility_capability_and_executable(self):
        h = _Harness()
        h.run()
        compatibility, capability, executable = h.selector.calls[0]
        self.assertIs(compatibility, h.compatibility)
        self.assertIs(capability, h.capability)
        self.assertIs(executable, h.preflight.executable)

    def test_selected_target_is_used_in_the_request(self):
        target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        h = _Harness(selector=_FakeSelector(target=target))
        h.run()
        self.assertIs(h.runner.calls[0][1], target)
        self.assertIs(h.runner.calls[0][2].target, target)

    def test_selection_failure_is_preparation_failure(self):
        error = RuntimeSelectionError(
            SelectionErrorCode.BACKEND_UNSUPPORTED, "backend unsupported"
        )
        h = _Harness(selector=_FakeSelector(error=error))
        raised = h.run_error()
        self.assertIsInstance(raised, em.ExecutePreparationError)
        self.assertEqual(str(raised), "backend unsupported")
        self.assertEqual(h.runner.calls, [])

    def test_no_backend_preference_accepts_the_selector_outcome(self):
        target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        h = _Harness(selector=_FakeSelector(target=target))
        self.assertTrue(h.run().success)

    def test_matching_backend_preference_proceeds(self):
        h = _Harness()
        self.assertTrue(h.run(backend_preference="CPU").success)

    def test_mismatched_backend_preference_fails_closed(self):
        h = _Harness()
        raised = h.run_error(backend_preference="Vulkan")
        self.assertIsInstance(raised, em.ExecutePreparationError)
        self.assertIn("Vulkan", str(raised))
        self.assertEqual(len(h.selector.calls), 1)
        self.assertEqual(h.runner.calls, [])

    def test_preference_is_never_a_target_of_its_own(self):
        self.assertNotIn("ExecutionTarget", SOURCE)


class RequestAndRunnerTests(unittest.TestCase):
    def test_request_shape(self):
        h = _Harness()
        h.run()
        _, target, request = h.runner.calls[0]
        self.assertIsInstance(request, ExecutionRequest)
        self.assertIs(request.artifact, h.artifact)
        self.assertEqual(request.prompt, "hello")
        self.assertIs(request.target, target)
        self.assertEqual(request.timeout_seconds, 600.0)

    def test_custom_timeout_is_forwarded(self):
        h = _Harness()
        h.run(timeout_seconds=12.5)
        self.assertEqual(h.runner.calls[0][2].timeout_seconds, 12.5)

    def test_invalid_timeout_fails_before_the_runner(self):
        for value in (0, -1, float("inf"), True, "fast"):
            with self.subTest(value=value):
                h = _Harness()
                raised = h.run_error(timeout_seconds=value)
                self.assertIsInstance(raised, em.ExecutePreparationError)
                self.assertEqual(h.runner.calls, [])

    def test_missing_runner_is_a_preparation_failure(self):
        h = _Harness(deps_overrides={"runner": None})
        raised = h.run_error()
        self.assertIsInstance(raised, em.ExecutePreparationError)
        self.assertIn("ModelRunner", str(raised))

    def test_runner_must_be_a_model_runner(self):
        h = _Harness(deps_overrides={"runner": mock.Mock()})
        self.assertIsInstance(h.run_error(), em.ExecutePreparationError)

    def test_runner_called_once_with_executable_target_request(self):
        h = _Harness()
        h.run()
        self.assertEqual(len(h.runner.calls), 1)
        executable, target, request = h.runner.calls[0]
        self.assertIs(executable, h.preflight.executable)
        self.assertIs(target, h.selector.target)
        self.assertIs(request.target, h.selector.target)

    def test_result_is_returned_verbatim(self):
        expected = ExecutionResult(True, 0, "stdout", "stderr")
        h = _Harness(runner=_FakeRunner(expected))
        self.assertIs(h.run(), expected)

    def test_failure_result_is_returned_verbatim(self):
        expected = ExecutionResult(
            False,
            1,
            "",
            "boom",
            ExecutionErrorInfo(ExecutionErrorCode.TIMEOUT, "timed out"),
        )
        h = _Harness(runner=_FakeRunner(expected))
        result = h.run()
        self.assertIs(result, expected)
        self.assertFalse(result.success)

    def test_preparation_warnings_precede_runner_warnings_on_success(self):
        expected = ExecutionResult(
            True, 0, "stdout", "stderr", warnings=("C",)
        )
        h = _Harness(
            compatibility=_compat(warnings=("A",)),
            selector=_FakeSelector(warnings=("B",)),
            runner=_FakeRunner(expected),
        )
        result = h.run()
        self.assertIsNot(result, expected)
        self.assertTrue(result.success)
        self.assertEqual(result.warnings, ("A", "B", "C"))
        self.assertEqual(expected.warnings, ("C",))

    def test_preparation_warnings_precede_runner_warnings_on_failure(self):
        error = ExecutionErrorInfo(ExecutionErrorCode.PROCESS_FAILED, "boom")
        diagnostics = mock.sentinel.diagnostics
        runtime_metrics = mock.sentinel.runtime_metrics
        expected = ExecutionResult(
            False,
            7,
            "partial stdout",
            "runtime stderr",
            error,
            warnings=("runner A", "runner B"),
            diagnostics=diagnostics,
            runtime_metrics=runtime_metrics,
        )
        h = _Harness(
            compatibility=_compat(warnings=("compat A", "compat B")),
            selector=_FakeSelector(warnings=("selection A",)),
            runner=_FakeRunner(expected),
        )
        result = h.run()
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 7)
        self.assertEqual(result.stdout, "partial stdout")
        self.assertEqual(result.stderr, "runtime stderr")
        self.assertIs(result.error, error)
        self.assertIs(result.diagnostics, diagnostics)
        self.assertIs(result.runtime_metrics, runtime_metrics)
        self.assertEqual(
            result.warnings,
            ("compat A", "compat B", "selection A", "runner A", "runner B"),
        )

    def test_runner_warnings_without_preparation_warnings_are_verbatim(self):
        expected = ExecutionResult(True, 0, "", "", warnings=("runner",))
        h = _Harness(runner=_FakeRunner(expected))
        self.assertIs(h.run(), expected)

    def test_no_warnings_yields_empty_tuple(self):
        self.assertEqual(_Harness().run().warnings, ())

    def test_duplicate_warnings_are_preserved(self):
        expected = ExecutionResult(True, 0, "", "", warnings=("A",))
        h = _Harness(
            compatibility=_compat(warnings=("A", "A")),
            selector=_FakeSelector(warnings=("A",)),
            runner=_FakeRunner(expected),
        )
        self.assertEqual(h.run().warnings, ("A", "A", "A", "A"))

    def test_preparation_error_warnings_are_unchanged(self):
        h = _Harness(
            compatibility=_compat(
                CompatibilityStatus.INCOMPATIBLE, warnings=("A", "A")
            )
        )
        error = h.run_error()
        self.assertIsInstance(error, em.ExecutePreparationError)
        self.assertEqual(error.warnings, ("A", "A"))
        self.assertEqual(h.runner.calls, [])

    def test_runner_is_not_touched_when_preparation_fails(self):
        h = _Harness(compatibility=_compat(CompatibilityStatus.INCOMPATIBLE))
        h.run_error()
        self.assertEqual(h.runner.calls, [])


class FreshnessTests(unittest.TestCase):
    def test_every_invocation_re_resolves(self):
        h = _Harness()
        h.run()
        h.run()
        self.assertEqual(h.resolver.resolve.call_count, 2)
        self.assertEqual(len(h.compatibility_calls), 2)

    def test_nothing_is_cached_between_invocations(self):
        h = _Harness()
        h.run()
        h.order.clear()
        h.run()
        self.assertEqual(
            h.order,
            ["resolve", "capability", "compatibility", "preflight", "select", "run"],
        )


class DefaultCollaboratorTests(unittest.TestCase):
    def test_default_capability_provider_detects_fresh_capability(self):
        h = _Harness(deps_overrides={"capability_provider": None})
        with mock.patch.object(
            em, "detect_llama_capability", return_value=_capability()
        ) as detect:
            result = h.run()
        self.assertTrue(result.success)
        detect.assert_called_once_with()

    def test_default_compatibility_provider_uses_legacy_assessment(self):
        h = _Harness(deps_overrides={"compatibility_provider": None})
        with mock.patch.object(em, "detect_hardware") as hardware, mock.patch.object(
            em, "detect_backends", return_value=[]
        ) as backends, mock.patch.object(
            em, "assess_model", return_value=_compat()
        ) as assess:
            hardware.return_value = mock.Mock(gpus=[])
            result = h.run()
        self.assertTrue(result.success)
        backends.assert_called_once_with(detected_gpu_backends=set())
        args, kwargs = assess.call_args
        self.assertEqual(len(args), 4)
        self.assertIs(args[3], h.model)
        self.assertEqual(args[1][0].name, "llama.cpp / llama.app")
        self.assertIn("config", kwargs)

    def test_default_preflight_is_artifact_preflight_bound_to_the_store(self):
        h = _Harness(deps_overrides={"preflight_factory": None})
        with mock.patch.object(em, "ArtifactExecutionPreflight") as factory:
            factory.return_value.validate.return_value = _executable(h.artifact)
            result = h.run()
        self.assertTrue(result.success)
        factory.assert_called_once_with(h.deps.model_store)

    def test_default_selector_is_runtime_backend_selector(self):
        h = _Harness(deps_overrides={"selector": None})
        with mock.patch.object(em, "RuntimeBackendSelector") as selector_cls:
            selector_cls.return_value.select.return_value = RuntimeSelection(
                ExecutionTarget("llama.cpp CLI", "CPU")
            )
            result = h.run()
        self.assertTrue(result.success)
        selector_cls.assert_called_once_with()
        selector_cls.return_value.select.assert_called_once()


class IsolationTests(unittest.TestCase):
    def _imported_modules(self):
        modules = set()
        for node in ast.walk(ast.parse(SOURCE)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
                modules.add("app." + node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name)
                    modules.add("app." + alias.name)
        return modules

    def test_no_forbidden_imports(self):
        modules = self._imported_modules()
        for banned in (
            "subprocess",
            "app.run_service",
            "app.main",
            "app.api",
            "app.cli",
        ):
            self.assertNotIn(banned, modules)

    def _identifiers(self):
        names = set()
        for node in ast.walk(ast.parse(SOURCE)):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        return names

    def test_no_execution_or_runner_concretions(self):
        # No concrete runner, no process spawning, no shell execution anywhere
        # in the module's code (docstrings excluded by using the AST).
        names = self._identifiers()
        for banned in ("subprocess", "LlamaCppRunner", "Popen", "system"):
            self.assertNotIn(banned, names)
        # Never even mentioned in prose or comments.
        self.assertNotIn("LlamaCppRunner", SOURCE)

    def test_no_evaluation_dependencies(self):
        modules = self._imported_modules()
        for evaluation in (
            "app.evaluation_pipeline",
            "app.evaluation_composition",
            "app.evaluation_adapter",
            "app.compatibility_domain",
            "app.evaluate_compatibility",
            "app.application_wiring",
        ):
            self.assertNotIn(evaluation, modules)

    def test_module_binds_no_legacy_or_concrete_collaborators(self):
        self.assertFalse(hasattr(em, "run_service"))
        self.assertFalse(hasattr(em, "LlamaCppRunner"))
        self.assertFalse(hasattr(em, "api"))
        self.assertFalse(hasattr(em, "cli"))

    def test_runner_dependency_is_the_abstraction(self):
        field = em.ExecuteModelDependencies.__dataclass_fields__["runner"]
        self.assertEqual(field.type, "ModelRunner | None")


if __name__ == "__main__":
    unittest.main()
