
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

"""Tests for the local HTTP API (Fase 6.1, bloques 1-2).

These tests exercise the HTTP transport against the real core mapping
functions with minimal doubles: a stub ``ModelStore``-like object and, where
useful, a tiny in-test catalog. ``POST /v1/run`` tests patch
``app.api.run_once`` so no real model is required, llama.cpp is never
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
    parse_run_request,
)
from app.main import main as cli_main
from app.model_store import ModelStore
from app.models import ArtifactSpec, ModelSpec
from app.run_service import RunDependencies, RunOutcome

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

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        headers: dict | None = None,
    ):
        connection = http.client.HTTPConnection(HOST, self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            connection.close()

    def post_json(self, path: str, payload, *, raw_body: bytes | None = None):
        if raw_body is not None:
            body = raw_body
        elif payload is None:
            body = None
        else:
            body = json.dumps(payload).encode("utf-8")
        return self.request(
            "POST", path, body=body,
            headers={"Content-Type": "application/json"},
        )

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
            self.assertEqual(headers["Allow"], "GET, POST")
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
        argv = ["castlearq", "serve"]
        with mock.patch("app.main.serve", return_value=0) as serve_mock, mock.patch(
            "sys.argv", argv
        ):
            exit_code = cli_main()
        self.assertEqual(exit_code, 0)
        serve_mock.assert_called_once_with(host="127.0.0.1", port=8000)

    def test_cli_rejects_host_flag_for_non_serve_commands(self):
        argv = ["castlearq", "models", "--host", "127.0.0.1"]
        with mock.patch("sys.argv", argv), self.assertRaises(SystemExit) as caught:
            cli_main()
        self.assertEqual(caught.exception.code, 2)


def _run_outcome(**kwargs) -> RunOutcome:
    values = {
        "model_id": "qwen2.5-coder-7b-instruct",
        "output": "hello from fake runtime",
        "exit_code": 0,
        "warnings": (),
    }
    values.update(kwargs)
    return RunOutcome(**values)


class RunEndpointTests(unittest.TestCase):
    """POST /v1/run: validation, core-error mapping and the global lock."""

    def test_valid_request_returns_200_with_run_dto(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=_run_outcome()
        ) as run_mock:
            status, headers, raw = harness.post_json(
                "/v1/run",
                {"model_id": "qwen2.5-coder-7b-instruct", "prompt": "Hello"},
            )
        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Content-Type"], "application/json; charset=utf-8"
        )
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(payload["model_id"], "qwen2.5-coder-7b-instruct")
        self.assertEqual(payload["output"], "hello from fake runtime")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["warnings"], [])
        run_mock.assert_called_once()
        _, kwargs = run_mock.call_args
        self.assertIsInstance(kwargs.get("dependencies"), RunDependencies)

    def test_optional_fields_are_forwarded(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=_run_outcome()
        ) as run_mock:
            status, _, _ = harness.post_json(
                "/v1/run",
                {
                    "model_id": "m",
                    "prompt": "p",
                    "quantization": "Q4_K_M",
                    "filename": "model.gguf",
                    "timeout": 120,
                },
            )
        self.assertEqual(status, 200)
        _, kwargs = run_mock.call_args
        self.assertEqual(kwargs.get("quantization"), "Q4_K_M")
        self.assertEqual(kwargs.get("filename"), "model.gguf")
        self.assertEqual(kwargs.get("timeout_seconds"), 120.0)

    def test_run_dto_parsing_rejects_bad_inputs(self):
        self.assertEqual(
            parse_run_request({"model_id": "m", "prompt": "p"}).model_id, "m"
        )
        bad_payloads = (
            [1, 2], "text", None, 42, {},
            {"model_id": "m"}, {"prompt": "p"},
            {"model_id": "", "prompt": "p"},
            {"model_id": None, "prompt": "p"},
            {"model_id": "m", "prompt": None},
            {"model_id": "m", "prompt": "  "},
            {"model_id": 1, "prompt": "p"},
            {"model_id": "m", "prompt": 5},
            {"model_id": "m", "prompt": "p", "foo": "bar"},
            {"model_id": "m", "prompt": "p", "argv": ["x"]},
            {"model_id": "m", "prompt": "p", "environment": {}},
            {"model_id": "m", "prompt": "p", "path": "/tmp/x"},
            {"model_id": "m", "prompt": "p", "timeout": True},
            {"model_id": "m", "prompt": "p", "timeout": -1},
            {"model_id": "m", "prompt": "p", "timeout": 0},
            {"model_id": "m", "prompt": "p", "timeout": "x"},
            {"model_id": "m", "prompt": "p", "quantization": 5},
        )
        for bad in bad_payloads:
            with self.subTest(payload=bad):
                with self.assertRaises(ValueError):
                    parse_run_request(bad)

    def test_invalid_json_returns_400(self):
        with ServerHarness(model_store=StubStore([])) as harness:
            status, _, raw = harness.post_json(
                "/v1/run", None, raw_body=b"{not json"
            )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid JSON"})

    def test_unknown_field_returns_400(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=_run_outcome()
        ) as run_mock:
            status, _, raw = harness.post_json(
                "/v1/run",
                {"model_id": "m", "prompt": "p", "foo": "bar"},
            )
        self.assertEqual(status, 400)
        self.assertIn("unknown field", json.loads(raw)["error"])
        run_mock.assert_not_called()

    def test_missing_and_mistyped_fields_return_400(self):
        cases = (
            {"prompt": "p"},
            {"model_id": "m"},
            {"model_id": None, "prompt": "p"},
            {"model_id": "m", "prompt": None},
            {"model_id": "m", "prompt": "p", "timeout": True},
            {"model_id": "m", "prompt": "p", "timeout": -5},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with ServerHarness(
                    model_store=StubStore([])
                ) as harness, mock.patch(
                    "app.api.run_once", return_value=_run_outcome()
                ) as run_mock:
                    status, _, _ = harness.post_json("/v1/run", payload)
                self.assertEqual(status, 400)
                run_mock.assert_not_called()

    def test_oversized_run_body_returns_413(self):
        big = b'{"model_id": "m", "prompt": "' + b"x" * (
            MAX_REQUEST_BODY_BYTES + 1
        ) + b'"}'
        assert len(big) > MAX_REQUEST_BODY_BYTES
        with ServerHarness(model_store=StubStore([])) as harness:
            status, _, raw = harness.post_json("/v1/run", None, raw_body=big)
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(raw), {"error": "request body too large"})

    def test_wrong_content_type_returns_400(self):
        with ServerHarness(model_store=StubStore([])) as harness:
            status, _, raw = harness.request(
                "POST", "/v1/run", body=b"{}",
                headers={"Content-Type": "text/plain"},
            )
        self.assertEqual(status, 400)
        self.assertIn("Content-Type", json.loads(raw)["error"])

    def test_unknown_model_returns_404(self):
        from app.run_service import ModelNotFoundError

        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once",
            side_effect=ModelNotFoundError("Model not found: nope"),
        ):
            status, _, _ = harness.post_json(
                "/v1/run", {"model_id": "nope", "prompt": "hi"}
            )
        self.assertEqual(status, 404)

    def test_preparation_failure_returns_422(self):
        from app.run_service import RunPreparationFailedError

        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once",
            side_effect=RunPreparationFailedError("artifact not found"),
        ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(raw), {"error": "artifact not found"})

    def test_runtime_failure_returns_503(self):
        from app.run_service import RunExecutionFailedError

        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once",
            side_effect=RunExecutionFailedError("llama.cpp exited"),
        ):
            status, _, _ = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 503)

    def test_unexpected_error_returns_500_without_details(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once",
            side_effect=RuntimeError("secret /tmp/boom --argv"),
        ):
            status, _, raw = harness.request(
                "POST", "/v1/run",
                body=b'{"model_id": "m", "prompt": "hi"}',
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(status, 500)
        text = raw.decode("utf-8")
        self.assertEqual(json.loads(text), {"error": "internal server error"})
        self.assertNotIn("secret", text)
        self.assertNotIn("/tmp/boom", text)

    def test_concurrent_run_returns_409(self):
        started = threading.Event()
        release = threading.Event()

        def slow_run(*args, **kwargs):
            started.set()
            assert release.wait(timeout=10)
            return _run_outcome()

        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", side_effect=slow_run
        ):
            results = {}

            def first():
                results["first"] = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "one"}
                )

            worker = threading.Thread(target=first, daemon=True)
            worker.start()
            self.assertTrue(started.wait(timeout=10))
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )
            self.assertEqual(status, 409)
            self.assertIn("already running", json.loads(raw)["error"])
            release.set()
            worker.join(timeout=10)
        self.assertEqual(results["first"][0], 200)

    def test_lock_released_after_success(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=_run_outcome()
        ):
            first = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "one"}
            )[0]
            second = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )[0]
        self.assertEqual((first, second), (200, 200))

    def test_lock_released_after_failure(self):
        from app.run_service import RunExecutionFailedError

        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RunExecutionFailedError("boom")
            return _run_outcome()

        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", side_effect=flaky
        ):
            first = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "one"}
            )[0]
            second = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )[0]
        self.assertEqual((first, second), (503, 200))

    def test_response_contains_no_paths_or_process_details(self):
        outcome = _run_outcome(output="ok generated text", warnings=("slow",))
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=outcome
        ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(
            sorted(payload), ["exit_code", "model_id", "output", "warnings"]
        )
        for forbidden in ("argv", "env", "environment", "command", "local_path"):
            self.assertNotIn(forbidden, payload)
            self.assertNotIn(forbidden, raw.decode("utf-8"))

    def test_api_does_not_shell_out_to_cli(self):
        with ServerHarness(model_store=StubStore([])) as harness, mock.patch(
            "app.api.run_once", return_value=_run_outcome()
        ), mock.patch("subprocess.run") as subprocess_mock, mock.patch(
            "app.main.run_model"
        ) as cli_mock:
            status, _, _ = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 200)
        subprocess_mock.assert_not_called()
        cli_mock.assert_not_called()



if __name__ == "__main__":
    unittest.main()