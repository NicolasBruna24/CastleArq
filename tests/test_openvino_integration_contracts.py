import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq.conversion import OpenVINOConversionService
from castlearq.model_store import ModelStore
from castlearq.openvino_inference import OpenVINOInferenceService


class OpenVINOIntegrationContractsTests(unittest.TestCase):
    def test_conversion_store_inference_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = ModelStore(root)
            dest = root / "dest"

            def fake_run(argv, **kw):
                (dest / "openvino_model.xml").write_bytes(b"<xml/>")
                (dest / "weights.bin").write_bytes(b"weights")
                return mock.Mock(returncode=0, stdout="", stderr="")

            svc = OpenVINOConversionService(store, run_process=fake_run)
            with mock.patch("castlearq.conversion.shutil.which", return_value="/bin/optimum-cli"):
                result = svc.convert("org/model", destination=dest, precision="fp16")
            self.assertTrue(result.success, result.message)
            self.assertIsNotNone(result.manifest_path)

            def fake_pipeline(model_dir, device):
                return mock.Mock(generate=lambda prompt, max_new_tokens=8: "hello")

            inf = OpenVINOInferenceService(store, pipeline_factory=fake_pipeline)
            gen = inf.generate(result.manifest_path, "hi", device="CPU", max_new_tokens=4)
            self.assertEqual(gen.text, "hello")
            self.assertEqual(gen.effective_device, "unverified")


if __name__ == "__main__":
    unittest.main()
