
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

import unittest
from dataclasses import FrozenInstanceError

from app.downloads import (
    ArtifactFilesystemInspection,
    ArtifactFilesystemState,
    RecoveryDecision,
    RecoveryDecisionResult,
    RecoveryDecider,
)


class RecoveryDeciderTests(unittest.TestCase):
    def setUp(self):
        self.decider = RecoveryDecider()

    def test_clean_maps_to_no_action(self):
        result = self.decider.decide(
            ArtifactFilesystemInspection(False, False, ArtifactFilesystemState.CLEAN)
        )
        self.assertEqual(result.decision, RecoveryDecision.NO_ACTION)

    def test_partial_maps_to_resume_eligible(self):
        result = self.decider.decide(
            ArtifactFilesystemInspection(False, True, ArtifactFilesystemState.PARTIAL)
        )
        self.assertEqual(result.decision, RecoveryDecision.RESUME_ELIGIBLE)

    def test_final_exists_maps_to_use_existing(self):
        result = self.decider.decide(
            ArtifactFilesystemInspection(True, False, ArtifactFilesystemState.FINAL_EXISTS)
        )
        self.assertEqual(result.decision, RecoveryDecision.USE_EXISTING)

    def test_inconsistent_maps_to_review_required(self):
        result = self.decider.decide(
            ArtifactFilesystemInspection(True, True, ArtifactFilesystemState.INCONSISTENT)
        )
        self.assertEqual(result.decision, RecoveryDecision.REVIEW_REQUIRED)

    def test_result_is_frozen(self):
        result = RecoveryDecisionResult(RecoveryDecision.NO_ACTION, "reason")
        with self.assertRaises(FrozenInstanceError):
            result.reason = "changed"

    def test_decider_requires_only_inspection(self):
        result = self.decider.decide(
            ArtifactFilesystemInspection(False, False, ArtifactFilesystemState.CLEAN)
        )
        self.assertIsInstance(result, RecoveryDecisionResult)
        self.assertEqual(result.reason, "No final artifact or partial download exists")


if __name__ == "__main__":
    unittest.main()
