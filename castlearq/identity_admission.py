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

"""B9.95: persistent, forward-only Identity Admission Registry.

This module persists the binding between an EXTERNAL LOCATOR and the LOGICAL
MODEL IDENTITY that CastleArq admitted for it. It is the persistence half of
Identity Admission; the derivation half lives in :mod:`castlearq.model_identity`
and is consumed here, never modified.

Authority
=========

```text
curated    -> persisted    -> derived
```

- **Curated** (``model_identity.SOURCE_REPOSITORY_TO_MODEL_ID``) remains
  authoritative and is never overwritten.
- **Persisted** is authoritative for any repository already admitted here.
- **Derived** is a fallback computed by the pure identity mechanism; it is
  consulted only when neither a curated nor a persisted identity exists.

A persisted binding is IMMUTABLE. Re-registering the identical triple succeeds
without change; registering a different identity for a known locator is
rejected, and a later change to the derivation policy can never silently
rewrite what was already admitted.

Boundary
========

This module is deliberately FORWARD-ONLY. It exposes exactly two operations::

    lookup(source, repository) -> model_id | None
    register(source, repository, model_id) -> None

There is no reverse lookup, no enumeration, no removal and no update. That is
not an omission: a ``model_id -> repository`` capability would let a derived
identity be resolved by the acquisition gate (``downloadable_locator``) and
would therefore make derived identities downloadable, breaking the invariant
recorded when B9.94 Increment 1 closed. Persisting a reverse index would have
the same effect, so the on-disk format carries none.

Persistence
===========

A standalone JSON file, NOT hosted by ``ModelStore``. ``ModelStore`` is
artifact-addressed (``<root>/<model_id>/<artifact_id>/manifest.json``); placing
a non-artifact registry inside it would change that layout, which B9.94 37.5
forbids. The root-resolution and fail-loud-validation patterns are borrowed
from :mod:`castlearq.session`; the durability sequence is borrowed from
``ModelStore._write_manifest``. Neither module is modified, imported for state,
or otherwise coupled to this one.

Writes are atomic: temporary sibling file, flush, ``os.fsync`` on the file,
``os.replace``, then ``os.fsync`` on the parent directory. ``os.replace`` is
atomic on POSIX, so a reader never observes a partially written registry.

Known limitation
=================

``read -> modify -> replace`` is NOT transactional. Two processes registering
DIFFERENT repositories concurrently can lose one update, because each rewrites
the whole file. This is accepted and documented for B9.95; atomic replacement
protects readers from torn files but provides no isolation. Concurrent writes
to the SAME locator are benign, because identical registrations are idempotent
and identical writes do not conflict. No locking is introduced.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .model_identity import logical_model_id

__all__ = [
    "IdentityAdmissionError",
    "lookup",
    "register",
    "registry_path",
    "registry_root",
]

#: Environment-variable override for the registry root. Tests only, mirroring
#: ``session.SESSION_ROOT_ENV``. The value is a DIRECTORY, never a file path.
IDENTITY_REGISTRY_ROOT_ENV = "CASTLEARQ_IDENTITY_REGISTRY_ROOT"

#: Directory holding the registry under ``~/.castlearq``. A sibling of
#: ``sessions/``, never a descendant, so the two stores are never conflated.
_REGISTRY_DIRNAME = ".castlearq"

#: The registry filename inside the root.
_REGISTRY_FILENAME = "identity-admission.json"

#: Persisted format version. Any other value is rejected, never guessed.
_SCHEMA_VERSION = 1

#: The only key permitted inside a stored identity record.
_RECORD_MODEL_ID = "model_id"

#: Temporary-file suffix, mirroring the ``session.py`` write pattern.
_TEMPORARY_SUFFIX = ".tmp"


class IdentityAdmissionError(Exception):
    """A failure of the persistent identity admission boundary.

    A boundary data condition, independent from ``SessionError``,
    ``ModelStoreError`` and ``DerivedIdentityError``: identity admission owns
    neither diagnosis sessions, artifact manifests, nor derivation errors.

    It signals a conflicting registration, malformed registry state, or an
    unsupported schema version. Every case FAILS CLOSED: the registry is left
    unchanged and no identity is ever fabricated, guessed or defaulted.
    """


def registry_root(
    home: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the registry root directory (overridable for tests only).

    Mirrors ``session.session_root`` exactly: an environment override wins when
    present and non-empty; otherwise the root is ``~/.castlearq``. The value is
    a directory; the filename is applied by :func:`registry_path`.
    """
    environment = os.environ if environ is None else environ
    override = environment.get(IDENTITY_REGISTRY_ROOT_ENV, "")
    if override:
        return Path(override)
    base = Path.home() if home is None else home
    return base / _REGISTRY_DIRNAME


def registry_path(root: Path | None = None) -> Path:
    """Return the concrete registry file inside ``root``."""
    target_root = registry_root() if root is None else root
    return target_root / _REGISTRY_FILENAME


def _validate_locator(value, label: str) -> str:
    """Reject an empty or non-string locator or identity component."""
    if not isinstance(value, str) or not value.strip():
        raise IdentityAdmissionError(f"{label} must be a non-empty string")
    return value


def _locator_key(source: str, repository: str) -> str:
    """Return the deterministic, collision-free composite registry key.

    ``json.dumps([source, repository])`` is used rather than a delimiter join:
    ``source + "/" + repository`` is ambiguous (``("a", "b/c")`` and
    ``("a/b", "c")`` would collide), and so is every other fixed delimiter
    unless that delimiter is excluded from both components. A JSON array is
    unambiguous by construction and stays readable in the stored file.
    """
    return json.dumps([source, repository], separators=(",", ":"))


