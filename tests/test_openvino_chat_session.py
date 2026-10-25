import threading
import unittest
from unittest.mock import Mock

from castlearq.chat import ChatSessionClosedError, ChatSessionConfigError, OpenVINOChatSession


class FakeService:
    def __init__(self):
        self.calls = []
        self.close_calls = 0

    def generate(self, manifest_path, prompt, *, device="CPU", max_new_tokens=8):
        self.calls.append((str(manifest_path), prompt, device, max_new_tokens))
        return Mock(text=f"reply to: {prompt.splitlines()[-1]}")

    def close(self):
        self.close_calls += 1


class BlockingService(FakeService):
    """FakeService that blocks inside generate() until the blocker event is set.

    Used to prove that close() waits for an in-flight send before closing the
    service, and that close() does not interrupt a generation that is already
    running.
    """

    def __init__(self, blocker):
        super().__init__()
        self._blocker = blocker

    def generate(self, manifest_path, prompt, *, device="CPU", max_new_tokens=8):
        self._blocker.wait()
        return super().generate(manifest_path, prompt, device=device, max_new_tokens=max_new_tokens)


class OpenVINOChatSessionTests(unittest.TestCase):
    def test_first_turn(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        turn = s.send("hi")
        self.assertEqual(turn.user, "hi")
        self.assertIn("reply", turn.assistant)
        self.assertEqual(len(svc.calls), 1)
        self.assertIn("User: hi", svc.calls[0][1])

    def test_second_turn_includes_history(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        s.send("hi")
        s.send("again")
        self.assertEqual(len(svc.calls), 2)
        self.assertIn("User: hi", svc.calls[1][1])
        self.assertIn("Assistant: reply", svc.calls[1][1])
        self.assertIn("User: again", svc.calls[1][1])

    def test_isolation(self):
        svc1, svc2 = FakeService(), FakeService()
        a = OpenVINOChatSession("/tmp/a/manifest.json", service=svc1)
        b = OpenVINOChatSession("/tmp/b/manifest.json", service=svc2)
        a.send("x")
        self.assertEqual(len(b.history), 0)

    def test_failure_does_not_append(self):
        svc = FakeService()
        svc.generate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        with self.assertRaises(RuntimeError):
            s.send("hi")
        self.assertEqual(len(s.history), 0)

    def test_valid_defaults_are_accepted(self):
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=FakeService())
        self.assertEqual(s._max_transcript_chars, 4000)

    def test_invalid_max_transcript_chars_rejected(self):
        for bad in (None, 0, -1, True, False, "4000", 3.5, []):
            with self.subTest(bad=bad):
                with self.assertRaises(ChatSessionConfigError):
                    OpenVINOChatSession("/tmp/m/manifest.json", service=FakeService(), max_transcript_chars=bad)

    def test_close_idempotent_and_send_after(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        s.close()
        self.assertEqual(svc.close_calls, 1)
        s.close()  # second close must not double-close the service
        self.assertEqual(svc.close_calls, 1)
        with self.assertRaises(ChatSessionClosedError):
            s.send("hi")

    def test_concurrent_serialization(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        results = []
        def worker(p):
            results.append(s.send(p))
        t1 = threading.Thread(target=worker, args=("a",))
        t2 = threading.Thread(target=worker, args=("b",))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(s.history), 2)

    def test_close_closes_injected_service_once(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        s.close()
        self.assertEqual(svc.close_calls, 1)
        s.close()
        self.assertEqual(svc.close_calls, 1)

    def test_two_sessions_have_distinct_services(self):
        a = OpenVINOChatSession("/tmp/a/manifest.json", service=FakeService())
        b = OpenVINOChatSession("/tmp/b/manifest.json", service=FakeService())
        self.assertIsNot(a._service, b._service)

    def test_closing_one_session_closes_its_own_service(self):
        a = FakeService()
        b = FakeService()
        s1 = OpenVINOChatSession("/tmp/a/manifest.json", service=a)
        s2 = OpenVINOChatSession("/tmp/b/manifest.json", service=b)
        s1.close()
        self.assertEqual(a.close_calls, 1)
        self.assertEqual(b.close_calls, 0)
        s2.close()
        self.assertEqual(b.close_calls, 1)

    def test_close_waits_until_active_turns_finish(self):
        import time
        blocker = threading.Event()
        svc = BlockingService(blocker)
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc)
        # Close is only allowed once the active turn has finished; before that
        # the service must still be open (i.e. not closed yet).
        self.assertEqual(svc.close_calls, 0)
        # Start a turn that blocks inside generate() until the blocker is set.
        t = threading.Thread(target=s.send, args=("blocked",))
        t.start()
        # Wait for the worker to actually start and block inside generate().
        time.sleep(0.5)
        # While a generation is in flight, the service must still be open.
        self.assertEqual(svc.close_calls, 0)
        # Initiate close() in a separate thread so that it blocks while the
        # generation is still active (proving close does not close the service
        # while generate() is still running).
        close_done = threading.Event()
        close_err = []
        def do_close():
            try:
                s.close()
                close_done.set()
            except Exception as e:  # noqa: BLE001
                close_err.append(e)
        c = threading.Thread(target=do_close)
        c.start()
        # While close() is blocked waiting for the active send, the service
        # must still be open.
        time.sleep(0.5)
        self.assertEqual(svc.close_calls, 0)
        # Release the blocked generation so the active send can finish.
        blocker.set()
        # Now close() should wake, close the service, and return.
        c.join(timeout=5)
        self.assertTrue(close_done.is_set())
        self.assertFalse(close_err)
        self.assertEqual(svc.close_calls, 1)
        t.join(timeout=5)
        self.assertEqual(len(svc.calls), 1)
        with self.assertRaises(ChatSessionClosedError):
            s.send("x")

    def test_rejected_turn_does_not_modify_history(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=10)
        with self.assertRaises(ChatSessionConfigError):
            s.send("p" * 20)
        self.assertEqual(s.history, [])

    def test_transcript_limit_and_isolation_still_work(self):
        a = OpenVINOChatSession("/tmp/a/manifest.json", service=FakeService(), max_transcript_chars=100)
        b = OpenVINOChatSession("/tmp/b/manifest.json", service=FakeService(), max_transcript_chars=50)
        a._history = [("a1", "a1")]
        b._history = [("b1", "b1")]
        a.send("ap")
        b.send("bp")
        self.assertEqual(len(a.history), 2)
        self.assertEqual(a.history[1][0], "ap")
        self.assertEqual(len(b.history), 2)
        self.assertEqual(b.history[1][0], "bp")


if __name__ == "__main__":
    unittest.main()
    def test_transcript_within_limit_counts_prefixes(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=1000)
        s._history = [
            ("Hello there", "Hi, I'm Alice"),
            ("How are you", "I'm fine"),
        ]
        prompt = "Tell me a joke"
        s.send(prompt)
        full = svc.calls[0][1]
        expected = (
            "User: Hello there\nAssistant: Hi, I'm Alice"
            "\nUser: How are you\nAssistant: I'm fine"
            "\nUser: Tell me a joke\nAssistant:"
        )
        self.assertEqual(full, expected)
        self.assertLessEqual(len(full), s._max_transcript_chars)
        self.assertIn("User: Hello there", full)
        self.assertIn("Assistant: Hi, I'm Alice", full)
        self.assertIn("User: How are you", full)
        self.assertIn("Assistant: I'm fine", full)
        self.assertIn("User: Tell me a joke", full)
        self.assertIn("Assistant:", full)

    def test_older_complete_turns_removed(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=70)
        s._history = [("u1", "a1"), ("u2", "a2"), ("u3", "a3")]
        s.send("prompt")
        full = svc.calls[0][1]
        expected = "User: u2\nAssistant: a2\nUser: u3\nAssistant: a3\nUser: prompt\nAssistant:"
        self.assertEqual(full, expected)
        self.assertNotIn("User: u1", full)
        self.assertIn("User: u2", full)
        self.assertIn("User: u3", full)
        self.assertIn("User: prompt", full)
        self.assertLessEqual(len(full), s._max_transcript_chars)

    def test_current_turn_exceeding_limit_rejected_without_generate(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=10)
        long_prompt = "p" * 20
        with self.assertRaises(ChatSessionConfigError) as ctx:
            s.send(long_prompt)
        self.assertIn("prompt exceeds max_transcript_chars", str(ctx.exception))
        self.assertEqual(len(svc.calls), 0)
        self.assertEqual(len(s.history), 0)

    def test_generation_failure_after_history_selection(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=1000)
        s._history = [("older", "reply")]

        def boom_generate(*args, **kwargs):
            svc.calls.append((args[1],))
            raise RuntimeError("boom")

        svc.generate = boom_generate
        with self.assertRaises(RuntimeError):
            s.send("now")
        self.assertEqual(len(s.history), 1)
        self.assertEqual(len(svc.calls), 1)
        self.assertIn("User: older", svc.calls[0][0])

    def test_history_unchanged_when_current_turn_rejected(self):
        svc = FakeService()
        s = OpenVINOChatSession("/tmp/m/manifest.json", service=svc, max_transcript_chars=30)
        s._history = [("keep", "this"), ("also", "keep")]
        long_prompt = "p" * 20
        with self.assertRaises(ChatSessionConfigError):
            s.send(long_prompt)
        self.assertEqual(s._history, [("keep", "this"), ("also", "keep")])
        self.assertEqual(len(svc.calls), 0)

    def test_history_and_limit_isolation_between_sessions(self):
        a = OpenVINOChatSession("/tmp/a/manifest.json", service=FakeService(), max_transcript_chars=100)
        b = OpenVINOChatSession("/tmp/b/manifest.json", service=FakeService(), max_transcript_chars=50)
        a._history = [("a", "a")]
        a.send("apa")
        b._history = [("b", "b")]
        b.send("bpb")
        self.assertEqual(len(a.history), 2)
        self.assertEqual(len(b.history), 2)
        self.assertEqual(a.history[0], ("a", "a"))
        self.assertEqual(b.history[0], ("b", "b"))
        self.assertEqual(a.history[1][0], "apa")
        self.assertEqual(b.history[1][0], "bpb")
        self.assertNotEqual(a._max_transcript_chars, b._max_transcript_chars)

if __name__ == "__main__":
    unittest.main()
