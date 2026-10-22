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

"""Pure classifier for runtime-reported GPU layer-offload evidence.

Inspects only the captured stdout/stderr of the actual inference
subprocess. It never executes commands, reads files, touches the
environment, or persists data.

Scope: runtime-reported layer *placement* for one inference run, not
independently measured GPU utilization or proof of GPU computation.
"""

from dataclasses import dataclass
from enum import Enum
import re


#: Normalized runtime identity (leading ``version:`` prefix stripped) for
#: which the final-report format below was validated against real output.
SUPPORTED_RUNTIME_VERSION = "0.4.0-dev (build 10909, commit a2878d30d)"

SUPPORTED_RUNTIME_VERSIONS = frozenset({SUPPORTED_RUNTIME_VERSION})

#: Exact final-report line observed in build 10909 stderr, e.g.
#: ``load_tensors: offloaded 23/23 layers to GPU``. ASCII digits only.
_FINAL_COUNT = re.compile(
    r"load_tensors:[ \t]*offloaded[ \t]+([0-9]+)[ \t]*/[ \t]*([0-9]+)"
    r"[ \t]+layers[ \t]+to[ \t]+GPU"
)

#: Sanity cap for a plausible layer total; larger totals are malformed.
_MAX_PLAUSIBLE_LAYERS = 1_000_000


class OffloadStatus(str, Enum):
    """Tri-state outcome of offload-evidence classification."""

    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    UNKNOWN = "unknown"


class OffloadEvidenceCategory(str, Enum):
    """Short normalized reason for the classification."""

    FINAL_COUNT = "final_count"
    NO_FINAL_COUNT = "no_final_count"
    CONFLICTING_REPORTS = "conflicting_reports"
    MALFORMED_COUNT = "malformed_count"
    UNVALIDATED_ZERO = "unvalidated_zero"
    NONZERO_EXIT = "nonzero_exit"
    TIMEOUT = "timeout"
    LAUNCH_FAILURE = "launch_failure"
    NOT_EXECUTED = "not_executed"
    UNSUPPORTED_VERSION = "unsupported_version"


@dataclass(frozen=True)
class GpuOffloadEvidence:
    """In-memory, per-run assessment of runtime-reported layer placement.

    ``NOT_CONFIRMED`` is reserved for future version-validated explicit
    zero semantics; the initial classifier never emits it (zero forms
    stay ``UNKNOWN``). No raw logs are retained.
    """

    status: OffloadStatus
    evidence_category: str
    offloaded_layers: int | None = None
    total_layers: int | None = None
    source_stream: str | None = None
    runtime_version: str | None = None



def normalize_runtime_version(version: str | None) -> str | None:
    """Strip a leading ``version:`` prefix; ``None`` when empty."""
    if not isinstance(version, str):
        return None
    text = version.strip()
    if not text:
        return None
    if text.lower().startswith("version:"):
        text = text[len("version:"):].strip()
        if not text:
            return None
    return text


def _unknown(category: OffloadEvidenceCategory, version: str | None = None,
             ) -> GpuOffloadEvidence:
    return GpuOffloadEvidence(
        status=OffloadStatus.UNKNOWN,
        evidence_category=category.value,
        runtime_version=version,
    )


def assess_gpu_offload(
    stdout: str | None,
    stderr: str | None,
    exit_code: int | None,
    *,
    timed_out: bool = False,
    launch_failed: bool = False,
    not_executed: bool = False,
    runtime_version: str | None = None,
) -> GpuOffloadEvidence:
    """Classify runtime-reported layer offload for one inference run.

    Pure: no subprocess, file I/O, env access, or persistence.
    Precedence: not_executed > launch_failed > timed_out > nonzero exit
    > unsupported version > parse. Explicit zero counts stay ``UNKNOWN``
    (``unvalidated_zero``); ``NOT_CONFIRMED`` is never emitted here.
    """
    if not_executed:
        return _unknown(OffloadEvidenceCategory.NOT_EXECUTED,
                        runtime_version)
    if launch_failed:
        return _unknown(OffloadEvidenceCategory.LAUNCH_FAILURE,
                        runtime_version)
    if timed_out:
        return _unknown(OffloadEvidenceCategory.TIMEOUT, runtime_version)
    if not isinstance(exit_code, bool) and exit_code != 0:
        return _unknown(OffloadEvidenceCategory.NONZERO_EXIT,
                        runtime_version)
    if normalize_runtime_version(runtime_version) not in (
            SUPPORTED_RUNTIME_VERSIONS):
        return _unknown(OffloadEvidenceCategory.UNSUPPORTED_VERSION,
                        runtime_version)
    found: list[tuple[int, int, str]] = []
    for text, stream in ((stdout, "stdout"), (stderr, "stderr")):
        if not isinstance(text, str) or not text:
            continue
        for match in _FINAL_COUNT.finditer(text):
            try:
                off = int(match.group(1))
                tot = int(match.group(2))
            except ValueError:
                return _unknown(
                    OffloadEvidenceCategory.MALFORMED_COUNT,
                    runtime_version)
            found.append((off, tot, stream))
    if not found:
        return _unknown(OffloadEvidenceCategory.NO_FINAL_COUNT,
                        runtime_version)
    distinct = {(off, tot) for off, tot, _ in found}
    if len(distinct) > 1:
        return _unknown(OffloadEvidenceCategory.CONFLICTING_REPORTS,
                        runtime_version)
    off, tot = next(iter(distinct))
    if tot <= 0 or tot > _MAX_PLAUSIBLE_LAYERS or off < 0 or off > tot:
        return _unknown(OffloadEvidenceCategory.MALFORMED_COUNT,
                        runtime_version)
    if off == 0:
        return _unknown(OffloadEvidenceCategory.UNVALIDATED_ZERO,
                        runtime_version)
    streams = {stream for _, _, stream in found}
    source = "stderr" if "stderr" in streams else next(iter(streams))
    return GpuOffloadEvidence(
        status=OffloadStatus.CONFIRMED,
        evidence_category=OffloadEvidenceCategory.FINAL_COUNT.value,
        offloaded_layers=off,
        total_layers=tot,
        source_stream=source,
        runtime_version=runtime_version,
    )
