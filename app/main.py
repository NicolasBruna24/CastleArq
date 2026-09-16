
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
from .execution import ArtifactExecutionPreflight, ArtifactPreflightError, ExecutionRequest, ExecutableArtifact
from . import gpu_diagnosis
from .gpu_diagnosis import (
    DiagnosisResult,
    DiagnosisStatus,
    GpuComponent,
    Recommendation,
)
from .gpu_setup import GpuSoftwareStatus, diagnose_gpu_software
from .remediation import (
    COMPONENT_LABELS,
    RemediationPlan,
    build_remediation_plan,
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
from .model_store import ModelStore, StoredArtifact, UnsafePathError
from .downloads import (
    DownloadPlan,
    DownloadPlanStatus,
    DownloadPlanner,
    DownloadResult,
    DownloadResultStatus,
    Downloader,
)
from .models import ArtifactSpec, ModelSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runtimes import (
    RuntimeCapability,
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
    detect_runtimes,
    recommend,
)
from .runner import LlamaCppRunner
from .selection import RuntimeBackendSelector, RuntimeSelection, RuntimeSelectionError
from .sources import HuggingFaceSource, SourceError
from .sources.huggingface import _download_url, detect_quantization
from .chat import ChatSessionError, start_chat_session
from .artifact_selection import ArtifactSelectionError, select_artifact


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


def print_detection() -> None:
    hardware = detect_hardware()
    runtimes = detect_runtimes()
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)
    runtime, backend = recommend(runtimes, backends)

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


