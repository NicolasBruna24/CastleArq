
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

"""Tests for Block 3.1 chat session lifecycle (HTTP, no turns)."""
from __future__ import annotations
import http.client
import json
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock
from app import api as api_module
from app.api import MAX_CHAT_SESSIONS, MAX_REQUEST_BODY_BYTES, _ChatSessionRegistry, build_server, parse_chat_session_request, parse_session_id


class FakeSession:
    def __init__(self, state_value="ready", turns=()):
        self.state = SimpleNamespace(value=state_value)
        self.turns = tuple(turns)
        self.close_count = 0
        self.close_error = None

    def close(self):
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error


def _opened(model_id="m", session=None):
    return ChatSessionOpened(session=session or FakeSession(), model_id=model_id)


class ServerHarness:
    def __init__(self, **kwargs):
        self.server = build_server(HOST, 0, **kwargs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.server.server_address[1]

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection(HOST, self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def post_json(self, path, payload, raw_body=None, content_type="application/json"):
        body = raw_body if raw_body is not None else (
            None if payload is None else json.dumps(payload).encode())
        return self.request("POST", path, body=body,
                            headers={"Content-Type": content_type})

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

from app.run_service import ChatLaunchFailedError, ChatSessionOpened, ModelNotFoundError, RunPreparationFailedError
HOST = "127.0.0.1"

class ParseTests(unittest.TestCase):
    def test_valid(self):
        dto = parse_chat_session_request({"model_id": "m"})
        self.assertEqual(dto.model_id, "m")
        dto2 = parse_chat_session_request(
            {"model_id": "m", "quantization": "Q4_K_M", "filename": "a.gguf"})
        self.assertEqual(dto2.quantization, "Q4_K_M")

    def test_rejects(self):
        for bad in (None, [], "x", 5):
            with self.assertRaises(ValueError):
                parse_chat_session_request(bad)
        for field in ("path", "argv", "env", "command", "executable",
                      "artifact_path", "runtime", "backend", "prompt"):
            with self.assertRaises(ValueError):
                parse_chat_session_request({"model_id": "m", field: "x"})
        for payload in ({"model_id": 5}, {"model_id": "  "},
                        {"model_id": "m", "quantization": ""},
                        {"model_id": "m", "filename": ""},
                        {"quantization": "Q4_K_M"}):
            with self.assertRaises(ValueError):
                parse_chat_session_request(payload)

    def test_session_id(self):
        good = str(uuid.uuid4())
        self.assertEqual(parse_session_id(good), good)
        for bad in ("", "not-a-uuid", "123"):
            with self.assertRaises(ValueError):
                parse_session_id(bad)


class PostTests(unittest.TestCase):
    def test_create_201(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("my-model")):
            status, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "my-model"})
        self.assertEqual(status, 201)
        payload = json.loads(raw.decode())
        self.assertEqual(sorted(payload), ["model_id", "session_id", "status"])
        uuid.UUID(payload["session_id"], version=4)
        self.assertNotIn("argv", raw.decode().lower())

    def test_distinct_ids(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=[_opened("m"), _opened("m")]):
            _, _, r1 = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            _, _, r2 = h.post_json("/v1/chat/sessions", {"model_id": "m"})
        self.assertNotEqual(json.loads(r1)["session_id"], json.loads(r2)["session_id"])

    def test_404(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", side_effect=ModelNotFoundError("nope")):
            status, _, _ = h.post_json("/v1/chat/sessions", {"model_id": "ghost"})
        self.assertEqual(status, 404)

    def test_422(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=RunPreparationFailedError("bad")):
            status, _, _ = h.post_json("/v1/chat/sessions", {"model_id": "m"})
        self.assertEqual(status, 422)

    def test_503_no_leak(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=ChatLaunchFailedError("/tmp/secret boom")):
            status, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
        self.assertEqual(status, 503)
        self.assertNotIn("/tmp/secret", raw.decode())

    def test_500_no_leak(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", side_effect=RuntimeError("boom")):
            status, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
        self.assertEqual(status, 500)
        self.assertNotIn("boom", raw.decode())

    def test_bad_requests_400(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened()) as fac:
            status, _, _ = h.post_json("/v1/chat/sessions", None, raw_body=b"{bad")
            self.assertEqual(status, 400)
            for raw_body in (b"[]", b'"x"'):
                status, _, _ = h.post_json("/v1/chat/sessions", None, raw_body=raw_body)
                self.assertEqual(status, 400)
            status, _, _ = h.post_json(
                "/v1/chat/sessions", {"model_id": "m", "argv": ["x"]})
            self.assertEqual(status, 400)
            status, _, _ = h.post_json(
                "/v1/chat/sessions", {"model_id": "m"}, content_type="text/plain")
            self.assertEqual(status, 400)
            for payload in ({"model_id": 5}, {"model_id": "  "},
                            {"model_id": "m", "quantization": ""}):
                status, _, _ = h.post_json("/v1/chat/sessions", payload)
                self.assertEqual(status, 400)
        fac.assert_not_called()

    def test_413(self):
        big = b'{"model_id": "' + b"x" * (MAX_REQUEST_BODY_BYTES + 1) + b'"}'
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened()) as fac:
            status, _, _ = h.post_json("/v1/chat/sessions", None, raw_body=big)
        self.assertEqual(status, 413)
        fac.assert_not_called()

    def test_dangerous_fields_400(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened()) as fac:
            for field in ("path", "argv", "env", "command", "executable",
                          "artifact_path", "runtime", "backend"):
                status, _, _ = h.post_json(
                    "/v1/chat/sessions", {"model_id": "m", field: "x"})
                self.assertEqual(status, 400, field)
        fac.assert_not_called()

    def test_max_sessions_409(self):
        sessions = [_opened() for _ in range(MAX_CHAT_SESSIONS)]
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", side_effect=sessions) as fac:
            codes = []
            last = b""
            for _ in range(MAX_CHAT_SESSIONS + 1):
                status, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
                codes.append(status)
                last = raw
        self.assertEqual(codes, [201] * MAX_CHAT_SESSIONS + [409])
        # Pre-check rejects before launching: no extra runtime is started.
        self.assertEqual(fac.call_count, MAX_CHAT_SESSIONS)
        self.assertIn("maximum chat sessions", last.decode())

    def test_failed_open_registers_nothing(self):
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=ChatLaunchFailedError("no runtime")):
            status, _, _ = h.post_json("/v1/chat/sessions", {"model_id": "m"})
        self.assertEqual(status, 503)
        self.assertEqual(len(registry), 0)


