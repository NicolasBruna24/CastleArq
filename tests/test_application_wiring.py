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

"""I1 tests for the B9.14 Application / Composition Root (application wiring).

Contract tests for ``app/application_wiring.py`` only — they protect the
ratified architectural contracts, not Observation / Integration internals:

1. Production composition: the Composition Root runs with the Q-9c
   production bindings and yields an ``IntegrationResult`` (plus the
   Q-9c glue contracts owned by this module: I-Q9-06 / I-Q9-07).
2. Fresh context per invocation (Q-2, I-Q9-03): invocation A's context
   is not invocation B's context; no global or cached context, a fresh
   observer per invocation.
3. Single observation (Q-6, §19): exactly one ``capture_context()``
   call per invocation.
4. Registry injection (Q-3a–Q-3d, I-02, I-Q9-04): the registry
   delivered to ``integrate()`` IS ``INITIAL_KNOWLEDGE_REGISTRY``,
   unreplaced and not rebuilt per invocation.
5. Single integration (§19): exactly one ``integrate()`` call per
   invocation.
6. Result identity / transport (§16, §12 stop-line): the value returned
   is EXACTLY the ``IntegrationResult`` produced by Integration — no
   wrapper, no reinterpretation.
7. Class-A forwarding (Q-7 = FORWARD, §11.3): Class-A evidence captured
   in the context flows into ``integrate()`` normally; no abort, no
   retry, no fallback, no reclassification inside the Composition Root.
8. No double composition (§19): one invocation → one observer, one
   observation, one integration of the same captured context.

All test doubles live in this file (Q-9d allow-list). No legacy module,
no Observation / Boundary Adapter / Integration / Knowledge module and
no existing test is modified or re-tested here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest import mock

from app import application_wiring as wiring
from app.initial_knowledge import INITIAL_KNOWLEDGE_REGISTRY
from app.observation_domain import (
    CoverageEntry,
    CoverageState,
    EnvironmentContext,
    HardwareObservation,
    ObservationCoverage,
    ObservationFamily,
    ObservationState,
    ObservedValue,
    PlatformObservation,
    RuntimeObservation,
)
from app.observation_knowledge import IntegrationResult, integrate
from app.observation_probe import CommandResult

OBSERVED = ObservationState.OBSERVED
UNAVAILABLE = ObservationState.UNAVAILABLE
ERROR = ObservationState.ERROR

# ----------------------------------------------------------------------
# Class-A context fixture (values conform to the ratified B9.11 domain)
# ----------------------------------------------------------------------

def fact(state=OBSERVED, value=None, source="i1-test", detail=None):
    if detail is None and state is not OBSERVED:
        detail = state.value
    return ObservedValue(state=state, value=value, source=source, detail=detail)


def class_a_environment(timestamp="2026-01-01T00:00:00+00:00") -> EnvironmentContext:
    """An ``EnvironmentContext`` carrying Class-A acquisition evidence."""
    runtime = RuntimeObservation(
        canonical_id="llama.cpp",
        executable_path=fact(ERROR, source="cmd:llama.cpp", detail="timeout"),
        raw_version=fact(UNAVAILABLE, source="cmd:llama.cpp --version"),
        detected_backends=(),
        backends_outcome=fact(ERROR, source="cmd:llama.cpp --help", detail="crash"),
        coverage=ObservationCoverage(entries=(
            CoverageEntry(ObservationFamily.RUNTIME_DISCOVERY, CoverageState.OBSERVED),
            CoverageEntry(ObservationFamily.RUNTIME_BACKENDS, CoverageState.OBSERVED),
        )),
    )
    return EnvironmentContext(
        timestamp=timestamp,
        platform=PlatformObservation(
            os_family=fact(OBSERVED, "linux", source="python:platform.system"),
            os_release=fact(OBSERVED, "6.8", source="python:platform.release"),
            architecture=fact(OBSERVED, "x86_64", source="python:platform.machine"),
            distribution=fact(
                UNAVAILABLE,
                source="file:/etc/os-release",
                detail="/etc/os-release not accessible or not found",
            ),
        ),
        hardware=HardwareObservation(
            memory_total_bytes=fact(OBSERVED, 16 * 1024**3, source="file:/proc/meminfo"),
            devices=(),
            acquisition_error=fact(UNAVAILABLE, source="which:lspci", detail="not found"),
        ),
        runtimes=(runtime,),
    )


# ----------------------------------------------------------------------
# Wiring-level test doubles (live only in this file; Q-9d allow-list)
# ----------------------------------------------------------------------

class RecordingObserver:
    """``EnvironmentObserver`` double: counts constructions and captures.

    Every ``capture_context()`` returns a NEW Class-A context, so any
    caching or reuse of a context inside the Composition Root would show
    up as identity equality between distinct captures.
    """

    instances: list[RecordingObserver] = []
    _sequence = 0

    def __init__(
        self,
        command_runner=None,
        file_reader=None,
        which_finder=None,
        timestamp_provider=None,
    ):
        self.bindings = (command_runner, file_reader, which_finder, timestamp_provider)
        self.captured_contexts: list[EnvironmentContext] = []
        RecordingObserver.instances.append(self)

    def capture_context(self) -> EnvironmentContext:
        RecordingObserver._sequence += 1
        context = class_a_environment(
            timestamp=f"2026-01-01T00:00:{RecordingObserver._sequence % 60:02d}+00:00"
        )
        self.captured_contexts.append(context)
        return context

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls._sequence = 0


class RecordingIntegrate:
    """``integrate()`` double: records every call, then delegates for real."""

    def __init__(self, implementation=integrate):
        self.calls: list[tuple[EnvironmentContext, object]] = []
        self._implementation = implementation

    def __call__(self, context, registry):
        self.calls.append((context, registry))
        return self._implementation(context, registry)

# ----------------------------------------------------------------------
# Test 1 — production composition (real Q-9c bindings)
# ----------------------------------------------------------------------

class ProductionCompositionTests(unittest.TestCase):
    """The Composition Root builds and runs with the production bindings."""

    def test_composition_runs_with_production_bindings(self) -> None:
        result = wiring.compose_and_integrate()
        self.assertIsInstance(result, IntegrationResult)

    def test_q9c_timestamp_provider_is_utc_iso8601(self) -> None:
        stamp = wiring.utc_timestamp()
        parsed = datetime.fromisoformat(stamp)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_q9c_command_runner_preserves_b911_semantics(self) -> None:
        # success: exit code / stdout / stderr preserved, no error
        ok = wiring.production_command_runner(
            [sys.executable, "-c", "print('i1-ok')"], 30.0
        )
        self.assertIsInstance(ok, CommandResult)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(ok.stdout, "i1-ok\n")
        self.assertEqual(ok.stderr, "")
        self.assertIsNone(ok.error)

        # non-zero exit preserved as returncode (never swallowed into error)
        failed = wiring.production_command_runner(
            [sys.executable, "-c", "import sys; sys.exit(3)"], 30.0
        )
        self.assertEqual(failed.returncode, 3)
        self.assertIsNone(failed.error)

        # OSError → CommandResult.error (never None, never raised: Class-A)
        missing = wiring.production_command_runner(
            ["i1-binary-that-does-not-exist-9f3a"], 30.0
        )
        self.assertEqual(missing.returncode, -1)
        self.assertIsInstance(missing.error, str)
        self.assertTrue(missing.error)

        # explicit timeout → CommandResult.error (Class-A evidence, forwarded)
        timed_out = wiring.production_command_runner(
            [sys.executable, "-c", "import time; time.sleep(30)"], 0.25
        )
        self.assertEqual(timed_out.returncode, -1)
        self.assertIsInstance(timed_out.error, str)
        self.assertIn("timeout", timed_out.error)

    def test_q9c_file_reader_preserves_observer_contract(self) -> None:
        # existing content → str
        content = wiring.production_file_reader(__file__)
        self.assertIsInstance(content, str)
        self.assertIn("application_wiring", content)
        # absent file → None
        absent = str(Path(__file__).parent / "no-such-file-for-i1")
        self.assertIsNone(wiring.production_file_reader(absent))
        # unreadable path (directory) → None, never raised
        self.assertIsNone(wiring.production_file_reader(str(Path(__file__).parent)))


# ----------------------------------------------------------------------
# Tests 2–8 — Composition Root architectural contracts
# ----------------------------------------------------------------------

class CompositionRootContractTests(unittest.TestCase):
    """Behavioral checks of one Composition Root invocation (Q-1..Q-7)."""

    def setUp(self) -> None:
        RecordingObserver.reset()

    def _compose(self, integrate_double):
        with mock.patch.object(
            wiring, "EnvironmentObserver", RecordingObserver
        ), mock.patch.object(wiring, "integrate", integrate_double):
            return wiring.compose_and_integrate()

    def test_fresh_context_per_invocation(self) -> None:
        # Test 2 (Q-2, I-Q9-03): invocation A ≠ invocation B.
        recorder = RecordingIntegrate()
        first = self._compose(recorder)
        second = self._compose(recorder)
        self.assertEqual(len(recorder.calls), 2)
        context_a, registry_a = recorder.calls[0]
        context_b, registry_b = recorder.calls[1]
        self.assertIsNot(context_a, context_b)  # no cached/global context
        self.assertIsNot(first, second)
        # a fresh observer per invocation; the registry (Q-3b) is the SAME
        # Composition-Root-lifetime instance, never rebuilt
        self.assertEqual(len(RecordingObserver.instances), 2)
        self.assertIsNot(
            RecordingObserver.instances[0], RecordingObserver.instances[1]
        )
        self.assertIs(registry_a, registry_b)
        self.assertIs(registry_a, INITIAL_KNOWLEDGE_REGISTRY)

    def test_single_observation_per_invocation(self) -> None:
        # Test 3 (Q-6, §19): exactly one capture_context() per invocation.
        recorder = RecordingIntegrate()
        self._compose(recorder)
        self.assertEqual(len(RecordingObserver.instances), 1)
        observer = RecordingObserver.instances[0]
        self.assertEqual(len(observer.captured_contexts), 1)

    def test_registry_injection_is_the_initial_knowledge_registry(self) -> None:
        # Test 4 (Q-3a–Q-3d, I-02): the registry handed to integrate() IS
        # INITIAL_KNOWLEDGE_REGISTRY — no replacement, no second dataset,
        # no rebuild across invocations.
        recorder = RecordingIntegrate()
        self._compose(recorder)
        self._compose(recorder)
        self.assertEqual(len(recorder.calls), 2)
        registries = [registry for _, registry in recorder.calls]
        for registry in registries:
            self.assertIs(registry, INITIAL_KNOWLEDGE_REGISTRY)
        self.assertIs(registries[0], registries[1])

    def test_single_integration_per_invocation(self) -> None:
        # Test 5 (§19): exactly one integrate() call per invocation.
        recorder = RecordingIntegrate()
        result = self._compose(recorder)
        self.assertEqual(len(recorder.calls), 1)
        self.assertIsInstance(result, IntegrationResult)

    def test_result_is_the_integration_result_itself(self) -> None:
        # Test 6 (§16, §12): the returned value is EXACTLY Integration's
        # own result — no wrapper, no reinterpretation, no new result type.
        sentinel = integrate(class_a_environment(), INITIAL_KNOWLEDGE_REGISTRY)
        stub = mock.Mock(return_value=sentinel)
        result = self._compose(stub)
        self.assertIs(result, sentinel)
        stub.assert_called_once()

    def test_class_a_evidence_is_forwarded_not_aborted(self) -> None:
        # Test 7 (Q-7 = FORWARD): the Class-A context flows into
        # integrate() exactly once; the invocation returns normally with
        # an observable IntegrationResult — no abort, no retry, no
        # fallback, no reclassification of the evidence.
        recorder = RecordingIntegrate()
        result = self._compose(recorder)  # must not raise: no abort path
        self.assertEqual(len(RecordingObserver.instances), 1)
        observer = RecordingObserver.instances[0]
        self.assertEqual(len(observer.captured_contexts), 1)
        self.assertEqual(len(recorder.calls), 1)  # one capture → one integrate
        context, _ = recorder.calls[0]
        self.assertIs(context, observer.captured_contexts[0])
        # classification reaches integrate() unreinterpreted (no ERROR →
        # UNAVAILABLE, no Class-A → Class-B)
        self.assertEqual(context.hardware.acquisition_error.state, UNAVAILABLE)
        runtime = context.runtimes[0]
        self.assertEqual(runtime.executable_path.state, ERROR)
        self.assertEqual(runtime.backends_outcome.state, ERROR)
        # observable outcome exists at the stop-line
        self.assertIsInstance(result, IntegrationResult)

    def test_one_invocation_is_one_composition(self) -> None:
        # Test 8 (§19, Q-6): one observer, one observation, one
        # integration, and the captured context IS the integrated one —
        # no second Composition Root, no second Observation/Integration.
        recorder = RecordingIntegrate()
        self._compose(recorder)
        self.assertEqual(len(RecordingObserver.instances), 1)
        observer = RecordingObserver.instances[0]
        self.assertEqual(len(observer.captured_contexts), 1)
        self.assertEqual(len(recorder.calls), 1)
        self.assertIs(recorder.calls[0][0], observer.captured_contexts[0])


if __name__ == "__main__":
    unittest.main()

