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

"""B9.85/B9.97: application acquisition boundary (use case) and its result contract.

This module is the application boundary allocated by B9.85 (roadmap register,
section 23). It owns the orchestration that used to live inside the CLI
``run_download`` function, and it is the first real production consumer of the
completed B9.80-B9.84 discovery chain:

    model_id
        -> locator resolver          (model_identity, injected)
        -> discovery_provider.inspect(repository)      B9.80/B9.81
        -> select_discovered_artifact(...)             B9.84
        -> map_discovered_artifacts(..., identity_resolver=...)   B9.82
        -> ArtifactSpec
        -> planner.plan(...) -> downloader.download(...) -> store.save_manifest(...)
        -> AcquisitionOutcome

B9.97 adds an independent revision channel (Option C — Independent Revision
Channel).  ``ArtifactSpec.revision`` is the concrete carrier. Revision never
enters ``model_id``/``artifact_id`` derivation, never lives in the acquisition
binding, and never alters the ``locator_resolver`` contract.

The approved architectural decisions govern this module:

- **D1/D2** it is a service class with injected collaborators, following the
  repository's own ``ModelExecutionService`` precedent. No global caching, no
  second dependency-injection mechanism and no service construction at import
  time: the composition root builds one service per use-case invocation.
- **D3** the service knows nothing about logical model identity. It receives an
  already-bound ``IdentityResolver = Callable[[str], str | None]`` and forwards
  it unchanged to B9.82. It never imports ``model_identity``, never sees a
  ``source`` value and never fabricates an identity.
- **D4** expected failures are translated into ``AcquisitionError`` with a
  stable application category while the original exception is preserved both
  as ``cause`` and as the Python exception cause.
- **D5** the legacy ``ModelSource`` architecture is untouched. This module
  neither imports nor removes it; coexistence is preserved.
- **D7** the application result is ``AcquisitionOutcome``: an application-level
  contract that never exposes ``Path`` objects, ``DownloadPlan`` or
  ``DownloadResult``.

Guarantees:

- **No printing.** Presentation belongs to the CLI adapter.
- **No ranking, scoring, recommendation or fuzzy matching.** Selection is the
  deterministic B9.84 contract, used unchanged.
- **One discovery round-trip.** Candidate information for an ambiguous or
  failed selection is derived from the artifacts already in hand, never from a
  second discovery request.
- **B9.80-B9.84 are consumed, not redesigned.**
- **B9.97 revision invariant.** Revision selects artifact state; it never
  identifies the model, never enters ``model_id``/``artifact_id`` derivation,
  never lives in the acquisition binding, and never alters the
  ``locator_resolver`` contract.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import Enum
import re

from .acquisition_mapping import AcquisitionMappingError, map_discovered_artifacts
from .discovery import DiscoveredArtifact, DiscoveryError, ModelDiscovery, ModelVariant
from .discovery_selection import DiscoveredSelectionError, select_discovered_artifact
from .downloads.downloader import Downloader
from .downloads.planner import DownloadPlan, DownloadPlanner, DownloadPlanStatus
from .model_store import ModelStore, UnsafePathError

__all__ = [
    "AcquisitionCandidate",
    "AcquisitionError",
    "AcquisitionErrorCategory",
    "AcquisitionOutcome",
    "AcquisitionStatus",
    "ModelAcquisitionService",
]

# B9.82's contract, restated for documentation only. The service forwards the
# injected callable unchanged and never widens or narrows this signature.
IdentityResolver = Callable[[str], "str | None"]

# The locator resolves a logical model id to its single (source, repository)
# pair, or None. It is injected so this module stays free of ``model_identity``.
LocatorResolver = Callable[[str], "tuple[str, str] | None"]


class AcquisitionErrorCategory(str, Enum):
    """Stable, application-facing failure categories (D4).

    These describe *what the application boundary could not do*, not which
    lower-level exception happened to be raised. The original exception is
    always preserved on ``AcquisitionError.cause``.
    """

    MODEL_NOT_RESOLVABLE = "model_not_resolvable"
    DISCOVERY_FAILED = "discovery_failed"
    SELECTION_FAILED = "selection_failed"
    MAPPING_FAILED = "mapping_failed"
    IDENTITY_UNRESOLVED = "identity_unresolved"
    PLANNING_FAILED = "planning_failed"
    TRANSFER_FAILED = "transfer_failed"
    PERSISTENCE_FAILED = "persistence_failed"


class AcquisitionError(Exception):
    """Application-level acquisition failure with a preserved cause (D4).

    Lower-level discovery, selection, mapping, planning, transfer and
    persistence exceptions are translated here so that CLI adapters never have
    to know six unrelated exception types. The original exception is kept on
    ``cause`` and is also chained as the Python exception cause, so no
    diagnostic information is lost.

    Programming errors that are unrelated to the acquisition flow (for example
    a non-callable collaborator) are deliberately not wrapped.
    """

    def __init__(
        self,
        category: AcquisitionErrorCategory,
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
        # Presentation data attached by the service when a selection fails. It
        # describes what discovery already found; it is never a ranking and it
        # never triggers a second discovery request.
        self.model_id: str = ""
        self.candidate_filenames: tuple[str, ...] = ()
        self.candidates: tuple[AcquisitionCandidate, ...] = ()
@dataclass(frozen=True)
class AcquisitionCandidate:
    """One declared discovery candidate offered to the caller for reference.

    This carries exactly the information the CLI already presented for an
    ambiguous or failed selection: filename, declared quantization, declared
    size and declared SHA-256. All of it is *declared* L1 metadata; it is never
    a verified claim and never an identity.

    It is populated only when the legacy behaviour would have listed
    candidates, that is, when no explicit selector was supplied.
    """

    filename: str
    quantization: str
    declared_size: int | None = None
    declared_sha256: str | None = None


class AcquisitionStatus(str, Enum):
    """The application acquisition outcome states (D7).

    ``READY``, ``BLOCKED`` and ``ALREADY_DOWNLOADED`` are normal application
    outcomes, not failures, and are never converted into exceptions.
    ``FAILED`` reports that the flow could not complete and carries the reason
    on ``AcquisitionOutcome.error`` / ``AcquisitionOutcome.message``.
    """

    READY = "ready"
    ALREADY_DOWNLOADED = "already_downloaded"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class AcquisitionOutcome:
    """The application-level acquisition result (D7).

    Filesystem paths are exposed as strings, never as ``Path`` objects, and no
    infrastructure type (``DownloadPlan``, ``DownloadResult``) is exposed: this
    is an application contract usable by any future adapter without depending
    on the acquisition infrastructure.
    """

    status: AcquisitionStatus
    model_id: str
    filename: str | None = None
    size_bytes: int | None = None
    destination: str | None = None
    reasons: tuple[str, ...] = ()
    message: str | None = None
    failure_status: str | None = None
    verified: bool | None = None
    bytes_downloaded: int | None = None
    manifest_path: str | None = None
    error: AcquisitionError | None = None
    candidate_filenames: tuple[str, ...] = ()
    candidates: tuple[AcquisitionCandidate, ...] = ()

    @property
    def succeeded(self) -> bool:
        """True when the artifact is available without any failure."""
        return self.status in {
            AcquisitionStatus.READY,
            AcquisitionStatus.ALREADY_DOWNLOADED,
        }

    @property
    def has_candidates(self) -> bool:
        """True when discovery data is available for presentation."""
        return bool(self.candidates)
def _as_text(value) -> str | None:
    """Expose a filesystem path as a string; no ``Path`` crosses the boundary."""
    return None if value is None else str(value)


def _candidate_infos(
    artifacts: Sequence[DiscoveredArtifact],
) -> tuple[AcquisitionCandidate, ...]:
    """Project already-discovered artifacts into presentation-safe candidates.

    This performs no discovery and no selection: it only reads data the service
    already holds, which is what keeps ambiguous selection to a single discovery
    round-trip. Ordering follows discovery order and is never a ranking.
    """
    return tuple(
        AcquisitionCandidate(
            filename=artifact.filename,
            quantization=artifact.declared_quantization,
            declared_size=artifact.declared_size,
            declared_sha256=artifact.declared_sha256,
        )
        for artifact in artifacts
    )


class ModelAcquisitionService:
    """Coordinate discovery, selection, mapping, planning and acquisition.

    Every collaborator is injected at the composition root; this class builds
    nothing and caches nothing. It holds no identity knowledge (D3): the
    ``identity_resolver`` it receives is already bound to the authoritative
    identity source and is forwarded to B9.82 unchanged.
    """

    def __init__(
        self,
        discovery_provider: ModelDiscovery,
        identity_resolver: IdentityResolver,
        locator_resolver: LocatorResolver,
        planner: DownloadPlanner,
        downloader: Downloader,
        store: ModelStore,
        locator_audit: Callable[[str], tuple[tuple[str, str], ...]] | None = None,
    ) -> None:
        self.discovery_provider = discovery_provider
        self.identity_resolver = identity_resolver
        self.locator_resolver = locator_resolver
        self.planner = planner
        self.downloader = downloader
        self.store = store
        self.locator_audit = locator_audit

    # -- public use case ----------------------------------------------------

    def acquire(
        self,
        model_id: str,
        *,
        quantization: str | None = None,
        filename: str | None = None,
        revision: str | None = None,
    ) -> AcquisitionOutcome:
        """Acquire exactly one artifact for a logical model id.

        Returns an ``AcquisitionOutcome`` for every expected outcome, including
        a refused or ambiguous selection. It raises only ``AcquisitionError``
        when the flow cannot be completed and no more specific outcome state
        applies.

        ``revision`` is an optional explicit caller-supplied Git commit hash
        (40 hex characters). When provided it takes authority over any revision
        discovered from the provider (B9.97 Option C — Independent Revision
        Channel). When ``None`` the existing behaviour is preserved and the
        revision is carried from discovery unchanged.

        Revision never enters ``model_id``/``artifact_id`` derivation, never
        lives in the acquisition binding, and never alters the
        ``locator_resolver`` contract.
        """
        # B9.97: validate explicit caller revision; fail closed on malformed input.
        if revision is not None and (
            not isinstance(revision, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}", revision)
        ):
            raise AcquisitionError(
                AcquisitionErrorCategory.PLANNING_FAILED,
                "Artifact revision must be a 40-character hexadecimal commit hash",
            )

        repository = self._resolve_repository(model_id)
        variants = self._discover(repository)
        discovered = tuple(
            artifact for variant in variants for artifact in variant.artifacts
        )

        selected = self._select(
            model_id,
            variants,
            discovered,
            quantization=quantization,
            filename=filename,
            revision=revision,
        )

        spec = self._map(model_id, selected, caller_revision=revision)
        return self._plan_and_acquire(model_id, spec)

    # -- internal steps -----------------------------------------------------

    def _resolve_repository(self, model_id: str) -> str:
        locator = self.locator_resolver(model_id)
        if locator is None:
            # Distinguish "mapped but not downloadable" from "not mapped at
            # all", exactly as the CLI reported before B9.85.
            locators: tuple[tuple[str, str], ...] = ()
            if self.locator_audit is not None:
                locators = tuple(self.locator_audit(model_id))
            if len(locators) == 1:
                raise AcquisitionError(
                    AcquisitionErrorCategory.MODEL_NOT_RESOLVABLE,
                    f"unsupported source: {locators[0][0]}",
                )
            raise AcquisitionError(
                AcquisitionErrorCategory.MODEL_NOT_RESOLVABLE,
                f"no unique source repository is mapped to model: {model_id}",
            )
        _, repository = locator
        return repository

    def _discover(self, repository: str) -> tuple[ModelVariant, ...]:
        try:
            return tuple(self.discovery_provider.inspect(repository))
        except DiscoveryError as error:
            raise AcquisitionError(
                AcquisitionErrorCategory.DISCOVERY_FAILED,
                str(error),
                cause=error,
            ) from error

    def _select(
        self,
        model_id: str,
        variants: tuple[ModelVariant, ...],
        discovered: tuple[DiscoveredArtifact, ...],
        *,
        quantization: str | None,
        filename: str | None,
        revision: str | None,
    ) -> DiscoveredArtifact:
        """Run the deterministic B9.84 selection over already-known variants.

        Candidate presentation data is retained *before* selection and attached
        to the failure only when no explicit selector was supplied, which is
        exactly when the legacy CLI listed candidates. No second discovery
        request is made, and ``DiscoveredSelectionError`` is never modified.

        B9.97: ``revision`` is forwarded to ``select_discovered_artifact`` so
        that the selection layer can filter on revision when a caller explicitly
        supplies one.  Revision never enters identity derivation here.
        """
        try:
            return select_discovered_artifact(
                variants,
                quantization=quantization,
                filename=filename,
                revision=revision,
            )
        except DiscoveredSelectionError as error:
            failure = AcquisitionError(
                AcquisitionErrorCategory.SELECTION_FAILED,
                str(error),
                cause=error,
            )
            failure.model_id = model_id
            failure.candidate_filenames = tuple(
                artifact.filename for artifact in discovered
            )
            # Presentation data is attached only when the legacy behaviour
            # would have listed candidates (no explicit selector of any kind).
            failure.candidates = (
                _candidate_infos(discovered)
                if quantization is None and filename is None and revision is None
                else ()
            )
            raise failure from error

    def _map(
        self,
        model_id: str,
        selected: DiscoveredArtifact,
        *,
        caller_revision: str | None = None,
    ):
        """Map the selected artifact and assert the requested identity.

        ``identity_resolver`` is forwarded unchanged, so B9.82 remains the only
        place identity is injected. B9.83 revision transport and OD-1 are
        unaffected: this layer never computes ``artifact_id``.

        A discovery provider that declares its own ``model_id`` is still held to
        the requested identity: a declared identity that contradicts the
        request is refused rather than silently re-resolved.

        B9.97: when ``caller_revision`` is not ``None`` it is applied to the
        mapped spec via ``dataclasses.replace`` after mapping, so the explicit
        caller revision takes authority over any revision the discovery provider
        declared.  Only ``spec.revision`` is mutated; ``model_id`` and
        ``artifact_id`` are untouched, preserving the protected invariant.
        """
        if selected.model_id is not None and selected.model_id != model_id:
            raise AcquisitionError(
                AcquisitionErrorCategory.IDENTITY_UNRESOLVED,
                f"discovered artifact model_id {selected.model_id!r} does not "
                f"match {model_id!r}",
            )

        try:
            mapped = map_discovered_artifacts(
                [selected],
                identity_resolver=self.identity_resolver,
            )
        except AcquisitionMappingError as error:
            raise AcquisitionError(
                AcquisitionErrorCategory.MAPPING_FAILED,
                str(error),
                cause=error,
            ) from error

        spec = mapped[0]
        if spec.model_id != model_id:
            raise AcquisitionError(
                AcquisitionErrorCategory.IDENTITY_UNRESOLVED,
                f"discovered artifact model_id {spec.model_id!r} does not "
                f"match {model_id!r}",
            )

        # B9.97: caller revision is authoritative over advisory discovery revision.
        # Only spec.revision is overridden; model_id and artifact_id are invariant.
        if caller_revision is not None:
            spec = replace(spec, revision=caller_revision)

        return spec

    def _plan_and_acquire(self, model_id: str, spec) -> AcquisitionOutcome:
        try:
            plan: DownloadPlan = self.planner.plan(spec)
        except UnsafePathError as error:
            raise AcquisitionError(
                AcquisitionErrorCategory.PLANNING_FAILED,
                str(error),
                cause=error,
            ) from error

        if plan.status == DownloadPlanStatus.ALREADY_DOWNLOADED:
            return AcquisitionOutcome(
                status=AcquisitionStatus.ALREADY_DOWNLOADED,
                model_id=model_id,
                filename=spec.filename,
                destination=_as_text(plan.destination),
            )
        if plan.status == DownloadPlanStatus.BLOCKED:
            return AcquisitionOutcome(
                status=AcquisitionStatus.BLOCKED,
                model_id=model_id,
                filename=spec.filename,
                reasons=tuple(plan.reasons),
            )
        if plan.status != DownloadPlanStatus.READY:
            # A plan status outside the declared enum is a boundary defect; the
            # boundary must report it, never crash on it.
            raw_status = getattr(plan.status, "value", plan.status)
            raise AcquisitionError(
                AcquisitionErrorCategory.PLANNING_FAILED,
                f"cannot plan download (status: {raw_status})",
            )

        try:
            result = self.downloader.download(plan)
        except UnsafePathError as error:
            raise AcquisitionError(
                AcquisitionErrorCategory.TRANSFER_FAILED,
                str(error),
                cause=error,
            ) from error

        if not result.success:
            return AcquisitionOutcome(
                status=AcquisitionStatus.FAILED,
                model_id=model_id,
                filename=spec.filename,
                destination=_as_text(result.destination),
                # The downloader status stays distinguishable at the
                # application level; the CLI presents it, the boundary does
                # not interpret it.
                failure_status=result.status.value,
                message=(
                    f"download failed ({result.status.value}): {result.error}"
                ),
            )

        # B9.40: a successful transfer is not the end of the flow; manifest
        # registration is what makes the artifact resolvable by the store.
        try:
            manifest_path = self.store.save_manifest(spec)
        except (UnsafePathError, OSError, ValueError) as error:
            raise AcquisitionError(
                AcquisitionErrorCategory.PERSISTENCE_FAILED,
                "artifact was downloaded but its local manifest could not be "
                f"persisted: {error}",
                cause=error,
            ) from error

        return AcquisitionOutcome(
            status=AcquisitionStatus.READY,
            model_id=model_id,
            filename=spec.filename,
            size_bytes=spec.size_bytes,
            destination=_as_text(result.destination),
            bytes_downloaded=result.bytes_downloaded,
            manifest_path=_as_text(manifest_path),
            # Whether an integrity digest was actually verified is a downloader
            # fact, reported by the boundary and presented by the CLI. It is
            # never inferred by presentation.
            verified=bool(spec.sha256),
        )
