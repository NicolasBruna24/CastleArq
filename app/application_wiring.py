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

"""B9.14 I1: Application / Composition Root of the CastleArq path.

Implements the ratified B9.14 contract (see
``docs/B9.14-application-wiring-specification.md``). Composition only —
this module is the sole authorized composition point of the CastleArq
path (Q-1/Q-9a/Q-9b, §13.3):

    external caller (Q-6 direct activation — NOT implemented here)
        ↓
    Application / Composition Root (this module)
        ↓
    construct the four Q-9c production bindings
        ↓
    EnvironmentObserver(...)
        ↓
    capture_context()                  → fresh EnvironmentContext (Q-2)
        ↓
    INITIAL_KNOWLEDGE_REGISTRY         (Q-3a–Q-3d, provisioned here)
        ↓
    integrate(context, registry)       (B9.13 contract, invoked once)
        ↓
    IntegrationResult                  → returned verbatim, STOP (§12)

Boundaries NOT implemented here (ratified and separate): the Q-6 host /
activation mechanism (a future caller invokes this module directly), the
Q-5 Post-Integration Receiver (the result is left at the stop-line), and
Evaluation (§12 stop-line, I-04/I-05/I-Q9-08/I-Q9-09).

Failure policy: Class-A acquisition failures are recorded as data inside
the captured ``EnvironmentContext`` by the observer (which returns,
never raises) and are FORWARDED through ``integrate()`` into the
``IntegrationResult`` (Q-7 = FORWARD, §11.3); Class-B defects propagate
unchanged (§11.2). This module performs NO error reclassification and
introduces NO retry, fallback, recovery, degradation, backend selection
or model execution.

Importing this module has no side effects: no capture, no integration,
no activation runs at import time.
"""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
import subprocess
from typing import Sequence

from .initial_knowledge import INITIAL_KNOWLEDGE_REGISTRY
from .observation_knowledge import IntegrationResult, integrate
from .observation_probe import CommandResult, EnvironmentObserver

__all__ = ["compose_and_integrate"]


# ----------------------------------------------------------------------
# Q-9c production bindings (composition-root glue; §13.1 / §13.3)
# ----------------------------------------------------------------------

def utc_timestamp() -> str:
    """UTC ISO-8601 timestamp (Q-9c TimestampProvider).

    Evaluated fresh on every call: no cache, no global clock, no
    background refresh.
    """
    return datetime.now(timezone.utc).isoformat()


def _partial_text(value: bytes | str | None) -> str:
    """Best-effort ``str`` view of captured child output (glue only)."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def production_command_runner(
    command: Sequence[str], timeout: float
) -> CommandResult:
    """Q-9c CommandRunner glue for ``Callable[[Sequence[str], float], CommandResult]``.

    Preserves the ratified B9.11 semantics (I-Q9-06): explicit timeout;
    never ``shell=True``; exit code / stdout / stderr preserved; timeout
    and ``OSError`` are represented as ``CommandResult.error`` (never as
    ``None``, never collapsed into ``UNAVAILABLE``); no exception escapes
    for failures of the external operation, so the observer records them
    as ERROR evidence (Class-A) and Q-7 forwards them.

    ``hardware.default_command_runner`` is deliberately NOT reused: its
    contract is incompatible with ``CommandResult`` (Q-9 Discovery).
    """
    try:
        completed = subprocess.run(
            list(command),
            shell=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            returncode=-1,
            stdout=_partial_text(exc.stdout),
            stderr=_partial_text(exc.stderr),
            error=f"timeout after {timeout} second(s)",
        )
    except OSError as exc:
        return CommandResult(
            returncode=-1,
            stdout="",
            stderr="",
            error=f"os error: {exc}",
        )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def production_file_reader(path: str) -> str | None:
    """Q-9c FileReader glue for ``Callable[[str], str | None]``.

    Existing readable content → ``str``; missing / unreadable file →
    ``None`` (the observer contract that yields OBSERVED / UNAVAILABLE
    semantics, I-Q9-07). ``LinuxHardwareDetector._read`` and the
    ``gpu_setup`` helpers are deliberately NOT reused: their semantics do
    not match the B9.11 contract.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


# ----------------------------------------------------------------------
# Composition Root invocation (Q-6: one activation → one invocation)
# ----------------------------------------------------------------------

def compose_and_integrate() -> IntegrationResult:
    """One CastleArq Composition Root invocation, and nothing else.

    Builds the Q-9c production bindings, constructs an
    ``EnvironmentObserver``, captures exactly one fresh
    ``EnvironmentContext`` (Q-2), integrates it exactly once against the
    Composition-Root-provisioned ``INITIAL_KNOWLEDGE_REGISTRY``
    (Q-3a–Q-3d, injected explicitly per I-02), and returns the
    ``IntegrationResult`` verbatim at the §12 stop-line for the
    caller-side continuation (Q-5 receiver boundary — not implemented
    here).

    No observer, context or result is held across invocations; no
    exception handling, retry, fallback or reinterpretation is applied.
    """
    observer = EnvironmentObserver(
        command_runner=production_command_runner,
        file_reader=production_file_reader,
        which_finder=shutil.which,
        timestamp_provider=utc_timestamp,
    )
    context = observer.capture_context()
    registry = INITIAL_KNOWLEDGE_REGISTRY
    return integrate(context, registry)
