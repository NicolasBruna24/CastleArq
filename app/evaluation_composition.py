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

"""B9.15: Evaluation Composition — the stage-scoped composition point.

Realizes the RATIFIED Evaluation Composition architecture
(``docs/B9.15-evaluation-composition-specification.md``): the single,
function-level composition point immediately downstream of the Q-8
Evaluation Entry Boundary.

    Q-8 (accept → retain → forward)
        → compose_evaluation(...)                     (composition)
        → build_evaluation_context(...)               (composition; existing B9.8)
        → evaluate(model, artifact, context)          (Evaluation begins; B9.3)

Responsibilities: assembly only. Accept the delivered ``IntegrationResult``
verbatim, accept the explicitly injected ``KnowledgeRegistry`` (a required
parameter — no default, no global, no lookup of any dataset module) and the
caller-supplied evaluation-time values, then delegate unchanged to the
existing B9.9 pipeline. The RuntimeCapability reconciliation algorithm is
DEFERRED (ownership: this block), so this module performs NO pairing,
matching, ranking or selection of runtimes and does not read the delivered
record's contents: the caller declares which runtime capability to evaluate.

Non-responsibilities: no DTO / envelope / wrapper of the delivered record,
no concrete Q-8 receiver, no activation technology, no state, no cache, no
error handling, no persistence, no serialization, no model execution, no
backend selection. Composition ends where ``evaluate()`` begins.

Purity: no I/O, process, network or environment facility and no
module-level mutable state; same inputs always yield an equal output and
inputs are never mutated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .compatibility_knowledge import KnowledgeRegistry, KnowledgeScope
from .evaluation_pipeline import StrictEvaluation, evaluate_strict
from .models import ArtifactSpec, ModelSpec
from .observation_knowledge import IntegrationResult

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from .runtimes import RuntimeCapability


def compose_evaluation(
    result: IntegrationResult,
    registry: KnowledgeRegistry,
    spec: ModelSpec,
    artifact: ArtifactSpec,
    capability: "RuntimeCapability",
    backend: str | None = None,
    required_capabilities: tuple[str, ...] = (),
    scope: KnowledgeScope | None = None,
) -> StrictEvaluation:
    """Assemble one Evaluation from the Q-8 delivery and caller-declared values.

    ``result`` is the ``IntegrationResult`` delivered through the Q-8
    Evaluation Entry Boundary: it is accepted verbatim and preserved —
    never transformed, wrapped, serialized or reclassified — and its
    contents are not read, because the RuntimeCapability reconciliation
    algorithm (owned by this block) is DEFERRED: no pairing, matching or
    selection happens here, and the caller declares the runtime to
    evaluate. ``registry`` is an explicit injected dependency with no
    default. ``spec``, ``artifact``, ``capability``, ``backend``,
    ``required_capabilities`` and ``scope`` are caller-supplied
    evaluation-time values.

    Assembly (``to_model``, ``to_artifact``, ``build_evaluation_context``)
    and Evaluation (``evaluate``) run inside the existing B9.9 pipeline,
    unchanged; composition ends where ``evaluate()`` begins. The pipeline
    record is returned verbatim for downstream continuation; no error
    handling, retry, fallback or substitution is applied here.
    """
    if type(result) is not IntegrationResult:
        raise ValueError("result must be an IntegrationResult")
    return evaluate_strict(
        registry,
        spec,
        artifact,
        capability,
        backend=backend,
        required_capabilities=required_capabilities,
        scope=scope,
    )
