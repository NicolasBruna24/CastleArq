
# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.79: RuntimeArtifactEvidence -> evaluation -> admission integration."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from castlearq import compatibility_evaluator as ce
from castlearq import evaluate_compatibility as uc
from castlearq import evaluation_pipeline as ep
from castlearq import initial_knowledge as ik
from castlearq.compatibility_domain import CheckStatus, CompatibilityStatus
from castlearq.model_domain import (
    Model,
    ModelArchitecture,
    ModelArtifact,
    ModelCapabilities,
    ModelIdentity,
    ModelPrecision,
    ModelQuantization,
    QuantizationStatus,
)
from castlearq.model_store import StoredArtifact
from castlearq.models import ArtifactSpec, ArtifactState, ModelSpec
from castlearq.observation_knowledge import IntegrationResult
from castlearq.runtime_artifact_evidence import (
    ArtifactObservation,
    RuntimeArtifactEvidence,
)
from castlearq.runtime_artifact_observer import RuntimeObservationError
from castlearq.runtimes import PromptInputMode, RuntimeCapability


def _evidence(observation):
    return RuntimeArtifactEvidence(
        runtime_identity="/usr/bin/llama",
        runtime_version="v1",
        artifact_reference="abc",
        artifact_format="GGUF",
        artifact_architecture="qwen2",
        backend="Vulkan0",
        observation=observation,
        provenance="test",
    )


def _capability():
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path="/usr/bin/fake",
        version="v1",
        supported_formats=("GGUF",),
        supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        compatibility_names=("llama.cpp",),
        backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
    )


def _spec(**overrides):
    base = {
        "name": "Qwen3 Demo", "provider": "Unknown", "family": "Qwen3",
        "size_bytes": 1234, "format": "GGUF", "id": None, "parameter_count_b": 7.6,
        "task": "coding", "architecture": "Unknown",
        "supported_runtimes": ("llama.cpp / llama.app",),
        "supported_backends": ("Vulkan", "CPU"), "context_length": 4096,
    }
    base.update(overrides)
    return ModelSpec(**base)


def _artifact(**overrides):
    base = {"model_id": "Qwen3 Demo", "source": "test", "repository": "repo",
            "filename": "model.gguf", "format": "GGUF",
            "quantization": "Q4_K_M", "size_bytes": 1234,
            "state": ArtifactState.DOWNLOADED}
    base.update(overrides)
    return ArtifactSpec(**base)


def _status(evaluation, name):
    return {check.name: check.status for check in evaluation.result.checks}[name]


class ProjectionTests(unittest.TestCase):
    """evaluate_strict projects evidence onto the strict tri-state."""

    def _evaluate(self, evidence):
        return ep.evaluate_strict(
            ik.INITIAL_KNOWLEDGE_REGISTRY, _spec(), _artifact(), _capability(),
            runtime_artifact_evidence=evidence,
        )

    def test_positive_projects_true_and_passed(self):
        evaluation = self._evaluate(_evidence(ArtifactObservation.POSITIVE))
        self.assertIs(evaluation.context.runtime.supports_artifact, True)
        self.assertIs(_status(evaluation, "runtime artifact support"), CheckStatus.PASSED)

    def test_negative_projects_false_and_failed(self):
        evaluation = self._evaluate(_evidence(ArtifactObservation.NEGATIVE))
        self.assertIs(evaluation.context.runtime.supports_artifact, False)
        self.assertIs(_status(evaluation, "runtime artifact support"), CheckStatus.FAILED)

    def test_unknown_projects_none_and_unknown(self):
        evaluation = self._evaluate(_evidence(ArtifactObservation.UNKNOWN))
        self.assertIsNone(evaluation.context.runtime.supports_artifact)
        self.assertIs(_status(evaluation, "runtime artifact support"), CheckStatus.UNKNOWN)

    def test_absence_keeps_unknown(self):
        evaluation = ep.evaluate_strict(
            ik.INITIAL_KNOWLEDGE_REGISTRY, _spec(), _artifact(), _capability(),
        )
        self.assertIsNone(evaluation.context.runtime.supports_artifact)
        self.assertIs(_status(evaluation, "runtime artifact support"), CheckStatus.UNKNOWN)

    def test_declarative_projection_is_never_fabricated(self):
        evaluation = self._evaluate(_evidence(ArtifactObservation.POSITIVE))
        self.assertIsNone(evaluation.projection.runtime_knowledge.supports_artifact)


def _model(**overrides):
    fields = {
        "identity": ModelIdentity(name="Qwen3", model_id="qwen3-coder"),
        "architecture": ModelArchitecture(architecture="Transformer", model_type="MoE"),
        "capabilities": ModelCapabilities(text_generation=True),
    }
    fields.update(overrides)
    return Model(**fields)


