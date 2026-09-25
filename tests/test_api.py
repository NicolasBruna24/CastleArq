
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
useful, a tiny in-test catalog.

B9.52: ``POST /v1/run`` no longer calls the legacy ``run_service.run_once``.
It now crosses the ratified admission contract (evaluation -> ``to_admission``
-> ``execute_model``), so these tests patch ``app.api.evaluate_model_compatibility``
to control the policy input and ``app.api.execute_model`` to control execution.
llama.cpp is never executed, nothing is downloaded and Ollama is never touched.
The gate itself is the real one -- only its inputs are doubles.
"""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
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


def _evaluation(
    model_id, *, status="evaluated", verdict="compatible",
    blocking_outcome=None,
):
    """A stand-in ``EvaluateModelCompatibilityResult``.

    B9.52 controls the *policy input* only. The admission projection
    (``to_admission``) and the gate (``_check_admission``) are the real ones,
    so these tests exercise the production decision, not a re-implementation.
    """
    evaluation = (
        SimpleNamespace(result=SimpleNamespace(status=verdict))
        if verdict is not None
        else None
    )
    return SimpleNamespace(
        model_id=model_id,
        artifact=None,
        runtime="fake-llama.cpp",
        capability=None,
        evaluation=evaluation,
        integration=None,
        status=status,
        blocking_outcome=blocking_outcome,
    )


def _execution_result(success=True, stdout="hello from fake runtime",
                      exit_code=0, warnings=(), error=None):
    """A stand-in ``ExecutionResult`` (what ``execute_model`` returns)."""
    return SimpleNamespace(
        success=success,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        error=error,
        warnings=tuple(warnings),
        diagnostics=None,
        runtime_metrics=None,
    )


def _not_found(model_id):
    """The blocked evaluation the resolver produces for an unknown model."""
    return _evaluation(
        model_id, status="blocked", verdict=None,
        blocking_outcome=f"Model not found in the local catalog: {model_id}",
    )


class GateHarness:
    """Patch the evaluation + execution seams for one request.

    ``verdict`` drives the policy input, ``result``/``error`` drive execution.
    Defaults to a compatible evaluation and a successful execution, i.e. the
    happy path; each test overrides only what it is about.
    """

    def __init__(self, *, verdict="compatible", evaluation=None,
                 result=None, error=None, eval_error=None, status="evaluated"):
        self.verdict = verdict
        self._evaluation = evaluation
        self._result = result
        self._error = error
        self._eval_error = eval_error
        self._status = status
        self.evaluations = []
        self.executions = []

    def __enter__(self):
        def evaluate(model_id, **kwargs):
            self.evaluations.append((model_id, kwargs))
            if self._eval_error is not None:
                raise self._eval_error
            if self._evaluation is not None:
                return self._evaluation
            return _evaluation(model_id, status=self._status,
                               verdict=self.verdict)

        def execute(**kwargs):
            self.executions.append(kwargs)
            if self._error is not None:
                raise self._error
            return self._result or _execution_result()

        self._p1 = mock.patch("app.api.evaluate_model_compatibility",
                              side_effect=evaluate)
        self._p2 = mock.patch("app.api.execute_model", side_effect=execute)
        self._p3 = mock.patch("app.api.compose_execute_model_dependencies",
                              return_value=object())
        self._p1.start()
        self._p2.start()
        self._p3.start()
        return self

    def __exit__(self, *exc):
        for patcher in (self._p3, self._p2, self._p1):
            patcher.stop()
        return False


class RunEndpointTests(unittest.TestCase):
    """POST /v1/run under the B9.51 admission contract (implemented in B9.52).

    Covers validation, the full status mapping, the rejection bodies, the
    global lock and the guarantee that a refusal never reaches the runner.
    """

    def test_valid_request_returns_200_with_run_dto(self):
        """16.1 happy path: evaluation -> admission -> execution -> 200."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness() as gate:
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
        # The contract requires the gate to be crossed BEFORE execution.
        self.assertEqual(len(gate.evaluations), 1)
        self.assertEqual(len(gate.executions), 1)
        # And the admission actually minted is the one handed to the use case.
        admission = gate.executions[0]["admission"]
        self.assertEqual(admission.status, "evaluated")
        self.assertEqual(admission.verdict, "compatible")

    def test_optional_fields_are_forwarded(self):
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness() as gate:
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
        _, eval_kwargs = gate.evaluations[0]
        self.assertEqual(eval_kwargs.get("quantization"), "Q4_K_M")
        self.assertEqual(eval_kwargs.get("filename"), "model.gguf")
        exec_kwargs = gate.executions[0]
        self.assertEqual(exec_kwargs.get("quantization"), "Q4_K_M")
        self.assertEqual(exec_kwargs.get("filename"), "model.gguf")
        self.assertEqual(exec_kwargs.get("timeout_seconds"), 120.0)

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
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness() as gate:
            status, _, raw = harness.post_json(
                "/v1/run",
                {"model_id": "m", "prompt": "p", "foo": "bar"},
            )
        self.assertEqual(status, 400)
        self.assertIn("unknown field", json.loads(raw)["error"])
        # Validation precedes the lock, the evaluation and execution.
        self.assertEqual(gate.evaluations, [])
        self.assertEqual(gate.executions, [])

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
                ) as harness, GateHarness() as gate:
                    status, _, _ = harness.post_json("/v1/run", payload)
                self.assertEqual(status, 400)
                self.assertEqual(gate.executions, [])

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
        """An absent model is 404 (unchanged), not a 403 refusal."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness() as gate:
            def evaluate(model_id, **kwargs):
                gate.evaluations.append((model_id, kwargs))
                return _not_found(model_id)
            with mock.patch("app.api.evaluate_model_compatibility",
                            side_effect=evaluate):
                status, _, raw = harness.post_json(
                    "/v1/run", {"model_id": "nope", "prompt": "hi"}
                )
        self.assertEqual(status, 404)
        self.assertIn("not found", json.loads(raw)["error"].lower())
        self.assertEqual(gate.executions, [])

    def test_admission_denied_returns_403_with_the_ratified_body(self):
        """16.2 INCOMPATIBLE -> 403 + admission body, and no execution."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(verdict="incompatible") as gate:
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 403)
        self.assertEqual(
            json.loads(raw),
            {
                "error": "execution refused by compatibility admission",
                "admission": {"status": "evaluated", "verdict": "incompatible"},
            },
        )
        # 16.8: a refusal must never reach the runner.
        self.assertEqual(gate.executions, [])

    def test_insufficient_evidence_is_denied(self):
        """insufficient_evidence is not an admitting verdict -> 403."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(verdict="insufficient_evidence") as gate:
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 403)
        self.assertEqual(
            json.loads(raw)["admission"],
            {"status": "evaluated", "verdict": "insufficient_evidence"},
        )
        self.assertEqual(gate.executions, [])

    def test_blocked_evaluation_is_denied(self):
        """A blocked evaluation carries no verdict and still refuses."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(status="blocked", verdict=None) as gate:
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 403)
        self.assertEqual(
            json.loads(raw)["admission"], {"status": "blocked", "verdict": None}
        )
        self.assertEqual(gate.executions, [])

    def test_evaluation_exception_returns_500_and_is_not_a_denial(self):
        """16.3 an evaluation that RAISED is 500, never a false INCOMPATIBLE."""
        boom = RuntimeError("gguf header corrupt at /models/secret.gguf")
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(eval_error=boom) as gate:
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 500)
        text = raw.decode("utf-8")
        self.assertEqual(
            json.loads(text),
            {
                "error": "compatibility evaluation failed",
                "admission": {"status": "blocked", "verdict": None},
            },
        )
        # No verdict is invented, no internal detail leaks, nothing ran.
        self.assertNotIn("INCOMPATIBLE", text)
        self.assertNotIn("incompatible", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("gguf", text)
        self.assertNotIn("secret.gguf", text)
        self.assertNotIn("corrupt", text)
        self.assertEqual(gate.executions, [])

    def test_rejection_bodies_expose_only_the_admission_summary(self):
        """7.2: no checks, evidence, paths or diagnostics reach the client."""
        for verdict in ("incompatible", "insufficient_evidence"):
            with self.subTest(verdict=verdict):
                with ServerHarness(model_store=StubStore([])) as harness, \
                        GateHarness(verdict=verdict):
                    _, _, raw = harness.post_json(
                        "/v1/run", {"model_id": "m", "prompt": "hi"}
                    )
                payload = json.loads(raw)
                # Assert on the KEYS, not on substrings: the verdict value
                # "insufficient_evidence" legitimately contains the word
                # "evidence", which must not be confused with a leaked
                # evidence payload.
                self.assertEqual(sorted(payload), ["admission", "error"])
                self.assertEqual(sorted(payload["admission"]),
                                 ["status", "verdict"])
                self.assertEqual(payload["admission"]["verdict"], verdict)
                text = raw.decode("utf-8")
                for forbidden in ("checks", "diagnostics", "expected",
                                  "observed", "artifact", "capability",
                                  "filename", "/", "\\"):
                    self.assertNotIn(forbidden, text)

    def test_preparation_failure_returns_422(self):
        from app.execute_model import ExecutePreparationError

        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(
                    error=ExecutePreparationError("artifact not found")
                ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(raw), {"error": "artifact not found"})

    def test_preparation_failure_preserves_warnings(self):
        """5.2: 422 keeps its shape and gains the optional warnings."""
        from app.execute_model import ExecutePreparationError

        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(
                    error=ExecutePreparationError(
                        "no executable target",
                        warnings=("cpu fallback selected",),
                    )
                ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 422)
        self.assertEqual(
            json.loads(raw),
            {"error": "no executable target",
             "warnings": ["cpu fallback selected"]},
        )

    def test_admission_denied_inside_execute_model_is_still_403(self):
        """10: the defence in depth maps ExecuteAdmissionDeniedError to 403."""
        from app.execute_model import ExecuteAdmissionDeniedError

        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(
                    error=ExecuteAdmissionDeniedError("denied by evaluation")
                ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 403)
        self.assertEqual(
            json.loads(raw)["error"],
            "execution refused by compatibility admission",
        )

    def test_runtime_failure_returns_503(self):
        """A failed run is a result, not an exception -> 503."""
        failure = SimpleNamespace(
            code="runtime_error", message="llama.cpp exited with status 1"
        )
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(
                    result=_execution_result(
                        success=False, stdout="", exit_code=1, error=failure
                    )
                ):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 503)
        self.assertEqual(
            json.loads(raw)["error"], "llama.cpp exited with status 1"
        )

    def test_unexpected_error_returns_500_without_details(self):
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(error=RuntimeError("secret /tmp/boom --argv")):
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
        """16.6: request A holds the lock, request B is refused, not queued."""
        started = threading.Event()
        release = threading.Event()

        def slow_execute(**kwargs):
            started.set()
            assert release.wait(timeout=10)
            return _execution_result()

        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness() as gate, mock.patch(
                    "app.api.execute_model", side_effect=slow_execute):
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
            # The refused request never even evaluated: the lock is taken
            # before evaluation, so B did no work at all.
            self.assertEqual(len(gate.evaluations), 1)
            release.set()
            worker.join(timeout=10)
        self.assertEqual(results["first"][0], 200)

    def test_lock_is_released_and_a_later_request_is_served(self):
        """20: A acquires, B -> 409, A finishes, C is allowed."""
        started = threading.Event()
        release = threading.Event()
        gate = GateHarness()

        def slow_execute(**kwargs):
            started.set()
            assert release.wait(timeout=10)
            return _execution_result()

        with ServerHarness(model_store=StubStore([])) as harness, gate, \
                mock.patch("app.api.execute_model", side_effect=slow_execute):
            worker = threading.Thread(
                target=lambda: harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "one"}
                ),
                daemon=True,
            )
            worker.start()
            self.assertTrue(started.wait(timeout=10))
            busy = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )[0]
            release.set()
            worker.join(timeout=10)
            # A is finished: the very next request must be served normally.
            after = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "three"}
            )[0]
        self.assertEqual(busy, 409)
        self.assertEqual(after, 200)

    def test_lock_released_after_success(self):
        with ServerHarness(model_store=StubStore([])) as harness, GateHarness():
            first = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "one"}
            )[0]
            second = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )[0]
        self.assertEqual((first, second), (200, 200))

    def test_lock_released_after_admission_denial(self):
        """16.7: a refusal must not leave the server locked forever."""
        with ServerHarness(model_store=StubStore([])) as harness:
            with GateHarness(verdict="incompatible"):
                denied = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "one"}
                )[0]
            with GateHarness():
                allowed = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "two"}
                )[0]
        self.assertEqual((denied, allowed), (403, 200))

    def test_lock_released_after_evaluation_error(self):
        """16.7: a failed evaluation must not leave the server locked."""
        with ServerHarness(model_store=StubStore([])) as harness:
            with GateHarness(eval_error=RuntimeError("gguf unreadable")):
                failed = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "one"}
                )[0]
            with GateHarness():
                allowed = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "two"}
                )[0]
        self.assertEqual((failed, allowed), (500, 200))

    def test_lock_released_after_preparation_failure(self):
        from app.execute_model import ExecutePreparationError

        with ServerHarness(model_store=StubStore([])) as harness:
            with GateHarness(error=ExecutePreparationError("no artifact")):
                failed = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "one"}
                )[0]
            with GateHarness():
                allowed = harness.post_json(
                    "/v1/run", {"model_id": "m", "prompt": "two"}
                )[0]
        self.assertEqual((failed, allowed), (422, 200))

    def test_lock_released_after_failure(self):
        failure = SimpleNamespace(code="runtime_error", message="boom")

        def flaky(**kwargs):
            if not hasattr(flaky, "seen"):
                flaky.seen = True
                return _execution_result(
                    success=False, stdout="", exit_code=1, error=failure
                )
            return _execution_result()

        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(result=_execution_result()), \
                mock.patch("app.api.execute_model", side_effect=flaky):
            first = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "one"}
            )[0]
            second = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "two"}
            )[0]
        self.assertEqual((first, second), (503, 200))

    def test_response_contains_no_paths_or_process_details(self):
        result = _execution_result(
            stdout="ok generated text", warnings=("slow",)
        )
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(result=result):
            status, _, raw = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(
            sorted(payload), ["exit_code", "model_id", "output", "warnings"]
        )
        self.assertEqual(payload["warnings"], ["slow"])
        for forbidden in ("argv", "env", "environment", "command", "local_path"):
            self.assertNotIn(forbidden, payload)
            self.assertNotIn(forbidden, raw.decode("utf-8"))

    def test_api_does_not_shell_out_to_cli(self):
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(), mock.patch("subprocess.run") as subprocess_mock, \
                mock.patch("app.main.run_model") as cli_mock:
            status, _, _ = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 200)
        subprocess_mock.assert_not_called()
        cli_mock.assert_not_called()

    def test_api_does_not_fall_back_to_the_legacy_run_pipeline(self):
        """B9.52: /v1/run must not silently keep the ungated legacy path."""
        with ServerHarness(model_store=StubStore([])) as harness, \
                GateHarness(), \
                mock.patch("app.run_service.run_once") as legacy_mock:
            status, _, _ = harness.post_json(
                "/v1/run", {"model_id": "m", "prompt": "hi"}
            )
        self.assertEqual(status, 200)
        legacy_mock.assert_not_called()



if __name__ == "__main__":
    unittest.main()