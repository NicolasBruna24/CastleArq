"""Physical import of a local GGUF artifact into the managed model store.

B9.67, stage 1: the physical core only. It validates a local file, observes
the GGUF evidence the current reader can justify, computes the content digest
that *is* the artifact identity, copies atomically through a ``.part`` file
and registers a manifest.

Three separations are deliberate and load-bearing:

* **Content identity is not an integrity declaration.** The computed
  SHA-256 is stored as ``ArtifactSpec.content_id`` and is what
  ``artifact_id`` returns. It is deliberately *not* copied into
  ``ArtifactSpec.sha256``: that field is a declaration to be checked against
  the file, and filling it with the digest we just computed would make
  ``inspect_manifest`` compare a value against itself and report VERIFIED
  -- a verification that never happened. An imported artifact therefore has
  a content identity and an UNKNOWN integrity declaration.

* **Nothing is derived that was not observed.** No logical model identity,
  no provenance, no parameter count, no memory estimate, no quantization. A
  local file has no known publisher or repository, so ``source``,
  ``repository`` and ``download_url`` stay ``None`` rather than being
  fabricated. Only ``general.architecture`` is observed, because the
  existing reader can read exactly that and nothing more.

* **Failure is not ignorance.** A concrete violation (missing path,
  symlink, invalid GGUF, unsafe label, copy error) is ``FAILED`` with a
  reason. ``UNKNOWN`` is never used to report an operation that failed.

This stage is not wired to the resolver, the CLI or execution; nothing here
is reachable from those paths yet.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .gguf_reader import GGUFReadError, read_architecture_evidence
from .model_store import ModelStore, UnsafePathError
from .models import ArtifactSpec, ArtifactState, ModelSpec

_CHUNK = 1024 * 1024


class ImportStatus(str, Enum):
    """Outcome of one local import attempt.

    Deliberately its own vocabulary, not ``DownloadResultStatus``: importing
    from a local path shares no origin, no partial-resume semantics and no
    network error model with downloading.
    """

    IMPORTED = "imported"
    REUSED = "reused"
    FAILED = "failed"


@dataclass(frozen=True)
class ImportResult:
    """What later stages need in order to consume an import.

    ``model`` carries ``id=None`` on purpose: the sanitized label is
    presentation and addressing only, never a logical model identity that
    nothing in this stage could justify.
    """

    status: ImportStatus
    content_id: str | None = None
    artifact: ArtifactSpec | None = None
    model: ModelSpec | None = None
    label: str | None = None
    sanitized_label: str | None = None
    filename: str | None = None
    destination: Path | None = None
    architecture: str | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is not ImportStatus.FAILED

    @property
    def artifact_id(self) -> str | None:
        return self.artifact.artifact_id if self.artifact is not None else None


def _fail(error: str, **extra: Any) -> ImportResult:
    return ImportResult(status=ImportStatus.FAILED, error=error, **extra)


def _model_for(sanitized_label: str) -> ModelSpec:
    """A ModelSpec whose logical identity stays UNKNOWN.

    The label addresses and presents. It is never assigned to ``id``: this
    stage read no evidence establishing which model the file is, and a label
    is a name the operator chose, not an identity.
    """
    return ModelSpec(id=None, name=sanitized_label, format="GGUF")



class LocalArtifactImporter:
    """Import a local GGUF file into ``store`` as a managed artifact."""

    def __init__(self, store: ModelStore) -> None:
        self.store = store

    def import_artifact(
        self,
        path: str | Path,
        label: str | None = None,
    ) -> ImportResult:
        source = Path(path)
        raw_label = label if label is not None else source.name

        # 1. Inspect the source read-only, before reading or copying it.
        #    lstat (not stat) is what makes a symlink observable at all.
        try:
            info = os.lstat(source)
        except FileNotFoundError:
            return _fail(f"Source path does not exist: {source}")
        except OSError as error:
            return _fail(f"Cannot inspect source path: {error}")
        if stat.S_ISLNK(info.st_mode):
            return _fail(f"Source is a symbolic link: {source}")
        if stat.S_ISDIR(info.st_mode):
            return _fail(f"Source is a directory, not a file: {source}")
        if not stat.S_ISREG(info.st_mode):
            return _fail(f"Source is not a regular file: {source}")

        # 2. GGUF validity, plus the only evidence the reader can justify.
        try:
            evidence = read_architecture_evidence(source)
        except GGUFReadError as error:
            return _fail(f"Source is not a valid GGUF file: {error}")
        warnings: list[str] = []
        if not evidence.present:
            warnings.append(
                "No general.architecture was observed; architecture remains "
                "UNKNOWN rather than inferred."
            )

        # 3. Label -> sanitized addressing value, using the store's own rules.
        try:
            sanitized_label = self.store._safe_model_id(raw_label)
            filename = self.store._safe_filename(source.name)
        except UnsafePathError as error:
            return _fail(f"Unsafe label or filename: {error}")

        # 4. Content digest == physical identity.
        try:
            content_id = self._content_digest(source)
        except OSError as error:
            return _fail(f"Cannot read source content: {error}")
        size_bytes = info.st_size

        # 5. REUSED: the same bytes are never stored twice, whatever the
        #    incoming filename or label happen to be.
        existing = self.store.find_by_content_id(content_id)
        if existing is not None and existing.artifact is not None:
            kept = existing.artifact
            return ImportResult(
                status=ImportStatus.REUSED,
                content_id=content_id,
                artifact=kept,
                model=_model_for(kept.model_id),
                label=raw_label,
                sanitized_label=kept.model_id,
                filename=kept.filename,
                destination=self.store.artifact_directory(kept) / kept.filename,
                architecture=evidence.architecture_raw,
                warnings=tuple(warnings)
                + ("Content is already managed; the existing copy was kept.",),
            )

        artifact = ArtifactSpec(
            model_id=sanitized_label,
            source=None,
            repository=None,
            filename=filename,
            format="GGUF",
            quantization="Unknown",
            download_url=None,
            size_bytes=size_bytes,
            # The integrity declaration stays UNKNOWN; see the docstring.
            sha256=None,
            state=ArtifactState.DOWNLOADED,
            content_id=content_id,
        )
        destination = self.store.artifact_directory(artifact) / filename

        # 6. Copy through `.part`, publish, and only then register the manifest.
        failure = self._copy_atomically(source, artifact, content_id, size_bytes)
        if failure is not None:
            return failure

        try:
            self.store.save_manifest(artifact)
        except (OSError, UnsafePathError, ValueError) as error:
            return _fail(
                f"Published file but could not register its manifest: {error}",
                content_id=content_id,
                artifact=artifact,
                model=_model_for(sanitized_label),
                label=raw_label,
                sanitized_label=sanitized_label,
                filename=filename,
                destination=destination,
                architecture=evidence.architecture_raw,
                warnings=tuple(warnings),
            )

        return ImportResult(
            status=ImportStatus.IMPORTED,
            content_id=content_id,
            artifact=artifact,
            model=_model_for(sanitized_label),
            label=raw_label,
            sanitized_label=sanitized_label,
            filename=filename,
            destination=destination,
            architecture=evidence.architecture_raw,
            warnings=tuple(warnings),
        )


    def _copy_atomically(
        self,
        source: Path,
        artifact: ArtifactSpec,
        content_id: str,
        size_bytes: int,
    ) -> ImportResult | None:
        """Copy to ``<name>.part`` then publish. A failure result or None.

        Mirrors the downloader's publication pattern: the bytes land in a
        ``.part`` file, which is never executable, and the final name only
        appears once the whole file is on disk. If the copy dies the
        ``.part`` is removed, so no manifest can ever end up describing an
        incomplete artifact.
        """
        part_name = f"{artifact.filename}.part"
        root_fd = model_fd = artifact_fd = part_fd = None
        try:
            root_fd = self.store._open_root(create=True)
            model_fd = self.store._open_directory(
                root_fd, self.store._safe_model_id(artifact.model_id), create=True
            )
            artifact_fd = self.store._open_directory(
                model_fd, artifact.artifact_id, create=True
            )
            self.store._reject_symlink_components(
                self.store.artifact_directory(artifact) / artifact.filename
            )

            # A pre-existing partial is not resumed: a local copy is cheap
            # and re-derived from the source, and appending to an existing
            # `.part` could mix the bytes of two different contents.
            for name in (artifact.filename, part_name):
                try:
                    mode = os.lstat(name, dir_fd=artifact_fd).st_mode
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(mode):
                    raise UnsafePathError(f"Symlink is not allowed: {name}")
                os.unlink(name, dir_fd=artifact_fd)

            part_fd = os.open(
                part_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=artifact_fd,
            )
            copied = 0
            with source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(_CHUNK), b""):
                    view = memoryview(chunk)
                    while view:
                        written = os.write(part_fd, view)
                        if written <= 0:
                            raise OSError("Unable to write import chunk")
                        view = view[written:]
                    copied += len(chunk)
            os.fsync(part_fd)
            os.close(part_fd)
            part_fd = None

            # The copy must be complete and must be the content that was
            # hashed, or the digest recorded in the manifest would describe
            # bytes that are not the published ones.
            if copied != size_bytes:
                return _fail(
                    f"Copied size {copied} differs from source size {size_bytes}.",
                    content_id=content_id,
                )
            observed = self._partial_digest(part_name, artifact_fd)
            if not hmac.compare_digest(observed, content_id):
                return _fail(
                    "Copied content digest differs from the source content digest.",
                    content_id=content_id,
                )

            # Publish atomically, then fsync the directory entry.
            os.link(
                part_name,
                artifact.filename,
                src_dir_fd=artifact_fd,
                dst_dir_fd=artifact_fd,
            )
            os.unlink(part_name, dir_fd=artifact_fd)
            os.fsync(artifact_fd)
            return None
        except UnsafePathError as error:
            self._discard(part_name, artifact_fd)
            return _fail(str(error), content_id=content_id)
        except (OSError, ValueError) as error:
            self._discard(part_name, artifact_fd)
            return _fail(
                f"Cannot copy artifact into the model store: {error}",
                content_id=content_id,
            )
        finally:
            for fd in (part_fd, artifact_fd, model_fd, root_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    @staticmethod
    def _discard(name: str, directory_fd: int | None) -> None:
        """Remove a partial copy so no `.part` is left to look complete."""
        if directory_fd is None:
            return
        try:
            os.unlink(name, dir_fd=directory_fd)
        except OSError:
            pass

    @staticmethod
    def _partial_digest(name: str, directory_fd: int) -> str:
        digest = hashlib.sha256()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, "rb", closefd=False) as stream:
                for chunk in iter(lambda: stream.read(_CHUNK), b""):
                    digest.update(chunk)
        finally:
            os.close(fd)
        return digest.hexdigest()

    @staticmethod
    def _content_digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(_CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()