class GetDeleteTests(unittest.TestCase):
    def _create(self, h):
        status, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "my-model"})
        self.assertEqual(status, 201)
        return json.loads(raw.decode())["session_id"]

    def test_get_200(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("my-model")):
            sid = self._create(h)
            status, _, raw = h.request("GET", f"/v1/chat/sessions/{sid}")
        self.assertEqual(status, 200)
        payload = json.loads(raw.decode())
        self.assertEqual(payload["turn_count"], 0)
        self.assertEqual(payload["status"], "ready")
        for forbidden in ("argv", "pid", "stderr", "executable", ".gguf"):
            self.assertNotIn(forbidden, raw.decode().lower())

    def test_get_unknown_404(self):
        with ServerHarness() as h:
            status, _, _ = h.request("GET", f"/v1/chat/sessions/{uuid.uuid4()}")
        self.assertEqual(status, 404)

    def test_get_malformed_400(self):
        with ServerHarness() as h:
            status, _, _ = h.request("GET", "/v1/chat/sessions/not-a-uuid")
        self.assertEqual(status, 400)

    def test_delete_204_close_once(self):
        session = FakeSession()
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                return_value=ChatSessionOpened(session=session, model_id="m")):
            _, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            sid = json.loads(raw.decode())["session_id"]
            status, _, body = h.request("DELETE", f"/v1/chat/sessions/{sid}")
            self.assertEqual(status, 204)
            self.assertEqual(body, b"")
            gs, _, _ = h.request("GET", f"/v1/chat/sessions/{sid}")
            self.assertEqual(gs, 404)
        self.assertEqual(session.close_count, 1)

    def test_delete_unknown_404(self):
        with ServerHarness() as h:
            status, _, _ = h.request("DELETE", f"/v1/chat/sessions/{uuid.uuid4()}")
        self.assertEqual(status, 404)

    def test_delete_malformed_400(self):
        with ServerHarness() as h:
            status, _, _ = h.request("DELETE", "/v1/chat/sessions/not-a-uuid")
        self.assertEqual(status, 400)

    def test_double_delete(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("m")):
            _, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            sid = json.loads(raw.decode())["session_id"]
            first, _, _ = h.request("DELETE", f"/v1/chat/sessions/{sid}")
            second, _, _ = h.request("DELETE", f"/v1/chat/sessions/{sid}")
        self.assertEqual((first, second), (204, 404))


