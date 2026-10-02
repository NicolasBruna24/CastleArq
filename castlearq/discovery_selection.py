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

"""B9.84: Discovery-domain deterministic artifact selection boundary.

This module is the selection boundary declared by B9.84 (roadmap register,
sections 20 and 21). It selects **exactly one** already-discovered
``DiscoveredArtifact`` from the B9.80 ``ModelVariant[]`` domain using explicit,
deterministic, non-heuristic criteria, and it sits strictly *upstream* of the
B9.82 acquisition mapper:

    Discovery -> B9.84 selection -> B9.82 mapping -> Acquisition

The human architectural decisions recorded in section 20 govern this module:

- **D1** the input domain is ``ModelVariant[]``. The model -> variant ->
  artifact hierarchy established by B9.80/B9.81 is consumed as-is. Variants
  are never reconstructed and quantization grouping is never re-derived.
- **D2** selection happens here, before B9.82. B9.82 stays a pure 1:1
  translator and never receives alternatives it would have to discard.
- **D3** ``revision`` is a first-class, explicit selection criterion. It is
  declared remote provenance (L1) and never content identity, never
  ``artifact_id`` and never verified content. B9.83 OD-1 is preserved: this
  module neither computes nor influences any identity.
- **D4** this is a *separate* discovery-domain contract. The existing
  acquisition-domain selector (``castlearq.artifact_selection``,
  ``select_artifact``/``ArtifactSelectionError``) is deliberately untouched and
  is neither imported, subclassed nor refactored into a shared abstraction.
  The selector validation below restates the established semantics
  independently.
- **D5** identity is the responsibility of the B9.82 caller. No identity
  resolver is accepted, and ``model_id`` is never read, resolved, fabricated or
  mutated.
- **D6** selection is exactly one result or an explicit failure. There is no
  ranking, scoring, recommendation, fuzzy matching or incidental-order choice:
  if more than one artifact satisfies the criteria, that is an ambiguity
  failure, not a hint to take the first one.
- **D7** this boundary owns a dedicated error. It is independent from
  ``ArtifactSelectionError`` (acquisition domain) and from ``DiscoveryError``
  (discovery/provider failures).
- **D8** an empty candidate collection is an explicit selection failure and
  stays distinguishable from a populated collection that simply matches
  nothing.

Guarantees (recorded as invariants, not aspirations):

- **Pure.** No network access, no persistence, no filesystem access, no
  identity resolution, no ranking. The only inputs are the supplied variants
  and the supplied selectors; the only result is an existing discovered object.
- **Deterministic.** The outcome is a pure function of the candidate set and
  the criteria, and is independent of the incidental ordering of the input.
- **Non-mutating.** Variants and artifacts are frozen dataclasses and are
  returned exactly as discovered. The selected artifact is the *original*
  ``DiscoveredArtifact``, never a derived copy.

The four failure categories -- empty candidates, no match, ambiguity and
invalid selector -- are all reported as ``DiscoveredSelectionError`` with
deterministic, descriptive and mutually distinguishable messages. Programming
errors keep their natural ``TypeError``/``ValueError`` and are deliberately not
wrapped, matching the convention established at the B9.82 boundary.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from .discovery import DiscoveredArtifact, ModelVariant

__all__ = ["DiscoveredSelectionError", "select_discovered_artifact"]


class DiscoveredSelectionError(Exception):
    """Raised when deterministic discovery-domain selection cannot complete.

    This is the B9.84 selection-boundary error (D7). It is intentionally
    independent from ``castlearq.artifact_selection.ArtifactSelectionError``,
    which belongs to the acquisition-domain selector, and from
    ``castlearq.discovery.DiscoveryError``, which represents discovery and
    provider failures. Neither is reused or subclassed.

    The failure category is always recoverable from the message: an empty
    candidate set, no match, an ambiguous match, or an invalid selector are
    four distinguishable conditions (D6, D8).
    """


def _validate_selector_filename(filename: str) -> str:
    """Validate and return an exact filename selector.

    Restates the established acquisition-domain selector semantics
    independently (D4): the value must be a safe, single, plain path segment.
    It is never interpreted as a path, never normalized into one, and never
    matched partially.
    """
    if not isinstance(filename, str):
        raise DiscoveredSelectionError("Filename selector must be a string")
    filename = filename.strip()
    if not filename:
        raise DiscoveredSelectionError("Filename selector must not be empty")

    path = PurePosixPath(filename)
    if (
        path.is_absolute()
        or filename in {".", ".."}
        or "\\" in filename
        or "/" in filename
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise DiscoveredSelectionError(
            f"Unsafe or invalid filename selector: {filename!r}"
        )
    return filename


def _validate_selector_quantization(quantization: str) -> str:
    """Validate and return a quantization selector, without normalizing it."""
    if not isinstance(quantization, str):
        raise DiscoveredSelectionError("Quantization selector must be a string")
    cleaned = quantization.strip()
    if not cleaned:
        raise DiscoveredSelectionError("Quantization selector must not be empty")
    return cleaned


def _validate_selector_revision(revision: str) -> str:
    """Validate a revision selector without altering the declared revision.

    D3 is a *selection* affordance only. The selector is compared verbatim
    against the declared value: no case folding, no prefix matching and no
    substitution of ``"main"`` is performed here.
    """
    if not isinstance(revision, str):
        raise DiscoveredSelectionError("Revision selector must be a string")
    if not revision.strip():
        raise DiscoveredSelectionError("Revision selector must not be empty")
    return revision


def _iter_discovered(
    variants: Iterable[ModelVariant],
) -> tuple[DiscoveredArtifact, ...]:
    """Flatten the artifacts already contained in the supplied variants.

    The declared B9.80/B9.81 hierarchy is consumed as-is: variants are never
    rebuilt, artifacts are never regrouped, and no discovery data is altered.
    The returned tuple is ordered exactly as supplied; because selection never
    depends on position (D6), the order carries no selection semantics.
    """
    if isinstance(
        variants, (str, bytes, bytearray, ModelVariant, DiscoveredArtifact)
    ):
        raise TypeError("variants must be an iterable of ModelVariant")

    discovered: list[DiscoveredArtifact] = []
    for variant in variants:
        if not isinstance(variant, ModelVariant):
            raise TypeError("every variant must be a ModelVariant")
        discovered.extend(variant.artifacts)
    return tuple(discovered)


def select_discovered_artifact(
    variants: Iterable[ModelVariant],
    *,
    quantization: str | None = None,
    filename: str | None = None,
    revision: str | None = None,
) -> DiscoveredArtifact:
    """Select exactly one discovered artifact using explicit, deterministic rules.

    ``variants`` is the already-discovered ``ModelVariant[]`` domain (D1). The
    artifacts it contains are the only candidates. No variant is reconstructed
    and no grouping is re-derived.

    Selectors are optional, keyword-only, and combine cumulatively with logical
    AND. Each selector is explicit and non-heuristic:

    - ``quantization`` matches ``DiscoveredArtifact.declared_quantization``
      exactly, case-insensitively. It is never matched partially.
    - ``filename`` matches ``DiscoveredArtifact.filename`` exactly,
      case-sensitively. It is never matched partially, and unsafe or
      path-like selectors are rejected as invalid selectors.
    - ``revision`` matches ``DiscoveredArtifact.revision`` exactly and verbatim.

    ``revision`` is declared remote provenance (L1). It is not content
    identity, not ``artifact_id``, and not verified content; selecting by it
    changes no identity and mutates nothing (D3, B9.83 OD-1). An absent
    revision stays ``None``: it is never invented and never defaulted to
    ``"main"``.

    The outcome is independent of the incidental ordering of ``variants`` and
    of the artifacts within them (D6). Behavior:

    - no candidates at all -> ``DiscoveredSelectionError`` (empty candidates);
    - no artifact satisfies the criteria -> ``DiscoveredSelectionError``
      (no match);
    - more than one artifact satisfies the criteria ->
      ``DiscoveredSelectionError`` (ambiguity). Selection never falls back to
      the first, last, largest, smallest, preferred, best or latest match;
    - exactly one artifact satisfies the criteria -> that artifact is
      returned, as the original object, unchanged.
