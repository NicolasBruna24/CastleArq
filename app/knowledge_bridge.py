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

"""B9.7: pure bridge from the B9.5 knowledge base to the B9.3 evaluator.

Projects existing declarative knowledge (B9.5 ``KnowledgeRegistry``) into the
supplied ``RuntimeKnowledge`` input of B9.3 (``app/compatibility_evaluator.py``).
The bridge transports knowledge; it never invents it, never resolves aliases,
never applies similarity or scope overlap, never ranks sources and never
performs I/O (B9.4 §20 contract, implemented without modifying B9.3/B9.5).

Projection unit: ``(runtime, exact scope)``. Only assertions whose subject is
the requested runtime (canonical ``(kind, canonical_id)`` identity), whose
predicate is ``SUPPORTS`` and whose scope is EXACTLY the requested
``KnowledgeScope`` are considered. An omitted scope field is not a wildcard
and a global row is never widened to cover a platform (B9.5, B9.6.0 §11).

States map as follows onto the tri-state ``RuntimeKnowledge`` lists:

- ``SUPPORTED``   → the corresponding ``supported_*`` list;
- ``UNSUPPORTED`` → the corresponding ``unsupported_*`` list;
- ``UNKNOWN``     → into NEITHER list (explicit UNKNOWN is recorded in
  ``excluded_unknown``; absence and explicit UNKNOWN are indistinguishable
  inside ``RuntimeKnowledge`` itself — documented integration limit);
- no assertion    → nothing is invented; the relation stays absent, which
  B9.3 reads as UNKNOWN. It is never turned into UNSUPPORTED.

Capabilities and platforms have no representation in ``RuntimeKnowledge``
(B9.4 §20); such assertions are reported in ``unrepresentable`` and never
transformed into another kind. Relations holding BOTH ``SUPPORTED`` and
``UNSUPPORTED`` declarations are reported per-relation in ``conflicts`` and
project nothing: the bridge never picks a winner and never disguises a
conflict as UNKNOWN or UNSUPPORTED. ``supports_artifact`` stays ``None``
unless the registry itself contains a runtime→artifact claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from .compatibility_evaluator import RuntimeKnowledge
from .compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeConflict,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)

#: Relation keys (B9.5 identity) whose object kind RuntimeKnowledge can carry.
_REPRESENTABLE_KINDS = (
    KnowledgeKind.FORMAT,
    KnowledgeKind.ARCHITECTURE,
    KnowledgeKind.BACKEND,
)

#: Destination list labels per representable object kind and state.
_SUPPORTED_LABELS = {
    KnowledgeKind.FORMAT: "supported_formats",
    KnowledgeKind.ARCHITECTURE: "supported_architectures",
    KnowledgeKind.BACKEND: "supported_backends",
}
_UNSUPPORTED_LABELS = {
    KnowledgeKind.FORMAT: "unsupported_formats",
    KnowledgeKind.ARCHITECTURE: "unsupported_architectures",
    KnowledgeKind.BACKEND: "unsupported_backends",
}


@dataclass(frozen=True)
class KnowledgeProjection:
    """Frozen result of one B9.7 projection, with full traceability.

    ``projected`` holds exactly the assertions that produced list membership
    in ``runtime_knowledge``. ``excluded_unknown`` holds explicit stored
    UNKNOWN rows under the requested scope. ``unrepresentable`` holds
    assertions ``RuntimeKnowledge`` cannot carry (capabilities, platforms).
    ``conflicts`` holds one ``KnowledgeConflict`` per opposed relation; the
    conflicting assertions are projected into NO list. Provenance survives by
    keeping the original assertion objects themselves.
    """

    runtime: KnowledgeSubject
    scope: KnowledgeScope
    runtime_knowledge: RuntimeKnowledge
    projected: tuple[KnowledgeAssertion, ...] = ()
    excluded_unknown: tuple[KnowledgeAssertion, ...] = ()
    unrepresentable: tuple[KnowledgeAssertion, ...] = ()
    conflicts: tuple[KnowledgeConflict, ...] = ()


def project_knowledge(
    registry: KnowledgeRegistry,
    runtime: KnowledgeSubject,
    scope: KnowledgeScope | None = None,
) -> KnowledgeProjection:
    """Project one runtime's exact-scope knowledge into ``RuntimeKnowledge``.

    Pure and deterministic: the same ``(registry, runtime, scope)`` always
    yields an equal ``KnowledgeProjection``, independent of insertion order
    (``KnowledgeRegistry.entries`` is canonically ordered). The registry is
    never mutated.
    """
    if type(registry) is not KnowledgeRegistry:
        raise ValueError("registry must be a KnowledgeRegistry")
    if type(runtime) is not KnowledgeSubject:
        raise ValueError("runtime must be a KnowledgeSubject")
    if runtime.kind is not KnowledgeKind.RUNTIME:
        raise ValueError(
            f"runtime must be a RUNTIME subject, got {runtime.kind.value!r}")
    if scope is None:
        scope = KnowledgeScope()
    if type(scope) is not KnowledgeScope:
        raise ValueError("scope must be a KnowledgeScope")

    selected: list[KnowledgeAssertion] = []
    unrepresentable: list[KnowledgeAssertion] = []
    for assertion in registry.entries:
        if (assertion.subject.kind is not KnowledgeKind.RUNTIME
                or assertion.subject.canonical_id != runtime.canonical_id):
            continue
        if assertion.scope != scope:
            continue
        if assertion.predicate is not KnowledgePredicate.SUPPORTS:
            unrepresentable.append(assertion)
            continue
        if assertion.object.kind not in _REPRESENTABLE_KINDS:
            unrepresentable.append(assertion)
            continue
        selected.append(assertion)

    # Group by exact relation key, preserving the registry's canonical order.
    groups: dict[tuple, list[KnowledgeAssertion]] = {}
    for assertion in selected:
        key = (assertion.object.kind, assertion.object.canonical_id)
        groups.setdefault(key, []).append(assertion)

    projected: list[KnowledgeAssertion] = []
    excluded_unknown: list[KnowledgeAssertion] = []
    conflicts: list[KnowledgeConflict] = []
    lists: dict[str, list[str]] = {}
    for key in sorted(groups, key=repr):
        items = groups[key]
        states = {item.state for item in items}
        if (KnowledgeState.SUPPORTED in states
                and KnowledgeState.UNSUPPORTED in states):
            conflicts.append(KnowledgeConflict(items))
            continue
        for assertion in items:
            kind = key[0]
            if assertion.state is KnowledgeState.SUPPORTED:
                projected.append(assertion)
                lists.setdefault(_SUPPORTED_LABELS[kind], []).append(
                    assertion.object.canonical_id)
            elif assertion.state is KnowledgeState.UNSUPPORTED:
                projected.append(assertion)
                lists.setdefault(_UNSUPPORTED_LABELS[kind], []).append(
                    assertion.object.canonical_id)
            else:
                excluded_unknown.append(assertion)

    runtime_knowledge = RuntimeKnowledge(
        name=runtime.canonical_id,
        supports_artifact=None,
        supported_formats=tuple(lists.get("supported_formats", ())),
        unsupported_formats=tuple(lists.get("unsupported_formats", ())),
        supported_architectures=tuple(lists.get(
            "supported_architectures", ())),
        unsupported_architectures=tuple(lists.get(
            "unsupported_architectures", ())),
        supported_backends=tuple(lists.get("supported_backends", ())),
        unsupported_backends=tuple(lists.get("unsupported_backends", ())),
    )
    return KnowledgeProjection(
        runtime=runtime,
        scope=scope,
        runtime_knowledge=runtime_knowledge,
        projected=tuple(projected),
        excluded_unknown=tuple(excluded_unknown),
        unrepresentable=tuple(unrepresentable),
        conflicts=tuple(conflicts),
    )
