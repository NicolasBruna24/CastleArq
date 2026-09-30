
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