def _model_artifact():
    return ModelArtifact(
        precision=ModelPrecision(),
        quantization=ModelQuantization(QuantizationStatus.QUANTIZED, "Q4_K_M", 4),
        identifier="qwen3-coder",
        format="GGUF",
    )


def _knowledge(supports_artifact):
    return ce.RuntimeKnowledge(
        name="llama.cpp",
        supports_artifact=supports_artifact,
        supported_formats=("GGUF",),
        supported_architectures=("Transformer",),
        supported_model_types=("MoE",),
        supported_backends=("Vulkan",),
    )


def _verdict_value(admission):
    return getattr(admission.verdict, "value", admission.verdict)


class AdmissionTests(unittest.TestCase):
    """The projected tri-state keeps the existing admission contract."""

    def _admission(self, observation):
        evidence = _evidence(observation)
        context = ce.EvaluationContext(
            runtime=_knowledge(evidence.supports_artifact), backend="Vulkan"
        )
        compat = ce.evaluate(_model(), _model_artifact(), context)
        result = uc.EvaluateModelCompatibilityResult(
            model_id="qwen3-coder", artifact=None, runtime="llama.cpp CLI",
            capability=None, evaluation=SimpleNamespace(result=compat),
            integration=None, status="evaluated", blocking_outcome=None,
        )
        return uc.to_admission(result), compat

    def test_negative_failed_denies(self):
        admission, compat = self._admission(ArtifactObservation.NEGATIVE)
        self.assertIs(compat.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(_verdict_value(admission), "incompatible")

    def test_unknown_is_non_blocking(self):
        admission, compat = self._admission(ArtifactObservation.UNKNOWN)
        self.assertIs(compat.status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(_verdict_value(admission), "compatible")

    def test_positive_has_no_regression(self):
        admission, compat = self._admission(ArtifactObservation.POSITIVE)
        self.assertIs(compat.status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(admission.status, "evaluated")
        self.assertEqual(_verdict_value(admission), "compatible")


class _FakeStore:
    def __init__(self, entries):
        self._entries = entries

    def list_artifacts(self):
        return self._entries


def _deps(**overrides):
    artifact = _artifact(model_id="qwen2.5-coder-7b-instruct")
    base = {
        "model_store": _FakeStore([
            StoredArtifact(artifact=artifact, state=artifact.state,
                           manifest_path=Path("/tmp/manifest.json"))
        ]),
        "models": (_spec(id="qwen2.5-coder-7b-instruct"),),
        "capability": _capability(),
        "registry": ik.INITIAL_KNOWLEDGE_REGISTRY,
        "integrate_fn": lambda: IntegrationResult(),
        "evaluate_fn": mock.Mock(return_value="EVAL-SENTINEL"),
    }
    base.update(overrides)
    return uc.EvaluateCompatibilityDependencies(**base)


class WiringTests(unittest.TestCase):
    """evaluate_model_compatibility produces and transports the evidence."""

    def test_evidence_is_produced_and_forwarded_to_evaluation(self):
        sentinel = _evidence(ArtifactObservation.POSITIVE)
        observer = mock.Mock(return_value=sentinel)
        captured = {}

        def evaluate_fn(**kwargs):
            captured.update(kwargs)
            return "EVAL-SENTINEL"

        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(runtime_artifact_observer=observer,
                               evaluate_fn=evaluate_fn),
        )
        observer.assert_called_once()
        self.assertIs(captured["runtime_artifact_evidence"], sentinel)
        self.assertEqual(result.status, "evaluated")

    def test_observer_receives_resolved_context(self):
        observer = mock.Mock(return_value=_evidence(ArtifactObservation.UNKNOWN))
        uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(runtime_artifact_observer=observer),
        )
        kwargs = observer.call_args.kwargs
        self.assertEqual(kwargs["executable_path"], "/usr/bin/fake")
        self.assertEqual(kwargs["artifact_format"], "GGUF")
        # No declared backend -> no concrete device could be determined.
        self.assertIsNone(kwargs["device"])

    def test_no_concrete_backend_yields_unknown_observation(self):
        captured = {}

        def evaluate_fn(**kwargs):
            captured.update(kwargs)
            return "EVAL-SENTINEL"

        uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct", dependencies=_deps(evaluate_fn=evaluate_fn),
        )
        # The real default observer runs no subprocess without a device.
        self.assertIsNotNone(captured["runtime_artifact_evidence"])
        self.assertIs(
            captured["runtime_artifact_evidence"].observation,
            ArtifactObservation.UNKNOWN,
        )

    def test_producer_error_propagates_as_evaluation_error(self):
        def observer(**kwargs):
            raise RuntimeObservationError("could not launch")

        with self.assertRaises(RuntimeObservationError):
            uc.evaluate_model_compatibility(
                "qwen2.5-coder-7b-instruct",
                dependencies=_deps(runtime_artifact_observer=observer),
            )


if __name__ == "__main__":
    unittest.main()
