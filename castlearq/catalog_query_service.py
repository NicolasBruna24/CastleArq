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

"""B9.86: application catalog / query boundary (use case) and its result contract.

This module is the application boundary allocated by B9.86 (roadmap register,
section 25). It is the application-level consumer of the **search** side of the
B9.80 ``ModelDiscovery`` port, complementing the **inspect** side consumed by the
B9.85 ``ModelAcquisitionService``:

    ModelDiscovery.search(query, *, limit, cursor)
        -> ModelCatalogQueryService.query(...)
        -> CatalogQueryOutcome(candidates, next_cursor)

The two boundaries are independent consumers of the same domain port:

    ModelDiscovery  -->  B9.86 catalog / query boundary   (this module)
    ModelDiscovery  -->  B9.85 acquisition discovery path (ModelAcquisitionService)

The approved architectural decisions govern this module:

- **D1** this boundary is an application layer DISTINCT from Model Library UX.
  It exposes discovery capability; it does not become a product surface.
- **D2** its negative scope is fixed by the allocation: no presentation, no
  transport, no persistence, no ranking, no identity resolution, no selection,
  no acquisition, no cache.

The load-bearing invariant, recorded in section 25.5 of the roadmap register:

    Application boundary != Model Library UX

Guarantees:

- **Pass-through, not interpretation.** ``query``, ``limit`` and ``cursor`` are
  forwarded to the discovery provider unchanged, and ``next_cursor`` is returned
  unchanged. This boundary validates nothing: B9.81 owns cursor encoding and
  decoding, and the provider owns the limit bound. Duplicating either here would
  make this module a second validation authority.
- **Lossless candidates.** Candidate objects are passed through by identity.
  No field is added, renamed, defaulted, derived, normalized or reinterpreted,
  and the provider's order is preserved exactly as returned.
- **No product semantics.** No ranking, recommendation, fuzzy matching,
  normalization, query rewriting, sorting, deduplication or caching.
- **One round-trip.** ``search()`` is invoked exactly once per ``query()`` call.
- **No printing.** Presentation belongs to a future authorized adapter.

Importantly, this module imports only the discovery **port**. It never imports a
concrete provider; the provider is injected by ``application_wiring``, exactly as
``ModelAcquisitionService`` receives its collaborators.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .discovery import DiscoveryError, ModelCandidate, ModelDiscovery

__all__ = [
    "CatalogQueryError",
    "CatalogQueryErrorCategory",
    "CatalogQueryOutcome",
    "ModelCatalogQueryService",
]


class CatalogQueryErrorCategory(str, Enum):
    """Stable, application-facing failure categories for the query boundary.

    These describe *what the application boundary could not do*, not which
    lower-level exception happened to be raised. They are deliberately NOT the
    B9.85 acquisition categories: catalog query and acquisition fail for
    different reasons and must not share a vocabulary.

    ``DISCOVERY_FAILED`` covers the transport, response-shape and remote
    metadata failures the discovery layer reports as ``DiscoveryError``.
    ``INVALID_CURSOR`` is reserved for a cursor the provider refuses as
    malformed. The provider stays authoritative for that decision; the
    application boundary only reports it under a stable application category.
    """

    DISCOVERY_FAILED = "discovery_failed"
    INVALID_CURSOR = "invalid_cursor"


class CatalogQueryError(Exception):
    """Application-level query failure with a preserved cause.

    Discovery-layer failures are translated here so that a future adapter never
    has to import ``DiscoveryError`` or any other discovery-module type. The
    original exception is kept on ``CatalogQueryError.cause`` and is also
    chained as the Python exception cause, so no diagnostic information is lost.

    Programming errors unrelated to the query flow (for example a non-string
    ``query`` or an out-of-range ``limit`` raised by the provider) are
    deliberately not wrapped: they propagate unchanged as ``TypeError`` and
    ``ValueError``, because they are caller-contract violations rather than
    expected operational failures.
    """

    def __init__(
        self,
        category: CatalogQueryErrorCategory,
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
class CatalogQueryOutcome:
    """The application-level catalog query result.

    Two fields, mapped one-to-one onto what ``ModelDiscovery.search()``
    returns. No ``total``, ``has_next``, ``page``, ``offset``, ``rank``,
    ``score`` or recommendation is derived here: the provider's cursor is opaque
    and deliberately does not expose them, and inventing them would be
    interpretation rather than exposure.

    Candidates are the provider's own ``ModelCandidate`` objects, passed through
    by identity, so the declared L1 remote metadata is preserved losslessly.
    """

    candidates: tuple[ModelCandidate, ...]
    next_cursor: str | None


class ModelCatalogQueryService:
    """Query remote model candidates through the B9.80 discovery port.

    Every collaborator is injected at the composition root; this class builds
    nothing and caches nothing. It holds no identity knowledge, performs no
    selection, no ranking and no persistence, and is independent of
    ``ModelAcquisitionService``.
    """

    def __init__(self, discovery_provider: ModelDiscovery) -> None:
        self.discovery_provider = discovery_provider

    # -- public use case ----------------------------------------------------

    def query(
        self,
        query,
        *,
        limit=20,
        cursor=None,
    ) -> CatalogQueryOutcome:
        """Query the discovery port once and return an application result.

        ``query``, ``limit`` and ``cursor`` are forwarded unchanged and
        ``next_cursor`` is returned unchanged. The only work performed here is
        translating a ``DiscoveryError`` into a ``CatalogQueryError`` with a
        stable application category while preserving the original cause.
        """
        try:
            candidates, next_cursor = self.discovery_provider.search(
                query,
                limit=limit,
                cursor=cursor,
            )
        except DiscoveryError as error:
            raise CatalogQueryError(
                self._category(error),
                str(error),
                cause=error,
            ) from error

        return CatalogQueryOutcome(
            candidates=tuple(candidates),
            next_cursor=next_cursor,
        )

    # -- internal steps -----------------------------------------------------

    @staticmethod
    def _category(error: DiscoveryError) -> CatalogQueryErrorCategory:
        """Map a discovery failure onto a stable application category.

        The provider owns cursor validity; a refused cursor is reported as
        ``INVALID_CURSOR`` and every other discovery failure as
        ``DISCOVERY_FAILED``. This is a classification of an already-known
        domain failure, never a second validation pass.
        """
        if "cursor" in str(error).lower():
            return CatalogQueryErrorCategory.INVALID_CURSOR
        return CatalogQueryErrorCategory.DISCOVERY_FAILED
