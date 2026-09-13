"""Command-line interface for LocalAI Hub."""

from __future__ import annotations

import argparse
import sys

from .hardware import detect_hardware
from .compatibility import CompatibilityConfig, assess_model, load_config, recommend_models
from .execution import ArtifactExecutionPreflight, ExecutionRequest
from .execution_service import ModelExecutionService
from .model_catalog import get_catalog
from .model_store import ModelStore
from .downloads import DownloadPlanStatus, DownloadPlanner
from .models import ArtifactSpec
from .resolver import ModelArtifactResolutionError, ModelArtifactResolver
from .runner import LlamaCppRunner
from .sources import HuggingFaceSource, SourceError
from .sources.huggingface import _download_url, detect_quantization
from .runtimes import (
    RuntimeStatus,
    detect_backends,
    detect_llama_capability,
    detect_runtimes,
    recommend,
)
from .selection import RuntimeBackendSelector


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
    try:
        download_url = _download_url(repository, filename)
    except SourceError as error:
        print(f"Plan error: {error}")
        return 1
    artifact = ArtifactSpec(
        model_id=repository,
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

    hardware = detect_hardware()
    capability = detect_llama_capability()
    runtimes = [
        RuntimeStatus(
            "llama.cpp / llama.app",
            installed=capability.executable_path is not None,
            available=capability.available,
            gpu_backend_detected=bool(hardware.gpus),
            supported_backends=capability.supported_backends,
        )
    ]
    detected_gpu_backends = {
        backend for gpu in hardware.gpus for backend in gpu.backends
    }
    backends = detect_backends(detected_gpu_backends=detected_gpu_backends)

    def evaluate(model):
        return assess_model(
            hardware,
            runtimes,
            backends,
            model,
            config=CompatibilityConfig(),
        )

    result = ModelExecutionService(
        evaluate,
        ArtifactExecutionPreflight(model_store),
        RuntimeBackendSelector(),
        capability,
        LlamaCppRunner(capability),
    ).execute(
        resolved.model,
        resolved.artifact,
        ExecutionRequest(
            resolved.artifact,
            prompt,
            timeout_seconds=_DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        ),
    )
    if result.success:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        return 0
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.error:
        print(f"Run error: {result.error.message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="localai", description="LocalAI Hub hardware detection")
    parser.add_argument(
        "command", choices=("detect", "models", "list", "source", "plan", "run"),
        help="command to execute",
    )
    parser.add_argument("provider", nargs="?")
    parser.add_argument("repository", nargs="?")
    parser.add_argument("--prompt")
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
    elif args.command == "run":
        if args.repository is not None:
            parser.error("run accepts exactly one model-id")
        return run_model(args.provider, args.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
