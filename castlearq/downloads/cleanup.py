
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

"""Explicit, narrowly scoped artifact cleanup operations."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum

from ..model_store import ModelStore, UnsafePathError
from ..models import ArtifactSpec


class CleanupOperation(str, Enum):
    DELETE_PARTIAL = "delete_partial"
    DELETE_FINAL = "delete_final"


@dataclass(frozen=True)
class CleanupResult:
    operation: CleanupOperation
    success: bool
    changed: bool
    reason: str


class ArtifactCleanup:
    """Execute only the explicitly requested artifact-file deletion."""

    def __init__(self, model_store: ModelStore) -> None:
        self.model_store = model_store

    def execute(
        self,
        artifact: ArtifactSpec,
        operation: CleanupOperation,
    ) -> CleanupResult:
        if not isinstance(operation, CleanupOperation):
            raise ValueError("Invalid cleanup operation")

        filename = self.model_store._safe_filename(artifact.filename)
        if filename == "manifest.json":
            raise UnsafePathError("manifest.json is not a cleanup target")
        target_name = (
            f"{filename}.part"
            if operation == CleanupOperation.DELETE_PARTIAL
            else filename
        )
        root_fd = model_fd = artifact_fd = None
        try:
            try:
                root_fd = self.model_store._open_root(create=False)
            except FileNotFoundError:
                return self._unchanged(operation, "Cleanup target does not exist")

            try:
                model_fd = self.model_store._open_directory(
                    root_fd,
                    self.model_store._safe_model_id(artifact.model_id),
                    create=False,
                )
            except FileNotFoundError:
                return self._unchanged(operation, "Cleanup target does not exist")

            try:
                artifact_fd = self.model_store._open_directory(
                    model_fd,
                    artifact.artifact_id,
                    create=False,
                )
            except FileNotFoundError:
                return self._unchanged(operation, "Cleanup target does not exist")

            try:
                mode = os.lstat(target_name, dir_fd=artifact_fd).st_mode
            except FileNotFoundError:
                return self._unchanged(operation, "Cleanup target does not exist")
            if stat.S_ISLNK(mode):
                raise UnsafePathError(f"Symlink is not allowed: {target_name}")
            if stat.S_ISDIR(mode):
                raise UnsafePathError(f"Directories are not cleanup targets: {target_name}")

            os.unlink(target_name, dir_fd=artifact_fd)
            return CleanupResult(operation, True, True, "Cleanup target deleted")
        finally:
            for fd in (artifact_fd, model_fd, root_fd):
                if fd is not None:
                    os.close(fd)

    @staticmethod
    def _unchanged(
        operation: CleanupOperation,
        reason: str,
    ) -> CleanupResult:
        return CleanupResult(operation, True, False, reason)
