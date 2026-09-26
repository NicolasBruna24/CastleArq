
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

"""Model compatibility and recommendation logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from .hardware import HardwareSnapshot
from .models import ModelSpec, Quantization
from .runtimes import BackendStatus, RuntimeStatus


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    MARGINAL = "marginal"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompatibilityConfig:
    safety_margin: float = 1.20
    ram_offload_factor: float = 0.50
    model_overhead: float = 1.15

    def __post_init__(self) -> None:
        if self.safety_margin < 1:
            raise ValueError("safety_margin must be >= 1")
        if self.ram_offload_factor < 0:
            raise ValueError("ram_offload_factor must be >= 0")
        if self.model_overhead <= 0:
            raise ValueError("model_overhead must be > 0")


def default_config_path() -> Path:
    """Return the user configuration path without creating it."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "castlearq" / "config.toml"


def load_config(path: Path | None = None) -> CompatibilityConfig:
    if path is None:
        path = default_config_path()
    values: dict[str, float | int] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return CompatibilityConfig()
    in_section = False
    for line in lines:
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith("["):
            in_section = stripped == "[compatibility]"
            continue
        if not in_section or "=" not in stripped:
            continue
        key, raw = (item.strip() for item in stripped.split("=", 1))
        try:
            values[key] = float(raw) if "." in raw else int(raw)
        except ValueError:
            raise ValueError(f"Invalid compatibility value for {key}: {raw}") from None
    defaults = CompatibilityConfig()
    parsed = CompatibilityConfig(
        safety_margin=float(values.get("safety_margin", defaults.safety_margin)),
        ram_offload_factor=float(values.get("ram_offload_factor", defaults.ram_offload_factor)),
        model_overhead=float(values.get("model_overhead", defaults.model_overhead)),
    )
    return parsed


@dataclass(frozen=True)
class CompatibilityResult:
    model: ModelSpec
    status: CompatibilityStatus
    score: int
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    estimated_memory_bytes: int | None
    memory_is_estimate: bool
    recommended_quantization: Quantization | None
    recommended_runtime: str | None
    recommended_backend: str | None


def estimate_memory_bytes(model: ModelSpec, quantization: Quantization, config: CompatibilityConfig) -> int | None:
    if model.parameter_count_b is None:
        return None
    parameters = model.parameter_count_b * 1_000_000_000
    return int(parameters * quantization.bits_per_parameter / 8 * config.model_overhead)


def assess_model(
    hardware: HardwareSnapshot,
    runtimes: list[RuntimeStatus],
    backends: list[BackendStatus],
    model: ModelSpec,
    quantization: Quantization | None = None,
    config: CompatibilityConfig = CompatibilityConfig(),
) -> CompatibilityResult:
    runtime_status = _choose_runtime(model, runtimes)
    runtime = runtime_status.name if runtime_status else None
    backend = _choose_backend(model, backends, runtime_status)
    if runtime is None or backend is None:
        return CompatibilityResult(
            model,
            CompatibilityStatus.UNKNOWN if runtime is not None else CompatibilityStatus.INCOMPATIBLE,
            0,
            (
                # B9.54: the public runtime surface is English-first (B9.53
                # section 10). These are user-facing reasons shown by
                # ``castlearq models`` and carried in ``execute`` warnings;
                # only the wording changes, never the status, score or
                # decision taken on this branch.
                "No evidence of a compatible runtime/backend combination."
                if runtime is not None
                else "No compatible runtime available.",
            ),
            (),
            None, True, None, runtime, backend,
        )
    selected = quantization or _best_quantization(hardware, model, config)
    if selected is None:
        selected = min(model.quantizations, key=lambda item: item.quality) if model.quantizations else None
    if selected is None:
        return CompatibilityResult(
            model, CompatibilityStatus.UNKNOWN, 0,
            ("Not enough information about the model parameters or memory.",), (),
            None, True, None, runtime, backend,
        )
    estimated = estimate_memory_bytes(model, selected, config)
    capacity = _capacity_bytes(hardware)
    if estimated is None or capacity is None:
        return CompatibilityResult(
            model, CompatibilityStatus.UNKNOWN, 0,
            ("Model or hardware memory is unknown.",), (),
            estimated, True, selected, runtime, backend,
        )
    gpu_capacities, ram_capacity = capacity
    safe_gpu = max(
        (int(value / config.safety_margin) for value in gpu_capacities),
        default=None,
    )
    safe_ram = int(ram_capacity * config.ram_offload_factor / config.safety_margin)
    if safe_gpu is not None and estimated <= safe_gpu:
        status = CompatibilityStatus.COMPATIBLE
        reason = "Estimated memory fits in VRAM with a safety margin."
        margin = (safe_gpu - estimated) / max(safe_gpu, 1)
    elif runtime_status and runtime_status.supports_backend("CPU") and safe_ram > 0 and estimated <= safe_ram:
        status = CompatibilityStatus.MARGINAL
        reason = "Requires falling back to system RAM; performance may be significantly reduced."
        margin = (safe_ram - estimated) / max(safe_ram, 1)
    else:
        status = (
            CompatibilityStatus.UNKNOWN
            if not gpu_capacities and runtime_status is None
            else CompatibilityStatus.INCOMPATIBLE
        )
        reason = (
            "Not enough evidence of memory capacity or offload capability."
            if status == CompatibilityStatus.UNKNOWN
            else "Estimated memory exceeds the available capacity with the safety margin."
        )
        margin = -1
    score = _score(status, selected.quality, margin, backend, model.task)
    warnings = ("Model memory is an estimate.",)
    if status == CompatibilityStatus.MARGINAL:
        warnings += ("Falling back to system RAM is not equivalent to VRAM.",)
    return CompatibilityResult(
        model, status, score, (reason,), warnings, estimated, True,
        selected, runtime, backend,
    )


