"""Deterministic, non-heuristic explicit selection of model artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from .models import ArtifactSpec


class ArtifactSelectionError(Exception):
    """Raised when explicit or implicit artifact selection cannot be completed."""


def _validate_selector_filename(filename: str) -> None:
    if not isinstance(filename, str):
        raise ArtifactSelectionError("Filename selector must be a string")
    filename = filename.strip()
    if not filename:
        raise ArtifactSelectionError("Filename selector must not be empty")

    path = PurePosixPath(filename)
    if (
        path.is_absolute()
        or "\\" in filename
        or "/" in filename
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise ArtifactSelectionError(f"Unsafe or invalid filename selector: {filename!r}")


def _validate_selector_quantization(quantization: str) -> str:
    if not isinstance(quantization, str):
        raise ArtifactSelectionError("Quantization selector must be a string")
    cleaned = quantization.strip()
    if not cleaned:
        raise ArtifactSelectionError("Quantization selector must not be empty")
    return cleaned


def select_artifact(
    artifacts: list[ArtifactSpec],
    *,
    quantization: str | None = None,
    filename: str | None = None,
) -> ArtifactSpec:
    """Select exactly one ArtifactSpec using explicit, non-heuristic rules.

    - When no selectors are given:
      - 1 artifact: selected.
      - 0 artifacts: raises ArtifactSelectionError.
      - >1 artifacts: raises ArtifactSelectionError with ambiguity details.
    - When selectors are given (--quantization, --filename, or both):
      - Filters are applied cumulatively (AND logic).
      - Quantization matching is exact (case-insensitive).
      - Filename matching is exact (case-sensitive).
      - Exactly 1 match: selected.
      - 0 matches: raises ArtifactSelectionError.
      - >1 matches: raises ArtifactSelectionError (e.g. sharded quantization).
    """
    if not isinstance(artifacts, list):
        raise ArtifactSelectionError("Artifacts must be a list")

    norm_quant: str | None = None
    if quantization is not None:
        norm_quant = _validate_selector_quantization(quantization).upper()

    norm_filename: str | None = None
    if filename is not None:
        _validate_selector_filename(filename)
        norm_filename = filename.strip()

    has_selector = norm_quant is not None or norm_filename is not None

    if not has_selector:
        if not artifacts:
            raise ArtifactSelectionError("No GGUF artifacts found")
        if len(artifacts) == 1:
            return artifacts[0]
        raise ArtifactSelectionError(
            "Model maps to multiple artifacts; specify --quantization or --filename"
        )

    matched = list(artifacts)

    if norm_quant is not None:
        matched = [
            a for a in matched
            if isinstance(a.quantization, str) and a.quantization.upper() == norm_quant
        ]
        if not matched:
            raise ArtifactSelectionError(
                f"No artifact matches quantization {quantization!r}"
            )

    if norm_filename is not None:
        matched = [a for a in matched if a.filename == norm_filename]
        if not matched:
            if norm_quant is not None:
                raise ArtifactSelectionError(
                    f"No artifact matches both quantization {quantization!r} "
                    f"and filename {filename!r}"
                )
            raise ArtifactSelectionError(
                f"No artifact matches filename {filename!r}"
            )

    if len(matched) > 1:
        if norm_filename is None:
            raise ArtifactSelectionError(
                f"Multiple artifacts match quantization {quantization!r}; "
                "specify --filename to disambiguate"
            )
        raise ArtifactSelectionError(
            f"Multiple artifacts match filename {filename!r}"
        )

    return matched[0]

