
# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.79: unit tests for the RuntimeArtifactEvidence contract (B9.46.23)."""

from __future__ import annotations

import dataclasses
import unittest

from castlearq.runtime_artifact_evidence import (
    ArtifactObservation,
    RuntimeArtifactEvidence,
)

FIELDS = [
    "runtime_identity",
    "runtime_version",
    "artifact_reference",
    "artifact_format",
    "artifact_architecture",
    "backend",
    "observation",
    "provenance",
]


def evidence(**overrides):
    base = {
        "runtime_identity": "/usr/local/bin/llama",
        "runtime_version": "llama.cpp 0.4.0-dev",
        "artifact_reference": "abc123",
        "artifact_format": "GGUF",
        "artifact_architecture": "qwen2",
        "backend": "Vulkan",
        "observation": ArtifactObservation.POSITIVE,
        "provenance": "RuntimeArtifactObserver: llama cli -n 0",
    }
    base.update(overrides)
    return RuntimeArtifactEvidence(**base)


class ContractShapeTests(unittest.TestCase):
    def test_exact_field_set(self):
        self.assertEqual(list(RuntimeArtifactEvidence.__dataclass_fields__), FIELDS)

    def test_excludes_non_contract_concepts(self):
        for excluded in (
            "model_id",
            "identifier",
            "manifest",
            "generated_text",
            "execution_result",
            "content_id",
        ):
            self.assertNotIn(excluded, RuntimeArtifactEvidence.__dataclass_fields__)

    def test_is_frozen_and_ephemeral(self):
        item = evidence()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.observation = ArtifactObservation.NEGATIVE  # type: ignore[misc]

    def test_optional_context_may_be_absent(self):
        item = evidence(
            runtime_version=None, artifact_architecture=None, backend=None
        )
        self.assertIsNone(item.runtime_version)
        self.assertIsNone(item.artifact_architecture)
        self.assertIsNone(item.backend)

    def test_observation_values_are_the_contract_tristate(self):
        self.assertEqual(ArtifactObservation.POSITIVE.value, "positive")
        self.assertEqual(ArtifactObservation.NEGATIVE.value, "negative")
        self.assertEqual(ArtifactObservation.UNKNOWN.value, "unknown")


class ProjectionTests(unittest.TestCase):
    def test_positive_projects_true(self):
        self.assertIs(evidence(observation=ArtifactObservation.POSITIVE).supports_artifact, True)

    def test_negative_projects_false(self):
        self.assertIs(evidence(observation=ArtifactObservation.NEGATIVE).supports_artifact, False)

    def test_unknown_projects_none(self):
        self.assertIs(evidence(observation=ArtifactObservation.UNKNOWN).supports_artifact, None)


class ValidationTests(unittest.TestCase):
    def test_required_strings_must_be_non_empty(self):
        for field in (
            "runtime_identity",
            "artifact_reference",
            "artifact_format",
            "provenance",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence(**{field: ""})

    def test_observation_must_be_the_enum(self):
        with self.assertRaises(ValueError):
            evidence(observation="positive")

    def test_optional_strings_reject_blank_but_allow_none(self):
        for field in ("runtime_version", "artifact_architecture", "backend"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence(**{field: "   "})
            self.assertIsNone(getattr(evidence(**{field: None}), field))

    def test_missing_required_argument_is_rejected(self):
        with self.assertRaises(TypeError):
            RuntimeArtifactEvidence(
                runtime_identity="x",
                runtime_version=None,
                artifact_reference="a",
                artifact_format="GGUF",
                artifact_architecture=None,
                backend=None,
                observation=ArtifactObservation.UNKNOWN,
            )


if __name__ == "__main__":
    unittest.main()
