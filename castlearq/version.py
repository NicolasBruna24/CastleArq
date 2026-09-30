"""Distribution version resolution for CastleArq."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path


def get_version() -> str:
    """Return the installed distribution version, with source fallback."""
    try:
        return importlib.metadata.version("castlearq")
    except importlib.metadata.PackageNotFoundError:
        path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            version = data["project"]["version"]
            return str(version) if version else "unknown"
        except (OSError, KeyError, TypeError, ValueError):
            return "unknown"
