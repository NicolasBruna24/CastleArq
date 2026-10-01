
# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""B9.79: ephemeral pre-admission runtime/artifact evidence (contract B9.46.23).

``RuntimeArtifactEvidence`` is the ephemeral, non-persistent record produced at
the physical runtime/artifact observation boundary *before* admission. It
answers one question only:

    Which observed runtime instance, which physical artifact, under which
    execution context, produced which observation, and with what provenance?

It is not Knowledge, not manifest data, not artifact state and not a second
compatibility engine. It never claims successful inference: a positive
observation means the observed runtime accepted/loaded the artifact during the
recorded operation, and nothing more (B9.46.23, B9.46.28, B9.79 section 6).

Projection to the strict runtime-artifact-support check is deliberately pure and
lossless (B9.46.23 section 11):

    POSITIVE -> True   -> PASSED
    NEGATIVE -> False  -> FAILED
    UNKNOWN  -> None   -> UNKNOWN

A producer error is never representable here: it is raised by the producer and
must not be silently folded into ``NEGATIVE`` (B9.79 section 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ArtifactObservation",
    "RuntimeArtifactEvidence",
]


class ArtifactObservation(str, Enum):
    """Outcome of one runtime/artifact observation operation (B9.46.23 §11)."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuntimeArtifactEvidence:
    """Ephemeral pre-admission runtime/artifact evidence (B9.46.23 §4).

    ``runtime_identity``, ``artifact_reference``, ``artifact_format``,
    ``observation`` and ``provenance`` are required; ``runtime_version``,
    ``artifact_architecture`` and ``backend`` are context that may be absent
    (``None``) when the runtime could not report it. The record carries no
    model identity, no manifest state, no generated text and no execution
    result, and it is never persisted (B9.46.23 §5).
    """

    runtime_identity: str
    runtime_version: str | None
    artifact_reference: str
    artifact_format: str
    artifact_architecture: str | None
    backend: str | None
    observation: ArtifactObservation
    provenance: str

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_identity, str) or not self.runtime_identity.strip():
            raise ValueError("runtime_identity must be a non-empty string")
        if self.runtime_version is not None and (
            not isinstance(self.runtime_version, str)
            or not self.runtime_version.strip()
        ):
            raise ValueError("runtime_version must be a non-empty string or None")
        if not isinstance(self.artifact_reference, str) or not self.artifact_reference.strip():
            raise ValueError("artifact_reference must be a non-empty string")
        if not isinstance(self.artifact_format, str) or not self.artifact_format.strip():
            raise ValueError("artifact_format must be a non-empty string")
        if self.artifact_architecture is not None and (
            not isinstance(self.artifact_architecture, str)
            or not self.artifact_architecture.strip()
        ):
            raise ValueError("artifact_architecture must be a non-empty string or None")
        if self.backend is not None and (
            not isinstance(self.backend, str) or not self.backend.strip()
        ):
            raise ValueError("backend must be a non-empty string or None")
        if not isinstance(self.observation, ArtifactObservation):
            raise ValueError("observation must be an ArtifactObservation")
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError("provenance must be a non-empty string")

    @property
    def supports_artifact(self) -> bool | None:
        """Project this observation onto the strict tri-state (B9.46.23 §11).

        ``POSITIVE -> True``, ``NEGATIVE -> False``, ``UNKNOWN -> None``. The
        strict evaluator remains the interpreter of the supplied value.
        """
        if self.observation is ArtifactObservation.POSITIVE:
            return True
        if self.observation is ArtifactObservation.NEGATIVE:
            return False
        return None