def print_gpu_diagnosis() -> int:
    """Observe the environment and print the GPU software diagnosis.

    Reuses the existing detection pipeline (``hardware`` + ``gpu_setup``) and
    the pure B2/B3 modules. Read-only: it never installs, downloads or
    modifies the system, and never executes a recipe.
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


def print_models() -> None:
    hardware = detect_hardware()
    runtimes = detect_runtimes()
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)
    results = recommend_models(
        hardware, runtimes, backends, get_catalog(), config=load_config()
    )
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


def print_local_models(model_store: ModelStore | None = None) -> None:
    print("CastleArq - Local models")
    print("==========================")
    store = model_store or ModelStore()
    entries = store.list_artifacts()
    if not entries:
        print("No local model artifacts found.")
        return

    # Group valid artifacts by logical model_id
    grouped: dict[str, list[StoredArtifact]] = {}
    invalid_entries: list[StoredArtifact] = []

    for entry in entries:
        if entry.artifact is None:
            invalid_entries.append(entry)
            continue
        grouped.setdefault(entry.artifact.model_id, []).append(entry)

    for model_id in sorted(grouped.keys()):
        print(f"\n{model_id}")
        # Sort artifacts deterministically by filename
        artifacts = sorted(grouped[model_id], key=lambda e: e.artifact.filename)  # type: ignore[union-attr]
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
        for entry in sorted(invalid_entries, key=lambda e: str(e.manifest_path)):
            print(f"  - {entry.manifest_path} ({entry.message or 'invalid manifest'})")


def print_source(provider: str | None, repository: str | None) -> int:
    if provider != "huggingface" or not repository:
        print("Usage: python3 -m app.main source huggingface <repository>")
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


def print_plan(repository: str | None, filename: str | None) -> int:
    if not repository or not filename:
        print("Usage: python3 -m app.main plan <repository> <filename>")
        return 2
    model_id = logical_model_id("huggingface", repository)
    if model_id is None:
        print(f"Plan error: repository is not mapped to a catalog model: {repository}")
        return 1
    try:
        download_url = _download_url(repository, filename)
    except SourceError as error:
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
    plan = DownloadPlanner().plan(artifact)
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
    out=None,
    err=None,
) -> int:
    """Download exactly one explicit artifact for a logical model ID.

    Selection policy (explicit, no guessing):
    - the logical ID must resolve to exactly one (source, repository)
      via :mod:`app.model_identity`;
    - ``HuggingFaceSource.discover_artifacts`` returns available GGUF artifacts;
    - ``select_artifact`` selects exactly one artifact deterministically if
      no ambiguity exists or matching the given selectors;
    - ``DownloadPlanner.plan`` then owns all destination/state/space
      validation and the ``Downloader`` performs the transfer.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if not model_id:
        print("Usage: python3 -m app.main download <model-id>", file=err)
        return 2

    locator = downloadable_locator(model_id)
    if locator is None:
        locators = source_repositories_for_logical_model(model_id)
        if len(locators) == 1:
            print(f"Download error: unsupported source: {locators[0][0]}", file=err)
        else:
            print(
                f"Download error: no unique source repository is mapped to model: {model_id}",
                file=err,
            )
        return 1
    _, repository = locator

    source = (source_factory or HuggingFaceSource)()
    try:
        artifacts = source.discover_artifacts(repository)
    except SourceError as error:
        print(f"Download error: {error}", file=err)
        return 1

    try:
        artifact = select_artifact(
            artifacts, quantization=quantization, filename=filename
        )
    except ArtifactSelectionError as error:
        if not quantization and not filename:
            print(f"CastleArq - Download candidates for model: {model_id}", file=out)
            print("==========================", file=out)
            if not artifacts:
                print("No GGUF artifacts found.", file=out)
            for item in artifacts:
                size = item.size_bytes if item.size_bytes is not None else "Unknown"
                print(f"\n  {item.filename}", file=out)
                print(f"    Quantization: {item.quantization}", file=out)
                print(f"    Size: {size}", file=out)
                print(f"    SHA-256: {item.sha256 or 'Unknown'}", file=out)
            print(f"\nDownload error: {error}", file=err)
        else:
            print(f"Download error: {error}", file=err)
        return 1
    if artifact.model_id != model_id:
        print(
            f"Download error: discovered artifact model_id "
            f"{artifact.model_id!r} does not match {model_id!r}",
            file=err,
        )
        return 1

    planner = (planner_factory or DownloadPlanner)()
    try:
        plan = planner.plan(artifact)
    except (UnsafePathError, ValueError, TypeError) as error:
        print(f"Download error: {error}", file=err)
        return 1
    except SourceError as error:
        print(f"Download error: {error}", file=err)
        return 1

    print(f"Model: {artifact.model_id}", file=out)
    print(f"Artifact: {artifact.filename}", file=out)
    print(
        f"Size: {artifact.size_bytes if artifact.size_bytes is not None else 'Unknown'}",
        file=out,
    )
    print(f"Source: Hugging Face", file=out)
    print("", file=out)
    print("Planning download...", file=out)

    if plan.status == DownloadPlanStatus.ALREADY_DOWNLOADED:
        print("Artifact already downloaded.", file=out)
        return 0
    if plan.status == DownloadPlanStatus.BLOCKED:
        for reason in plan.reasons:
            print(f"Download error: {reason}", file=err)
        if not plan.reasons:
            print("Download error: download plan is blocked", file=err)
        return 1
    if plan.status != DownloadPlanStatus.READY:
        print(
            f"Download error: cannot plan download (status: {plan.status.value})",
            file=err,
        )
        return 1

    print(f"Destination: {plan.destination}", file=out)
    print("Downloading...", file=out)
    downloader = (downloader_factory or Downloader)(ModelStore())
    try:
        result = downloader.download(plan)
    except UnsafePathError as error:
        print(f"Download error: {error}", file=err)
        return 1
    if result.success:
        print("Download complete.", file=out)
        if artifact.sha256:
            print("SHA-256 verified.", file=out)
        print("Artifact state: downloaded", file=out)
        return 0
    if result.status == DownloadResultStatus.CHECKSUM_MISMATCH:
        print(f"Download error: SHA-256 verification failed: {result.error}", file=err)
        return 1
    if result.status in {
        DownloadResultStatus.HTTP_ERROR,
        DownloadResultStatus.NETWORK_ERROR,
    }:
        print(f"Download error: download failed: {result.error}", file=err)
        return 1
    if result.status == DownloadResultStatus.FILESYSTEM_ERROR:
        print(f"Download error: filesystem error: {result.error}", file=err)
        return 1
    print(
        f"Download error: download failed ({result.status.value}): {result.error}",
        file=err,
    )
    return 1


