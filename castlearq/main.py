
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

"""Command-line interface for CastleArq."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from types import SimpleNamespace

from .api import serve
from .run_service import (
    ExecutionPreparation,
    PreparationError,
    detect_runtime_statuses as _detect_runtime_statuses,
    prepare as _prepare,
)
from .compatibility import CompatibilityConfig, CompatibilityStatus, assess_model, load_config, recommend_models
from .execution import ArtifactExecutionPreflight, ArtifactPreflightError, ExecutionRequest, ExecutableArtifact, PreflightErrorCode
from . import gpu_diagnosis
from . import json_output
from .gpu_diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    GpuComponent,
    Recommendation,
)
from .gpu_setup import GpuSoftwareStatus, diagnose_gpu_software
from .gpu_diagnosis import MissingComponent, FunctionalCheck
from .remediation import (
    COMPONENT_LABELS,
    RemediationPlan,
    build_remediation_plan,
)
from .remediation_verification import (
    format_remediation_verification,
    verify_remediation,
)
from .session import (
    DiagnosisSession,
    MissingComponentRecord,
    SessionError,
    clear_session,
    load_session,
    save_session,
)
from .hardware import (
    GPUInfo,
    HardwareSnapshot,
    detect_hardware,
    detect_platform,
)
from .model_catalog import get_catalog
from .model_identity import (
    downloadable_locator,
    logical_model_id,
    source_repositories_for_logical_model,
)
from .model_store import (
    ModelStore,
    ModelStoreResolution,
    StoredArtifact,
    UnsafePathError,
    legacy_store_notice,
    resolve_model_store,
)
from .version import get_version
from .downloads import (
    DownloadPlan,
    DownloadPlanStatus,
    DownloadPlanner,
    DownloadResult,
    DownloadResultStatus,
    Downloader,
)
from .models import ArtifactSpec, ArtifactState, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runtimes import (
    RuntimeCapability,
    RuntimeAvailability,
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
    detect_runtimes,
    recommend,
    resolve_llama_runtime,
)
from .runner import LlamaCppRunner
from .selection import RuntimeBackendSelector, RuntimeSelection, RuntimeSelectionError
from .sources import HuggingFaceSource, SourceError
from .sources.huggingface import _download_url, detect_quantization
from .chat import ChatSessionError, start_chat_session
from .artifact_selection import ArtifactSelectionError, select_artifact
from .application_wiring import (
    compose_acquisition_service,
    compose_execute_model_dependencies,
)
from .acquisition_service import (
    AcquisitionError,
    AcquisitionErrorCategory,
    AcquisitionOutcome,
    AcquisitionStatus,
    ModelAcquisitionService,
)
from .discovery import DiscoveryError, ModelDiscovery
from .execute_model import (
    ExecuteAdmissionDeniedError,
    ExecutePreparationError,
    execute_model,
)
from .evaluate_compatibility import (
    EvaluateCompatibilityDependencies,
    evaluate_model_compatibility,
    to_admission,
)
from .compatibility_report import (
    evaluation_report,
    format_evaluation_report,
)
from .compatibility_domain import CheckStatus
from .validation_report import format_validation_report
from .importing import ImportStatus, LocalArtifactImporter
from pathlib import Path


def _catalog_model_ids() -> frozenset[str]:
    """Logical model IDs currently known by the compatibility catalog.

    Kept intentionally small and CLI-local so that no source or store gains a
    backwards dependency on the catalog. Discovery remains discovery; this is
    only a presentation/validation aid so the user sees which logical model a
    source artifact maps to and whether that model is known.
    """
    return frozenset(model.model_id for model in get_catalog())


_DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0


def _format_gib(value: float | None) -> str:
    return f"{value:.0f} GB" if value is not None else "Unknown"


def _format_mib(value: float | None) -> str:
    return f"{value * 1024:.0f} MiB" if value is not None else "Unknown"


def _json_detect_payload(hardware, runtimes, backends, runtime, backend) -> dict:
    """Project the existing ``detect`` result; recompute nothing.

    Hardware detection keeps its own vocabulary: an empty GPU list means
    "no GPU was detected" (a definite observation, so it stays ``[]``), and
    a GPU property that exists in the model but was not observed on this
    machine (PCI id, VRAM, driver) uses the UNKNOWN structure. This payload
    is hardware detection, NOT the runtime capability model of
    ``runtime --json``, and not a compatibility evaluation.
    """
    # ``recommend()`` returns this display sentinel when nothing was
    # available; JSON reports the definite absence as null, never UNKNOWN.
    recommended_runtime = None if runtime == "None detected" else runtime
    recommended_backend = None if backend == "None detected" else backend
    return {
        "system": {
            "operating_system": _json_observed_text(hardware.operating_system),
            "architecture": _json_observed_text(hardware.architecture),
        },
        "cpu": {
            "model": _json_observed_text(hardware.cpu.model),
            "architecture": _json_observed_text(hardware.cpu.architecture),
            "cores": _json_observed(hardware.cpu.cores),
        },
        "memory": {
            "total_bytes": _json_observed(hardware.memory.total_bytes),
        },
        "gpus": [
            {
                "name": _json_observed_text(gpu.name),
                "vendor": _json_observed_text(gpu.vendor),
                "pci_id": _json_observed(gpu.pci_id),
                "device_id": _json_observed(gpu.device_id),
                "driver": _json_observed_text(gpu.driver),
                "vram_bytes": _json_observed(gpu.vram_bytes),
                "vram_available_bytes": _json_observed(
                    gpu.vram_available_bytes
                ),
                "sources": dict(gpu.sources),
                "backends": list(gpu.backends),
            }
            for gpu in hardware.gpus
        ],
        "runtimes": [
            {
                "name": item.name,
                "label": item.label,
                "installed": item.installed,
                "available": item.available,
                "gpu_backend_detected": item.gpu_backend_detected,
                "supported_backends": list(item.supported_backends),
            }
            for item in runtimes
        ],
        "backends": [
            {"name": item.name, "available": item.available}
            for item in backends
        ],
        "recommendation": {
            "runtime": recommended_runtime,
            "backend": recommended_backend,
        },
    }


def print_detection(*, as_json: bool = False) -> None:
    hardware = detect_hardware()
    runtimes = detect_runtimes()
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)
    runtime, backend = recommend(runtimes, backends)

    if as_json:
        _emit_json_envelope(
            "detect",
            0,
            _json_detect_payload(hardware, runtimes, backends, runtime, backend),
        )
        return

    print("CastleArq")
    print("==========================")
    print("\nSystem")
    print(f"  OS: {hardware.operating_system}")
    print(f"  Architecture: {hardware.architecture}")
    print("\nCPU")
    print(f"  {hardware.cpu.model}")
    print("\nMemory")
    print(f"  RAM: {_format_gib(hardware.memory.total_gib)}")
    print("\nGPU")
    if hardware.gpus:
        for gpu in hardware.gpus:
            print(f"  {gpu.name}")
            print(f"  Vendor: {gpu.vendor}")
            print(f"  PCI ID: {gpu.pci_id or 'Unknown'}")
            print(f"  Driver: {gpu.driver}")
            print(f"  VRAM: {_format_mib(gpu.vram_gib)}")
            print(f"  VRAM available: {_format_mib(gpu.vram_available_gib)}")
            print(f"  VRAM source: {gpu.sources.get('vram', 'unavailable')}")
            print(f"  Backends: {', '.join(gpu.backends) if gpu.backends else 'None detected'}")
    else:
        print("  Not detected")
    print("\nRuntimes")
    for item in runtimes:
        print(f"  {item.name}: {item.label}")
    print("\nBackends")
    for item in backends:
        print(f"  {item.name}: {'available' if item.available else 'not available'}")
    print("\nRecommendation")
    print(f"  Recommended runtime: {runtime}")
    print(f"  Recommended backend: {backend}")


@dataclass(frozen=True)
class GpuDiagnosisReport:
    """Read-only result of the CLI ``diagnose`` command."""

    hardware: HardwareSnapshot
    software: GpuSoftwareStatus
    gpu: GPUInfo | None
    runtime: str
    backend: str
    platform: str
    diagnosis: DiagnosisResult
    recommendation: Recommendation
    plan: RemediationPlan


def _diagnosis_runtime_key(runtime_label: str) -> str:
    """Map a detected runtime label to the canonical diagnosis key.

    Detection labels look like ``"llama.cpp / llama.app"`` while the B2
    matrix is keyed by the canonical runtime (``"llama.cpp"``). Unmodelled
    labels are preserved so the diagnosis reports them as unknown instead of
    inventing support.
    """
    return runtime_label.split("/", 1)[0].strip().lower()


def _component_state(component: GpuComponent, diagnosis: DiagnosisResult) -> str:
    """Project one component's state from the diagnosis public output."""
    if any(item.component is component for item in diagnosis.missing_components):
        return "MISSING"
    if f"{component.value} status unknown" in diagnosis.warnings:
        return "UNKNOWN"
    return "READY"


def build_gpu_diagnosis_report(
    *,
    hardware: HardwareSnapshot,
    software: GpuSoftwareStatus,
    runtime: str,
    backend: str,
    platform: str,
) -> GpuDiagnosisReport:
    """Run the pure B2/B3 pipeline over already-detected facts (no I/O)."""
    gpu = hardware.gpus[0] if hardware.gpus else None
    canonical_runtime = _diagnosis_runtime_key(runtime)
    diagnosis = gpu_diagnosis.diagnose(
        software=software,
        runtime=canonical_runtime,
        backend=backend,
        gpu=gpu,
        platform=platform,
    )
    recommendation = gpu_diagnosis.recommend(diagnosis)
    plan = build_remediation_plan(diagnosis)
    return GpuDiagnosisReport(
        hardware=hardware,
        software=software,
        gpu=gpu,
        runtime=canonical_runtime,
        backend=backend,
        platform=platform,
        diagnosis=diagnosis,
        recommendation=recommendation,
        plan=plan,
    )


