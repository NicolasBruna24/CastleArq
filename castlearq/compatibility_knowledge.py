# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

"""B9.5: immutable, in-memory declarative knowledge; no local observations.

Queries compare canonical (kind, id) identities and EXACT scopes. None in a
scope is not a wildcard. No version ranges, alias resolution or scope overlap
resolution is performed. Different scopes remain separate, not proven disjoint.

Open world: missing entries mean UNKNOWN. Opposite explicit states yield a
KnowledgeConflict, never an arbitrary winner or a disguised UNKNOWN. Provenance
is optional descriptive metadata, not truth/confidence. No real knowledge ships
here, and no evaluator, loader, clock, system probe or execution is involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class KnowledgeState(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class KnowledgePredicate(str, Enum):
    SUPPORTS = "supports"


class KnowledgeKind(str, Enum):
    RUNTIME = "runtime"
    BACKEND = "backend"
    FORMAT = "format"
    ARCHITECTURE = "architecture"
    CAPABILITY = "capability"
    PLATFORM = "platform"


def _text(value: object, label: str, optional: bool = False) -> None:
    if optional and value is None:
        return
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _items(values: object, kind: type, label: str) -> tuple:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a list or tuple")
    result = tuple(values)
    if any(type(item) is not kind for item in result):
        raise ValueError(f"{label} must contain {kind.__name__} only")
    return result


@dataclass(frozen=True)
class KnowledgeSubject:
    """Canonical entity reference, reused for assertion subjects AND objects.

    Display names and aliases are metadata, never lookup keys. No implicit
    normalization is performed; identifiers with boundary whitespace are invalid.
    """

    kind: KnowledgeKind
    canonical_id: str
    display_name: str | None = None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not KnowledgeKind:
            raise ValueError("kind must be a KnowledgeKind")
        _text(self.canonical_id, "canonical_id")
        if self.canonical_id != self.canonical_id.strip():
            raise ValueError("canonical_id must not have boundary whitespace")
        _text(self.display_name, "display_name", optional=True)
        aliases = _items(self.aliases, str, "aliases")
        for alias in aliases:
            _text(alias, "alias")
        object.__setattr__(self, "aliases", aliases)


@dataclass(frozen=True)
class KnowledgeScope:
    """Opaque scope metadata, matched exactly; omitted fields imply no wildcard.

    Even an empty scope is only an exact unqualified record, not evidence of
    universal applicability. Advanced applicability/overlap belongs to later work.
    """

    runtime_id: str | None = None
    runtime_version: str | None = None
    backend_id: str | None = None
    platform: str | None = None
    variant: str | None = None

    def __post_init__(self) -> None:
        for label in ("runtime_id", "runtime_version", "backend_id", "platform", "variant"):
            _text(getattr(self, label), label, optional=True)


@dataclass(frozen=True)
class KnowledgeProvenance:
    """Optional source/date labels; preserved verbatim, never fetched or ranked.

    Dates are declarative strings: no date parser, current-time defaults or
    external validation. References, including URLs, are inert text only.
    """

    source: str | None = None
    source_type: str | None = None
    reference: str | None = None
    published_at: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        for label in ("source", "source_type", "reference", "published_at", "observed_at"):
            _text(getattr(self, label), label, optional=True)


@dataclass(frozen=True)
class KnowledgeAssertion:
    subject: KnowledgeSubject
    predicate: KnowledgePredicate
    object: KnowledgeSubject
    state: KnowledgeState
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    provenance: KnowledgeProvenance = field(default_factory=KnowledgeProvenance)

    def __post_init__(self) -> None:
        for label, kind in (
            ("subject", KnowledgeSubject), ("object", KnowledgeSubject),
            ("predicate", KnowledgePredicate), ("state", KnowledgeState),
            ("scope", KnowledgeScope), ("provenance", KnowledgeProvenance),
        ):
            if type(getattr(self, label)) is not kind:
                raise ValueError(f"{label} must be a {kind.__name__}")


def _relation(assertion: KnowledgeAssertion) -> tuple:
    return (
        assertion.subject.kind, assertion.subject.canonical_id,
        assertion.predicate, assertion.object.kind, assertion.object.canonical_id,
        assertion.scope,
    )


def _assertions(values: object) -> tuple[KnowledgeAssertion, ...]:
    # Validated immutable fields: repr supplies a stable order including None.
    return tuple(sorted(set(_items(values, KnowledgeAssertion, "assertions")), key=repr))


@dataclass(frozen=True)
class KnowledgeConflict:
    """Opposite declarations for ONE exact relation/scope, with every source."""

    assertions: tuple[KnowledgeAssertion, ...]

    def __post_init__(self) -> None:
        values = _assertions(self.assertions)
        if len({_relation(item) for item in values}) != 1:
            raise ValueError("conflict must describe one exact relation and scope")
        states = {item.state for item in values}
        if not {KnowledgeState.SUPPORTED, KnowledgeState.UNSUPPORTED} <= states:
            raise ValueError("conflict requires both SUPPORTED and UNSUPPORTED")
        object.__setattr__(self, "assertions", values)


@dataclass(frozen=True)
class KnowledgeRegistry:
    """Persistent value registry: add returns a NEW registry, never mutates.

    Full-equality deduplication and ordering are independent of insertion order.
    Different provenance is preserved. ``entries`` replaces the suggested
    assertions() accessor with a frozen tuple. Queries require explicit endpoints;
    omitted scope means exact empty scope, NOT a wildcard. Cross-scope overlap
    detection/resolution is deferred, not implicitly declared conflict-free.
    """

    entries: tuple[KnowledgeAssertion, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", _assertions(self.entries))

    def add(self, assertion: KnowledgeAssertion) -> KnowledgeRegistry:
        if type(assertion) is not KnowledgeAssertion:
            raise ValueError("assertion must be a KnowledgeAssertion")
        return KnowledgeRegistry(self.entries + (assertion,))

    def query(
        self, subject: KnowledgeSubject, object: KnowledgeSubject, *,
        predicate: KnowledgePredicate = KnowledgePredicate.SUPPORTS,
        scope: KnowledgeScope = KnowledgeScope(),
    ) -> tuple[KnowledgeAssertion, ...]:
        """Exact canonical identity/scope lookup; aliases/display names ignored."""
        probe = KnowledgeAssertion(subject, predicate, object, KnowledgeState.UNKNOWN, scope)
        key = _relation(probe)
        return tuple(item for item in self.entries if _relation(item) == key)

    def state_for(
        self, subject: KnowledgeSubject, object: KnowledgeSubject, *,
        predicate: KnowledgePredicate = KnowledgePredicate.SUPPORTS,
        scope: KnowledgeScope = KnowledgeScope(),
    ) -> KnowledgeState | KnowledgeConflict:
        """Return open-world state or conflict; UNKNOWN is not a contrary claim."""
        matches = self.query(subject, object, predicate=predicate, scope=scope)
        states = {item.state for item in matches} - {KnowledgeState.UNKNOWN}
        if len(states) == 2:
            return KnowledgeConflict(matches)
        if KnowledgeState.SUPPORTED in states:
            return KnowledgeState.SUPPORTED
        if KnowledgeState.UNSUPPORTED in states:
            return KnowledgeState.UNSUPPORTED
        return KnowledgeState.UNKNOWN

    def has_conflict(
        self, subject: KnowledgeSubject, object: KnowledgeSubject, *,
        predicate: KnowledgePredicate = KnowledgePredicate.SUPPORTS,
        scope: KnowledgeScope = KnowledgeScope(),
    ) -> bool:
        return isinstance(
            self.state_for(subject, object, predicate=predicate, scope=scope),
            KnowledgeConflict,
        )

    def conflicts(self) -> tuple[KnowledgeConflict, ...]:
        """All exact-scope conflicts in deterministic order, with provenance."""
        results = []
        seen = set()
        for item in self.entries:
            key = _relation(item)
            if key not in seen:
                seen.add(key)
                result = self.state_for(
                    item.subject, item.object, predicate=item.predicate, scope=item.scope,
                )
                if isinstance(result, KnowledgeConflict):
                    results.append(result)
        return tuple(results)

