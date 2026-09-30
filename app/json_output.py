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

"""Shared JSON output layer for the CLI ``--json`` surface (B9.76.2).

Single serialization layer behind the future ``--json`` commands
(B9.76.3+)::

    CLI command -> CLI output layer -> JSON

Deliberately CLI-specific and independent of the HTTP layer: the flow
must never go through HTTP DTOs, and no HTTP module may depend on this
one. No business logic lives here — the layer never decides exit codes,
never selects command fields, never computes hashes or identities, and
never turns a missing value into UNKNOWN (or UNKNOWN into a value).

Contract ratified in B9.76.1:

- envelope ``schema = "castlearq.cli"``, ``schema_version = 1``, plus
  ``command``, ``exit_code``, ``payload``, ``warnings`` and ``error``;
- enums serialize through ``.value`` (``CheckStatus.PASSED`` becomes
  ``"passed"``, never ``"PASSED"``);
- an unknown property is explicit:
  ``{"value": ..., "status": "unknown", "reason": ...}`` — ``None``
  alone is never promoted to UNKNOWN;
- ``error`` is ``{"kind": ..., "message": ...}`` or ``null``; an
  admission denial is a payload, never an ``error``;
- the output is exactly one deterministic JSON document
  (``json.dumps(..., indent=2, sort_keys=True)``, the ``app.session``
  precedent), with no banners, prefixes or human text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any

#: Fixed public schema identifier of the CLI JSON contract.
SCHEMA = "castlearq.cli"

#: Fixed public schema version of the CLI JSON contract.
SCHEMA_VERSION = 1

#: The only two keys a structured error object may carry.
_ERROR_KEYS = frozenset({"kind", "message"})


def serialize(value: Any) -> Any:
    """Convert ``value`` into plain JSON-safe data (generic, recursive).

    Handles ``dict``, ``list``, ``tuple``, ``str``, ``int``, ``float``,
    ``bool``, ``None``, :class:`enum.Enum` (projected through
    ``.value``) and dataclasses (field by field). Anything else raises
    :class:`TypeError`: this layer never guesses a representation for
    unknown types and contains no per-command serializers.
    """
    if isinstance(value, Enum):
        return serialize(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            _dict_key(key): serialize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            entry.name: serialize(getattr(value, entry.name))
            for entry in fields(value)
        }
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _dict_key(key: Any) -> str:
    """Return the JSON object key for ``key`` (enums use ``.value``)."""
    if isinstance(key, Enum):
        key = key.value
    return key if isinstance(key, str) else str(key)


def dumps(document: Any) -> str:
    """Render ``document`` as exactly one deterministic JSON document.

    Nothing but the document itself is produced — no trailing text, no
    prefixes, no human formatting. How the document reaches stdout is
    the wiring's decision (B9.76.3), not this layer's.
    """
    return json.dumps(serialize(document), indent=2, sort_keys=True)


def unknown(reason: str, *, value: Any = None) -> dict[str, Any]:
    """Represent a relevant property CastleArq has no value for.

    Produces the normative shape::

        {"value": <value>, "status": "unknown", "reason": "<code>"}

    ``reason`` is mandatory and must be a stable code backed by existing
    architecture (for example ``not_observed`` or
    ``no_checksum_declared``). This layer does not validate the
    vocabulary — each command owns its reasons.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")
    return {"value": value, "status": "unknown", "reason": reason}


def known(value: Any) -> dict[str, Any]:
    """Represent a property with an observed value.

    Symmetric counterpart of :func:`unknown`::

        {"value": <value>, "status": "known"}

    No ``reason`` is attached: a known value needs no explanation.
    """
    return {"value": value, "status": "known"}


def error(kind: str, message: str) -> dict[str, str]:
    """Build the structured error object ``{"kind", "message"}``.

    The set of ``kind`` codes is deliberately open — each command
    decides its own (for example ``evaluation_error``); only the shape
    is fixed. Admission denials never become errors.
    """
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("kind must be a non-empty string")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")
    return {"kind": kind, "message": message}


@dataclass(frozen=True)
class CliEnvelope:
    """The ratified ``castlearq.cli`` envelope (B9.76.1 §3).

    ``exit_code`` is the code the process will really return — this
    layer only carries it, never decides it. ``payload`` is
    command-specific plain data; no domain shape is imposed here.
    ``warnings`` and ``error`` stay strictly separate: warnings are
    advisory strings, an error is a failure object, and an admission
    denial is a payload with a ``null`` error.
    """

    command: str
    exit_code: int
    payload: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error: dict[str, str] | None = None
    schema: str = field(default=SCHEMA, init=False)
    schema_version: int = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command:
            raise ValueError("command must be a non-empty string")
        if isinstance(self.exit_code, bool):
            raise ValueError("exit_code must be an integer")
        if not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict")
        if isinstance(self.warnings, list):
            object.__setattr__(self, "warnings", tuple(self.warnings))
        elif not isinstance(self.warnings, tuple):
            raise ValueError("warnings must be a tuple of strings")
        for warning in self.warnings:
            if not isinstance(warning, str):
                raise ValueError("warnings must be strings")
        if self.error is None:
            return
        if not isinstance(self.error, dict):
            raise ValueError("error must be null or an object")
        if frozenset(self.error) != _ERROR_KEYS:
            raise ValueError(
                "error carries exactly 'kind' and 'message'")
        for key in _ERROR_KEYS:
            item = self.error[key]
            if not isinstance(item, str) or not item:
                raise ValueError(
                    f"error {key} must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection of the whole envelope."""
        return serialize(self)
