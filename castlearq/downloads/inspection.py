
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

"""Read-only inspection of local artifact filesystem state."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum

from ..model_store import ModelStore, UnsafePathError
from ..models import ArtifactSpec


class ArtifactFilesystemState(str, Enum):
    CLEAN = "clean"
    PARTIAL = "partial"
    FINAL_EXISTS = "final_exists"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class ArtifactFilesystemInspection:
    final_exists: bool
    partial_exists: bool
    state: ArtifactFilesystemState


class ArtifactFilesystemInspector:
    """Inspect artifact and partial paths without creating or modifying them."""

    def __init__(self, model_store: ModelStore) -> None:
        self.model_store = model_store

    def inspect(self, artifact: ArtifactSpec) -> ArtifactFilesystemInspection:
        filename = self.model_store._safe_filename(artifact.filename)
        root_fd = None
        model_fd = None
        artifact_fd = None
        try:
            try:
                root_fd = self.model_store._open_root(create=False)
            except FileNotFoundError:
                return self._result(False, False)

            try:
                model_fd = self.model_store._open_directory(
                    root_fd,
                    self.model_store._safe_model_id(artifact.model_id),
                    create=False,
                )
            except FileNotFoundError:
                return self._result(False, False)

            try:
                artifact_fd = self.model_store._open_directory(
                    model_fd,
                    artifact.artifact_id,
                    create=False,
                )
            except FileNotFoundError:
                return self._result(False, False)

            final_exists = self._safe_file_exists(filename, artifact_fd)
            partial_exists = self._safe_file_exists(f"{filename}.part", artifact_fd)
            return self._result(final_exists, partial_exists)
        finally:
            for fd in (artifact_fd, model_fd, root_fd):
                if fd is not None:
                    os.close(fd)

    @staticmethod
    def _safe_file_exists(name: str, directory_fd: int) -> bool:
        try:
            mode = os.lstat(name, dir_fd=directory_fd).st_mode
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(mode):
            raise UnsafePathError(f"Symlink is not allowed: {name}")
        return True

    @staticmethod
    def _result(
        final_exists: bool, partial_exists: bool
    ) -> ArtifactFilesystemInspection:
        if final_exists and partial_exists:
            state = ArtifactFilesystemState.INCONSISTENT
        elif final_exists:
            state = ArtifactFilesystemState.FINAL_EXISTS
        elif partial_exists:
            state = ArtifactFilesystemState.PARTIAL
        else:
            state = ArtifactFilesystemState.CLEAN
        return ArtifactFilesystemInspection(final_exists, partial_exists, state)
