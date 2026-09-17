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

"""Immutable model-intelligence domain (Block B8.1).

Implements the contract documented in
``docs/B8.0-model-intelligence-design.md``: a logical :class:`Model` with
0..N immutable :class:`ModelArtifact` variants. This is a pure
representation domain: no I/O, no discovery, no compatibility analysis, no
memory estimation and no system access.

Core decision (B8.0): ``None`` means *unknown* — "CastleArq does not have
enough information to assert this" — never a fabricated value and never
"the attribute does not exist". Invariants are enforced in ``__post_init__``
with ``ValueError`` (the same style as ``MissingComponent`` in B2).

Three different concepts (correction after the first B8.1 review):

```text
precision  !=  quantization  !=  format
```

* :class:`ModelPrecision` — the numeric precision of the weights
  (``F32``, ``F16``, ``BF16``, ``FP8``, …; no closed enum).
* :class:`ModelQuantization` — whether the artifact is quantized, with an
  explicit three-state :class:`QuantizationStatus`:

  - ``UNKNOWN`` — no evidence to decide whether it is quantized;
  - ``NOT_QUANTIZED`` — evidence confirms it is not quantized;
  - ``QUANTIZED`` — evidence confirms it is quantized.

  ``UNKNOWN != NOT_QUANTIZED``: they are never represented by the same
  value, and neither is automatically converted into the other. A
  quantized artifact never implies a base precision (``GGUF + Q4_K_M``
  keeps ``precision = UNKNOWN``).
* :class:`ModelArtifact.format` — the container format, independent of
  precision and quantization.

``nominal_bits`` is a declared figure, never an actual average bits-per-
parameter measurement and never a memory calculation.

``Model`` never carries conclusions (``compatible``, ``can_run``,
``recommended_*``, memory estimates): those belong to the future
Compatibility Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class ModelIdentity:
    """Identity of a logical model (B8.0 §3.1).

    ``name`` is conceptually mandatory and cannot be empty or whitespace;
    ``model_id``, ``version`` and ``variant`` may be ``None`` (unknown).
    Nothing is invented from missing values.
    """

    name: str
    model_id: str | None = None
    version: str | None = None
    variant: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name is mandatory and cannot be empty")


@dataclass(frozen=True)
class ModelProvenance:
    """Basic provenance of a logical model (B8.0 §3.2).

    Provenance is *not* trust: trust scores, signatures, hashes and evidence
    chains belong to B9+. Every field may be ``None`` (unknown).
    """

    source: str | None = None
    repository: str | None = None
    author: str | None = None


@dataclass(frozen=True)
class ModelArchitecture:
    """Structural description of a logical model (B8.0 §3.3).

    All fields may be ``None``. ``parameters`` and ``active_parameters``,
    when known, must be positive integers with
    ``active_parameters <= parameters``. An unknown ``active_parameters``
    is never assumed equal to ``parameters`` and never coerced to zero.
    """

    architecture: str | None = None
    model_type: str | None = None
    parameters: int | None = None
    active_parameters: int | None = None

    def __post_init__(self) -> None:
        for name in ("parameters", "active_parameters"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer or None")
            if value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            self.parameters is not None
            and self.active_parameters is not None
            and self.active_parameters > self.parameters
        ):
            raise ValueError("active_parameters cannot exceed parameters")


class QuantizationStatus(str, Enum):
    """Explicit three-state evidence about artifact quantization (B8.1).

    ``UNKNOWN`` — CastleArq has no sufficient evidence to determine whether
    the artifact is quantized.

    ``NOT_QUANTIZED`` — evidence confirms the artifact is not quantized.

    ``QUANTIZED`` — evidence confirms the artifact is quantized.

    ``UNKNOWN != NOT_QUANTIZED``: the absence of information is never
    converted into an assertion.
    """

    UNKNOWN = "unknown"
    NOT_QUANTIZED = "not_quantized"
    QUANTIZED = "quantized"


@dataclass(frozen=True)
class ModelQuantization:
    """Quantization of one artifact (B8.0 §3.4, corrected in B8.1).

    ``status`` is mandatory. ``method`` and ``nominal_bits`` may be ``None``
    (unknown); ``nominal_bits``, when known, must be a positive integer and
    is a *declared* figure — never the actual average bits per parameter and
    never a memory input.

    Invariants:

    - ``UNKNOWN``: ``method``/``nominal_bits`` are not required;
    - ``NOT_QUANTIZED``: ``method`` and ``nominal_bits`` must be ``None``;
    - ``QUANTIZED``: the method and/or the nominal bits may still be
      unknown (e.g. quantized with unknown details).

    There is no closed list of methods and no artificial ``"none"`` token.
    """

    status: QuantizationStatus
    method: str | None = None
    nominal_bits: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, QuantizationStatus):
            raise ValueError("status must be a QuantizationStatus")
        if self.method is not None and not isinstance(self.method, str):
            raise ValueError("method must be a string or None")
        if self.nominal_bits is not None:
            if isinstance(self.nominal_bits, bool) or not isinstance(
                self.nominal_bits, int
            ):
                raise ValueError("nominal_bits must be an integer or None")
            if self.nominal_bits <= 0:
                raise ValueError("nominal_bits must be a positive integer")
        if (
            self.status is QuantizationStatus.NOT_QUANTIZED
            and (self.method is not None or self.nominal_bits is not None)
        ):
            raise ValueError(
                "NOT_QUANTIZED artifacts cannot declare a method or"
                " nominal_bits")


@dataclass(frozen=True)
class ModelPrecision:
    """Numeric precision of an artifact's weights (B8.0 §3.4, B8.1 fix).

    Precision is *not* quantization and *not* the format. ``name`` and
    ``bits`` may each be ``None`` (unknown); ``bits``, when known, must be a
    positive integer. No closed enum of precisions is imposed — CastleArq
    does not assume it knows every precision that exists.
    """

    name: str | None = None
    bits: int | None = None

    def __post_init__(self) -> None:
        if self.name is not None and not isinstance(self.name, str):
            raise ValueError("name must be a string or None")
        if self.bits is not None:
            if isinstance(self.bits, bool) or not isinstance(self.bits, int):
                raise ValueError("bits must be an integer or None")
            if self.bits <= 0:
                raise ValueError("bits must be a positive integer")


@dataclass(frozen=True)
class ModelArtifact:
    """One concrete, storable/distributable variant of a model (B8.0 §2).

    ``format``, ``precision`` and ``quantization`` are three independent
    concepts; not every format carries a precision or a quantization.
    ``storage_size_bytes`` describes storage only — it is never a runtime
    memory figure. Every field except ``precision`` and ``quantization`` may
    be ``None`` (unknown).
    """

    precision: ModelPrecision
    quantization: ModelQuantization
    identifier: str | None = None
    format: str | None = None
    storage_size_bytes: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.precision, ModelPrecision):
            raise ValueError("precision must be a ModelPrecision")
        if not isinstance(self.quantization, ModelQuantization):
            raise ValueError("quantization must be a ModelQuantization")
        if self.identifier is not None and not isinstance(
            self.identifier, str
        ):
            raise ValueError("identifier must be a string or None")
        if self.format is not None and not isinstance(self.format, str):
            raise ValueError("format must be a string or None")
        if self.storage_size_bytes is not None:
            if isinstance(self.storage_size_bytes, bool) or not isinstance(
                self.storage_size_bytes, int
            ):
                raise ValueError(
                    "storage_size_bytes must be an integer or None")
            if self.storage_size_bytes < 0:
                raise ValueError(
                    "storage_size_bytes must be a non-negative integer")


@dataclass(frozen=True)
class ModelCapabilities:
    """Model capabilities with evidence semantics (B8.0 §4, B8.0 §5).

    Each capability is ``True`` (confirmed), ``False`` (confirmed absent) or
    ``None`` (unknown). ``None`` is never converted into ``False``. The
    taxonomy is intentionally limited to these five capabilities; future
    ones (audio, reranking, speech, …) extend the domain later.
    """

    text_generation: bool | None = None
    code_generation: bool | None = None
    vision: bool | None = None
    embeddings: bool | None = None
    tool_use: bool | None = None

    def __post_init__(self) -> None:
        for name in (
            "text_generation",
            "code_generation",
            "vision",
            "embeddings",
            "tool_use",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool or None")


@dataclass(frozen=True)
class Model:
    """A logical model with its immutable artifact variants (B8.0 §2).

    ``artifacts`` is a ``tuple`` (immutable) and may be empty. ``max_context``
    may be ``None``; when known it must be a positive integer. This structure
    carries facts only — never compatibility conclusions or memory estimates.
    """

    identity: ModelIdentity
    provenance: ModelProvenance = field(default_factory=ModelProvenance)
    architecture: ModelArchitecture = field(default_factory=ModelArchitecture)
    max_context: int | None = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    artifacts: tuple[ModelArtifact, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ModelIdentity):
            raise ValueError("identity must be a ModelIdentity")
        if not isinstance(self.provenance, ModelProvenance):
            raise ValueError("provenance must be a ModelProvenance")
        if not isinstance(self.architecture, ModelArchitecture):
            raise ValueError("architecture must be a ModelArchitecture")
        if not isinstance(self.capabilities, ModelCapabilities):
            raise ValueError("capabilities must be a ModelCapabilities")
        if self.max_context is not None:
            if isinstance(self.max_context, bool) or not isinstance(
                self.max_context, int
            ):
                raise ValueError("max_context must be an integer or None")
            if self.max_context <= 0:
                raise ValueError("max_context must be a positive integer")
        if isinstance(self.artifacts, list):
            object.__setattr__(self, "artifacts", tuple(self.artifacts))
        elif not isinstance(self.artifacts, tuple):
            raise ValueError("artifacts must be a tuple of ModelArtifact")
        for artifact in self.artifacts:
            if not isinstance(artifact, ModelArtifact):
                raise ValueError("artifacts must contain ModelArtifact only")