def format_gpu_diagnosis_report(report: GpuDiagnosisReport) -> str:
    """Render a report as human-readable text (never a Python object dump)."""
    lines = [
        "CastleArq — GPU diagnosis",
        "==========================",
        "",
        "System",
        f"  OS: {report.hardware.operating_system}",
        f"  Architecture: {report.hardware.architecture}",
        "",
        "GPU",
    ]
    if report.gpu is not None:
        lines.extend(
            (
                f"  {report.gpu.name}",
                f"  Vendor: {report.gpu.vendor}",
                f"  Driver: {report.gpu.driver}",
            )
        )
    else:
        lines.append("  Not detected")
    lines.extend(
        (
            "",
            "Target",
            f"  Platform: {report.platform or 'Unknown'}",
            f"  Runtime: {report.runtime or 'Unknown'}",
            f"  Backend: {report.backend or 'Unknown'}",
            "",
            "GPU software",
        )
    )
    requirements = gpu_diagnosis.requirements_for(report.runtime, report.backend)
    if requirements is None:
        lines.append("  No requirement model for this runtime/backend pair.")
    elif not requirements:
        lines.append("  No GPU software components are required.")
    else:
        for requirement in requirements:
            label = COMPONENT_LABELS.get(
                requirement.component, requirement.component.value)
            state = _component_state(requirement.component, report.diagnosis)
            lines.append(f"  {label}: {state}")
    lines.extend(
        (
            "",
            "Diagnosis",
            f"  Overall status: {report.diagnosis.status.value.upper()}",
        )
    )
    if report.diagnosis.warnings:
        lines.extend(("", "Warnings"))
        lines.extend(f"  - {warning}" for warning in report.diagnosis.warnings)
    lines.extend(("", "Recommendations"))
    if report.recommendation.recipe_refs:
        lines.extend(
            f"  - {recipe}" for recipe in report.recommendation.recipe_refs)
    elif report.diagnosis.status is DiagnosisStatus.MISSING_COMPONENT:
        lines.append("  No compatible recipe found for this platform.")
    elif report.diagnosis.status is DiagnosisStatus.READY:
        lines.append("  No remediation required.")
    else:
        lines.append("  No remediation available until the status is confirmed.")
    lines.extend(("", "Remediation plan"))
    lines.append(f"  Status: {report.plan.status.value.upper()}")
    if report.plan.actions:
        for action in report.plan.actions:
            lines.append(f"  {action.order}. {action.description}")
        lines.append("")
        lines.append(
            "Authorization required: "
            + ("yes" if report.plan.requires_authorization else "no"))
    else:
        for note in report.plan.notes:
            lines.append(f"  {note}")
    lines.append("No actions have been executed.")
    return "\n".join(lines)


def _diagnosis_session(report: GpuDiagnosisReport) -> DiagnosisSession:
    """Capture the context ``verify`` will need later (data only)."""
    return DiagnosisSession(
        schema_version=1,
        original_status=report.diagnosis.status,
        # Canonical keys (as canonicalised by diagnose), not the raw labels,
        # so verify always compares against the same reference context.
        runtime=report.diagnosis.runtime,
        backend=report.diagnosis.backend,
        platform=report.platform,
        missing=tuple(
            MissingComponentRecord(
                component=missing.component.value,
                required_by=missing.required_by,
                detail=missing.evidence.detail,
                source=missing.evidence.source,
            )
            for missing in report.diagnosis.missing_components
        ),
    )


def _diagnosis_from_session(session: DiagnosisSession) -> DiagnosisResult:
    """Rebuild the original diagnosis from persisted, validated data.

    Only confirmed absences were persisted (``passed`` is always ``False``),
    so ``MissingComponent``'s invariant still holds: unknown evidence is never
    turned into a missing component. An unknown component name is rejected as
    an invalid session rather than silently ignored.
    """
    components: list[MissingComponent] = []
    for record in session.missing:
        try:
            component = GpuComponent(record.component)
        except ValueError as error:
            raise ValueError(
                f"unknown component in session: {record.component!r}"
            ) from error
        components.append(
            MissingComponent(
                component,
                FunctionalCheck(False, record.detail, record.source),
                record.required_by,
            )
        )
    return DiagnosisResult(
        status=session.original_status,
        missing_components=tuple(components),
        runtime=session.runtime,
        backend=session.backend,
        platform=session.platform,
    )


def print_gpu_diagnosis() -> int:
    """Observe the environment and print the GPU software diagnosis.

    Reuses the existing detection pipeline (``hardware`` + ``gpu_setup``) and
    the pure B2/B3 modules. Read-only: it never installs, downloads or
    modifies the system, and never executes a recipe. When a component is
    confirmed missing, the context needed by ``verify`` is persisted as data
    under ``~/.castlearq/sessions/`` (never executed, never a system file).
    """
    hardware = detect_hardware()
    runtime_label, backend_label = recommend(
        detect_runtimes(),
        detect_backends(
            detected_gpu_backends={
                backend for gpu in hardware.gpus for backend in gpu.backends
            }
        ),
    )
    gpu = hardware.gpus[0] if hardware.gpus else None
    software = diagnose_gpu_software(
        driver=gpu.driver if gpu is not None else "Unknown")
    report = build_gpu_diagnosis_report(
        hardware=hardware,
        software=software,
        runtime=runtime_label,
        backend=backend_label,
        platform=detect_platform(hardware.operating_system),
    )
    print(format_gpu_diagnosis_report(report))
    if report.diagnosis.status is DiagnosisStatus.MISSING_COMPONENT:
        try:
            save_session(_diagnosis_session(report))
        except OSError as error:
            print(f"Warning: could not persist verification session: {error}")
        else:
            print(
                "Verification session saved. Apply the remediation manually,"
                " then run: python3 -m castlearq.main verify")
    return 0


def print_remediation_verification() -> int:
    """Re-observe the environment and verify the remediation (read-only).

    Loads the persisted session, rebuilds the original diagnosis and plan
    with the pure B5 builder, obtains a fresh state through the existing
    read-only probes, and compares them with the pure B7 verification.
    Nothing is ever executed: neither plan commands nor recipe commands.
    """
    try:
        session = load_session()
    except (SessionError, OSError) as error:
        print(f"Verification session is unusable: {error}")
        print("Run 'python3 -m castlearq.main diagnose' to create a new one.")
        return 2
    if session is None:
        print("No previous diagnosis session found.")
        print("Run 'python3 -m castlearq.main diagnose' first.")
        return 0
    try:
        original = _diagnosis_from_session(session)
    except ValueError as error:
        print(f"Verification session is unusable: {error}")
        print("Run 'python3 -m castlearq.main diagnose' to create a new one.")
        return 2

    plan = build_remediation_plan(original)
    hardware = detect_hardware()
    runtime_label, backend_label = recommend(
        detect_runtimes(),
        detect_backends(
            detected_gpu_backends={
                backend for gpu in hardware.gpus for backend in gpu.backends
            }
        ),
    )
    gpu = hardware.gpus[0] if hardware.gpus else None
    software = diagnose_gpu_software(
        driver=gpu.driver if gpu is not None else "Unknown")
    # The comparison is anchored to the original context; if the environment
    # now recommends a different pair, it is reported as a warning instead of
    # silently changing the reference.
    followup = gpu_diagnosis.diagnose(
        software=software,
        runtime=session.runtime,
        backend=session.backend,
        platform=session.platform,
    )
    extra_warnings: list[str] = []
    current_runtime = _diagnosis_runtime_key(runtime_label)
    if current_runtime != session.runtime:
        extra_warnings.append(
            f"the environment now recommends runtime {current_runtime!r}"
            f" (original: {session.runtime!r})")
    if backend_label.strip().lower() != session.backend:
        extra_warnings.append(
            f"the environment now recommends backend {backend_label!r}"
            f" (original: {session.backend!r})")
    current_platform = detect_platform(hardware.operating_system)
    if current_platform != session.platform:
        extra_warnings.append(
            f"detected platform changed to {current_platform!r}"
            f" (original: {session.platform!r})")
    verification = verify_remediation(original, plan, followup, software)
    print(format_remediation_verification(
        verification, extra_warnings=tuple(extra_warnings)))
    return 0


def _download_status(model_id: str) -> str:
    """Describe whether a logical model currently has a downloadable source.

    Availability comes exclusively from ``downloadable_locator`` so this
    presentation always agrees with the ``download`` command gate. The reason
    text for non-available models is derived from the same static mapping, so
    ``models`` stays offline and never guesses among multiple locators.
    """
    locator = downloadable_locator(model_id)
    if locator is not None:
        source, repository = locator
        return f"available ({source}: {repository})"
    locators = source_repositories_for_logical_model(model_id)
    if len(locators) > 1:
        return "unavailable (multiple sources mapped)"
    if len(locators) == 1:
        return "unavailable (unsupported source)"
    return "not available yet"


def _json_models_payload(hardware, results) -> dict:
    """Project the existing ``models`` result; recompute nothing.

    The catalog assessment belongs to the LEGACY compatibility domain
    (``castlearq.compatibility``: compatible / marginal / incompatible / unknown),
    which is NOT the strict B9.3 evaluation vocabulary. It is therefore
    reported under its own ``legacy_compatibility`` name so the two can
    never be read as the same thing, and its enum travels as ``.value``.

    A ``None`` here always means "not determined" for the memory estimate
    and the recommended quantization, so both use the UNKNOWN structure; a
    missing recommended runtime/backend is a definite "none recommended"
    and stays ``null``.
    """
    known_vram = [
        gpu.vram_available_bytes if gpu.vram_available_bytes is not None
        else gpu.vram_bytes
        for gpu in hardware.gpus
        if gpu.vram_available_bytes is not None or gpu.vram_bytes is not None
    ]
    models = []
    for result in results:
        quantization = result.recommended_quantization
        models.append({
            "model_id": result.model.model_id,
            "name": result.model.name,
            # Availability comes from the same downloadable locator the
            # `download` gate uses, so the two can never disagree.
            "download": _download_status(result.model.model_id),
            "legacy_compatibility": {
                "status": result.status.value,
                "score": result.score,
                "reasons": list(result.reasons),
                "warnings": list(result.warnings),
            },
            "memory": _json_observed(result.estimated_memory_bytes),
            "memory_is_estimate": result.memory_is_estimate,
            "quantization": _json_observed(
                quantization.name if quantization is not None else None
            ),
            "runtime": result.recommended_runtime,
            "backend": result.recommended_backend,
        })
    return {
        "hardware": {
            "ram_bytes": _json_observed(hardware.memory.total_bytes),
            "gpu_count": len(hardware.gpus),
            "vram_bytes_per_gpu": known_vram if known_vram else None,
        },
        "models": models,
    }


def print_models(*, as_json: bool = False) -> None:
    hardware = detect_hardware()
    runtimes = detect_runtimes()
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)
    results = recommend_models(
        hardware, runtimes, backends, get_catalog(), config=load_config()
    )
    if as_json:
        # Same detection, same catalog, same recommendations: only the
        # representation changes. The per-model warnings stay in the payload,
        # where they belong to that model's assessment.
        _emit_json_envelope(
            "models", 0, _json_models_payload(hardware, results)
        )
        return
    print("CastleArq - Model recommendations")
    print("==========================")
    if not results:
        print("No models available in the catalog.")
        return
    known_vram = [
        gpu.vram_available_gib if gpu.vram_available_bytes is not None
        else gpu.vram_gib
        for gpu in hardware.gpus
        if gpu.vram_available_bytes is not None or gpu.vram_bytes is not None
    ]
    vram_summary = (
        ", ".join(_format_mib(value) for value in known_vram)
        if known_vram
        else "Unknown"
    )
    print(f"\nHardware: {_format_gib(hardware.memory.total_gib)} RAM")
    print(f"  VRAM per GPU: {vram_summary}")
    if len(hardware.gpus) > 1:
        print("  Multi-GPU analysis: not supported")
    for index, result in enumerate(results, 1):
        quantization = result.recommended_quantization
        memory = (
            f"{result.estimated_memory_bytes / (1024**3):.1f} GiB estimated"
            if result.estimated_memory_bytes is not None
            else "Unknown memory"
        )
        print(f"\n{index}. {result.model.name}")
        print(f"  Model ID: {result.model.model_id}")
        print(f"  Download: {_download_status(result.model.model_id)}")
        print(f"  Status: {result.status.value.upper()}")
        print(f"  Score: {result.score}")
        print(f"  Quantization: {quantization.name if quantization else 'Unknown'}")
        print(f"  Memory: {memory}")
        print(f"  Runtime: {result.recommended_runtime or 'None'}")
        print(f"  Backend: {result.recommended_backend or 'None'}")
        for reason in result.reasons:
            print(f"  Reason: {reason}")
        for warning in result.warnings:
            print(f"  Warning: {warning}")


