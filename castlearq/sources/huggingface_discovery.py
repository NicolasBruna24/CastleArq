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

"""B9.81: Hugging Face discovery provider (L1 remote metadata only).

Implements the ``ModelDiscovery`` port from B9.80 against the public Hugging
Face model metadata API. Only metadata endpoints under ``/api/models`` are
queried; artifact content is never requested by this module.

Decision R1: the small pure helpers this provider needs (repository and
filename validation, URL construction, declared size/SHA-256 extraction,
quantization detection) are intentionally duplicated here instead of imported
from the acquisition source, so the provider has zero acquisition coupling.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from ..discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelDiscovery,
    ModelVariant,
)

__all__ = ["HuggingFaceDiscoveryProvider"]

PROVIDER_ID = "huggingface"

Transport = Callable[[str, float], "bytes | tuple[bytes, dict[str, str]]"]

_REPOSITORY_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
)
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_REVISION_RE = re.compile(r"[0-9a-fA-F]{40}")
_LINK_NEXT_RE = re.compile(r"<([^<>]+)>\s*;\s*[^,]*rel=\"?next\"?")
_CURSOR_MAX_LENGTH = 8192
_CURSOR_PATH_MAX_LENGTH = 2048


# --- duplicated pure helpers (Decision R1) ---------------------------------


def _validate_repository(repository: str) -> None:
    if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
        raise DiscoveryError("Invalid Hugging Face repository id")


def _validate_filename(filename: str) -> None:
    path = PurePosixPath(filename)
    if (
        not filename
        or path.is_absolute()
        or "\\" in filename
        or any(part in {"", ".", ".."} for part in path.parts)
        or "/" in filename
    ):
        raise DiscoveryError("Unsafe artifact filename")


def _api_origin(api_base: str) -> str:
    parsed = urlparse(api_base)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise DiscoveryError("Hugging Face API host must be https://huggingface.co")
    return f"{parsed.scheme}://{parsed.netloc}"


def _metadata_url(api_base: str, repository: str) -> str:
    return f"{api_base.rstrip('/')}/models/{quote(repository, safe='/')}"


def _tree_metadata_url(api_base: str, repository: str, revision: str | None) -> str:
    ref = quote(revision, safe="") if revision else "main"
    return (
        f"{api_base.rstrip('/')}/models/{quote(repository, safe='/')}"
        f"/tree/{ref}?recursive=true"
    )


def _download_url(repository: str, filename: str) -> str:
    url = (
        f"https://huggingface.co/{quote(repository, safe='/')}"
        f"/resolve/main/{quote(filename, safe='')}"
    )
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        raise DiscoveryError("Invalid Hugging Face download URL")
    return url


def _extract_size(entry: dict[str, object]) -> int | None:
    value = entry.get("size")
    if value is None and isinstance(entry.get("lfs"), dict):
        value = entry["lfs"].get("size")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DiscoveryError("Invalid artifact size")
    return value


def _extract_sha256(entry: dict[str, object]) -> str | None:
    lfs = entry.get("lfs")
    value = lfs.get("oid") if isinstance(lfs, dict) else None
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise DiscoveryError("Invalid artifact SHA-256")
    return value.lower()


def detect_quantization(filename: str) -> str:
    """Return a conservative quantization match from a GGUF filename."""
    match = re.search(
        r"(?<![A-Za-z0-9])"
        r"(Q(?:2_K|3_K(?:_[SML])?|4_(?:K(?:_[SML])?|0)|5_(?:K(?:_[SML])?|0)|6_K|8_0))"
        r"(?![A-Za-z0-9])",
        filename.upper().replace("-", "_"),
    )
    return match.group(1) if match else "Unknown"


# --- metadata helpers -------------------------------------------------------


def _opt_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _sanitize_tags(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    tags: list[str] = []
    for tag in value:
        if isinstance(tag, str) and tag.strip() and tag not in tags:
            tags.append(tag)
    return tuple(tags)


def _declared_architecture(payload: dict[str, object]) -> str | None:
    config = payload.get("config")
    if isinstance(config, dict):
        return _opt_str(config.get("model_type"))
    return None


def _entry_has_gguf(entry: dict[str, object], tags: tuple[str, ...]) -> bool:
    siblings = entry.get("siblings")
    if isinstance(siblings, list):
        for sibling in siblings:
            if not isinstance(sibling, dict):
                continue
            filename = sibling.get("rfilename")
            if isinstance(filename, str) and filename.lower().endswith(".gguf"):
                return True
    return any(tag.lower() == "gguf" for tag in tags)


def _declared_revision(value: object) -> str | None:
    if isinstance(value, str) and _REVISION_RE.fullmatch(value):
        return value
    return None


def _candidate_from_entry(entry: object) -> ModelCandidate | None:
    if not isinstance(entry, dict):
        return None
    repository = entry.get("id")
    if not isinstance(repository, str):
        repository = entry.get("modelId")
    if not isinstance(repository, str):
        return None
    _validate_repository(repository)
    tags = _sanitize_tags(entry.get("tags"))
    return ModelCandidate(
        provider_id=PROVIDER_ID,
        repository=repository,
        display_name=_opt_str(entry.get("displayName")),
        author=_opt_str(entry.get("author")),
        description=_opt_str(entry.get("description")),
        tags=tags,
        declared_architecture=_declared_architecture(entry),
        has_gguf=_entry_has_gguf(entry, tags),
    )


# --- opaque cursor ----------------------------------------------------------


def _encode_cursor(next_url: str) -> str:
    parsed = urlparse(next_url)
    if parsed.scheme and (parsed.scheme != "https" or parsed.netloc != "huggingface.co"):
        raise DiscoveryError("Unexpected pagination link host")
    path = parsed.path
    if not _is_safe_cursor_path(path):
        raise DiscoveryError("Unexpected pagination link path")
    query = parsed.query
    if "://" in query or "#" in query or "\\" in query or _has_control_chars(query):
        raise DiscoveryError("Unexpected pagination link query")
    token = {"v": 1, "p": path, "q": query}
    raw = json.dumps(token, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, api_base: str) -> str:
    if not cursor or len(cursor) > _CURSOR_MAX_LENGTH:
        raise DiscoveryError("Invalid discovery cursor")
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        token = json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        raise DiscoveryError("Invalid discovery cursor") from error
    if not isinstance(token, dict) or set(token) != {"v", "p", "q"}:
        raise DiscoveryError("Invalid discovery cursor payload")
    if token["v"] != 1:
        raise DiscoveryError("Unsupported discovery cursor version")
    path, query = token["p"], token["q"]
    if not isinstance(path, str) or len(path) > _CURSOR_PATH_MAX_LENGTH:
        raise DiscoveryError("Invalid discovery cursor path")
    if not _is_safe_cursor_path(path):
        raise DiscoveryError("Invalid discovery cursor path")
    if not isinstance(query, str) or len(query) > _CURSOR_MAX_LENGTH:
        raise DiscoveryError("Invalid discovery cursor query")
    if "://" in query or "#" in query or "\\" in query or _has_control_chars(query):
        raise DiscoveryError("Invalid discovery cursor query")
    origin = _api_origin(api_base)
    url = f"{origin}{path}"
    return f"{url}?{query}" if query else url


def _is_safe_cursor_path(path: str) -> bool:
    return (
        path.startswith("/api/")
        and ".." not in path
        and "//" not in path
        and "\\" not in path
        and "?" not in path
        and "#" not in path
        and not _has_control_chars(path)
    )


def _has_control_chars(value: str) -> bool:
    return any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)


def _next_cursor(headers: dict[str, str], api_base: str) -> str | None:
    link = headers.get("link")
    if not link:
        return None
    match = _LINK_NEXT_RE.search(link)
    if match is None:
        return None
    return _encode_cursor(match.group(1))


def _http_get(url: str, timeout: float) -> tuple[bytes, dict[str, str]]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "CastleArq"})
    with urlopen(request, timeout=timeout) as response:
        headers = {name.lower(): value for name, value in response.headers.items()}
        return response.read(), headers


@dataclass(frozen=True)
class HuggingFaceDiscoveryProvider(ModelDiscovery):
    """``ModelDiscovery`` provider backed by the Hugging Face metadata API."""

    api_base: str = "https://huggingface.co/api"
    timeout: float = 10.0
    transport: Transport | None = None

    # --- port ---------------------------------------------------------------
    def search(self, query, *, limit=20, cursor=None):
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an int between 1 and 1000")
        if cursor is not None and not isinstance(cursor, str):
            raise TypeError("cursor must be a string or None")
        _api_origin(self.api_base)
        if cursor is None:
            url = self._search_url(query, limit)
        else:
            url = _decode_cursor(cursor, self.api_base)
        payload, headers = self._request(url)
        if not isinstance(payload, list):
            raise DiscoveryError("Hugging Face search response must be a list")
        candidates: list[ModelCandidate] = []
        for entry in payload:
            candidate = _candidate_from_entry(entry)
            if candidate is not None:
                candidates.append(candidate)
        return tuple(candidates), _next_cursor(headers, self.api_base)

    def inspect(self, repository):
        if not isinstance(repository, str):
            raise TypeError("repository must be a string")
        _validate_repository(repository)
        _api_origin(self.api_base)
        metadata, _ = self._request(_metadata_url(self.api_base, repository))
        if not isinstance(metadata, dict):
            raise DiscoveryError("Hugging Face model metadata must be an object")
        revision = _declared_revision(metadata.get("sha"))
        tree, _ = self._request(_tree_metadata_url(self.api_base, repository, revision))
        if not isinstance(tree, list):
            raise DiscoveryError("Hugging Face tree metadata must be a list")
        artifacts = self._gguf_artifacts(repository, tree, revision)
        if not artifacts:
            return ()
        candidate = ModelCandidate(
            provider_id=PROVIDER_ID,
            repository=repository,
            display_name=_opt_str(metadata.get("displayName")),
            author=_opt_str(metadata.get("author")),
            description=_opt_str(metadata.get("description")),
            tags=_sanitize_tags(metadata.get("tags")),
            declared_architecture=_declared_architecture(metadata),
            has_gguf=True,
        )
        return _group_variants(candidate, artifacts)

    # --- internals ----------------------------------------------------------
    def _search_url(self, query: str, limit: int) -> str:
        params = [f"limit={limit}", "full=true"]
        if query:
            params.append(f"search={quote(query, safe='')}")
        return f"{self.api_base.rstrip('/')}/models?{'&'.join(params)}"

    def _gguf_artifacts(
        self,
        repository: str,
        tree: list[object],
        revision: str | None,
    ) -> list[DiscoveredArtifact]:
        artifacts: list[DiscoveredArtifact] = []
        for entry in tree:
            if not isinstance(entry, dict):
                continue
            filename = entry.get("path")
            if not isinstance(filename, str) or not filename.lower().endswith(".gguf"):
                continue
            if entry.get("type") == "directory":
                continue
            _validate_filename(filename)
            artifacts.append(
                DiscoveredArtifact(
                    repository=repository,
                    filename=filename,
                    format="GGUF",
                    declared_quantization=detect_quantization(filename),
                    model_id=None,
                    source=PROVIDER_ID,
                    download_url=_download_url(repository, filename),
                    declared_size=_extract_size(entry),
                    declared_sha256=_extract_sha256(entry),
                    revision=revision,
                )
            )
        return artifacts

    def _request(self, url: str) -> tuple[object, dict[str, str]]:
        try:
            raw = (self.transport or _http_get)(url, self.timeout)
        except HTTPError as error:
            raise DiscoveryError(
                f"Hugging Face metadata request failed: HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise DiscoveryError(f"Hugging Face metadata request failed: {error}") from error
        body, headers = _normalize_response(raw)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DiscoveryError("Hugging Face returned invalid JSON") from error
        return payload, headers


def _normalize_response(raw: object) -> tuple[bytes, dict[str, str]]:
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw), {}
    if isinstance(raw, tuple) and len(raw) == 2:
        body, headers = raw
        if not isinstance(body, (bytes, bytearray)):
            raise DiscoveryError("Invalid transport result")
        try:
            normalized = {str(k).lower(): str(v) for k, v in dict(headers).items()}
        except (TypeError, ValueError) as error:
            raise DiscoveryError("Invalid transport result headers") from error
        return bytes(body), normalized
    raise DiscoveryError("Invalid transport result")


def _group_variants(
    candidate: ModelCandidate,
    artifacts: list[DiscoveredArtifact],
) -> tuple[ModelVariant, ...]:
    groups: dict[str, list[DiscoveredArtifact]] = {}
    for artifact in sorted(artifacts, key=lambda item: item.filename):
        groups.setdefault(artifact.declared_quantization, []).append(artifact)
    return tuple(
        ModelVariant(
            candidate=candidate,
            declared_quantization=quantization,
            artifacts=tuple(groups[quantization]),
        )
        for quantization in sorted(groups)
    )
