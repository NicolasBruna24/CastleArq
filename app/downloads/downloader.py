"""Basic streaming artifact downloads.

This module intentionally excludes resume, retries, checksums, and manifest
management. A completed temporary file is published without replacing an
existing artifact.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..model_store import ModelStore, UnsafePathError
from .planner import DownloadPlan, DownloadPlanStatus, _validate_url


class DownloadResultStatus(str, Enum):
    SUCCESS = "success"
    PLAN_REJECTED = "plan_rejected"
    ALREADY_EXISTS = "already_exists"
    PARTIAL_EXISTS = "partial_exists"
    HTTP_ERROR = "http_error"
    NETWORK_ERROR = "network_error"
    FILESYSTEM_ERROR = "filesystem_error"
    SIZE_MISMATCH = "size_mismatch"


@dataclass(frozen=True)
class DownloadResult:
    success: bool
    status: DownloadResultStatus
    destination: Path | None
    bytes_downloaded: int
    error: str | None = None


ResponseOpener = Callable[[str, float], BinaryIO]


def _open_url(url: str, timeout: float) -> BinaryIO:
    return urlopen(
        Request(url, headers={"User-Agent": "LocalAI-Hub"}),
        timeout=timeout,
    )


class Downloader:
    def __init__(
        self,
        model_store: ModelStore,
        *,
        opener: ResponseOpener = _open_url,
        timeout: float = 30.0,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.model_store = model_store
        self.opener = opener
        self.timeout = timeout
        self.chunk_size = chunk_size

    def download(self, plan: DownloadPlan) -> DownloadResult:
        if plan.status != DownloadPlanStatus.READY:
            return DownloadResult(
                False,
                DownloadResultStatus.PLAN_REJECTED,
                plan.destination,
                0,
                f"Download plan is not ready: {plan.status.value}",
            )
        artifact = plan.artifact
        if plan.destination is None:
            return DownloadResult(
                False,
                DownloadResultStatus.PLAN_REJECTED,
                None,
                0,
                "Download plan has no destination",
            )
        try:
            _validate_url(artifact.download_url or "", artifact.repository, artifact.filename)
            expected = self._destination(artifact)
            if expected != plan.destination:
                raise UnsafePathError("Download plan destination does not match ModelStore")
            return self._download_to_destination(artifact, expected)
        except UnsafePathError:
            raise
        except ValueError as error:
            return DownloadResult(
                False, DownloadResultStatus.PLAN_REJECTED, plan.destination, 0, str(error)
            )

    def _destination(self, artifact) -> Path:
        directory = self.model_store._artifact_directory(artifact)
        filename = self.model_store._safe_filename(artifact.filename)
        destination = directory / filename
        self.model_store._reject_symlink_components(destination)
        return destination

    def _download_to_destination(self, artifact, destination: Path) -> DownloadResult:
        parent = destination.parent
        part_name = f"{destination.name}.part"
        root_fd = self.model_store._open_root(create=True)
        model_fd = None
        artifact_fd = None
        part_fd = None
        created_part = False
        bytes_downloaded = 0
        try:
            model_fd = self.model_store._open_directory(
                root_fd, self.model_store._safe_model_id(artifact.model_id), create=True
            )
            artifact_fd = self.model_store._open_directory(
                model_fd, artifact.artifact_id, create=True
            )
            self.model_store._reject_symlink_components(destination)
            for name in (destination.name, part_name):
                try:
                    mode = os.lstat(name, dir_fd=artifact_fd).st_mode
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(mode):
                    raise UnsafePathError(f"Symlink is not allowed: {name}")
                if name == destination.name:
                    return DownloadResult(
                        False,
                        DownloadResultStatus.ALREADY_EXISTS,
                        destination,
                        0,
                        "Artifact already exists",
                    )
                return DownloadResult(
                    False,
                    DownloadResultStatus.PARTIAL_EXISTS,
                    destination,
                    0,
                    "Artifact partial file already exists",
                )

            part_fd = os.open(
                part_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=artifact_fd,
            )
            created_part = True
            response = None
            try:
                response = self.opener(artifact.download_url or "", self.timeout)
                while True:
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    view = memoryview(chunk)
                    while view:
                        written = os.write(part_fd, view)
                        if written <= 0:
                            raise OSError("Unable to write download chunk")
                        view = view[written:]
                    bytes_downloaded += len(chunk)
                os.fsync(part_fd)
            except HTTPError as error:
                return self._failure(
                    DownloadResultStatus.HTTP_ERROR,
                    destination,
                    bytes_downloaded,
                    f"HTTP {error.code}",
                )
            except (URLError, TimeoutError, OSError) as error:
                return self._failure(
                    DownloadResultStatus.NETWORK_ERROR,
                    destination,
                    bytes_downloaded,
                    str(error),
                )
            finally:
                if response is not None:
                    response.close()

            if artifact.size_bytes is not None and bytes_downloaded != artifact.size_bytes:
                return self._failure(
                    DownloadResultStatus.SIZE_MISMATCH,
                    destination,
                    bytes_downloaded,
                    "Downloaded size differs from artifact metadata",
                )
            os.close(part_fd)
            part_fd = None
            try:
                os.link(
                    part_name,
                    destination.name,
                    src_dir_fd=artifact_fd,
                    dst_dir_fd=artifact_fd,
                )
            except FileExistsError:
                return self._failure(
                    DownloadResultStatus.ALREADY_EXISTS,
                    destination,
                    bytes_downloaded,
                    "Artifact appeared before atomic publication",
                )
            os.unlink(part_name, dir_fd=artifact_fd)
            os.fsync(artifact_fd)
            created_part = False
            return DownloadResult(True, DownloadResultStatus.SUCCESS, destination, bytes_downloaded)
        except UnsafePathError:
            raise
        except FileExistsError as error:
            return self._failure(
                DownloadResultStatus.PARTIAL_EXISTS,
                destination,
                bytes_downloaded,
                "Artifact partial file already exists",
            )
        except (OSError, ValueError) as error:
            return self._failure(
                DownloadResultStatus.FILESYSTEM_ERROR,
                destination,
                bytes_downloaded,
                str(error),
            )
        finally:
            if part_fd is not None:
                os.close(part_fd)
            if created_part and artifact_fd is not None:
                try:
                    os.unlink(part_name, dir_fd=artifact_fd)
                except FileNotFoundError:
                    pass
            for fd in (artifact_fd, model_fd, root_fd):
                if fd is not None:
                    os.close(fd)

    def _failure(
        self,
        status: DownloadResultStatus,
        destination: Path,
        bytes_downloaded: int,
        error: str,
    ) -> DownloadResult:
        return DownloadResult(False, status, destination, bytes_downloaded, error)
