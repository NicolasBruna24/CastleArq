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

"""Functional compatibility evaluator (Block B9.3).

First executable compatibility reasoning layer, implementing the rules of
``docs/B9.2-compatibility-evaluation-rules.md`` for one functional claim:

> The supplied artifact can be considered functionally compatible with the
> supplied runtime/backend context, given the available model/artifact
> metadata and explicitly supplied runtime/backend capability knowledge.

Resource feasibility, performance and trust are NOT part of this claim.

The evaluator is an interpreter, never a detector: it reads supplied facts
(``Model``, ``ModelArtifact``, ``HardwareSnapshot``, ``RuntimeKnowledge``)
and produces a ``CompatibilityResult``. It never manufactures facts, never
performs I/O, never executes anything and holds no knowledge database —
capability knowledge is *supplied* through ``RuntimeKnowledge``.

UNKNOWN semantics: ``UNKNOWN != FAILED`` and ``UNKNOWN != INCOMPATIBLE``.
Every check below is determinant for the functional claim; an ``UNKNOWN``
on a required check yields ``INSUFFICIENT_EVIDENCE``, never a failure.
B9.3 produces no conditions (no implemented rule justifies one yet), so a
clean pass yields ``COMPATIBLE`` directly.

Determinism: fixed check order, no sets, no dict iteration, no global
state, no input mutation — same inputs always give the same result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .compatibility_domain import (
    CheckStatus,
    CompatibilityCheck,
    CompatibilityResult,
    CompatibilityStatus,
    EvidenceItem,
    EvidenceKind,
)
from .hardware import HardwareSnapshot
from .model_domain import Model, ModelArtifact

#: Capability names understood by the B8.1 model domain.
_CAPABILITY_FIELDS = (
    "text_generation",
    "code_generation",
    "vision",
    "embeddings",
    "tool_use",
)


def _names(values: object, label: str) -> tuple[str, ...]:
    """Normalize an optional string collection (list → tuple, else kept)."""
    if isinstance(values, list):
        values = tuple(values)
    if not isinstance(values, tuple):
        raise ValueError(f"{label} must be a tuple of strings")
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must contain non-empty strings only")
    return values


@dataclass(frozen=True)
class RuntimeKnowledge:
    """Explicit, supplied capability knowledge about one runtime (B9.2 §9).

    Declarative input only — never a built-in database. Each supported /
    unsupported pair is tri-state: membership in ``supported_*`` means
    explicitly supported, membership in ``unsupported_*`` means explicitly
    rejected, absence from both means unknown. ``supports_artifact``
    answers the runtime-level claim distinctly from the format claim.
    Contradictory knowledge (the same value in both lists of a pair) is
    malformed input, not uncertainty, and is rejected at construction.
    Matching is exact; no string-similarity inference is ever applied.
    """

    name: str | None = None
    supports_artifact: bool | None = None
    supported_formats: tuple[str, ...] = ()
    unsupported_formats: tuple[str, ...] = ()
    supported_architectures: tuple[str, ...] = ()
    unsupported_architectures: tuple[str, ...] = ()
    supported_model_types: tuple[str, ...] = ()
    unsupported_model_types: tuple[str, ...] = ()
    supported_backends: tuple[str, ...] = ()
    unsupported_backends: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name is not None and (
            not isinstance(self.name, str) or not self.name.strip()
        ):
            raise ValueError("name must be a non-empty string or None")
        if self.supports_artifact is not None and not isinstance(
            self.supports_artifact, bool
        ):
            raise ValueError("supports_artifact must be a bool or None")
        for label in (
            "supported_formats",
            "unsupported_formats",
            "supported_architectures",
            "unsupported_architectures",
            "supported_model_types",
            "unsupported_model_types",
            "supported_backends",
            "unsupported_backends",
        ):
            object.__setattr__(
                self, label, _names(getattr(self, label), label))
        for supported_label, unsupported_label in (
            ("supported_formats", "unsupported_formats"),
            ("supported_architectures", "unsupported_architectures"),
            ("supported_model_types", "unsupported_model_types"),
            ("supported_backends", "unsupported_backends"),
        ):
            for value in getattr(self, supported_label):
                if value in getattr(self, unsupported_label):
                    raise ValueError(
                        "contradictory runtime knowledge: "
                        f"{supported_label} and {unsupported_label} both "
                        f"contain {value!r}")


@dataclass(frozen=True)
class EvaluationContext:
    """Execution context for one functional evaluation (B9.2 §20).

    ``hardware`` is accepted because the future contract includes it, but
    B9.3 derives no check from hardware facts: GPU presence never implies
    backend support, and no capacity is calculated. ``backend`` names the
    concrete backend under evaluation (``None`` = unknown).
    ``required_capabilities`` lists model capabilities the claim requires;
    names are validated against the B8.1 taxonomy (unknown names raise).
    """

    runtime: RuntimeKnowledge = field(default_factory=RuntimeKnowledge)
    backend: str | None = None
    hardware: HardwareSnapshot | None = None
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeKnowledge):
            raise ValueError("runtime must be a RuntimeKnowledge")
        if self.backend is not None and (
            not isinstance(self.backend, str) or not self.backend.strip()
        ):
            raise ValueError("backend must be a non-empty string or None")
        if self.hardware is not None and not isinstance(
            self.hardware, HardwareSnapshot
        ):
            raise ValueError("hardware must be a HardwareSnapshot or None")
        capabilities = _names(
            self.required_capabilities, "required_capabilities")
        for capability in capabilities:
            if capability not in _CAPABILITY_FIELDS:
                raise ValueError(
                    f"unknown capability for B8.1 taxonomy: {capability!r}")
        object.__setattr__(self, "required_capabilities", capabilities)


def _observed(source: str, value: object) -> EvidenceItem:
    """One observed evidence item (facts are read, never manufactured)."""
    return EvidenceItem(source=source, value=value, kind=EvidenceKind.OBSERVED)


def _tri_state(
    value: str | None, supported: tuple[str, ...], unsupported: tuple[str, ...]
) -> CheckStatus:
    """Exact-membership tri-state: supported → PASSED, rejected → FAILED,
    absent from both (or value unknown) → UNKNOWN. No similarity.

    Contradictory overlap cannot occur: ``RuntimeKnowledge`` rejects it."""
    if value is None:
        return CheckStatus.UNKNOWN
    if value in supported:
        return CheckStatus.PASSED
    if value in unsupported:
        return CheckStatus.FAILED
    return CheckStatus.UNKNOWN


def _check_identity(model: Model, artifact: ModelArtifact) -> CompatibilityCheck:
    """Artifact↔model identity: strong model_id match wins; a bare
    identifier-vs-name equality never proves identity (UNKNOWN)."""
    model_id = model.identity.model_id
    identifier = artifact.identifier
    evidence = (
        _observed("model.identity.model_id", model_id),
        _observed("artifact.identifier", identifier),
    )
    if model_id is not None and identifier is not None:
        if identifier == model_id:
            return CompatibilityCheck(
                name="artifact-model identity",
                status=CheckStatus.PASSED,
                expected=model_id,
                observed=identifier,
                evidence=evidence,
            )
        return CompatibilityCheck(
            name="artifact-model identity",
            status=CheckStatus.FAILED,
            expected=model_id,
            observed=identifier,
            evidence=evidence,
        )
    return CompatibilityCheck(
        name="artifact-model identity",
        status=CheckStatus.UNKNOWN,
        expected=model_id,
        observed=identifier,
        evidence=evidence,
    )


def _check_format(
    artifact: ModelArtifact, knowledge: RuntimeKnowledge
) -> CompatibilityCheck:
    """Format read from ``artifact.format`` only (B9.2 §7)."""
    status = _tri_state(
        artifact.format, knowledge.supported_formats,
        knowledge.unsupported_formats)
    return CompatibilityCheck(
        name="artifact format support",
        status=status,
        expected=(artifact.format if status is CheckStatus.PASSED
                  else None) if status is not CheckStatus.FAILED else None,
        observed=artifact.format,
        evidence=(
            _observed("artifact.format", artifact.format),
            _observed(
                "runtime.supported_formats",
                ", ".join(knowledge.supported_formats) or None),
            _observed(
                "runtime.unsupported_formats",
                ", ".join(knowledge.unsupported_formats) or None),
        ),
    )


def _check_architecture(
    model: Model, knowledge: RuntimeKnowledge
) -> CompatibilityCheck:
    """Architecture/model-type from explicit knowledge only (B9.2 §6)."""
    architecture = model.architecture.architecture
    if architecture is not None:
        status = _tri_state(
            architecture, knowledge.supported_architectures,
            knowledge.unsupported_architectures)
        source, value = "model.architecture", architecture
    else:
        model_type = model.architecture.model_type
        status = _tri_state(
            model_type, knowledge.supported_model_types,
            knowledge.unsupported_model_types)
        source, value = "model.model_type", model_type
    expected = value if status is CheckStatus.PASSED else None
    return CompatibilityCheck(
        name="model architecture support",
        status=status,
        expected=expected,
        observed=value,
        evidence=(
            _observed(source, value),
            _observed("runtime.architecture_knowledge", "explicit lists"),
        ),
    )


def _check_runtime(
    knowledge: RuntimeKnowledge,
) -> CompatibilityCheck:
    """Runtime-level claim from ``supports_artifact`` only (B9.2 §9)."""
    if knowledge.supports_artifact is True:
        status = CheckStatus.PASSED
    elif knowledge.supports_artifact is False:
        status = CheckStatus.FAILED
    else:
        status = CheckStatus.UNKNOWN
    return CompatibilityCheck(
        name="runtime artifact support",
        status=status,
        expected=(True if status is CheckStatus.PASSED else None)
        if status is not CheckStatus.FAILED else None,
        observed=knowledge.supports_artifact,
        evidence=(
            _observed("runtime.name", knowledge.name),
            _observed("runtime.supports_artifact", knowledge.supports_artifact),
        ),
    )


def _check_backend(
    context: EvaluationContext,
) -> CompatibilityCheck:
    """Backend from explicit runtime/backend knowledge only (B9.2 §9).

    Hardware facts are never consulted here: GPU presence must not imply
    backend support.
    """
    status = _tri_state(
        context.backend, context.runtime.supported_backends,
        context.runtime.unsupported_backends)
    return CompatibilityCheck(
        name="runtime backend support",
        status=status,
        expected=(context.backend if status is CheckStatus.PASSED
                  else None) if status is not CheckStatus.FAILED else None,
        observed=context.backend,
        evidence=(
            _observed("context.backend", context.backend),
            _observed(
                "runtime.supported_backends",
                ", ".join(context.runtime.supported_backends) or None),
            _observed(
                "runtime.unsupported_backends",
                ", ".join(context.runtime.unsupported_backends) or None),
        ),
    )


def _check_capabilities(
    model: Model, required: tuple[str, ...]
) -> tuple[CompatibilityCheck, ...]:
    """One check per explicitly required capability (B9.2 §11).

    ``True`` → PASSED, ``False`` → FAILED (determinant), ``None`` →
    UNKNOWN. Non-required capabilities are never checked.
    """
    checks: list[CompatibilityCheck] = []
    for capability in required:
        value = getattr(model.capabilities, capability)
        status = (CheckStatus.PASSED if value is True
                  else CheckStatus.FAILED if value is False
                  else CheckStatus.UNKNOWN)
        checks.append(CompatibilityCheck(
            name=f"model capability: {capability}",
            status=status,
            expected=(True if status is CheckStatus.PASSED else None)
            if status is not CheckStatus.FAILED else None,
            observed=value,
            evidence=(
                _observed(f"model.capabilities.{capability}", value),
            ),
        ))
    return tuple(checks)


def evaluate(
    model: Model,
    artifact: ModelArtifact,
    context: EvaluationContext,
) -> CompatibilityResult:
    """Evaluate one artifact in one execution context (B9.2 rules A–D).

    Pure and deterministic: builds the six functional checks in fixed
    order, then aggregates — Rule A (any determinant FAILED →
    ``INCOMPATIBLE``), Rule D (any determinant UNKNOWN on evidence the
    functional claim needs → ``INSUFFICIENT_EVIDENCE``), otherwise
    ``COMPATIBLE`` (B9.3 emits no conditions, so Rule B never fires here).
    Every check is determinant for the functional claim; hardware is
    carried in the context but never read for functional conclusions.
    """
    if not isinstance(model, Model):
        raise ValueError("model must be a Model")
    if not isinstance(artifact, ModelArtifact):
        raise ValueError("artifact must be a ModelArtifact")
    if not isinstance(context, EvaluationContext):
        raise ValueError("context must be an EvaluationContext")
    checks = (
        _check_identity(model, artifact),
        _check_format(artifact, context.runtime),
        _check_architecture(model, context.runtime),
        _check_runtime(context.runtime),
        _check_backend(context),
        *_check_capabilities(model, context.required_capabilities),
    )
    if any(check.status is CheckStatus.FAILED for check in checks):
        status = CompatibilityStatus.INCOMPATIBLE
    elif any(
        check.status is CheckStatus.UNKNOWN
        and check.name != "runtime artifact support"
        for check in checks
    ):
        status = CompatibilityStatus.INSUFFICIENT_EVIDENCE
    else:
        status = CompatibilityStatus.COMPATIBLE
    return CompatibilityResult(status=status, checks=checks)
