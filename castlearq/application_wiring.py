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

B9.22 extension (composition only — wiring only): the same module is the
composition point of the Execute Model use case
(``docs/B9.19-execute-application-use-case-specification.md``). It names the
concrete collaborators of that Application boundary (``ModelStore``,
``get_catalog``, ``detect_llama_capability``, ``ArtifactExecutionPreflight``,
``RuntimeBackendSelector``, ``LlamaCppRunner``) and returns an
``ExecuteModelDependencies`` value that a caller hands to ``execute_model``:

    Application / Composition Root (this module)
        ↓
    ExecuteModelDependencies
        ↓
    execute_model()

Constructing a collaborator is NOT performing its job: this module still
captures no context, integrates nothing, reconciles nothing, builds no
execution target and runs no subprocess for the Execute path either. The
ordering, the compatibility gate, the selection authority and the execution
stay inside the use case; ``castlearq/execute_model.py`` keeps importing no
concrete infrastructure and never knows a runner implementation
(B9.22 §3/§10). The direction is one-way: this module imports the
Application boundary, never the reverse.

Importing this module has no side effects: no capture, no integration,
no detection, no activation and no composition runs at import time.
"""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
import subprocess
from typing import Callable, Sequence

from .acquisition_service import ModelAcquisitionService
from .catalog_query_service import ModelCatalogQueryService
from .discovery import ModelDiscovery
from .downloads.downloader import Downloader
from .downloads.planner import DownloadPlanner
from .execute_model import ExecuteModelDependencies
from .execution import ArtifactExecutionPreflight
from .initial_knowledge import INITIAL_KNOWLEDGE_REGISTRY
from .model_catalog import get_catalog
from .model_identity import (
    downloadable_locator,
    logical_model_id,
    source_repositories_for_logical_model,
)
from .model_store import ModelStore
from .observation_knowledge import IntegrationResult, integrate
from .observation_probe import CommandResult, EnvironmentObserver
from .runner import LlamaCppRunner
from .runtimes import RuntimeCapability, detect_llama_capability
from .selection import RuntimeBackendSelector
from .sources.huggingface_discovery import HuggingFaceDiscoveryProvider

__all__ = ["compose_and_integrate", "compose_execute_model_dependencies"]


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


# ----------------------------------------------------------------------
# Execute Model composition (B9.22: real collaborators, wiring only)
# ----------------------------------------------------------------------

def production_capability_provider() -> RuntimeCapability:
    """Detect the llama.cpp runtime capability (B9.19 §12 freshness, Q-2).

    Evaluated fresh on every call: no module cache, no process-level cache,
    no second ``RuntimeCapability`` object and no background refresh. The
    probe is the machine state as it is right now, exactly like
    ``run_service.detect_once()``.
    """
    return detect_llama_capability()


def compose_execute_model_dependencies(
    model_store: ModelStore | None = None,
) -> ExecuteModelDependencies:
    """Compose ``ExecuteModelDependencies`` from real infrastructure (B9.22).

    One call = ONE use-case invocation: the dependencies are built, the
    capability is detected once, and the composed value is handed to
    ``execute_model`` and then discarded. The returned object MUST NOT be
    cached between invocations, because the capability it carries is a
    snapshot of the machine at composition time.

    Capability identity (B9.22 §5): the single ``RuntimeCapability`` detected
    here is what ``capability_provider`` returns AND what ``LlamaCppRunner``
    is constructed with, so the capability the selector reasons about (target
    backend, runtime name, supported formats) is exactly the capability the
    runner executes with — never two divergent detections of one machine. The
    detected instance is created at composition time (it IS the freshness
    boundary), which satisfies both the selector/runner shared-instance
    requirement and B9.19 §12: the provider returns that same instance on
    every call within this composition, and the next composition detects
    again. Mirrors ``run_service.run_once`` (detect once per invocation,
    one runner per invocation, no cache anywhere).

    Bindings are composition only: the concrete store, catalog, preflight,
    selector and runner are named HERE and nowhere in the Application use
    case (§3/§10). ``compatibility_provider`` is deliberately left unset: its
    Application default (the B9.19 §8 transitional legacy gate) is the
    ratified binding, and re-composing that assessment glue here would
    duplicate the legacy assessment path (B9.22 §9 — no new abstraction,
    no duplicated gate).

    No exception handling, retry, fallback, degradation or reinterpretation
    is applied: a detection or store failure is a Class-B defect and
    propagates unchanged (§11.2).

    ``model_store`` (B9.74): the store this invocation selected. It is passed
    in by the caller that resolved ``--model-store``; when it is omitted the
    composition binds the environment/default-resolved store, exactly as
    before. Composition still names the store here and nowhere else, and no
    second resolution is introduced: the value the CLI resolved is the value
    bound.
    """
    capability = production_capability_provider()

    def capability_provider() -> RuntimeCapability:
        """The capability of THIS composition (identity, not a cache)."""
        return capability

    return ExecuteModelDependencies(
        model_store=model_store if model_store is not None else ModelStore(),
        models=get_catalog(),
        capability_provider=capability_provider,
        preflight_factory=ArtifactExecutionPreflight,
        selector=RuntimeBackendSelector(),
        runner=LlamaCppRunner(capability),
    )


# ----------------------------------------------------------------------
# Acquisition composition (B9.85: application boundary + production wiring)
# ----------------------------------------------------------------------

def compose_acquisition_service(
    *,
    source: str = "huggingface",
    discovery_provider: ModelDiscovery | None = None,
    model_store: ModelStore | None = None,
    planner_factory: Callable[[], DownloadPlanner] | None = None,
    downloader_factory: Callable[[ModelStore], Downloader] | None = None,
) -> ModelAcquisitionService:
    """Compose the B9.85 ``ModelAcquisitionService`` from real collaborators.

    This is the composition point for the download use case, in the same
    spirit as ``compose_execute_model_dependencies`` for the execute use case.

    One call is ONE use-case invocation. The service is never cached between
    invocations: the store is resolved by the caller (B9.22 rule — the value
    the CLI resolved is the value bound), and the single ``ModelStore``
    instance it owns drives planning, transfer and registration so the planned
    destination always belongs to the store that persists the artifact.

    Identity (D3): ``logical_model_id`` stays the single authority. It is bound
    HERE, into a resolver of B9.82's exact contract —
    ``Callable[[str], str | None]`` — and the service receives only that bound
    callable. The service therefore has no ``source`` value, no identity table
    and no way to fabricate an identity.

    No second dependency-injection mechanism is introduced: collaborators are
    passed explicitly, exactly as for the execute use case.
    """
    store = model_store if model_store is not None else ModelStore()

    def identity_resolver(repository: str) -> str | None:
        """B9.82 IdentityResolver bound to this composition's source."""
        return logical_model_id(source, repository)

    planner = (
        planner_factory() if planner_factory is not None
        else DownloadPlanner(model_store=store)
    )
    downloader = (
        downloader_factory(store) if downloader_factory is not None
        else Downloader(store)
    )

    return ModelAcquisitionService(
        discovery_provider=(
            discovery_provider
            if discovery_provider is not None
            else HuggingFaceDiscoveryProvider()
        ),
        identity_resolver=identity_resolver,
        locator_resolver=downloadable_locator,
        planner=planner,
        downloader=downloader,
        store=store,
        locator_audit=source_repositories_for_logical_model,
    )
