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

"""B9.12 I1: Boundary Adapter — pure translation domain core.

Implements the ratified B9.12 contract (see
``docs/B9.12-boundary-adapter-specification.md``) as an isolated translation
boundary between the Observation domain (B9.11) and the Knowledge layer:

    Observation
        |
        v  B9.12 (this module)
    Knowledge-facing projection + Boundary Trace

The adapter TRANSLATES. It never probes, evaluates, ranks, recommends,
selects, or executes. Purity contract (spec §16): no I/O, no clocks, no
randomness, no environment reads, no command execution, no discovery of
new facts.

Isolation (spec §19): this module does NOT import legacy provider modules
(``app.platform``, ``app.hardware``, ``app.runtimes``, ``app.gpu_setup``)
and never reuses the legacy ``compatibility_names`` vocabulary. It imports
only the B9.11 observation domain (its input contract) and the Knowledge
contracts that define the destination vocabulary (``KnowledgeSubject``,
``KnowledgeScope``, ``KnowledgeKind``).

I1 scope (implementation slice): explicit runtime identity mapping (§9),
Knowledge-facing projection (§6/§8), fixed ``KnowledgeScope()`` v1 (§10),
minimum Boundary Trace semantics (§6.1), deterministic translation
outcomes (§16), and the epistemic preservation rules (§12, §15).
Integration with the evaluator/bridge/application flow is a later,
separately controlled block (spec §3, §18).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from app.compatibility_knowledge import (
    KnowledgeKind,
    KnowledgeScope,
    KnowledgeSubject,
)
from app.observation_domain import (
    CoverageState,
    EnvironmentContext,
    ObservationFamily,
    ObservationState,
    ObservedValue,
    RuntimeObservation,
)

# ----------------------------------------------------------------------
# §9: explicit, closed, deterministic identity mapping table.
#
# The contract is owned by the Boundary Adapter. The table is keyed by
# ``RuntimeObservation.canonical_id`` — the fixed probing target — never by
# ``executable_path``, provenance ``source``, or any resolved candidate
# name (§7). Knowledge aliases (``llamacpp``, ``llama.app``) are metadata,
# never lookup keys, and are deliberately NOT mapping inputs. Candidate
# names ``llama`` / ``llama-cli`` / ``llama.app`` are executable evidence,
# not identities.
# ----------------------------------------------------------------------

_LLAMA_CPP = "llama.cpp"
_OLLAMA = "ollama"

RUNTIME_IDENTITY_MAPPING: Mapping[str, str] = MappingProxyType({
    _LLAMA_CPP: _LLAMA_CPP,
    _OLLAMA: _OLLAMA,
})


class MappingOutcome(str, Enum):
    """Outcome of one runtime identity mapping (§6.1, category 3)."""

    MAPPED = "mapped"
    #: a syntactically valid observation identity for which the closed
    #: table defines no mapping: an explicit "no mapping" outcome, never
    #: a guess (§9).
    UNMAPPED = "unmapped"
    #: the input was not a valid observation identity at all (§9: explicit,
    #: typed failure for invalid input).
    REJECTED = "rejected"


class TraceOutcome(str, Enum):
    """Boundary trace outcome categories (§6.1)."""

    MAPPED = "mapped"
    EXCLUDED = "excluded"
    UNMAPPED = "unmapped"
    REJECTED = "rejected"
    ERROR = "error"


class UnmappedIdentityError(ValueError):
    """Explicit typed failure for an unknown observation identity (§9).

    Same style as ``resolve_runtime``'s zero-match ``ValueError``. Raised
    only by the direct mapping function; the whole-context translation
    records the same fact as an explicit ``UNMAPPED`` trace outcome instead
    of aborting (§6.1), so one unknown runtime never hides the mappings of
    the others.
    """


def _validate_observation_identity(identity: object) -> str:
    if type(identity) is not str or not identity.strip():
        raise ValueError("observation identity must be a non-empty string")
    return identity


def map_runtime_identity(observation_identity: str) -> KnowledgeSubject:
    """Map one observation identity to its Knowledge runtime identity.

    Exact, closed, deterministic lookup in the ratified §9 table. No fuzzy,
    case-insensitive, substring, prefix, or similarity matching, and no
    normalization of the input. Unknown identities raise
    :class:`UnmappedIdentityError` — they are never guessed.

    The result is a ``KnowledgeSubject``-aligned canonical identity (§6):
    the resolved executable candidate is NOT an identity (§7), so this
    function accepts only the observation identity itself.
    """
    identity = _validate_observation_identity(observation_identity)
    knowledge_id = RUNTIME_IDENTITY_MAPPING.get(identity)
    if knowledge_id is None:
        raise UnmappedIdentityError(
            f"no explicit B9.12 mapping for observation identity {identity!r}"
        )
    return KnowledgeSubject(kind=KnowledgeKind.RUNTIME, canonical_id=knowledge_id)


__all__ = [
    "BoundaryTrace",
    "BoundaryTraceEntry",
    "BoundaryTranslation",
    "MappingOutcome",
    "RuntimeBoundaryTrace",
    "RuntimeProjection",
    "TraceOutcome",
    "UnmappedIdentityError",
    "map_runtime_identity",
    "translate",
]


# ----------------------------------------------------------------------
# §6 output 1: Knowledge-facing projection.
#
# Carries exactly the mapped Knowledge runtime identity and the fixed v1
# scope ``KnowledgeScope()`` (§10), plus the observed backend evidence set
# carried verbatim (§11: CROSS_BOUNDARY as observed evidence set, never
# selection). No compatibility, preference, ranking, score, confidence, or
# selection fields exist here (§8, §14).
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeProjection:
    """Knowledge-facing projection of one ``RuntimeObservation`` (§6.1).

    ``knowledge_subject`` is the mapped Knowledge runtime identity and
    ``scope`` is always the v1 ``KnowledgeScope()`` (§10): scope is never
    derived from platform, version, backend, hardware, path, or provenance.

    ``detected_backends`` is the observed evidence set, verbatim: it means
    "the probe observed this syntactic evidence" and never "these backends
    are compatible/preferred/selected" (§14). ``backends_coverage`` and
    ``backends_outcome`` are carried verbatim so the epistemic distinctions
    of §12 survive: ``NOT_OBSERVED`` means "not probed" (the family is
    never presented as an evidence set), and a probed family without
    positive evidence stays distinguishable from probing failure via
    ``backends_outcome`` exactly as B9.11 defines it.
    """

    observation_identity: str
    knowledge_subject: KnowledgeSubject
    scope: KnowledgeScope
    detected_backends: tuple[ObservedValue, ...] = ()
    backends_coverage: CoverageState = CoverageState.NOT_OBSERVED
    backends_outcome: ObservedValue | None = None

    def __post_init__(self) -> None:
        if type(self.knowledge_subject) is not KnowledgeSubject:
            raise ValueError("knowledge_subject must be a KnowledgeSubject")
        if self.knowledge_subject.kind is not KnowledgeKind.RUNTIME:
            raise ValueError(
                "knowledge_subject must be a RUNTIME subject, "
                f"got {self.knowledge_subject.kind.value!r}"
            )
        if type(self.scope) is not KnowledgeScope:
            raise ValueError("scope must be a KnowledgeScope")
        # §10: KnowledgeScope() is the only scope B9.12 v1 produces.
        if self.scope != KnowledgeScope():
            raise ValueError(
                "B9.12 v1 produces exactly KnowledgeScope(); "
                "no other scope is ratified"
            )
        if not isinstance(self.detected_backends, tuple):
            raise ValueError("detected_backends must be a tuple")
        for b in self.detected_backends:
            if not isinstance(b, ObservedValue):
                raise ValueError(
                    "detected_backends must contain ObservedValue instances only"
                )
        if not isinstance(self.backends_coverage, CoverageState):
            raise ValueError("backends_coverage must be a CoverageState")
        if self.backends_outcome is not None and not isinstance(
            self.backends_outcome, ObservedValue
        ):
            raise ValueError("backends_outcome must be an ObservedValue or None")

    "UnmappedIdentityError",
    "map_runtime_identity",
    "translate",

# ----------------------------------------------------------------------
# §6 output 2 / §6.1: Boundary Trace (minimum semantic contract).
#
# The trace records everything that crossed and everything deliberately
# excluded. Provenance (``ObservedValue.source`` strings and per-fact
# details) travels verbatim (§13); the applied identity mapping is recorded
# as adapter metadata, kept separate from observation provenance (§13).
# Timestamps are carried as-is (TRACE_ONLY, §11); no timestamp is ever
# generated here (§16: no clocks).
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class BoundaryTraceEntry:
    """One trace record with the §6.1 minimum semantics."""

    #: what the record is about (fact family / item name).
    item: str
    #: the §6.1 outcome category (mapped / excluded / unmapped / rejected /
    #: error).
    outcome: TraceOutcome
    #: input observation identity when the record concerns identity mapping.
    observation_identity: str | None = None
    #: mapped identity when the mapping outcome is MAPPED.
    mapped_identity: str | None = None
    #: coverage state relevant to the boundary (§6.1 point 5).
    coverage: CoverageState | None = None
    #: observation provenance, verbatim (§6.1 point 6, §13).
    provenance: tuple[str, ...] = ()
    #: acquisition/error or diagnostic information, verbatim where it
    #: originates in the observation (§6.1 point 7, §15).
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.item, str) or not self.item.strip():
            raise ValueError("item must be a non-empty string")
        if not isinstance(self.outcome, TraceOutcome):
            raise ValueError("outcome must be a TraceOutcome")
        for name in ("observation_identity", "mapped_identity"):
            val = getattr(self, name)
            if val is not None and (not isinstance(val, str) or not val.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")
        if self.coverage is not None and not isinstance(self.coverage, CoverageState):
            raise ValueError("coverage must be a CoverageState or None")
        if not isinstance(self.provenance, tuple):
            raise ValueError("provenance must be a tuple")
        for source in self.provenance:
            if not isinstance(source, str) or not source.strip():
                raise ValueError("provenance must contain non-empty strings only")
        if self.detail is not None and (
            not isinstance(self.detail, str) or not self.detail.strip()
        ):
            raise ValueError("detail must be a non-empty string or None")


@dataclass(frozen=True)
class RuntimeBoundaryTrace:
    """Boundary trace of one ``RuntimeObservation`` (§6.1)."""

    observation_identity: str
    #: applied identity mapping as adapter metadata (§13): input → output,
    #: kept separate from observation provenance. ``None`` when unmapped.
    mapping_input: str
    mapping_output: str | None
    mapping_outcome: MappingOutcome
    entries: tuple[BoundaryTraceEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.observation_identity, str) or (
            not self.observation_identity.strip()
        ):
            raise ValueError("observation_identity must be a non-empty string")
        if not isinstance(self.mapping_input, str) or not self.mapping_input.strip():
            raise ValueError("mapping_input must be a non-empty string")
        if self.mapping_output is not None and (
            not isinstance(self.mapping_output, str) or not self.mapping_output.strip()
        ):
            raise ValueError("mapping_output must be a non-empty string or None")
        if not isinstance(self.mapping_outcome, MappingOutcome):
            raise ValueError("mapping_outcome must be a MappingOutcome")
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, BoundaryTraceEntry):
                raise ValueError("entries must contain BoundaryTraceEntry only")


@dataclass(frozen=True)
class BoundaryTrace:
    """Boundary trace of one whole ``EnvironmentContext`` translation.

    ``context_entries`` records the context-level families that did not
    cross (§11: TRACE_ONLY platform details and timestamps, OUT_OF_SCOPE
    hardware) plus acquisition/error information (§15). Nothing crosses
    silently: every excluded family is recorded as deliberately excluded.
    """

    runtime_traces: tuple[RuntimeBoundaryTrace, ...] = ()
    context_entries: tuple[BoundaryTraceEntry, ...] = ()
    #: observation snapshot timestamp, carried as-is (TRACE_ONLY, §11/§13).
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_traces, tuple):
            raise ValueError("runtime_traces must be a tuple")
        for t in self.runtime_traces:
            if not isinstance(t, RuntimeBoundaryTrace):
                raise ValueError(
                    "runtime_traces must contain RuntimeBoundaryTrace only"
                )
        if not isinstance(self.context_entries, tuple):
            raise ValueError("context_entries must be a tuple")
        for entry in self.context_entries:
            if not isinstance(entry, BoundaryTraceEntry):
                raise ValueError(
                    "context_entries must contain BoundaryTraceEntry only"
                )
        if not isinstance(self.timestamp, str):
            raise ValueError("timestamp must be a string")


@dataclass(frozen=True)
class BoundaryTranslation:
    """The two conceptual outputs of B9.12, and nothing else (§6)."""

    projections: tuple[RuntimeProjection, ...] = ()
    trace: BoundaryTrace = field(default_factory=BoundaryTrace)


# ----------------------------------------------------------------------
# §6: translation entry point. Pure, deterministic, total over valid
# inputs: every syntactically valid EnvironmentContext yields either a
# defined output or a defined, typed rejection (§16).
# ----------------------------------------------------------------------

_PLATFORM_ITEMS = (
    "platform.os_family",
    "platform.os_release",
    "platform.architecture",
    "platform.distribution",
)

_HARDWARE_ITEMS = (
    "hardware.memory_total_bytes",
    "hardware.devices",
    "hardware.acquisition_error",
)

_RUNTIME_EXCLUDED_ITEMS = (
    "executable_path",
    "raw_version",
)


def _provenance_of(value: ObservedValue) -> tuple[str, ...]:
    """Provenance of one observed fact, verbatim (§13)."""
    return (value.source,)


def _excluded_entry(
    item: str,
    outcome: TraceOutcome,
    *,
    provenance: tuple[str, ...] = (),
    detail: str | None = None,
) -> BoundaryTraceEntry:
    return BoundaryTraceEntry(
        item=item,
        outcome=outcome,
        provenance=provenance,
        detail=detail,
    )


def _fact_detail(value: ObservedValue) -> str | None:
    """Acquisition/error information of one fact, verbatim (§6.1 pt 7)."""
    if value.detail is not None:
        return value.detail
    if value.state is not ObservationState.OBSERVED:
        return value.state.value
    return None


def _trace_runtime(
    runtime: RuntimeObservation,
) -> tuple[RuntimeProjection | None, RuntimeBoundaryTrace]:
    """Translate one runtime observation (pure)."""
    identity = runtime.canonical_id
    try:
        subject = map_runtime_identity(identity)
    except UnmappedIdentityError:
        # Explicit "no mapping" outcome (§9): recorded, never guessed.
        return None, RuntimeBoundaryTrace(
            observation_identity=identity,
            mapping_input=identity,
            mapping_output=None,
            mapping_outcome=MappingOutcome.UNMAPPED,
            entries=(
                BoundaryTraceEntry(
                    item="runtime.canonical_id",
                    outcome=TraceOutcome.UNMAPPED,
                    observation_identity=identity,
                ),
            ),
        )

    entries: list[BoundaryTraceEntry] = [
        BoundaryTraceEntry(
            item="runtime.canonical_id",
            outcome=TraceOutcome.MAPPED,
            observation_identity=identity,
            mapped_identity=subject.canonical_id,
        )
    ]
    # §11: executable_path and raw_version are TRACE_ONLY — recorded as
    # deliberately excluded, provenance preserved verbatim.
    for item in _RUNTIME_EXCLUDED_ITEMS:
        value: ObservedValue = getattr(runtime, item)
        entries.append(
            _excluded_entry(
                f"runtime.{item}",
                TraceOutcome.EXCLUDED,
                provenance=_provenance_of(value),
                detail=_fact_detail(value),
            )
        )

    # §11: backend evidence is CROSS_BOUNDARY as an observed evidence set,
    # never selection (§14). Coverage travels as epistemic metadata (§12).
    backends_coverage = runtime.coverage.state_for(ObservationFamily.RUNTIME_BACKENDS)
    if backends_coverage is CoverageState.OBSERVED:
        entries.append(
            BoundaryTraceEntry(
                item="runtime.detected_backends",
                outcome=TraceOutcome.MAPPED,
                observation_identity=identity,
                mapped_identity=subject.canonical_id,
                coverage=backends_coverage,
                provenance=tuple(
                    source
                    for b in runtime.detected_backends
                    for source in _provenance_of(b)
                ),
            )
        )
        if runtime.backends_outcome is not None:
            # Probed without positive evidence, or probing failed (§12):
            # preserved verbatim, never collapsed (§15).
            entries.append(
                BoundaryTraceEntry(
                    item="runtime.backends_outcome",
                    outcome=(
                        TraceOutcome.ERROR
                        if runtime.backends_outcome.state is ObservationState.ERROR
                        else TraceOutcome.EXCLUDED
                    ),
                    observation_identity=identity,
                    provenance=_provenance_of(runtime.backends_outcome),
                    detail=_fact_detail(runtime.backends_outcome),
                )
            )
    else:
        entries.append(
            BoundaryTraceEntry(
                item="runtime.detected_backends",
                outcome=TraceOutcome.EXCLUDED,
                observation_identity=identity,
                coverage=backends_coverage,
            )
        )

    projection = RuntimeProjection(
        observation_identity=identity,
        knowledge_subject=subject,
        scope=KnowledgeScope(),
        detected_backends=runtime.detected_backends,
        backends_coverage=backends_coverage,
        backends_outcome=runtime.backends_outcome,
    )
    return projection, RuntimeBoundaryTrace(
        observation_identity=identity,
        mapping_input=identity,
        mapping_output=subject.canonical_id,
        mapping_outcome=MappingOutcome.MAPPED,
        entries=tuple(entries),
    )


def _context_entries(context: EnvironmentContext) -> tuple[BoundaryTraceEntry, ...]:
    """Context-level trace entries: exclusions, coverage, errors (§11/§15)."""
    entries: list[BoundaryTraceEntry] = []
    for item in _PLATFORM_ITEMS:
        value: ObservedValue = getattr(context.platform, item.split(".", 1)[1])
        entries.append(
            _excluded_entry(
                item,
                TraceOutcome.EXCLUDED,
                provenance=_provenance_of(value),
                detail=_fact_detail(value),
            )
        )
    for item in _HARDWARE_ITEMS:
        value = getattr(context.hardware, item.split(".", 1)[1])
        if value is None:
            continue
        if isinstance(value, ObservedValue):
            provenance: tuple[str, ...] = _provenance_of(value)
            detail = _fact_detail(value)
        else:
            # Device collections are OUT_OF_SCOPE structure (§11); they are
            # recorded as excluded without being converted into facts.
            provenance = ()
            detail = None
        entries.append(
            _excluded_entry(
                item,
                TraceOutcome.EXCLUDED,
                provenance=provenance,
                detail=detail,
            )
        )
    return tuple(entries)


def translate(context: EnvironmentContext) -> BoundaryTranslation:
    """Translate one ``EnvironmentContext`` (pure, deterministic, §16).

    Returns exactly the two conceptual B9.12 outputs (§6): the
    Knowledge-facing projections of the mapped runtimes and the boundary
    trace. The adapter performs no probing, evaluation, ranking,
    recommendation, selection, or execution (§4, §17) and never converts
    ``UNAVAILABLE``/``ERROR``/``NOT_OBSERVED`` into unsupported/absent
    (§12, §15).
    """
    if type(context) is not EnvironmentContext:
        raise ValueError("context must be an EnvironmentContext")

    projections: list[RuntimeProjection] = []
    runtime_traces: list[RuntimeBoundaryTrace] = []
    for runtime in context.runtimes:
        projection, trace = _trace_runtime(runtime)
        runtime_traces.append(trace)
        if projection is not None:
            projections.append(projection)

    return BoundaryTranslation(
        projections=tuple(projections),
        trace=BoundaryTrace(
            runtime_traces=tuple(runtime_traces),
            context_entries=_context_entries(context),
            timestamp=context.timestamp,
        ),
    )

