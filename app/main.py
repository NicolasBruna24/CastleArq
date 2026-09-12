"""Command-line interface for LocalAI Hub."""

from __future__ import annotations

import argparse

from .hardware import detect_hardware
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="localai", description="LocalAI Hub hardware detection")
    parser.add_argument("command", choices=("detect",), help="command to execute")
    args = parser.parse_args()
    if args.command == "detect":
        print_detection()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
