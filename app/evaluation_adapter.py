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

"""B9.8: pure adapter from the execution domain to the strict B9.3 domain.

Adapts ``ModelSpec``/``ArtifactSpec`` (``app/models.py``) and a detected
runtime capability into the strict evaluation inputs of B9.3
(``Model``, ``ModelArtifact``, ``EvaluationContext``), composing the B9.7
knowledge bridge for the runtime knowledge. It never executes ``evaluate()``,
never touches production wiring and never turns legacy heuristics into
knowledge (B9.8 design, ratified decisions N-1..N-4):

- Centinels such as ``"Unknown"`` and empty strings become ``None``
  (unknown), never fabricated facts.
- ``ModelSpec.task``, ``supported_runtimes`` (e.g. the composite alias
  ``"llama.cpp / llama.app"``) and ``supported_backends`` are legacy
  recommendations and are NEVER copied into the strict domain.
- ``ModelArtifact.identifier`` is always ``None`` (N-1) and quantization is
  always ``UNKNOWN`` (N-2): a catalogue label never proves quantization or
  precision.
- The runtime is resolved ONLY by exact canonical_id membership against the
  registry's RUNTIME subjects (no fuzzy, no case folding, no substring, no
  invented aliases); the scope stays exactly ``KnowledgeScope()`` in v1 (N-3:
  the raw CLI version string is never turned into ``runtime_version``).
- Backends are canonicalized through the closed declarative table N-4;
  anything outside it becomes ``None`` (UNKNOWN downstream), never
  UNSUPPORTED.

Purity: this module imports neither ``app.runtimes`` (the capability arrives
as an already-built value object; the type hint uses ``TYPE_CHECKING``) nor
any I/O, process, network or environment facility. Same inputs always yield
equal outputs; inputs are never mutated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .compatibility_evaluator import EvaluationContext
from .compatibility_knowledge import (
    KnowledgeKind,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeSubject,
)
from .knowledge_bridge import KnowledgeProjection, project_knowledge
from .model_domain import (
    Model,
    ModelArchitecture,
    ModelArtifact,
    ModelCapabilities,
    ModelIdentity,
    ModelPrecision,
    ModelProvenance,
    ModelQuantization,
    QuantizationStatus,
)
from .models import ArtifactSpec, ModelSpec

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from .runtimes import RuntimeCapability

#: Ratified decision N-4: closed declarative canonical identity table.
CANONICAL_BACKENDS: tuple[tuple[str, str], ...] = (
    ("CPU", "cpu"),
    ("Vulkan", "vulkan"),
    ("CUDA", "cuda"),
    ("ROCm", "rocm"),
    ("HIP", "hip"),
    ("SYCL", "sycl"),
)

_CANONICAL_BACKEND_MAP = dict(CANONICAL_BACKENDS)

_UNKNOWN_SENTINEL = "Unknown"


def _explicit(value: object) -> str | None:
    """Legacy centinels ("Unknown", empty, non-string) become None."""
    if not isinstance(value, str):
        return None
    if not value.strip() or value == _UNKNOWN_SENTINEL:
        return None
    return value


def canonize_backend(backend: str | None) -> str | None:
    """Exact declarative lookup on the closed N-4 table; else None."""
    if backend is None:
        return None
    return _CANONICAL_BACKEND_MAP.get(backend)

def to_model(spec: ModelSpec) -> Model:
    """Adapt a legacy catalogue spec into a strict facts-only ``Model``."""
    if type(spec) is not ModelSpec:
        raise ValueError("spec must be a ModelSpec")
    if not isinstance(spec.name, str) or not spec.name.strip():
        raise ValueError("spec.name must be a non-empty string")
    return Model(
        identity=ModelIdentity(name=spec.name, model_id=spec.id),
        provenance=ModelProvenance(source=_explicit(spec.provider)),
        architecture=ModelArchitecture(
            architecture=_explicit(spec.architecture),
            parameters=(
                None if spec.parameter_count_b is None
                else int(round(spec.parameter_count_b * 1_000_000_000))
            ),
        ),
        max_context=spec.context_length,
        capabilities=ModelCapabilities(),
        artifacts=(),
    )


def to_artifact(spec: ArtifactSpec) -> ModelArtifact:
    """Adapt a legacy artifact spec into a strict ``ModelArtifact`` (N-1, N-2)."""
    if type(spec) is not ArtifactSpec:
        raise ValueError("spec must be an ArtifactSpec")
    return ModelArtifact(
        precision=ModelPrecision(),
        quantization=ModelQuantization(status=QuantizationStatus.UNKNOWN),
        identifier=None,
        format=_explicit(spec.format),
        storage_size_bytes=spec.size_bytes,
    )


def resolve_runtime(
    registry: KnowledgeRegistry, capability: "RuntimeCapability"
) -> KnowledgeSubject:
    """Resolve the canonical RUNTIME subject by EXACT id membership only.

    A runtime subject matches when its ``canonical_id`` equals
    ``capability.name`` or appears exactly in
    ``capability.compatibility_names``. Zero or multiple matches raise
    ``ValueError``; nothing is normalized, folded, substring- or
    similarity-matched, and no alias is ever invented.
    """
    if type(registry) is not KnowledgeRegistry:
        raise ValueError("registry must be a KnowledgeRegistry")
    name = getattr(capability, "name", None)
    names = getattr(capability, "compatibility_names", ())
    if not isinstance(name, str) or not name.strip():
        raise ValueError("capability.name must be a non-empty string")
    if names is None or isinstance(names, str) or not isinstance(
            names, (list, tuple)):
        raise ValueError("capability.compatibility_names must be a sequence")
    provided = (name, *tuple(item for item in names if isinstance(item, str)))

    candidates: list[KnowledgeSubject] = []
    seen: set[str] = set()
    for assertion in registry.entries:
        subject = assertion.subject
        if (subject.kind is not KnowledgeKind.RUNTIME
                or subject.canonical_id in seen):
            continue
        seen.add(subject.canonical_id)
        if any(subject.canonical_id == value for value in provided):
            candidates.append(subject)
    if not candidates:
        raise ValueError(
            "runtime cannot be resolved by exact canonical_id membership")
    if len(candidates) > 1:
        raise ValueError(
            "ambiguous runtime resolution: "
            + ", ".join(sorted(item.canonical_id for item in candidates)))
    return candidates[0]


def runtime_scope(scope: KnowledgeScope | None = None) -> KnowledgeScope:
    """Exact scope for B9.8 v1: default empty, never enriched (N-3)."""
    if scope is None:
        return KnowledgeScope()
    if type(scope) is not KnowledgeScope:
        raise ValueError("scope must be a KnowledgeScope or None")
    return scope


def build_evaluation_context(
    registry: KnowledgeRegistry,
    capability: "RuntimeCapability",
    backend: str | None = None,
    required_capabilities: tuple[str, ...] | list[str] = (),
    scope: KnowledgeScope | None = None,
) -> tuple[EvaluationContext, KnowledgeProjection]:
    """Assemble a strict ``EvaluationContext`` from declared inputs only.

    Composes ``project_knowledge`` (B9.7) with the exact scope and the
    canonical backend. ``required_capabilities`` is passed through untouched
    for B9.3's own taxonomy validation; it is never derived from ``task``,
    from the capability or from the knowledge base. ``evaluate()`` is NOT
    executed here.
    """
    subject = resolve_runtime(registry, capability)
    exact_scope = runtime_scope(scope)
    projection = project_knowledge(registry, subject, exact_scope)
    if not isinstance(required_capabilities, (tuple, list)):
        raise ValueError(
            "required_capabilities must be a tuple or list of strings")
    context = EvaluationContext(
        runtime=projection.runtime_knowledge,
        backend=canonize_backend(backend),
        hardware=None,
        required_capabilities=tuple(required_capabilities),
    )
    return context, projection