def _format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "Unknown"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MiB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GiB"


# B9.76.3: the commands that accept ``--json`` in this block. The option is
# deliberately not global: every other command keeps argparse's behaviour of
# rejecting it, so the JSON surface grows one MUST command at a time.
_JSON_COMMANDS = (
    "compatibility",
    "validate",
    "list",
    "store",
    "import",
    # B9.76.5: the SHOULD surface. Same envelope, four different domains.
    "models",
    "runtime",
    "detect",
    "plan",
)


def _emit_json_envelope(
    command: str,
    exit_code: int,
    payload: dict,
    *,
    error: dict | None = None,
    warnings: tuple[str, ...] = (),
    out=None,
) -> int:
    """Print exactly one ``castlearq.cli`` envelope and return ``exit_code``.

    The command built the payload and decided the exit code; the shared
    ``castlearq.json_output`` layer owns the envelope and the serialization. This
    helper never invents data and never derives an exit code: the code it is
    given is the code the process returns.
    """
    out = out if out is not None else sys.stdout
    envelope = json_output.CliEnvelope(
        command=command,
        exit_code=exit_code,
        payload=payload,
        error=error,
        warnings=warnings,
    )
    print(json_output.dumps(envelope), file=out)
    return exit_code


def _json_quantization(value: str) -> dict:
    """Represent a quantization string as an explicit observation.

    ``ArtifactSpec.quantization`` defaults to the ``"Unknown"`` sentinel, so
    an unobserved quantization becomes the ratified unknown structure and is
    never fabricated from a filename; a real value stays a known observation.
    """
    if value == "Unknown":
        return json_output.unknown("not_observed")
    return json_output.known(value)


def _json_observed(value) -> dict:
    """Represent an optional observed value without inventing a sentinel.

    ``None`` here means "this property exists in the domain model but was
    not observed on this machine" (an absent runtime version, an unprobed
    capability). It is reported as the ratified UNKNOWN structure, never as
    the string ``"Unknown"`` and never as a bare ``null``. A ``None`` that
    means "definitely absent" (no GPU detected, no runtime recommended) is
    NOT routed here: it stays ``null``.
    """
    if value is None:
        return json_output.unknown("not_observed")
    return json_output.known(value)


def _json_observed_text(value) -> dict:
    """Represent a text field whose domain default is the ``"Unknown"`` sentinel.

    ``CPUInfo.model``/``architecture``, ``GPUInfo.name``/``vendor``/``driver``
    and the snapshot's system strings all default to the literal ``"Unknown"``
    when the detector could not read them. That sentinel is a display value,
    not data: it becomes the ratified UNKNOWN structure here, so no
    ``"Unknown"`` datum ever reaches the JSON surface.
    """
    if value is None or value == "Unknown":
        return json_output.unknown("not_observed")
    return json_output.known(value)


def _json_artifact(artifact: ArtifactSpec | None) -> dict | None:
    """Project the artifact identity already present on ``ArtifactSpec``.

    Only existing fields are exposed. The declared integrity digest
    (``sha256``) and the computed content identity (``content_id``) stay two
    separate keys: neither is ever presented as the other.
    """
    if artifact is None:
        return None
    return {
        "model_id": artifact.model_id,
        "filename": artifact.filename,
        "quantization": _json_quantization(artifact.quantization),
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
        "content_id": artifact.content_id,
    }


def _json_validation_payload(
    *,
    artifact: ArtifactSpec,
    safety: CheckStatus,
    size: CheckStatus,
    integrity: CheckStatus,
    state: ArtifactState | None,
    problem: str | None = None,
) -> dict:
    """Build the ``validate --json`` payload from evidence already derived.

    The three P1.2 dimensions are reported as check statuses (enums through
    the shared serializer). The declared size and the declared SHA-256 are
    separate properties: an absent declaration stays explicitly UNKNOWN with
    its architecture-backed reason instead of collapsing into ``null``, and
    a present declaration stays a known value even when a different check
    failed before it could run.
    """
    declared_size = (
        json_output.unknown("no_size_declared")
        if artifact.size_bytes is None
        else json_output.known(artifact.size_bytes)
    )
    declared_sha256 = (
        json_output.unknown("no_checksum_declared")
        if artifact.sha256 is None
        else json_output.known(artifact.sha256)
    )
    return {
        "artifact": _json_artifact(artifact),
        "state": state,
        "checks": {
            "safety": safety,
            "size": size,
            "integrity": integrity,
        },
        "declared_size": declared_size,
        "declared_sha256": declared_sha256,
        "problem": problem,
    }


def _group_local_artifacts(
    entries: list[StoredArtifact],
) -> tuple[list[tuple[str, list[StoredArtifact]]], list[StoredArtifact]]:
    """Group stored artifacts by model and order them as ``list`` shows them.

    Shared by the human and the JSON paths so the two surfaces can never
    drift in selection or ordering: models sorted by id, artifacts sorted by
    filename, invalid manifests last, sorted by manifest path.
    """
    grouped: dict[str, list[StoredArtifact]] = {}
    invalid_entries: list[StoredArtifact] = []
    for entry in entries:
        if entry.artifact is None:
            invalid_entries.append(entry)
            continue
        grouped.setdefault(entry.artifact.model_id, []).append(entry)
    ordered = [
        (
            model_id,
            sorted(grouped[model_id], key=lambda e: e.artifact.filename),  # type: ignore[union-attr]
        )
        for model_id in sorted(grouped.keys())
    ]
    invalid_entries.sort(key=lambda e: str(e.manifest_path))
    return ordered, invalid_entries


def print_local_models(model_store: ModelStore | None = None) -> None:
    """List the artifacts of the model store selected for this invocation.

    ``model_store`` is the store B9.74 resolved for the invocation (from
    ``--model-store``); when it is omitted the command resolves the store
    itself through the same single resolution function, so both paths name the
    same root.
    """
    print("CastleArq - Local models")
    print("==========================")
    store = model_store or ModelStore()
    entries = store.list_artifacts()
    if not entries:
        print("No local model artifacts found.")
        return

    # Group valid artifacts by logical model_id; ordering shared with the
    # B9.76.3 JSON path so both surfaces show exactly the same artifacts.
    ordered, invalid_entries = _group_local_artifacts(entries)

    for model_id, artifacts in ordered:
        print(f"\n{model_id}")
        for entry in artifacts:
            artifact = entry.artifact
            assert artifact is not None
            size = _format_size(artifact.size_bytes)
            status_str = entry.state.value.upper()
            print(f"  - filename: {artifact.filename}")
            print(f"    quantization: {artifact.quantization}")
            print(f"    size: {size}")
            print(f"    status: {status_str}")
            if entry.message:
                print(f"    problem: {entry.message}")

    if invalid_entries:
        print("\nInvalid artifacts:")
        for entry in invalid_entries:
            print(f"  - {entry.manifest_path} ({entry.message or 'invalid manifest'})")


def list_command(
    model_store: ModelStore | None = None,
    *,
    out=None,
) -> int:
    """Emit the ``list --json`` document (B9.76.3).

    Read-only: the same store selection, the same artifacts and the same
    ordering as :func:`print_local_models`, only the representation changes.
    Exit ``0`` exactly like the human path, which returns ``None`` (success).
    """
    out = out if out is not None else sys.stdout
    store = model_store or ModelStore()
    ordered, invalid_entries = _group_local_artifacts(store.list_artifacts())
    artifacts: list[dict] = []
    for model_id, entries in ordered:
        for entry in entries:
            artifact = entry.artifact
            assert artifact is not None
            artifacts.append(
                {
                    "model_id": model_id,
                    "filename": artifact.filename,
                    "quantization": _json_quantization(artifact.quantization),
                    "size_bytes": artifact.size_bytes,
                    "status": entry.state,
                    "problem": entry.message,
                }
            )
    payload = {
        "artifacts": artifacts,
        "invalid_artifacts": [
            {
                "path": str(entry.manifest_path),
                "problem": entry.message or "invalid manifest",
            }
            for entry in invalid_entries
        ],
    }
    return _emit_json_envelope("list", 0, payload, out=out)


def _json_import_payload(result) -> dict:
    """Project one import result into the ``import --json`` payload.

    Mirrors what the human report already states, and adds nothing: the
    observed GGUF evidence, the managed location, the computed content
    identity, and the three properties an imported artifact provably does
    NOT have.

    Two separations are load-bearing and are preserved verbatim (B9.67):

    * ``content_id`` is the *computed* identity of the bytes that were
      imported. It is never an integrity declaration: the importer
      deliberately leaves ``ArtifactSpec.sha256`` unset, so ``integrity``
      stays UNKNOWN (``not_declared``) even though a content identity
      exists. The digest is never copied into ``sha256``.
    * The sanitized label is addressing and presentation, not a logical
      identity. Nothing read here establishes which model the file is, so
      ``logical_identity`` stays UNKNOWN (``no_catalog_evidence``) and no
      model id is ever synthesized from the label, the filename, the
      architecture or the content id.
    """
    artifact = result.artifact
    return {
        "status": result.status.value,
        "label": result.sanitized_label,
        "content_id": result.content_id,
        "format": (
            json_output.known(artifact.format)
            if artifact is not None
            else json_output.unknown("not_observed")
        ),
        "architecture": (
            json_output.known(result.architecture)
            if result.architecture
            else json_output.unknown("not_observed")
        ),
        "storage": {
            "path": (
                str(result.destination)
                if result.destination is not None
                else None
            ),
            "filename": result.filename,
        },
        "logical_identity": json_output.unknown("no_catalog_evidence"),
        "integrity": (
            json_output.known(artifact.sha256)
            if artifact is not None and artifact.sha256 is not None
            else json_output.unknown("not_declared")
        ),
        "memory_estimate": json_output.unknown("not_observed"),
    }


