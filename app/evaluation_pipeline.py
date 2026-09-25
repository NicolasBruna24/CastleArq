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

"""B9.9: strict evaluation pipeline -- pure composition, no interpretation.

Composes the already-ratified blocks into one deterministic call:

    B9.8 adapter (ModelSpec/ArtifactSpec/RuntimeCapability → strict domain)
        + D-1 canonical format table
    B9.7 bridge (KnowledgeRegistry → KnowledgeProjection/RuntimeKnowledge)
    B9.3 evaluator (evaluate(model, artifact, context))

and returns a frozen :class:`StrictEvaluation` carrying the adapted inputs,
the evaluation context, the full ``KnowledgeProjection`` traceability and the
strict B9.3 ``CompatibilityResult``.

B9.9 adds NO knowledge and NO interpretation: it never derives capabilities
from ``task`` or model names, never derives precision/quantization/identity
from labels, never converts UNKNOWN or absence into UNSUPPORTED, never
resolves conflicts and never produces legacy recommendations. Production
wiring and decision policy belong to a future block (B9.10).

Purity: this module imports neither ``app.runtimes`` in runtime (the
capability arrives as an already-built value object; ``TYPE_CHECKING`` for
the hint, same pattern as B9.8) nor any I/O, process, network or environment
facility. Same inputs always yield an equal output; inputs are never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .compatibility_evaluator import (
    CompatibilityResult,
    EvaluationContext,
    evaluate,
)
from .compatibility_knowledge import KnowledgeRegistry, KnowledgeScope
from .evaluation_adapter import build_evaluation_context, to_artifact, to_model
from .knowledge_bridge import KnowledgeProjection
from .model_domain import Model, ModelArtifact
from .models import ArtifactSpec, ModelSpec

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from .runtimes import RuntimeCapability

#: Ratified decision D-1: closed declarative canonical format table.
#: Exact identity mapping only; it must never become a generic normalizer.
CANONICAL_FORMATS: tuple[tuple[str, str], ...] = (
    ("GGUF", "gguf"),
)

_CANONICAL_FORMAT_MAP = dict(CANONICAL_FORMATS)


@dataclass(frozen=True)
class StrictEvaluation:
    """Frozen result of one strict evaluation, with full traceability.

    ``projection`` keeps the untouched B9.7 ``KnowledgeProjection`` (original
    assertions with provenance, excluded UNKNOWN rows, unrepresentable
    relations and conflicts). ``result`` is the strict B9.3
    ``CompatibilityResult``; B9.9 never translates it into legacy
    recommendations.
    """

    model: Model
    artifact: ModelArtifact
    context: EvaluationContext
    projection: KnowledgeProjection
    result: CompatibilityResult


def canonical_format(format_value: str | None) -> str | None:
    """Exact D-1 lookup; unlisted values pass through unchanged."""
    if format_value is None:
        return None
    return _CANONICAL_FORMAT_MAP.get(format_value, format_value)


def evaluate_strict(
    registry: KnowledgeRegistry,
    spec: ModelSpec,
    artifact: ArtifactSpec,
    capability: RuntimeCapability,
    backend: str | None = None,
    required_capabilities: tuple[str, ...] = (),
    scope: KnowledgeScope | None = None,
    physical_evidence: object | None = None,
) -> StrictEvaluation:
    """Run the strict B9.8 → B9.7 → B9.3 chain deterministically.

    Pure: adapts the execution-domain inputs with B9.8, applies the closed
    D-1 format table to the adapted artifact, assembles the evaluation
    context (which embeds the B9.7 projection) and evaluates with B9.3. The
    result is never interpreted, never translated to the legacy model and
    never used to decide execution.
    """
    model = to_model(spec)
    if physical_evidence is not None and physical_evidence.architecture_raw is not None:
        model = replace(
            model,
            architecture=replace(
                model.architecture,
                architecture=physical_evidence.architecture_raw,
            ),
        )
    adapted_artifact = to_artifact(artifact)
    adapted_artifact = replace(
        adapted_artifact,
        format=canonical_format(adapted_artifact.format),
    )
    context, projection = build_evaluation_context(
        registry,
        capability,
        backend=backend,
        required_capabilities=required_capabilities,
        scope=scope,
    )
    result = evaluate(model, adapted_artifact, context)
    return StrictEvaluation(
        model=model,
        artifact=adapted_artifact,
        context=context,
        projection=projection,
        result=result,
    )
