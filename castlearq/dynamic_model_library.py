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

"""B9.91: internal Dynamic Model Library capability (live / stateless).

This module is an **application-layer composition capability** over the already
closed B9.80-B9.90 discovery, selection and acquisition architecture. It is not
a discovery provider, not a discovery port, not a selection engine, not an
acquisition service, not an acquisition facade, not a persistence layer and not
a presentation layer.

The responsibility it owns, and the only responsibility it owns, is
**composition**:

    search(query, limit, cursor)          -> candidates + provider cursor
        candidate
            -> inspect(candidate.repository)
                -> ModelVariant[]  (each carrying its own candidate)
                    -> DiscoveredArtifact[]
                        -> B9.84 select_discovered_artifact(...)
                            -> selected DiscoveredArtifact   (handoff)

Guarantees:

- **D1 — composition only.** The capability owns no discovery, selection,
  mapping, locator, download, persistence or presentation authority. It
  references existing authorities; it never duplicates or redefines them.
- **D2 — reuse of the existing discovery representations.** ``ModelCandidate``,
  ``ModelVariant`` and ``DiscoveredArtifact`` are returned **by identity**.
  There is no ``LibraryModel`` / ``LibraryVariant`` / ``LibraryArtifact`` /
  ``LibraryEntry`` hierarchy, no wrapper type and no parallel model domain.
- **D3 — candidate-first navigation.** ``search`` produces candidates; a
  candidate's own ``repository`` is the input to ``inspect``. No candidate is
  ever reconstructed and ``variant.candidate`` is never replaced.
- **D4 — pass-through, not interpretation.** ``query``, ``limit`` and
  ``cursor`` are forwarded unchanged; the provider's ``next_cursor`` is returned
  unchanged and is never decoded, validated, rebuilt or persisted. Provider
  candidate order is preserved exactly, duplicates are **not** collapsed,
  nothing is sorted, filtered, normalized or deduplicated. An empty search
  result is a completed call, not a failure.
- **D5 — B9.84 is the sole selection authority.** Selection is a thin
  delegation to ``castlearq.discovery_selection.select_discovered_artifact``.
  This module implements **no** selection rule of its own: no pre-filtering, no
  pre-sorting, no selector pre-validation, no fallback, no ambiguity
  resolution, no quantization / filename / revision matching, no ranking and no
  "best artifact" notion. The delegate is injectable only so that delegation is
  observable; the default is the B9.84 function itself.
- **D6 — acquisition handoff ends at the selected artifact.** The value that
  leaves this capability is the exact ``DiscoveredArtifact`` instance returned
  by B9.84. No ``ArtifactSpec`` is constructed, no identity is resolved, and
  this module imports neither ``models``, ``acquisition_mapping``,
  ``acquisition_service``, ``downloads.*`` nor ``model_store``. B9.82 mapping,
  B9.85 orchestration and B9.90 locator authority remain untouched.
- **D7 — transient identity only.** ``provider_id``, ``repository``,
  ``declared_quantization``, ``filename`` and ``revision`` are used exactly as
  discovery supplies them. No persistent library identity, no grouping key that
  outlives a call, no identity normalization and no identity registry.
- **D8 — revision is provenance + selection metadata.** It is transported and
  may be selected on, unchanged. It is never normalized, broadened, persisted
  or turned into identity. B9.90 remains the acquisition locator authority.
- **D9 — declared / unverified metadata.** Every field reaching a caller is L1
  provider-declared metadata. It is never renamed, defaulted, promoted to a
  verified fact or otherwise reinterpreted. ``"Unknown"`` quantization and
  ``"Unknown"`` format remain valid declared values. No quality, ranking or
  recommendation semantics are introduced.
- **D10 — no ``model_domain`` dependency.** The L1 discovery representation is
  not the compatibility / evaluation representation; no conversion or third
  representation is performed here.
- **D11 — acquirability is unspecified in B9.91.** All discovered entries stay
  visible regardless of acquisition mapping availability, and the capability
  exposes **no** acquisition status at all: no acquirability field, no
  ``is_acquirable`` query, no acquirability resolver, no ``model_identity``
  import, no inference of acquisition availability and no fabricated logical
  model ID. ``discoverability != acquirability``.
- **D12 — live / stateless / per-invocation.** Collaborators are injected and
  held only as references. No last query, cursor, candidate, variant or selected
  artifact is retained; no cache, memoization or module-level mutable state
  exists. Two consecutive calls are fully independent.
- **D13 — internal, no presentation.** Nothing here renders, prints, routes or
  serializes. There is no CLI command, no HTTP endpoint, no GUI and no
  marketplace. The capability is not exported from ``castlearq/__init__.py``.
- **D14 — a minimal application-level error boundary.** Exactly two stable
  categories describe what this boundary could not do; they describe *this*
  capability and deliberately do not share B9.85's acquisition vocabulary nor
  B9.86's cursor vocabulary. ``DiscoveryError`` and ``DiscoveredSelectionError``
  are translated while preserving the original exception on ``cause`` and
  chaining it as the Python exception cause. Programming errors that indicate
  caller-contract violations are deliberately **not** wrapped and propagate
  unchanged as ``TypeError`` / ``ValueError``. No exception hierarchy is
  introduced and neither translated type is subclassed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from .discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelDiscovery,
    ModelVariant,
)
from .discovery_selection import (
    DiscoveredSelectionError,
    select_discovered_artifact,
)

__all__ = [
    "DynamicModelLibrary",
    "DynamicModelLibraryError",
    "DynamicModelLibraryErrorCategory",
    "DynamicModelLibraryQueryOutcome",
    "DynamicModelLibrarySelectionOutcome",
]


class DynamicModelLibraryErrorCategory(str, Enum):
    """Stable, application-facing failure categories for this boundary.

    These describe *what the Dynamic Model Library capability could not do*,
    not which lower-level exception happened to be raised. They are
    deliberately NOT the B9.85 acquisition categories (this boundary performs
    no acquisition) and deliberately NOT the B9.86 query categories (this
    boundary owns no cursor vocabulary and never re-validates a cursor).

    ``DISCOVERY_FAILED`` covers the provider, transport and remote-metadata
    failures the discovery layer reports as ``DiscoveryError``.
    ``SELECTION_FAILED`` covers the deterministic selection failures the B9.84
    boundary reports as ``DiscoveredSelectionError``.
    """

    DISCOVERY_FAILED = "discovery_failed"
    SELECTION_FAILED = "selection_failed"


class DynamicModelLibraryError(Exception):
    """Application-level library failure with a preserved cause.

    Discovery-layer and selection-layer failures are translated here so that a
    future adapter never has to import ``DiscoveryError``,
    ``DiscoveredSelectionError`` or any other discovery-module type. The
    original exception is kept on ``DynamicModelLibraryError.cause`` and is also
    chained as the Python exception cause, so no diagnostic information is
    lost.

    Programming errors that are unrelated to this capability's flow (for
    example a non-``ModelDiscovery`` collaborator or a wrongly typed candidate
    collection) are deliberately not wrapped: they propagate unchanged as
    ``TypeError`` and ``ValueError``, because they are caller-contract
    violations rather than expected operational failures.
    """

    def __init__(
        self,
        category: DynamicModelLibraryErrorCategory,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


@dataclass(frozen=True)
class DynamicModelLibraryQueryOutcome:
    """The application-level result of one candidate-first search.

    ``candidates`` are the provider's own ``ModelCandidate`` objects, passed
    through by identity, so declared L1 remote metadata is preserved losslessly
    and the provider's order is preserved exactly — including any duplicates.
    ``next_cursor`` is the provider's opaque cursor returned unchanged; no
    ``total``, ``rank``, ``score`` or recommendation is derived here, because
    the provider deliberately does not expose them and inventing them would be
    interpretation rather than exposure.
    """

    candidates: tuple[ModelCandidate, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class DynamicModelLibrarySelectionOutcome:
    """The application-level result of one selection handoff.

    ``selected`` is the exact ``DiscoveredArtifact`` instance returned by the
    B9.84 selection boundary, never a copy, a mapping or a wrapper. The
    capability ends here: producing an ``ArtifactSpec``, resolving identity and
    acquiring the artifact remain the responsibility of the existing B9.82,
    B9.85 and B9.90 boundaries.
    """

    selected: DiscoveredArtifact


SelectionDelegate = Callable[..., DiscoveredArtifact]


def _need_candidate(value: object, name: str) -> ModelCandidate:
    if not isinstance(value, ModelCandidate):
        raise TypeError(f"{name} must be a ModelCandidate")
    return value


def _iter_variants(value: object) -> tuple[ModelVariant, ...]:
    if isinstance(value, ModelVariant):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        collected = tuple(value)
        for variant in collected:
            if not isinstance(variant, ModelVariant):
                raise TypeError("variants must contain ModelVariant only")
        return collected
    raise TypeError("variants must be a ModelVariant or an iterable of them")


class DynamicModelLibrary:
    """Internal, live and stateless model-oriented capability over discovery.

    Every collaborator is injected at the composition root. This class builds
    nothing, caches nothing and stores no per-call state: each call is one
    discovery round-trip (or one selection delegation) and nothing survives the
    call. It holds no identity knowledge, performs no acquisition, no
    persistence and no presentation, and it is independent of
    ``ModelAcquisitionService`` and of the B9.86 query boundary.
    """

    def __init__(
        self,
        discovery_provider: ModelDiscovery,
        *,
        selection_delegate: SelectionDelegate | None = None,
    ) -> None:
        if not hasattr(discovery_provider, "search") or not hasattr(
            discovery_provider, "inspect"
        ):
            raise TypeError("discovery_provider must implement ModelDiscovery")
        self.discovery_provider = discovery_provider
        # Injectable so that delegation to B9.84 is observable. The default IS
        # the B9.84 function; no alternative selection algorithm exists here.
        self.selection_delegate: SelectionDelegate = (
            selection_delegate
            if selection_delegate is not None
            else select_discovered_artifact
        )

    # -- public use cases ----------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> DynamicModelLibraryQueryOutcome:
        """Search discovered models, candidate-first.

        ``query``, ``limit`` and ``cursor`` are forwarded to the discovery port
        unchanged and the provider's ``next_cursor`` is returned unchanged. The
        only work performed here is translating a ``DiscoveryError`` into a
        ``DynamicModelLibraryError`` with a stable application category while
        preserving the original cause.

        An empty result is a completed call, not a failure. Duplicate
        candidates are preserved and the provider's order is preserved exactly.
        """
        arguments: dict[str, object] = {}
        if limit is not None:
            # Forwarded only when supplied: the boundary owns no default of its
            # own and passing None through would replace a declared provider
            # default with an invalid value.
            arguments["limit"] = limit
        try:
            candidates, next_cursor = self.discovery_provider.search(
                query, **arguments, cursor=cursor
            )
        except DiscoveryError as error:
            raise DynamicModelLibraryError(
                DynamicModelLibraryErrorCategory.DISCOVERY_FAILED,
                f"model discovery search failed: {error}",
                cause=error,
            ) from error

        return DynamicModelLibraryQueryOutcome(
            candidates=tuple(candidates),
            next_cursor=next_cursor,
        )

    def inspect(self, candidate: ModelCandidate) -> tuple[ModelVariant, ...]:
        """Inspect one discovered candidate and return its declared variants.

        The candidate's own ``repository`` is the only value taken from it; no
        field is derived, rewritten or reconstructed. The returned
        ``ModelVariant`` objects are the provider's own instances, with their
        own ``candidate`` and their provider-defined ordering untouched. No
        candidate is reconstructed and no grouping is re-derived.
        """
        repository = _need_candidate(candidate, "candidate").repository
        try:
            variants = self.discovery_provider.inspect(repository)
        except DiscoveryError as error:
            raise DynamicModelLibraryError(
                DynamicModelLibraryErrorCategory.DISCOVERY_FAILED,
                f"model discovery inspection failed: {error}",
                cause=error,
            ) from error
        return tuple(variants)

    def select(
        self,
        variants: ModelVariant | Iterable[ModelVariant],
        *,
        quantization: str | None = None,
        filename: str | None = None,
        revision: str | None = None,
    ) -> DynamicModelLibrarySelectionOutcome:
        """Delegate deterministic selection to the B9.84 authority.

        ``variants`` is the already-discovered ``ModelVariant[]`` domain. The
        selectors are passed straight through: this module validates nothing,
        filters nothing and sorts nothing, so B9.84's semantics — including its
        exact matching rules and its ambiguity-as-failure contract — remain the
        sole authority.

        The value returned to the caller is the exact ``DiscoveredArtifact``
        instance B9.84 selected; nothing is copied, mapped or wrapped.
        """
        discovered = _iter_variants(variants)
        try:
            selected = self.selection_delegate(
                discovered,
                quantization=quantization,
                filename=filename,
                revision=revision,
            )
        except DiscoveredSelectionError as error:
            raise DynamicModelLibraryError(
                DynamicModelLibraryErrorCategory.SELECTION_FAILED,
                f"deterministic artifact selection failed: {error}",
                cause=error,
            ) from error
        return DynamicModelLibrarySelectionOutcome(selected=selected)