def import_command(
    path: str | None,
    *,
    label: str | None = None,
    model_store: ModelStore | None = None,
    as_json: bool = False,
) -> int:
    """Import a local GGUF file into the managed model store (B9.67).

    This is a presentation layer only. Every decision -- source validation,
    GGUF validation, content digest, label sanitization, duplicate detection,
    atomic publication and manifest registration -- belongs to
    ``LocalArtifactImporter``. The CLI deliberately computes no hash, copies
    no file and builds no ``ArtifactSpec``, so there is exactly one place
    where import policy can live.

    Nothing is resolved or executed here: importing makes an artifact
    available, and the user runs it later through the existing commands.
    """
    if not path:
        usage = (
            "Usage: python3 -m castlearq.main import <path-to-gguf> [--label LABEL]"
        )
        if as_json:
            # The human usage line goes to stdout, which JSON mode must keep
            # pure, so it moves to stderr next to the structured envelope.
            print(usage, file=sys.stderr)
            return _emit_json_envelope(
                "import",
                2,
                {},
                error=json_output.error("usage_error", usage),
            )
        print(usage)
        return 2
    # `LocalArtifactImporter` inspects the path itself. Expanding `~` here is
    # shell convenience, not validation: no sanitizer is duplicated. The store
    # is the one B9.74 resolved for this invocation, so an import lands in the
    # selected store and nowhere else.
    importer = LocalArtifactImporter(
        model_store if model_store is not None else ModelStore()
    )
    result = importer.import_artifact(Path(path).expanduser(), label=label)

    if result.status is ImportStatus.FAILED:
        if as_json:
            # A failed import is a domain outcome with an existing reason, not
            # a crash: exit 1 stays, the reason becomes the envelope error and
            # the store is still untouched.
            return _emit_json_envelope(
                "import",
                1,
                {},
                error=json_output.error(
                    "import_error", result.error or "unknown failure"
                ),
                warnings=result.warnings,
            )
        print("CastleArq - Local artifact import")
        print("==========================")
        print("  Status: FAILED")
        print(f"  Reason: {result.error or 'unknown failure'}")
        print("  Nothing was imported; the model store is unchanged.")
        return 1

    if as_json:
        return _emit_json_envelope(
            "import",
            0,
            _json_import_payload(result),
            warnings=result.warnings,
        )

    reused = result.status is ImportStatus.REUSED
    print("CastleArq - Local artifact import")
    print("==========================")
    print(f"  Status: {result.status.value.upper()}")
    if reused:
        print("  The model store already managed this exact content; the")
        print("  existing copy was kept and no second copy was created.")
    print(f"  Label: {result.sanitized_label}")
    # The content digest is the artifact's *physical* identity. It is shown
    # apart from the logical identity below so the two are never confused.
    print(f"  Content ID: {result.content_id}")
    print(f"  Format: {result.artifact.format if result.artifact else 'Unknown'}")
    print(f"  Architecture: {result.architecture or 'Unknown'}")
    print(f"  Storage: {result.destination}")
    print("  Logical identity: UNKNOWN")
    print("  Integrity declaration: UNKNOWN")
    print("  Memory estimate: UNKNOWN")
    for warning in result.warnings:
        print(f"  Warning: {warning}")
    return 0


def print_source(provider: str | None, repository: str | None) -> int:
    if provider != "huggingface" or not repository:
        print("Usage: python3 -m castlearq.main source huggingface <repository>")
        return 2
    try:
        artifacts = HuggingFaceSource().discover_artifacts(repository)
    except SourceError as error:
        print(f"Source error: {error}")
        return 1
    print(f"CastleArq - Hugging Face metadata: {repository}")
    print("==========================")
    if not artifacts:
        print("No GGUF artifacts found.")
        return 0

    catalog_ids = _catalog_model_ids()
    model_ids = sorted({artifact.model_id for artifact in artifacts})
    for model_id in model_ids:
        status = "in catalog" if model_id in catalog_ids else "not in catalog"
        print(f"\n  Model: {model_id}")
        print(f"    Catalog: {status}")
    if model_ids and model_ids[0] not in catalog_ids:
        print(
            "\n  Warning: the logical model ID above is not in the local catalog;"
            " run/chat will not resolve it until it is added."
        )

    for artifact in artifacts:
        print(f"\n  {artifact.filename}")
        print(f"    Format: {artifact.format}")
        print(f"    Quantization: {artifact.quantization}")
        print(f"    Size: {artifact.size_bytes if artifact.size_bytes is not None else 'Unknown'}")
        print(f"    SHA-256: {artifact.sha256 or 'Unknown'}")
        print(f"    URL: {artifact.download_url}")
        print(f"    Artifact ID: {artifact.artifact_id}")
    return 0


def _json_plan_payload(artifact, plan) -> dict:
    """Project the existing ``plan`` result; the planner is untouched.

    A ``None`` destination, required size or available disk space means the
    offline planner could not determine it -- the human report says
    ``Unknown`` -- so each becomes the ratified UNKNOWN structure. A BLOCKED
    plan is a plan *status*, not an operational error: it stays in the
    payload with a null error, and UNKNOWN is never turned into a failure.
    """
    return {
        "artifact": {
            "model_id": artifact.model_id,
            "source": artifact.source,
            "repository": artifact.repository,
            "filename": artifact.filename,
            "format": artifact.format,
            "quantization": _json_quantization(artifact.quantization),
            "download_url": artifact.download_url,
        },
        "plan": {
            "status": plan.status.value,
            "destination": _json_observed(
                str(plan.destination) if plan.destination is not None else None
            ),
            "required_bytes": _json_observed(plan.required_bytes),
            "available_bytes": _json_observed(plan.available_bytes),
            "existing": plan.existing,
            "reasons": list(plan.reasons),
        },
    }


def print_plan(
    repository: str | None,
    filename: str | None,
    model_store: ModelStore | None = None,
    *,
    as_json: bool = False,
) -> int:
    if not repository or not filename:
        usage = "Usage: python3 -m castlearq.main plan <repository> <filename>"
        if as_json:
            print(usage, file=sys.stderr)
            return _emit_json_envelope(
                "plan", 2, {}, error=json_output.error("usage_error", usage)
            )
        print(usage)
        return 2
    model_id = logical_model_id("huggingface", repository)
    if model_id is None:
        message = (
            f"repository is not mapped to a catalog model: {repository}"
        )
        if as_json:
            # The reason travels in the envelope; stdout stays a single
            # document, so the human line is not printed in this mode.
            return _emit_json_envelope(
                "plan", 1, {}, error=json_output.error("plan_error", message)
            )
        print(f"Plan error: {message}")
        return 1
    try:
        download_url = _download_url(repository, filename)
    except SourceError as error:
        if as_json:
            return _emit_json_envelope(
                "plan", 1, {}, error=json_output.error("plan_error", str(error))
            )
        print(f"Plan error: {error}")
        return 1
    artifact = ArtifactSpec(
        model_id=model_id,
        source="huggingface",
        repository=repository,
        filename=filename,
        format="GGUF",
        quantization=detect_quantization(filename),
        download_url=download_url,
    )
    plan = DownloadPlanner(model_store=model_store).plan(artifact)
    if as_json:
        return _emit_json_envelope(
            "plan",
            0 if plan.status != DownloadPlanStatus.BLOCKED else 1,
            _json_plan_payload(artifact, plan),
        )
    print("CastleArq - Offline download plan")
    print("==========================")
    print(f"  Model: {artifact.model_id}")
    print(f"  Repository: {artifact.repository}")
    print(f"  Filename: {artifact.filename}")
    print(f"  Format: {artifact.format}")
    print(f"  Quantization: {artifact.quantization}")
    print(f"  Status: {plan.status.value.upper()}")
    print(f"  Destination: {plan.destination or 'Unknown'}")
    print(f"  Size: {plan.required_bytes if plan.required_bytes is not None else 'Unknown'}")
    print(
        f"  Available disk: "
        f"{plan.available_bytes if plan.available_bytes is not None else 'Unknown'}"
    )
    print(f"  Existing: {'yes' if plan.existing else 'no'}")
    print(f"  Reasons: {', '.join(plan.reasons) if plan.reasons else 'none'}")
    print("  Network: offline; metadata discovery is not performed")
    return 0 if plan.status != DownloadPlanStatus.BLOCKED else 1


