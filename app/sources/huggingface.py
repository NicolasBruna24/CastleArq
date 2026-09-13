"""Hugging Face repository metadata discovery.

Only the public model metadata API is queried. Artifact content is never
requested by this module.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .base import ModelSource
from ..model_identity import logical_model_id
from ..models import ArtifactSpec, ArtifactState


class SourceError(Exception):
    """Controlled error raised for invalid or unavailable source metadata."""


Transport = Callable[[str, float], bytes]


def _default_model_id(repository: str) -> str | None:
    return logical_model_id("huggingface", repository)


@dataclass(frozen=True)
class HuggingFaceSource(ModelSource):
    api_base: str = "https://huggingface.co/api"
    timeout: float = 10.0
    transport: Transport | None = None
    model_id_provider: Callable[[str], str | None] | None = None

    def _logical_model_id(self, repository: str) -> str | None:
        provider = self.model_id_provider or _default_model_id
        return provider(repository)

    def discover_artifacts(self, repository: str) -> list[ArtifactSpec]:
        _validate_repository(repository)
        model_id = self._logical_model_id(repository)
        if model_id is None:
            raise SourceError(
                f"Repository is not mapped to a catalog model: {repository}"
            )
        api_url = _metadata_url(self.api_base, repository)
        payload = self._get_json(api_url)
        if not isinstance(payload, dict):
            raise SourceError("Hugging Face model metadata must be an object")
        files = payload.get("siblings")
        if files is None:
            files = payload.get("files")
        if not isinstance(files, list):
            raise SourceError("Hugging Face response does not contain a file list")

        artifacts: list[ArtifactSpec] = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            artifact = self._artifact_from_file(model_id, repository, entry)
            if artifact is not None:
                artifacts.append(artifact)
        if any(
            artifact.size_bytes is None or artifact.sha256 is None
            for artifact in artifacts
        ):
            tree = self._get_json(_tree_metadata_url(self.api_base, repository))
            artifacts = _enrich_from_tree(artifacts, tree)
        return artifacts

    def _get_json(self, url: str) -> dict[str, object] | list[object]:
        try:
            raw = (self.transport or _http_get)(url, self.timeout)
            payload = json.loads(raw.decode("utf-8"))
        except HTTPError as error:
            raise SourceError(f"Hugging Face metadata request failed: HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise SourceError(f"Hugging Face metadata request failed: {error}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceError("Hugging Face returned invalid JSON") from error
        if not isinstance(payload, (dict, list)):
            raise SourceError("Hugging Face returned invalid metadata")
        return payload

    def _artifact_from_file(
        self, model_id: str, repository: str, entry: dict[str, object]
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
            model_id=model_id,
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


def _tree_metadata_url(api_base: str, repository: str) -> str:
    parsed = urlparse(api_base)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise SourceError("Hugging Face API host must be https://huggingface.co")
    return f"{api_base.rstrip('/')}/models/{quote(repository, safe='/')}/tree/main?recursive=true"


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


def _enrich_from_tree(
    artifacts: list[ArtifactSpec], payload: dict[str, object] | list[object]
) -> list[ArtifactSpec]:
    if not isinstance(payload, list):
        return artifacts
    entries = {
        entry.get("path"): entry
        for entry in payload
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    enriched: list[ArtifactSpec] = []
    for artifact in artifacts:
        entry = entries.get(artifact.filename)
        if not isinstance(entry, dict):
            enriched.append(artifact)
            continue
        size = artifact.size_bytes
        if size is None:
            size = _extract_size(entry)
        sha256 = artifact.sha256
        if sha256 is None:
            sha256 = _extract_tree_oid(entry)
        enriched.append(replace(artifact, size_bytes=size, sha256=sha256))
    return enriched


def _extract_tree_oid(entry: dict[str, object]) -> str | None:
    lfs = entry.get("lfs")
    value = lfs.get("oid") if isinstance(lfs, dict) else None
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return value.lower()
    return None


def _http_get(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "LocalAI-Hub"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()
