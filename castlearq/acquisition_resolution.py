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

"""B9.96: Acquisition Resolution — independent persistent acquisition bindings.

This module is the D+B architecture ratified for B9.96:

```text
D = the RESPONSIBILITY BOUNDARY   Acquisition Resolution is a separate
                                   concern from Identity Admission and from
                                   acquisition proper.
B = the STATE MECHANISM           independent persistent acquisition
                                   bindings; never identity records.
```

Authority
=========

```text
curated downloadable locator  ->  persistent acquisition binding
```

:func:`downloadable_locator` answers first, unchanged and byte-identical; the
persistent binding is consulted ONLY when the curated path yields no
downloadable locator. Acquisition state therefore NEVER silently overrides
curated authority, and a binding that disagrees with an existing curated
locator for the same ``model_id`` is rejected at registration time.

Boundary
========

This module answers only ``model_id -> (source, repository)``. It performs NO
reverse identity lookup: the binding precondition is the FORWARD consistency
check ``resolve_admitted_model_id(source, repository) == model_id`` over a
caller-supplied locator, using the pure derivation/admission function in
:mod:`castlearq.model_identity`, which is imported read-only and never
modified. Identity Admission remains forward-only and is not imported here at
all; ``model_id`` is never computed, mutated or re-derived by this module.
The composed resolver is injected through the existing ``locator_resolver``
seam at the composition root; ``ModelAcquisitionService`` is unchanged.

Lifecycle (B9.96)
=================

Exactly three explicit, owner-invoked mutations::

    bind(model_id, source, repository)     create; never overwrites
    update(model_id, source, repository)   replace; requires an existing binding
    delete(model_id)                       remove; requires an existing binding

Identical re-registration is idempotent and skips the write entirely. Every
rejected operation fails CLOSED before any write and leaves the persisted file
byte-for-byte unchanged. Acquisition itself NEVER creates, updates or deletes
bindings. Cardinality is at most one active binding per ``model_id`` (the
``model_id`` is the record key); multi-locator acquisition is out of scope and
remains a deferred future surface. There is no historical or versioned state
and no automatic rename handling.

Persistence
===========

A standalone JSON file, ``~/.castlearq/acquisition-bindings.json``, NOT hosted
by ``ModelStore`` and never merged with ``identity-admission.json`` or session
state. It stores exactly ``model_id -> {source, repository}``: no provider
metadata, no aliases, no provenance, no revision, no artifact identity and no
runtime state. The root is overridable for tests through
``CASTLEARQ_ACQUISITION_BINDINGS_ROOT`` (a DIRECTORY). Writes follow the
established durable pattern: temporary sibling file, flush, ``os.fsync`` on
the file, ``os.replace``, then ``os.fsync`` on the parent directory, with
deterministic serialization (``indent=2``, ``sort_keys=True``, no timestamps).

Known limitation
================

``read -> modify -> replace`` is NOT transactional — the same accepted
limitation B9.95 recorded for the identity registry. No locking is
introduced. An absent file is an empty registry; a present but malformed or
unsupported file FAILS LOUDLY and is never mistaken for "no binding".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .model_identity import (
    SUPPORTED_DOWNLOAD_SOURCES,
    downloadable_locator,
    resolve_admitted_model_id,
    source_repositories_for_logical_model,
)

__all__ = [
    "ACQUISITION_BINDINGS_ROOT_ENV",
    "AcquisitionBindingError",
    "bind",
    "bindings_path",
    "bindings_root",
    "delete",
    "resolve_acquisition_locator",
    "resolve_binding",
    "update",
]

#: Environment-variable override for the bindings root. Tests only, mirroring
#: ``session.SESSION_ROOT_ENV`` and ``identity_admission``. The value is a
#: DIRECTORY, never a file path.
ACQUISITION_BINDINGS_ROOT_ENV = "CASTLEARQ_ACQUISITION_BINDINGS_ROOT"

#: State directory under which the registry lives: a sibling of
#: ``identity-admission.json`` and ``sessions/``, never a descendant, so the
#: three stores are never conflated.
_BINDINGS_DIRNAME = ".castlearq"

#: The registry filename inside the root.
_BINDINGS_FILENAME = "acquisition-bindings.json"

#: Persisted format version. Any other value is rejected, never guessed.
_SCHEMA_VERSION = 1

#: The only keys permitted inside a stored binding record.
_RECORD_SOURCE = "source"
_RECORD_REPOSITORY = "repository"
_RECORD_FIELDS = {_RECORD_SOURCE, _RECORD_REPOSITORY}

#: Temporary-file suffix, mirroring the ``session.py`` write pattern.
_TEMPORARY_SUFFIX = ".tmp"


class AcquisitionBindingError(Exception):
    """A failure of the acquisition-resolution boundary.

    A boundary data condition, independent from ``SessionError``,
    ``ModelStoreError``, ``IdentityAdmissionError`` and ``AcquisitionError``:
    acquisition resolution owns neither diagnosis sessions, artifact
    manifests, identity records nor the acquisition flow itself.

    It signals a conflicting or duplicate binding, a failed forward identity
    precondition, a curated disagreement, an unsupported source, a missing
    lifecycle target, or malformed registry state. Every case FAILS CLOSED:
    the registry is left byte-for-byte unchanged and no binding is ever
    fabricated, guessed or defaulted.
    """


def bindings_root(
    home: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the bindings root directory (overridable for tests only).

    Mirrors ``identity_admission.registry_root`` exactly: an environment
    override wins when present and non-empty; otherwise the root is
    ``~/.castlearq``. The value is a directory; the filename is applied by
    :func:`bindings_path`.
    """
    environment = os.environ if environ is None else environ
    override = environment.get(ACQUISITION_BINDINGS_ROOT_ENV, "")
    if override:
        return Path(override)
    base = Path.home() if home is None else home
    return base / _BINDINGS_DIRNAME


