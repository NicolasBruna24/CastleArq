# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from castlearq.admission import EvaluationAdmission
from castlearq.compatibility import CompatibilityResult, CompatibilityStatus
from castlearq.execution import (
    ArtifactPreflightError,
    ExecutionResult,
    ExecutionTarget,
    PreflightErrorCode,
)
from castlearq.execution_preparation import (
    AdmissionDeniedError,
    ExecutionPreparation,
    ExecutionPreparationDependencies,
    PreparationFailureError,
    prepare_execution,
)
from castlearq.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from castlearq.models import ArtifactSpec, ModelSpec
from castlearq.run_service import (
    ExecuteAdmissionDeniedError,
    PreparationError,
    RunDependencies,
    RunOutcome,
    RunPreparationFailedError,
    prepare,
    run_once,
)
from castlearq.runner import ModelRunner
from castlearq.runtimes import (
    BackendStatus,
    PromptInputMode,
    RuntimeCapability,
    RuntimeStatus,
)
from castlearq.selection import RuntimeSelectionError, SelectionErrorCode
from castlearq.evaluate_compatibility import EvaluateModelCompatibilityResult, to_admission


def _admitting_evaluation():
    """Evaluation result that projects to an admitting Admission via to_admission()."""
    from unittest import mock

    strict_result = mock.Mock(status="compatible")
    evaluation = mock.Mock(result=strict_result)
    return EvaluateModelCompatibilityResult(
        model_id="test-model",
        artifact=None,
        runtime="llama.cpp CLI",
        capability=None,
        evaluation=evaluation,
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


class ExecutionPreparationTests(unittest.TestCase):
    def setUp(self):
        self.admission = to_admission(_admitting_evaluation())
        self.model = ModelSpec(name="test model", id="test-model")
        self.artifact = ArtifactSpec(
            model_id="test-model",
            source="test",
            repository="test/repo",
            filename="model.gguf",
            format="GGUF",
        )
        self.capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/llama",
            version="test",
            supported_formats=("GGUF",),
            supported_backends=("CPU", "Vulkan"),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
        )
        self.store = Mock()
        self.hardware = HardwareSnapshot(
            operating_system="test",
            architecture="test",
            cpu=CPUInfo(),
            memory=MemoryInfo(total_bytes=1024),
            gpus=[GPUInfo(backends=["Vulkan"])],
        )
        self.compatibility = CompatibilityResult(
            model=self.model,
            status=CompatibilityStatus.COMPATIBLE,
            score=100,
            reasons=(),
            warnings=("compatibility warning",),
            estimated_memory_bytes=1024,
            memory_is_estimate=True,
            recommended_quantization=None,
            recommended_runtime="llama.cpp / llama.app",
            recommended_backend="Vulkan",
        )
        self.executable = Mock()
        self.target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        self.events = []

        class Preflight:
            def validate(inner_self, artifact):
                self.events.append(("preflight", artifact))
                return self.executable

        class Selector:
            def select(
                inner_self,
                compatibility,
                capability,
                executable_artifact,
                *,
                requested_backend=None,
            ):
                self.events.append(
                    (
                        "select",
                        compatibility,
                        capability,
                        executable_artifact,
                        requested_backend,
                    )
                )
                return SimpleNamespace(
                    target=self.target, warnings=("selection warning",)
                )

        self.dependencies = ExecutionPreparationDependencies(
            hardware_provider=lambda: self.events.append("hardware")
            or self.hardware,
            runtime_status_provider=lambda capability: self.events.append(
                ("runtimes", capability)
            )
            or [
                RuntimeStatus(
                    name="llama.cpp / llama.app",
                    installed=True,
                    available=True,
                    gpu_backend_detected=False,
                    supported_backends=("CPU", "Vulkan"),
                )
            ],
            backend_provider=lambda gpu_backends: self.events.append(
                ("backends", gpu_backends)
            )
            or [BackendStatus("Vulkan", True)],
            compatibility_provider=lambda hardware, runtimes, backends, model: self.events.append(
                ("compatibility", hardware, runtimes, backends, model)
            )
            or self.compatibility,
            preflight_factory=lambda store: self.events.append(
                ("preflight_factory", store)
            )
            or Preflight(),
            selector_factory=lambda: self.events.append("selector_factory")
            or Selector(),
        )

    def test_prepare_execution_uses_injected_providers_in_order(self):
        preparation = prepare_execution(
            self.model,
            self.artifact,
            self.capability,
            self.store,
            admission=self.admission,
            requested_backend="CPU",
            dependencies=self.dependencies,
        )

        self.assertIsInstance(preparation, ExecutionPreparation)
        self.assertIs(preparation.executable_artifact, self.executable)
        self.assertIs(preparation.target, self.target)
        self.assertEqual(
            preparation.compatibility_warnings, ("compatibility warning",)
        )
        self.assertEqual(preparation.selection_warnings, ("selection warning",))
        self.assertEqual(
            [event if isinstance(event, str) else event[0] for event in self.events],
            [
                "hardware",
                "runtimes",
                "backends",
                "compatibility",
                "preflight_factory",
                "preflight",
                "selector_factory",
                "select",
            ],
        )
        self.assertEqual(
            self.events[2], ("backends", {"Vulkan"})
        )
        self.assertEqual(self.events[-1][-1], "CPU")

    def test_none_admission_denies_before_any_provider(self):
        with self.assertRaises(AdmissionDeniedError):
            prepare_execution(
                self.model,
                self.artifact,
                self.capability,
                self.store,
                admission=None,
                dependencies=self.dependencies,
            )
        self.assertEqual(self.events, [])

    def test_preflight_failure_preserves_cause_and_compatibility_warnings(self):
        preflight_error = ArtifactPreflightError(
            PreflightErrorCode.MISSING_ARTIFACT, "missing"
        )
        dependencies = ExecutionPreparationDependencies(
            hardware_provider=self.dependencies.hardware_provider,
            runtime_status_provider=self.dependencies.runtime_status_provider,
            backend_provider=self.dependencies.backend_provider,
            compatibility_provider=self.dependencies.compatibility_provider,
            preflight_factory=lambda store: SimpleNamespace(
                validate=Mock(side_effect=preflight_error)
            ),
            selector_factory=self.dependencies.selector_factory,
        )

        with self.assertRaises(PreparationFailureError) as caught:
            prepare_execution(
                self.model,
                self.artifact,
                self.capability,
                self.store,
                admission=self.admission,
                dependencies=dependencies,
            )
        self.assertIs(caught.exception.__cause__, preflight_error)
        self.assertEqual(
            caught.exception.compatibility_warnings, ("compatibility warning",)
        )

    def test_run_service_reexports_preparation_type_and_maps_neutral_errors(self):
        from castlearq import run_service

        self.assertIs(run_service.ExecutionPreparation, ExecutionPreparation)
        self.assertIs(run_service.EvaluationAdmission, EvaluationAdmission)

        admission_error = AdmissionDeniedError("denied")
        with patch(
            "castlearq.run_service.prepare_execution",
            side_effect=admission_error,
        ):
            with self.assertRaises(ExecuteAdmissionDeniedError) as caught:
                prepare(
                    self.model,
                    self.artifact,
                    self.capability,
                    self.store,
                    admission=self.admission,
                )
        self.assertEqual(str(caught.exception), "denied")
        self.assertIs(caught.exception.__cause__, admission_error)

        preparation_error = PreparationFailureError(
            "cannot prepare",
            compatibility_warnings=("compat",),
            selection_warnings=("selection",),
        )
        with patch(
            "castlearq.run_service.prepare_execution",
            side_effect=preparation_error,
        ):
            with self.assertRaises(PreparationError) as caught:
                prepare(
                    self.model,
                    self.artifact,
                    self.capability,
                    self.store,
                    admission=self.admission,
                )
        self.assertEqual(str(caught.exception), "cannot prepare")
        self.assertEqual(caught.exception.warnings, ("compat", "selection"))
        self.assertIs(caught.exception.__cause__, preparation_error)

    def test_run_service_none_admission_still_denies_before_preflight(self):
        with patch("castlearq.run_service.ArtifactExecutionPreflight") as preflight:
            with patch("castlearq.run_service.RuntimeBackendSelector") as selector:
                with self.assertRaises(ExecuteAdmissionDeniedError):
                    prepare(
                        self.model,
                        self.artifact,
                        self.capability,
                        self.store,
                        admission=None,
                    )
        preflight.assert_not_called()
        selector.assert_not_called()

    def test_selector_error_is_translated_with_cause_and_warnings(self):
        selection_error = RuntimeSelectionError(
            SelectionErrorCode.BACKEND_UNSUPPORTED, "backend unavailable"
        )

        class FailingSelector:
            def select(self, *args, **kwargs):
                raise selection_error

        dependencies = ExecutionPreparationDependencies(
            hardware_provider=self.dependencies.hardware_provider,
            runtime_status_provider=self.dependencies.runtime_status_provider,
            backend_provider=self.dependencies.backend_provider,
            compatibility_provider=self.dependencies.compatibility_provider,
            preflight_factory=self.dependencies.preflight_factory,
            selector_factory=FailingSelector,
        )
        with self.assertRaises(PreparationFailureError) as caught:
            prepare_execution(
                self.model,
                self.artifact,
                self.capability,
                self.store,
                admission=self.admission,
                dependencies=dependencies,
            )
        self.assertIs(caught.exception.__cause__, selection_error)
        self.assertEqual(
            caught.exception.compatibility_warnings, ("compatibility warning",)
        )

    def test_run_once_preserves_success_projection_and_requested_backend(self):
        class TestRunner(ModelRunner):
            def run(self, executable_artifact, target, request):
                raise NotImplementedError

        runner = TestRunner()
        runner.run = Mock(
            return_value=ExecutionResult(
                success=True,
                exit_code=0,
                stdout="model output",
                stderr="",
                warnings=("runner warning",),
            )
        )
        preflight = Mock()
        preflight.validate.return_value = self.executable
        selector = Mock()
        selector.select.return_value = SimpleNamespace(
            target=self.target, warnings=("selection warning",)
        )
        dependencies = RunDependencies(
            model_store=self.store,
            models=(self.model,),
            capability=self.capability,
            runner=runner,
        )

        with patch("castlearq.run_service.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact
            )
            with patch("castlearq.run_service.detect_hardware", return_value=self.hardware):
                with patch("castlearq.run_service.detect_backends", return_value=[]):
                    with patch(
                        "castlearq.run_service.assess_model",
                        return_value=self.compatibility,
                    ):
                        with patch(
                            "castlearq.run_service.ArtifactExecutionPreflight",
                            return_value=preflight,
                        ):
                            with patch(
                                "castlearq.run_service.RuntimeBackendSelector",
                                return_value=selector,
                            ):
                                outcome = run_once(
                                    "test-model",
                                    "prompt",
                                    dependencies=dependencies,
                                    admission=self.admission,
                                    requested_backend="Vulkan",
                                )

        self.assertIsInstance(outcome, RunOutcome)
        self.assertEqual(outcome.model_id, "test-model")
        self.assertEqual(outcome.output, "model output")
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(
            outcome.warnings,
            (
                "compatibility warning",
                "selection warning",
                "runner warning",
            ),
        )
        selector.select.assert_called_once()
        self.assertEqual(
            selector.select.call_args.kwargs["requested_backend"], "Vulkan"
        )
        self.assertIs(runner.run.call_args.args[0], self.executable)
        self.assertIs(runner.run.call_args.args[1], self.target)
        self.assertEqual(runner.run.call_args.args[2].target, self.target)

    def test_run_once_maps_missing_admission_and_stops_before_preflight(self):
        dependencies = RunDependencies(
            model_store=self.store,
            models=(self.model,),
            capability=self.capability,
        )

        with patch("castlearq.run_service.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact
            )
            with patch(
                "castlearq.run_service.ArtifactExecutionPreflight"
            ) as preflight:
                with patch(
                    "castlearq.run_service.RuntimeBackendSelector"
                ) as selector:
                    with self.assertRaises(RunPreparationFailedError) as caught:
                        run_once(
                            "test-model",
                            "prompt",
                            dependencies=dependencies,
                            admission=None,
                        )

        self.assertIn("deny-by-default", str(caught.exception))
        preflight.assert_not_called()
        selector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
