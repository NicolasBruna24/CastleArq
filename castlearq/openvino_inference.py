"""OpenVINO GenAI inference service for CastleArq Core."""

from __future__ import annotations

import hashlib
import os
import glob
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from castlearq.model_store import ModelStore, StoredArtifact
from castlearq.models import ArtifactState


class OpenVINOInferenceError(Exception):
    pass


class MissingDependencyError(OpenVINOInferenceError):
    pass


class InvalidArtifactError(OpenVINOInferenceError):
    pass


class PipelineInitError(OpenVINOInferenceError):
    pass


class GenerationError(OpenVINOInferenceError):
    pass
def _extract_generated_text(result) -> str:
    """Extract the first generated text from an OpenVINO GenAI result."""
    if isinstance(result, str):
        return result
    texts = getattr(result, "texts", None)
    if isinstance(texts, (list, tuple)) and len(texts) > 0 and isinstance(texts[0], str):
        return texts[0]
    raise GenerationError("OpenVINO generation returned no text")



@dataclass(frozen=True)
class OpenVINOGenerationResult:
    text: str
    device: str
    requested_backend: str = ""
    initialization_status: str = "ok"
    effective_device: str = "unverified"
    requested_device: str = ""
    available_devices: tuple[str, ...] | None = None
    physical_telemetry: dict | None = None
    finish_reason: str | None = None


class PipelineFactory(Protocol):
    def __call__(self, model_dir: Path, device: str) -> Any:
        ...


def sample_xe_telemetry() -> dict | None:
    samples = {}
    for hwmon in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name_path = os.path.join(hwmon, "name")
        try:
            with open(name_path) as f:
                name = f.read().strip()
        except (OSError, ValueError):
            continue
        if name != "xe":
            continue
        readings = {}
        try:
            entries = sorted(os.listdir(hwmon))
        except OSError:
            continue
        for entry in entries:
            if not (entry.startswith("temp") and entry.endswith("_input")):
                continue
            path = os.path.join(hwmon, entry)
            try:
                with open(path) as f:
                    raw = f.read().strip()
                value = int(raw)
            except (OSError, ValueError):
                continue
            readings[entry] = value
        if readings:
            samples[os.path.basename(hwmon)] = readings
    if not samples:
        return None
    return {"source": "sysfs:hwmon:xe", "available": True, "samples": samples}


