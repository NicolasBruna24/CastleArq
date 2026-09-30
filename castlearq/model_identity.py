
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


# Sources the current download flow is able to fetch from.
SUPPORTED_DOWNLOAD_SOURCES: frozenset[str] = frozenset({"huggingface"})


def downloadable_locator(model_id: str) -> tuple[str, str] | None:
    """Return the single downloadable ``(source, repository)`` locator, or None.

    This is the one predicate for "this logical model can currently be
    downloaded". It is explicit and deterministic: a model qualifies only when
    it maps to exactly one locator AND that locator's source is supported by the
    download flow. Zero, multiple or unsupported locators never yield a result;
    there is no first-match, no fuzzy or substring matching, no aliases, no I/O,
    no network access and no local paths involved.
    """
    locators = source_repositories_for_logical_model(model_id)
    if len(locators) != 1:
        return None
    source, repository = locators[0]
    if source not in SUPPORTED_DOWNLOAD_SOURCES:
        return None
    return locators[0]
