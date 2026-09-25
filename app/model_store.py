
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

"""Local model artifact manifests and safe storage inspection.

Manifests persist declared metadata plus an acquisition record; the local
artifact state is never persisted — it is always derived by inspecting the
filesystem against the manifest's expectations (B9.41).

This module intentionally does not perform network access or model downloads.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import errno
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import ArtifactSpec, ArtifactState


class ModelStoreError(Exception):
    """Base error for local model store operations."""


class UnsafePathError(ModelStoreError):
    """Raised when an identifier or path escapes the model store."""


@dataclass(frozen=True)
class StoredArtifact:
    artifact: ArtifactSpec | None
    state: ArtifactState
    manifest_path: Path
    message: str | None = None


_LEGACY_MODELS_DIRECTORY = "~/.local/share/localai-hub/models"
_DEFAULT_MODELS_DIRECTORY = "~/.local/share/castlearq/models"
LEGACY_MODELS_DIRECTORY = _LEGACY_MODELS_DIRECTORY
DEFAULT_MODELS_DIRECTORY = _DEFAULT_MODELS_DIRECTORY


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path))


def default_models_directory(config_path: Path | None = None) -> Path:
    """Resolve the model store root without creating filesystem entries."""
    data_home = os.environ.get("XDG_DATA_HOME")
    new_default = (Path(data_home).expanduser() / "castlearq" / "models" if data_home
                   else _expand(DEFAULT_MODELS_DIRECTORY))
    legacy_default = _expand(LEGACY_MODELS_DIRECTORY)
    value: str | None = None
    if config_path is not None:
        try:
            in_models = False
            for line in config_path.read_text(encoding="utf-8").splitlines():
                stripped = line.split("#", 1)[0].strip()
                if stripped.startswith("["):
                    in_models = stripped == "[models]"
                elif in_models and stripped.startswith("directory") and "=" in stripped:
                    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    candidate = _expand(value) if value else new_default
    if candidate == new_default and not candidate.exists() and legacy_default.exists():
        return legacy_default
    return candidate


class ModelStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_models_directory()).expanduser()

    def list_artifacts(self) -> list[StoredArtifact]:
        if not self.root.exists():
            return []
        entries: list[StoredArtifact] = []
        for manifest_path in sorted(self.root.glob("*/ */manifest.json".replace(" ", ""))):
            entries.append(self.inspect_manifest(manifest_path))
        return entries

    def save_manifest(self, artifact: ArtifactSpec) -> Path:
        """Persist declared artifact metadata plus an acquisition record.

        The manifest records identity, provenance, declared metadata, the
        integrity expectations (size/sha256) and the acquisition timestamp
        ``downloaded_at`` (conceptually ``registered_at``: the physical field
        name is kept to avoid an extra migration; it is registration metadata,
        never an authority of state).

        No derived state is computed or stored here: ``state`` and ``verified``
        are not written, and ``ArtifactSpec.state`` is only an in-memory
        discovery default — not a source of truth and never persisted in new
        manifests. Nothing is inspected or verified in this operation; the
        local artifact state is always derived by :meth:`inspect_manifest`
        from manifest expectations plus filesystem facts. Legacy manifests
        that still carry ``state``/``verified`` remain readable; their values
        are tolerated for compatibility and never authoritative.
        """
        self._safe_filename(artifact.filename)
        root_fd = self._open_root(create=True)
        try:
            model_fd = self._open_directory(
                root_fd, self._safe_model_id(artifact.model_id), create=True
            )
            try:
                artifact_fd = self._open_directory(
                    model_fd, artifact.artifact_id, create=True
                )
                try:
                    return self._write_manifest(artifact, artifact_fd)
                finally:
                    os.close(artifact_fd)
            finally:
                os.close(model_fd)
        finally:
            os.close(root_fd)

    def _write_manifest(self, artifact: ArtifactSpec, directory_fd: int) -> Path:
        manifest_path = self._artifact_directory(artifact) / "manifest.json"
        for name in ("manifest.json", "manifest.json.part"):
            try:
                mode = os.lstat(name, dir_fd=directory_fd).st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                raise UnsafePathError(f"Symlink is not allowed: {name}")
        payload = {
            "model_id": artifact.model_id,
            "source": artifact.source,
            "repository": artifact.repository,
            "filename": artifact.filename,
            "format": artifact.format,
            "quantization": artifact.quantization,
            "download_url": artifact.download_url,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
            # B9.41: `state` and `verified` are deliberately NOT persisted —
            # the local artifact state is derived by `inspect_manifest()` from
            # manifest expectations plus filesystem facts, never read back
            # from the manifest. `downloaded_at` stays as the acquisition /
            # registration timestamp (conceptually `registered_at`); the
            # physical name is kept to avoid an extra migration.
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        temporary_name = "manifest.json.part"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(temporary_name, flags, 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except OSError:
                pass
            raise
        os.replace(temporary_name, "manifest.json", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
        return manifest_path

    def inspect_manifest(self, manifest_path: Path) -> StoredArtifact:
        try:
            safe_manifest = self._safe_existing_path(manifest_path)
            self._reject_symlink_components(safe_manifest)
            payload = json.loads(safe_manifest.read_text(encoding="utf-8"))
            artifact = _artifact_from_payload(payload)
            file_path = self._safe_existing_path(
                safe_manifest.parent / self._safe_filename(artifact.filename)
            )
            partial_path = file_path.with_name(file_path.name + ".part")
            if partial_path.exists():
                if partial_path.is_symlink():
                    raise UnsafePathError("Artifact partial file is a symlink")
                return StoredArtifact(artifact, ArtifactState.DOWNLOADING, safe_manifest)
            if file_path.is_symlink():
                raise UnsafePathError("Artifact file is a symlink")
            if not file_path.exists():
                return StoredArtifact(artifact, ArtifactState.NOT_DOWNLOADED, safe_manifest)
            actual_size = file_path.stat().st_size
            if artifact.size_bytes is not None and actual_size != artifact.size_bytes:
                return StoredArtifact(
                    artifact, ArtifactState.FAILED, safe_manifest, "File size differs from manifest"
                )
            if artifact.sha256:
                digest = _sha256(file_path)
                state = ArtifactState.VERIFIED if digest == artifact.sha256.lower() else ArtifactState.FAILED
                message = None if state == ArtifactState.VERIFIED else "SHA-256 differs from manifest"
                return StoredArtifact(artifact, state, safe_manifest, message)
            return StoredArtifact(artifact, ArtifactState.DOWNLOADED, safe_manifest)
        except (OSError, ValueError, KeyError, TypeError, UnsafePathError) as error:
            return StoredArtifact(None, ArtifactState.FAILED, manifest_path, str(error))

    def _open_root(self, create: bool) -> int:
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        try:
            return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise UnsafePathError("Model store root must not be a symlink") from error
            raise

    def _open_directory(
        self,
        parent_fd: int,
        name: str,
        *,
        create: bool,
    ) -> int:
        try:
            return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except FileNotFoundError:
            if not create:
                raise
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                try:
                    if stat.S_ISLNK(os.lstat(name, dir_fd=parent_fd).st_mode):
                        raise UnsafePathError(f"Symlink is not allowed: {name}") from error
                except FileNotFoundError:
                    pass
            if error.errno == errno.ELOOP:
                raise UnsafePathError(f"Symlink is not allowed: {name}") from error
            raise

    def _artifact_directory(self, artifact: ArtifactSpec) -> Path:
        model_dir = self._safe_child(self.root, self._safe_model_id(artifact.model_id))
        return self._safe_child(model_dir, artifact.artifact_id)

    def _safe_child(self, parent: Path, value: str) -> Path:
        return parent / self._safe_component(value)

    def _safe_existing_path(self, path: Path) -> Path:
        self._reject_symlink_components(path)
        root = self.root.absolute()
        candidate = path.absolute()
        if root != candidate and root not in candidate.parents:
            raise UnsafePathError("Path escapes model store")
        return candidate

    def _reject_symlink_components(self, path: Path) -> None:
        try:
            if self.root.is_symlink():
                raise UnsafePathError("Model store root is a symlink")
        except OSError as error:
            raise UnsafePathError(f"Cannot inspect model store root: {error}") from error
        root = self.root.absolute()
        current = root
        try:
            relative = path.absolute().relative_to(root)
        except ValueError as error:
            raise UnsafePathError("Path escapes model store") from error
        for component in relative.parts:
            current /= component
            try:
                if current.is_symlink():
                    raise UnsafePathError(f"Symlink is not allowed: {current}")
            except OSError as error:
                raise UnsafePathError(f"Cannot inspect path component: {current}") from error

    @staticmethod
    def _safe_component(value: str) -> str:
        if not value or value in {".", ".."} or Path(value).is_absolute():
            raise UnsafePathError("Unsafe path component")
        if "/" in value or "\\" in value or ".." in value:
            raise UnsafePathError("Unsafe path component")
        sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", value)
        if not sanitized or sanitized in {".", ".."}:
            raise UnsafePathError("Unsafe path component")
        return sanitized

    @staticmethod
    def _safe_model_id(value: str) -> str:
        if not value or Path(value).is_absolute() or any(
            part in {".", ".."} for part in Path(value).parts
        ):
            raise UnsafePathError("Unsafe model identifier")
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.replace("/", "__").replace("\\", "__"))
        if not sanitized or sanitized in {".", ".."}:
            raise UnsafePathError("Unsafe model identifier")
        return sanitized

    def _safe_filename(self, filename: str) -> str:
        return self._safe_component(filename)


def _artifact_from_payload(payload: dict[str, object]) -> ArtifactSpec:
    required = ("model_id", "source", "repository", "filename")
    for key in required:
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"Invalid manifest field: {key}")
    # Legacy manifests (pre-B9.41) persisted `state`; new manifests never do.
    # The value is validated only so legacy manifests keep loading (read
    # tolerance). It is never used to derive the current local state — that
    # authority belongs exclusively to `ModelStore.inspect_manifest()`.
    state_value = payload.get("state", ArtifactState.NOT_DOWNLOADED.value)
    try:
        state = ArtifactState(str(state_value))
    except ValueError as error:
        raise ValueError("Invalid manifest state") from error
    size = payload.get("size_bytes")
    if size is not None and (not isinstance(size, int) or size < 0):
        raise ValueError("Invalid manifest size_bytes")
    sha256 = payload.get("sha256")
    if sha256 is not None and (
        not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
    ):
        raise ValueError("Invalid manifest sha256")
    return ArtifactSpec(
        model_id=str(payload["model_id"]),
        source=str(payload["source"]),
        repository=str(payload["repository"]),
        filename=str(payload["filename"]),
        format=str(payload.get("format", "Unknown")),
        quantization=str(payload.get("quantization", "Unknown")),
        download_url=payload.get("download_url") if isinstance(payload.get("download_url"), str) else None,
        size_bytes=size,
        sha256=sha256,
        state=state,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
