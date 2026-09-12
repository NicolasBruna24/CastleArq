"""Small source interface for remote model metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ArtifactSpec


class ModelSource(ABC):
    @abstractmethod
    def discover_artifacts(self, repository: str) -> list[ArtifactSpec]:
        """Return downloadable metadata without downloading artifact content."""
        raise NotImplementedError
