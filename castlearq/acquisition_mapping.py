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

"""B9.82: discovery-to-acquisition mapping boundary.

This module is a pure translation boundary declared by B9.82 (roadmap section
18). It converts the declared L1 output of the B9.80 discovery domain into
``ArtifactSpec`` values that the existing acquisition infrastructure already
consumes. It performs no acquisition, planning, download, persistence or
verification, and it imports only ``castlearq.discovery`` and
``castlearq.models``.

Contract (section 18.5):

- ``identity_resolver`` is a REQUIRED keyword-only callable with no default.
  It is called as ``identity_resolver(repository)`` and must return the
  catalog identity for that repository, or ``None`` when no identity exists.
  This mirrors the injectable ``model_id_provider`` of ``HuggingFaceSource``.
  This module never imports ``castlearq.model_identity`` and never resolves an
  identity on the caller's behalf: identity resolution is the caller's policy.
- A missing, non-string or unsafe identity raises ``AcquisitionMappingError``.
  No identity is ever fabricated: neither ``None`` nor ``"Unknown"`` is
  produced.
- Programming errors (a non-callable resolver, an unsupported input shape, a
  non-``DiscoveredArtifact`` element) keep their natural ``TypeError``.
- ``DiscoveredArtifact.revision`` is transported verbatim by B9.83. B9.82
  discarded it as a recorded decision (decision 2); B9.83 supersedes that
  boundary behaviour prospectively. The value stays *declared* metadata: it
  is never converted into ``content_id`` or ``sha256``, it never becomes a
  verified claim, and by the OD-1 human architectural decision recorded in
  the roadmap register (19.7) it does **not** participate in
  ``ArtifactSpec.artifact_id``. An absent revision stays ``None``; it is
  never fabricated and never defaulted to ``"main"``.
- Everything else is preserved exactly as declared: ``declared_quantization``,
  ``declared_size`` and ``declared_sha256`` keep their values and their
  declared meaning. ``sha256`` remains an integrity *declaration*, distinct
  from ``content_id``, which this boundary always leaves as ``None``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import PurePosixPath

from .discovery import DiscoveredArtifact, ModelVariant
from .models import ArtifactSpec, ArtifactState

__all__ = ["AcquisitionMappingError", "map_discovered_artifacts"]

IdentityResolver = Callable[[str], "str | None"]
MappingInput = ModelVariant | Iterable[DiscoveredArtifact]


class AcquisitionMappingError(Exception):
    """Declared failure at the discovery-to-acquisition boundary.

    Raised only for boundary data conditions, chiefly an identity the
    caller-supplied resolver cannot supply. It is independent from
    ``DiscoveryError`` and ``SourceError``; programming errors keep their
    natural ``TypeError``/``ValueError``.
    """


def map_discovered_artifacts(
    artifacts: MappingInput,
    *,
    identity_resolver: IdentityResolver,
) -> tuple[ArtifactSpec, ...]:
    """Translate discovered artifacts into acquisition ``ArtifactSpec`` values.

    ``artifacts`` is either a ``ModelVariant`` or an iterable of
    ``DiscoveredArtifact``. Exactly one ``ArtifactSpec`` is produced per
    artifact, in input order. No network, filesystem, persistence, planning or
    verification is involved, and the result is deterministic.
    """
    if not callable(identity_resolver):
        raise TypeError("identity_resolver must be callable")
    return tuple(
        _map_artifact(artifact, identity_resolver)
        for artifact in _as_discovered(artifacts)
    )


def _as_discovered(artifacts: MappingInput) -> tuple[DiscoveredArtifact, ...]:
    """Normalize the two accepted input shapes into a tuple of artifacts."""
    if isinstance(artifacts, ModelVariant):
        candidates: Iterable[object] = artifacts.artifacts
    elif isinstance(artifacts, (str, bytes, bytearray)):
        raise TypeError(
            "artifacts must be a ModelVariant or an iterable of "
            "DiscoveredArtifact"
        )
    else:
        try:
            candidates = tuple(artifacts)
        except TypeError as error:
            raise TypeError(
                "artifacts must be a ModelVariant or an iterable of "
                "DiscoveredArtifact"
            ) from error
    for candidate in candidates:
        if not isinstance(candidate, DiscoveredArtifact):
            raise TypeError("every artifact must be a DiscoveredArtifact")
    return tuple(candidates)  # type: ignore[return-value]


def _map_artifact(
    artifact: DiscoveredArtifact,
    identity_resolver: IdentityResolver,
) -> ArtifactSpec:
    return ArtifactSpec(
        model_id=_resolve_identity(artifact, identity_resolver),
        source=artifact.source,
        repository=artifact.repository,
        filename=artifact.filename,
        format=artifact.format,
        # Declared quantization keeps its value and its declared meaning; it is
        # never promoted to a verified claim.
        quantization=artifact.declared_quantization,
        # Declared download locator. It is metadata, never fetched here.
        download_url=artifact.download_url,
        size_bytes=artifact.declared_size,
        # Integrity declaration, kept as declared; never computed here.
        sha256=artifact.declared_sha256,
        # B9.83 supersedes B9.82 decision 2 prospectively: the declared
        # revision is now transported verbatim instead of discarded. It is
        # declared provenance metadata, NOT content identity and NOT an
        # integrity proof, and by the OD-1 decision (roadmap register 19.7)
        # it does not participate in `artifact_id`. Absence stays `None`; it
        # is never fabricated and never defaulted to "main".
        revision=artifact.revision,
        state=ArtifactState.NOT_DOWNLOADED,
        # B9.67: content_id is a computed identity and is never available to
        # declared remote metadata.
        content_id=None,
    )


def _resolve_identity(
    artifact: DiscoveredArtifact,
    identity_resolver: IdentityResolver,
) -> str:
    """Return the caller-resolved identity, or fail explicitly.

    An absent, non-string or unsafe identity is a boundary data condition and
    raises ``AcquisitionMappingError``. No placeholder identity is ever
    substituted.
    """
    model_id = identity_resolver(artifact.repository)
    if not isinstance(model_id, str) or not _is_safe_identity(model_id):
        raise AcquisitionMappingError(
            "Identity could not be resolved for repository: "
            f"{artifact.repository}"
        )
    return model_id


def _is_safe_identity(value: str) -> bool:
    """Reject identities the store could not address safely.

    Mirrors the rejections of the store's ``_safe_model_id`` (empty, absolute
    or dot-segmented values) without importing the store: this module must
    stay free of it.
    """
    if not value.strip():
        return False
    if value in {".", ".."}:
        return False
    path = PurePosixPath(value)
    if path.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)