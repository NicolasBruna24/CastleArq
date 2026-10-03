
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

"""Validate model artifacts and produce offline download plans.

This module deliberately does not create files, modify manifests, or access
remote URLs. Download execution belongs to a future phase.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from ..model_store import ModelStore, UnsafePathError
from ..models import ArtifactSpec, ArtifactState
from ..sources.huggingface import _validate_filename, _validate_repository
from ..sources.huggingface import SourceError


class DownloadPlanStatus(str, Enum):
    READY = "ready"
    ALREADY_DOWNLOADED = "already_downloaded"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DownloadPlan:
    artifact: ArtifactSpec
    destination: Path | None
    status: DownloadPlanStatus
    reasons: tuple[str, ...]
    available_bytes: int | None
    required_bytes: int | None
    existing: bool


DiskUsageProvider = Callable[[Path], int]


def _available_bytes(path: Path) -> int:
    filesystem_path = path
    while not filesystem_path.exists():
        if filesystem_path.parent == filesystem_path:
            break
        filesystem_path = filesystem_path.parent
    return shutil.disk_usage(filesystem_path).free


class DownloadPlanner:
    def __init__(
        self,
        model_store: ModelStore | None = None,
        disk_usage_provider: DiskUsageProvider = _available_bytes,
    ) -> None:
        self.model_store = model_store or ModelStore()
        self.disk_usage_provider = disk_usage_provider

    def plan(self, artifact: ArtifactSpec | None) -> DownloadPlan:
        if not isinstance(artifact, ArtifactSpec):
            return self._blocked(
                artifact, "Artifact must be an ArtifactSpec"
            )

        reasons: list[str] = []
        try:
            artifact = self._validate_metadata(artifact)
            destination = self._destination(artifact)
        except UnsafePathError:
            raise
        except (SourceError, ValueError, TypeError) as error:
            return DownloadPlan(
                artifact=artifact,
                destination=None,
                status=DownloadPlanStatus.BLOCKED,
                reasons=(str(error),),
                available_bytes=None,
                required_bytes=None,
                existing=False,
            )

        manifest_path = destination.parent / "manifest.json"
        existing = manifest_path.exists() or destination.exists() or Path(
            f"{destination}.part"
        ).exists()
        if manifest_path.exists():
            stored = self.model_store.inspect_manifest(manifest_path)
            if stored.state in {ArtifactState.DOWNLOADED, ArtifactState.VERIFIED}:
                return DownloadPlan(
                    artifact=artifact,
                    destination=destination,
                    status=DownloadPlanStatus.ALREADY_DOWNLOADED,
                    reasons=(),
                    available_bytes=None,
                    required_bytes=artifact.size_bytes,
                    existing=True,
                )
            if stored.state == ArtifactState.FAILED:
                message = stored.message or f"Existing artifact state is {stored.state.value}"
                return DownloadPlan(
                    artifact=artifact,
                    destination=destination,
                    status=DownloadPlanStatus.BLOCKED,
                    reasons=(message,),
                    available_bytes=None,
                    required_bytes=artifact.size_bytes,
                    existing=True,
                )
        elif existing and not Path(f"{destination}.part").exists():
            return DownloadPlan(
                artifact=artifact,
                destination=destination,
                status=DownloadPlanStatus.BLOCKED,
                reasons=("Artifact files exist without a valid manifest",),
                available_bytes=None,
                required_bytes=artifact.size_bytes,
                existing=True,
            )

        try:
            available = self.disk_usage_provider(self.model_store.root)
        except OSError as error:
            return DownloadPlan(
                artifact=artifact,
                destination=destination,
                status=DownloadPlanStatus.UNKNOWN,
                reasons=(f"Unable to determine available disk space: {error}",),
                available_bytes=None,
                required_bytes=artifact.size_bytes,
                existing=existing,
            )
        if isinstance(available, bool) or not isinstance(available, int) or available < 0:
            return DownloadPlan(
                artifact=artifact,
                destination=destination,
                status=DownloadPlanStatus.UNKNOWN,
                reasons=("Disk usage provider returned an invalid value",),
                available_bytes=None,
                required_bytes=artifact.size_bytes,
                existing=existing,
            )
        if artifact.size_bytes is None:
            return DownloadPlan(
                artifact=artifact,
                destination=destination,
                status=DownloadPlanStatus.UNKNOWN,
                reasons=("Artifact size is unknown; available space cannot be guaranteed",),
                available_bytes=available,
                required_bytes=None,
                existing=existing,
            )
        if artifact.size_bytes > available:
            return DownloadPlan(
                artifact=artifact,
                destination=destination,
                status=DownloadPlanStatus.BLOCKED,
                reasons=("Insufficient available disk space",),
                available_bytes=available,
                required_bytes=artifact.size_bytes,
                existing=existing,
            )
        return DownloadPlan(
            artifact=artifact,
            destination=destination,
            status=DownloadPlanStatus.READY,
            reasons=tuple(reasons),
            available_bytes=available,
            required_bytes=artifact.size_bytes,
            existing=existing,
        )

    def _destination(self, artifact: ArtifactSpec) -> Path:
        directory = self.model_store._artifact_directory(artifact)
        filename = self.model_store._safe_filename(artifact.filename)
        destination = directory / filename
        self.model_store._reject_symlink_components(destination)
        return destination

    @staticmethod
    def _validate_metadata(artifact: ArtifactSpec) -> ArtifactSpec:
        """Validate declared metadata and return the canonicalized artifact.

        B9.90: the planner is the single canonical acquisition-locator
        authority. After repository, filename and revision syntax have been
        validated, the canonical locator is derived from the trusted artifact
        fields — never from the incoming URL — and it is that canonical URL
        which must pass the existing URL security validation. The incoming
        ``download_url`` remains transport metadata: it is still held to the
        same security model and path correspondence, but it never decides the
        revision component of the locator carried by the resulting plan. An
        already-canonical artifact is returned unchanged, so it keeps its
        identity.
        """
        if not artifact.source:
            raise ValueError("Artifact source is required")
        if artifact.source != "huggingface":
            raise ValueError(f"Unsupported artifact source: {artifact.source}")
        if not artifact.repository:
            raise ValueError("Artifact repository is required")
        _validate_repository(artifact.repository)
        _validate_filename(artifact.filename)
        if not isinstance(artifact.format, str) or artifact.format.upper() != "GGUF":
            raise ValueError("Only GGUF artifacts are supported")
        revision = artifact.revision
        if revision is not None and (
            not isinstance(revision, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}", revision)
        ):
            # B9.90: a malformed non-None revision is rejected explicitly,
            # before any locator is derived from it, instead of surfacing as
            # a malformed URL that only path comparison would catch. The
            # syntax contract is exactly the existing 40-hex contract; it is
            # neither broadened nor normalized here.
            raise ValueError(
                "Artifact revision must be a 40-character hexadecimal commit hash"
            )
        if not artifact.download_url:
            raise ValueError("Artifact download URL is required")
        # B9.90: derive the canonical locator from the trusted declared fields
        # only; the incoming URL is never authoritative for the revision
        # component. The canonical URL itself then passes the existing URL
        # security validation unchanged.
        canonical_url = _canonical_download_url(
            artifact.repository, artifact.filename, revision
        )
        _validate_url(canonical_url, artifact.repository, artifact.filename, revision)
        try:
            _validate_url(
                artifact.download_url,
                artifact.repository,
                artifact.filename,
                revision,
            )
        except ValueError:
            if revision is None:
                raise
            # B9.90: the discovery provider intentionally emits the unpinned
            # `main` form together with a declared revision. That combination
            # is accepted as transport metadata only — the canonical locator
            # validated above replaces it in the resulting plan. A locator
            # declaring a different revision, a different repository or
            # filename, or violating any URL security rule still fails here.
            _validate_url(
                artifact.download_url,
                artifact.repository,
                artifact.filename,
                None,
            )
        if artifact.size_bytes is not None and (
            isinstance(artifact.size_bytes, bool)
            or not isinstance(artifact.size_bytes, int)
            or artifact.size_bytes < 0
        ):
            raise ValueError("Invalid artifact size")
        if artifact.sha256 is not None and (
            not isinstance(artifact.sha256, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", artifact.sha256)
        ):
            raise ValueError("Invalid artifact SHA-256")
        # B9.90: the plan carries the canonical locator. The incoming locator
        # is replaced by the planner-derived canonical one whenever they
        # differ (e.g. the provider's main form for a declared revision); an
        # already-canonical artifact keeps its identity untouched.
        if artifact.download_url != canonical_url:
            artifact = replace(artifact, download_url=canonical_url)
        return artifact

    def _blocked(self, artifact: ArtifactSpec | None, reason: str) -> DownloadPlan:
        if not isinstance(artifact, ArtifactSpec):
            artifact = ArtifactSpec(
                model_id="Unknown",
                source="Unknown",
                repository="Unknown/Unknown",
                filename="Unknown",
            )
        return DownloadPlan(
            artifact=artifact,
            destination=None,
            status=DownloadPlanStatus.BLOCKED,
            reasons=(reason,),
            available_bytes=None,
            required_bytes=None,
            existing=False,
        )


def _canonical_download_url(
    repository: str, filename: str, revision: str | None
) -> str:
    """Derive the canonical acquisition locator from trusted artifact fields.

    B9.90: this is the sole canonical locator derivation, and it lives only in
    the planner. It reads the declared ``repository``, ``filename`` and
    ``revision`` — never the incoming URL — so ``revision=None`` yields the
    unpinned ``/resolve/main/`` form and a declared 40-hex revision yields
    ``/resolve/<revision>/``. The result is validated by ``_validate_url``
    before it can appear in a READY plan.
    """
    return (
        f"https://huggingface.co/{repository}/resolve/{revision or 'main'}/{filename}"
    )


def _validate_url(
    url: str,
    repository: str,
    filename: str,
    revision: str | None = None,
) -> None:
    """Validate the download URL against repository, filename and revision.

    B9.83: when a declared ``revision`` is present the expected path segment
    is that revision; when it is absent the existing ``resolve/main``
    contract is enforced unchanged. Every other guarantee — HTTPS only, the
    huggingface.co host, no credentials, no port, no query or fragment, and
    the exact repository/filename correspondence — is preserved and not
    weakened. A declared revision is never accepted from an undeclared
    artifact, and the default ``main`` form is never accepted for an artifact
    that declares a different revision.

    B9.90: a non-None ``revision`` must itself satisfy the acquisition-path
    revision contract (exactly 40 hexadecimal characters); a malformed
    revision is rejected explicitly instead of being folded into the expected
    path. This is the shared validation rule the Downloader uses defensively,
    aligned to the planner's canonical contract — it validates only, never
    constructs or repairs a locator.
    """
    if revision is not None and (
        not isinstance(revision, str)
        or not re.fullmatch(r"[0-9a-fA-F]{40}", revision)
    ):
        raise ValueError(
            "Artifact revision must be a 40-character hexadecimal commit hash"
        )
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "huggingface.co"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Artifact URL must be an HTTPS Hugging Face URL")
    expected_path = (
        f"/{repository}/resolve/{revision or 'main'}/{filename}"
    )
    if unquote(parsed.path) != expected_path:
        raise ValueError("Artifact URL does not match repository and filename")
