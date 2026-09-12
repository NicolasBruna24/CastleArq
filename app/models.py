"""Data structures for model metadata and quantization estimates."""

from dataclasses import dataclass
@dataclass(frozen=True)
class Quantization:
    name: str
    bits_per_parameter: float
    quality: int
    recommended: bool = False
    memory_estimated: bool = True


DEFAULT_QUANTIZATIONS = (
    Quantization("Q2_K", 2.75, 1),
    Quantization("Q3_K_M", 3.5, 2),
    Quantization("Q4_K_M", 4.5, 3, recommended=True),
    Quantization("Q5_K_M", 5.5, 4),
    Quantization("Q6_K", 6.5, 5),
    Quantization("Q8_0", 8.5, 6),
)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str = "Unknown"
    family: str = "Unknown"
    size_bytes: int | None = None
    format: str = "Unknown"
    id: str | None = None
    parameter_count_b: float | None = None
    task: str = "general-purpose"
    architecture: str = "Unknown"
    supported_runtimes: tuple[str, ...] = ("llama.cpp / llama.app",)
    supported_backends: tuple[str, ...] = ("Vulkan", "CPU")
    context_length: int | None = None
    quantizations: tuple[Quantization, ...] = DEFAULT_QUANTIZATIONS
    metadata_estimated: bool = True

    @property
    def model_id(self) -> str:
        return self.id or self.name
