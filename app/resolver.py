"""Read-only resolution of logical models to local artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .artifact_selection import ArtifactSelectionError, select_artifact
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactState, ArtifactSpec, ModelSpec


class ModelArtifactResolutionError(Exception):
    """Raised when a logical model cannot resolve to one local artifact."""


@dataclass(frozen=True)
class ResolvedModelArtifact:
    model: ModelSpec
    artifact: ArtifactSpec


class ModelArtifactResolver:
    """Resolve canonical logical model IDs to exactly one usable artifact.

    The input must be a ``ModelSpec.model_id`` (the canonical logical
    identity). Artifacts belong to a logical model when their persisted
    ``ArtifactSpec.model_id`` is exactly that identity. Source repositories
    are locators, never model identities, and are never accepted here.
    """

    def __init__(
        self,
        model_store: ModelStore | None = None,
        models: tuple[ModelSpec, ...] | None = None,
    ) -> None:
        self.model_store = model_store or ModelStore()
        self.models = models if models is not None else get_catalog()

    def resolve(
        self,
        model_id: str,
        *,
        quantization: str | None = None,
        filename: str | None = None,
    ) -> ResolvedModelArtifact:
        model = next((item for item in self.models if item.model_id == model_id), None)
        if model is None:
            raise ModelArtifactResolutionError(
                f"Model not found in the local catalog: {model_id}"
            )

        matching = [
            entry
            for entry in self.model_store.list_artifacts()
            if entry.artifact is not None
            and entry.artifact.model_id == model.model_id
        ]
        if not matching:
            raise ModelArtifactResolutionError(
                f"No local artifact is installed for model: {model_id}"
            )

        incomplete = [entry for entry in matching if entry.state == ArtifactState.DOWNLOADING]
        if incomplete:
            raise ModelArtifactResolutionError(
                f"Artifact download is incomplete for model: {model_id}"
            )

        failed = [entry for entry in matching if entry.state == ArtifactState.FAILED]
        if failed:
            raise ModelArtifactResolutionError(
                f"Local artifact is invalid for model: {model_id}"
            )

        unavailable = [
            entry
            for entry in matching
            if entry.state == ArtifactState.NOT_DOWNLOADED
        ]
        if unavailable:
            raise ModelArtifactResolutionError(
                f"Artifact is not available locally for model: {model_id}"
            )

        usable = [
            entry
            for entry in matching
            if entry.state in {ArtifactState.VERIFIED, ArtifactState.DOWNLOADED}
        ]
        if not usable:
            raise ModelArtifactResolutionError(
                f"No usable local artifact is installed for model: {model_id}"
            )

        candidates = [entry.artifact for entry in usable if entry.artifact is not None]
        try:
            selected = select_artifact(
                candidates,
                quantization=quantization,
                filename=filename,
            )
        except ArtifactSelectionError as error:
            raise ModelArtifactResolutionError(str(error)) from error

        return ResolvedModelArtifact(model, selected)
