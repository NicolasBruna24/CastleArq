# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application Boundary tests for Evaluate Model Compatibility.

Tests the Application wiring only (capability policy, resolution
coordination, verbatim IntegrationResult forwarding). Domain
semantics of B9.14/B9.15 are owned by their own suites.
"""

from __future__ import annotations

import unittest
from unittest import mock

from app.compatibility_domain import CheckStatus
from app import evaluate_compatibility as uc
from app import initial_knowledge as ik
from app.models import ArtifactSpec, ArtifactState, ModelSpec
from app.model_store import StoredArtifact
from app.observation_knowledge import IntegrationResult
from app.runtimes import PromptInputMode, RuntimeCapability


def _capability(**overrides):
    base = dict(
        name="llama.cpp CLI",
        executable_path="/usr/bin/fake",
        version="v1",
        supported_formats=("GGUF",),
        supported_backends=("CPU",),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        compatibility_names=("llama.cpp",),
    )
    base.update(overrides)
    return RuntimeCapability(**base)


def _unavailable_capability():
    return _capability(
        available=False,
        reason="llama executable was not found",
    )


def _model(**overrides):
    base = dict(
        id="qwen2.5-coder-7b-instruct",
        name="Qwen2.5-Coder 7B Instruct",
    )
    base.update(overrides)
    return ModelSpec(**base)


def _artifact(**overrides):
    base = dict(
        model_id="qwen2.5-coder-7b-instruct",
        source="huggingface",
        repository="repo",
        filename="model.gguf",
        format="GGUF",
        quantization="Q4_K_M",
        state=ArtifactState.DOWNLOADED,
    )
    base.update(overrides)
    return ArtifactSpec(**base)


class _FakeStore:
    def __init__(self, entries):
        self._entries = entries

    def list_artifacts(self):
        return self._entries


def _stored(artifact, state=None):
    return StoredArtifact(
        artifact=artifact,
        state=state if state is not None else artifact.state,
        manifest_path=__import__("pathlib").Path("/tmp/manifest.json"),
    )


def _deps(**overrides):
    base = dict(
        model_store=_FakeStore([_stored(_artifact())]),
        models=(_model(),),
        capability=_capability(),
        registry=ik.INITIAL_KNOWLEDGE_REGISTRY,
        integrate_fn=lambda: IntegrationResult(),
        evaluate_fn=mock.Mock(return_value="EVAL-SENTINEL"),
    )
    base.update(overrides)
    return uc.EvaluateCompatibilityDependencies(**base)

class AvailablePolicyTests(unittest.TestCase):
    def test_unavailable_blocks_before_b915(self):
        evaluate_fn = mock.Mock()
        integrate_fn = mock.Mock()
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(
                capability=_unavailable_capability(),
                integrate_fn=integrate_fn,
                evaluate_fn=evaluate_fn,
            ),
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.evaluation)
        self.assertIsNotNone(result.blocking_outcome)
        self.assertIsNotNone(result.capability)
        self.assertFalse(result.capability.available)
        evaluate_fn.assert_not_called()
        integrate_fn.assert_not_called()

    def test_available_does_not_block_policy(self):
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct", dependencies=_deps()
        )
        self.assertEqual(result.status, "evaluated")
        self.assertIsNone(result.blocking_outcome)


class SuccessPathTests(unittest.TestCase):
    def test_forwards_same_objects_verbatim(self):
        sentinel = IntegrationResult()
        integrate_calls: list = []
        captured: dict = {}

        def integrate_fn():
            integrate_calls.append(True)
            return sentinel

        def evaluate_fn(**kwargs):
            captured.update(kwargs)
            return "EVAL-SENTINEL"

        deps = _deps(integrate_fn=integrate_fn, evaluate_fn=evaluate_fn)
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct", dependencies=deps
        )
        self.assertEqual(len(integrate_calls), 1)
        self.assertIs(result.integration, sentinel)
        self.assertIs(captured["result"], sentinel)
        self.assertIs(captured["capability"], deps.capability)
        self.assertIs(captured["registry"], ik.INITIAL_KNOWLEDGE_REGISTRY)
        self.assertIs(captured["spec"], deps.models[0])
        self.assertIsInstance(captured["artifact"], ArtifactSpec)
        self.assertEqual(result.evaluation, "EVAL-SENTINEL")
        self.assertEqual(result.status, "evaluated")
        self.assertIsNone(result.blocking_outcome)

    def test_identity_is_object_identity(self):
        sentinel = IntegrationResult()
        captured: dict = {}

        def evaluate_fn(**kwargs):
            captured.update(kwargs)
            return "EVAL-SENTINEL"

        uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(
                integrate_fn=lambda: sentinel, evaluate_fn=evaluate_fn
            ),
        )
        self.assertTrue(captured["result"] is sentinel)


class ResolutionFailureTests(unittest.TestCase):
    def test_unknown_model_blocks_without_b915(self):
        evaluate_fn = mock.Mock()
        result = uc.evaluate_model_compatibility(
            "unknown-model", dependencies=_deps(evaluate_fn=evaluate_fn)
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.evaluation)
        evaluate_fn.assert_not_called()

    def test_artifact_ambiguity_blocks_without_b915(self):
        second = _artifact(filename="other.gguf", quantization="Q4_K_M")
        store = _FakeStore([_stored(_artifact()), _stored(second)])
        evaluate_fn = mock.Mock()
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(model_store=store, evaluate_fn=evaluate_fn),
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.evaluation)
        evaluate_fn.assert_not_called()

    def test_missing_artifact_blocks_without_b915(self):
        store = _FakeStore([])
        evaluate_fn = mock.Mock()
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(model_store=store, evaluate_fn=evaluate_fn),
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.evaluation)
        evaluate_fn.assert_not_called()


class B914FailureTests(unittest.TestCase):
    def test_b914_failure_blocks_without_b915_no_fabrication(self):
        def failing():
            raise RuntimeError("observer blew up")

        evaluate_fn = mock.Mock()
        result = uc.evaluate_model_compatibility(
            "qwen2.5-coder-7b-instruct",
            dependencies=_deps(integrate_fn=failing, evaluate_fn=evaluate_fn),
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.evaluation)
        self.assertIsNone(result.integration)
        self.assertIsNotNone(result.blocking_outcome)
        self.assertIsNotNone(result.artifact)
        self.assertIsNotNone(result.capability)
        evaluate_fn.assert_not_called()


class B915FailureTests(unittest.TestCase):
    def test_b915_failure_propagates_not_silenced(self):
        def failing(**kwargs):
            raise ValueError("ambiguous runtime resolution")

        with self.assertRaises(ValueError):
            uc.evaluate_model_compatibility(
                "qwen2.5-coder-7b-instruct",
                dependencies=_deps(evaluate_fn=failing),
            )


class AdmissionProjectionTests(unittest.TestCase):
    def _result(self, status="evaluated", verdict=None):
        strict_result = None
        if verdict is not None:
            strict_result = mock.Mock(status=verdict)
        evaluation = None
        if strict_result is not None:
            evaluation = mock.Mock(result=strict_result)
        return uc.EvaluateModelCompatibilityResult(
            model_id="m1",
            artifact=None,
            runtime="llama.cpp CLI",
            capability=None,
            evaluation=evaluation,
            integration=None,
            status=status,
            blocking_outcome=None,
        )

    def test_compatible_admits(self):
        admission = uc.to_admission(self._result(verdict="compatible"))
        self.assertEqual(admission, uc.EvaluationAdmission("evaluated", "compatible"))

    def test_compatible_with_conditions_admits(self):
        admission = uc.to_admission(
            self._result(verdict="compatible_with_conditions")
        )
        self.assertEqual(
            admission,
            uc.EvaluationAdmission("evaluated", "compatible_with_conditions"),
        )

    def test_incompatible_projects_denying_verdict(self):
        admission = uc.to_admission(self._result(verdict="incompatible"))
        self.assertEqual(admission, uc.EvaluationAdmission("evaluated", "incompatible"))

    def test_insufficient_runtime_only_projects_admitting_verdict(self):
        result = self._result(verdict="insufficient_evidence")
        runtime_check = mock.Mock(status=CheckStatus.UNKNOWN)
        runtime_check.name = "runtime artifact support"
        result.evaluation.result.checks = (runtime_check,)
        admission = uc.to_admission(result)
        self.assertEqual(
            admission,
            uc.EvaluationAdmission("evaluated", "compatible"),
        )

    def test_blocked_result_has_no_admitting_verdict(self):
        admission = uc.to_admission(self._result(status="blocked"))
        self.assertEqual(admission, uc.EvaluationAdmission("blocked", None))

    def test_missing_evaluation_fails_closed(self):
        admission = uc.to_admission(self._result())
        self.assertEqual(admission, uc.EvaluationAdmission("evaluated", None))

    def test_missing_or_malformed_result_fails_closed(self):
        self.assertEqual(uc.to_admission(None), uc.EvaluationAdmission("blocked", None))
        malformed = mock.Mock(status="evaluated", evaluation=mock.Mock(result=None))
        self.assertEqual(
            uc.to_admission(malformed), uc.EvaluationAdmission("evaluated", None)
        )


if __name__ == "__main__":
    unittest.main()