def bindings_path(root: Path | None = None) -> Path:
    """Return the concrete bindings file inside ``root``."""
    target_root = bindings_root() if root is None else root
    return target_root / _BINDINGS_FILENAME


def _validate_text(value, label: str) -> str:
    """Reject an empty or non-string binding component."""
    if not isinstance(value, str) or not value.strip():
        raise AcquisitionBindingError(f"{label} must be a non-empty string")
    return value


def _parse_bindings(payload: object) -> dict[str, tuple[str, str]]:
    """Validate untrusted registry data into a model_id -> locator mapping.

    Every field is checked explicitly. Anything malformed, incomplete, or
    carrying an unexpected field raises :class:`AcquisitionBindingError`
    rather than being partially trusted. An unknown ``schema_version`` is
    rejected, and is NEVER guessed.
    """
    if not isinstance(payload, dict):
        raise AcquisitionBindingError("bindings data must be a JSON object")

    if "schema_version" not in payload:
        raise AcquisitionBindingError("bindings data has no schema_version")
    version = payload["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise AcquisitionBindingError(
            f"bindings schema_version must be an integer: {version!r}"
        )
    if version != _SCHEMA_VERSION:
        raise AcquisitionBindingError(
            f"unsupported bindings schema version: {version!r}"
        )

    unexpected = set(payload) - {"schema_version", "bindings"}
    if unexpected:
        raise AcquisitionBindingError(
            f"bindings data has unexpected fields: {sorted(unexpected)}"
        )

    bindings = payload.get("bindings")
    if not isinstance(bindings, dict):
        raise AcquisitionBindingError(
            "bindings data must be a JSON object under 'bindings'"
        )

    resolved: dict[str, tuple[str, str]] = {}
    for model_id, record in bindings.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise AcquisitionBindingError(
                f"binding keys must be non-empty strings: {model_id!r}"
            )
        if not isinstance(record, dict):
            raise AcquisitionBindingError(
                f"binding record must be a JSON object: {model_id!r}"
            )
        record_fields = set(record)
        if record_fields != _RECORD_FIELDS:
            raise AcquisitionBindingError(
                f"binding record must contain exactly {sorted(_RECORD_FIELDS)}: "
                f"{model_id!r} has {sorted(record_fields)}"
            )
        source = record[_RECORD_SOURCE]
        repository = record[_RECORD_REPOSITORY]
        if not isinstance(source, str) or not source.strip():
            raise AcquisitionBindingError(
                f"binding record has an invalid source: {model_id!r}"
            )
        if not isinstance(repository, str) or not repository.strip():
            raise AcquisitionBindingError(
                f"binding record has an invalid repository: {model_id!r}"
            )
        resolved[model_id] = (source, repository)
    return resolved