def _parse_registry(payload: object) -> dict[str, str]:
    """Validate untrusted registry data into a locator -> model_id mapping.

    Every field is checked explicitly. Anything malformed, incomplete, or
    carrying an unexpected field raises :class:`IdentityAdmissionError` rather
    than being partially trusted. An unknown ``schema_version`` is rejected,
    and is NEVER guessed.
    """
    if not isinstance(payload, dict):
        raise IdentityAdmissionError("registry data must be a JSON object")

    if "schema_version" not in payload:
        raise IdentityAdmissionError("registry data has no schema_version")
    version = payload["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise IdentityAdmissionError(
            f"registry schema_version must be an integer: {version!r}"
        )
    if version != _SCHEMA_VERSION:
        raise IdentityAdmissionError(
            f"unsupported registry schema version: {version!r}"
        )

    unexpected = set(payload) - {"schema_version", "identities"}
    if unexpected:
        raise IdentityAdmissionError(
            f"registry data has unexpected fields: {sorted(unexpected)}"
        )

    identities = payload.get("identities")
    if not isinstance(identities, dict):
        raise IdentityAdmissionError("registry identities must be a JSON object")

    resolved: dict[str, str] = {}
    for key, record in identities.items():
        if not isinstance(key, str):
            raise IdentityAdmissionError("registry identity keys must be strings")
        if not isinstance(record, dict):
            raise IdentityAdmissionError(
                f"registry identity record must be a JSON object: {key!r}"
            )
        record_fields = set(record)
        if record_fields != {_RECORD_MODEL_ID}:
            raise IdentityAdmissionError(
                f"registry identity record must contain exactly "
                f"{_RECORD_MODEL_ID!r}: {key!r} has {sorted(record_fields)}"
            )
        model_id = record[_RECORD_MODEL_ID]
        if not isinstance(model_id, str) or not model_id.strip():
            raise IdentityAdmissionError(
                f"registry identity record has an invalid model_id: {key!r}"
            )
        resolved[key] = model_id
    return resolved


def _load(path: Path) -> dict[str, str]:
    """Return the persisted mapping, or an empty one when absent.

    An absent file is NOT corruption and yields an empty registry. A present
    but unreadable, malformed or unsupported file is corruption and raises:
    silently treating corrupt authoritative state as "no identities" would be
    fail-open and would permit silent reassignment of an admitted identity.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise IdentityAdmissionError(
            f"cannot read identity registry: {error}"
        ) from error
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise IdentityAdmissionError(
            f"identity registry is not valid JSON: {error}"
        ) from error
    return _parse_registry(payload)
def _write(path: Path, identities: dict[str, str]) -> None:
    """Persist the mapping atomically and durably.

    Temporary sibling file, flush, ``fsync`` the file, ``os.replace``, then
    ``fsync`` the parent directory so the rename itself survives a crash. The
    sequence mirrors ``ModelStore._write_manifest``; ``os.replace`` is atomic
    on POSIX, so a reader never observes a partially written registry.

    Serialization is deterministic (``indent=2``, ``sort_keys=True``): identical
    logical state always produces byte-identical output. No timestamp and no
    generated identifier is persisted, precisely so that determinism holds.
    """
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "identities": {
            key: {_RECORD_MODEL_ID: model_id}
            for key, model_id in identities.items()
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


def lookup(source: str, repository: str) -> str | None:
    """Return the persisted logical model identity for a locator, or None.

    ``None`` means "not admitted here": either the registry does not exist, or
    the locator is absent from it. Lookup NEVER creates the registry, NEVER
    derives an identity, and NEVER consults or mutates curated authority. It is
    the forward lookup only, by design.

    A registry that EXISTS but is malformed or unreadable raises rather than
    returning ``None``: corruption must never be mistaken for absence, because
    treating it as absence would permit an admitted identity to be re-registered
    under a different value.
    """
    _validate_locator(source, "source")
    _validate_locator(repository, "repository")
    identities = _load(registry_path())
    return identities.get(_locator_key(source, repository))


def register(source: str, repository: str, model_id: str) -> None:
    """Persist an admitted identity binding. The binding is immutable.

    Fails CLOSED, leaving the registry byte-for-byte unchanged, when:

    - the locator already holds a DIFFERENT model identity;
    - the model identity is already bound to a DIFFERENT locator;
    - the model identity conflicts with a curated identity held by another
      locator, which curated authority owns and which is never overwritten.

    Re-registering an identical triple succeeds without changing the logical
    identity and skips the write entirely, so a repeated admission can never
    perturb the file.
    """
    _validate_locator(source, "source")
    _validate_locator(repository, "repository")
    _validate_locator(model_id, "model_id")

    path = registry_path()
    identities = _load(path)
    key = _locator_key(source, repository)

    existing = identities.get(key)
    if existing is not None:
        if existing == model_id:
            return
        raise IdentityAdmissionError(
            "locator is already admitted with a different identity: "
            f"({source}, {repository})"
        )

    # No reverse index is persisted, so uniqueness of a model identity across
    # locators is enforced by a forward scan. This is what prevents two
    # different repositories from collapsing onto one logical model.
    for other_model_id in identities.values():
        if other_model_id == model_id:
            raise IdentityAdmissionError(
                "model identity is already admitted for a different locator: "
                f"{model_id!r}"
            )

    # Curated authority is never overwritten. When the curated table binds this
    # locator to a different identity, curated wins and the registry refuses the
    # divergent proposal instead of persisting a contradiction.
    curated = logical_model_id(source, repository)
    if curated is not None and curated != model_id:
        raise IdentityAdmissionError(
            "curated identity is authoritative and differs: "
            f"({source}, {repository})"
        )

    identities[key] = model_id
    _write(path, identities)