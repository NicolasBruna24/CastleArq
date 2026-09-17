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

"""Persistent remediation context between ``diagnose`` and ``verify``.

The CLI lifecycle spans separate invocations: ``diagnose`` observes the
system and proposes a declarative plan, the user applies the solution
manually, and ``verify`` re-observes and compares. This module persists the
small, strictly typed context the later comparison needs
(:class:`DiagnosisSession`) under ``~/.castlearq/sessions/`` — the user's own
space, never a system location.

Strictly no execution: the session file is data. It is parsed with
``json.loads`` into frozen dataclasses, never ``eval``'d, never handed to a
shell, and never used as a source of commands. Corrupt or invalid files are
rejected with :class:`SessionError` (a controlled error), never executed and
never silently trusted. Nothing here talks to the network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .gpu_diagnosis import DiagnosisStatus

#: Environment-variable override for the session root (tests).
SESSION_ROOT_ENV = "CASTLEARQ_SESSION_ROOT"

_SESSIONS_DIRNAME = "sessions"
_SESSION_FILENAME = "gpu-remediation.json"
_SCHEMA_VERSION = 1
_STATUS_VALUES = frozenset(status.value for status in DiagnosisStatus)


class SessionError(Exception):
    """A persisted session exists but cannot be trusted or used."""


@dataclass(frozen=True)
class DiagnosisSession:
    """Minimal context required to verify a remediation later.

    Everything is data captured from the original ``diagnose`` run; the
    plan itself is rebuilt at verification time by the pure B5 builder from
    the persisted original diagnosis. No commands, paths or secrets are
    stored, and nothing stored is ever executed.
    """

    schema_version: int
    original_status: DiagnosisStatus
    runtime: str
    backend: str
    platform: str
    missing: tuple["MissingComponentRecord", ...] = ()

    def to_dict(self) -> dict[str, object]:
        """JSON-safe projection (plain data, no references to commands)."""
        return {
            "schema_version": self.schema_version,
            "original_status": self.original_status.value,
            "runtime": self.runtime,
            "backend": self.backend,
            "platform": self.platform,
            "missing_components": [item.to_dict() for item in self.missing],
        }


@dataclass(frozen=True)
class MissingComponentRecord:
    """Faithful copy of one missing component's evidence (data only).

    ``passed`` is always ``False`` (only confirmed absences are persisted)
    so reconstructing :class:`~app.gpu_diagnosis.MissingComponent` keeps its
    invariant: unknown evidence is never turned into a missing component.
    """

    component: str
    required_by: str
    detail: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "component": self.component,
            "required_by": self.required_by,
            "detail": self.detail,
            "source": self.source,
        }



def parse_session(payload: object) -> DiagnosisSession:
    """Validate untrusted data into a :class:`DiagnosisSession`.

    Every field is checked explicitly; anything malformed, incomplete or of
    the wrong type raises :class:`SessionError` instead of being partially
    trusted. Unknown schema versions are rejected — never guessed.
    """
    if not isinstance(payload, dict):
        raise SessionError("session data must be a JSON object")
    version = payload.get("schema_version")
    if version != _SCHEMA_VERSION:
        raise SessionError(f"unsupported session schema version: {version!r}")
    status = payload.get("original_status")
    if not isinstance(status, str) or status not in _STATUS_VALUES:
        raise SessionError(f"invalid original_status: {status!r}")
    raw_missing = payload.get("missing_components", [])
    if not isinstance(raw_missing, list):
        raise SessionError("missing_components must be a list")
    missing: list[MissingComponentRecord] = []
    for item in raw_missing:
        if not isinstance(item, dict):
            raise SessionError("each missing component must be an object")
        for key in ("component", "required_by", "detail", "source"):
            if not isinstance(item.get(key), str):
                raise SessionError(f"invalid missing component {key!r}")
        missing.append(
            MissingComponentRecord(
                component=item["component"],
                required_by=item["required_by"],
                detail=item["detail"],
                source=item["source"],
            )
        )
    fields: list[str] = []
    for key in ("runtime", "backend", "platform"):
        value = payload.get(key)
        if not isinstance(value, str):
            raise SessionError(f"invalid {key}: {value!r}")
        fields.append(value)
    runtime, backend, platform = fields
    return DiagnosisSession(
        schema_version=_SCHEMA_VERSION,
        original_status=DiagnosisStatus(status),
        runtime=runtime,
        backend=backend,
        platform=platform,
        missing=tuple(missing),
    )



def session_root(
    home: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return ``~/.castlearq/sessions`` (overridable for tests only)."""
    environment = os.environ if environ is None else environ
    override = environment.get(SESSION_ROOT_ENV, "")
    if override:
        return Path(override)
    base = Path.home() if home is None else home
    return base / ".castlearq" / _SESSIONS_DIRNAME


def session_path(root: Path | None = None) -> Path:
    """Return the concrete session file inside ``root``."""
    target_root = session_root() if root is None else root
    return target_root / _SESSION_FILENAME


def save_session(
    session: DiagnosisSession,
    root: Path | None = None,
) -> Path:
    """Persist the session (atomic replace; creates the directory)."""
    path = session_path(root)
    payload = json.dumps(session.to_dict(), indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
    os.replace(tmp, path)
    return path


def load_session(
    root: Path | None = None,
) -> DiagnosisSession | None:
    """Load the persisted session, or ``None`` when none was saved.

    A file that exists but cannot be read, parsed or validated raises
    :class:`SessionError` — corrupt data is reported, never executed and
    never partially trusted.
    """
    path = session_path(root)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SessionError(f"cannot read session file: {error}") from error
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise SessionError(
            f"session file is not valid JSON: {error}") from error
    return parse_session(payload)


def clear_session(root: Path | None = None) -> bool:
    """Remove the persisted session; return whether one existed."""
    path = session_path(root)
    if not path.exists():
        return False
    path.unlink()
    return True
