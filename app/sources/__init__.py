"""External metadata sources for LocalAI Hub."""

from .huggingface import HuggingFaceSource, SourceError

__all__ = ["HuggingFaceSource", "SourceError"]
