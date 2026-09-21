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

"""B9.13 I1: Observation → Knowledge integration (pure transport).

Implements the ratified B9.13 contract (see
``docs/B9.13-integration-specification.md``). Composition only:

    EnvironmentContext + KnowledgeRegistry
        ↓
    B9.12 translate()  (Boundary Adapter — sole identity owner)
        ↓
    BoundaryTranslation
        ↓
    B9.13 (this module): project_knowledge() per mapped projection
        ↓
    IntegrationResult {entries, unmapped, trace}

Integration never acquires the environment, never probes, never performs a
second identity translation, never calls ``resolve_runtime``/builds a
``RuntimeCapability``, never creates a ``KnowledgeAssertion``, never selects
or ranks backends, never evaluates compatibility, never constructs an
``EvaluationContext``, never decides, and never executes. Backend observation
evidence is never converted into Knowledge semantics; it remains preserved
verbatim inside the propagated ``BoundaryTrace`` (B9.13 §16).

Purity (B9.13 §23): no I/O, no subprocess, no filesystem, no environment
reads, no clocks, no randomness, no probing, no global mutable state. The
same immutable inputs produce a structurally equivalent result. The
``KnowledgeRegistry`` is a mandatory parameter; there is no default registry.

The operational representation of UNMAPPED as an explicit
``IntegrationResult.unmapped`` data entry (no exception, no KnowledgeSubject,
never UNSUPPORTED) is the ratified B9.13 policy (spec §14, I-24).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.boundary_adapter import (
    BoundaryTrace,
    MappingOutcome,
    translate,
)
from app.compatibility_knowledge import KnowledgeRegistry
from app.knowledge_bridge import KnowledgeProjection, project_knowledge
from app.observation_domain import EnvironmentContext

__all__ = [
    "IntegrationResult",
    "RuntimeIntegration",
    "UnmappedRuntime",
    "integrate",
]


@dataclass(frozen=True)
class RuntimeIntegration:
    """Knowledge-facing integration of one mapped runtime (B9.13 §19).

    ``knowledge`` is the verbatim ``KnowledgeProjection`` returned by
    ``project_knowledge`` for the B9.12 subject/scope — never reinterpreted.
    An empty projection is a valid result (Knowledge absence; read as
    ``UNKNOWN`` downstream). No backend evidence field exists here: observed
    backend evidence remains preserved verbatim in the propagated trace.
    """

    observation_identity: str
    knowledge: KnowledgeProjection

    def __post_init__(self) -> None:
        if type(self.knowledge) is not KnowledgeProjection:
            raise ValueError("knowledge must be a KnowledgeProjection")


@dataclass(frozen=True)
class UnmappedRuntime:
    """Explicit record of one runtime that did not cross the boundary.

    Ratified B9.13 policy (spec §14, I-24): a data entry, not an exception;
    it is never ERROR, never UNSUPPORTED, never a KnowledgeSubject. The
    outcome is the B9.12 mapping outcome, carried verbatim. (Today B9.12
    emits only ``UNMAPPED``; ``REJECTED`` is a B9.12 trace-vocabulary
    category that ``translate()`` does not currently emit and carries no
    operational B9.13 semantics — B9.13 §15.)
    """

    observation_identity: str
    outcome: MappingOutcome

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, MappingOutcome):
            raise ValueError("outcome must be a MappingOutcome")
        if self.outcome is MappingOutcome.MAPPED:
            raise ValueError(
                "a mapped runtime cannot be recorded as an unmapped entry"
            )


@dataclass(frozen=True)
class IntegrationResult:
    """The two-part B9.13 output, and nothing else (spec §19).

    ``entries`` holds one ``RuntimeIntegration`` per mapped runtime, in
    observation order. ``unmapped`` holds one ``UnmappedRuntime`` per
    runtime that did not cross, in observation order.
    ``len(entries) + len(unmapped) == len(context.runtimes)`` (I-18).
    ``trace`` is the B9.12 ``BoundaryTrace`` propagated verbatim (I-22):
    provenance, coverage, mapping outcomes, acquisition outcomes, error
    details, backend evidence and exclusion information survive intact.
    There is no ``backend_evidence`` field and no ``context`` field (I-06,
    I-26): zero runtimes yield ``entries=()``, ``unmapped=()`` and the
    translated trace of the empty context.
    """

    entries: tuple[RuntimeIntegration, ...] = ()
    unmapped: tuple[UnmappedRuntime, ...] = ()
    trace: BoundaryTrace = field(default_factory=BoundaryTrace)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, RuntimeIntegration):
                raise ValueError("entries must contain RuntimeIntegration only")
        if not isinstance(self.unmapped, tuple):
            raise ValueError("unmapped must be a tuple")
        for item in self.unmapped:
            if not isinstance(item, UnmappedRuntime):
                raise ValueError("unmapped must contain UnmappedRuntime only")
        if not isinstance(self.trace, BoundaryTrace):
            raise ValueError("trace must be a BoundaryTrace")


def integrate(
    context: EnvironmentContext, registry: KnowledgeRegistry
) -> IntegrationResult:
    """Integrate one observed environment with the supplied knowledge base.

    Pure and deterministic (B9.13 §23): the same immutable
    ``(context, registry)`` always yields a structurally equivalent
    ``IntegrationResult``. The registry is never mutated.

    Identity flows exclusively from B9.12: each mapped projection's
    ``knowledge_subject`` and ``scope`` are passed verbatim to
    ``project_knowledge`` — no second translation, no second mapping table,
    no heuristic. Each runtime is processed independently: an UNMAPPED
    runtime never prevents a mapped runtime from producing a valid entry,
    and no ranking or selection ever occurs.
    """
    if type(context) is not EnvironmentContext:
        raise ValueError("context must be an EnvironmentContext")
    if type(registry) is not KnowledgeRegistry:
        raise ValueError("registry must be a KnowledgeRegistry")

    translation = translate(context)

    # projections and runtime_traces both follow context.runtimes order;
    # consume the projections in lockstep with the mapped traces.
    projections = iter(translation.projections)
    entries: list[RuntimeIntegration] = []
    unmapped: list[UnmappedRuntime] = []
    for runtime_trace in translation.trace.runtime_traces:
        if runtime_trace.mapping_outcome is MappingOutcome.MAPPED:
            projection = next(projections)
            if projection.observation_identity != runtime_trace.observation_identity:
                raise ValueError(
                    "B9.12 trace/projection order mismatch for identity "
                    f"{runtime_trace.observation_identity!r}"
                )
            entries.append(
                RuntimeIntegration(
                    observation_identity=projection.observation_identity,
                    knowledge=project_knowledge(
                        registry,
                        projection.knowledge_subject,
                        projection.scope,
                    ),
                )
            )
        else:
            # Ratified B9.13 policy: an explicit data entry, never an
            # exception, never UNSUPPORTED (spec §14, §15, I-24). Today the
            # non-mapped outcome emitted by B9.12 is UNMAPPED; any other
            # non-mapped outcome the B9.12 trace vocabulary may one day
            # carry is recorded verbatim without invented semantics.
            unmapped.append(
                UnmappedRuntime(
                    observation_identity=runtime_trace.observation_identity,
                    outcome=runtime_trace.mapping_outcome,
                )
            )

    return IntegrationResult(
        entries=tuple(entries),
        unmapped=tuple(unmapped),
        trace=translation.trace,
    )
