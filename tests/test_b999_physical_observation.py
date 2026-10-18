# EMD physical-observation tests: explicit durable gguf_architecture capture.
import io
import os
import struct
import tempfile
import unittest
from pathlib import Path

from castlearq import admitted_models as am
from castlearq.admitted_commands import observe_physical_command
from castlearq.admitted_resolution import (
    AdmittedMaterialConflictError,
    resolve_model_for_evaluation,
)
from castlearq.model_identity import resolve_admitted_model_id
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec

SRC = "huggingface"
REPO = "someowner/physical-obs"


def _gguf(arch=None):
    entries = (("general.architecture", arch),) if arch is not None else ()
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, len(entries)))
    for key, value in entries:
        raw = value.encode("utf-8")
        data.extend(struct.pack("<Q", len(key.encode("utf-8"))))
        data.extend(key.encode("utf-8"))
        data.extend(struct.pack("<I", 8))
        data.extend(struct.pack("<Q", len(raw)))
        data.extend(raw)
    return bytes(data)


class PhysicalObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get(am.ADMITTED_MODELS_ROOT_ENV)
        os.environ[am.ADMITTED_MODELS_ROOT_ENV] = str(
            Path(self.tmp.name) / "admitted"
        )
        self.store_root = Path(self.tmp.name) / "store"
        self.store = ModelStore(self.store_root)
        self.mid = resolve_admitted_model_id(SRC, REPO)
        am.describe(
            self.mid, SRC, REPO, filename="m.gguf", quantization="Q4_K_M",
            architecture="llama", format="GGUF",
        )

    def tearDown(self):
        if self.old is None:
            os.environ.pop(am.ADMITTED_MODELS_ROOT_ENV, None)
        else:
            os.environ[am.ADMITTED_MODELS_ROOT_ENV] = self.old
        self.tmp.cleanup()

    def _install(self, payload, revision=None):
        spec = ArtifactSpec(
            model_id=self.mid, source=SRC, repository=REPO, filename="m.gguf",
            format="GGUF", quantization="Q4_K_M", revision=revision,
        )
        self.store.save_manifest(spec)
        target = self.store._artifact_directory(spec) / "m.gguf"
        target.write_bytes(payload)
        return spec

    def test_success_records_observation_with_provenance(self):
        spec = self._install(_gguf("llama"))
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                self.mid, filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            0,
        )
        rec = am.resolve(self.mid)
        self.assertEqual(len(rec.observations), 1)
        obs = rec.observations[0]
        self.assertEqual(obs["claim"], "gguf_architecture")
        self.assertEqual(obs["value"], "llama")
        self.assertIn(spec.artifact_id, obs["observation_provenance"]["observation_context"])
        self.assertEqual(rec.accepted.architecture, "llama")
        self.assertEqual(am.material_conflicts(rec), ())
        resolved = resolve_model_for_evaluation(self.mid)
        self.assertTrue(resolved.from_admitted)

    def test_revision_included_when_declared(self):
        spec = self._install(_gguf("llama"), revision="abc123")
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                self.mid, filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            0,
        )
        obs = am.resolve(self.mid).observations[0]
        self.assertIn("abc123", obs["observation_provenance"]["observation_context"])
        self.assertIn(spec.artifact_id, obs["observation_provenance"]["observation_context"])

    def test_divergence_registers_conflict_and_blocks(self):
        self._install(_gguf("mistral"))
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                self.mid, filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            0,
        )
        rec = am.resolve(self.mid)
        conflicts = am.material_conflicts(rec)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["declared"], "llama")
        self.assertEqual(conflicts[0]["observed"], "mistral")
        with self.assertRaises(AdmittedMaterialConflictError):
            resolve_model_for_evaluation(self.mid)

    def test_missing_file_persists_nothing(self):
        before = am.resolve(self.mid)
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                self.mid, filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            1,
        )
        self.assertIn("Observe-physical error", err.getvalue())
        self.assertEqual(len(am.resolve(self.mid).observations), 0)
        self.assertEqual(am.resolve(self.mid).accepted, before.accepted)

    def test_corrupt_and_missing_metadata_persist_nothing(self):
        for payload in (b"NOPE", _gguf(None)):
            self._install(payload)
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(
                observe_physical_command(
                    self.mid, filename="m.gguf", model_store=self.store,
                    out=out, err=err,
                ),
                1,
            )
            self.assertIn("Observe-physical error", err.getvalue())
        self.assertEqual(len(am.resolve(self.mid).observations), 0)

    def test_unknown_model_persists_nothing(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                "nope", filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            1,
        )
        self.assertEqual(len(am.resolve(self.mid).observations), 0)

    def test_persists_across_reload_and_evaluation_stays_readonly(self):
        self._install(_gguf("llama"))
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            observe_physical_command(
                self.mid, filename="m.gguf", model_store=self.store,
                out=out, err=err,
            ),
            0,
        )
        self.assertEqual(len(am.resolve(self.mid).observations), 1)
        from castlearq.evaluate_compatibility import (
            evaluate_model_compatibility,
        )
        try:
            evaluate_model_compatibility(self.mid)
        except Exception:
            pass
        self.assertEqual(len(am.resolve(self.mid).observations), 1)

    def test_cli_success_and_usage(self):
        from castlearq.main import _admitted_command
        out, err = io.StringIO(), io.StringIO()
        res = _admitted_command(
            "observe", model_id=self.mid, physical_gguf=True,
            out=out, err=err,
        )
        self.assertIn(res, (0, 1))
        out2, err2 = io.StringIO(), io.StringIO()
        self.assertEqual(
            _admitted_command("observe", physical_gguf=True,
                              out=out2, err=err2),
            2,
        )
        self.assertIn("Usage", err2.getvalue())


if __name__ == "__main__":
    unittest.main()
