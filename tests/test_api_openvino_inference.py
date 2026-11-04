import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from castlearq.api import build_server
from castlearq.model_store import ModelStore
from castlearq.openvino_inference import (
    MissingDependencyError, InvalidArtifactError, PipelineInitError, GenerationError,
)

HOST = "127.0.0.1"

class Harness:
    def __init__(self, store):
        self.server = build_server(HOST, 0, model_store=store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    @property
    def port(self): return self.server.server_address[1]
    def post(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection(HOST, self.port, timeout=10)
        data = None if body is None else json.dumps(body).encode()
        conn.request("POST", path, body=data, headers=headers or {"Content-Type":"application/json"})
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            payload = json.loads(raw.decode())
        except Exception:
            payload = None
        return r.status, payload, raw
    def get(self, path):
        conn = http.client.HTTPConnection(HOST, self.port, timeout=10)
        conn.request("GET", path)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        return r.status, raw
    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

class TestOpenVINOHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = ModelStore(self.root)
        d = self.root / "m" / "a"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({
            "model_id": "ov-model",
            "source": "openvino-export",
            "repository": "r",
            "filename": "openvino_model.xml",
            "format": "OpenVINO IR",
            "quantization": "FP16",
            "files": [],
            "files_sha256": None,
        }))
        (d / "openvino_model.xml").write_text("<xml/>")
        self.h = Harness(self.store)

    def tearDown(self):
        self.h.close()
        self.tmp.cleanup()

    def test_valid_request(self):
        fake_result = SimpleNamespace(text="hello", initialization_status="ok", effective_device="unknown", physical_telemetry={"before": None, "after": None})
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.return_value = fake_result
            status, payload, _ = self.h.post("/v1/openvino/infer", {
                "model_id": "ov-model", "prompt": "Hi", "device": "GPU", "max_tokens": 4,
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["text"], "hello")
        self.assertEqual(payload["model_id"], "ov-model")
        self.assertEqual(payload["effective_device"], "unknown")
        self.assertEqual(payload["physical_telemetry"], {"before": None, "after": None})

    def test_invalid_json(self):
        conn = http.client.HTTPConnection(HOST, self.h.port, timeout=10)
        conn.request("POST", "/v1/openvino/infer", body=b"{bad", headers={"Content-Type":"application/json","Content-Length":"4"})
        r = conn.getresponse(); r.read(); conn.close()
        self.assertEqual(r.status, 400)

    def test_missing_fields(self):
        status, payload, _ = self.h.post("/v1/openvino/infer", {"prompt":"Hi"})
        self.assertEqual(status, 400)

    def test_unknown_model(self):
        status, payload, _ = self.h.post("/v1/openvino/infer", {"model_id":"nope","prompt":"Hi"})
        self.assertEqual(status, 404)

    def test_gguf_rejected(self):
        d = self.root / "g" / "a"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({
            "model_id": "gguf-model",
            "source": "x",
            "repository": "r",
            "filename": "m.gguf",
            "format": "GGUF",
            "quantization": "Q4",
            "files": [],
            "files_sha256": None,
        }))
        (d / "m.gguf").write_text("x")
        status, payload, _ = self.h.post("/v1/openvino/infer", {"model_id":"gguf-model","prompt":"Hi"})
        self.assertEqual(status, 422)

    def test_invalid_device(self):
        status, _, _ = self.h.post("/v1/openvino/infer", {"model_id":"ov-model","prompt":"Hi","device":"TPU"})
        self.assertEqual(status, 400)

    def test_invalid_max_tokens(self):
        status, _, _ = self.h.post("/v1/openvino/infer", {"model_id":"ov-model","prompt":"Hi","max_tokens":0})
        self.assertEqual(status, 400)

    def test_missing_dependency(self):
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.side_effect = MissingDependencyError("no dep")
            status, _, _ = self.h.post("/v1/openvino/infer", {"model_id":"ov-model","prompt":"Hi"})
        self.assertEqual(status, 503)

    def test_init_error(self):
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.side_effect = PipelineInitError("boom")
            status, _, _ = self.h.post("/v1/openvino/infer", {"model_id":"ov-model","prompt":"Hi"})
        self.assertEqual(status, 500)

    def test_generation_error(self):
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.side_effect = GenerationError("genfail")
            status, _, _ = self.h.post("/v1/openvino/infer", {"model_id":"ov-model","prompt":"Hi"})
        self.assertEqual(status, 500)

    def test_pipeline_reused_across_consecutive_requests(self):
        """Two consecutive requests with same model/device reuse the same service."""
        fake_result = SimpleNamespace(
            text="hello", initialization_status="ok",
            effective_device="unknown", physical_telemetry={"before": None, "after": None},
        )
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.return_value = fake_result
            # First request
            status1, _, _ = self.h.post("/v1/openvino/infer", {
                "model_id": "ov-model", "prompt": "Hi", "device": "GPU", "max_tokens": 4,
            })
            # Second request with same model/device
            status2, _, _ = self.h.post("/v1/openvino/infer", {
                "model_id": "ov-model", "prompt": "Hi again", "device": "GPU", "max_tokens": 4,
            })
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        # Constructor called only once (lazy creation + caching)
        self.assertEqual(cls.call_count, 1)
        # generate called twice on the same service instance
        self.assertEqual(cls.return_value.generate.call_count, 2)

    def test_concurrent_requests_share_service(self):
        """Two concurrent requests both succeed and share the same service."""
        fake_result = SimpleNamespace(
            text="hello", initialization_status="ok",
            effective_device="unknown", physical_telemetry={"before": None, "after": None},
        )
        results = []
        errors = []

        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.return_value = fake_result

            def make_request():
                try:
                    status, _, _ = self.h.post("/v1/openvino/infer", {
                        "model_id": "ov-model", "prompt": "Hi", "device": "CPU", "max_tokens": 4,
                    })
                    results.append(status)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            t1 = threading.Thread(target=make_request)
            t2 = threading.Thread(target=make_request)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(s == 200 for s in results))
        # Constructor called only once despite concurrent access
        self.assertEqual(cls.call_count, 1)
        # generate called twice on the same service instance
        self.assertEqual(cls.return_value.generate.call_count, 2)

    def test_service_closed_on_shutdown(self):
        """The shared OpenVINO service is closed when the server shuts down."""
        fake_result = SimpleNamespace(
            text="hello", initialization_status="ok",
            effective_device="unknown", physical_telemetry={"before": None, "after": None},
        )
        with mock.patch("castlearq.openvino_inference.OpenVINOInferenceService") as cls:
            cls.return_value.generate.return_value = fake_result
            self.h.post("/v1/openvino/infer", {
                "model_id": "ov-model", "prompt": "Hi", "device": "CPU", "max_tokens": 4,
            })
            # Service was created
            self.assertEqual(cls.call_count, 1)
            service_instance = cls.return_value
            # Shut down the server
            self.h.close()
            # Service.close() was invoked
            service_instance.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