class ShutdownTests(unittest.TestCase):
    def test_close_all(self):
        s1, s2 = FakeSession(), FakeSession()
        registry = _ChatSessionRegistry()
        registry.register("a", api_module._ChatSessionEntry(s1, "m"))
        registry.register("b", api_module._ChatSessionEntry(s2, "m"))
        server = build_server(HOST, 0, chat_registry=registry)
        server.server_close()
        self.assertEqual((s1.close_count, s2.close_count), (1, 1))
        self.assertEqual(len(registry), 0)

    def test_bad_close_tolerated(self):
        good, bad = FakeSession(), FakeSession()
        bad.close_error = RuntimeError("boom")
        registry = _ChatSessionRegistry()
        registry.register("good", api_module._ChatSessionEntry(good, "m"))
        registry.register("bad", api_module._ChatSessionEntry(bad, "m"))
        server = build_server(HOST, 0, chat_registry=registry)
        server.server_close()
        self.assertEqual(good.close_count, 1)
        self.assertEqual(len(registry), 0)


class RegressionTests(unittest.TestCase):
    def test_no_shellout_no_cli(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("m")
             ), mock.patch("subprocess.Popen") as popen_mock, mock.patch(
                "subprocess.run") as run_mock, mock.patch(
                "app.main.run_model") as rm, mock.patch(
                "app.main.chat_model") as cm:
            _, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            sid = json.loads(raw.decode())["session_id"]
            h.request("GET", f"/v1/chat/sessions/{sid}")
            h.request("DELETE", f"/v1/chat/sessions/{sid}")
        popen_mock.assert_not_called()
        run_mock.assert_not_called()
        rm.assert_not_called()
        cm.assert_not_called()

    def test_no_subprocess_import(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(api_module.__file__).read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        self.assertNotIn("subprocess", mods)

    def test_turns_not_implemented(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("m")):
            _, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            sid = json.loads(raw.decode())["session_id"]
            status, _, _ = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "hi"})
        self.assertIn(status, (404, 405))


class ServiceTests(unittest.TestCase):
    def test_open_ok(self):
        from app import run_service as rs
        resolved = SimpleNamespace(
            model=SimpleNamespace(model_id="logical-id"), artifact=SimpleNamespace())
        prep = SimpleNamespace(
            executable_artifact=SimpleNamespace(), target=SimpleNamespace())
        cap = SimpleNamespace()
        with mock.patch.object(rs, "ModelArtifactResolver") as rc, mock.patch.object(
                rs, "prepare", return_value=prep):
            rc.return_value.resolve.return_value = resolved
            deps = rs.ChatDependencies(
                model_store=mock.Mock(), models=(), capability=cap,
                session_factory=lambda c, e, t: FakeSession())
            opened = rs.open_chat_session("logical-id", dependencies=deps)
        self.assertEqual(opened.model_id, "logical-id")
        rc.return_value.resolve.assert_called_once_with(
            "logical-id", quantization=None, filename=None)

    def test_open_maps_404_422(self):
        from app import run_service as rs
        mk = rs.ChatDependencies(model_store=mock.Mock(), models=(), capability=object())
        with mock.patch.object(rs, "ModelArtifactResolver") as rc:
            rc.return_value.resolve.side_effect = rs.ModelArtifactResolutionError(
                "Model not found in the local catalog: x")
            with self.assertRaises(ModelNotFoundError):
                rs.open_chat_session("x", dependencies=mk)
        with mock.patch.object(rs, "ModelArtifactResolver") as rc:
            rc.return_value.resolve.side_effect = rs.ModelArtifactResolutionError(
                "No local artifact")
            with self.assertRaises(RunPreparationFailedError):
                rs.open_chat_session("x", dependencies=mk)
        with mock.patch.object(rs, "ModelArtifactResolver") as rc, mock.patch.object(
                rs, "prepare", side_effect=rs.PreparationError("bad")):
            rc.return_value.resolve.return_value = SimpleNamespace(
                model=SimpleNamespace(), artifact=SimpleNamespace())
            with self.assertRaises(RunPreparationFailedError):
                rs.open_chat_session("x", dependencies=mk)

    def test_open_maps_launch(self):
        from app import run_service as rs
        from app.chat import ChatLaunchError
        mk = rs.ChatDependencies(
            model_store=mock.Mock(), models=(), capability=object(),
            session_factory=lambda *a: (_ for _ in ()).throw(
                ChatLaunchError("no runtime")))
        with mock.patch.object(rs, "ModelArtifactResolver") as rc, mock.patch.object(
                rs, "prepare"):
            rc.return_value.resolve.return_value = SimpleNamespace(
                model=SimpleNamespace(model_id="m"), artifact=SimpleNamespace())
            with self.assertRaises(ChatLaunchFailedError):
                rs.open_chat_session("x", dependencies=mk)


if __name__ == "__main__":
    unittest.main()

