# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").
# B9.99: admitted-model resolution bridge (part 1).
"""B9.99: resolve admitted identities to ModelSpec + conflict gate."""
from __future__ import annotations
from dataclasses import dataclass
from . import admitted_models as am
from .model_catalog import get_catalog
from .models import ModelSpec
class AdmittedResolutionError(Exception):
    pass


class AdmittedMaterialConflictError(AdmittedResolutionError):
    """A known admitted model has an unresolved material declared-vs-observed conflict."""
@dataclass(frozen=True)
class AdmittedResolution:
    model: ModelSpec
    record: object
    from_admitted: bool
def resolve_model_for_evaluation(model_id: str) -> AdmittedResolution:
    rec = am.resolve(model_id)
    if rec is None:
        for spec in get_catalog():
            if spec.model_id == model_id:
                return AdmittedResolution(model=spec, record=None, from_admitted=False)
        raise AdmittedResolutionError(f"Model not found in the local catalog: {model_id!r}")
    conflicts = am.material_conflicts(rec)
    if conflicts:
        c = conflicts[0]
        raise AdmittedMaterialConflictError(f"unresolved material conflict on {c['claim']!r}: declared={c['declared']!r} observed={c['observed']!r}")
    kw = am.project_to_model_spec_kwargs(rec)
    spec = ModelSpec(name=rec.model_id, id=rec.model_id, provider=rec.source, family=rec.repository, architecture=kw["architecture"], format=kw["format"], parameter_count_b=kw["parameter_count_b"], context_length=kw["context_length"])
    return AdmittedResolution(model=spec, record=rec, from_admitted=True)
