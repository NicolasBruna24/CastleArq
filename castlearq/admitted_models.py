# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").
# B9.99: durable Executable Model Description authority.
"""B9.99: durable Executable Model Description authority."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
__all__=["ADMITTED_MODELS_ROOT_ENV","AdmittedModelError","AcceptedClaims","DeclarationProvenance","AdmittedModelRecord","RefreshDiff","admitted_models_path","describe","resolve","record_observation","refresh","reconcile","material_conflicts","project_to_model_spec_kwargs"]
ADMITTED_MODELS_ROOT_ENV="CASTLEARQ_ADMITTED_MODELS_ROOT"
_FILENAME="admitted-models.json"
_FORMAT_VERSION=1
CLAIM_NAMES=("architecture","parameter_count_b","context_length","format")
class AdmittedModelError(Exception):
    pass
@dataclass(frozen=True)
class AcceptedClaims:
    architecture: str | None=None
    parameter_count_b: float | None=None
    context_length: int | None=None
    format: str | None=None
@dataclass(frozen=True)
class DeclarationProvenance:
    source: str
    repository: str
    captured_at: str
    capture_context: str
    location: str | None=None
@dataclass(frozen=True)
class AdmittedModelRecord:
    model_id: str
    source: str
    repository: str
    filename: str | None
    quantization: str | None
    revision: str | None
    accepted: AcceptedClaims
    declaration_provenance: DeclarationProvenance
    accepted_at: str
    observations: tuple=()
    pending_declaration: dict | None=None
    reconciliations: tuple=()
@dataclass(frozen=True)
class RefreshDiff:
    model_id: str
    changed: tuple
    unchanged: tuple
    has_changes: bool
def _root():
    o=os.environ.get(ADMITTED_MODELS_ROOT_ENV)
    if o is not None:
        assert o.strip(),"empty override"
        return Path(os.path.expanduser(o)).expanduser()
    return Path(os.path.expanduser("~")) / ".castlearq"
def admitted_models_path():
    return _root()/_FILENAME
def _utcnow():
    return datetime.now(timezone.utc).isoformat()
def _vt(v,l):
    if not isinstance(v,str) or not v.strip(): raise AdmittedModelError(l+" must be non-empty")
    return v
def _vc(a,p,c,f):
    if a is not None and (not isinstance(a,str) or not a.strip()): raise AdmittedModelError("bad arch")
    if p is not None and (isinstance(p,bool) or not isinstance(p,(int,float)) or p<=0): raise AdmittedModelError("bad params")
    if c is not None and (isinstance(c,bool) or not isinstance(c,int) or c<=0): raise AdmittedModelError("bad ctx")
    if f is not None and (not isinstance(f,str) or not f.strip()): raise AdmittedModelError("bad format")
    return AcceptedClaims(architecture=a,parameter_count_b=float(p) if p is not None else None,context_length=c,format=f)
def _load(path):
    if not path.exists(): return {}
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as e: raise AdmittedModelError("unreadable") from e
    if not isinstance(payload,dict) or payload.get("version")!=_FORMAT_VERSION: raise AdmittedModelError("bad registry")
    m=payload.get("models",{})
    if not isinstance(m,dict): raise AdmittedModelError("bad registry")
    return m
def _write(path,models):
    path.parent.mkdir(parents=True,exist_ok=True)
    t=json.dumps({"version":_FORMAT_VERSION,"models":models},indent=2,sort_keys=True)+"\n"
    tmp=path.with_name(path.name+".tmp")
    try:
        fh=open(tmp,"w",encoding="utf-8");fh.write(t);fh.flush();os.fsync(fh.fileno());fh.close();os.replace(tmp,path)
        fd=os.open(str(path.parent),os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        try: os.unlink(tmp)
        except OSError: pass
def _from_stored(mid,s):
    a=s.get("accepted",{});pv=s.get("declaration_provenance",{})
    return AdmittedModelRecord(model_id=mid,source=s.get("source"),repository=s.get("repository"),filename=s.get("filename"),quantization=s.get("quantization"),revision=s.get("revision"),accepted=AcceptedClaims(architecture=a.get("architecture"),parameter_count_b=a.get("parameter_count_b"),context_length=a.get("context_length"),format=a.get("format")),declaration_provenance=DeclarationProvenance(source=pv.get("source",s.get("source")),repository=pv.get("repository",s.get("repository")),captured_at=pv.get("captured_at",""),capture_context=pv.get("capture_context",""),location=pv.get("location")),accepted_at=s.get("accepted_at",""),observations=tuple(s.get("observations",())),pending_declaration=s.get("pending_declaration"),reconciliations=tuple(s.get("reconciliations",())))
def describe(mid,src,repo,*,filename=None,quantization=None,revision=None,architecture=None,parameter_count_b=None,context_length=None,format=None,capture_context="explicit describe",location=None,captured_at=None):
    from .model_identity import resolve_admitted_model_id
    _vt(mid,"model_id");_vt(src,"source");_vt(repo,"repository");_vt(capture_context,"capture_context")
    cl=_vc(architecture,parameter_count_b,context_length,format)
    try: r=resolve_admitted_model_id(src,repo)
    except Exception as e: raise AdmittedModelError(str(e)) from e
    if r!=mid: raise AdmittedModelError("identity consistency check failed")
    now=captured_at or _utcnow();p=admitted_models_path();ms=_load(p);ex=ms.get(mid)
    acc={"architecture":cl.architecture,"parameter_count_b":cl.parameter_count_b,"context_length":cl.context_length,"format":cl.format}
    if ex is not None:
        ok=ex.get("source")==src and ex.get("repository")==repo and ex.get("filename")==filename and ex.get("quantization")==quantization and ex.get("revision")==revision and ex.get("accepted")==acc
        if ok: return _from_stored(mid,ex)
        raise AdmittedModelError("already described; divergent re-description rejected")
    st={"model_id":mid,"source":src,"repository":repo,"filename":filename,"quantization":quantization,"revision":revision,"accepted":acc,"declaration_provenance":{"source":src,"repository":repo,"captured_at":now,"capture_context":capture_context,"location":location},"accepted_at":now,"observations":[],"pending_declaration":None,"reconciliations":[]}
    ms[mid]=st;_write(p,ms);return _from_stored(mid,st)
def resolve(mid):
    _vt(mid,"model_id")
    s=_load(admitted_models_path()).get(mid)
    return None if s is None else _from_stored(mid,s)
def record_observation(mid,claim,value,*,observation_context,observed_at=None):
    _vt(mid,"model_id");_vt(observation_context,"observation_context")
    if claim not in CLAIM_NAMES and claim not in ("size_bytes","sha256_match","gguf_architecture"): raise AdmittedModelError("unknown claim")
    p=admitted_models_path();ms=_load(p);s=ms.get(mid)
    if s is None: raise AdmittedModelError("no description")
    s["observations"]=[*s.get("observations",[]),{"claim":claim,"value":value,"observation_provenance":{"observed_at":observed_at or _utcnow(),"observation_context":observation_context}}]
    _write(p,ms);return _from_stored(mid,s)
def refresh(mid,*,architecture=None,parameter_count_b=None,context_length=None,format=None,capture_context="explicit refresh",location=None,captured_at=None):
    _vt(mid,"model_id");_vt(capture_context,"capture_context")
    cl=_vc(architecture,parameter_count_b,context_length,format)
    p=admitted_models_path();ms=_load(p);s=ms.get(mid)
    if s is None: raise AdmittedModelError("no description")
    cand={"architecture":cl.architecture,"parameter_count_b":cl.parameter_count_b,"context_length":cl.context_length,"format":cl.format,"provenance":{"source":s.get("source"),"repository":s.get("repository"),"captured_at":captured_at or _utcnow(),"capture_context":capture_context,"location":location}}
    acc=s.get("accepted",{});ch=[];un=[]
    [un.append(n) if cand[n]==acc.get(n) else ch.append(n) for n in CLAIM_NAMES]
    s["pending_declaration"]=cand;_write(p,ms)
    return RefreshDiff(model_id=mid,changed=tuple(ch),unchanged=tuple(un),has_changes=bool(ch))
def reconcile(mid,decisions,*,basis,reconciled_at=None):
    _vt(mid,"model_id");_vt(basis,"basis")
    ok={"keep_accepted","accept_pending","mark_unknown"}
    [(_ for _ in () ) ]
    for k,v in decisions.items():
        if k not in CLAIM_NAMES: raise AdmittedModelError("unknown claim")
        if v not in ok: raise AdmittedModelError("bad decision")
    p=admitted_models_path();ms=_load(p);s=ms.get(mid)
    if s is None: raise AdmittedModelError("no description")
    pe=s.get("pending_declaration")
    if any(v!="keep_accepted" for v in decisions.values()) and pe is None: raise AdmittedModelError("no pending")
    now=reconciled_at or _utcnow();acc=dict(s.get("accepted",{}));hist=list(s.get("reconciliations",[]))
    for k,v in decisions.items():
        prior=acc.get(k)
        if v=="keep_accepted": oc="kept_accepted"
        elif v=="mark_unknown": acc[k]=None;oc="marked_unknown"
        else: acc[k]=pe[k];oc="accepted_pending"
        hist.append({"claim":k,"outcome":oc,"prior":prior,"basis":basis,"at":now})
    s["accepted"]=acc;s["reconciliations"]=hist;s["pending_declaration"]=None;_write(p,ms);return _from_stored(mid,s)
def material_conflicts(rec):
    out=[];by={}
    [by.setdefault(e.get("claim"),[]).append(e.get("value")) for e in rec.observations]
    am={"architecture":rec.accepted.architecture,"parameter_count_b":rec.accepted.parameter_count_b,"context_length":rec.accepted.context_length,"format":rec.accepted.format}
    for cl in CLAIM_NAMES:
        d=am[cl];ex="gguf_architecture" if cl=="architecture" else "__none__"
        for ob in by.get(cl,[])+by.get(ex,[]):
            if d is not None and ob is not None and ob!=d: out.append({"claim":cl,"declared":d,"observed":ob})
    return tuple(out)
def project_to_model_spec_kwargs(rec):
    return {"architecture":rec.accepted.architecture or "Unknown","parameter_count_b":rec.accepted.parameter_count_b,"context_length":rec.accepted.context_length,"format":rec.accepted.format or "Unknown"}
