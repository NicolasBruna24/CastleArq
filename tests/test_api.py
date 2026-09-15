"""Tests for the read-only HTTP API (Fase 6.1, bloque 1).

These tests exercise the HTTP transport against the real core mapping
functions with minimal doubles: a stub ``ModelStore``-like object and, where
useful, a tiny in-test catalog. No real model is required, llama.cpp is never
executed, nothing is downloaded and Ollama is never touched.
"""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from app.api import (
    APIConfigurationError,
    MAX_REQUEST_BODY_BYTES,
    build_server,
    get_version,
    list_artifact_dtos,
    list_model_dtos,
)
from app.main import main as cli_main
from app.model_store import ModelStore
from app.models import ArtifactSpec, ModelSpec

HOST = "127.0.0.1"


def artifact(**kwargs) -> ArtifactSpec:
    values = {
        "model_id": "qwen2.5-coder-7b-instruct",
        "source": "huggingface",
        "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "filename": "model-q4_k_m.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "size_bytes": 4700,
    }
    values.update(kwargs)
    return ArtifactSpec(**values)


class StubStore:
    """Minimal stand-in exposing the ModelStore.list_artifacts interface."""

    def __init__(self, entries):
        self._entries = list(entries)

    def list_artifacts(self):
        return list(self._entries)


class ServerHarness:
    """Start/stop a real API server on 127.0.0.1:0 in a background thread."""

    def __init__(self, **kwargs):
        self.server = build_server(HOST, 0, **kwargs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    def request(self, method: str, path: str, body: bytes | None = None):
        connection = http.client.HTTPConnection(HOST, self.port, timeout=10)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            connection.close()

    def get_json(self, path: str):
        status, headers, raw = self.request("GET", path)
        return status, headers, json.loads(raw.decode("utf-8"))

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)

    def __enter__(self) -> "ServerHarness":
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()


class ApiServerTests(unittest.TestCase):
    """Shared live server for the endpoint tests."""

    @classmethod
    def setUpClass(cls):
        cls.harness = ServerHarness(model_store=StubStore([]))

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()

    def test_health_returns_ok_and_version(self):
        status, _, payload = self.harness.get_json("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok", "version": get_version()})

    def test_health_version_matches_pyproject_source_of_truth(self):
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(get_version(), data["project"]["version"])

    def test_models_returns_valid_json_catalog(self):
        status, _, payload = self.harness.get_json("/v1/models")
        self.assertEqual(status, 200)
        models = payload["models"]
        self.assertEqual(len(models), 3)
        ids = [model["model_id"] for model in models]
        self.assertIn("qwen2.5-coder-7b-instruct", ids)
        for model in models:
            self.assertTrue(model["name"])
            self.assertIsInstance(model["downloadable"], bool)

    def test_models_expose_downloadability_from_core(self):
        _, _, payload = self.harness.get_json("/v1/models")
        by_id = {model["model_id"]: model for model in payload["models"]}
        downloadable = by_id["qwen2.5-coder-7b-instruct"]
        self.assertTrue(downloadable["downloadable"])
        self.assertEqual(downloadable["download_source"], "huggingface")
        self.assertEqual(
            downloadable["download_repository"],
            "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        )
        self.assertFalse(by_id["llama-3.1-8b-instruct"]["downloadable"])

    def test_artifacts_empty_store_returns_valid_json(self):
        status, _, payload = self.harness.get_json("/v1/artifacts")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"artifacts": []})

    def test_unknown_route_returns_404(self):
        status, _, payload = self.harness.get_json("/v1/unknown")
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "not found"})

    def test_post_on_get_endpoints_returns_405_with_allow(self):
        for path in ("/health", "/v1/models", "/v1/artifacts"):
            status, headers, raw = self.harness.request("POST", path)
            self.assertEqual(status, 405)
            self.assertEqual(headers["Allow"], "GET")
            self.assertEqual(json.loads(raw), {"error": "method not allowed"})

    def test_content_type_is_json_on_success_and_errors(self):
        for path, method in (
            ("/health", "GET"),
            ("/v1/models", "GET"),
            ("/v1/artifacts", "GET"),
            ("/v1/unknown", "GET"),
            ("/health", "POST"),
        ):
            status, headers, _ = self.harness.request(method, path)
            self.assertTrue(status in (200, 404, 405))
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")

    def test_get_with_body_is_rejected(self):
        status, _, raw = self.harness.request("GET", "/health", body=b"x")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "GET requests must not include a body"})

    def test_oversized_request_body_is_rejected(self):
        connection = http.client.HTTPConnection(HOST, self.harness.port, timeout=10)
        try:
            connection.request(
                "GET",
                "/health",
                headers={"Content-Length": str(MAX_REQUEST_BODY_BYTES + 1)},
            )
            response = connection.getresponse()
            raw = response.read()
            self.assertEqual(response.status, 413)
            self.assertEqual(json.loads(raw), {"error": "request body too large"})
        finally:
            connection.close()

    def test_internal_error_returns_json_500_without_stack_trace(self):
        class ExplodingStore:
            def list_artifacts(self):
                raise RuntimeError("secret failure detail /tmp/secret/path")

        with ServerHarness(model_store=ExplodingStore()) as harness:
            status, _, raw = harness.request("GET", "/v1/artifacts")
        self.assertEqual(status, 500)
        text = raw.decode("utf-8")
        self.assertEqual(json.loads(text), {"error": "internal server error"})
        self.assertNotIn("RuntimeError", text)
        self.assertNotIn("secret failure detail", text)


