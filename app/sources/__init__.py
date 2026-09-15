"""External metadata sources for CastleArq."""

from .huggingface import HuggingFaceSource, SourceError

__all__ = ["HuggingFaceSource", "SourceError"]
