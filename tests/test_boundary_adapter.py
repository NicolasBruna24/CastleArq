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

"""Hermetic tests for B9.12 I1: boundary adapter domain core.

Covers exactly the I1 contract: explicit closed identity mapping (§9),
executable-candidate separation (§7), fixed KnowledgeScope() v1 (§10),
determinism (§16), epistemic preservation (§12/§15), backend evidence
semantics (§14), minimum trace semantics (§6.1), and purity (§16).
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.boundary_adapter import (
    BoundaryTranslation,
    MappingOutcome,
    TraceOutcome,
    UnmappedIdentityError,
    map_runtime_identity,
    translate,
)
from app.compatibility_knowledge import (
    KnowledgeKind,
    KnowledgeScope,
    KnowledgeSubject,
)
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

OBSERVED = ObservationState.OBSERVED
UNAVAILABLE = ObservationState.UNAVAILABLE
ERROR = ObservationState.ERROR


def fact(
    state: ObservationState = OBSERVED,
    value: object = None,
    source: str = "test",
    detail: str | None = None,
) -> ObservedValue:
    # AD-05: non-OBSERVED states require a non-empty detail.
    if detail is None and state is not OBSERVED:
        detail = state.value
    return ObservedValue(state=state, value=value, source=source, detail=detail)


def runtime_observation(
    canonical_id: str,
    *,
    executable_value: object | None = None,
    version_state: ObservationState = OBSERVED,
    backends: tuple[ObservedValue, ...] = (),
    backends_coverage: CoverageState = CoverageState.NOT_OBSERVED,
    backends_outcome: ObservedValue | None = None,
) -> RuntimeObservation:
    executable_state = (
        OBSERVED if executable_value is not None else UNAVAILABLE
    )
    if version_state is OBSERVED and executable_value is None:
        version_state = UNAVAILABLE
    version_value = "raw text" if version_state is OBSERVED else None
    return RuntimeObservation(
        canonical_id=canonical_id,
        executable_path=fact(executable_state, executable_value, "which:probe"),
        raw_version=fact(version_state, version_value, "cmd:--version"),
        detected_backends=backends,
        backends_outcome=backends_outcome,
        coverage=ObservationCoverage(
            entries=(
                CoverageEntry(ObservationFamily.RUNTIME_DISCOVERY, CoverageState.OBSERVED),
                CoverageEntry(ObservationFamily.RUNTIME_VERSION, CoverageState.OBSERVED),
                CoverageEntry(
                    ObservationFamily.RUNTIME_BACKENDS, backends_coverage
                ),
            )
        ),
    )


def environment(*runtimes: RuntimeObservation) -> EnvironmentContext:
    return EnvironmentContext(
        timestamp="2026-09-18T12:00:00Z",
        platform=PlatformObservation(
            os_family=fact(OBSERVED, "darwin"),
            os_release=fact(OBSERVED, "25.0.0"),
            architecture=fact(OBSERVED, "arm64"),
            distribution=fact(UNAVAILABLE),
        ),
        hardware=HardwareObservation(
            memory_total_bytes=fact(OBSERVED, 16 * 1024**3),
            devices=(),
            acquisition_error=None,
        ),
        runtimes=runtimes,
    )


class IdentityMappingTests(unittest.TestCase):
    def test_known_identities_map_exactly(self) -> None:
        self.assertEqual(
            map_runtime_identity("llama.cpp"),
            KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp"),
        )
        self.assertEqual(
            map_runtime_identity("ollama"),
            KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="ollama"),
        )

    def test_unknown_identity_is_not_guessed(self) -> None:
        for unknown in ("llamacpp", "LLAMA.CPP", " llama.cpp", "llama.cpp ", "x"):
            with self.assertRaises(UnmappedIdentityError, msg=unknown):
                map_runtime_identity(unknown)

    def test_invalid_identity_is_rejected(self) -> None:
        for invalid in ("", "   ", None, 3):
            with self.assertRaises(ValueError, msg=repr(invalid)):
                map_runtime_identity(invalid)  # type: ignore[arg-type]

    def test_unmapped_error_is_value_error(self) -> None:
        self.assertTrue(issubclass(UnmappedIdentityError, ValueError))

    def test_executable_candidates_are_not_identities(self) -> None:
        for candidate in ("llama", "llama-cli", "llama.app", "which:llama"):
            with self.assertRaises(UnmappedIdentityError, msg=candidate):
                map_runtime_identity(candidate)


class ProjectionTests(unittest.TestCase):
    def test_projection_carries_mapped_identity_and_v1_scope(self) -> None:
        result = translate(environment(runtime_observation("llama.cpp")))
        self.assertEqual(len(result.projections), 1)
        p = result.projections[0]
        self.assertEqual(p.observation_identity, "llama.cpp")
        self.assertEqual(
            p.knowledge_subject,
            KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id="llama.cpp"),
        )
        self.assertEqual(p.scope, KnowledgeScope())

    def test_v1_scope_never_varies_with_environment(self) -> None:
        observations = (
            runtime_observation("ollama"),
            runtime_observation("llama.cpp", backends=(fact(value="vulkan"),)),
        )
        result = translate(environment(*observations))
        for projection in result.projections:
            self.assertEqual(projection.scope, KnowledgeScope())

    def test_projection_has_no_decision_fields(self) -> None:
        result = translate(environment(runtime_observation("llama.cpp")))
        p = result.projections[0]
        for forbidden in (
            "compatible",
            "incompatible",
            "preferred",
            "recommended",
            "selected",
            "score",
            "ranking",
            "confidence",
        ):
            self.assertFalse(hasattr(p, forbidden), forbidden)


class BackendEvidenceTests(unittest.TestCase):
    def test_backend_evidence_is_preserved_verbatim_not_decided(self) -> None:
        evidence = (
            fact(value="vulkan", source="cmd:llama-cli --list-backends"),
            fact(value="cuda", source="cmd:llama-cli --list-backends"),
        )
        result = translate(
            environment(
                runtime_observation(
                    "llama.cpp",
                    backends=evidence,
                    backends_coverage=CoverageState.OBSERVED,
                )
            )
        )
        p = result.projections[0]
        self.assertEqual(p.detected_backends, evidence)
        self.assertEqual(p.backends_coverage, CoverageState.OBSERVED)
        self.assertIsNone(p.backends_outcome)
        for forbidden in ("compatible", "preferred", "selected", "recommended"):
            self.assertFalse(hasattr(p, forbidden), forbidden)


class EpistemicPreservationTests(unittest.TestCase):
    def test_not_observed_backends_stay_not_observed(self) -> None:
        result = translate(environment(runtime_observation("ollama")))
        p = result.projections[0]
        self.assertEqual(p.backends_coverage, CoverageState.NOT_OBSERVED)
        self.assertEqual(p.detected_backends, ())
        self.assertIsNone(p.backends_outcome)
        entry = next(
            e for e in result.trace.runtime_traces[0].entries
            if e.item == "runtime.detected_backends"
        )
        self.assertEqual(entry.coverage, CoverageState.NOT_OBSERVED)

    def test_probed_unavailable_stays_unavailable_not_absent(self) -> None:
        outcome = fact(UNAVAILABLE, source="cmd:llama-cli --list-backends")
        result = translate(
            environment(
                runtime_observation(
                    "llama.cpp",
                    backends_coverage=CoverageState.OBSERVED,
                    backends_outcome=outcome,
                )
            )
        )
        p = result.projections[0]
        self.assertEqual(p.backends_coverage, CoverageState.OBSERVED)
        self.assertEqual(p.backends_outcome, outcome)
        self.assertEqual(p.backends_outcome.state, UNAVAILABLE)

    def test_probed_error_stays_error_not_unavailable(self) -> None:
        outcome = fact(
            ERROR, source="cmd:llama-cli --list-backends", detail="timeout"
        )
        result = translate(
            environment(
                runtime_observation(
                    "llama.cpp",
                    backends_coverage=CoverageState.OBSERVED,
                    backends_outcome=outcome,
                )
            )
        )
        p = result.projections[0]
        self.assertEqual(p.backends_outcome, outcome)
        self.assertEqual(p.backends_outcome.state, ERROR)
        error_entry = next(
            e for e in result.trace.runtime_traces[0].entries
            if e.item == "runtime.backends_outcome"
        )
        self.assertEqual(error_entry.outcome, TraceOutcome.ERROR)
        self.assertEqual(error_entry.detail, "timeout")

    def test_unavailable_executable_stays_unavailable(self) -> None:
        result = translate(environment(runtime_observation("ollama")))
        entry = next(
            e for e in result.trace.runtime_traces[0].entries
            if e.item == "runtime.executable_path"
        )
        self.assertEqual(entry.detail, "unavailable")


class TraceTests(unittest.TestCase):
    def test_minimum_trace_semantics_are_represented(self) -> None:
        result = translate(
            environment(
                runtime_observation(
                    "llama.cpp",
                    executable_value="/usr/local/bin/llama-cli",
                    backends=(
                        fact(value="vulkan", source="cmd:llama-cli --list-backends"),
                    ),
                    backends_coverage=CoverageState.OBSERVED,
                )
            )
        )
        trace = result.trace.runtime_traces[0]
        # (1) input identity, (2) applied mapping, (3) mapping outcome.
        self.assertEqual(trace.observation_identity, "llama.cpp")
        self.assertEqual(trace.mapping_input, "llama.cpp")
        self.assertEqual(trace.mapping_output, "llama.cpp")
        self.assertEqual(trace.mapping_outcome, MappingOutcome.MAPPED)
        # (4) deliberately excluded facts.
        excluded = {e.item for e in trace.entries if e.outcome is TraceOutcome.EXCLUDED}
        self.assertIn("runtime.executable_path", excluded)
        self.assertIn("runtime.raw_version", excluded)
        # (5) coverage, (6) provenance, (7) acquisition/error info.
        backend_entry = next(
            e for e in trace.entries if e.item == "runtime.detected_backends"
        )
        self.assertEqual(backend_entry.coverage, CoverageState.OBSERVED)
        self.assertIn("cmd:llama-cli --list-backends", backend_entry.provenance)
        mapped = next(
            e for e in trace.entries if e.item == "runtime.canonical_id"
        )
        self.assertEqual(mapped.mapped_identity, "llama.cpp")

    def test_trace_records_all_outcome_categories(self) -> None:
        self.assertEqual(
            {o.value for o in TraceOutcome},
            {"mapped", "excluded", "unmapped", "rejected", "error"},
        )

    def test_context_exclusions_are_recorded(self) -> None:
        result = translate(environment(runtime_observation("ollama")))
        items = {e.item for e in result.trace.context_entries}
        for expected in (
            "platform.os_family",
            "platform.os_release",
            "platform.architecture",
            "platform.distribution",
            "hardware.memory_total_bytes",
            "hardware.devices",
        ):
            self.assertIn(expected, items)
        self.assertEqual(result.trace.timestamp, "2026-09-18T12:00:00Z")

    def test_unmapped_runtime_is_traced_not_guessed(self) -> None:
        result = translate(
            environment(
                runtime_observation("llama.cpp"),
                runtime_observation("llama.app"),
            )
        )
        self.assertEqual(len(result.projections), 1)
        self.assertEqual(len(result.trace.runtime_traces), 2)
        unmapped = result.trace.runtime_traces[1]
        self.assertEqual(unmapped.observation_identity, "llama.app")
        self.assertEqual(unmapped.mapping_outcome, MappingOutcome.UNMAPPED)
        self.assertIsNone(unmapped.mapping_output)
        self.assertEqual(
            unmapped.entries[0].outcome, TraceOutcome.UNMAPPED
        )

    def test_provenance_travels_verbatim(self) -> None:
        result = translate(
            environment(
                runtime_observation(
                    "llama.cpp", executable_value="/opt/llama/bin/llama"
                )
            )
        )
        entry = next(
            e for e in result.trace.runtime_traces[0].entries
            if e.item == "runtime.executable_path"
        )
        self.assertEqual(entry.provenance, ("which:probe",))


class DeterminismAndPurityTests(unittest.TestCase):
    def test_same_input_yields_equal_output(self) -> None:
        ctx = environment(
            runtime_observation(
                "llama.cpp",
                executable_value="/usr/bin/llama-cli",
                backends=(fact(value="cpu"),),
                backends_coverage=CoverageState.OBSERVED,
            ),
            runtime_observation("ollama"),
        )
        first = translate(ctx)
        second = translate(ctx)
        self.assertEqual(first, second)
        self.assertEqual(repr(first), repr(second))

    def test_translation_is_a_pure_function_of_its_input(self) -> None:
        # No probing or environment access: the adapter accepts an already
        # observed value object; the call performs no I/O of its own.
        ctx = environment(runtime_observation("llama.cpp"))
        self.assertIsInstance(translate(ctx), BoundaryTranslation)

    def test_module_has_no_legacy_or_io_imports(self) -> None:
        source = (
            Path(__file__).resolve().parent.parent / "app" / "boundary_adapter.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        forbidden = {
            "app.platform",
            "app.hardware",
            "app.runtimes",
            "app.gpu_setup",
            "subprocess",
            "os",
            "platform",
            "time",
            "random",
            "socket",
            "shutil",
        }
        self.assertFalse(imported & forbidden, imported & forbidden)
        # No forbidden side-effect-capable calls in the adapter source.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr,
                    {"system", "popen", "run", "check_output", "getenv", "time"},
                    node.func.attr,
                )


if __name__ == "__main__":
    unittest.main()
