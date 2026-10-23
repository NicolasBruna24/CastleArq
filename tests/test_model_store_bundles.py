# Copyright 2026 Nicolas Bruna
import hashlib, json, tempfile, unittest
from pathlib import Path
from castlearq.model_store import ModelStore, UnsafePathError
from castlearq.models import ArtifactSpec, ArtifactState

def artifact(**kwargs):
    values = {"model_id":"qwen/coder","source":"huggingface","repository":"owner/repository","filename":"model-q4.gguf","format":"GGUF","quantization":"Q4_K_M"}
    values.update(kwargs)
    return ArtifactSpec(**values)

class BundleRegressionTests(unittest.TestCase):
    def test_files_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(Path(d)); aux="aux.bin"
            spec = artifact(files=(aux,), file_checksums={aux:"a"*64})
            manifest = store.save_manifest(spec)
            payload = json.loads(manifest.read_text())
            self.assertEqual(payload["files"],[aux])
            loaded = store.inspect_manifest(manifest).artifact
            self.assertEqual(loaded.files,(aux,))
            self.assertEqual(loaded.file_checksums,{aux:"a"*64})
    def test_old_manifest_without_files(self):
        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(Path(d)); spec=artifact()
            manifest = store.save_manifest(spec)
            payload=json.loads(manifest.read_text()); payload.pop("files",None); payload.pop("files_sha256",None)
            manifest.write_text(json.dumps(payload))
            loaded=store.inspect_manifest(manifest).artifact
            self.assertEqual(loaded.files,())
            self.assertEqual(loaded.file_checksums,{})
    def test_individual_artifact_compat(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); content=b"model"; checksum=hashlib.sha256(content).hexdigest()
            spec=artifact(size_bytes=len(content),sha256=checksum)
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(content)
            self.assertEqual(store.inspect_manifest(manifest).state,ArtifactState.VERIFIED)
    def test_complete_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); aux="aux.bin"; ac=b"aux"; ck=hashlib.sha256(ac).hexdigest()
            spec=artifact(files=(aux,),file_checksums={aux:ck})
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            (manifest.parent/aux).write_bytes(ac)
            self.assertEqual(store.inspect_manifest(manifest).state,ArtifactState.DOWNLOADED)
    def test_bundle_missing_aux(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); aux="aux.bin"
            spec=artifact(files=(aux,))
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            self.assertEqual(store.inspect_manifest(manifest).state,ArtifactState.NOT_DOWNLOADED)
    def test_unsafe_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); spec=artifact(files=("../evil.txt",))
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            entry=store.inspect_manifest(manifest)
            self.assertEqual(entry.state,ArtifactState.FAILED)
            self.assertIn("Unsafe",entry.message or "")
    def test_symlink_aux_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); aux="aux.bin"
            spec=artifact(files=(aux,))
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            (manifest.parent/"target").write_bytes(b"x")
            (manifest.parent/aux).symlink_to("target")
            entry=store.inspect_manifest(manifest)
            self.assertEqual(entry.state,ArtifactState.FAILED)
    def test_malformed_entries_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); spec=artifact()
            manifest=store.save_manifest(spec)
            payload=json.loads(manifest.read_text()); payload["files"]=[123]
            manifest.write_text(json.dumps(payload))
            entry=store.inspect_manifest(manifest)
            self.assertEqual(entry.state,ArtifactState.FAILED)
    def test_aux_checksum_verified(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); aux="aux.bin"; ac=b"aux"; ck=hashlib.sha256(ac).hexdigest()
            spec=artifact(files=(aux,),file_checksums={aux:ck})
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            (manifest.parent/aux).write_bytes(ac)
            self.assertEqual(store.inspect_manifest(manifest).state,ArtifactState.DOWNLOADED)
    def test_aux_checksum_change_detected(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); aux="aux.bin"; ac=b"aux"; ck=hashlib.sha256(ac).hexdigest()
            spec=artifact(files=(aux,),file_checksums={aux:ck})
            manifest=store.save_manifest(spec)
            (manifest.parent/spec.filename).write_bytes(b"model")
            (manifest.parent/aux).write_bytes(b"changed")
            entry=store.inspect_manifest(manifest)
            self.assertEqual(entry.state,ArtifactState.FAILED)
            self.assertEqual(entry.message,"SHA-256 differs from manifest")

if __name__=="__main__":
    unittest.main()