class OpenVINOInferenceService:
    def __init__(
        self,
        model_store: ModelStore,
        pipeline_factory: PipelineFactory | None = None,
        tokenizer_path: Path | str | None = None,
    ) -> None:
        self._model_store = model_store
        self._pipeline_factory = pipeline_factory
        self._tokenizer_path = Path(tokenizer_path) if tokenizer_path is not None else None
        self._pipeline = None
        self._pipeline_lock = threading.Lock()
        self._pipeline_key = None
        self._available_devices: tuple[str, ...] | None = None
        self._available_devices_checked = False
        self._service_closed = False
        self._service_closed_lock = threading.Lock()
        if self._tokenizer_path is not None and not (self._tokenizer_path / "openvino_tokenizer.xml").is_file():
            raise InvalidArtifactError("Explicit tokenizer directory missing openvino_tokenizer.xml")

    def _build_pipeline_factory(self):
        if self._pipeline_factory is not None:
            return self._pipeline_factory
        ov_genai = self._load_genai()
        tokenizer_path = self._tokenizer_path
        if tokenizer_path is None:
            def factory(d, dev):
                model_dir = Path(str(d))
                tokenizer_xml = model_dir / "openvino_tokenizer.xml"
                if tokenizer_xml.is_file():
                    tokenizer = ov_genai.Tokenizer(str(tokenizer_xml.parent))
                    return ov_genai.LLMPipeline(str(d), tokenizer, dev)
                return ov_genai.LLMPipeline(str(d), dev)
            return factory
        tokenizer = ov_genai.Tokenizer(str(tokenizer_path))
        return lambda d, dev: ov_genai.LLMPipeline(str(d), tokenizer, dev)

    def _load_genai(self):
        try:
            import openvino_genai as ov_genai
        except Exception as exc:
            raise MissingDependencyError("openvino_genai is not available") from exc
        return ov_genai
    def _validate_integrated_tokenizer(self, model_dir: Path, spec: Any) -> None:
        tokenizer_files = {
            "openvino_tokenizer.xml",
            "openvino_tokenizer.bin",
            "openvino_detokenizer.xml",
            "openvino_detokenizer.bin",
        }
        present = {name for name in tokenizer_files if (model_dir / name).is_file()}
        if not present:
            return
        if present != tokenizer_files:
            missing = sorted(tokenizer_files - present)
            raise InvalidArtifactError(
                "Integrated OpenVINO tokenizer is incomplete: missing " + ", ".join(missing)
            )
        checksums = getattr(spec, "file_checksums", None)
        if checksums:
            for name in sorted(tokenizer_files):
                expected = checksums.get(name)
                if expected is None:
                    continue
                actual = hashlib.sha256((model_dir / name).read_bytes()).hexdigest()
                if actual != expected:
                    raise InvalidArtifactError(
                        f"Integrated OpenVINO tokenizer checksum mismatch: {name}"
                    )
        try:
            artifact = self._model_store.inspect_manifest(model_dir / "manifest.json", verify=True)
        except Exception as exc:
            raise InvalidArtifactError(str(exc)) from exc
        if artifact.state in (ArtifactState.FAILED, ArtifactState.NOT_DOWNLOADED):
            raise InvalidArtifactError(f"Artifact state invalid: {artifact.state}")
        spec = getattr(artifact, "artifact", artifact)
        if getattr(spec, "format", None) != "OpenVINO IR":
            raise InvalidArtifactError("Artifact is not OpenVINO IR")
        if getattr(spec, "filename", None) != "openvino_model.xml":
            raise InvalidArtifactError("Primary OpenVINO XML missing")
        return artifact

    def _resolve_artifact(self, manifest_path: Path) -> StoredArtifact:
        try:
            artifact = self._model_store.inspect_manifest(manifest_path, verify=True)
        except Exception as exc:
            raise InvalidArtifactError(str(exc)) from exc
        if artifact.state in (ArtifactState.FAILED, ArtifactState.NOT_DOWNLOADED):
            raise InvalidArtifactError(f"Artifact state invalid: {artifact.state}")
        spec = getattr(artifact, "artifact", artifact)
        if getattr(spec, "format", None) != "OpenVINO IR":
            raise InvalidArtifactError("Artifact is not OpenVINO IR")
        if getattr(spec, "filename", None) != "openvino_model.xml":
            raise InvalidArtifactError("Primary OpenVINO XML missing")
        return artifact
    def _validate_artifact_files(self, model_dir: Path, spec: Any) -> None:
        xml_path = model_dir / "openvino_model.xml"
        if not xml_path.is_file() or xml_path.is_symlink():
            raise InvalidArtifactError("Primary OpenVINO XML missing")
        files = getattr(spec, "files", ()) or ()
        resolved_root = model_dir.resolve()
        for rel in files:
            if not isinstance(rel, str) or not rel:
                raise InvalidArtifactError("Invalid manifest file entry")
            target = (model_dir / rel).resolve()
            try:
                target.relative_to(resolved_root)
            except ValueError:
                raise InvalidArtifactError("Manifest file escapes model directory")
            if not target.is_file() or target.is_symlink():
                raise InvalidArtifactError(f"Missing declared artifact file: {rel}")
        weight_files = [p for p in model_dir.rglob("*.bin") if p.is_file() and not p.is_symlink()]
        if not weight_files:
            raise InvalidArtifactError("Missing required .bin weights")

    def _available_openvino_devices(self) -> tuple[str, ...] | None:
        if self._available_devices_checked:
            return self._available_devices
        self._available_devices_checked = True
        try:
            import openvino as ov

            core = ov.Core()
            devices = tuple(str(device) for device in core.available_devices)
            self._available_devices = devices if devices else None
        except Exception:
            self._available_devices = None
        return self._available_devices

    def generate(
        self,
        manifest_path: Path,
        prompt: str,
        *,
        device: str = "CPU",
        max_new_tokens: int = 8,
    ) -> OpenVINOGenerationResult:
        if not isinstance(max_new_tokens, int) or max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be a positive integer")
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        with self._pipeline_lock:
            artifact = self._resolve_artifact(manifest_path)
            model_dir = manifest_path.parent
            spec = getattr(artifact, "artifact", artifact)
            self._validate_artifact_files(model_dir, spec)
            self._validate_integrated_tokenizer(model_dir, spec)
            factory = self._build_pipeline_factory()
            key = (str(model_dir), device)
            if self._pipeline is not None and self._pipeline_key == key:
                pipeline = self._pipeline
            else:
                try:
                    pipeline = factory(model_dir, device)
                except Exception as exc:
                    self._pipeline = None
                    self._pipeline_key = None
                    raise PipelineInitError(str(exc)) from exc
                self._pipeline = pipeline
                self._pipeline_key = key
            try:
                result = pipeline.generate(prompt, max_new_tokens=max_new_tokens)
                text = _extract_generated_text(result)
                finish_reason = None if isinstance(result, str) else getattr(result, "finish_reason", None) or getattr(result, "status", None)
            except Exception as exc:
                raise GenerationError(str(exc)) from exc
            before = sample_xe_telemetry()
            after = sample_xe_telemetry()
            return OpenVINOGenerationResult(text=text, device=device, requested_backend=device, initialization_status="ok", effective_device="unverified", requested_device=device, available_devices=self._available_openvino_devices(), physical_telemetry={"before": before, "after": after}, finish_reason=finish_reason)

    def close(self) -> None:
        # Close the pipeline reference exactly once, even with concurrent calls.
        # The owning session coordinates the timing of this call (it waits for
        # in-flight turns and signals the service when it is safe to stop).
        with self._service_closed_lock:
            if self._service_closed:
                return
            self._service_closed = True
        with self._pipeline_lock:
            self._pipeline = None
            self._pipeline_key = None