def run_model(
    model_id: str | None,
    prompt: str | None,
    *,
    quantization: str | None = None,
    filename: str | None = None,
) -> int:
    if not model_id or prompt is None or not prompt.strip():
        print("Usage: python3 -m app.main run <model-id> --prompt <text>", file=sys.stderr)
        return 2
    try:
        model_store = ModelStore()
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
    try:
        preparation = _prepare(
            resolved.model, resolved.artifact, capability, model_store
        )
    except PreparationError as error:
        print(f"Run error: {error.message}", file=sys.stderr)
        for warning in (*error.compatibility_warnings, *error.selection_warnings):
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
) -> int:
    """Interactive multi-turn chat over one persistent runtime process."""
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    input_fn = input_fn if input_fn is not None else input

    if not model_id:
        print("Usage: python3 -m app.main chat <model-id>", file=err)
        return 2

    try:
        model_store = ModelStore()
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

    try:
        preparation = _prepare(
            resolved.model, resolved.artifact, capability, model_store
        )
    except PreparationError as error:
        print(f"Chat error: {error.message}", file=err)
        for warning in (*error.compatibility_warnings, *error.selection_warnings):
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


USAGE_FLOW = """\
usage flow:
  1. discover models:      python3 -m app.main models
  2. download a model:     python3 -m app.main download <model-id>
  3. list local artifacts: python3 -m app.main list
  4. run a single prompt:  python3 -m app.main run <model-id> --prompt "..."
  5. start a chat session: python3 -m app.main chat <model-id>
  6. diagnose GPU software: python3 -m app.main diagnose

model-id notes:
  models prints a friendly name (e.g. "Qwen2.5-Coder 7B Instruct") together
  with the canonical model id (e.g. "qwen2.5-coder-7b-instruct"). Always pass
  the model id, never the friendly name, to download, run and chat.

examples:
  python3 -m app.main models
  python3 -m app.main download qwen2.5-coder-7b-instruct
  python3 -m app.main run qwen2.5-coder-7b-instruct --prompt "Hello"
  python3 -m app.main diagnose


"""
def serve_command(host: str | None = None, port: int | None = None) -> int:
    """Start the read-only HTTP API server (loopback-only)."""
    return serve(host=host or "127.0.0.1", port=8000 if port is None else port)


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
        description="CastleArq: local model discovery, download, execution and chat",
        epilog=USAGE_FLOW,
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=("detect", "diagnose", "models", "list", "source", "plan", "download", "run", "chat", "serve"),
        help="command to execute",
    )
    parser.add_argument(
        "provider",
        nargs="?",
        help=(
            "command-specific value: model-id for download/run/chat; "
            "source provider for source; repository for plan"
        ),
    )
    parser.add_argument(
        "repository",
        nargs="?",
        help=(
            "command-specific value: repository for source; "
            "artifact filename for plan"
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
        help="quantization level to select for download, run or chat",
    )
    parser.add_argument(
        "--filename",
        help="exact artifact filename to select for download, run or chat",
    )
    args = parser.parse_args()
    supported_flags = {
        "detect": (),
        "diagnose": (),
        "models": (),
        "list": (),
        "source": (),
        "plan": (),
        "download": ("quantization", "filename"),
        "run": ("prompt", "quantization", "filename"),
        "chat": ("quantization", "filename"),
        "serve": (),
    }
    for flag in ("prompt", "quantization", "filename"):
        if getattr(args, flag) is not None and flag not in supported_flags[args.command]:
            parser.error(f"--{flag} is not valid for command '{args.command}'")
    for flag in ("host", "port"):
        if getattr(args, flag) is not None and args.command != "serve":
            parser.error(f"--{flag} is not valid for command '{args.command}'")
    if args.command == "diagnose" and (
        args.provider is not None or args.repository is not None
    ):
        parser.error("diagnose takes no arguments")
    if args.command == "detect":
        print_detection()
    elif args.command == "diagnose":
        return print_gpu_diagnosis()
    elif args.command == "models":
        print_models()
    elif args.command == "list":
        print_local_models()
    elif args.command == "source":
        return print_source(args.provider, args.repository)
    elif args.command == "plan":
        return print_plan(args.provider, args.repository)
    elif args.command == "download":
        if args.repository is not None:
            parser.error("download accepts exactly one model-id")
        return run_download(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
        )
    elif args.command == "run":
        if args.repository is not None:
            parser.error("run accepts exactly one model-id")
        return run_model(
            args.provider,
            args.prompt,
            quantization=args.quantization,
            filename=args.filename,
        )
    elif args.command == "chat":
        if args.repository is not None:
            parser.error("chat accepts exactly one model-id")
        return chat_model(
            args.provider,
            quantization=args.quantization,
            filename=args.filename,
        )
    elif args.command == "serve":
        return serve_command(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
