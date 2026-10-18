# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").
# B9.99: explicit admitted-model journey commands.
"""B9.99 product callers: admit/describe/refresh/reconcile/show."""
from __future__ import annotations
from . import admitted_models as am
from .acquisition_resolution import bind as _bind, AcquisitionBindingError
from .gguf_reader import GGUFReadError, read_architecture_evidence
from .identity_admission import register as _admit_register, IdentityAdmissionError
from .model_identity import resolve_admitted_model_id
from .model_store import ModelStore
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
def admit_command(source: str, repository: str, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        model_id = resolve_admitted_model_id(source, repository)
    except Exception as error:
        print(f"Admit error: {error}", file=err); return 1
    try:
        _admit_register(source, repository, model_id)
    except IdentityAdmissionError as error:
        print(f"Admit error: {error}", file=err); return 1
    print(f"Admitted {model_id} for ({source}, {repository})", file=out)
    return 0
def bind_command(model_id: str, source: str, repository: str, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        _bind(model_id, source, repository)
    except AcquisitionBindingError as error:
        print(f"Bind error: {error}", file=err); return 1
    print(f"Bound {model_id} to ({source}, {repository})", file=out)
    return 0
def describe_command(model_id, source, repository, *, filename=None, quantization=None, revision=None, architecture=None, parameter_count_b=None, context_length=None, fmt=None, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        rec = am.describe(model_id, source, repository, filename=filename, quantization=quantization, revision=revision, architecture=architecture, parameter_count_b=parameter_count_b, context_length=context_length, format=fmt)
    except am.AdmittedModelError as error:
        print(f"Describe error: {error}", file=err); return 1
    print(f"Described {rec.model_id} accepted={rec.accepted}", file=out)
    return 0
def refresh_command(model_id, *, architecture=None, parameter_count_b=None, context_length=None, fmt=None, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        diff = am.refresh(model_id, architecture=architecture, parameter_count_b=parameter_count_b, context_length=context_length, format=fmt)
    except am.AdmittedModelError as error:
        print(f"Refresh error: {error}", file=err); return 1
    print(f"Refreshed {model_id} changed={list(diff.changed)} unchanged={list(diff.unchanged)}", file=out)
    return 0
def reconcile_command(model_id, decisions: dict, *, basis: str, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        rec = am.reconcile(model_id, decisions, basis=basis)
    except am.AdmittedModelError as error:
        print(f"Reconcile error: {error}", file=err); return 1
    print(f"Reconciled {model_id} accepted={rec.accepted}", file=out)
    return 0
def show_command(model_id, out=None, err=None) -> int:
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        rec = am.resolve(model_id)
    except am.AdmittedModelError as error:
        print(f"Show error: {error}", file=err); return 1
    if rec is None:
        print(f"Unknown admitted model: {model_id}", file=err); return 1
    print(f"model_id={rec.model_id} source={rec.source} repository={rec.repository}", file=out)
    print(f"accepted={rec.accepted}", file=out)
    print(f"provenance={rec.declaration_provenance}", file=out)
    print(f"pending={rec.pending_declaration}", file=out)
    print(f"observations={len(rec.observations)} reconciliations={len(rec.reconciliations)}", file=out)
    return 0


def observe_command(model_id, claim, value, *, observation_context, out=None, err=None) -> int:
    """Explicit durable observation capture (B1 findings resolution).

    The only supported durable observation write path. Ordinary evaluation,
    resolution, execution, and chat never call it implicitly.
    """
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        rec = am.record_observation(
            model_id, claim, value, observation_context=observation_context
        )
    except am.AdmittedModelError as error:
        print(f"Observe error: {error}", file=err); return 1
    print(f"Observed {model_id} {claim}={value!r} total={len(rec.observations)}", file=out)
    return 0

def observe_physical_command(
    model_id,
    *,
    quantization=None,
    filename=None,
    model_store=None,
    out=None,
    err=None,
) -> int:
    """Observe the physical GGUF architecture of the resolved local artifact.

    Explicit, human-invoked durability for the ephemeral physical evidence
    that evaluation already reads: resolve exactly one local artifact with
    ``ModelArtifactResolver``, read ``general.architecture`` with the
    existing GGUF reader, and persist it as a ``gguf_architecture``
    observation whose context carries the resolved ``artifact_id``
    (plus the declared revision when the resolved artifact carries one).
    ``accepted`` claims are never modified here; divergence surfaces
    through the existing material-conflict gate, and reconciliation stays
    an explicit human action. Any failure leaves the registry unchanged.
    """
    import sys
    out = out or sys.stdout; err = err or sys.stderr
    try:
        store = model_store if model_store is not None else ModelStore()
        resolved = ModelArtifactResolver(store).resolve(
            model_id, quantization=quantization, filename=filename
        )
    except ModelArtifactResolutionError as error:
        print(f"Observe-physical error: {error}", file=err); return 1
    if resolved.path is None:
        print(
            "Observe-physical error: resolved artifact has no managed path",
            file=err,
        )
        return 1
    try:
        evidence = read_architecture_evidence(resolved.path)
    except GGUFReadError as error:
        print(f"Observe-physical error: {error}", file=err); return 1
    if evidence.architecture_raw is None:
        print(
            "Observe-physical error: general.architecture is absent",
            file=err,
        )
        return 1
    revision = resolved.artifact.revision
    context = f"physical-gguf:{resolved.artifact.artifact_id}"
    if revision:
        context += f":{revision}"
    try:
        rec = am.record_observation(
            model_id,
            "gguf_architecture",
            evidence.architecture_raw,
            observation_context=context,
        )
    except am.AdmittedModelError as error:
        print(f"Observe-physical error: {error}", file=err); return 1
    print(
        f"Observed {model_id} gguf_architecture={evidence.architecture_raw!r} "
        f"total={len(rec.observations)}",
        file=out,
    )
    return 0
