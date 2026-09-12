"""Validate model artifacts and produce offline download plans.

This module deliberately does not create files, modify manifests, or access
remote URLs. Download execution belongs to a future phase.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
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
            self._validate_metadata(artifact)
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
    def _validate_metadata(artifact: ArtifactSpec) -> None:
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
        if not artifact.download_url:
            raise ValueError("Artifact download URL is required")
        _validate_url(artifact.download_url, artifact.repository, artifact.filename)
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


def _validate_url(url: str, repository: str, filename: str) -> None:
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
        f"/{repository}/resolve/main/{filename}"
    )
    if unquote(parsed.path) != expected_path:
        raise ValueError("Artifact URL does not match repository and filename")
