"""Read-only resolution of logical models to local artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    """Resolve catalog model IDs to exactly one usable local artifact."""

    def __init__(
        self,
        model_store: ModelStore | None = None,
        models: tuple[ModelSpec, ...] | None = None,
    ) -> None:
        self.model_store = model_store or ModelStore()
        self.models = models if models is not None else get_catalog()

    def resolve(self, model_id: str) -> ResolvedModelArtifact:
        model = next((item for item in self.models if item.model_id == model_id), None)
        if model is None:
            raise ModelArtifactResolutionError(
                f"Model not found in the local catalog: {model_id}"
            )

        matching = [
            entry
            for entry in self.model_store.list_artifacts()
            if entry.artifact is not None and _matches_model(model, entry.artifact)
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
        if len(usable) > 1:
            raise ModelArtifactResolutionError(
                f"Multiple local artifacts match model: {model_id}"
            )
        if not usable:
            raise ModelArtifactResolutionError(
                f"No usable local artifact is installed for model: {model_id}"
            )
        return ResolvedModelArtifact(model, usable[0].artifact)


def _matches_model(model: ModelSpec, artifact: ArtifactSpec) -> bool:
    logical_id = _normalize(model.model_id)
    repository_name = artifact.repository.rsplit("/", 1)[-1]
    artifact_model_name = artifact.model_id.rsplit("/", 1)[-1]
    return logical_id in {
        _normalize(_without_gguf_suffix(repository_name)),
        _normalize(_without_gguf_suffix(artifact_model_name)),
    }


def _without_gguf_suffix(value: str) -> str:
    return re.sub(r"[-_.]?gguf$", "", value, flags=re.IGNORECASE)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())
