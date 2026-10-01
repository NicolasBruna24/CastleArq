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

"""B9.80: Model Discovery domain contract (L1 remote metadata only)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

__all__ = [
    "DiscoveredArtifact",
    "DiscoveryError",
    "ModelCandidate",
    "ModelDiscovery",
    "ModelVariant",
]


class DiscoveryError(Exception):
    """Domain error for the discovery port; independent from SourceError."""


def _need(name, v):
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _opt(name, v):
    if v is not None and (not isinstance(v, str) or not v.strip()):
        raise ValueError(f"{name} must be a non-empty string or None")


@dataclass(frozen=True)
class ModelCandidate:
    """One remote search hit (L1 untrusted metadata). No L2/L3 fields."""

    provider_id: str
    repository: str
    display_name: str | None = None
    author: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    declared_architecture: str | None = None
    has_gguf: bool = False

    def __post_init__(self):
        _need("provider_id", self.provider_id)
        _need("repository", self.repository)
        _opt("display_name", self.display_name)
        _opt("author", self.author)
        _opt("description", self.description)
        _opt("declared_architecture", self.declared_architecture)
        if isinstance(self.tags, list):
            object.__setattr__(self, "tags", tuple(self.tags))
        if not isinstance(self.tags, tuple):
            raise ValueError("tags must be a tuple of str")
        for t in self.tags:
            if not isinstance(t, str) or not t.strip():
                raise ValueError("tags must contain non-empty strings only")
        if not isinstance(self.has_gguf, bool):
            raise ValueError("has_gguf must be a bool")


@dataclass(frozen=True)
class DiscoveredArtifact:
    """One remote declared artifact (L1). Declared != verified."""

    repository: str
    filename: str
    format: str = "Unknown"
    declared_quantization: str = "Unknown"
    model_id: str | None = None
    source: str | None = None
    download_url: str | None = None
    declared_size: int | None = None
    declared_sha256: str | None = None
    revision: str | None = None

    def __post_init__(self):
        _need("repository", self.repository)
        _need("filename", self.filename)
        _need("format", self.format)
        _need("declared_quantization", self.declared_quantization)
        _opt("model_id", self.model_id)
        _opt("source", self.source)
        _opt("download_url", self.download_url)
        _opt("revision", self.revision)
        if self.declared_size is not None:
            if isinstance(self.declared_size, bool):
                raise ValueError("declared_size must be a non-negative int or None")
            if not isinstance(self.declared_size, int) or self.declared_size < 0:
                raise ValueError("declared_size must be a non-negative int or None")
        if self.declared_sha256 is not None:
            if not isinstance(self.declared_sha256, str) or not self.declared_sha256.strip():
                raise ValueError("declared_sha256 must be a non-empty string or None")


@dataclass(frozen=True)
class ModelVariant:
    """One remote declared grouping (L1). Requires >= 1 artifact."""

    candidate: ModelCandidate
    declared_quantization: str
    artifacts: tuple[DiscoveredArtifact, ...] = ()

    def __post_init__(self):
        if not isinstance(self.candidate, ModelCandidate):
            raise ValueError("candidate must be a ModelCandidate")
        _need("declared_quantization", self.declared_quantization)
        if isinstance(self.artifacts, list):
            object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if not isinstance(self.artifacts, tuple) or len(self.artifacts) < 1:
            raise ValueError("artifacts must contain at least one DiscoveredArtifact")
        for a in self.artifacts:
            if not isinstance(a, DiscoveredArtifact):
                raise ValueError("artifacts must contain DiscoveredArtifact only")


class ModelDiscovery(ABC):
    """Domain port for remote discovery (L1 boundary, ABC convention)."""

    @abstractmethod
    def search(self, query, *, limit=20, cursor=None):
        """Return (candidates, next_cursor); cursor is opaque."""
        raise NotImplementedError

    @abstractmethod
    def inspect(self, repository):
        """Return remote declared variants for repository (L1)."""
        raise NotImplementedError
