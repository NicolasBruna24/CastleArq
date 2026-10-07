# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application Use Case: Evaluate Model Compatibility.

Coordinates one compatibility evaluation per
``docs/application-use-case-evaluate-model-compatibility.md``:

    capability -> application policy -> model/artifact resolution
    + B9.14 -> IntegrationResult -> B9.15 -> Application Result

Stateless coordinator only: no translation, integration, knowledge
projection, reconciliation, evaluation, decision or execution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .application_wiring import compose_and_integrate
from .compatibility_knowledge import KnowledgeRegistry, KnowledgeScope
from .compatibility_domain import CheckStatus, CompatibilityStatus
from .evaluation_composition import compose_evaluation
from .evaluation_pipeline import StrictEvaluation
from .execute_model import EvaluationAdmission
from .gguf_reader import (
    GGUFArchitectureEvidence,
    GGUFReadError,
    read_architecture_evidence,
)
from .initial_knowledge import INITIAL_KNOWLEDGE_REGISTRY
from .model_catalog import get_catalog
from .model_store import ModelStore
from .models import ArtifactSpec, ModelSpec
from .observation_knowledge import IntegrationResult
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runtime_artifact_evidence import RuntimeArtifactEvidence
from .runtime_artifact_observer import RuntimeArtifactObserver
from .runtimes import detect_llama_capability

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .runtimes import RuntimeCapability

__all__ = [
    "EvaluateCompatibilityDependencies",
    "EvaluateModelCompatibilityResult",
    "evaluate_model_compatibility",
    "to_admission",
]


@dataclass(frozen=True)
class EvaluateCompatibilityDependencies:
    """Explicit injectable collaborators for the use case."""

    model_store: ModelStore | None = None
    models: tuple[ModelSpec, ...] | None = None
    capability: RuntimeCapability | None = None
    registry: KnowledgeRegistry | None = None
    integrate_fn: Callable[[], IntegrationResult] | None = None
    evaluate_fn: Callable[..., StrictEvaluation] | None = None
    evidence_reader: Callable[[Path], GGUFArchitectureEvidence] | None = None
    runtime_artifact_observer: Callable[..., RuntimeArtifactEvidence] | None = None


@dataclass(frozen=True)
class EvaluateModelCompatibilityResult:
    """Application-level outcome of one compatibility evaluation."""

    model_id: str
    artifact: ArtifactSpec | None
    runtime: str | None
    capability: RuntimeCapability | None
    evaluation: StrictEvaluation | None
    integration: IntegrationResult | None
    status: str
    blocking_outcome: str | None
    # B9.66: propagated from ``ResolvedModelArtifact.imported``. The strict
    # compatibility result is NOT altered by this flag -- an imported artifact
    # whose logical identity is unknown still evaluates to
    # INSUFFICIENT_EVIDENCE. Only the admission projection that follows is
    # scoped by it.
    imported: bool = False


_NON_BLOCKING_E2E_UNKNOWNS = frozenset({
    "runtime artifact support",
    "runtime backend support",
})

#: B9.66: an imported artifact has no catalog model, so "artifact-model
#: identity" is UNKNOWN by construction rather than by uncertainty -- there is
#: no prior claim for it to contradict. The check is still evaluated and still
#: reported as UNKNOWN; it is never promoted to PASSED, and INCOMPATIBLE
#: remains blocking for imported artifacts exactly as for catalog ones.
_IMPORT_NON_BLOCKING_UNKNOWNS = frozenset({
    "artifact-model identity",
})


def _non_blocking_unknowns(imported: bool) -> frozenset[str]:
    """Return the UNKNOWN check names that may coexist with admission.

    For every artifact CastleArq already tolerates runtime-side evidence gaps.
    An imported artifact additionally tolerates the catalog-identity gap, which
    is the one condition that cannot be established at all for a file the
    catalog never described. ``imported=False`` returns the original set
    unchanged, so catalog admission policy is bit-for-bit identical.
    """
    if imported:
        return _NON_BLOCKING_E2E_UNKNOWNS | _IMPORT_NON_BLOCKING_UNKNOWNS
    return _NON_BLOCKING_E2E_UNKNOWNS


def to_admission(
    result: EvaluateModelCompatibilityResult | None,
) -> EvaluationAdmission:
    """Project a completed evaluation result into the Execute admission seam.

    This is deliberately a pure, fail-closed projection.  It carries only the
    application status and strict verdict; diagnostics and model/artifact
    identity remain on ``EvaluateModelCompatibilityResult``.  A missing or
    malformed result is represented as a blocked admission and can never allow
    execution.
    """
    if result is None:
        return EvaluationAdmission(status="blocked")
    verdict = None
    evaluation = getattr(result, "evaluation", None)
    strict_result = getattr(evaluation, "result", None)
    if strict_result is not None:
        verdict = getattr(strict_result, "status", None)
    if isinstance(verdict, str) and verdict == CompatibilityStatus.INSUFFICIENT_EVIDENCE:
        checks = getattr(strict_result, "checks", ())
        if not isinstance(checks, (tuple, list)):
            checks = ()
        unknown_names = {
            getattr(check, "name", None)
            for check in checks
            if getattr(check, "status", None) is CheckStatus.UNKNOWN
        }
        failed = any(
            getattr(check, "status", None) is CheckStatus.FAILED for check in checks
        )
        if (
            not failed
            and unknown_names
            and unknown_names <= _non_blocking_unknowns(
                getattr(result, "imported", False)
            )
        ):
            verdict = "compatible"
    return EvaluationAdmission(
        status=getattr(result, "status", "blocked"),
        verdict=verdict if isinstance(verdict, str) else None,
    )


