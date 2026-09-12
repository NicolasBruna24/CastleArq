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
