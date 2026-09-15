"""Streaming artifact downloads with safe HTTP Range resume.

This module intentionally excludes retries and manifest management. A
completed temporary file is published without replacing an existing artifact.
"""

from __future__ import annotations

import os
import re
import stat
import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable, Mapping
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
    CHECKSUM_MISMATCH = "checksum_mismatch"
    RESUME_NOT_SUPPORTED = "resume_not_supported"
    RANGE_NOT_SATISFIABLE = "range_not_satisfiable"
    INVALID_CONTENT_RANGE = "invalid_content_range"
    PARTIAL_TOO_LARGE = "partial_too_large"
    PARTIAL_COMPLETE_UNVERIFIED = "partial_complete_unverified"


@dataclass(frozen=True)
class DownloadResult:
    success: bool
    status: DownloadResultStatus
    destination: Path | None
    bytes_downloaded: int
    error: str | None = None


ResponseOpener = Callable[..., BinaryIO]


def _open_url(
    url: str, timeout: float, headers: Mapping[str, str] | None = None
) -> BinaryIO:
    request_headers = {"User-Agent": "CastleArq"}
    if headers:
        request_headers.update(headers)
    return urlopen(
        Request(url, headers=request_headers),
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
            part_exists = False
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
                part_exists = True

            expected_size = artifact.size_bytes
            if part_exists:
                part_fd = os.open(
                    part_name,
                    os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW,
                    dir_fd=artifact_fd,
                )
                partial_size = os.fstat(part_fd).st_size
                if expected_size is not None and partial_size > expected_size:
                    return self._failure(
                        DownloadResultStatus.PARTIAL_TOO_LARGE,
                        destination,
                        partial_size,
                        "Partial file is larger than expected artifact",
                    )
                if (
                    expected_size is not None
                    and partial_size == expected_size
                    and artifact.sha256 is None
                ):
                    return self._failure(
                        DownloadResultStatus.PARTIAL_COMPLETE_UNVERIFIED,
                        destination,
                        partial_size,
                        "Partial file has expected size but is not verified",
                    )
                offset = partial_size
            else:
                part_fd = os.open(
                    part_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=artifact_fd,
                )
                created_part = True
                offset = 0
            bytes_downloaded = offset
            observed_size = expected_size
            response = None
            try:
                if not (
                    part_exists
                    and expected_size is not None
                    and offset == expected_size
                ):
                    headers = {"Range": f"bytes={offset}-"} if part_exists else {}
                    response = self._open_response(artifact.download_url or "", headers)
                    response_status = _response_status(response)
                else:
                    response_status = None
                if part_exists and response_status is not None:
                    if response_status == 200:
                        return self._failure(
                            DownloadResultStatus.RESUME_NOT_SUPPORTED,
                            destination,
                            offset,
                            "Server ignored the Range request",
                        )
                    if response_status == 416:
                        return self._failure(
                            DownloadResultStatus.RANGE_NOT_SATISFIABLE,
                            destination,
                            offset,
                            "Range is not satisfiable",
                        )
                    if response_status != 206:
                        return self._failure(
                            DownloadResultStatus.INVALID_CONTENT_RANGE,
                            destination,
                            offset,
                            f"Expected HTTP 206, received {response_status}",
                        )
                    try:
                        range_start, range_end, range_total = _parse_content_range(
                            _response_header(response, "Content-Range")
                        )
                    except ValueError as error:
                        return self._failure(
                            DownloadResultStatus.INVALID_CONTENT_RANGE,
                            destination,
                            offset,
                            str(error),
                        )
                    if range_start != offset or range_end < range_start:
                        return self._failure(
                            DownloadResultStatus.INVALID_CONTENT_RANGE,
                            destination,
                            offset,
                            "Content-Range does not match the local offset",
                        )
                    if expected_size is not None and range_total != expected_size:
                        return self._failure(
                            DownloadResultStatus.INVALID_CONTENT_RANGE,
                            destination,
                            offset,
                            "Content-Range total differs from expected size",
                        )
                    if observed_size is None:
                        observed_size = range_total
                if response is not None:
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
                if part_exists and error.code == 416:
                    return self._failure(
                        DownloadResultStatus.RANGE_NOT_SATISFIABLE,
                        destination,
                        offset,
                        "Range is not satisfiable",
                    )
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

            if observed_size is not None and bytes_downloaded != observed_size:
                return self._failure(
                    DownloadResultStatus.SIZE_MISMATCH,
                    destination,
                    bytes_downloaded,
                    "Downloaded size differs from artifact metadata",
                )
            if artifact.sha256 is not None:
                try:
                    actual_sha256 = self._sha256_partial(part_name, artifact_fd)
                except OSError as error:
                    created_part = False
                    return self._failure(
                        DownloadResultStatus.FILESYSTEM_ERROR,
                        destination,
                        bytes_downloaded,
                        str(error),
                    )
                if not hmac.compare_digest(actual_sha256, artifact.sha256.lower()):
                    created_part = False
                    return self._failure(
                        DownloadResultStatus.CHECKSUM_MISMATCH,
                        destination,
                        bytes_downloaded,
                        "Downloaded artifact checksum does not match metadata",
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

    def _sha256_partial(self, part_name: str, artifact_fd: int) -> str:
        read_fd = os.open(
            part_name,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=artifact_fd,
        )
        try:
            digest = hashlib.sha256()
            while True:
                chunk = os.read(read_fd, self.chunk_size)
                if not chunk:
                    return digest.hexdigest()
                digest.update(chunk)
        finally:
            os.close(read_fd)

    def _open_response(self, url: str, headers: Mapping[str, str]) -> BinaryIO:
        if headers:
            try:
                return self.opener(url, self.timeout, headers)
            except TypeError:
                raise TypeError(
                    "Injected opener must accept headers for resume requests"
                )
        return self.opener(url, self.timeout)

    def _failure(
        self,
        status: DownloadResultStatus,
        destination: Path,
        bytes_downloaded: int,
        error: str,
    ) -> DownloadResult:
        return DownloadResult(False, status, destination, bytes_downloaded, error)


def _response_status(response: BinaryIO) -> int:
    status = getattr(response, "status", None)
    if status is None and hasattr(response, "getcode"):
        status = response.getcode()
    return int(status) if status is not None else 200


def _response_header(response: BinaryIO, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        value = headers.get(name)
        if value is not None:
            return str(value)
    if hasattr(response, "getheader"):
        value = response.getheader(name)
        return str(value) if value is not None else None
    return None


def _parse_content_range(value: str | None) -> tuple[int, int, int | None]:
    if value is None:
        raise ValueError("206 response is missing Content-Range")
    match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", value)
    if not match:
        raise ValueError("Invalid Content-Range")
    start = int(match.group(1))
    end = int(match.group(2))
    total = int(match.group(3))
    if total <= end or total <= 0:
        raise ValueError("Invalid Content-Range total")
    return start, end, total
