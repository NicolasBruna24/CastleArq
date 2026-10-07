
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

"""Read-only resolution of logical models to local artifacts."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .artifact_selection import ArtifactSelectionError, select_artifact
from .model_catalog import get_catalog
from .model_store import ModelStore, UnsafePathError
from .models import ArtifactState, ArtifactSpec, ModelSpec


class ModelArtifactResolutionError(Exception):
    """Raised when a logical model cannot resolve to one local artifact."""


@dataclass(frozen=True)
class ResolvedModelArtifact:
    model: ModelSpec
    artifact: ArtifactSpec
    # B9.66: whether this resolution came from a locally imported artifact
    # rather than the model catalog. Catalog resolution keeps ``imported=False``
    # exactly, so admission and memory policy for catalog models are unchanged.
    # This is the explicit discriminator used by the admission policy; the
    # legacy memory gate separately relies on ``ModelSpec.id is None``, which
    # the B9.66 contract makes equivalent (a catalog model always has an
    # explicit id; an imported model has none).
    imported: bool = False
    # B9.67: the managed file this resolution points at, always inside the
    # model store. It is ``None`` for no successful resolution. This is the
    # managed location, never the external path a file was imported from:
    # importing and resolving are separate operations, and execution must
    # never fall back to the original source path.
    path: Path | None = None


class ModelArtifactResolver:
    """Resolve canonical logical model IDs to exactly one usable artifact.

    The input must be a ``ModelSpec.model_id`` (the canonical logical
    identity) for catalog models, or the sanitized label of a locally
    imported artifact. Artifacts belong to a logical model when their
    persisted ``ArtifactSpec.model_id`` is exactly that identity. Source
    repositories are locators, never model identities, and are never
    accepted here.

    B9.67: when the requested id is not in the catalog, resolution falls
    back to a locally imported artifact addressed by its sanitized label.
    Imported resolution never promotes that label to a logical identity:
    ``ArtifactSpec.model_id`` holds the sanitized label because it is the
    storage key, and the returned ``ModelSpec.id`` stays ``None``. The two
    are deliberately different things, and the label is never copied into
    ``ModelSpec.id``.
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
            # B9.99: an explicitly admitted non-curated identity resolves to
            # its durable Executable Model Description. Read-only: no
            # refresh, no reconciliation, no mutation. Material conflicts
            # fail closed here so both evaluation and execution deny.
            try:
                from .admitted_resolution import (
                    AdmittedMaterialConflictError,
                    AdmittedResolutionError,
                    resolve_model_for_evaluation,
                )
            except Exception:
                return self._resolve_imported(model_id, quantization, filename)
            try:
                admitted = resolve_model_for_evaluation(model_id)
            except AdmittedMaterialConflictError as error:
                # B9.99 findings resolution (B2): typed conflict signal fails
                # closed. Unknown identities fall through to the B9.67
                # imported-label fallback, preserving curated/imported paths.
                raise ModelArtifactResolutionError(str(error)) from error
            except AdmittedResolutionError:
                return self._resolve_imported(model_id, quantization, filename)
            if admitted.from_admitted:
                model = admitted.model
            else:
                # B9.67: not a catalog model. The caller may be naming a locally
                # imported artifact by its sanitized label. This fallback only
                # ever runs once the catalog lookup has already failed, so the
                # catalog path above is untouched.
                return self._resolve_imported(model_id, quantization, filename)

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

        selected_entry = next(
            entry for entry in usable if entry.artifact is selected
        )
        return ResolvedModelArtifact(
            model,
            selected,
            False,
            self._managed_path(selected_entry.manifest_path, selected),
        )

    def _resolve_imported(
        self,
        label: str,
        quantization: str | None,
        filename: str | None,
    ) -> ResolvedModelArtifact:
        """Resolve a locally imported artifact by its sanitized label.

        B9.67. Only managed state is consulted: candidates come from
        ``ModelStore.list_artifacts()``, which already inspects each manifest
        against the filesystem. An external path is never a resolution input,
        so importing and resolving stay separate operations.
        """
        # The label must be a plain storage key, not a path. This rejects
        # selectors like "/home/user/model.gguf" before any store access.
        # The store's own sanitizer is used when available; when a minimal
        # read-only double provides none, reject anything path-like inline so
        # a path is never accepted as a label either way.
        sanitize = getattr(self.model_store, "_safe_model_id", None)
        if sanitize is None:
            if (
                not label
                or label in {".", ".."}
                or "/" in label
                or "\\" in label
                or Path(label).is_absolute()
            ):
                raise ModelArtifactResolutionError(
                    f"Model not found in the local catalog: {label}"
                )
            sanitized = label
        else:
            try:
                sanitized = sanitize(label)
            except UnsafePathError as error:
                raise ModelArtifactResolutionError(
                    f"Model not found in the local catalog: {label}"
                ) from error

        candidates = []
        for entry in self.model_store.list_artifacts():
            artifact = entry.artifact
            # `content_id is not None` is what makes an entry imported, so a
            # catalog artifact can never be mistaken for an imported one.
            if artifact is None or artifact.content_id is None:
                continue
            if artifact.model_id != sanitized:
                continue
            # Reuse the store's own state validation. An imported artifact is
            # held to exactly the same safety conditions as a catalog one.
            if entry.state in {ArtifactState.VERIFIED, ArtifactState.DOWNLOADED}:
                candidates.append((artifact, entry.manifest_path))

        if not candidates:
            raise ModelArtifactResolutionError(
                f"Model not found in the local catalog: {label}"
            )

        try:
            selected = select_artifact(
                [artifact for artifact, _ in candidates],
                quantization=quantization,
                filename=filename,
            )
        except ArtifactSelectionError as error:
            raise ModelArtifactResolutionError(str(error)) from error

        selected_manifest = next(
            manifest for artifact, manifest in candidates if artifact is selected
        )
        # B9.67: the sanitized label is presentation and addressing only. The
        # logical identity stays UNKNOWN, so `id` is None and the `id or name`
        # fallback is never treated as an identity claim.
        model = ModelSpec(
            id=None,
            name=sanitized,
            format=selected.format,
        )
        return ResolvedModelArtifact(
            model,
            selected,
            True,
            self._managed_path(selected_manifest, selected),
        )

    def _managed_path(self, manifest_path: Path, artifact: ArtifactSpec) -> Path | None:
        """The managed file for ``artifact``, verified safe to execute.

        The location comes from the manifest the store already reported, not
        from re-deriving a path, so resolution never invents its own addressing
        scheme. The store's own validation is then applied and the result must
        be a regular, non-symlink file inside the store; anything else fails
        closed rather than yielding a path that could escape.

        Returns ``None`` when the store does not expose the filesystem
        validation primitives. That keeps this resolver usable with the
        minimal read-only doubles the policy tests construct, where there is
        no filesystem to validate against.
        """
        store = self.model_store
        root = getattr(store, "root", None)
        safe_existing = getattr(store, "_safe_existing_path", None)
        reject_symlinks = getattr(store, "_reject_symlink_components", None)
        if root is None or safe_existing is None or reject_symlinks is None:
            return None
        try:
            safe = safe_existing(manifest_path.parent / artifact.filename)
            reject_symlinks(safe)
            info = os.lstat(safe)
        except (UnsafePathError, OSError, ValueError) as error:
            raise ModelArtifactResolutionError(
                f"Managed artifact path is not usable: {error}"
            ) from error
        if not stat.S_ISREG(info.st_mode):
            raise ModelArtifactResolutionError(
                f"Managed artifact is not a regular file: {safe}"
            )
        return safe
