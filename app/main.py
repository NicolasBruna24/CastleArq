"""Command-line interface for LocalAI Hub."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from types import SimpleNamespace

from .compatibility import CompatibilityConfig, CompatibilityStatus, assess_model, load_config, recommend_models
from .execution import ArtifactExecutionPreflight, ArtifactPreflightError, ExecutionRequest, ExecutableArtifact
from .hardware import detect_hardware
from .model_catalog import get_catalog
from .model_identity import SOURCE_REPOSITORY_TO_MODEL_ID, logical_model_id
from .model_store import ModelStore, UnsafePathError
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



@dataclass(frozen=True)
class ExecutionPreparation:
    """Inputs shared by one-shot run and interactive chat.

    This type is deliberately minimal and immutable: it carries only the
    information that both execution paths need AFTER resolution but BEFORE
    any runtime process is launched. It does not execute anything.

    ``compatibility_warnings`` and ``selection_warnings`` are kept separate so
    that each execution path can preserve its exact historical warning
    behaviour (one-shot run prints both; interactive chat prints only
    selection warnings).
    """

    executable_artifact: ExecutableArtifact
    target: ExecutionTarget
    compatibility_warnings: tuple[str, ...]
    selection_warnings: tuple[str, ...]


class PreparationError(Exception):
    """Raised when an artifact cannot be prepared for any execution path."""

    def __init__(
        self,
        message: str,
        compatibility_warnings: tuple[str, ...] = (),
        selection_warnings: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.compatibility_warnings = compatibility_warnings
        self.selection_warnings = selection_warnings

    @property
    def warnings(self) -> tuple[str, ...]:
        """Merged warnings, deduplicated, for callers that treat them uniformly."""
        return tuple(dict.fromkeys((*self.compatibility_warnings, *self.selection_warnings)))


def _detect_runtime_statuses(
    capability: RuntimeCapability,
) -> list[RuntimeStatus]:
    """Build the runtime list that both run and chat currently construct inline."""
    return [
        RuntimeStatus(
            "llama.cpp / llama.app",
            installed=capability.executable_path is not None,
            available=capability.available,
            gpu_backend_detected=False,
            supported_backends=capability.supported_backends,
        )
    ]


def _prepare(
    model: ModelSpec,
    artifact: ArtifactSpec,
    capability: "RuntimeCapability",
    model_store: ModelStore,
) -> ExecutionPreparation:
    """Resolve compatibility, preflight and selection without launching anything.

    Both ``run_model`` and ``chat_model`` need exactly this sequence. Keeping it
    here guarantees both paths make the same decisions from the same inputs.
    """
    hardware = detect_hardware()
    runtimes = _detect_runtime_statuses(capability)
    detected_gpu_backends = {backend for gpu in hardware.gpus for backend in gpu.backends}
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)

    compatibility = assess_model(
        hardware, runtimes, backends, model, config=CompatibilityConfig()
    )
    if compatibility.status in {
        CompatibilityStatus.INCOMPATIBLE,
        CompatibilityStatus.UNKNOWN,
    }:
        raise PreparationError(
            "Model compatibility does not permit execution",
            compatibility_warnings=compatibility.warnings,
        )

    try:
        executable_artifact = ArtifactExecutionPreflight(model_store).validate(artifact)
    except ArtifactPreflightError as error:
        raise PreparationError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    try:
        selection = RuntimeBackendSelector().select(
            compatibility, capability, executable_artifact
        )
    except RuntimeSelectionError as error:
        raise PreparationError(
            error.message, compatibility_warnings=compatibility.warnings
        ) from error

    return ExecutionPreparation(
        executable_artifact=executable_artifact,
        target=selection.target,
        compatibility_warnings=compatibility.warnings,
        selection_warnings=selection.warnings,
    )

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

    print("LocalAI Hub")
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
    print("LocalAI Hub - Model recommendations")
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


def print_local_models() -> None:
    print("LocalAI Hub - Local models")
    print("==========================")
    entries = ModelStore().list_artifacts()
    if not entries:
        print("No local model artifacts found.")
        return
    for entry in entries:
        if entry.artifact is None:
            print(f"  INVALID: {entry.manifest_path} ({entry.message})")
            continue
        print(f"  {entry.artifact.model_id} / {entry.artifact.filename}")
        print(f"    State: {entry.state.value}")
        print(f"    Source: {entry.artifact.source}")
        if entry.message:
            print(f"    Problem: {entry.message}")


def print_source(provider: str | None, repository: str | None) -> int:
    if provider != "huggingface" or not repository:
        print("Usage: python3 -m app.main source huggingface <repository>")
        return 2
    try:
        artifacts = HuggingFaceSource().discover_artifacts(repository)
    except SourceError as error:
        print(f"Source error: {error}")
        return 1
    print(f"LocalAI Hub - Hugging Face metadata: {repository}")
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
    print("LocalAI Hub - Offline download plan")
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

    repositories = sorted(
        repository
        for (source, repository), logical in SOURCE_REPOSITORY_TO_MODEL_ID.items()
        if logical == model_id
    )
    if len(repositories) != 1:
        print(
            f"Download error: no unique source repository is mapped to model: {model_id}",
            file=err,
        )
        return 1
    repository = repositories[0]
    source_name = next(
        source
        for (source, name), logical in SOURCE_REPOSITORY_TO_MODEL_ID.items()
        if logical == model_id and name == repository
    )
    if source_name != "huggingface":
        print(f"Download error: unsupported source: {source_name}", file=err)
        return 1

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
            print(f"LocalAI Hub - Download candidates for model: {model_id}", file=out)
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


def run_model(model_id: str | None, prompt: str | None) -> int:
    if not model_id or prompt is None or not prompt.strip():
        print("Usage: python3 -m app.main run <model-id> --prompt <text>", file=sys.stderr)
        return 2
    try:
        model_store = ModelStore()
        resolver = ModelArtifactResolver(model_store)
        resolved = resolver.resolve(model_id)
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
        resolved = resolver.resolve(model_id)
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

    print("LocalAI Hub — chat", file=out)
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="localai", description="LocalAI Hub hardware detection")
    parser.add_argument(
        "command",
        choices=("detect", "models", "list", "source", "plan", "download", "run", "chat"),
        help="command to execute",
    )
    parser.add_argument("provider", nargs="?")
    parser.add_argument("repository", nargs="?")
    parser.add_argument("--prompt")
    parser.add_argument("--quantization", help="quantization level to select for download")
    parser.add_argument("--filename", help="exact artifact filename to select for download")
    args = parser.parse_args()
    if args.command == "detect":
        print_detection()
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
        return run_model(args.provider, args.prompt)
    elif args.command == "chat":
        if args.repository is not None:
            parser.error("chat accepts exactly one model-id")
        return chat_model(args.provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
