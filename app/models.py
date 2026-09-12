"""Data structures for model metadata and quantization estimates."""

from dataclasses import dataclass
from enum import Enum
import hashlib
@dataclass(frozen=True)
class Quantization:
    name: str
    bits_per_parameter: float
    quality: int
    recommended: bool = False
    memory_estimated: bool = True


class ArtifactState(str, Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class ArtifactSpec:
    model_id: str
    source: str
    repository: str
    filename: str
    format: str = "Unknown"
    quantization: str = "Unknown"
    download_url: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    state: ArtifactState = ArtifactState.NOT_DOWNLOADED

    @property
    def artifact_id(self) -> str:
        value = "|".join(
            (self.source, self.repository, self.filename, self.quantization)
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
