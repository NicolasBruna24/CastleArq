from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from castlearq.admission import EvaluationAdmission
from castlearq.execute_model import (
    ExecuteAdmissionDeniedError,
    ExecuteModelDependencies,
    ExecutePreparationError,
    execute_model,
)
from castlearq.execution import (
    ExecutableArtifact,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
)
from castlearq.execution_preparation import AdmissionDeniedError
from castlearq.models import ArtifactSpec, ModelSpec
from castlearq.run_service import (
    RunDependencies,
    RunPreparationFailedError,
    run_once,
)
from castlearq.runner import ExecutionRunner, LlamaCppRunner, ModelRunner
from castlearq.runner_factory import (
    RunnerFactoryDependencies,
    RunnerFactoryError,
    create_runner,
)
from castlearq.runtimes import PromptInputMode, RuntimeCapability
from castlearq.sycl_runner import SyclLlamaRunner

from castlearq.evaluate_compatibility import EvaluateModelCompatibilityResult, to_admission


def _admitting_evaluation():
    """Evaluation result that projects to an admitting Admission via to_admission()."""
    from unittest import mock

    strict_result = mock.Mock(status="compatible")
    evaluation = mock.Mock(result=strict_result)
    return EvaluateModelCompatibilityResult(
        model_id="model-1",
        artifact=None,
        runtime="llama.cpp CLI",
        capability=None,
        evaluation=evaluation,
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


def _capability(
    backends: tuple[str, ...] = ("CPU", "Vulkan", "SYCL"),
    name: str = "llama.cpp CLI",
):
    return RuntimeCapability(
        name=name,
        executable_path="/usr/bin/llama",
        version="test",
        supported_formats=("GGUF",),
        supported_backends=backends,
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
    )


class _FakeRunner(ModelRunner):
    def __init__(self):
        self.calls = []

    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        self.calls.append((executable_artifact, target, request))
        return ExecutionResult(True, 0, "output", "")


class _ExternalRunner:
    def __init__(self):
        self.calls = []

    def run(
        self,
        executable_artifact: ExecutableArtifact,
        target: ExecutionTarget,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        self.calls.append((executable_artifact, target, request))
        return ExecutionResult(True, 0, "external output", "")


class RunnerFactoryTests(unittest.TestCase):
    def setUp(self):
        self.capability = _capability()
        self.sycl_capability = _capability(
            backends=("SYCL",), name="llama.cpp SYCL"
        )
        self.cpu_target = ExecutionTarget("llama.cpp CLI", "CPU")
        self.vulkan_target = ExecutionTarget("llama.cpp CLI", "Vulkan")
        self.sycl_target = ExecutionTarget("llama.cpp SYCL", "SYCL")

    def test_official_runners_implement_common_contract(self):
        self.assertTrue(issubclass(LlamaCppRunner, ExecutionRunner))
        self.assertTrue(issubclass(SyclLlamaRunner, ExecutionRunner))

    def test_constructs_cpu_runner(self):
        expected = _FakeRunner()
        factory = Mock(return_value=expected)
        runner = create_runner(
            self.capability,
            self.cpu_target,
            dependencies=RunnerFactoryDependencies(llama_cpp_factory=factory),
        )
        self.assertIs(runner, expected)
        factory.assert_called_once_with(self.capability)

    def test_constructs_vulkan_runner(self):
        expected = _FakeRunner()
        factory = Mock(return_value=expected)
        runner = create_runner(
            self.capability,
            self.vulkan_target,
            dependencies=RunnerFactoryDependencies(llama_cpp_factory=factory),
        )
        self.assertIs(runner, expected)
        factory.assert_called_once_with(self.capability)

    def test_cpu_and_vulkan_targets_select_llama_cpp_factory(self):
        expected = _FakeRunner()
        with patch(
            "castlearq.runner_factory.LlamaCppRunner", return_value=expected
        ) as factory:
            for target in (self.cpu_target, self.vulkan_target):
                with self.subTest(backend=target.backend):
                    self.assertIs(
                        create_runner(self.capability, target),
                        expected,
                    )
        self.assertEqual(factory.call_count, 2)
        factory.assert_called_with(self.capability)

    def test_constructs_sycl_runner(self):
        expected = SyclLlamaRunner("/sycl/llama", "/oneapi/setvars.sh")
        factory = Mock(return_value=expected)
        runner = create_runner(
            self.sycl_capability,
            self.sycl_target,
            dependencies=RunnerFactoryDependencies(sycl_factory=factory),
        )
        self.assertIs(runner, expected)
        factory.assert_called_once_with(self.sycl_capability)

    def test_sycl_target_uses_existing_builder(self):
        expected = SyclLlamaRunner("/sycl/llama", "/oneapi/setvars.sh")
        with patch(
            "castlearq.sycl_runner.build_sycl_runner",
            return_value=expected,
        ) as builder:
            runner = create_runner(self.sycl_capability, self.sycl_target)
        self.assertIs(runner, expected)
        builder.assert_called_once_with(capability=self.sycl_capability)

    def test_preserves_compatible_injected_runners(self):
        cpu_runner = _FakeRunner()
        sycl_runner = SyclLlamaRunner("/sycl/llama", "/oneapi/setvars.sh")
        self.assertIs(
            create_runner(
                self.capability, self.cpu_target, configured_runner=cpu_runner
            ),
            cpu_runner,
        )
        self.assertIs(
            create_runner(
                self.sycl_capability,
                self.sycl_target,
                configured_runner=sycl_runner,
            ),
            sycl_runner,
        )

    def test_preserves_structural_cpu_and_vulkan_runners(self):
        for target in (self.cpu_target, self.vulkan_target):
            with self.subTest(backend=target.backend):
                runner = _ExternalRunner()
                self.assertIs(
                    create_runner(
                        self.capability, target, configured_runner=runner
                    ),
                    runner,
                )

    def test_rejects_runner_incompatible_with_backend(self):
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.sycl_capability,
                self.sycl_target,
                configured_runner=_FakeRunner(),
            )
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.capability,
                self.cpu_target,
                configured_runner=SyclLlamaRunner(
                    "/sycl/llama", "/oneapi/setvars.sh"
                ),
            )
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.capability,
                self.cpu_target,
                configured_runner=object(),
            )

    def test_rejects_runner_without_callable_run(self):
        class NoRun:
            pass

        class NonCallableRun:
            run = "not callable"

        for runner in (NoRun(), NonCallableRun()):
            with self.subTest(runner=type(runner).__name__), self.assertRaises(
                RunnerFactoryError
            ):
                create_runner(
                    self.capability,
                    self.cpu_target,
                    configured_runner=runner,
                )

    def test_rejects_structural_runner_for_sycl_without_fallback(self):
        cpu_factory = Mock()
        sycl_factory = Mock()
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.sycl_capability,
                self.sycl_target,
                configured_runner=_ExternalRunner(),
                dependencies=RunnerFactoryDependencies(
                    llama_cpp_factory=cpu_factory,
                    sycl_factory=sycl_factory,
                ),
            )
        cpu_factory.assert_not_called()
        sycl_factory.assert_not_called()

    def test_rejects_capability_target_mismatch(self):
        cpu_factory = Mock()
        sycl_factory = Mock()
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.capability,
                self.sycl_target,
                dependencies=RunnerFactoryDependencies(
                    llama_cpp_factory=cpu_factory,
                    sycl_factory=sycl_factory,
                ),
            )
        cpu_factory.assert_not_called()
        sycl_factory.assert_not_called()

    def test_rejects_invalid_capability_type(self):
        with self.assertRaises(RunnerFactoryError):
            create_runner(object(), self.cpu_target)

    def test_rejects_target_backend_not_supported_by_capability(self):
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                _capability(backends=("CPU",)),
                self.vulkan_target,
            )

    def test_rejects_target_runtime_not_matching_capability(self):
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.capability,
                ExecutionTarget("llama.cpp SYCL", "CPU"),
            )

    def test_accepts_runtime_alias_declared_by_capability(self):
        capability = RuntimeCapability(
            name="llama.cpp CLI",
            executable_path="/usr/bin/llama",
            version="test",
            supported_formats=("GGUF",),
            supported_backends=("CPU",),
            prompt_input_modes=(PromptInputMode.ARGUMENT,),
            supports_one_shot=True,
            available=True,
            compatibility_names=("llama.cpp / llama.app",),
        )
        target = ExecutionTarget("llama.cpp / llama.app", "CPU")
        runner = _FakeRunner()
        self.assertIs(
            create_runner(
                capability,
                target,
                configured_runner=runner,
            ),
            runner,
        )

    def test_rejects_non_sycl_runtime_capability_for_sycl(self):
        capability = _capability(backends=("SYCL",))
        target = ExecutionTarget("llama.cpp CLI", "SYCL")
        with self.assertRaises(RunnerFactoryError):
            create_runner(capability, target)

    def test_rejects_unsupported_backend_without_fallback(self):
        cpu_factory = Mock()
        sycl_factory = Mock()
        with self.assertRaises(RunnerFactoryError):
            create_runner(
                self.capability,
                ExecutionTarget("llama.cpp CLI", "OpenVINO"),
                configured_runner=_FakeRunner(),
                dependencies=RunnerFactoryDependencies(
                    llama_cpp_factory=cpu_factory,
                    sycl_factory=sycl_factory,
                ),
            )
        cpu_factory.assert_not_called()
        sycl_factory.assert_not_called()

    def test_construction_error_is_neutral_and_has_no_backend_fallback(self):
        construction_error = ValueError("invalid runner configuration")
        cpu_factory = Mock(side_effect=construction_error)
        sycl_factory = Mock()
        with self.assertRaises(RunnerFactoryError) as caught:
            create_runner(
                self.capability,
                self.cpu_target,
                dependencies=RunnerFactoryDependencies(
                    llama_cpp_factory=cpu_factory,
                    sycl_factory=sycl_factory,
                ),
            )
        self.assertIs(caught.exception.__cause__, construction_error)
        cpu_factory.assert_called_once_with(self.capability)
        sycl_factory.assert_not_called()

    def test_sycl_construction_error_is_neutral(self):
        construction_error = OSError("SYCL configuration unavailable")
        factory = Mock(side_effect=construction_error)
        with self.assertRaises(RunnerFactoryError) as caught:
            create_runner(
                self.sycl_capability,
                self.sycl_target,
                dependencies=RunnerFactoryDependencies(sycl_factory=factory),
            )
        self.assertIs(caught.exception.__cause__, construction_error)
        factory.assert_called_once_with(self.sycl_capability)


class RunnerFactoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.model = ModelSpec(id="model-1", name="Model 1")
        self.artifact = ArtifactSpec(
            model_id="model-1",
            source="test",
            repository="test/repo",
            filename="model.gguf",
        )
        self.capability = _capability()
        self.executable = ExecutableArtifact(
            artifact=self.artifact,
            path=Path("/models/model.gguf"),
            size_verified=True,
            checksum_verified=False,
        )
        self.target = ExecutionTarget("llama.cpp CLI", "CPU")
        self.preparation = SimpleNamespace(
            executable_artifact=self.executable,
            target=self.target,
            compatibility_warnings=(),
            selection_warnings=(),
        )
        self.admission = to_admission(_admitting_evaluation())
        self.store = Mock()
        self.runner = _FakeRunner()

    def test_execute_model_constructs_runner_when_not_injected(self):
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.prepare_execution",
                return_value=self.preparation,
            ), patch(
                "castlearq.execute_model.create_runner",
                return_value=self.runner,
            ) as factory:
                result = execute_model(
                    "model-1",
                    "prompt",
                    backend_preference="CPU",
                    admission=self.admission,
                    dependencies=dependencies,
                )

        self.assertTrue(result.success)
        factory.assert_called_once_with(
            self.capability,
            self.target,
            configured_runner=None,
        )
        self.assertEqual(self.runner.calls[0][1], self.target)

    def test_execute_model_translates_factory_error_with_cause(self):
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
        )
        factory_error = RunnerFactoryError("runner construction failed")
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.prepare_execution",
                return_value=self.preparation,
            ), patch(
                "castlearq.execute_model.create_runner",
                side_effect=factory_error,
            ) as factory, self.assertRaises(ExecutePreparationError) as caught:
                execute_model(
                    "model-1",
                    "prompt",
                    admission=self.admission,
                    dependencies=dependencies,
                )

        self.assertIs(caught.exception.__cause__, factory_error)
        factory.assert_called_once()

    def test_execute_model_preserves_injected_runner(self):
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
            runner=self.runner,
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.prepare_execution",
                return_value=self.preparation,
            ), patch(
                "castlearq.execute_model.create_runner",
                wraps=create_runner,
            ) as factory:
                result = execute_model(
                    "model-1",
                    "prompt",
                    admission=self.admission,
                    dependencies=dependencies,
                )

        self.assertTrue(result.success)
        self.assertIs(factory.call_args.kwargs["configured_runner"], self.runner)

    def test_execute_model_rejects_structural_runner_without_nominal_contract(self):
        external_runner = _ExternalRunner()
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
            runner=external_runner,
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.prepare_execution",
                return_value=self.preparation,
            ), self.assertRaises(ExecutePreparationError):
                execute_model(
                    "model-1",
                    "prompt",
                    admission=self.admission,
                    dependencies=dependencies,
                )
        self.assertEqual(external_runner.calls, [])

    def test_execute_model_preserves_injected_sycl_runner(self):
        sycl_target = ExecutionTarget("llama.cpp SYCL", "SYCL")
        preparation = SimpleNamespace(
            executable_artifact=self.executable,
            target=sycl_target,
            compatibility_warnings=(),
            selection_warnings=(),
        )
        runner = SyclLlamaRunner("/sycl/llama", "/oneapi/setvars.sh")
        runner.run = Mock(return_value=ExecutionResult(True, 0, "sycl output", ""))
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: _capability(
                backends=("SYCL",), name="llama.cpp SYCL"
            ),
            runner=runner,
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.prepare_execution",
                return_value=preparation,
            ):
                result = execute_model(
                    "model-1",
                    "prompt",
                    backend_preference="SYCL",
                    admission=self.admission,
                    dependencies=dependencies,
                )

        self.assertEqual(result.stdout, "sycl output")
        runner.run.assert_called_once()

    def test_execute_model_denial_stops_preparation_and_sycl_construction(self):
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
            compatibility_provider=Mock(),
            preflight_factory=Mock(),
            selector=Mock(),
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.sycl_runner.build_sycl_runner"
            ) as sycl_builder, self.assertRaises(
                ExecuteAdmissionDeniedError
            ):
                execute_model(
                    "model-1",
                    "prompt",
                    admission=None,
                    dependencies=dependencies,
                )

        dependencies.compatibility_provider.assert_not_called()
        dependencies.preflight_factory.assert_not_called()
        dependencies.selector.select.assert_not_called()
        sycl_builder.assert_not_called()

    def test_execute_model_admission_precedes_runner_construction(self):
        dependencies = ExecuteModelDependencies(
            model_store=self.store,
            models=(self.model,),
            capability_provider=lambda: self.capability,
        )
        with patch("castlearq.execute_model.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact, imported=False, path=None
            )
            with patch(
                "castlearq.execute_model.create_runner"
            ) as factory, patch(
                "castlearq.execute_model.prepare_execution",
                side_effect=AdmissionDeniedError("denied"),
            ), self.assertRaises(ExecuteAdmissionDeniedError):
                execute_model(
                    "model-1",
                    "prompt",
                    admission=None,
                    dependencies=dependencies,
                )
        factory.assert_not_called()

    def test_run_once_uses_factory_and_preserves_requested_backend(self):
        runner = _FakeRunner()
        runner.run = Mock(return_value=ExecutionResult(True, 0, "output", ""))
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
            with patch(
                "castlearq.run_service.prepare", return_value=self.preparation
            ) as prepare_mock, patch(
                "castlearq.run_service.create_runner",
                wraps=create_runner,
            ) as factory:
                outcome = run_once(
                    "model-1",
                    "prompt",
                    dependencies=dependencies,
                    admission=self.admission,
                    requested_backend="CPU",
                )

        self.assertEqual(outcome.output, "output")
        self.assertEqual(
            prepare_mock.call_args.kwargs["requested_backend"], "CPU"
        )
        factory.assert_called_once()
        self.assertIs(
            factory.call_args.kwargs["configured_runner"],
            runner,
        )
        runner.run.assert_called_once()

    def test_run_once_preserves_external_cpu_and_vulkan_runners(self):
        for backend in ("CPU", "Vulkan"):
            with self.subTest(backend=backend):
                target = ExecutionTarget("llama.cpp CLI", backend)
                preparation = SimpleNamespace(
                    executable_artifact=self.executable,
                    target=target,
                    compatibility_warnings=(),
                    selection_warnings=(),
                )
                runner = _ExternalRunner()
                dependencies = RunDependencies(
                    model_store=self.store,
                    models=(self.model,),
                    capability=self.capability,
                    runner=runner,
                )
                with patch(
                    "castlearq.run_service.ModelArtifactResolver"
                ) as resolver:
                    resolver.return_value.resolve.return_value = SimpleNamespace(
                        model=self.model, artifact=self.artifact
                    )
                    with patch(
                        "castlearq.run_service.prepare",
                        return_value=preparation,
                    ), patch(
                        "castlearq.run_service.create_runner",
                        wraps=create_runner,
                    ) as factory:
                        outcome = run_once(
                            "model-1",
                            "prompt",
                            dependencies=dependencies,
                            admission=self.admission,
                            requested_backend=backend,
                        )

                self.assertEqual(outcome.output, "external output")
                self.assertIs(
                    factory.call_args.kwargs["configured_runner"], runner
                )
                self.assertEqual(len(runner.calls), 1)
                self.assertIs(runner.calls[0][1], target)

    def test_run_once_constructs_runner_when_not_injected(self):
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
                "castlearq.run_service.prepare", return_value=self.preparation
            ), patch(
                "castlearq.run_service.LlamaCppRunner",
                return_value=self.runner,
            ) as llama_runner:
                outcome = run_once(
                    "model-1",
                    "prompt",
                    dependencies=dependencies,
                    admission=self.admission,
                )

        self.assertEqual(outcome.output, "output")
        llama_runner.assert_called_once_with(self.capability)
        self.assertEqual(self.runner.calls[0][1], self.target)

    def test_run_once_dispatches_to_injected_sycl_runner(self):
        capability = _capability(backends=("SYCL",), name="llama.cpp SYCL")
        target = ExecutionTarget("llama.cpp SYCL", "SYCL")
        preparation = SimpleNamespace(
            executable_artifact=self.executable,
            target=target,
            compatibility_warnings=(),
            selection_warnings=(),
        )
        runner = SyclLlamaRunner("/sycl/llama", "/oneapi/setvars.sh")
        runner.run = Mock(return_value=ExecutionResult(True, 0, "sycl", ""))
        dependencies = RunDependencies(
            model_store=self.store,
            models=(self.model,),
            capability=capability,
            runner=runner,
        )
        with patch("castlearq.run_service.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact
            )
            with patch(
                "castlearq.run_service.prepare", return_value=preparation
            ):
                outcome = run_once(
                    "model-1",
                    "prompt",
                    dependencies=dependencies,
                    admission=self.admission,
                    requested_backend="SYCL",
                )

        self.assertEqual(outcome.output, "sycl")
        runner.run.assert_called_once()

    def test_run_once_translates_capability_target_mismatch(self):
        capability = _capability(backends=("SYCL",), name="llama.cpp SYCL")
        preparation = SimpleNamespace(
            executable_artifact=self.executable,
            target=self.target,
            compatibility_warnings=(),
            selection_warnings=(),
        )
        dependencies = RunDependencies(
            model_store=self.store,
            models=(self.model,),
            capability=capability,
        )
        with patch("castlearq.run_service.ModelArtifactResolver") as resolver:
            resolver.return_value.resolve.return_value = SimpleNamespace(
                model=self.model, artifact=self.artifact
            )
            with patch(
                "castlearq.run_service.prepare", return_value=preparation
            ), self.assertRaises(RunPreparationFailedError) as caught:
                run_once(
                    "model-1",
                    "prompt",
                    dependencies=dependencies,
                    admission=self.admission,
                )

        self.assertIsInstance(caught.exception.__cause__, RunnerFactoryError)

    def test_run_once_translates_runner_factory_error(self):
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
                "castlearq.run_service.prepare", return_value=self.preparation
            ), patch(
                "castlearq.run_service.create_runner",
                side_effect=RunnerFactoryError("construction denied"),
            ), self.assertRaises(RunPreparationFailedError) as caught:
                run_once(
                    "model-1",
                    "prompt",
                    dependencies=dependencies,
                    admission=self.admission,
                )
        self.assertEqual(str(caught.exception), "construction denied")
        self.assertIsInstance(caught.exception.__cause__, RunnerFactoryError)


if __name__ == "__main__":
    unittest.main()
