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

"""Immutable compatibility-result domain (Block B9.1).

Implements the representational contract of
``docs/B9.0-compatibility-engine-design.md``: the structures needed to
*represent* a compatibility outcome with its evidence, conditions and
warnings. This module does NOT calculate compatibility — no engine, no
aggregation, no memory estimation, no hardware/runtime adapters.

Core decisions (B9.0):

- ``CompatibilityStatus`` has exactly four states; there is no top-level
  ``UNKNOWN`` (insufficient evidence is ``INSUFFICIENT_EVIDENCE``).
- ``UNKNOWN != FAILED`` and ``UNKNOWN != INCOMPATIBLE``: a check-level
  ``UNKNOWN`` never becomes a failure, and an isolated ``UNKNOWN`` never
  forces the whole result into ``INSUFFICIENT_EVIDENCE``. Sufficiency is
  the future engine's call, so no automatic aggregation is implemented.
- Conditions are declarative data (never commands, never callables).
- Result-level invariants only (``COMPATIBLE`` carries no conditions,
  ``COMPATIBLE_WITH_CONDITIONS`` requires at least one,
  ``INCOMPATIBLE`` requires at least one ``FAILED`` check).
- Pure: frozen dataclasses, tuples, no I/O, no execution, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CompatibilityStatus(str, Enum):
    """Overall compatibility verdict (B9.0 §2)."""

    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_CONDITIONS = "compatible_with_conditions"
    INCOMPATIBLE = "incompatible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CheckStatus(str, Enum):
    """Outcome of one compatibility check (B9.0 §4).

    ``PASSED`` — sufficient evidence and the condition holds.
    ``FAILED`` — sufficient evidence and the condition does not hold.
    ``UNKNOWN`` — insufficient evidence to decide.
    """

    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class EvidenceKind(str, Enum):
    """Provenance level of one evidence item (B9.0 §5)."""

    OBSERVED = "observed"
    CALCULATED = "calculated"
    INFERRED = "inferred"


#: Values an evidence item (or check expectation/observation) may carry.
#: ``None`` means unknown; no other "empty" representation is allowed.
EvidenceValue = str | int | float | bool | None


def _check_value(name: str, value: Any) -> EvidenceValue:
    """Validate an evidence-style value (primitives or ``None`` only)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"{name} must be str, int, float, bool or None")


def _check_name(name: str, value: Any) -> str:
    """Validate a mandatory non-empty identifier."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class EvidenceItem:
    """One cited fact sustaining a check or condition (B9.0 §4–§5).

    ``source`` is a human-readable origin (e.g.
    ``"HardwareSnapshot.gpus[0].vram"``); ``kind`` records the provenance
    level and is never upgraded automatically (an ``INFERRED`` item stays
    ``INFERRED``). No secrets, credentials or sensitive data belong here.
    """

    source: str
    value: EvidenceValue = None
    kind: EvidenceKind = EvidenceKind.OBSERVED

    def __post_init__(self) -> None:
        _check_name("source", self.source)
        _check_value("value", self.value)
        if not isinstance(self.kind, EvidenceKind):
            raise ValueError("kind must be an EvidenceKind")


@dataclass(frozen=True)
class CompatibilityCheck:
    """One evaluated statement with its expected/observed pair (B9.0 §4).

    Generic by design: ``name``, ``expected`` and ``observed`` accept any
    short value (or ``None`` when unknown) so future requirements can be
    evaluated without changing this contract. ``status`` is never ``None``.
    """

    name: str
    status: CheckStatus
    expected: EvidenceValue = None
    observed: EvidenceValue = None
    evidence: tuple[EvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        _check_name("name", self.name)
        if not isinstance(self.status, CheckStatus):
            raise ValueError("status must be a CheckStatus")
        _check_value("expected", self.expected)
        _check_value("observed", self.observed)
        if isinstance(self.evidence, list):
            object.__setattr__(self, "evidence", tuple(self.evidence))
        elif not isinstance(self.evidence, tuple):
            raise ValueError("evidence must be a tuple of EvidenceItem")
        for item in self.evidence:
            if not isinstance(item, EvidenceItem):
                raise ValueError("evidence must contain EvidenceItem only")


@dataclass(frozen=True)
class CompatibilityCondition:
    """One declarative condition attached to a verdict (B9.0 §10).

    A condition is data, never an action: no commands, shell strings,
    install instructions or callables are allowed anywhere in this
    structure. A condition needs a clear name, a non-empty description and,
    when applicable, the backing evidence.
    """

    name: str
    description: str
    evidence: tuple[EvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        _check_name("name", self.name)
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")
        if isinstance(self.evidence, list):
            object.__setattr__(self, "evidence", tuple(self.evidence))
        elif not isinstance(self.evidence, tuple):
            raise ValueError("evidence must be a tuple of EvidenceItem")
        for item in self.evidence:
            if not isinstance(item, EvidenceItem):
                raise ValueError("evidence must contain EvidenceItem only")


@dataclass(frozen=True)
class CompatibilityResult:
    """A complete, explainable compatibility verdict (B9.0 §13).

    Result-level invariants only (representation, not aggregation):

    - ``COMPATIBLE`` carries no conditions;
    - ``COMPATIBLE_WITH_CONDITIONS`` requires at least one condition;
    - ``INCOMPATIBLE`` requires at least one ``FAILED`` check;
    - any status may carry checks, conditions-as-allowed and warnings.

    No ``compatible: bool`` exists: the verdict is ``status`` plus the
    information that explains it.
    """

    status: CompatibilityStatus
    checks: tuple[CompatibilityCheck, ...] = ()
    conditions: tuple[CompatibilityCondition, ...] = ()
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.status, CompatibilityStatus):
            raise ValueError("status must be a CompatibilityStatus")
        for collection, label, kind in (
            (self.checks, "checks", CompatibilityCheck),
            (self.conditions, "conditions", CompatibilityCondition),
        ):
            if isinstance(collection, list):
                object.__setattr__(
                    self, label, tuple(collection))
                collection = getattr(self, label)
            elif not isinstance(collection, tuple):
                raise ValueError(f"{label} must be a tuple")
            for item in collection:
                if not isinstance(item, kind):
                    raise ValueError(
                        f"{label} must contain {kind.__name__} only")
        if isinstance(self.warnings, list):
            object.__setattr__(self, "warnings", tuple(self.warnings))
        elif not isinstance(self.warnings, tuple):
            raise ValueError("warnings must be a tuple of strings")
        for warning in self.warnings:
            if not isinstance(warning, str) or not warning.strip():
                raise ValueError("warnings must be non-empty strings")
        if isinstance(self.notes, list):
            object.__setattr__(self, "notes", tuple(self.notes))
        elif not isinstance(self.notes, tuple):
            raise ValueError("notes must be a tuple of strings")
        for note in self.notes:
            if not isinstance(note, str) or not note.strip():
                raise ValueError("notes must be non-empty strings")
        if (self.status is CompatibilityStatus.COMPATIBLE
                and self.conditions):
            raise ValueError(
                "COMPATIBLE must not carry conditions; use"
                " COMPATIBLE_WITH_CONDITIONS")
        if (self.status is CompatibilityStatus.COMPATIBLE_WITH_CONDITIONS
                and not self.conditions):
            raise ValueError(
                "COMPATIBLE_WITH_CONDITIONS requires at least one condition")
        if (self.status is CompatibilityStatus.INCOMPATIBLE
                and not any(check.status is CheckStatus.FAILED
                            for check in self.checks)):
            raise ValueError(
                "INCOMPATIBLE requires at least one FAILED check")

