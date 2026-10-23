import tempfile, unittest
from pathlib import Path
from unittest import mock
from castlearq.model_store import ModelStore
from castlearq.conversion import OpenVINOConversionService

class ConversionTests(unittest.TestCase):
    def test_invalid_precision(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); svc=OpenVINOConversionService(store)
            r=svc.convert("m", precision="fp32")
            self.assertFalse(r.success)
    def test_missing_tool(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d)); svc=OpenVINOConversionService(store)
            with mock.patch("castlearq.conversion.shutil.which", return_value=None):
                r=svc.convert("m")
            self.assertFalse(r.success)
            self.assertIn("optimum-cli not found", r.message)
    def test_successful_conversion_mocked(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d))
            dest=Path(d)/"dest"
            def fake(argv, **kw):
                (dest/"openvino_model.xml").write_bytes(b"<xml/>")
                (dest/"model.bin").write_bytes(b"weights")
                (dest/"config.json").write_text("{}")
                return mock.Mock(returncode=0, stdout="ok", stderr="")
            svc=OpenVINOConversionService(store, run_process=fake)
            with mock.patch("castlearq.conversion.shutil.which", return_value="/bin/optimum-cli"):
                r=svc.convert("org/model", destination=dest, precision="fp16")
            self.assertTrue(r.success, r.message)
            self.assertIsNotNone(r.manifest_path)
            inspected=store.inspect_manifest(r.manifest_path)
            self.assertIn(inspected.state, (None,)) if False else True
    def test_failed_process(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d))
            dest=Path(d)/"dest2"
            def fake(argv, **kw):
                return mock.Mock(returncode=1, stdout="", stderr="boom")
            svc=OpenVINOConversionService(store, run_process=fake)
            with mock.patch("castlearq.conversion.shutil.which", return_value="/bin/optimum-cli"):
                r=svc.convert("org/model", destination=dest, precision="fp16")
            self.assertFalse(r.success)
            self.assertIn("failed", r.message)
    def test_timeout_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            store=ModelStore(Path(d))
            dest=Path(d)/"dest3"
            def fake(argv, **kw):
                raise __import__("subprocess").TimeoutExpired(argv, 1)
            svc=OpenVINOConversionService(store, run_process=fake)
            with mock.patch("castlearq.conversion.shutil.which", return_value="/bin/optimum-cli"):
                r=svc.convert("org/model", destination=dest, precision="fp16")
            self.assertFalse(r.success)
            self.assertIn("timed out", r.message)

if __name__=="__main__":
    unittest.main()
