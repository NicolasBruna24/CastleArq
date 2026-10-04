
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

B9.93 — Multi-layer identity contract (documentation only)
==========================================================

This module owns exactly ONE identity layer: **Logical Model**. The multi-layer
contract is a semantic contract, not a set of new classes. No runtime symbol is
introduced to name any other layer, and the representation of the logical model
identity remains the plain ``str`` declared by this module.

The layers and their owners are:

```text
Logical Model      this module (model_identity.py)   <- the only identity
Variant            discovery domain (ModelVariant)      selection unit
Artifact           discovery -> acquisition            acquirable unit
Revision           declared remote provenance           version pointer
Locator            this module + DownloadPlanner         acquisition gate
Storage Identity   ModelStore                            persistence address
```

Each layer below is explicitly NOT the logical model identity:

```text
Variant            a selectable variant of a logical model. It is a selection
                   WITHIN a logical model, never an alternative name for it,
                   and never a second identity.

Artifact           a concrete acquirable artifact (filename, size, sha256,
                   declared metadata). An artifact NEVER redefines the logical
                   identity of its model. The identity an artifact carries is a
                   REFERENCE to the logical model, not an assertion of identity.

Revision           declared provenance/version information for the observed
                   artifact or repository state.

                   revision != logical model identity

                   A revision is never promoted to model identity, and it never
                   participates in artifact identity (``ArtifactSpec.artifact_id``
                   excludes it by the ratified OD-1 decision).

Locator            the ``(source, repository)`` information required to ACQUIRE
                   an artifact. ``downloadable_locator`` is the single predicate
                   for "this logical model can currently be downloaded"; it is an
                   ACQUISITION GATE, not an identity resolver.

                   locator != logical model identity

                   A locator is never stored as an identity and never substituted
                   for one.

Storage Identity   the local persistence address ``<model_id>/<artifact_id>``,
                   derived and sanitised by ``ModelStore``. It is a PERSISTENCE
                   CONCERN, not a model-identity claim; a directory name is never
                   an identity.
```

These additional concepts are likewise NOT the logical model identity:

```text
Filename           an artifact attribute; never an identity and never a
                   basename-based inference source.
Quantization       artifact-level metadata. It participates in artifact
                   identity (``artifact_id``), which is a different layer, and it
                   never replaces or qualifies logical model identity.
Repository         a source locator. A repository is never SILENTLY PROMOTED
                   into a logical model identity: without an explicit entry in
                   ``SOURCE_REPOSITORY_TO_MODEL_ID`` it has no logical identity
                   at all, and this stays true under the ratified 1-repository ->
                   1-logical-model cardinality.
```

Governing rule
--------------

```text
No layer may substitute for or be silently promoted to another layer.
```

Consequences that this module already enforces and that B9.93 ratifies without
altering them:

```text
- Discovery remains identity-free: a discovered artifact carries no logical
  model identity, and identity is re-attached only at the explicit
  discovery-to-acquisition mapping boundary through a caller-supplied resolver.
- Provider-declared metadata is not authoritative identity. Declared metadata is
  L1 and untrusted; a provider never becomes the owner of logical model identity.
- Cardinality is preserved: ``downloadable_locator`` resolves a logical model
  only when it maps to exactly one locator whose source is supported. Zero,
  multiple or unsupported locators yield no result. No 1 -> N repository/model
  mapping exists.
- Unknown identity fails closed and is never inferred, guessed or defaulted.
- The B8.1 representation domain (``castlearq.model_domain``) remains PARALLEL
  and is NOT converged with this contract; no relationship is established here.
```

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
