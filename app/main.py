"""Command-line interface for LocalAI Hub."""

from __future__ import annotations

import argparse

from .hardware import detect_hardware
from .compatibility import load_config, recommend_models
from .model_catalog import get_catalog
from .model_store import ModelStore
from .runtimes import detect_backends, detect_runtimes, recommend


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="localai", description="LocalAI Hub hardware detection")
    parser.add_argument(
        "command", choices=("detect", "models", "list"), help="command to execute"
    )
    args = parser.parse_args()
    if args.command == "detect":
        print_detection()
    elif args.command == "models":
        print_models()
    elif args.command == "list":
        print_local_models()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