def run_download(
    model_id: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    source_factory=None,
    planner_factory=None,
    downloader_factory=None,
    model_store: ModelStore | None = None,
    out=None,
    err=None,
    service: "ModelAcquisitionService | None" = None,
) -> int:
    """Download exactly one explicit artifact for a logical model ID.

    Since B9.85 this function is a CLI adapter only and holds no business
    orchestration. Discovery, deterministic selection, acquisition mapping,
    identity resolution, planning, transfer and manifest registration are
    performed by :class:`ModelAcquisitionService`, which this command composes
    through :func:`castlearq.application_wiring.compose_acquisition_service`.
    The service composes the B9.80-B9.84 chain: B9.80/B9.81 discovery, then
    B9.84 deterministic selection, then B9.82 acquisition mapping, then
    planning, transfer and B9.40 registration.

    CLI responsibility (unchanged): argument validation, presentation of the
    :class:`AcquisitionOutcome`, and the exit status.

    Selection policy (explicit, no guessing), now enforced by the application
    boundary:
    - the logical ID must resolve to exactly one (source, repository)
      via :mod:`castlearq.model_identity`;
    - deterministic selection selects exactly one discovered artifact, or fails
      with an ambiguity that this command presents to the user;
    - ``DownloadPlanner.plan`` then owns all destination/state/space
      validation and the ``Downloader`` performs the transfer.

    Registration policy (B9.40), now performed by the application boundary: a
    successful transfer is not the end of the
    flow. The orchestrator persists the artifact manifest through
    :meth:`ModelStore.save_manifest` so the artifact becomes discoverable and
    resolvable by the store and the resolver. Persistence happens only after
    ``DownloadResult.success``; the ``Downloader`` itself never persists
    manifests and its transfer contract is unchanged. If the manifest cannot
    be persisted, the download is *not* reported as a complete success: an
    explicit error is printed and the command fails.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not model_id:
        print("Usage: python3 -m castlearq.main download <model-id>", file=err)
        return 2

    acquisition = service if service is not None else _compose_acquisition(
        source_factory=source_factory,
        planner_factory=planner_factory,
        downloader_factory=downloader_factory,
        model_store=model_store,
    )

    try:
        outcome = acquisition.acquire(
            model_id,
            quantization=quantization,
            filename=filename,
        )
    except AcquisitionError as error:
        _present_acquisition_candidates(error, out=out)
        print(f"Download error: {error}", file=err)
        return 1

    return _present_acquisition_outcome(outcome, out=out, err=err)


def _compose_acquisition(
    *,
    source_factory=None,
    planner_factory=None,
    downloader_factory=None,
    model_store: ModelStore | None = None,
) -> ModelAcquisitionService:
    """Build one acquisition service through the application composition root.

    B9.85: the CLI performs no orchestration and constructs no collaborators of
    its own. ``source_factory`` is the legacy test seam; when supplied it yields
    the discovery collaborator, which keeps the existing injection points
    working without reintroducing legacy discovery into this command.
    """
    discovery_provider = None
    if source_factory is not None:
        discovery_provider = _as_discovery_provider(source_factory())

    return compose_acquisition_service(
        discovery_provider=discovery_provider,
        model_store=model_store,
        planner_factory=planner_factory,
        downloader_factory=downloader_factory,
    )


def _as_discovery_provider(candidate):
    """Accept either a B9.81 discovery provider or a legacy source object.

    A genuine B9.81 provider implements the B9.80 port and is used directly.
    A legacy ``ModelSource`` implements only ``discover_artifacts`` and is
    adapted through a thin shim over the B9.80 port, so the existing
    ``source_factory`` test seam keeps working while this command runs the
    B9.80-B9.84 chain. ``ModelSource`` itself is untouched.
    """
    if isinstance(candidate, ModelDiscovery):
        return candidate
    if hasattr(candidate, "discover_artifacts"):
        return _LegacySourceDiscoveryAdapter(candidate)
    return candidate


class _LegacySourceDiscoveryAdapter:
    """Expose a legacy ``ModelSource`` through the B9.80 discovery port.

    This is a compatibility shim for the existing ``source_factory`` test seam
    only. It never retires or deprecates ``ModelSource``: the legacy
    architecture stays operational and untouched.
    """

    def __init__(self, source) -> None:
        self._source = source

    def inspect(self, repository: str):
        """Return B9.80 variants derived from the legacy declared artifacts."""
        from .discovery import (
            DiscoveredArtifact,
            ModelCandidate,
            ModelVariant,
        )

        try:
            artifacts = tuple(self._source.discover_artifacts(repository))
        except SourceError as error:
            # The legacy seam raises SourceError; the B9.80 port speaks
            # DiscoveryError, so the boundary translation happens here.
            raise DiscoveryError(str(error)) from error

        groups: dict[str, list] = {}
        for spec in artifacts:
            declared = DiscoveredArtifact(
                repository=spec.repository,
                filename=spec.filename,
                format=spec.format,
                declared_quantization=spec.quantization,
                model_id=spec.model_id,
                source=spec.source,
                download_url=spec.download_url,
                declared_size=spec.size_bytes,
                declared_sha256=spec.sha256,
                revision=spec.revision,
            )
            groups.setdefault(declared.declared_quantization, []).append(declared)

        provider_id = (
            getattr(artifacts[0], "source", None) if artifacts else "legacy"
        )
        candidate = ModelCandidate(
            provider_id=provider_id or "legacy",
            repository=repository,
            has_gguf=bool(artifacts),
        )
        return tuple(
            ModelVariant(
                candidate=candidate,
                declared_quantization=quantization,
                artifacts=tuple(groups[quantization]),
            )
            for quantization in sorted(groups)
        )

    def search(self, query, *, limit=20, cursor=None):
        """Not supported by the legacy seam; the B9.80 port requires it."""
        raise DiscoveryError(
            "the legacy source seam does not implement discovery search"
        )


def _present_acquisition_candidates(error: AcquisitionError, *, out) -> None:
    """Present discovered candidates for a refused selection.

    Candidate data is produced by the application boundary from the artifacts
    it already discovered; this function only prints. It is populated only
    when no explicit selector was supplied, which is exactly when candidates
    are worth showing.
    """
    if not error.candidates:
        if error.category is AcquisitionErrorCategory.SELECTION_FAILED and (
            not error.candidate_filenames
        ):
            # Discovery returned nothing at all; this is the legacy
            # "No GGUF artifacts found." presentation.
            print("CastleArq - Download candidates for model: " f"{error.model_id}", file=out)
            print("==========================", file=out)
            print("No GGUF artifacts found.", file=out)
        return
    print(f"CastleArq - Download candidates for model: {error.model_id}", file=out)
    print("==========================", file=out)
    for candidate in error.candidates:
        size = (
            candidate.declared_size
            if candidate.declared_size is not None
            else "Unknown"
        )
        print(f"\n  {candidate.filename}", file=out)
        print(f"    Quantization: {candidate.quantization}", file=out)
        print(f"    Size: {size}", file=out)
        print(f"    SHA-256: {candidate.declared_sha256 or 'Unknown'}", file=out)


def _failure_detail(message: str) -> str:
    """Recover the downloader's own error text from the boundary message."""
    _, _, detail = message.partition("): ")
    return detail if detail else message


def _present_acquisition_outcome(outcome: AcquisitionOutcome, *, out, err) -> int:
    """Present an application outcome and return the CLI exit status."""
    if outcome.status is AcquisitionStatus.BLOCKED:
        for reason in outcome.reasons or ("download plan is blocked",):
            print(f"Download error: {reason}", file=err)
        return 1

    if outcome.status is AcquisitionStatus.FAILED:
        # Keep the legacy, more specific download-failure wording the CLI
        # established, derived from the downloader status the boundary kept.
        status = outcome.failure_status
        detail = _failure_detail(outcome.message or "")
        if status == "checksum_mismatch":
            print(f"Download error: SHA-256 verification failed: {detail}", file=err)
        elif status in {"http_error", "network_error"}:
            print(f"Download error: download failed: {detail}", file=err)
        elif status == "filesystem_error":
            print(f"Download error: filesystem error: {detail}", file=err)
        else:
            print(f"Download error: {outcome.message}", file=err)
        return 1

    if outcome.status is AcquisitionStatus.ALREADY_DOWNLOADED:
        print(f"Model: {outcome.model_id}", file=out)
        print(f"Artifact: {outcome.filename}", file=out)
        print("Artifact already downloaded.", file=out)
        return 0
        print(f"Model: {outcome.model_id}", file=out)
        print(f"Artifact: {outcome.filename}", file=out)
        print("Artifact already downloaded.", file=out)
        return 0

    print(f"Model: {outcome.model_id}", file=out)
    print(f"Artifact: {outcome.filename}", file=out)
    if outcome.size_bytes is not None:
        print(f"Size: {outcome.size_bytes}", file=out)
    print("Source: Hugging Face", file=out)
    print("", file=out)
    print("Planning download...", file=out)
    if outcome.destination is not None:
        print(f"Destination: {outcome.destination}", file=out)
    print("Downloading...", file=out)

    print("Download complete.", file=out)
    if outcome.verified:
        print("SHA-256 verified.", file=out)
    print("Artifact state: downloaded", file=out)
    if outcome.manifest_path is not None:
        print(f"Registered manifest: {outcome.manifest_path}", file=out)
    return 0


def _error_message(error: BaseException) -> str:
    """B9.78: preparation and admission failures report through one accessor."""
    return str(getattr(error, "message", None) or error)


def _error_warnings(error: BaseException) -> tuple[str, ...]:
    return tuple(getattr(error, "warnings", ()) or ())


def _prepare_warnings(error: BaseException) -> tuple[str, ...]:
    """B9.78: preparation failures may carry compatibility and selection warnings."""
    return (
        tuple(getattr(error, "compatibility_warnings", ()) or ())
        + tuple(getattr(error, "selection_warnings", ()) or ())
    )


