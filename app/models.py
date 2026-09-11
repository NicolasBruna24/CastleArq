"""Model metadata types reserved for the model catalog phase."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str = "Unknown"
    family: str = "Unknown"
    size_bytes: int | None = None
    quantization: str = "Unknown"
    format: str = "Unknown"
    runtime: str = "Unknown"
    approximate_vram_bytes: int | None = None
