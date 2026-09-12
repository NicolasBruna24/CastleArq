"""Pure recovery decisions based on an inspected artifact filesystem state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .inspection import ArtifactFilesystemInspection, ArtifactFilesystemState


class RecoveryDecision(str, Enum):
    NO_ACTION = "no_action"
    RESUME_ELIGIBLE = "resume_eligible"
    USE_EXISTING = "use_existing"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class RecoveryDecisionResult:
    decision: RecoveryDecision
    reason: str


class RecoveryDecider:
    """Map an inspected filesystem state to a read-only recovery decision."""

    def decide(
        self,
        inspection: ArtifactFilesystemInspection,
    ) -> RecoveryDecisionResult:
        decisions = {
            ArtifactFilesystemState.CLEAN: (
                RecoveryDecision.NO_ACTION,
                "No final artifact or partial download exists",
            ),
            ArtifactFilesystemState.PARTIAL: (
                RecoveryDecision.RESUME_ELIGIBLE,
                "A partial download exists and may be resumed",
            ),
            ArtifactFilesystemState.FINAL_EXISTS: (
                RecoveryDecision.USE_EXISTING,
                "The final artifact exists",
            ),
            ArtifactFilesystemState.INCONSISTENT: (
                RecoveryDecision.REVIEW_REQUIRED,
                "The final artifact and partial download both exist",
            ),
        }
        decision, reason = decisions[inspection.state]
        return RecoveryDecisionResult(decision, reason)
