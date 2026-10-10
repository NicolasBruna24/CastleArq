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

"""Application Use Case: Train LoRA Adapter (bounded SFT prototype).

A separate, minimal training path that mirrors the Execute Model use case
ordering without sharing its runner or its artifact contract:

    validate request -> resolve/validate base model -> admission
      -> runner (staging dir) -> publish adapter -> TrainingResult

Boundaries (deliberate, load-bearing):

* The base model is an explicitly supplied local Transformers-compatible
  checkpoint directory. A GGUF file is NEVER a training model: GGUF inputs
  are rejected with ``UNSUPPORTED_MODEL_FORMAT`` before any runner runs.
* The execution admission (``EvaluationAdmission``) keeps its exact
  deny-by-default semantics: a supplied admission must carry an admitting
  verdict or training is refused. The ``execute`` path is untouched.
* When no execution admission is supplied, training proceeds ONLY under the
  training-specific validation boundary documented here: an explicitly
  validated local checkpoint directory plus an explicitly supplied output
  directory, with no downloads, no caching and no reuse of prior state.
  ``TrainingResult.admission_path`` records which boundary admitted the run,
  so the two paths are never confused.
* Adapter output is written to a caller-selected directory OUTSIDE the
  managed model store. The current ``ModelStore``/``ArtifactSpec`` schema is
  GGUF-artifact-addressed and has no base-model/adapter pairing concept, so
  the adapter is NOT registered as an executable CastleArq model artifact.
  Base-to-adapter lifecycle integration remains future work.
* Heavy ML dependencies (torch/transformers/peft/trl) are never imported by
  this module. The runner owns all lazy imports; a missing training stack
  surfaces as a typed ``DEPENDENCIES_MISSING`` failure, never an ImportError
  at CastleArq import time.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class TrainingErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    ADMISSION_DENIED = "admission_denied"
    UNSUPPORTED_MODEL_FORMAT = "unsupported_model_format"
    INVALID_DATASET = "invalid_dataset"
    INVALID_DESTINATION = "invalid_destination"
    DEPENDENCIES_MISSING = "dependencies_missing"
    RUN_FAILED = "run_failed"
    PUBLISH_FAILED = "publish_failed"


class TrainingPreparationError(Exception):
    """Training could not start or complete; nothing was published."""

    def __init__(
        self,
        code: TrainingErrorCode,
        message: str,
        warnings: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.warnings = tuple(warnings)


class TrainingAdmissionDeniedError(TrainingPreparationError):
    """A supplied execution admission denied training."""

    def __init__(self, message: str, warnings: tuple[str, ...] = ()) -> None:
        super().__init__(TrainingErrorCode.ADMISSION_DENIED, message, warnings)

@dataclass(frozen=True)
class TrainingRequest:
    """Input for one bounded SFT + LoRA training run.

    All paths are local. Nothing is downloaded and nothing leaves the
    machine. ``output_dir`` is a caller-selected directory outside the
    managed model store.
    """

    base_model_dir: str
    dataset_path: str
    output_dir: str
    max_steps: int = 10
    lora_rank: int = 8
    lora_alpha: int = 16


@dataclass(frozen=True)
class TrainingErrorInfo:
    code: TrainingErrorCode
    message: str


@dataclass
class TrainingResult:
    """Outcome of one training invocation."""

    success: bool
    output_dir: str | None = None
    base_model_dir: str | None = None
    files: tuple[str, ...] = ()
    steps_completed: int = 0
    final_loss: float | None = None
    # Which boundary admitted this run: "evaluation_admission" when the
    # caller supplied an admitting execution admission, otherwise
    # "local_directory_validation" (validated local checkpoint + explicit
    # output directory, no downloads, no cached state).
    admission_path: str = "local_directory_validation"
    warnings: tuple[str, ...] = ()
    error: TrainingErrorInfo | None = None


@dataclass(frozen=True)
class TrainingDependencies:
    """Explicit injectable collaborators for the training use case."""

    runner: Any | None = None


def _fail(code: TrainingErrorCode, message: str) -> TrainingPreparationError:
    return TrainingPreparationError(code, message)


def validate_training_request(request: TrainingRequest) -> None:
    """Reject malformed training requests before any filesystem work."""
    if not isinstance(request, TrainingRequest):
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST,
            "Training request must be a TrainingRequest",
        )
    for name in ("base_model_dir", "dataset_path", "output_dir"):
        value = getattr(request, name)
        if not isinstance(value, str) or not value.strip():
            raise _fail(
                TrainingErrorCode.INVALID_REQUEST,
                f"{name} must be a non-empty string",
            )
    if not isinstance(request.max_steps, int) or isinstance(
        request.max_steps, bool
    ):
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST, "max_steps must be an integer"
        )
    if not MIN_TRAINING_STEPS <= request.max_steps <= MAX_TRAINING_STEPS:
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST,
            f"max_steps must be between {MIN_TRAINING_STEPS} "
            f"and {MAX_TRAINING_STEPS}",
        )
    if not isinstance(request.lora_rank, int) or isinstance(
        request.lora_rank, bool
    ):
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST, "lora_rank must be an integer"
        )
    if not MIN_LORA_RANK <= request.lora_rank <= MAX_LORA_RANK:
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST,
            f"lora_rank must be between {MIN_LORA_RANK} "
            f"and {MAX_LORA_RANK}",
        )
    if not isinstance(request.lora_alpha, int) or request.lora_alpha <= 0:
        raise _fail(
            TrainingErrorCode.INVALID_REQUEST,
            "lora_alpha must be a positive integer",
        )



#: Admitting verdicts, mirroring ``execute_model._ADMITTING_VERDICTS``.
#: The training use case never mints an admission; it only enforces the same
#: deny-by-default verdict set when the caller supplies one.
_ADMITTING_VERDICTS = frozenset({"compatible", "compatible_with_conditions"})

#: Hard bounds for the prototype. Training is always bounded.
MIN_TRAINING_STEPS = 1
MAX_TRAINING_STEPS = 1000
MIN_LORA_RANK = 1
MAX_LORA_RANK = 64
MAX_DATASET_ROWS = 10000

#: Files that prove a directory is a Transformers-compatible checkpoint.
_TRANSFORMERS_CONFIG = "config.json"
_TRANSFORMERS_WEIGHT_SUFFIXES = (".safetensors", ".bin")

def _reject_symlink_components(path: Path) -> None:
    """Reject symlink-based escapes, mirroring ModelStore path safety."""
    current = path.absolute()
    while True:
        try:
            if os.path.islink(current):
                raise _fail(
                    TrainingErrorCode.INVALID_DESTINATION,
                    f"Path escapes through a symlink: {path}",
                )
        except TrainingPreparationError:
            raise
        except OSError as error:
            raise _fail(
                TrainingErrorCode.INVALID_DESTINATION,
                f"Cannot inspect destination path: {error}",
            )
        parent = current.parent
        if parent == current:
            return
        current = parent


def validate_base_model_dir(raw: str) -> Path:
    """Validate a local directory as a Transformers training checkpoint.

    A GGUF file or a directory containing GGUF weights is explicitly NOT a
    Transformers checkpoint and is rejected here, before any runner runs.
    """
    candidate = Path(raw).expanduser()
    if os.path.islink(candidate):
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            "Base model path must not be a symlink",
        )
    if not candidate.exists() or not candidate.is_dir():
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            "Base model directory does not exist or is not a directory: "
            + raw,
        )
    try:
        names = {entry.name for entry in candidate.iterdir()}
    except OSError as error:
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            f"Cannot read base model directory: {error}",
        )
    gguf_hits = sorted(
        name for name in names if name.lower().endswith(".gguf")
    )
    if gguf_hits:
        # A GGUF artifact is an inference artifact for llama.cpp, never a
        # Transformers training checkpoint. Refuse, do not convert.
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            "GGUF weights are not a Transformers training checkpoint "
            f"({', '.join(gguf_hits)}); supply a local Transformers "
            "checkpoint directory containing config.json and safetensors "
            "or pytorch weights",
        )
    if _TRANSFORMERS_CONFIG not in names:
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            "Base model directory is not a Transformers checkpoint: "
            "config.json is missing",
        )
    weights = sorted(
        name
        for name in names
        if name.lower().endswith(_TRANSFORMERS_WEIGHT_SUFFIXES)
    )
    if not weights:
        raise _fail(
            TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
            "Base model directory is not a Transformers checkpoint: "
            "no safetensors or pytorch weight files found",
        )
    return candidate


def validate_dataset_file(raw: str) -> list[dict[str, str]]:
    """Validate a local JSONL dataset and return its rows.

    Accepted row shape: ``{"text": "<training text>"}``. The file must be
    local; nothing is downloaded.
    """
    candidate = Path(raw).expanduser()
    if os.path.islink(candidate):
        raise _fail(
            TrainingErrorCode.INVALID_DATASET,
            "Dataset path must not be a symlink",
        )
    if not candidate.exists() or not candidate.is_file():
        raise _fail(
            TrainingErrorCode.INVALID_DATASET,
            f"Dataset file does not exist: {raw}",
        )
    if candidate.suffix.lower() not in {".jsonl", ".json"}:
        raise _fail(
            TrainingErrorCode.INVALID_DATASET,
            "Dataset must be a local .jsonl file "
            "(one JSON object per line with a 'text' field)",
        )
    rows: list[dict[str, str]] = []
    try:
        with candidate.open("r", encoding="utf-8") as stream:
            for lineno, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    raise _fail(
                        TrainingErrorCode.INVALID_DATASET,
                        f"Dataset line {lineno} is not valid JSON",
                    )
                if not isinstance(record, dict) or not isinstance(
                    record.get("text"), str
                ):
                    raise _fail(
                        TrainingErrorCode.INVALID_DATASET,
                        f"Dataset line {lineno} must be an object "
                        "with a string 'text' field",
                    )
                if not record["text"].strip():
                    raise _fail(
                        TrainingErrorCode.INVALID_DATASET,
                        f"Dataset line {lineno} has an empty 'text' field",
                    )
                rows.append({"text": record["text"]})
                if len(rows) > MAX_DATASET_ROWS:
                    raise _fail(
                        TrainingErrorCode.INVALID_DATASET,
                        "Dataset exceeds the prototype limit of "
                        f"{MAX_DATASET_ROWS} rows",
                    )
    except TrainingPreparationError:
        raise
    except OSError as error:
        raise _fail(
            TrainingErrorCode.INVALID_DATASET,
            f"Cannot read dataset file: {error}",
        )
    if not rows:
        raise _fail(
            TrainingErrorCode.INVALID_DATASET,
            "Dataset contains no usable training rows",
        )
    return rows


def validate_output_dir(raw: str) -> Path:
    """Validate a caller-selected adapter output directory.

    An existing non-empty destination is never silently overwritten.
    """
    candidate = Path(raw).expanduser()
    _reject_symlink_components(candidate)
    parent = candidate.absolute().parent
    if not parent.exists() or not parent.is_dir():
        raise _fail(
            TrainingErrorCode.INVALID_DESTINATION,
            f"Output parent directory does not exist: {parent}",
        )
    if os.path.lexists(candidate):
        if os.path.islink(candidate):
            raise _fail(
                TrainingErrorCode.INVALID_DESTINATION,
                f"Output path must not be a symlink: {raw}",
            )
        if candidate.is_file():
            raise _fail(
                TrainingErrorCode.INVALID_DESTINATION,
                f"Output path already exists as a file: {raw}",
            )
        if candidate.is_dir() and any(candidate.iterdir()):
            raise _fail(
                TrainingErrorCode.INVALID_DESTINATION,
                "Output directory already exists and is not empty: " + raw,
            )
    return candidate


def _check_admission(admission: Any) -> str:
    """Enforce deny-by-default on a supplied execution admission.

    Returns the admission path label. ``None`` means the caller supplied no
    execution admission, so the run proceeds only under the
    training-specific local-directory validation boundary. A supplied
    admission must carry an admitting verdict; anything else denies.
    """
    if admission is None:
        return "local_directory_validation"
    verdict = getattr(admission, "verdict", None)
    verdict = getattr(verdict, "value", verdict)
    normalized = (
        str(verdict).strip().lower().replace("-", "_") if verdict else ""
    )
    if normalized not in _ADMITTING_VERDICTS:
        raise TrainingAdmissionDeniedError(
            "Execution admission does not permit training "
            f"(verdict={verdict!r}); deny-by-default applies"
        )
    return "evaluation_admission"


def _write_run_metadata(
    staging: Path,
    *,
    base_model_dir: Path,
    request: TrainingRequest,
    outcome: Any,
    admission_path: str,
) -> str:
    """Write the minimum metadata identifying base model, config, result.

    Device evidence (``selected_device``/``effective_device``) is read with
    ``getattr`` defaults of ``None`` so injected/mock runners that predate
    these ``RunnerOutcome`` fields serialize safely as JSON ``null``
    (unknown device), never as an invented device.
    """
    payload = {
        "base_model_dir": str(base_model_dir),
        "lora_rank": request.lora_rank,
        "lora_alpha": request.lora_alpha,
        "max_steps": request.max_steps,
        "steps_completed": getattr(outcome, "steps_completed", 0),
        "final_loss": getattr(outcome, "final_loss", None),
        "selected_device": getattr(outcome, "selected_device", None),
        "effective_device": getattr(outcome, "effective_device", None),
        "admission_path": admission_path,
        "note": (
            "LoRA adapter output. Not a generally executable CastleArq "
            "model artifact; base-to-adapter lifecycle integration is "
            "future work."
        ),
    }
    metadata_path = staging / "training_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    return metadata_path.name


def train_adapter_model(
    request: TrainingRequest,
    *,
    admission: Any = None,
    dependencies: TrainingDependencies | None = None,
) -> TrainingResult:
    """Run one bounded SFT + LoRA training and publish the adapter.

    Order: validate request -> validate base model -> validate dataset ->
    validate destination -> admission gate -> runner (staging only) ->
    metadata -> atomic publish. Validation and admission failures are
    returned as failed ``TrainingResult`` values (never raised), mirroring
    how ``execute_model`` returns failure ``ExecutionResult`` values. A
    failed run never publishes partial output, and user data outside the
    staging directory is never deleted.
    """
    try:
        validate_training_request(request)
        base_model_dir = validate_base_model_dir(request.base_model_dir)
        rows = validate_dataset_file(request.dataset_path)
        output_dir = validate_output_dir(request.output_dir)
        admission_path = _check_admission(admission)
    except TrainingPreparationError as error:
        base_hint: str | None = None
        try:
            base_hint = str(
                Path(request.base_model_dir)
                if isinstance(request, TrainingRequest)
                else None
            )
        except Exception:
            base_hint = None
        return TrainingResult(
            success=False,
            output_dir=None,
            base_model_dir=base_hint,
            admission_path="local_directory_validation",
            warnings=error.warnings,
            error=TrainingErrorInfo(code=error.code, message=error.message),
        )

    deps = dependencies if dependencies is not None else TrainingDependencies()
    runner = deps.runner
    if runner is None:
        from .training_runner import SftLoraRunner

        runner = SftLoraRunner()

    staging_parent = output_dir.absolute().parent
    staging = Path(
        tempfile.mkdtemp(prefix="castlearq-train-", dir=str(staging_parent))
    )
    published = False
    try:
        run = runner.run(
            base_model_dir=base_model_dir,
            dataset_rows=rows,
            staging_dir=staging,
            max_steps=request.max_steps,
            lora_rank=request.lora_rank,
            lora_alpha=request.lora_alpha,
        )
        metadata_name = _write_run_metadata(
            staging,
            base_model_dir=base_model_dir,
            request=request,
            outcome=run,
            admission_path=admission_path,
        )
        files = tuple(sorted({*getattr(run, "files", ()), metadata_name}))
        try:
            os.rename(staging, output_dir)
        except OSError as error:
            raise _fail(
                TrainingErrorCode.PUBLISH_FAILED,
                f"Could not publish adapter to {output_dir}: {error}",
            )
        published = True
        return TrainingResult(
            success=True,
            output_dir=str(output_dir),
            base_model_dir=str(base_model_dir),
            files=files,
            steps_completed=int(getattr(run, "steps_completed", 0)),
            final_loss=getattr(run, "final_loss", None),
            admission_path=admission_path,
        )
    except TrainingPreparationError as error:
        return TrainingResult(
            success=False,
            output_dir=None,
            base_model_dir=str(base_model_dir),
            admission_path=admission_path,
            warnings=error.warnings,
            error=TrainingErrorInfo(code=error.code, message=error.message),
        )
    except Exception as error:  # runner defects are typed run failures
        return TrainingResult(
            success=False,
            output_dir=None,
            base_model_dir=str(base_model_dir),
            admission_path=admission_path,
            error=TrainingErrorInfo(
                code=TrainingErrorCode.RUN_FAILED,
                message=(
                    "Training runner failed: "
                    f"{type(error).__name__}: {error}"
                ),
            ),
        )
    finally:
        if not published and staging.exists():
            # Only the staging directory this invocation created is
            # removed; user data is never touched.
            shutil.rmtree(staging, ignore_errors=True)
