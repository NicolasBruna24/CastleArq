# B9.99 tests: durable Executable Model Description + provenance + journey.
import os
import tempfile
import unittest
from castlearq import admitted_models as am
from castlearq.admitted_resolution import resolve_model_for_evaluation, AdmittedResolutionError
from castlearq.model_identity import resolve_admitted_model_id
SRC = "huggingface"
REPO = "someowner/somemodel-b9999"
MID = resolve_admitted_model_id(SRC, REPO)
class B9999Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get(am.ADMITTED_MODELS_ROOT_ENV)
        os.environ[am.ADMITTED_MODELS_ROOT_ENV] = self.tmp.name
    def tearDown(self):
        if self.old is None:
            os.environ.pop(am.ADMITTED_MODELS_ROOT_ENV, None)
        else:
            os.environ[am.ADMITTED_MODELS_ROOT_ENV] = self.old
        self.tmp.cleanup()
    def test_describe_resolve_roundtrip_and_fresh_process(self):
        rec = am.describe(MID, SRC, REPO, filename="m.gguf", quantization="Q4_K_M", architecture="llama", format="GGUF")
        self.assertEqual(rec.accepted.architecture, "llama")
        again = am.resolve(MID)
        self.assertIsNotNone(again)
        self.assertEqual(again.accepted.format, "GGUF")
    def test_divergent_redescription_rejected(self):
        am.describe(MID, SRC, REPO, architecture="llama")
        with self.assertRaises(am.AdmittedModelError):
            am.describe(MID, SRC, REPO, architecture="mistral")
    def test_resolve_is_readonly_no_implicit_refresh(self):
        am.describe(MID, SRC, REPO, architecture="llama")
        before = am.resolve(MID)
        am.resolve(MID)
        after = am.resolve(MID)
        self.assertIsNone(after.pending_declaration)
        self.assertEqual(before.accepted, after.accepted)
    def test_refresh_stages_pending_keeps_accepted(self):
        am.describe(MID, SRC, REPO, architecture="llama")
        diff = am.refresh(MID, architecture="mistral")
        self.assertTrue(diff.has_changes)
        rec = am.resolve(MID)
        self.assertEqual(rec.accepted.architecture, "llama")
        self.assertIsNotNone(rec.pending_declaration)
    def test_evaluation_does_not_implicitly_record_observations(self):
        # B1: ordinary evaluation must not mutate the admitted-model store.
        import io as _io
        from castlearq.evaluate_compatibility import evaluate_model_compatibility
        am.describe(MID, SRC, REPO, architecture="llama", format="GGUF")
        before = am.resolve(MID)
        self.assertEqual(len(before.observations), 0)
        out = _io.StringIO()
        before_bytes = open(am.admitted_models_path(), "rb").read() if am.admitted_models_path().exists() else b""
        try:
            evaluate_model_compatibility(MID)
        except Exception:
            pass
        after = am.resolve(MID)
        self.assertEqual(len(after.observations), 0)
        after_bytes = open(am.admitted_models_path(), "rb").read() if am.admitted_models_path().exists() else b""
        # Evaluation of an admitted model with no local artifact fails at
        # resolution, but in no outcome may it append an observation.
        self.assertEqual(len(after.observations), len(before.observations))

    def test_explicit_observe_and_cli_surface(self):
        # B1 explicit boundary + B3 user-reachable CLI group.
        import io as _io
        from castlearq.admitted_commands import observe_command
        from castlearq.main import _admitted_command
        am.describe(MID, SRC, REPO, architecture="llama", format="GGUF")
        out, err = _io.StringIO(), _io.StringIO()
        self.assertEqual(
            observe_command(MID, "gguf_architecture", "llama", observation_context="cli-test", out=out, err=err), 0
        )
        self.assertEqual(len(am.resolve(MID).observations), 1)
        # CLI group reaches show/observe/refresh/reconcile without imports.
        out2, err2 = _io.StringIO(), _io.StringIO()
        self.assertEqual(_admitted_command("show", model_id=MID, out=out2, err=err2), 0)
        self.assertIn(MID, out2.getvalue())
        out3, err3 = _io.StringIO(), _io.StringIO()
        self.assertEqual(
            _admitted_command("observe", model_id=MID, claim="gguf_architecture", value="llama", context_note="n", out=out3, err=err3), 0
        )

    def test_conflict_blocks_and_reconcile_preserves_history(self):
        am.describe(MID, SRC, REPO, architecture="llama")
        am.record_observation(MID, "gguf_architecture", "mistral", observation_context="test")
        rec = am.resolve(MID)
        self.assertEqual(len(am.material_conflicts(rec)), 1)
        with self.assertRaises(AdmittedResolutionError):
            resolve_model_for_evaluation(MID)
        # B2: typed conflict signal (subclass of the resolution error).
        from castlearq.admitted_resolution import AdmittedMaterialConflictError
        with self.assertRaises(AdmittedMaterialConflictError):
            resolve_model_for_evaluation(MID)
        am.refresh(MID, architecture="mistral")
        out = am.reconcile(MID, {"architecture": "accept_pending"}, basis="human")
        self.assertEqual(out.accepted.architecture, "mistral")
        self.assertEqual(len(out.reconciliations), 1)
        resolved = resolve_model_for_evaluation(MID)
        self.assertTrue(resolved.from_admitted)
if __name__ == "__main__":
    unittest.main()
