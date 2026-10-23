from __future__ import annotations
import hashlib, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from castlearq.model_store import ModelStore, UnsafePathError
from castlearq.models import ArtifactSpec, ArtifactState

VALID_PRECISIONS = ("fp16", "int8", "int4")

@dataclass(frozen=True)
class ConversionResult:
    success: bool
    artifact: ArtifactSpec | None
    manifest_path: Path | None
    message: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""

def _sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()

class OpenVINOConversionService:
    def __init__(self, store, timeout=300.0, run_process=None):
        self.store=store; self.timeout=timeout; self._run=run_process or subprocess.run
    def convert(self, model, precision="fp16", revision=None, task="text-generation-with-past", destination=None):
        if precision not in VALID_PRECISIONS:
            return ConversionResult(False,None,None,"Unsupported precision: "+precision)
        tool=shutil.which("optimum-cli")
        if tool is None:
            return ConversionResult(False,None,None,"optimum-cli not found; install optimum-intel to enable conversion")
        owned_destination = destination is None
        if owned_destination:
            destination=Path(tempfile.mkdtemp(prefix="ov-export-"))
        else:
            destination=Path(destination)
            if destination.exists():
                return ConversionResult(False,None,None,"Destination already exists: "+str(destination))
            destination.mkdir(parents=True, exist_ok=True)
        argv=[tool,"export","openvino","--model",model,"--weight-format",precision]
        # Note: optimum-cli export openvino in the installed version does not
        # support --revision; revision is recorded as requested metadata only.
        if task: argv += ["--task",task]
        argv.append(str(destination))
        try:
            proc=self._run(argv,capture_output=True,text=True,timeout=self.timeout,shell=False)
        except subprocess.TimeoutExpired as e:
            if owned_destination: shutil.rmtree(destination,ignore_errors=True)
            return ConversionResult(False,None,None,"Conversion timed out",None,"",str(e))
        stdout=proc.stdout or ""; stderr=proc.stderr or ""
        if proc.returncode != 0:
            if owned_destination: shutil.rmtree(destination,ignore_errors=True)
            return ConversionResult(False,None,None,"optimum-cli failed (exit %d)"%proc.returncode,proc.returncode,stdout,stderr)
        try:
            xmls=list(destination.rglob("*.xml"))
            if not xmls: raise ValueError("No OpenVINO .xml found in output")
            for p in destination.rglob("*"):
                if p.is_symlink(): raise UnsafePathError("Symlink not allowed: "+str(p))
            primary_candidates=[p for p in xmls if p.name=="openvino_model.xml"]
            if len(primary_candidates)!=1:
                raise ValueError("Cannot identify primary OpenVINO model XML: expected exactly one openvino_model.xml, found %d"%len(primary_candidates))
            entry_xml=primary_candidates[0]
            all_files=[p for p in destination.rglob("*") if p.is_file()]
            aux=[]; checksums={}
            for p in all_files:
                if p==entry_xml: continue
                aux.append(p.name); checksums[p.name]=_sha256(p)
            aux_tuple=tuple(sorted(set(aux)))
            spec=ArtifactSpec(model_id=model,source="openvino-export",repository=model,filename=entry_xml.name,format="OpenVINO IR",quantization="FP16" if precision=="fp16" else precision.upper(),revision=revision,files=aux_tuple,file_checksums={k:checksums[k] for k in aux_tuple if k in checksums})
            managed=self.store.artifact_directory(spec)
            managed.mkdir(parents=True,exist_ok=True)
            for p in all_files:
                target=managed/p.relative_to(destination)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target)
            manifest=self.store.save_manifest(spec)
            inspected=self.store.inspect_manifest(manifest)
            if inspected.state not in (ArtifactState.DOWNLOADED,ArtifactState.VERIFIED):
                raise ValueError("Registered artifact failed inspection: "+str(inspected.message))
            if owned_destination:
                shutil.rmtree(destination,ignore_errors=True)
            return ConversionResult(True,spec,manifest,"Conversion completed",proc.returncode,stdout,stderr)
        except Exception as e:
            if owned_destination: shutil.rmtree(destination,ignore_errors=True)
            return ConversionResult(False,None,None,str(e),None,stdout if 'stdout' in locals() else "",stderr if 'stderr' in locals() else "")


from dataclasses import dataclass

@dataclass(frozen=True)
class ImportResult:
    success: bool
    artifact: ArtifactSpec | None = None
    manifest_path: Path | None = None
    message: str = ""

class OpenVINOImportService:
    def __init__(self, store):
        self.store = store

    def import_directory(self, source, model_id, precision="INT4", repository=None, revision=None):
        source = Path(source)
        if not source.is_dir():
            return ImportResult(False, None, None, "Source directory not found: " + str(source))
        try:
            xmls = [p for p in source.rglob("*") if p.is_file() and p.name == "openvino_model.xml"]
            if len(xmls) != 1:
                raise ValueError("Expected exactly one openvino_model.xml, found %d" % len(xmls))
            entry_xml = xmls[0]
            all_files = [p for p in source.rglob("*") if p.is_file()]
            for p in source.rglob("*"):
                if p.is_symlink():
                    raise UnsafePathError("Symlink not allowed: " + str(p))
                try:
                    p.resolve().relative_to(source.resolve())
                except Exception:
                    raise UnsafePathError("Unsafe path: " + str(p))
            if not any(p.name.endswith(".bin") for p in all_files):
                raise ValueError("Missing required .bin weights")
            aux = []
            checksums = {}
            for p in all_files:
                if p == entry_xml:
                    continue
                rel = p.relative_to(source).as_posix()
                aux.append(rel)
                checksums[rel] = _sha256(p)
            aux_tuple = tuple(sorted(set(aux)))
            checksum_map = {k: checksums[k] for k in aux_tuple}
            spec = ArtifactSpec(
                model_id=model_id,
                source="openvino-import",
                repository=repository,
                filename=entry_xml.name,
                format="OpenVINO IR",
                quantization=precision,
                revision=revision,
                files=aux_tuple,
                file_checksums=checksum_map,
            )
            managed = self.store.artifact_directory(spec)
            managed.mkdir(parents=True, exist_ok=True)
            for p in all_files:
                target = managed / p.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
            manifest = self.store.save_manifest(spec)
            inspected = self.store.inspect_manifest(manifest)
            if inspected.state not in (ArtifactState.DOWNLOADED, ArtifactState.VERIFIED):
                raise ValueError("Registered artifact failed inspection: " + str(inspected.message))
            return ImportResult(True, spec, manifest, "Import completed")
        except Exception as e:
            return ImportResult(False, None, None, str(e))
