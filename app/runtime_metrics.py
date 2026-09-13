"""Parsing of llama.cpp human-readable runtime metrics."""

import math
import re

from .execution import RuntimeMetricSource, RuntimeMetrics


_VALUE = r"[^\s\]|]+"
_METRICS_BLOCK = re.compile(
    rf"""
    \[
    \s*
    (?:
        Prompt\s*:\s*(?P<prompt>{_VALUE})\s*t\s*/\s*s
    )?
    \s*\|\s*
    (?:
        Generation\s*:\s*(?P<generation>{_VALUE})\s*t\s*/\s*s
    )?
    \s*
    \]
    """,
    re.VERBOSE,
)


def parse_llama_human_output(text: str) -> RuntimeMetrics | None:
    """Extract explicitly reported prompt and generation throughput metrics."""
    if not isinstance(text, str):
        return None

    for match in _METRICS_BLOCK.finditer(text):
        prompt = _parse_number(match.group("prompt"))
        generation = _parse_number(match.group("generation"))
        if prompt is not None or generation is not None:
            return RuntimeMetrics(
                prompt_tokens_per_second=prompt,
                generation_tokens_per_second=generation,
                source=RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
            )
    return None


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) and number >= 0 else None