def recommend_models(
    hardware: HardwareSnapshot,
    runtimes: list[RuntimeStatus],
    backends: list[BackendStatus],
    models: tuple[ModelSpec, ...] | list[ModelSpec],
    task: str | None = None,
    config: CompatibilityConfig = CompatibilityConfig(),
) -> list[CompatibilityResult]:
    results = [
        assess_model(hardware, runtimes, backends, model, config=config)
        for model in models
        if task is None or model.task == task
    ]
    return sorted(results, key=lambda result: result.score, reverse=True)


def _best_quantization(
    hardware: HardwareSnapshot, model: ModelSpec, config: CompatibilityConfig
) -> Quantization | None:
    candidates = sorted(
        model.quantizations,
        key=lambda item: item.quality,
        reverse=True,
    )
    capacity = _capacity_bytes(hardware)
    if capacity is None:
        return None
    safe_gpu = max(
        (int(value / config.safety_margin) for value in capacity[0]),
        default=None,
    )
    selected = None
    for candidate in candidates:
        estimated = estimate_memory_bytes(model, candidate, config)
        if estimated is not None and safe_gpu is not None and estimated <= safe_gpu:
            selected = candidate
            break
    if selected is not None:
        return selected
    if not _supports_cpu(model):
        return None
    safe_ram = int(capacity[1] * config.ram_offload_factor / config.safety_margin)
    for candidate in candidates:
        estimated = estimate_memory_bytes(model, candidate, config)
        if estimated is not None and estimated <= safe_ram:
            selected = candidate
            break
    return selected


def _capacity_bytes(hardware: HardwareSnapshot) -> tuple[tuple[int, ...], int] | None:
    ram = hardware.memory.total_bytes
    if ram is None:
        return None
    capacities = tuple(
        value for gpu in hardware.gpus
        for value in (_known_gpu_capacity(gpu),)
        if value is not None
    )
    return capacities, ram


def _choose_runtime(model: ModelSpec, runtimes: list[RuntimeStatus]) -> RuntimeStatus | None:
    for runtime in runtimes:
        if runtime.available and any(_same_name(runtime.name, supported) for supported in model.supported_runtimes):
            return runtime
    return None


def _choose_backend(
    model: ModelSpec,
    backends: list[BackendStatus],
    runtime: RuntimeStatus | None,
) -> str | None:
    for backend in backends:
        if (
            backend.available
            and backend.name in model.supported_backends
            and runtime is not None
            and runtime.supports_backend(backend.name)
        ):
            return backend.name
    return None


def _supports_cpu(model: ModelSpec) -> bool:
    return "CPU" in model.supported_backends


def _known_gpu_capacity(gpu) -> int | None:
    if gpu.vram_available_bytes is not None:
        return gpu.vram_available_bytes
    return gpu.vram_bytes


def _same_name(left: str, right: str) -> bool:
    return left.lower().replace(" ", "") in right.lower().replace(" ", "") or right.lower().replace(" ", "") in left.lower().replace(" ", "")


def _score(
    status: CompatibilityStatus,
    quality: int,
    margin: float,
    backend: str,
    task: str,
) -> int:
    base = {
        CompatibilityStatus.COMPATIBLE: 70,
        CompatibilityStatus.MARGINAL: 45,
        CompatibilityStatus.UNKNOWN: 20,
        CompatibilityStatus.INCOMPATIBLE: 0,
    }[status]
    margin_points = max(0, min(15, int(margin * 15))) if margin >= 0 else 0
    preferred_points = 5 if backend != "CPU" else 0
    task_points = {"coding": 5, "reasoning": 4, "general-purpose": 3}.get(task, 0)
    return min(100, base + quality + margin_points + preferred_points + task_points)
