"""Small, static model catalog for compatibility analysis.

The catalog contains no downloads or network access. Metadata marked as
estimated is intentionally kept separate from measured hardware data.
"""

from __future__ import annotations

from .models import DEFAULT_QUANTIZATIONS, ModelSpec, Quantization


def _quantizations() -> tuple[Quantization, ...]:
    return DEFAULT_QUANTIZATIONS


CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="qwen2.5-coder-7b-instruct",
        name="Qwen2.5-Coder 7B Instruct",
        provider="Qwen",
        family="Qwen2.5-Coder",
        parameter_count_b=7.0,
        task="coding",
        architecture="Transformer",
        supported_runtimes=("llama.cpp / llama.app", "Ollama"),
        supported_backends=("Vulkan", "CUDA", "ROCm", "CPU"),
        context_length=32768,
        quantizations=_quantizations(),
    ),
    ModelSpec(
        id="llama-3.1-8b-instruct",
        name="Llama 3.1 8B Instruct",
        provider="Meta",
        family="Llama 3.1",
        parameter_count_b=8.0,
        task="general-purpose",
        architecture="Transformer",
        supported_runtimes=("llama.cpp / llama.app", "Ollama"),
        supported_backends=("Vulkan", "CUDA", "ROCm", "CPU"),
        context_length=131072,
        quantizations=_quantizations(),
    ),
    ModelSpec(
        id="deepseek-r1-distill-qwen-14b",
        name="DeepSeek-R1-Distill-Qwen 14B",
        provider="DeepSeek",
        family="DeepSeek-R1-Distill",
        parameter_count_b=14.0,
        task="reasoning",
        architecture="Transformer",
        supported_runtimes=("llama.cpp / llama.app", "Ollama"),
        supported_backends=("Vulkan", "CUDA", "ROCm", "CPU"),
        context_length=32768,
        quantizations=_quantizations(),
    ),
)


def get_catalog() -> tuple[ModelSpec, ...]:
    return CATALOG