# ----------------------------------------------------------------------
# Catalog / query composition (B9.86: application boundary, no surface)
# ----------------------------------------------------------------------

def compose_catalog_query_service(
    *,
    discovery_provider: ModelDiscovery | None = None,
) -> ModelCatalogQueryService:
    """Compose the B9.86 ``ModelCatalogQueryService`` from real collaborators.

    This is the composition point for the catalog/query use case, in the same
    spirit as ``compose_acquisition_service`` for the download use case.

    One call is ONE service instance. The service is never cached between
    invocations and holds no state: every ``query()`` call is one discovery
    round-trip.

    Scope (B9.86 section 25): this function wires an application boundary and
    nothing else. It authorizes no CLI command, no API endpoint, no GUI and no
    Model Library surface. B9.86 is deliberately allocated without a production
    caller; that absence is a consequence of the approved scope, not a gap.

    The service never instantiates a provider: it receives the injected
    ``ModelDiscovery`` collaborator and imports only the port. No second
    dependency-injection mechanism is introduced; collaborators are passed
    explicitly, exactly as for the acquisition and execute use cases.
    """
    return ModelCatalogQueryService(
        discovery_provider=(
            discovery_provider
            if discovery_provider is not None
            else HuggingFaceDiscoveryProvider()
        ),
    )
