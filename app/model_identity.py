"""Explicit identity mapping between source repositories and logical models.

``ModelSpec.model_id`` is the canonical logical model identity. ``ArtifactSpec.
model_id`` must always reference that same logical identity and must never
carry a source repository. This table is the single explicit bridge between a
``(source, repository)`` locator and the logical model it belongs to. There is
no fuzzy or basename-based inference: repositories without an entry here have
no logical identity and must be rejected by discovery, planning and migration.
"""

from __future__ import annotations

# (source, repository) -> logical model ID (ModelSpec.model_id)
SOURCE_REPOSITORY_TO_MODEL_ID: dict[tuple[str, str], str] = {
    ("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"): (
        "qwen2.5-coder-7b-instruct"
    ),
}


def logical_model_id(source: str, repository: str) -> str | None:
    """Return the canonical logical model ID for a source locator, or None."""
    return SOURCE_REPOSITORY_TO_MODEL_ID.get((source, repository))


def source_repositories_for_logical_model(
    model_id: str,
) -> tuple[tuple[str, str], ...]:
    """Return the ``(source, repository)`` locators mapped to a logical model ID.

    The result is sorted so it is deterministic, and it is a pure read of the
    static mapping above: no I/O and no network access. Multiple locators are
    never collapsed into one; callers that require a single downloadable source
    must check the returned length themselves.
    """
    return tuple(
        sorted(
            (source, repository)
            for (source, repository), logical in SOURCE_REPOSITORY_TO_MODEL_ID.items()
            if logical == model_id
        )
    )
