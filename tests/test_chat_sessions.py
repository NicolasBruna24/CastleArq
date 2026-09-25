
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

"""Tests for Block 3.1 chat session lifecycle and Block 3.2 chat turns.

3.2 additions: ``POST /v1/chat/sessions/{id}/turns``. Session doubles below
implement the same public contract the real ``app.chat`` session exposes
(``send()`` appends a completed ``ChatTurn``, ``close()`` is idempotent), so
no runtime is executed and no model is needed.
"""
from __future__ import annotations
import http.client
import json
import threading
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock
from app import api as api_module
from app.api import MAX_CHAT_SESSIONS, MAX_REQUEST_BODY_BYTES, _ChatSessionRegistry, build_server, parse_chat_session_request, parse_chat_turn_request, parse_session_id
from app.chat import ChatProcessError, ChatSessionClosedError, ChatSessionError, ChatTurn
import socket


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


class ConcurrencyTracker:
    """Counts simultaneous ``send()`` calls, to prove real exclusion."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.entered = threading.Event()

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.entered.set()

    def leave(self) -> None:
        with self._lock:
            self.active -= 1


def wait_for_slot_release(entry, timeout: float = 5.0) -> bool:
    """Wait until the handler's ``finally`` released the per-session slot.

    ``_handle_chat_turn`` writes the HTTP response *before* its ``finally``
    releases the turn slot, so a client that already received its reply can
    still observe the lock held for a few microseconds. Tests must observe the
    release instead of racing it.
    """
    deadline = time.monotonic() + timeout
    while entry.turn_lock.locked() and time.monotonic() < deadline:
        time.sleep(0.001)
    return not entry.turn_lock.locked()


class TurnSession:
    """Session double honouring the real ``LlamaCppChatSession`` contract.

    Mirrors the parts of ``app.chat`` the HTTP layer depends on:

    - ``send()`` refuses a ``CLOSED``/``FAILED`` session with
      ``ChatSessionClosedError`` *before* generating anything, which is what
      makes a dead session answer 409 instead of re-running the runtime;
    - a generation that fails with a ``ChatSessionError`` (dead process,
      timeout) leaves the session ``FAILED``, exactly like ``app.chat``;
    - a completed ``ChatTurn`` is appended only after a successful generation
      and the session goes back to ``READY``;
    - ``close()`` is idempotent, switches the session to ``CLOSED`` and opens
      ``gate``, so a turn in flight observes the shutdown the way the real
      session does when its runtime process disappears mid-turn.

    ``gate`` holds a generation in flight; ``prompts`` records every ``send()``
    call, ``generations`` counts only the calls that really started generating
    and ``turns`` holds the completed ones.
    """

    def __init__(self, state_value="ready", responder=None, gate=None,
                 tracker=None):
        self.state = SimpleNamespace(value=state_value)
        self.turns = []
        self.prompts = []
        self.generations = 0
        self.close_count = 0
        self.close_error = None
        self.closed = False
        self._responder = responder
        self._gate = gate
        self._tracker = tracker

    def send(self, prompt):
        self.prompts.append(prompt)
        if self.state.value in ("closed", "failed"):
            # Same pre-check as LlamaCppChatSession.send: the state machine
            # decides, no generation is started on a dead session.
            raise ChatSessionClosedError("session is closed")
        self.state.value = "generating"
        self.generations += 1
        if self._tracker is not None:
            self._tracker.enter()
        try:
            if self._gate is not None and not self._gate.wait(timeout=10):
                self.state.value = "failed"
                raise ChatSessionError("simulated turn timeout")
            if self.closed:
                # close() shut the runtime down mid-turn; the real session
                # detects the dead process and fails the turn the same way.
                if self.state.value == "generating":
                    self.state.value = "failed"
                raise ChatProcessError(
                    "runtime process ended before turn completed")
            outcome = (
                self._responder(prompt) if self._responder is not None
                else ChatTurn(user=prompt, assistant="echo: " + prompt)
            )
            if isinstance(outcome, Exception):
                if isinstance(outcome, ChatSessionError) and not isinstance(
                        outcome, ChatSessionClosedError):
                    # app.chat leaves the session FAILED on process errors and
                    # timeouts (but not on the pre-generation closed error).
                    self.state.value = "failed"
                raise outcome
            self.turns.append(outcome)
            self.state.value = "ready"
            return outcome
        finally:
            if self._tracker is not None:
                self._tracker.leave()

    def close(self):
        self.close_count += 1
        self.closed = True
        self.state.value = "closed"
        if self._gate is not None:
            self._gate.set()
        if self.close_error is not None:
            raise self.close_error


def _admitting_evaluation(model_id, **kwargs):
    """A minimal evaluation result that ADMITS, for the chat lifecycle tests.

    B9.52 made ``POST /v1/chat/sessions`` an execution surface: it now crosses
    the same admission gate as ``/v1/run``. These tests use invented model ids
    ("m", "my-model") and stub only the launcher, so without this the gate
    would correctly refuse them as unknown models and every lifecycle test
    would fail on a 403/404 it never meant to exercise.

    The fixture is deliberately explicit and opt-out: it fakes the *policy
    input* (an evaluated, compatible verdict), never the gate itself, so the
    chat tests keep exercising the registry, the turn lock and the launch
    lifecycle. Tests about the gate itself live in
    ``tests/test_api_serve_contract.py``.
    """
    return SimpleNamespace(
        model_id=model_id,
        artifact=None,
        runtime="fake",
        capability=None,
        evaluation=SimpleNamespace(result=SimpleNamespace(status="compatible")),
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


def _denying_evaluation(model_id, **kwargs):
    """An evaluation that completes and is REFUSED (never raises)."""
    return SimpleNamespace(
        model_id=model_id,
        artifact=None,
        runtime="fake",
        capability=None,
        evaluation=SimpleNamespace(result=SimpleNamespace(status="incompatible")),
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


class AdmissionDefault(unittest.TestCase):
    """Base class: admit by default so lifecycle tests test their own subject.

    Every test in this module that opens a session either passes
    ``admit=False`` (to exercise a refusal) or patches the evaluation itself.
    """

    admit = True

    def setUp(self):
        if self.admit:
            patcher = mock.patch(
                "app.api.evaluate_model_compatibility",
                side_effect=_admitting_evaluation,
            )
            patcher.start()
            self.addCleanup(patcher.stop)


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


class PostTests(AdmissionDefault):
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


class GetDeleteTests(AdmissionDefault):
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


class ShutdownTests(AdmissionDefault):
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


class RegressionTests(AdmissionDefault):
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

    def test_only_the_turns_subpath_is_routed(self):
        """Block 3.2 wires ``.../turns``; other POST shapes keep Block 1 405."""
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session", return_value=_opened("m")):
            _, _, raw = h.post_json("/v1/chat/sessions", {"model_id": "m"})
            sid = json.loads(raw.decode())["session_id"]
            bare, _, _ = h.post_json(f"/v1/chat/sessions/{sid}", {"prompt": "hi"})
            extra, _, _ = h.post_json(
                f"/v1/chat/sessions/{sid}/turns/extra", {"prompt": "hi"})
            get_turns, _, _ = h.request("GET", f"/v1/chat/sessions/{sid}/turns")
        self.assertEqual((bare, extra), (405, 405))
        self.assertEqual(get_turns, 404)


class ChatTurnParseTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(
            parse_chat_turn_request({"prompt": "Hello"}).prompt, "Hello")
        self.assertEqual(parse_chat_turn_request({"prompt": " x "}).prompt, " x ")

    def test_rejects_everything_else(self):
        for bad in (None, [], "x", 5, 5.0, True):
            with self.assertRaises(ValueError):
                parse_chat_turn_request(bad)
        for bad in (
            {},                             # prompt missing
            {"prompt": None},               # wrong type
            {"prompt": 123},                # never coerced to "123"
            {"prompt": ["a"]},
            {"prompt": {"a": 1}},
            {"prompt": True},
            {"prompt": ""},                 # empty
            {"prompt": "   "},              # whitespace only
            {"prompt": "hi", "extra": 1},   # unknown field
            {"prompt": "hi", "argv": ["x"]},
            {"prompt": "hi", "model_id": "m"},
        ):
            with self.assertRaises(ValueError):
                parse_chat_turn_request(bad)


class ChatTurnRegistryTests(unittest.TestCase):
    """Direct coverage of the per-session turn slot (Block 3.2)."""

    def test_begin_turn_is_per_session_and_non_blocking(self):
        registry = _ChatSessionRegistry()
        first, second = TurnSession(), TurnSession()
        registry.register("a", api_module._ChatSessionEntry(first, "m"))
        registry.register("b", api_module._ChatSessionEntry(second, "m"))
        entry_a = registry.begin_turn("a")
        self.assertIs(entry_a.session, first)
        self.assertTrue(entry_a.turn_lock.locked())  # slot held while generating
        with self.assertRaises(api_module._ChatSessionBusy):
            registry.begin_turn("a")
        # A different session is never blocked by the first one.
        entry_b = registry.begin_turn("b")
        self.assertIs(entry_b.session, second)
        with self.assertRaises(api_module._ChatSessionNotFound):
            registry.begin_turn(str(uuid.uuid4()))
        registry.end_turn(entry_a)
        registry.end_turn(entry_a)  # double release never raises
        self.assertFalse(entry_a.turn_lock.locked())
        self.assertIs(registry.begin_turn("a").session, first)
        registry.end_turn(entry_b)

    def test_claim_for_removal_respects_busy_and_missing(self):
        registry = _ChatSessionRegistry()
        registry.register("a", api_module._ChatSessionEntry(TurnSession(), "m"))
        entry = registry.begin_turn("a")
        with self.assertRaises(api_module._ChatSessionBusy):
            registry.claim_for_removal("a")
        self.assertEqual(len(registry), 1)  # still registered while busy
        registry.end_turn(entry)
        removed = registry.claim_for_removal("a")
        self.assertIsNotNone(removed.session)
        self.assertTrue(removed.turn_lock.locked())  # held while closing
        self.assertEqual(len(registry), 0)
        with self.assertRaises(api_module._ChatSessionNotFound):
            registry.claim_for_removal("a")
        registry.end_turn(removed)
        self.assertFalse(removed.turn_lock.locked())


class ChatTurnHttpTests(AdmissionDefault):
    """``POST /v1/chat/sessions/{id}/turns`` contract (single-threaded)."""

    def _create(self, harness, session):
        with mock.patch(
                "app.api.open_chat_session",
                return_value=ChatSessionOpened(session=session, model_id="m")):
            status, _, raw = harness.post_json(
                "/v1/chat/sessions", {"model_id": "m"})
        self.assertEqual(status, 201)
        return json.loads(raw.decode())["session_id"]

    def test_happy_path_200_and_contract(self):
        session = TurnSession()
        with ServerHarness() as h:
            sid = self._create(h, session)
            status, headers, raw = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "Hello"})
            payload = json.loads(raw.decode())
            get_status, _, get_raw = h.request("GET", f"/v1/chat/sessions/{sid}")
        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(
            sorted(payload), ["response", "session_id", "turn_count"])
        self.assertEqual(payload["session_id"], sid)
        self.assertEqual(payload["response"], "echo: Hello")
        self.assertEqual(payload["turn_count"], 1)
        self.assertEqual(session.prompts, ["Hello"])
        self.assertEqual(get_status, 200)
        metadata = json.loads(get_raw.decode())
        self.assertEqual(metadata["turn_count"], 1)
        self.assertEqual(metadata["status"], "ready")

    def test_second_turn_increments_count(self):
        session = TurnSession()
        with ServerHarness() as h:
            sid = self._create(h, session)
            first, _, raw1 = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "one"})
            second, _, raw2 = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "two"})
        self.assertEqual((first, second), (200, 200))
        self.assertEqual(json.loads(raw1.decode())["turn_count"], 1)
        self.assertEqual(json.loads(raw2.decode())["turn_count"], 2)
        self.assertEqual(len(session.turns), 2)
        self.assertEqual([t.user for t in session.turns], ["one", "two"])

    def test_generation_failure_returns_503_without_counting(self):
        session = TurnSession(
            responder=lambda p: ChatProcessError("/tmp/secret boom"))
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h:
            sid = self._create(h, session)
            status, _, raw = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "Hello"})
            get_status, _, get_raw = h.request("GET", f"/v1/chat/sessions/{sid}")
            held = registry.get(sid).turn_lock.locked()
        self.assertEqual(status, 503)
        self.assertNotIn("/tmp/secret", raw.decode())
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_raw.decode())["turn_count"], 0)
        self.assertEqual(len(session.turns), 0)
        self.assertFalse(held, "the turn slot must be released on failure")

    def test_lock_released_after_generation_error(self):
        """A runtime error during a turn leaves FAILED and frees the slot.

        Mirrors the real ``LlamaCppChatSession`` sequence end to end:

        1. the first turn starts generating;
        2. the runtime fails during that generation (``ChatProcessError``);
        3. HTTP is the runtime-failure mapping (503) and leaks no detail;
        4. the turn slot is released, so the next request is *not* rejected as
           busy and reaches ``send()`` again;
        5. the failed turn is not counted;
        6. the session is left ``FAILED`` (visible through ``GET``), which is
           what ``app.chat`` does on a process error;
        7. the second turn never re-runs generation on the failed session and
           answers 409, the existing contract for a session that can no longer
           accept turns;
        8. no lock survives any of it.
        """
        session = TurnSession(
            responder=lambda p: ChatProcessError("process died"))
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h:
            sid = self._create(h, session)
            path = f"/v1/chat/sessions/{sid}/turns"
            entry = registry.get(sid)

            first, _, first_raw = h.post_json(path, {"prompt": "one"})
            self.assertEqual(first, 503)
            self.assertNotIn("process died", first_raw.decode())
            self.assertEqual(session.generations, 1)
            self.assertEqual(session.turns, [])            # not counted
            self.assertEqual(session.state.value, "failed")
            self.assertTrue(
                wait_for_slot_release(entry),
                "the failed turn must release the slot")

            meta_status, _, meta_raw = h.request(
                "GET", f"/v1/chat/sessions/{sid}")
            self.assertEqual(meta_status, 200)
            meta = json.loads(meta_raw.decode())
            self.assertEqual(meta["status"], "failed")
            self.assertEqual(meta["turn_count"], 0)

            second, _, second_raw = h.post_json(path, {"prompt": "two"})
            self.assertEqual(second, 409)
            body = json.loads(second_raw.decode())
            # Block 3.4: a FAILED session answers "failed" (coherent with the
            # GET status), not the generic "closed"; the slot was free, the
            # session state machine rejected the turn (not the API lock).
            self.assertIn("failed", body["error"])
            self.assertNotIn("already processing", second_raw.decode())
            self.assertEqual(session.generations, 1)       # never re-ran
            self.assertEqual(session.prompts, ["one", "two"])
            self.assertTrue(
                wait_for_slot_release(entry),
                "no lock may survive the rejected turn")
        self.assertEqual(session.turns, [])

    def test_closed_session_returns_409(self):
        session = TurnSession(
            responder=lambda p: ChatSessionClosedError("session is closed"))
        with ServerHarness() as h:
            sid = self._create(h, session)
            status, _, raw = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "Hello"})
        self.assertEqual(status, 409)
        self.assertIn("closed", json.loads(raw.decode())["error"])

    def test_unexpected_error_returns_500_without_details(self):
        session = TurnSession(responder=lambda p: RuntimeError("boom secret"))
        with ServerHarness() as h:
            sid = self._create(h, session)
            status, _, raw = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "Hello"})
        self.assertEqual(status, 500)
        self.assertNotIn("boom", raw.decode())

    def test_unknown_session_returns_404(self):
        with ServerHarness() as h:
            status, _, _ = h.post_json(
                f"/v1/chat/sessions/{uuid.uuid4()}/turns", {"prompt": "Hello"})
        self.assertEqual(status, 404)

    def test_malformed_session_id_returns_400(self):
        with ServerHarness() as h:
            status, _, _ = h.post_json(
                "/v1/chat/sessions/not-a-uuid/turns", {"prompt": "Hello"})
        self.assertEqual(status, 400)


    def test_invalid_requests_return_400_and_consume_nothing(self):
        session = TurnSession()
        with ServerHarness() as h:
            sid = self._create(h, session)
            path = f"/v1/chat/sessions/{sid}/turns"
            cases = [
                (None, b"{bad"),            # malformed JSON
                (None, b"[]"),              # body is not an object
                (None, b'"text"'),
                (None, b"5"),
                ({"prompt": "hi"}, b"   "),  # blank body
                ({"prompt": None}, None),   # wrong type
                ({"prompt": 123}, None),    # never coerced to "123"
                ({"prompt": []}, None),
                ({"prompt": {}}, None),
                ({"prompt": "  "}, None),   # empty after strip
                ({}, None),                 # prompt missing
                ({"prompt": "hi", "argv": ["x"]}, None),
                ({"prompt": "hi", "model_id": "m"}, None),
            ]
            for payload, raw_body in cases:
                status, _, _ = h.post_json(path, payload, raw_body=raw_body)
                self.assertEqual(status, 400, (payload, raw_body))
            wrong_type, _, _ = h.post_json(
                path, {"prompt": "hi"}, content_type="text/plain")
            self.assertEqual(wrong_type, 400)
            # Nothing was consumed: the session still accepts a valid turn.
            ok, _, raw = h.post_json(path, {"prompt": "Hello"})
        self.assertEqual(ok, 200)
        self.assertEqual(json.loads(raw.decode())["turn_count"], 1)
        self.assertEqual(session.prompts, ["Hello"])

    def test_oversized_body_returns_413(self):
        session = TurnSession()
        big = b'{"prompt": "' + b"x" * (MAX_REQUEST_BODY_BYTES + 1) + b'"}'
        with ServerHarness() as h:
            sid = self._create(h, session)
            status, _, _ = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", None, raw_body=big)
        self.assertEqual(status, 413)
        self.assertEqual(session.prompts, [])

    def test_empty_body_gets_deterministic_400_on_shared_endpoints(self):
        """Block 3.4: ``Content-Length: 0`` now answers 400 on every POST
        that shares ``_read_json_body`` (previously the connection was closed
        with no response, pre-existing debt of the shared helper)."""
        session = TurnSession()
        with ServerHarness() as h:
            sid = self._create(h, session)
            outcomes = []
            for path in ("/v1/run", "/v1/chat/sessions",
                         f"/v1/chat/sessions/{sid}/turns"):
                status, _, raw = h.post_json(path, None)
                outcomes.append((status, json.loads(raw.decode())["error"]))
        self.assertEqual(
            outcomes,
            [(400, "request body is required"),
             (400, "request body is required"),
             (400, "request body is required")])
        self.assertEqual(session.prompts, [])


class ChatTurnConcurrencyTests(AdmissionDefault):
    """Real multithreaded coverage of the per-session turn policy."""

    def _create(self, harness, session):
        return ChatTurnHttpTests._create(self, harness, session)

    def test_concurrent_turns_on_same_session_are_exclusive(self):
        gate = threading.Event()
        tracker = ConcurrencyTracker()
        session = TurnSession(gate=gate, tracker=tracker)
        barrier = threading.Barrier(2)
        results: dict[str, tuple] = {}
        with ServerHarness() as h:
            sid = self._create(h, session)
            path = f"/v1/chat/sessions/{sid}/turns"

            def turn(name, prompt):
                barrier.wait(timeout=10)
                results[name] = h.post_json(path, {"prompt": prompt})

            workers = [
                threading.Thread(target=turn, args=(name, prompt), daemon=True)
                for name, prompt in (("a", "one"), ("b", "two"))
            ]
            for worker in workers:
                worker.start()
            # One request owns the session while it generates; the other must
            # be rejected immediately (it cannot be 200 while the slot is
            # held, and the slot stays held until the gate opens).
            self.assertTrue(tracker.entered.wait(timeout=10))
            deadline = time.monotonic() + 10
            while not results and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(results), 1, results)
            rejected = next(iter(results.values()))
            self.assertEqual(rejected[0], 409)
            self.assertIn(
                "already processing", json.loads(rejected[2].decode())["error"])
            gate.set()
            for worker in workers:
                worker.join(timeout=10)
            self.assertFalse(
                any(w.is_alive() for w in workers), "no request may hang")
            self.assertEqual(sorted(r[0] for r in results.values()), [200, 409])
            self.assertEqual(tracker.max_active, 1)  # never two generations
            self.assertEqual(len(session.turns), 1)
            winner = next(r for r in results.values() if r[0] == 200)
            self.assertEqual(json.loads(winner[2].decode())["turn_count"], 1)
            # The slot is free again once the turn ended.
            after, _, after_raw = h.post_json(path, {"prompt": "three"})
            self.assertEqual(after, 200)
            self.assertEqual(json.loads(after_raw.decode())["turn_count"], 2)
        self.assertEqual(len(session.turns), 2)

    def test_busy_session_is_rejected_immediately(self):
        gate = threading.Event()
        tracker = ConcurrencyTracker()
        session = TurnSession(gate=gate, tracker=tracker)
        outcome: dict[str, tuple] = {}
        with ServerHarness() as h:
            sid = self._create(h, session)
            path = f"/v1/chat/sessions/{sid}/turns"
            worker = threading.Thread(
                target=lambda: outcome.__setitem__(
                    "first", h.post_json(path, {"prompt": "one"})),
                daemon=True)
            worker.start()
            self.assertTrue(tracker.entered.wait(timeout=10))
            started = time.monotonic()
            status, _, raw = h.post_json(path, {"prompt": "two"})
            elapsed = time.monotonic() - started
            self.assertEqual(status, 409)
            self.assertIn(
                "already processing", json.loads(raw.decode())["error"])
            # Answered while the first turn was still generating.
            self.assertLess(elapsed, 5.0)
            self.assertEqual(len(session.turns), 0)  # nothing counted
            gate.set()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(outcome["first"][0], 200)
            self.assertEqual(
                json.loads(outcome["first"][2].decode())["turn_count"], 1)
        self.assertEqual(len(session.turns), 1)

    def test_turns_on_different_sessions_run_concurrently(self):
        gate_a, gate_b = threading.Event(), threading.Event()
        tracker_a, tracker_b = ConcurrencyTracker(), ConcurrencyTracker()
        session_a = TurnSession(gate=gate_a, tracker=tracker_a)
        session_b = TurnSession(gate=gate_b, tracker=tracker_b)
        barrier = threading.Barrier(2)
        results: dict[str, tuple] = {}
        with ServerHarness() as h:
            sid_a = self._create(h, session_a)
            sid_b = self._create(h, session_b)

            def turn(name, sid):
                barrier.wait(timeout=10)
                results[name] = h.post_json(
                    f"/v1/chat/sessions/{sid}/turns", {"prompt": name})

            workers = [
                threading.Thread(target=turn, args=(name, sid), daemon=True)
                for name, sid in (("a", sid_a), ("b", sid_b))
            ]
            for worker in workers:
                worker.start()
            # Both turns are inside send() at the same time: no global lock.
            self.assertTrue(tracker_a.entered.wait(timeout=10))
            self.assertTrue(tracker_b.entered.wait(timeout=10))
            self.assertEqual(
                (tracker_a.max_active, tracker_b.max_active), (1, 1))
            gate_a.set()
            gate_b.set()
            for worker in workers:
                worker.join(timeout=10)
            self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(sorted(r[0] for r in results.values()), [200, 200])
        self.assertEqual(len(session_a.turns), 1)
        self.assertEqual(len(session_b.turns), 1)
        for result in results.values():
            self.assertEqual(json.loads(result[2].decode())["turn_count"], 1)


class ChatTurnLifecycleTests(AdmissionDefault):
    """DELETE×DELETE, DELETE/turn races and shutdown with the new turn slot."""

    def _create(self, harness, session):
        return ChatTurnHttpTests._create(self, harness, session)

    def test_delete_during_turn_is_busy_and_state_stays_consistent(self):
        gate = threading.Event()
        tracker = ConcurrencyTracker()
        session = TurnSession(gate=gate, tracker=tracker)
        registry = _ChatSessionRegistry()
        outcome: dict[str, tuple] = {}
        with ServerHarness(chat_registry=registry) as h:
            sid = self._create(h, session)
            worker = threading.Thread(
                target=lambda: outcome.__setitem__(
                    "turn", h.post_json(
                        f"/v1/chat/sessions/{sid}/turns", {"prompt": "one"})),
                daemon=True)
            worker.start()
            self.assertTrue(tracker.entered.wait(timeout=10))
            status, _, raw = h.request("DELETE", f"/v1/chat/sessions/{sid}")
            self.assertEqual(status, 409)
            self.assertIn(
                "already processing", json.loads(raw.decode())["error"])
            self.assertEqual(session.close_count, 0)  # never closed mid-turn
            self.assertIsNotNone(registry.get(sid))
            gate.set()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), "DELETE must not deadlock")
            self.assertEqual(outcome["turn"][0], 200)
            self.assertEqual(
                json.loads(outcome["turn"][2].decode())["turn_count"], 1)
            # Idle again: the delete now succeeds exactly once.
            deleted, _, _ = h.request("DELETE", f"/v1/chat/sessions/{sid}")
            self.assertEqual(deleted, 204)
            self.assertEqual(session.close_count, 1)
            gone, _, _ = h.request("GET", f"/v1/chat/sessions/{sid}")
            self.assertEqual(gone, 404)
            late, _, _ = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "after"})
            self.assertEqual(late, 404)
        self.assertEqual(len(registry), 0)

    def test_concurrent_deletes_on_same_session(self):
        """DELETE × DELETE: exactly one winner, one close, no deadlock.

        Both requests race on ``claim_for_removal``. The result set is
        deterministic even though the thread order is not: the winner claims
        the slot *and* unregisters the entry inside the same registry-lock
        section, so the loser always finds the session already gone (404) and
        never closes it -- the loser cannot be rejected as busy, because only
        an in-flight turn keeps an entry registered while holding the slot.
        ``close()`` therefore runs exactly once and no double close is
        accepted.
        """
        session = TurnSession()
        registry = _ChatSessionRegistry()
        barrier = threading.Barrier(2)
        results: dict[str, tuple] = {}
        with ServerHarness(chat_registry=registry) as h:
            sid = self._create(h, session)

            def delete(name):
                barrier.wait(timeout=10)
                results[name] = h.request(
                    "DELETE", f"/v1/chat/sessions/{sid}")

            workers = [
                threading.Thread(target=delete, args=(name,), daemon=True)
                for name in ("a", "b")
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)
            self.assertFalse(
                any(w.is_alive() for w in workers), "DELETE must not deadlock")
            gone, _, _ = h.request("GET", f"/v1/chat/sessions/{sid}")
        self.assertEqual(sorted(r[0] for r in results.values()), [204, 404])
        self.assertEqual(session.close_count, 1)   # closed once, never twice
        self.assertEqual(len(registry), 0)
        self.assertEqual(gone, 404)
        loser = next(r for r in results.values() if r[0] == 404)
        self.assertIn("not found", loser[2].decode())

    def test_shutdown_closes_sessions_with_an_inflight_turn(self):
        """Shutdown during a turn: one close, no deadlock, slot released.

        ``TurnSession.close()`` shuts the runtime down mid-turn, so the
        in-flight ``send()`` fails with the ``ChatProcessError`` the real
        ``LlamaCppChatSession`` raises when it detects its dead process. The
        handler maps that to 503 (runtime failure), never to the 409 used for
        a busy/closed session -- the double no longer answers 409 by accident.
        In the real race the runtime could also finish the turn just before
        dying, which would legitimately produce 200 with a counted turn; that
        branch is not asserted here.
        """
        gate = threading.Event()
        tracker = ConcurrencyTracker()
        session = TurnSession(gate=gate, tracker=tracker)
        registry = _ChatSessionRegistry()
        outcome: dict[str, tuple] = {}
        harness = ServerHarness(chat_registry=registry)
        try:
            sid = self._create(harness, session)
            entry = registry.get(sid)
            worker = threading.Thread(
                target=lambda: outcome.__setitem__(
                    "turn", harness.post_json(
                        f"/v1/chat/sessions/{sid}/turns", {"prompt": "one"})),
                daemon=True)
            worker.start()
            self.assertTrue(tracker.entered.wait(timeout=10))
            self.assertEqual(session.state.value, "generating")  # turn in flight
            self.assertEqual(session.generations, 1)
            # Shutdown must return promptly even with a turn in flight.
            harness.server.shutdown()
            harness.server.server_close()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), "shutdown must not deadlock")
            self.assertEqual(session.close_count, 1)   # closed exactly once
            self.assertEqual(len(registry), 0)         # registry drained
            self.assertEqual(outcome["turn"][0], 503)  # runtime failure, not 409
            self.assertTrue(
                wait_for_slot_release(entry),
                "the handler must release the slot")
            self.assertEqual(session.generations, 1)
            self.assertEqual(session.turns, [])        # turn_count untouched
            self.assertIn(session.state.value, ("closed", "failed"))
        finally:
            harness.stop()


class LifecycleHardeningTests(AdmissionDefault):
    """Block 3.3: registry/shutdown races never orphan a session.

    Races are exercised with real threads plus barriers/gates; the core
    register-vs-shutdown race repeats 10 rounds inside the test so that every
    interleaving (register wins / drain wins) is exercised many times.
    """

    def _post_create(self, harness):
        return harness.post_json("/v1/chat/sessions", {"model_id": "m"})

    @staticmethod
    def _spawn(n, target_factory):
        threads = [threading.Thread(
            target=target_factory(i), daemon=True) for i in range(n)]
        for thread in threads:
            thread.start()
        return threads

    @staticmethod
    def _join_all(threads, timeout: float = 10.0) -> None:
        for thread in threads:
            thread.join(timeout=timeout)
            if thread.is_alive():  # pragma: no cover - would hang the suite
                raise AssertionError("thread did not finish (deadlock?)")

    def test_close_all_empty_registry_is_noop(self):
        registry = _ChatSessionRegistry()
        registry.close_all()
        self.assertEqual(len(registry), 0)
        self.assertTrue(registry.is_closing())

    def test_shutdown_with_four_idle_sessions(self):
        registry = _ChatSessionRegistry()
        sessions = [FakeSession() for _ in range(MAX_CHAT_SESSIONS)]
        server = build_server(HOST, 0, chat_registry=registry)
        for session in sessions:
            registry.register(
                str(uuid.uuid4()),
                api_module._ChatSessionEntry(session, "m"))
        server.server_close()
        self.assertEqual(len(registry), 0)
        self.assertTrue(registry.is_closing())
        self.assertEqual([s.close_count for s in sessions], [1] * 4)

    def test_create_after_shutdown_is_503_without_launch(self):
        """Invariant 1: after shutdown, create never launches a runtime."""
        launches = []

        def factory(*args, **kwargs):
            launches.append(1)
            return _opened("m")

        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session", side_effect=factory):
            registry.close_all()
            status, _, raw = self._post_create(h)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw.decode())["error"],
                         "server is shutting down")
        self.assertEqual(launches, [])

    def test_delete_and_turn_after_shutdown_are_404(self):
        session = FakeSession()
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                return_value=ChatSessionOpened(session=session, model_id="m")):
            _, _, raw = self._post_create(h)
            sid = json.loads(raw.decode())["session_id"]
            registry.close_all()
            deleted, _, _ = h.request("DELETE", f"/v1/chat/sessions/{sid}")
            turn_status, _, _ = h.post_json(
                f"/v1/chat/sessions/{sid}/turns", {"prompt": "hi"})
        self.assertEqual(deleted, 404)
        self.assertEqual(turn_status, 404)
        self.assertEqual(session.close_count, 1)



    def test_register_race_vs_close_all_never_orphans(self):
        """Unit race, 10 rounds: every interleaving closes each session once.

        Workers register freshly launched sessions while the main thread
        drains. If the register wins, ``close_all`` closes the session; if the
        drain wins, ``register`` raises ``_ChatRegistryClosing`` and the
        worker mimics the create handler (close immediately). Either way the
        final state must be: empty registry, every session closed exactly once.
        """
        for _ in range(10):
            registry = _ChatSessionRegistry(max_sessions=64)
            sessions = [FakeSession() for _ in range(8)]
            start = threading.Barrier(len(sessions) + 1)

            def worker(session):
                start.wait(timeout=10)
                try:
                    registry.register(
                        str(uuid.uuid4()),
                        api_module._ChatSessionEntry(session, "m"))
                except api_module._ChatRegistryClosing:
                    session.close()

            threads = self._spawn(
                len(sessions), lambda i: (lambda s=sessions[i]: worker(s)))
            start.wait(timeout=10)
            registry.close_all()
            self._join_all(threads)
            self.assertEqual(len(registry), 0)
            self.assertEqual([s.close_count for s in sessions], [1] * 8)

    def test_create_concurrent_with_shutdown_never_orphans_http(self):
        """HTTP race, drain wins: the in-flight create answers 503 and self-closes.

        The patched factory blocks the create handler *between* the launch and
        the registration, so ``close_all`` is guaranteed to drain the (still
        empty) registry first. This is the exact race that leaked orphaned
        runtimes before Block 3.3.

        B9.52 note: this is ONE create in flight, not three concurrent ones.
        ``POST /v1/chat/sessions`` now takes the same ``run_lock`` as
        ``/v1/run`` (B9.51 section 5.4 -- opening a session starts a model), so
        concurrent creates are answered 409 by design and can no longer all be
        inside the launcher at once. The orphan guarantee is unchanged and is
        what is asserted here: the in-flight create is refused registration
        (503) and closes its own runtime exactly once.
        """
        registry = _ChatSessionRegistry()
        created = []
        in_flight = threading.Event()
        release = threading.Event()

        def factory(*args, **kwargs):
            session = FakeSession()
            created.append(session)
            in_flight.set()
            release.wait(timeout=10)
            return ChatSessionOpened(session=session, model_id="m")

        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session", side_effect=factory):
            outcome = {}

            def create():
                outcome["status"] = self._post_create(h)[0]

            worker = threading.Thread(target=create, daemon=True)
            worker.start()
            self.assertTrue(in_flight.wait(timeout=10))
            registry.close_all()  # drain wins: registration is rejected
            release.set()
            worker.join(timeout=10)
        self.assertEqual(outcome["status"], 503)
        self.assertEqual(len(registry), 0)
        # The launched runtime was closed exactly once and never registered.
        self.assertEqual([s.close_count for s in created], [1])

    def test_create_after_shutdown_is_refused_without_launching(self):
        """Creates that arrive after the drain never start a runtime.

        Companion to the test above: once ``close_all`` has run, the shutdown
        gate answers 503 before any launch is attempted, so no runtime can be
        orphaned by a late create. Independent of ``run_lock``, which is
        already released by then.
        """
        registry = _ChatSessionRegistry()
        launches = []
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=lambda *a, **k: launches.append(1)):
            registry.close_all()
            first = self._post_create(h)
            second = self._post_create(h)
        for status, _, raw in (first, second):
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(raw)["error"], "server is shutting down")
        self.assertEqual(launches, [])
        self.assertEqual(len(registry), 0)

    def test_concurrent_session_creates_are_serialised_by_the_run_lock(self):
        """B9.51 section 5.4: session open shares the single execution lock.

        A chat session launch starts a model, so it may not run concurrently
        with another execution (or another launch) on the same GPU. Concurrent
        creates therefore cannot all be in flight at once: exactly one reaches
        the launcher and the others are told 409 rather than queued.
        """
        registry = _ChatSessionRegistry()
        started = threading.Event()
        release = threading.Event()
        launches = []
        lock = threading.Lock()

        def factory(*args, **kwargs):
            with lock:
                launches.append(1)
            started.set()
            release.wait(timeout=10)
            return ChatSessionOpened(session=FakeSession(), model_id="m")

        outcomes = {}
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session", side_effect=factory):
            def create(i):
                outcomes[i] = self._post_create(h)

            threads = self._spawn(3, lambda i: (lambda i=i: create(i)))
            self.assertTrue(started.wait(timeout=10))
            # While one launch is in flight the lock is held: every other
            # create is refused immediately, with no queue behind it.
            for _ in range(20):
                if 409 in [s for s, _, _ in outcomes.values()]:
                    break
                time.sleep(0.01)
            release.set()
            self._join_all(threads)
        codes = sorted(status for status, _, _ in outcomes.values())
        self.assertEqual(codes.count(409), 2)
        self.assertEqual(codes.count(201), 1)
        # Proof of exclusion: only one launcher call was ever in flight.
        self.assertEqual(len(launches), 1)

    def test_create_registered_before_shutdown_is_closed_by_close_all(self):
        """HTTP race, register wins: close_all closes the registered session."""
        session = FakeSession()
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                return_value=ChatSessionOpened(session=session, model_id="m")):
            status, _, raw = self._post_create(h)
            self.assertEqual(status, 201)
            sid = json.loads(raw.decode())["session_id"]
            registry.close_all()
            after, _, _ = h.request("GET", f"/v1/chat/sessions/{sid}")
        self.assertEqual(after, 404)
        self.assertEqual(session.close_count, 1)
        self.assertEqual(len(registry), 0)

    def test_creation_concurrent_around_limit(self):
        """4 concurrent creates against max=2: exactly two 201, two 409."""
        registry = _ChatSessionRegistry(max_sessions=2)
        opened = [_opened("m") for _ in range(4)]
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session", side_effect=list(opened)):
            barrier = threading.Barrier(4)
            outcomes = {}

            def worker(i):
                barrier.wait(timeout=10)
                outcomes[i] = self._post_create(h)

            threads = self._spawn(4, lambda i: (lambda i=i: worker(i)))
            self._join_all(threads)
            codes = sorted(status for status, _, _ in outcomes.values())
            # Assert *inside* the with-block: ServerHarness.__exit__ triggers
            # server_close(), which drains the registry.
            self.assertEqual(codes, [201, 201, 409, 409])
            self.assertEqual(len(registry), 2)
        # The two registered sessions are closed exactly once by the harness
        # shutdown; the two limit-rejected ones were closed at rejection time
        # (or never launched if is_full() answered first). Nothing is left
        # open and nothing is closed twice.
        close_counts = sorted(
            s.close_count for s in (o.session for o in opened))
        self.assertEqual(sum(close_counts), 2)
        self.assertTrue(all(count in (0, 1) for count in close_counts))

    def test_fifth_session_concurrent_is_409(self):
        with ServerHarness() as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=[_opened("m") for _ in range(6)]):
            for _ in range(MAX_CHAT_SESSIONS):
                status, _, _ = self._post_create(h)
                self.assertEqual(status, 201)
            barrier = threading.Barrier(2)
            outcomes = {}

            def worker(i):
                barrier.wait(timeout=10)
                outcomes[i] = self._post_create(h)

            threads = self._spawn(2, lambda i: (lambda i=i: worker(i)))
            self._join_all(threads)
        codes = sorted(status for status, _, _ in outcomes.values())
        self.assertEqual(codes, [409, 409])

    def test_delete_and_post_concurrent(self):
        first = FakeSession()
        registry = _ChatSessionRegistry()
        with ServerHarness(chat_registry=registry) as h, mock.patch(
                "app.api.open_chat_session",
                side_effect=[ChatSessionOpened(session=first, model_id="m"),
                             ChatSessionOpened(
                                 session=FakeSession(), model_id="m")]):
            _, _, raw = self._post_create(h)
            sid = json.loads(raw.decode())["session_id"]
            barrier = threading.Barrier(2)
            outcomes = {}

            def do_delete(i):
                barrier.wait(timeout=10)
                outcomes[i] = h.request("DELETE", f"/v1/chat/sessions/{sid}")

            def do_create(i):
                barrier.wait(timeout=10)
                outcomes[i] = self._post_create(h)

            threads = self._spawn(
                2, lambda i: (lambda i=i: do_delete(i) if i == 0
                              else do_create(i)))
            self._join_all(threads)
            # Assert inside the with-block: ServerHarness.__exit__ drains.
            self.assertEqual(outcomes[0][0], 204)
            self.assertEqual(outcomes[1][0], 201)
            self.assertEqual(first.close_count, 1)
            self.assertEqual(len(registry), 1)


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


class OversizedBodyDrainTests(AdmissionDefault):
    """Post-fix regression tests: the early 413 drains a bounded body so
    clients deterministically receive it (no mid-upload TCP reset race)."""

    def test_max_plus_one_gets_413_stably(self):
        """MAX + 1 bytes is always answered with a real, readable 413."""
        session = TurnSession()
        big = b'{"prompt": "' + b"x" * (MAX_REQUEST_BODY_BYTES + 1) + b'"}'
        with ServerHarness() as h:
            sid = self._create(h, session)
            for _ in range(3):
                status, _, raw = h.post_json(
                    f"/v1/chat/sessions/{sid}/turns", None, raw_body=big)
                self.assertEqual(status, 413)
                self.assertIn(b"request body too large", raw)
        self.assertEqual(session.prompts, [])

    def test_drain_discards_bytes_without_accumulating_memory(self):
        """The drain reads in small chunks, drops them, and returns nothing."""
        reads = []

        class FakeRfile:
            def read(self, size):
                reads.append(size)
                return b"x" * size

        api_module._drain_request_body(
            FakeRfile(), MAX_REQUEST_BODY_BYTES + 1)
        self.assertTrue(reads)
        self.assertTrue(all(size <= 64 * 1024 for size in reads))
        self.assertEqual(sum(reads), MAX_REQUEST_BODY_BYTES + 1)
        self.assertIsNone(
            api_module._drain_request_body(FakeRfile(), 0))
        # No additional reads happened for length 0.
        self.assertEqual(reads[-1], 1)

    def test_drain_never_reads_beyond_the_cap(self):
        """Content-Length beyond DRAIN_CAP is not drained at all."""
        reads = []

        class FakeRfile:
            def read(self, size):
                reads.append(size)
                return b"x" * size

        api_module._drain_request_body(FakeRfile(), api_module.DRAIN_CAP_BYTES + 1)
        self.assertEqual(reads, [])

    def test_drain_reads_in_small_chunks_up_to_the_cap(self):
        """Chunked reads, capped, discarding every chunk immediately."""
        reads = []

        class FakeRfile:
            def read(self, size):
                reads.append(size)
                return b"x" * size

        api_module._drain_request_body(FakeRfile(), api_module.DRAIN_CAP_BYTES)
        self.assertTrue(reads)
        self.assertTrue(all(size <= 64 * 1024 for size in reads))
        self.assertEqual(sum(reads), api_module.DRAIN_CAP_BYTES)

    def test_drain_tolerates_client_disconnect(self):
        """An OSError while draining does not crash the handler path."""

        class BrokenRfile:
            def read(self, size):
                raise ConnectionResetError("client went away")

        api_module._drain_request_body(BrokenRfile(), 4096)

    def test_content_length_beyond_cap_closes_without_unbounded_drain(self):
        """A declared body far beyond DRAIN_CAP gets an immediate 413 even
        though the client never sends the bytes (no unbounded wait)."""
        session = TurnSession()
        with ServerHarness() as h:
            sid = self._create(h, session)
            with socket.create_connection((HOST, h.port), timeout=10) as sock:
                sock.settimeout(10)
                request = (
                    b"POST /v1/chat/sessions/" + sid.encode()
                    + b"/turns HTTP/1.1\r\n"
                    b"Host: " + HOST.encode() + b"\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: "
                    + str(api_module.DRAIN_CAP_BYTES * 100).encode()
                    + b"\r\n\r\n" + b"{}"
                )
                sock.sendall(request)
                response = b""
                while b"request body too large" not in response:
                    data = sock.recv(4096)
                    if not data:
                        break
                    response += data
        self.assertIn(b" 413 ", response)
        self.assertIn(b"request body too large", response)
        self.assertEqual(session.prompts, [])

    def _create(self, h, session):
        with mock.patch("app.api.open_chat_session",
                        return_value=_opened("my-model")):
            status, _, raw = h.post_json(
                "/v1/chat/sessions", {"model_id": "my-model"})
        self.assertEqual(status, 201)
        return json.loads(raw.decode())["session_id"]


if __name__ == "__main__":
    unittest.main()