def _blocked(
    model_id: str,
    outcome: str,
    *,
    artifact: ArtifactSpec | None = None,
    runtime: str | None = None,
    capability: RuntimeCapability | None = None,
    integration: IntegrationResult | None = None,
) -> EvaluateModelCompatibilityResult:
    return EvaluateModelCompatibilityResult(
        model_id=model_id,
        artifact=artifact,
        runtime=runtime,
        capability=capability,
        evaluation=None,
        integration=integration,
        status="blocked",
        blocking_outcome=outcome,
    )


def evaluate_model_compatibility(
    model_id: str,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    backend: str | None = None,
    required_capabilities: tuple[str, ...] = (),
    scope: KnowledgeScope | None = None,
    dependencies: EvaluateCompatibilityDependencies | None = None,
) -> EvaluateModelCompatibilityResult:
    """Evaluate compatibility of one model/artifact with one runtime."""
    if dependencies is not None:
        deps = dependencies
    else:
        deps = EvaluateCompatibilityDependencies()
    if deps.capability is not None:
        capability = deps.capability
    else:
        capability = detect_llama_capability()
    # Application flow policy (spec 3.2/4): unavailable capability stops
    # the use case before B9.15. NOT a domain rule; B9.15 untouched here.
    if capability.available is False:
        return _blocked(
            model_id,
            "Runtime is not available: " + capability.name,
            runtime=capability.name,
            capability=capability,
        )
    if deps.model_store is not None:
        store = deps.model_store
    else:
        store = ModelStore()
    if deps.models is not None:
        models = deps.models
    else:
        models = get_catalog()
    resolver = ModelArtifactResolver(store, models=models)
    try:
        resolved = resolver.resolve(
            model_id, quantization=quantization, filename=filename
        )
    except ModelArtifactResolutionError as error:
        return _blocked(
            model_id,
            str(error),
            runtime=capability.name,
            capability=capability,
        )
    if deps.registry is not None:
        registry = deps.registry
    else:
        registry = INITIAL_KNOWLEDGE_REGISTRY
    if deps.integrate_fn is not None:
        integrate_fn = deps.integrate_fn
    else:
        integrate_fn = compose_and_integrate
    evidence_reader: Any = deps.evidence_reader
    if evidence_reader is None:
        evidence_reader = read_architecture_evidence
    artifact_path: Path | None = None
    try:
        artifact_path = store._artifact_directory(resolved.artifact) / resolved.artifact.filename
        architecture_evidence = evidence_reader(artifact_path)
    except AttributeError:
        architecture_evidence = GGUFArchitectureEvidence(architecture_raw=None)
    except GGUFReadError:
        raise
    # B9.99 findings resolution (B1): ordinary evaluation is read-only
    # w.r.t. the admitted-model store. GGUF architecture evidence is
    # consumed ephemerally by the strict chain below; durable observation
    # capture is an explicit operation (see admitted_commands.observe_command).
    # B9.79: produce ephemeral pre-admission runtime/artifact evidence at the
    # physical observation boundary, next to the GGUF architecture reader. The
    # observer is a separate read-only producer -- never the post-admission
    # runner -- and it returns UNKNOWN without running anything when no concrete
    # device/executable/artifact path was resolved, so absent context is never a
    # positive claim. A producer error propagates; it is never folded into a
    # NEGATIVE observation (B9.79 sections 4 and 7).
    observer: Any = deps.runtime_artifact_observer
    if observer is None:
        observer = RuntimeArtifactObserver().observe
    runtime_artifact_evidence = observer(
        executable_path=capability.executable_path,
        runtime_identity=capability.executable_path or capability.name,
        runtime_version=capability.version,
        artifact_path=artifact_path,
        artifact_reference=resolved.artifact.artifact_id,
        artifact_format=resolved.artifact.format,
        artifact_architecture=architecture_evidence.architecture_raw,
        device=(
            capability.backend_argument(backend) if backend is not None else None
        ),
    )
    try:
        integration = integrate_fn()
    except Exception as error:
        return _blocked(
            resolved.model.model_id,
            "Integration failed: " + str(error),
            artifact=resolved.artifact,
            runtime=capability.name,
            capability=capability,
        )
    if type(integration) is not IntegrationResult:
        return _blocked(
            resolved.model.model_id,
            "Integration did not return an IntegrationResult",
            artifact=resolved.artifact,
            runtime=capability.name,
            capability=capability,
        )
    evaluate_fn: Any = deps.evaluate_fn
    if evaluate_fn is None:
        evaluate_fn = compose_evaluation
    # B9.15 failures propagate: Application never hides them.
    evaluation = evaluate_fn(
        result=integration,
        registry=registry,
        spec=resolved.model,
        artifact=resolved.artifact,
        capability=capability,
        backend=backend,
        required_capabilities=tuple(required_capabilities),
        scope=scope,
        physical_evidence=architecture_evidence,
        runtime_artifact_evidence=runtime_artifact_evidence,
    )
    return EvaluateModelCompatibilityResult(
        model_id=resolved.model.model_id,
        artifact=resolved.artifact,
        runtime=capability.name,
        capability=capability,
        evaluation=evaluation,
        integration=integration,
        status="evaluated",
        blocking_outcome=None,
        imported=resolved.imported,
    )
