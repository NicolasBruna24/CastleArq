"""Explicit, deterministic normalization of legacy model manifests.

Legacy manifests persisted the source repository inside ``model_id``. This
module rewrites only the persisted identity, using the explicit mapping in
:mod:`app.model_identity`, and renames the model directory so the artifact
stays discoverable by the store, preflight and downloader. The artifact file
itself (its bytes, size, SHA-256, filename and ``artifact_id``) is never
modified. The migration is idempotent: running it again changes nothing.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .model_identity import logical_model_id
from .model_store import ModelStore


class MigrationAction(str, Enum):
    UNCHANGED = "unchanged"
    MIGRATED = "migrated"
    UNMAPPED = "unmapped"
    CONFLICT = "conflict"
    INVALID = "invalid"


@dataclass(frozen=True)
class MigrationRecord:
    model_directory: str
    action: MigrationAction
    detail: str = ""


@dataclass(frozen=True)
class MigrationReport:
    records: tuple[MigrationRecord, ...]

    @property
    def migrated(self) -> int:
        return sum(
            1 for record in self.records if record.action is MigrationAction.MIGRATED
        )

    @property
    def unchanged(self) -> int:
        return sum(
            1 for record in self.records if record.action is MigrationAction.UNCHANGED
        )


def migrate_model_store(store: ModelStore) -> MigrationReport:
    """Normalize every legacy manifest in the store. Idempotent."""
    if not store.root.exists():
        return MigrationReport(())
    records: list[MigrationRecord] = []
    root_fd = store._open_root(create=False)
    try:
        for name in sorted(os.listdir(root_fd)):
            if not stat.S_ISDIR(os.lstat(name, dir_fd=root_fd).st_mode):
                continue
            records.extend(_migrate_model_directory(store, root_fd, name))
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return MigrationReport(tuple(records))


def _migrate_model_directory(
    store: ModelStore, root_fd: int, model_dir_name: str
) -> list[MigrationRecord]:
    records: list[MigrationRecord] = []
    model_fd = os.open(
        model_dir_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
    )
    try:
        for entry in sorted(os.listdir(model_fd)):
            if not stat.S_ISDIR(os.lstat(entry, dir_fd=model_fd).st_mode):
                continue
            artifact_fd = os.open(
                entry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=model_fd
            )
            try:
                record = _migrate_manifest(
                    store, root_fd, model_dir_name, artifact_fd
                )
            finally:
                os.close(artifact_fd)
            records.append(record)
    finally:
        os.close(model_fd)
    return records

def _migrate_manifest(
    store: ModelStore, root_fd: int, model_dir_name: str, artifact_fd: int
) -> MigrationRecord:
    try:
        payload = _read_manifest(artifact_fd)
        old_model_id = payload["model_id"]
        source = payload["source"]
        repository = payload["repository"]
        if not all(
            isinstance(value, str) and value
            for value in (old_model_id, source, repository)
        ):
            raise ValueError("invalid identity fields")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return MigrationRecord(model_dir_name, MigrationAction.INVALID)

    target_model_id = logical_model_id(source, repository)
    if target_model_id is None:
        return MigrationRecord(
            model_dir_name,
            MigrationAction.UNMAPPED,
            f"no mapping for ({source}, {repository})",
        )

    expected_dir_name = store._safe_model_id(target_model_id)
    already_identified = old_model_id == target_model_id
    already_placed = model_dir_name == expected_dir_name
    if already_identified and already_placed:
        return MigrationRecord(model_dir_name, MigrationAction.UNCHANGED)

    if not already_placed:
        try:
            os.lstat(expected_dir_name, dir_fd=root_fd)
        except FileNotFoundError:
            pass
        else:
            return MigrationRecord(
                model_dir_name,
                MigrationAction.CONFLICT,
                f"target directory already exists: {expected_dir_name}",
            )

    if not already_identified:
        _rewrite_manifest(payload, target_model_id, artifact_fd)

    if not already_placed:
        os.rename(
            model_dir_name,
            expected_dir_name,
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )

    return MigrationRecord(
        expected_dir_name,
        MigrationAction.MIGRATED,
        f"{old_model_id} -> {target_model_id}",
    )


def _read_manifest(artifact_fd: int) -> dict:
    fd = os.open("manifest.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=artifact_fd)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        return json.loads(stream.read())


def _rewrite_manifest(payload: dict, model_id: str, artifact_fd: int) -> None:
    updated = dict(payload)
    updated["model_id"] = model_id
    temporary_name = "manifest.json.migration.part"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(temporary_name, flags, 0o600, dir_fd=artifact_fd)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(updated, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            os.unlink(temporary_name, dir_fd=artifact_fd)
        except OSError:
            pass
        raise
    os.replace(
        temporary_name,
        "manifest.json",
        src_dir_fd=artifact_fd,
        dst_dir_fd=artifact_fd,
    )
    os.fsync(artifact_fd)