With no selector at all, a single candidate is selected and anything else
    fails; ambiguity is a failure, never an implicit "best" choice.

    This function performs no network access, no persistence, no filesystem
    access and no identity resolution. It accepts no identity resolver, and
    ``model_id`` is never read, resolved, fabricated or mutated (D5).

    It raises ``DiscoveredSelectionError`` for the four selection-boundary
    failures (empty candidates, no match, ambiguity, invalid selector) and
    leaves programming errors such as a non-iterable or wrongly typed
    ``variants`` as the natural ``TypeError``.
    """
    norm_quant: str | None = None
    if quantization is not None:
        norm_quant = _validate_selector_quantization(quantization)

    norm_filename: str | None = None
    if filename is not None:
        norm_filename = _validate_selector_filename(filename)

    norm_revision: str | None = None
    if revision is not None:
        norm_revision = _validate_selector_revision(revision)

    candidates = _iter_discovered(variants)

    has_selector = (
        norm_quant is not None
        or norm_filename is not None
        or norm_revision is not None
    )

    # D8: an empty candidate collection is its own explicit failure, kept
    # distinct from a populated collection that matches nothing.
    if not candidates:
        raise DiscoveredSelectionError("No discovered GGUF artifacts found")

    matched = candidates

    if norm_quant is not None:
        matched = tuple(
            a
            for a in matched
            if isinstance(a.declared_quantization, str)
            and a.declared_quantization.upper() == norm_quant.upper()
        )
        if not matched:
            raise DiscoveredSelectionError(
                f"No discovered artifact matches quantization {quantization!r}"
            )

    if norm_filename is not None:
        matched = tuple(a for a in matched if a.filename == norm_filename)
        if not matched:
            if norm_quant is not None:
                raise DiscoveredSelectionError(
                    f"No discovered artifact matches both quantization "
                    f"{quantization!r} and filename {filename!r}"
                )
            raise DiscoveredSelectionError(
                f"No discovered artifact matches filename {filename!r}"
            )

    if norm_revision is not None:
        matched = tuple(a for a in matched if a.revision == norm_revision)
        if not matched:
            raise DiscoveredSelectionError(
                f"No discovered artifact matches revision {revision!r}"
            )

    # D6: cardinality is a hard contract, and it is order-independent.
    if not has_selector:
        if len(matched) == 1:
            return matched[0]
        raise DiscoveredSelectionError(
            "Model maps to multiple discovered artifacts; specify quantization, "
            "filename or revision"
        )

    if len(matched) == 1:
        return matched[0]

    filenames = sorted(a.filename for a in matched)
    detail = ", ".join(repr(name) for name in filenames)
    raise DiscoveredSelectionError(
        f"Multiple discovered artifacts match the given criteria ({detail}); "
        "refine the selection to identify exactly one"
    )

    matched = candidates

    if norm_quant is not None:
        matched = tuple(
            a
            for a in matched
            if isinstance(a.declared_quantization, str)
            and a.declared_quantization.upper() == norm_quant.upper()
        )
        if not matched:
            raise DiscoveredSelectionError(
                f"No discovered artifact matches quantization {quantization!r}"
            )