def _load(path: Path) -> dict[str, tuple[str, str]]:
    """Return the persisted bindings, or an empty mapping when absent.

    An absent file is NOT corruption and yields an empty registry. A present
    but unreadable, malformed or unsupported file is corruption and raises:
    silently treating corrupt acquisition state as "no binding" would be
    fail-open and would mask a binding that exists.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise AcquisitionBindingError(
            f"cannot read acquisition bindings: {error}"
        ) from error
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise AcquisitionBindingError(
            f"acquisition bindings are not valid JSON: {error}"
        ) from error
    return _parse_bindings(payload)


def _write(path: Path, bindings: dict[str, tuple[str, str]]) -> None:
    """Persist the bindings atomically and durably.

    Temporary sibling file, flush, ``fsync`` the file, ``os.replace``, then
    ``fsync`` the parent directory so the rename itself survives a crash. The
    sequence mirrors ``identity_admission._write`` (itself mirroring
    ``ModelStore._write_manifest``); ``os.replace`` is atomic on POSIX, so a
    reader never observes a partially written registry.

    Serialization is deterministic (``indent=2``, ``sort_keys=True``): identical
    logical state always produces byte-identical output. No timestamp and no
    generated identifier is persisted, precisely so that determinism holds.
    """
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "bindings": {
            model_id: {_RECORD_SOURCE: source, _RECORD_REPOSITORY: repository}
            for model_id, (source, repository) in bindings.items()
        },
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + _TEMPORARY_SUFFIX)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # Never leave a stray temporary file behind after a failed write.
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    os.replace(temporary, path)

    # Durability of the rename itself requires syncing the containing
    # directory; syncing the file alone does not persist the new name.
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _validate_registration(model_id: str, source: str, repository: str) -> None:
    """Run every registration check BEFORE any registry read or write.

    Validation order (ratified): caller inputs, supported source, forward
    identity consistency, curated compatibility. A rejection here can never
    touch persisted state.
    """
    _validate_text(model_id, "model_id")
    _validate_text(source, "source")
    _validate_text(repository, "repository")

    if source not in SUPPORTED_DOWNLOAD_SOURCES:
        raise AcquisitionBindingError(f"unsupported acquisition source: {source!r}")

    resolved = resolve_admitted_model_id(source, repository)
    if resolved != model_id:
        raise AcquisitionBindingError(
            "forward identity consistency check failed: "
            f"resolve_admitted_model_id({source!r}, {repository!r}) is "
            f"{resolved!r}, not {model_id!r}"
        )

    curated_locators = source_repositories_for_logical_model(model_id)
    if curated_locators and (source, repository) not in curated_locators:
        raise AcquisitionBindingError(
            "curated locator is authoritative and differs: " f"{model_id!r}"
        )


def bind(model_id: str, source: str, repository: str) -> None:
    """Create the active acquisition binding for ``model_id``.

    The binding is created EXPLICITLY; Identity Admission never creates one
    and no value here is inferred by reversing ``(source, repository) ->
    model_id`` — all three values are caller-supplied and validated forward.

    Fails CLOSED, leaving the registry byte-for-byte unchanged, when:
    the forward consistency check fails; the source is unsupported; the
    supplied locator disagrees with a curated locator for this ``model_id``;
    or ``model_id`` already holds a DIFFERENT binding (``bind`` never
    overwrites — ``update`` is the explicit replacement operation).

    Re-registering the identical binding succeeds without changing anything
    and skips the write entirely, so a repeated bind can never perturb the
    file.
    """
    _validate_registration(model_id, source, repository)

    path = bindings_path()
    bindings = _load(path)
    existing = bindings.get(model_id)
    if existing is not None:
        if existing == (source, repository):
            return
        raise AcquisitionBindingError(
            "model already has an active acquisition binding: " f"{model_id!r}"
        )
    bindings[model_id] = (source, repository)
    _write(path, bindings)


def update(model_id: str, source: str, repository: str) -> None:
    """Replace the acquisition binding for an existing ``model_id``.

    The ONLY sanctioned way to change a binding's locator (``bind`` never
    overwrites). Fails CLOSED when no binding exists for ``model_id`` — an
    update never creates state — and re-validates every registration
    precondition (inputs, supported source, forward consistency, curated
    compatibility) before writing. An identical update is an idempotent
    success that skips the write. Changing the locator NEVER changes
    ``model_id``: identity is a different layer and is untouched here.
    """
    _validate_registration(model_id, source, repository)

    path = bindings_path()
    bindings = _load(path)
    existing = bindings.get(model_id)
    if existing is None:
        raise AcquisitionBindingError(
            "no acquisition binding to update: " f"{model_id!r}"
        )
    if existing == (source, repository):
        return
    bindings[model_id] = (source, repository)
    _write(path, bindings)


def delete(model_id: str) -> None:
    """Remove the acquisition binding for ``model_id``.

    Fails CLOSED when no binding exists — a delete never silently succeeds on
    a missing target and never fabricates state. Removal only touches this
    registry: ``model_id``, Identity Admission and curated authority are
    unaffected, because a binding answers "where do we acquire", never "what
    is this model".
    """
    _validate_text(model_id, "model_id")
    path = bindings_path()
    bindings = _load(path)
    if model_id not in bindings:
        raise AcquisitionBindingError(
            "no acquisition binding to delete: " f"{model_id!r}"
        )
    del bindings[model_id]
    _write(path, bindings)


def resolve_binding(model_id: str) -> tuple[str, str] | None:
    """Return the persisted ``(source, repository)`` for ``model_id``, or None.

    A read of this registry ONLY: it never writes, never creates the file and
    never consults curated authority (the composed resolver does that). An
    absent file yields None. A present but malformed or unreadable registry
    FAILS LOUDLY — corruption is never mistaken for "no binding".
    """
    return _load(bindings_path()).get(model_id)


def resolve_acquisition_locator(model_id: str) -> tuple[str, str] | None:
    """The composed acquisition resolver (the ``locator_resolver`` seam).

    The exact ratified D3 resolution order:

    ```text
    1. downloadable_locator(model_id)   — curated, unchanged, authoritative
    2. if it yields a downloadable locator, return it
    3. only otherwise, consult the persistent acquisition binding
    4. defensively re-validate the persisted source against
       SUPPORTED_DOWNLOAD_SOURCES before returning it
    ```

    Deterministic, read-only, and it NEVER mutates binding state, so
    ``acquire()`` cannot create, update or delete a binding through
    resolution. Corruption of the persisted registry raises loudly rather
    than degrading to None. Returning None reproduces the existing
    ``locator_resolver`` contract exactly, so ``ModelAcquisitionService``
    (unchanged) reports the same fail-closed error as before.
    """
    curated = downloadable_locator(model_id)
    if curated is not None:
        return curated
    binding = _load(bindings_path()).get(model_id)
    if binding is None:
        return None
    source, repository = binding
    if source not in SUPPORTED_DOWNLOAD_SOURCES:
        return None
    return binding