class ArtifactEndpointTests(unittest.TestCase):
    """Artifact listing against a real temporary ModelStore (no downloads)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(Path(self._tmp.name))

    def _start(self) -> ServerHarness:
        harness = ServerHarness(model_store=self.store)
        self.addCleanup(harness.stop)
        return harness

    def test_artifacts_endpoint_lists_saved_manifests(self):
        spec = artifact()
        self.store.save_manifest(spec)
        status, _, payload = self._start().get_json("/v1/artifacts")
        self.assertEqual(status, 200)
        entries = payload["artifacts"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(
            set(entry),
            {
                "model_id",
                "filename",
                "quantization",
                "size_bytes",
                "state",
                "artifact_id",
                "message",
            },
        )
        self.assertEqual(entry["model_id"], spec.model_id)
        self.assertEqual(entry["filename"], spec.filename)
        self.assertEqual(entry["quantization"], spec.quantization)
        self.assertEqual(entry["size_bytes"], 4700)
        self.assertEqual(entry["state"], "not_downloaded")
        self.assertEqual(entry["artifact_id"], spec.artifact_id)

    def test_artifact_dtos_do_not_expose_absolute_paths(self):
        self.store.save_manifest(artifact())
        self.store.save_manifest(artifact(filename="second.gguf"))
        # A manifest that fails inspection: its raw error could embed a path.
        model_dir = self.store.root / "qwen2.5-coder-7b-instruct"
        broken_dir = model_dir / "brokenartifact"
        broken_dir.mkdir(parents=True)
        (broken_dir / "manifest.json").write_text('{"model_id": ""}', encoding="utf-8")
        _, _, raw = self._start().request("GET", "/v1/artifacts")
        text = raw.decode("utf-8")
        self.assertNotIn(str(self._tmp.name), text)
        self.assertNotIn(str(Path.home()), text)
        payload = json.loads(text)
        for entry in payload["artifacts"]:
            self.assertNotIn("manifest_path", entry)
            self.assertNotIn("local_path", entry)
            self.assertNotIn("path", entry)

    def test_invalid_manifests_collapse_to_generic_note(self):
        model_dir = self.store.root / "broken"
        model_dir.mkdir(parents=True)
        (model_dir / "badartifact").mkdir()
        (model_dir / "badartifact" / "manifest.json").write_text(
            '{"model_id": ""}', encoding="utf-8"
        )
        _, _, payload = self._start().get_json("/v1/artifacts")
        entry = payload["artifacts"][0]
        self.assertIsNone(entry["model_id"])
        self.assertEqual(entry["state"], "failed")
        self.assertEqual(entry["message"], "invalid manifest")

    def test_artifacts_are_deterministically_ordered(self):
        self.store.save_manifest(artifact(filename="b.gguf"))
        self.store.save_manifest(artifact(filename="a.gguf"))
        _, _, payload = self._start().get_json("/v1/artifacts")
        filenames = [entry["filename"] for entry in payload["artifacts"]]
        self.assertEqual(filenames, ["a.gguf", "b.gguf"])

    def test_list_artifact_dtos_orders_invalid_entries_last(self):
        self.store.save_manifest(artifact())
        model_dir = self.store.root / "broken"
        model_dir.mkdir(parents=True)
        (model_dir / "zz").mkdir()
        (model_dir / "zz" / "manifest.json").write_text("not json", encoding="utf-8")
        dtos = list_artifact_dtos(self.store)
        self.assertEqual([dto.state for dto in dtos], ["not_downloaded", "failed"])
        self.assertEqual(dtos[-1].artifact_id, None)


class ModelDtoTests(unittest.TestCase):
    """Direct DTO mapping with a tiny injected catalog."""

    TINY_CATALOG = (
        ModelSpec(
            name="Tiny Model",
            id="tiny/model",
            provider="Tiny",
            family="Tiny",
            parameter_count_b=1.0,
            task="general-purpose",
            context_length=2048,
        ),
    )

    def test_model_dto_fields_and_no_unsafe_keys(self):
        dtos = list_model_dtos(self.TINY_CATALOG)
        self.assertEqual(len(dtos), 1)
        payload = dtos[0].to_dict()
        self.assertEqual(payload["model_id"], "tiny/model")
        self.assertEqual(payload["name"], "Tiny Model")
        self.assertFalse(payload["downloadable"])
        self.assertIsNone(payload["download_source"])
        for forbidden in ("path", "argv", "env", "environment", "manifest_path"):
            self.assertNotIn(forbidden, payload)

    def test_model_dtos_are_deterministic(self):
        first = [dto.to_dict() for dto in list_model_dtos()]
        second = [dto.to_dict() for dto in list_model_dtos()]
        self.assertEqual(first, second)


class ServerLifecycleTests(unittest.TestCase):
    """Binding, shutdown and loopback safety."""

    def test_server_binds_ephemeral_loopback_port(self):
        with ServerHarness() as harness:
            host, port = harness.server.server_address[:2]
            self.assertEqual(host, HOST)
            self.assertNotEqual(port, 0)

    def test_server_can_be_shutdown_cleanly(self):
        harness = ServerHarness()
        harness.stop()
        self.assertFalse(harness.thread.is_alive())

    def test_non_loopback_hosts_are_rejected(self):
        for bad_host in ("0.0.0.0", "192.168.1.10", "", "10.0.0.1"):
            with self.assertRaises(APIConfigurationError):
                build_server(bad_host, 0)

    def test_loopback_alias_and_secondary_loopback_are_accepted(self):
        for ok_host in ("localhost", "127.0.0.2"):
            server = build_server(ok_host, 0)
            server.server_close()

    def test_cli_serve_wiring(self):
        argv = ["localai", "serve"]
        with mock.patch("app.main.serve", return_value=0) as serve_mock, mock.patch(
            "sys.argv", argv
        ):
            exit_code = cli_main()
        self.assertEqual(exit_code, 0)
        serve_mock.assert_called_once_with(host="127.0.0.1", port=8000)

    def test_cli_rejects_host_flag_for_non_serve_commands(self):
        argv = ["localai", "models", "--host", "127.0.0.1"]
        with mock.patch("sys.argv", argv), self.assertRaises(SystemExit) as caught:
            cli_main()
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()