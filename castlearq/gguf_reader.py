# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License");
"""Minimal read-only GGUF header reader for physical artifact evidence."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

_MAGIC = b"GGUF"
_MAX_U64 = (1 << 64) - 1
_TYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_STRING = 8
_ARRAY = 9


class GGUFReadError(ValueError):
    """The input is not a safely readable GGUF header."""


@dataclass(frozen=True)
class GGUFArchitectureEvidence:
    architecture_raw: str | None
    architecture_provenance: str = "GGUF general.architecture"

    @property
    def present(self) -> bool:
        return self.architecture_raw is not None


class _Reader:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream

    def read(self, size: int) -> bytes:
        if size < 0 or size > _MAX_U64:
            raise GGUFReadError("unsafe GGUF length")
        try:
            data = self.stream.read(size)
        except (OSError, ValueError) as error:
            raise GGUFReadError("GGUF read failed") from error
        if len(data) != size:
            raise GGUFReadError("truncated GGUF")
        return data

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def string(self) -> str:
        size = self.u64()
        if size > 1 << 20:
            raise GGUFReadError("unsafe GGUF string length")
        try:
            return self.read(size).decode("utf-8")
        except UnicodeDecodeError as error:
            raise GGUFReadError("invalid GGUF string") from error

    def value(self, value_type: int) -> object | None:
        if value_type in _TYPE_SIZES:
            return self.read(_TYPE_SIZES[value_type])
        if value_type == _STRING:
            return self.string()
        if value_type == _ARRAY:
            element_type = self.u32()
            count = self.u64()
            if element_type not in _TYPE_SIZES and element_type not in (_STRING, _ARRAY):
                raise GGUFReadError("unsupported GGUF metadata type")
            if count > 1 << 20:
                raise GGUFReadError("unsafe GGUF array length")
            return tuple(self.value(element_type) for _ in range(count))
        raise GGUFReadError("unsupported GGUF metadata type")


def read_architecture_evidence(path: str | Path) -> GGUFArchitectureEvidence:
    """Read only the exact GGUF `general.architecture` string."""
    try:
        with Path(path).open("rb") as stream:
            reader = _Reader(stream)
            if reader.read(4) != _MAGIC:
                raise GGUFReadError("invalid GGUF magic")
            version = reader.u32()
            if version not in (2, 3):
                raise GGUFReadError("unsupported GGUF version")
            reader.u64()
            metadata_count = reader.u64()
            if metadata_count > 1 << 20:
                raise GGUFReadError("unsafe GGUF metadata count")
            found: str | None = None
            for _ in range(metadata_count):
                key = reader.string()
                value_type = reader.u32()
                value = reader.value(value_type)
                if key == "general.architecture":
                    if not isinstance(value, str):
                        raise GGUFReadError("general.architecture is not a string")
                    found = value
            return GGUFArchitectureEvidence(architecture_raw=found)
    except OSError as error:
        raise GGUFReadError("cannot open GGUF") from error
