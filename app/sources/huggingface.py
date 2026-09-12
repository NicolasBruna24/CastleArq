"""Hugging Face repository metadata discovery.

Only the public model metadata API is queried. Artifact content is never
requested by this module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .base import ModelSource
from ..models import ArtifactSpec, ArtifactState


class SourceError(Exception):
    """Controlled error raised for invalid or unavailable source metadata."""


Transport = Callable[[str, float], bytes]


@dataclass(frozen=True)
class HuggingFaceSource(ModelSource):
    api_base: str = "https://huggingface.co/api"
    timeout: float = 10.0
    transport: Transport | None = None

    def discover_artifacts(self, repository: str) -> list[ArtifactSpec]:
        _validate_repository(repository)
        api_url = _metadata_url(self.api_base, repository)
        payload = self._get_json(api_url)
        files = payload.get("siblings")
        if files is None:
            files = payload.get("files")
        if not isinstance(files, list):
            raise SourceError("Hugging Face response does not contain a file list")

        artifacts: list[ArtifactSpec] = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            artifact = self._artifact_from_file(repository, entry)
            if artifact is not None:
                artifacts.append(artifact)
        return artifacts

    def _get_json(self, url: str) -> dict[str, object]:
        try:
            raw = (self.transport or _http_get)(url, self.timeout)
            payload = json.loads(raw.decode("utf-8"))
        except HTTPError as error:
            raise SourceError(f"Hugging Face metadata request failed: HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise SourceError(f"Hugging Face metadata request failed: {error}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceError("Hugging Face returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise SourceError("Hugging Face returned an invalid metadata object")
        return payload

    def _artifact_from_file(
        self, repository: str, entry: dict[str, object]
    ) -> ArtifactSpec | None:
        filename = entry.get("rfilename", entry.get("path"))
        if not isinstance(filename, str) or not filename.lower().endswith(".gguf"):
            return None
        _validate_filename(filename)
        size = _extract_size(entry)
        sha256 = _extract_sha256(entry)
        url = _download_url(repository, filename)
        quantization = detect_quantization(filename)
        return ArtifactSpec(
            model_id=repository,
            source="huggingface",
            repository=repository,
            filename=filename,
            format="GGUF",
            quantization=quantization,
            download_url=url,
            size_bytes=size,
            sha256=sha256,
            state=ArtifactState.NOT_DOWNLOADED,
        )


def detect_quantization(filename: str) -> str:
    """Return a conservative quantization match from a GGUF filename."""
    match = re.search(
        r"(?<![A-Za-z0-9])"
        r"(Q(?:2_K|3_K(?:_[SML])?|4_(?:K(?:_[SML])?|0)|5_(?:K(?:_[SML])?|0)|6_K|8_0))"
        r"(?![A-Za-z0-9])",
        filename.upper().replace("-", "_"),
    )
    return match.group(1) if match else "Unknown"


def _validate_repository(repository: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}", repository):
        raise SourceError("Invalid Hugging Face repository id")


def _validate_filename(filename: str) -> None:
    from pathlib import PurePosixPath

    path = PurePosixPath(filename)
    if (
        not filename
        or path.is_absolute()
        or "\\" in filename
        or any(part in {"", ".", ".."} for part in path.parts)
        or "/" in filename
    ):
        raise SourceError("Unsafe artifact filename")


def _metadata_url(api_base: str, repository: str) -> str:
    parsed = urlparse(api_base)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise SourceError("Hugging Face API host must be https://huggingface.co")
    return f"{api_base.rstrip('/')}/models/{quote(repository, safe='/')}"


def _download_url(repository: str, filename: str) -> str:
    url = f"https://huggingface.co/{quote(repository, safe='/')}/resolve/main/{quote(filename)}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise SourceError("Invalid Hugging Face download URL")
    return url


def _extract_size(entry: dict[str, object]) -> int | None:
    value = entry.get("size")
    if value is None and isinstance(entry.get("lfs"), dict):
        value = entry["lfs"].get("size")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceError("Invalid artifact size")
    return value


def _extract_sha256(entry: dict[str, object]) -> str | None:
    lfs = entry.get("lfs")
    value = lfs.get("sha256") if isinstance(lfs, dict) else None
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise SourceError("Invalid artifact SHA-256")
    return value.lower()


def _http_get(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "LocalAI-Hub"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()