def _admit_for_preparation(
    model_id: str,
    capability: RuntimeCapability,
    *,
    quantization: str | None,
    filename: str | None,
    model_store: ModelStore,
) -> EvaluationAdmission | None:
    """B9.78 — one strict evaluation for the ``run``/``chat`` preparation paths.

    Returns the admission to transport into ``run_service``, or ``None`` when
    the evaluation itself raised. ``None`` is NOT authorization: it is handed
    to a fail-closed gate, so a broken evaluation still refuses execution.

    The capability detected immediately before preparation is injected, so no
    second runtime detection happens (one request -> one evaluation).

    B9.48 P0-2 is preserved: a raised evaluation is reported as an evaluation
    error, never folded into a compatibility denial.
    """
    try:
        result = evaluate_model_compatibility(
            model_id,
            quantization=quantization,
            filename=filename,
            dependencies=EvaluateCompatibilityDependencies(
                model_store=model_store, capability=capability
            ),
        )
    except (ModelArtifactResolutionError, RuntimeError, ValueError, OSError) as error:
        print(
            f"Compatibility evaluation error: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return None
    return to_admission(result)


def run_model(
    model_id: str | None,
    prompt: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    model_store: ModelStore | None = None,
) -> int:
    if not model_id or prompt is None or not prompt.strip():
        print("Usage: python3 -m castlearq.main run <model-id> --prompt <text>", file=sys.stderr)
        return 2
    try:
        model_store = model_store if model_store is not None else ModelStore()
        resolver = ModelArtifactResolver(model_store)
        resolved = resolver.resolve(
            model_id,
            quantization=quantization,
            filename=filename,
        )
    except ModelArtifactResolutionError as error:
        print(f"Run error: {error}", file=sys.stderr)
        return 1

    capability = detect_llama_capability()
    admission = _admit_for_preparation(
        model_id,
        capability,
        quantization=quantization,
        filename=filename,
        model_store=model_store,
    )
    try:
        preparation = _prepare(
            resolved.model, resolved.artifact, capability, model_store,
            admission=admission,
        )
    except (PreparationError, ExecuteAdmissionDeniedError) as error:
        print(f"Run error: {_error_message(error)}", file=sys.stderr)
        for warning in (*_error_warnings(error), *_prepare_warnings(error)):
            print(f"Warning: {warning}", file=sys.stderr)
        return 1

    request = ExecutionRequest(
        resolved.artifact,
        prompt,
        target=preparation.target,
        timeout_seconds=_DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    )
    result = LlamaCppRunner(capability).run(
        preparation.executable_artifact, preparation.target, request
    )
    if result.success:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        all_warnings = tuple(
            dict.fromkeys(
                (
                    *preparation.compatibility_warnings,
                    *preparation.selection_warnings,
                    *result.warnings,
                )
            )
        )
        for warning in all_warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        return 0
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.error:
        print(f"Run error: {result.error.message}", file=sys.stderr)
    return 1


def chat_model(
    model_id: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    input_fn=None,
    out=None,
    err=None,
    session_factory=None,
    model_store: ModelStore | None = None,
) -> int:
    """Interactive multi-turn chat over one persistent runtime process."""
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    input_fn = input_fn if input_fn is not None else input

    if not model_id:
        print("Usage: python3 -m castlearq.main chat <model-id>", file=err)
        return 2

    try:
        model_store = model_store if model_store is not None else ModelStore()
        resolver = ModelArtifactResolver(model_store)
        resolved = resolver.resolve(
            model_id,
            quantization=quantization,
            filename=filename,
        )
    except ModelArtifactResolutionError as error:
        print(f"Chat error: {error}", file=err)
        return 1

    capability = detect_llama_capability()
    if not capability.invocable:
        print(
            "Chat error: no invocable runtime is available",
            file=err,
        )
        return 1

    admission = _admit_for_preparation(
        model_id,
        capability,
        quantization=quantization,
        filename=filename,
        model_store=model_store,
    )
    try:
        preparation = _prepare(
            resolved.model, resolved.artifact, capability, model_store,
            admission=admission,
        )
    except (PreparationError, ExecuteAdmissionDeniedError) as error:
        print(f"Chat error: {_error_message(error)}", file=err)
        for warning in _prepare_warnings(error):
            print(f"Warning: {warning}", file=err)
        return 1

    for warning in preparation.selection_warnings:
        print(f"Warning: {warning}", file=err)

    def stream(chunk: str) -> None:
        out.write(chunk)
        out.flush()

    if session_factory is not None:
        session = session_factory(
            capability, preparation.executable_artifact, preparation.target, chunk_callback=stream
        )
    else:
        session = start_chat_session(
            capability,
            preparation.executable_artifact,
            preparation.target,
            chunk_callback=stream,
        )

    print("CastleArq — chat", file=out)
    print(f"Model: {model_id}", file=out)
    print("Type /exit to quit.", file=out)
    try:
        while True:
            try:
                out.write("you> ")
                out.flush()
                prompt = input_fn()
            except EOFError:
                break
            except KeyboardInterrupt:
                # Ctrl+C while waiting for input: close the session cleanly.
                break
            if not prompt.strip():
                continue
            if prompt.strip() == "/exit":
                break
            try:
                session.send(prompt)
            except KeyboardInterrupt:
                session.cancel()
                if session.state.value != "ready":
                    break
            except ChatSessionError as error:
                print(f"Chat error: {error}", file=err)
                break
            out.write("\n")
            out.flush()
    finally:
        session.close()
    print("Session closed.", file=out)
    return 0


def execute_command(
    model_id: str | None,
    prompt: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    out=None,
    err=None,
    model_store=None,
) -> int:
    """Run one prompt through the Execute Model use case (B9.24).

    Thin Product Caller: usage validation, one composition per invocation,
    one ``execute_model`` call with a fail-closed evaluation admission, and
    projection of
    the Application result to streams and exit code (0 success, 1 failure,
    2 usage). Infrastructure stays behind the Composition Root.

    B9.74: ``model_store`` is the opaque store the CLI resolved for this
    invocation, handed on to the two Application seams that own it (the
    composition and the evaluation dependencies). It is deliberately
    unannotated: the ratified B9.24 boundary check forbids this caller from
    naming infrastructure types, and the caller still coordinates none --
    it only forwards the value it was given. ``None`` means "no CLI selection"
    and leaves both seams on their unchanged environment-resolved default.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not model_id or prompt is None or not prompt.strip():
        print(
            "Usage: python3 -m castlearq.main execute <model-id> <prompt>",
            file=err,
        )
        return 2

    dependencies = compose_execute_model_dependencies(model_store=model_store)
    try:
        evaluation_result = evaluate_model_compatibility(
            model_id,
            quantization=quantization,
            filename=filename,
            dependencies=EvaluateCompatibilityDependencies(model_store=model_store),
        )
    except (
        ModelArtifactResolutionError,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        # B9.48 (P0-2): an evaluation that RAISED is not an evaluation that
        # DENIED. The previous behaviour folded both into
        # ``to_admission(None)``, so a broken GGUF read or a resolution
        # failure surfaced to the user as "deny-by-default applies" -- a
        # policy statement that was never actually made.
        #
        # The distinction is preserved end to end:
        #   * the cause is reported as an EVALUATION ERROR, not a denial;
        #   * execution is still fail-closed (no admission is minted, so the
        #     Execute gate cannot admit), preserving deny-by-default for the
        #     cases that really are decisions.
        print(
            f"Compatibility evaluation error: {type(error).__name__}: {error}",
            file=err,
        )
        evaluation_result = None
        admission = to_admission(None)
    else:
        admission = to_admission(evaluation_result)

    try:
        result = execute_model(
            model_id=model_id,
            prompt=prompt,
            quantization=quantization,
            filename=filename,
            admission=admission,
            dependencies=dependencies,
        )
    except (ExecutePreparationError, ExecuteAdmissionDeniedError) as error:
        print(f"Execute error: {error.message}", file=err)
        # B9.48 (P0-1): when the admission gate is what refused execution,
        # show the evaluation that produced it. The gate's own message says
        # only that deny-by-default applies; the checks, reasons and evidence
        # already computed by the evaluation are printed here so the user can
        # see WHICH check blocked and why. Nothing is inferred or invented.
        if evaluation_result is not None:
            print(format_evaluation_report(evaluation_result), file=err)
        for warning in error.warnings:
            print(f"Warning: {warning}", file=err)
        return 1

    if result.success:
        print(
            result.stdout,
            end="" if result.stdout.endswith("\n") else "\n",
            file=out,
        )
        for warning in result.warnings:
            print(f"Warning: {warning}", file=err)
        return 0
    if result.stderr:
        print(
            result.stderr,
            file=err,
            end="" if result.stderr.endswith("\n") else "\n",
        )
    if result.error is not None:
        print(f"Execute error: {result.error.message}", file=err)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=err)
    return 1


def _compatibility_evaluation_payload(result) -> dict:
    """Project one strict evaluation into the ``compatibility --json`` payload.

    Mirrors ``evaluate_model_compatibility()`` without adding anything: the
    application status, the strict verdict, the checks with their evidence
    and the model/artifact identity already on the result. The admission
    projection is deliberately NOT computed here -- the command adds it as a
    separate sibling payload key, so a strict INSUFFICIENT_EVIDENCE and a
    permitting admission remain observable at the same time. Enums pass
    through the shared serializer (``.value``, never their uppercase name).
    """

    def items(value) -> tuple:
        # Same defensive rule as castlearq.compatibility_report: only real
        # collections are projected, a stand-in degrades to "nothing to show".
        return tuple(value) if isinstance(value, (tuple, list)) else ()

    evaluation = result.evaluation
    strict = evaluation.result if evaluation is not None else None
    return {
        "status": result.status,
        "verdict": strict.status if strict is not None else None,
        "model_id": result.model_id,
        "runtime": result.runtime,
        "imported": result.imported,
        "blocking_outcome": result.blocking_outcome,
        "artifact": _json_artifact(result.artifact),
        "checks": items(getattr(strict, "checks", ())) if strict else (),
        "conditions": items(getattr(strict, "conditions", ())) if strict else (),
        "warnings": items(getattr(strict, "warnings", ())) if strict else (),
        "notes": items(getattr(strict, "notes", ())) if strict else (),
    }


def compatibility_command(
    model_id: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    out=None,
    err=None,
    model_store: ModelStore | None = None,
    as_json: bool = False,
) -> int:
    """Report the existing strict compatibility evaluation (B9.48).

    Read-only Product Caller for
    :func:`~castlearq.evaluate_compatibility.evaluate_model_compatibility`.
    It asks the question ``execute`` would answer implicitly, and it answers
    it WITHOUT running inference.

    Guarantees, in line with B9.48 section 7:

    * it runs no inference and launches no runtime process;
    * it performs no download and creates no artifact;
    * it does not modify the ModelStore -- it only reads it, through the same
      use case ``execute`` uses;
    * it creates no persistent state and writes no session or manifest;
    * it does not alter evaluation policy: it reuses ``to_admission`` for the
      exit code only, exactly as ``execute`` does.

    Exit codes follow the existing CLI convention: ``0`` when the evaluation
    admits execution, ``1`` when it does not, ``2`` on usage error.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not model_id or not model_id.strip():
        print(
            "Usage: python3 -m castlearq.main compatibility <model-id>",
            file=err,
        )
        if as_json:
            return _emit_json_envelope(
                "compatibility",
                2,
                {},
                error=json_output.error(
                    "usage_error",
                    "Usage: python3 -m castlearq.main compatibility <model-id>",
                ),
                out=out,
            )
        return 2

    try:
        result = evaluate_model_compatibility(
            model_id,
            quantization=quantization,
            filename=filename,
            dependencies=EvaluateCompatibilityDependencies(model_store=model_store),
        )
    except (
        ModelArtifactResolutionError,
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        # Same P0-2 distinction as `execute`: a raised error is reported as an
        # evaluation error, never as a compatibility verdict.
        message = f"{type(error).__name__}: {error}"
        print(f"Compatibility evaluation error: {message}", file=err)
        if as_json:
            # A raised evaluation is the operational failure it always was;
            # the envelope structures it, the exit code stays exactly 1.
            return _emit_json_envelope(
                "compatibility",
                1,
                {},
                error=json_output.error("evaluation_error", message),
                out=out,
            )
        return 1

    # Reuse the existing fail-closed projection for the exit code. This does
    # not change policy; it only reports what `execute` would decide.
    admission = to_admission(result)
    exit_code = 0 if admission.status == "evaluated" and admission.verdict in (
        "compatible",
        "compatible_with_conditions",
    ) else 1
    if as_json:
        # A denial is a payload, never an `error`: only the operational
        # failure above gets the envelope's error object.
        payload = {
            "evaluation": _compatibility_evaluation_payload(result),
            "admission": {
                "status": admission.status,
                "verdict": admission.verdict,
            },
        }
        return _emit_json_envelope("compatibility", exit_code, payload, out=out)
    print(format_evaluation_report(result), file=out)
    return exit_code


# P1.3: the P1.2 contract is already implemented inside
# `ArtifactExecutionPreflight.validate()` and `ModelStore.inspect_manifest()`.
# This command only *names* the evidence those two already produced. It
# re-implements no check of its own: no symlink logic, no path validation, no
# `.part` handling, no hashing and no size comparison.
#
#   SHA-256 declared + matches -> integrity PASSED
#   SHA-256 declared + differs -> integrity FAILED  (CHECKSUM_MISMATCH)
#   SHA-256 absent            -> integrity UNKNOWN  (NOT a failure, exit 0)
#   size_bytes absent         -> size UNKNOWN       (NOT a failure, exit 0)
#
# `UNKNOWN` is `CheckStatus.UNKNOWN` -- "insufficient evidence to decide" --
# the same vocabulary and the same rule the compatibility surface already uses
# ("UNKNOWN is never silently converted into a failure", README).
_PREFLIGHT_DIMENSION = {
    PreflightErrorCode.MISSING_ARTIFACT: "safety",
    PreflightErrorCode.PARTIAL_ARTIFACT: "safety",
    PreflightErrorCode.INCONSISTENT_ARTIFACT: "safety",
    PreflightErrorCode.UNSAFE_ARTIFACT: "safety",
    PreflightErrorCode.INVALID_ARTIFACT: "safety",
    PreflightErrorCode.SIZE_MISMATCH: "size",
    PreflightErrorCode.CHECKSUM_MISMATCH: "integrity",
}


def validate_command(
    model_id: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
    out=None,
    err=None,
    resolver: ModelArtifactResolver | None = None,
    preflight: ArtifactExecutionPreflight | None = None,
    store: ModelStore | None = None,
    as_json: bool = False,
) -> int:
    """Report what can be proven about one stored artifact (P1.3).

    Read-only Product Caller over the existing resolver and the existing
    execution preflight. It answers "what can I prove right now, and what
    evidence do I not have" without changing execution policy, artifact state
    or admission, and without writing anything.

    Exit codes follow the existing CLI convention: ``0`` when the validation
    operation succeeded, ``1`` when a check or the resolution actually failed,
    ``2`` on usage error.

    A missing SHA-256 is reported as ``UNKNOWN`` and exits ``0``: absence of
    evidence is not a failure, and this command makes no checksum policy.

    B9.74: ``store`` is the store the CLI resolved for this invocation. When it
    is given, the resolver is built on it, so resolution and the preflight
    cannot end up reading two different stores.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not model_id or not model_id.strip():
        print("Usage: python3 -m castlearq.main validate <model-id>", file=err)
        if as_json:
            return _emit_json_envelope(
                "validate",
                2,
                {},
                error=json_output.error(
                    "usage_error",
                    "Usage: python3 -m castlearq.main validate <model-id>",
                ),
                out=out,
            )
        return 2

    resolver = resolver or ModelArtifactResolver(store)
    store = store if store is not None else resolver.model_store
    preflight = preflight or ArtifactExecutionPreflight(store)

    try:
        resolved = resolver.resolve(
            model_id, quantization=quantization, filename=filename
        )
    except (ModelArtifactResolutionError, ValueError) as error:
        print(f"Validation error: {error}", file=err)
        if as_json:
            return _emit_json_envelope(
                "validate",
                1,
                {},
                error=json_output.error("validation_error", str(error)),
                out=out,
            )
        return 1

    artifact = resolved.artifact

    # `ArtifactState` is context only, never the validation verdict. It is
    # derived fresh and is not persisted, per B9.41.
    try:
        state = store.inspect_manifest(
            store._artifact_directory(artifact) / "manifest.json"
        ).state
    except (OSError, ValueError, KeyError, TypeError, UnsafePathError):
        state = None

    safety = size = integrity = CheckStatus.UNKNOWN

    try:
        executable = preflight.validate(artifact)
    except ArtifactPreflightError as error:
        safety = CheckStatus.PASSED
        failed = _PREFLIGHT_DIMENSION.get(error.code, "safety")
        if failed == "size":
            size = CheckStatus.FAILED
        elif failed == "integrity":
            integrity = CheckStatus.FAILED
        else:
            safety = CheckStatus.FAILED
        if as_json:
            # A failed check is the validation result, not an operational
            # error: it stays in the payload with the existing problem text.
            return _emit_json_envelope(
                "validate",
                1,
                _json_validation_payload(
                    artifact=artifact,
                    safety=safety,
                    size=size,
                    integrity=integrity,
                    state=state,
                    problem=f"{error.code.value}: {error.message}",
                ),
                out=out,
            )
        print(
            format_validation_report(
                model_id=artifact.model_id,
                filename=artifact.filename,
                safety=safety,
                size=size,
                integrity=integrity,
                state=state,
                failure=f"{error.code.value}: {error.message}",
            ),
            file=out,
        )
        return 1
    except UnsafePathError as error:
        # The inspector raises this for an unsafe path before the codes above
        # apply. It is a filesystem-safety refusal, not a checksum decision.
        if as_json:
            return _emit_json_envelope(
                "validate",
                1,
                _json_validation_payload(
                    artifact=artifact,
                    safety=CheckStatus.FAILED,
                    size=size,
                    integrity=integrity,
                    state=state,
                    problem=str(error),
                ),
                out=out,
            )
        print(
            format_validation_report(
                model_id=artifact.model_id,
                filename=artifact.filename,
                safety=CheckStatus.FAILED,
                size=size,
                integrity=integrity,
                state=state,
                failure=str(error),
            ),
            file=out,
        )
        return 1

    # Preflight returned an ExecutableArtifact. Both flags are `bool`, so a
    # `False` is disambiguated with the declaration itself: `size_verified` /
    # `checksum_verified` are False both when nothing was declared and when a
    # check did not run. A declared-and-wrong value never reaches here -- it
    # raised above.
    safety = CheckStatus.PASSED
    size = CheckStatus.PASSED if executable.size_verified else CheckStatus.UNKNOWN
    integrity = (
        CheckStatus.PASSED if executable.checksum_verified else CheckStatus.UNKNOWN
    )

    if as_json:
        # `UNKNOWN` is not a failure: exit 0, and the payload carries the
        # architecture-backed reasons instead of an "Unknown" datum.
        return _emit_json_envelope(
            "validate",
            0,
            _json_validation_payload(
                artifact=artifact,
                safety=safety,
                size=size,
                integrity=integrity,
                state=state,
            ),
            out=out,
        )
    print(
        format_validation_report(
            model_id=artifact.model_id,
            filename=artifact.filename,
            safety=safety,
            size=size,
            integrity=integrity,
            state=state,
        ),
        file=out,
    )
    # `UNKNOWN` is not a failure: the operation succeeded and the artifact is
    # exactly as usable as it was before this command ran.
    return 0


USAGE_FLOW = """\
usage flow:
  1. discover models:      castlearq models
  2. download a model:     castlearq download <model-id>
  3. import a local GGUF:  castlearq import <path>
  4. list local artifacts: castlearq list
  5. check compatibility:  castlearq compatibility <model-id>
  6. run a single prompt:  castlearq execute <model-id> "<prompt>"
  7. start a chat session: castlearq chat <model-id>
  8. diagnose GPU software: castlearq diagnose
  9. inspect llama runtime:  castlearq runtime
  10. re-check remediation:  castlearq verify

artifacts:
  artifacts come either from the catalog (models, download) or from a GGUF
  file you already have (import). Importing one is a single step: it copies
  the file into the model store and reports the label to use afterwards.
  `models` lists catalog and recommended models; `list` lists the managed
  artifacts available for use, including imported ones. A label is the
  operational identifier for later commands, not a claim about the model's
  logical identity, which may remain UNKNOWN.

execution:
  execute is the recommended command. It evaluates strict compatibility
  first and refuses to run when admission denies, printing the checks,
  reasons and evidence behind the refusal.
  run <model-id> --prompt "<text>" is the legacy interface. It reaches the
  same llama.cpp runtime through the legacy preparation pipeline and does
  NOT apply the strict evaluation admission. Prefer execute.

read-only inspection:
  detect  system, CPU, memory and GPU
  runtime resolved llama.cpp runtime state
  models  scored model recommendations
  list    locally stored artifacts and their derived state
  validate <model-id>
          validate one stored artifact: reports safety, declared size and
          cryptographic integrity separately. Read-only; an absent SHA-256 is
          reported as UNKNOWN, never as a failure
  compatibility <model-id>
          strict compatibility evaluation, without running inference
  source huggingface <repository>   inspect a remote source
  plan <repository> <filename>      inspect one remote artifact
  diagnose / verify
          GPU software diagnosis and its read-only re-verification
          (these concern the ENVIRONMENT, not artifact integrity)

model store:
  store   report the store in use: path, source (cli, config, xdg, default or
          legacy-compatibility), existence and legacy status. Read-only

  selection order, highest first:
    --model-store PATH  ->  config.toml [models] directory  ->  XDG_DATA_HOME
    ->  ~/.local/share/castlearq/models  ->  legacy compatibility fallback
  An explicit selection wins even when its directory does not exist yet, and
  --model-store PATH selects it for one invocation only. Nothing is ever
  moved, copied or deleted: CastleArq does not migrate models.

serving (EXECUTES MODELS - not a status-only surface):
  serve   HTTP API on 127.0.0.1. POST /v1/run runs real inference and
          POST /v1/chat/sessions opens a live chat session. Both apply the
          same strict evaluation admission as execute: a denied model answers
          403, and an evaluation that errors answers 500. See the README.

model-id notes:
  models prints a friendly name (e.g. "Qwen2.5-Coder 7B Instruct") together
  with the canonical model id (e.g. "qwen2.5-coder-7b-instruct"). Always pass
  the model id, never the friendly name, to download, execute, chat,
  compatibility and run.

exit codes:
  0  success / compatible      1  failure / not compatible      2  usage error

examples:
  castlearq models
  castlearq download qwen2.5-coder-7b-instruct
  castlearq compatibility qwen2.5-coder-7b-instruct
  castlearq validate qwen2.5-coder-7b-instruct
  castlearq execute qwen2.5-coder-7b-instruct "Reply with exactly OK"
  castlearq run qwen2.5-coder-7b-instruct --prompt "Hello"
  castlearq diagnose
  python3 -m castlearq.main --help  # development from checkout


"""
def _json_runtime_payload(resolved) -> dict:
    """Project the already-resolved llama.cpp runtime state.

    ``RuntimeCapability`` keeps its own model, and this payload never borrows
    the hardware vocabulary of ``detect --json`` nor a compatibility
    vocabulary. Properties that exist in the runtime model but were not
    observed (an absent version, an unprobed capability) use the UNKNOWN
    structure; ``availability`` travels as its enum ``.value``.
    """
    identity = resolved.identity
    capability = resolved.capability
    payload = {
        "runtime": {
            "canonical_id": identity.canonical_id,
            "executable_name": _json_observed(identity.executable_name),
            "executable_path": _json_observed(identity.executable_path),
            "version": _json_observed(identity.version),
            "build_identifier": _json_observed(identity.build_identifier),
            "availability": identity.availability.value,
            "reason": identity.reason,
        },
        "capability": (
            _json_observed(None)
            if capability is None
            else {
                "name": capability.name,
                "executable_path": _json_observed(capability.executable_path),
                "version": _json_observed(capability.version),
                "available": capability.available,
                "reason": capability.reason,
                "supports_one_shot": capability.supports_one_shot,
                "supported_formats": list(capability.supported_formats),
                "supported_backends": list(capability.supported_backends),
                "prompt_input_modes": [
                    mode.value for mode in capability.prompt_input_modes
                ],
                "compatibility_names": list(capability.compatibility_names),
            }
        ),
    }
    return payload


def print_runtime_diagnostics(out=None, *, as_json: bool = False) -> int:
    """Present the resolved official llama.cpp runtime state."""
    out = out if out is not None else sys.stdout
    resolved = resolve_llama_runtime()
    identity = resolved.identity
    if as_json:
        return _emit_json_envelope(
            "runtime",
            0 if identity.availability is RuntimeAvailability.AVAILABLE else 1,
            _json_runtime_payload(resolved),
            out=out,
        )
    print("Runtime: llama.cpp", file=out)
    print("Launcher: llama", file=out)
    if identity.executable_path is not None:
        print(f"Executable: {identity.executable_path}", file=out)
    if identity.version is not None:
        print(f"Version: {identity.version}", file=out)
    if identity.build_identifier is not None:
        print(f"Build: {identity.build_identifier}", file=out)
    print(f"Availability: {identity.availability.name}", file=out)
    if identity.reason:
        print(f"Reason: {identity.reason}", file=out)
    if resolved.capability is not None:
        print("Capabilities:", file=out)
        for capability in resolved.capability.supported_formats:
            print(f"  {capability}", file=out)
        for backend in resolved.capability.supported_backends:
            print(f"  {backend}", file=out)
    return 0 if identity.availability is RuntimeAvailability.AVAILABLE else 1


def serve_command(
    host: str | None = None,
    port: int | None = None,
    model_store: ModelStore | None = None,
) -> int:
    """Start the HTTP API server (loopback-only).

    B9.50: this is NOT a read-only surface. It executes models --
    ``POST /v1/run`` performs real inference and the ``/v1/chat`` routes
    open live sessions. The previous docstring and README/help text called
    it a "read-only HTTP API", which was factually wrong.

    Execution policy: the RATIFIED architectural policy (B9.51, which closes
    B9.23 section 13 K-3) is that HTTP execution shares the strict
    compatibility admission that ``execute`` applies -- admission is a
    property of execution, not of a command name or a transport. IMPLEMENTED in
    B9.52: ``POST /v1/run`` now evaluates, projects the admission through
    ``to_admission`` and executes through ``execute_model``, the same use case
    the CLI uses. The ratified contract (403 for a denial, 500 for an
    evaluation ERROR which is not a denial, 404 for an unknown model, 422
    preparation, 503 runtime, and a rejection body exposing only
    ``status``/``verdict``) lives in
    ``docs/B9.51-http-admission-contract-decision.md``.

    ``POST /v1/chat/sessions`` starts a model too, so it obeys the same gate
    and takes the same global ``run_lock``.

    Loopback binding is a NETWORK property and is not what makes the policy
    acceptable; the two are documented separately. ``run`` is unaffected:
    B9.52 performs no ``run`` -> ``execute`` cutover, so ``run`` keeps its
    historical legacy policy.

    B9.74: ``model_store`` is the store this invocation selected; the server
    uses it for listing, resolution and evaluation. HTTP execution keeps its
    own ratified composition (B9.52), which B9.74 does not touch.
    """
    return serve(
        host=host or "127.0.0.1",
        port=8000 if port is None else port,
        model_store=model_store,
    )


def store_command(
    *,
    model_store_path: str | None = None,
    out=None,
    as_json: bool = False,
) -> int:
    """Report which model store CastleArq uses for this invocation (B9.74).

    Read-only, and honest about it: the store is *resolved* (the same single
    resolution function every other command uses) and then *observed*. Nothing
    is created, moved, copied or deleted -- the report says ``Exists: no`` for
    a selected store that does not exist yet, and leaving it that way is the
    correct outcome, because the directory is created only when a write
    operation actually needs it.
    """
    out = out if out is not None else sys.stdout
    resolution = resolve_model_store(model_store_path)
    if as_json:
        # The five ratified B9.74 sources, reported exactly as resolution
        # named them; the resolution policy itself is untouched.
        payload = {
            "path": str(resolution.path),
            "source": resolution.source,
            "exists": resolution.path.exists(),
            "legacy_detected": resolution.legacy_detected,
            "legacy_used": resolution.legacy_used,
        }
        return _emit_json_envelope("store", 0, payload, out=out)
    print("Store", file=out)
    print(f"Path: {resolution.path}", file=out)
    print(f"Source: {resolution.source}", file=out)
    print(f"Exists: {'yes' if resolution.path.exists() else 'no'}", file=out)
    print(f"Legacy detected: {'yes' if resolution.legacy_detected else 'no'}", file=out)
    print(f"Legacy used: {'yes' if resolution.legacy_used else 'no'}", file=out)
    return 0


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Help formatter that never breaks hyphenated terms mid-word.

    ``textwrap``'s default ``break_on_hyphens=True`` can wrap tokens such as
    ``model-id`` as ``model-`` / ``id`` depending on terminal width, which
    corrupts the documented CLI contract (``model-id for download/run/chat``).
    Wrapping only at spaces keeps those terms intact at any width.
    """

    def _split_lines(self, text: str, width: int) -> list[str]:
        import textwrap

        text = self._whitespace_matcher.sub(" ", text).strip()
        wrapper = textwrap.TextWrapper(
            width=width,
            break_on_hyphens=False,
            break_long_words=False,
        )
        return wrapper.wrap(text)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="castlearq",
        description=(
            "CastleArq: local GGUF model management, compatibility evaluation "
            "and admitted execution with llama.cpp"
        ),
        epilog=USAGE_FLOW,
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"castlearq {get_version()}",
        help="show the installed CastleArq version and exit",
    )
    parser.add_argument("command", nargs="?", choices=("detect", "diagnose", "verify", "models", "list", "runtime", "source", "plan", "compatibility", "validate", "download", "import", "run", "execute", "chat", "serve", "store"), help="command to execute")
    parser.add_argument(
        "provider",
        nargs="?",
        help=(
            "command-specific value: model-id for download/run/chat/execute/"
            "compatibility/validate; source provider for source; "
            "repository for plan"
        ),
    )
    parser.add_argument(
        "repository",
        nargs="?",
        help=(
            "command-specific value: repository for source; "
            "artifact filename for plan; prompt for execute"
        ),
    )
    parser.add_argument("--prompt", help="prompt text for run")
    parser.add_argument(
        "--host",
        help="bind address for serve (loopback only; default 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="TCP port for serve (default 8000)",
    )
    parser.add_argument(
        "--quantization",
        help="quantization level to select for download, execute, compatibility, run or chat",
    )
    parser.add_argument(
        "--filename",
        help="exact artifact filename to select for download, execute, compatibility, run or chat",
    )
    parser.add_argument(
        "--label",
        help=(
            "presentation/storage label for import; sanitized by the model "
            "store and never used as a logical model identity"
        ),
    )
    parser.add_argument(
        "--model-store",
        metavar="PATH",
        help=(
            "model store to use for this invocation only; overrides config.toml "
            "[models] directory and XDG_DATA_HOME. Never created or modified by "
            "resolution alone"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "print exactly one castlearq.cli JSON document on stdout "
            "instead of human output (available for compatibility, "
            "validate, list and store, for import, and for the SHOULD "
            "commands models, runtime, detect and plan)"
        ),
    )
    args = parser.parse_args()
    if args.command is None:
        parser.error("a command is required")
    supported_flags = {
        "detect": (),
        "diagnose": (),
        "verify": (),
        "models": (),
        "list": (),
        "runtime": (),
        "source": (),
        "plan": (),
        "compatibility": ("quantization", "filename"),
        "validate": ("quantization", "filename"),
        "download": ("quantization", "filename"),
        "import": ("label",),
        "run": ("prompt", "quantization", "filename"),
        "execute": ("quantization", "filename"),
        "chat": ("quantization", "filename"),
        "serve": (),
        "store": (),
    }
    # B9.74: the commands that consume a model store. They are exactly the ones
    # that accept --model-store, and exactly the ones where the legacy
    # compatibility notice can be meaningful.
    store_commands = (
        "list",
        "plan",
        "download",
        "import",
        "validate",
        "run",
        "execute",
        "compatibility",
        "chat",
        "serve",
        "store",
    )
    for flag in ("prompt", "quantization", "filename", "label"):
        if getattr(args, flag) is not None and flag not in supported_flags[args.command]:
            parser.error(f"--{flag} is not valid for command '{args.command}'")
    for flag in ("host", "port"):
        if getattr(args, flag) is not None and args.command != "serve":
            parser.error(f"--{flag} is not valid for command '{args.command}'")
    # B9.76.3: --json exists only for the four MUST commands of the first
    # JSON surface. Everything else keeps argparse's behaviour: stderr + exit
    # 2, never JSON.
    if args.json and args.command not in _JSON_COMMANDS:
        parser.error(f"--json is not valid for command '{args.command}'")
    # Forwarded only when set, so the human-mode dispatch calls keep exactly
    # the signature they had before the JSON surface existed.
    json_kwargs = {"as_json": True} if args.json else {}
    if args.model_store is not None:
        if not args.model_store.strip():
            parser.error("--model-store requires a non-empty path")
        if args.command not in store_commands:
            parser.error(
                f"--model-store is not valid for command '{args.command}'"
            )
    if args.command == "diagnose" and (
        args.provider is not None or args.repository is not None
    ):
        parser.error("diagnose takes no arguments")
    if args.command == "verify" and (
        args.provider is not None or args.repository is not None
    ):
        parser.error("verify takes no arguments")

    # B9.74: select the store ONCE per invocation, through the single
    # resolution function, and hand the result to the command. The legacy
    # compatibility fallback is announced on stderr only when it is the store
    # actually selected, and nothing remembers that the notice was shown.
    #
    # `--model-store` is the one selection the CLI alone knows, so it is the
    # one value the CLI forwards as a store. Every other source (config,
    # XDG_DATA_HOME, default, legacy) is resolved by the command itself through
    # that same function when no store is forwarded, so both paths name exactly
    # the same root and no command can ever resolve a second, divergent store.
    model_store: ModelStore | None = None
    if args.command in store_commands:
        resolution = resolve_model_store(args.model_store)
        notice = legacy_store_notice(resolution)
        if notice is not None:
            print(notice, file=sys.stderr)
        if args.model_store is not None:
            model_store = ModelStore(resolution.path)

    if args.command == "detect":
        print_detection(as_json=args.json)
    elif args.command == "diagnose":
        return print_gpu_diagnosis()
    elif args.command == "verify":
        return print_remediation_verification()
    elif args.command == "models":
        print_models(as_json=args.json)
    elif args.command == "list":
        if args.json:
            return list_command(model_store, out=sys.stdout)
        print_local_models(model_store)
    elif args.command == "runtime":
        return print_runtime_diagnostics(as_json=args.json)
    elif args.command == "source":
        return print_source(args.provider, args.repository)
    elif args.command == "plan":
        return print_plan(
            args.provider,
            args.repository,
            model_store=model_store,
            **json_kwargs,
        )
    elif args.command == "store":
        return store_command(
            model_store_path=args.model_store,
            out=sys.stdout,
            **json_kwargs,
        )
    elif args.command == "compatibility":
        if args.repository is not None:
            parser.error("compatibility accepts exactly one model-id")
        return compatibility_command(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
            model_store=model_store,
            **json_kwargs,
        )
    elif args.command == "validate":
        if args.repository is not None:
            parser.error("validate accepts exactly one model-id")
        return validate_command(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
            store=model_store,
            **json_kwargs,
        )
    elif args.command == "download":
        if args.repository is not None:
            parser.error("download accepts exactly one model-id")
        return run_download(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
            model_store=model_store,
        )
    elif args.command == "import":
        if args.repository is not None:
            parser.error("import accepts exactly one path")
        return import_command(
            args.provider,
            label=args.label,
            model_store=model_store,
            **json_kwargs,
        )
    elif args.command == "run":
        if args.repository is not None:
            parser.error("run accepts exactly one model-id")
        return run_model(
            args.provider,
            args.prompt,
            quantization=args.quantization,
            filename=args.filename,
            model_store=model_store,
        )
    elif args.command == "execute":
        return execute_command(
            args.provider,
            args.repository,
            quantization=args.quantization,
            filename=args.filename,
            model_store=model_store,
        )
    elif args.command == "chat":
        if args.repository is not None:
            parser.error("chat accepts exactly one model-id")
        return chat_model(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
            model_store=model_store,
        )
    elif args.command == "serve":
        return serve_command(
            host=args.host, port=args.port, model_store=model_store
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
