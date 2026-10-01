
# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""B9.79: read-only runtime/artifact observation producer (pre-admission).

Separate from ``LlamaCppRunner`` on purpose: this observer belongs to the
*pre-admission* physical observation boundary and must never be the
post-admission execution path. It runs one isolated, bounded ``llama cli``
invocation that loads the artifact without meaningful generation::

    llama cli --simple-io --single-turn --model <artifact> --device <device>
      --prompt <prompt> -n 0 -lv 4

``-n 0`` prevents significant generation, ``--single-turn`` avoids a REPL and
``-lv 4`` raises log verbosity so load/rejection signals are observable. The
observation is read-only and ephemeral: nothing is persisted, the ModelStore
and the artifact are never modified, and no execution result is produced.

The classification is deliberately conservative (B9.79 sections 4, 6, 9): a
zero exit code alone is never ``POSITIVE`` and a non-zero exit code alone is
never ``NEGATIVE``. ``POSITIVE`` requires an explicit load marker *and* a zero
exit code; ``NEGATIVE`` requires an explicit rejection marker; everything else
is ``UNKNOWN``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from .runtime_artifact_evidence import (
    ArtifactObservation,
    RuntimeArtifactEvidence,
)

__all__ = [
    "DEFAULT_OBSERVATION_PROMPT",
    "DEFAULT_OBSERVATION_TIMEOUT_SECONDS",
    "RuntimeArtifactObserver",
    "RuntimeObservationError",
]

DEFAULT_OBSERVATION_PROMPT = "hi"
DEFAULT_OBSERVATION_TIMEOUT_SECONDS = 120.0

#: llama.cpp log signatures that witness an artifact load. They are
#: deliberately conservative: ``POSITIVE`` requires one of these *and* a zero
#: exit code, so arbitrary or empty output stays ``UNKNOWN``.
_LOAD_MARKERS: tuple[str, ...] = (
    "llama_model_loader",
    "load_tensors",
    "llama_model_load",
    "model loaded",
    "llama_new_context_with_model",
)

#: llama.cpp log signatures that witness an explicit artifact rejection or load
#: failure. They are matched before the load markers.
_REJECTION_MARKERS: tuple[str, ...] = (
    "failed to load model",
    "failed to load gguf",
    "failed to open gguf",
    "error loading model",
    "unable to load model",
    "cannot load model",
    "unknown model architecture",
)

RunProcess = Callable[..., subprocess.CompletedProcess]


class RuntimeObservationError(RuntimeError):
    """The observation could not be produced (producer/infrastructure error).

    Raised only when the *producer itself* could not perform the operation
    (e.g. the process could not be launched). A producer error is never
    projected as ``NEGATIVE`` (B9.79 section 4).
    """


class RuntimeArtifactObserver:
    """Produce :class:`RuntimeArtifactEvidence` by observing one runtime load."""

    def __init__(self, run_process: RunProcess | None = None) -> None:
        self._run_process = run_process or subprocess.run

    def observe(
        self,
        *,
        executable_path: str | None,
        runtime_identity: str,
        runtime_version: str | None,
        artifact_path: str | Path | None,
        artifact_reference: str,
        artifact_format: str,
        artifact_architecture: str | None,
        device: str | None,
        prompt: str = DEFAULT_OBSERVATION_PROMPT,
        timeout_seconds: float = DEFAULT_OBSERVATION_TIMEOUT_SECONDS,
    ) -> RuntimeArtifactEvidence:
        """Observe one runtime loading the artifact; never persists anything.

        Returns ``UNKNOWN`` without running anything when the physical context
        is incomplete (no executable, no resolved artifact path, or no concrete
        device/backend). A launch failure raises
        :class:`RuntimeObservationError`; a timeout, a zero exit code without a
        load signal and a non-zero exit code without an explicit rejection
        signal all yield ``UNKNOWN`` (never a fabricated ``NEGATIVE``).
        """
        base_identity = runtime_identity
        base_version: str | None = runtime_version
        base_reference = artifact_reference
        base_format = artifact_format
        base_architecture: str | None = artifact_architecture
        base_backend: str | None = device
        missing = self._missing_context(executable_path, artifact_path, device)
        if missing is not None:
            return RuntimeArtifactEvidence(
                runtime_identity=base_identity,
                runtime_version=base_version,
                artifact_reference=base_reference,
                artifact_format=base_format,
                artifact_architecture=base_architecture,
                backend=base_backend,
                observation=ArtifactObservation.UNKNOWN,
                provenance=f"runtime artifact observation not performed: {missing}",
            )
        argv = [
            str(executable_path),
            "cli",
            "--simple-io",
            "--single-turn",
            "--model",
            str(artifact_path),
            "--device",
            str(device),
            "--prompt",
            prompt,
            "-n",
            "0",
            "-lv",
            "4",
        ]
        provenance = "RuntimeArtifactObserver: " + " ".join(argv)
        try:
            completed = self._run_process(
                argv,
                capture_output=True,
                text=False,
                check=False,
                shell=False,
                env={"PATH": os.defpath},
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return RuntimeArtifactEvidence(
                runtime_identity=base_identity,
                runtime_version=base_version,
                artifact_reference=base_reference,
                artifact_format=base_format,
                artifact_architecture=base_architecture,
                backend=base_backend,
                observation=ArtifactObservation.UNKNOWN,
                provenance=provenance + " [timed out]",
            )
        except OSError as error:
            raise RuntimeObservationError(
                f"runtime artifact observation could not be launched: {error}"
            ) from error

        observation = _classify(
            completed.returncode, _text(completed.stdout), _text(completed.stderr)
        )
        return RuntimeArtifactEvidence(
            runtime_identity=base_identity,
            runtime_version=base_version,
            artifact_reference=base_reference,
            artifact_format=base_format,
            artifact_architecture=base_architecture,
            backend=base_backend,
            observation=observation,
            provenance=provenance,
        )

    @staticmethod
    def _missing_context(
        executable_path: str | None,
        artifact_path: str | Path | None,
        device: str | None,
    ) -> str | None:
        if not executable_path:
            return "no runtime executable was resolved"
        if artifact_path is None:
            return "no physical artifact path was resolved"
        if not device:
            return "no concrete backend/device was determined"
        return None


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _classify(exit_code: int | None, stdout: str, stderr: str) -> ArtifactObservation:
    """Classify one completed observation conservatively.

    A rejection marker -- an explicit artifact load failure -- is ``NEGATIVE``.
    Otherwise a load marker **with** a zero exit code is ``POSITIVE``.
    Everything else (including a bare zero or non-zero exit code with no causal
    marker) is ``UNKNOWN``: ``exit_code == 0`` alone never proves the artifact
    loaded, and ``exit_code != 0`` alone never proves the artifact was the
    cause (B9.79 sections 4, 6, 9).
    """
    haystack = f"{stdout}\n{stderr}".lower()
    if any(marker in haystack for marker in _REJECTION_MARKERS):
        return ArtifactObservation.NEGATIVE
    if exit_code == 0 and any(marker in haystack for marker in _LOAD_MARKERS):
        return ArtifactObservation.POSITIVE
    return ArtifactObservation.UNKNOWN
