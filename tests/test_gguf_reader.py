# Copyright 2026 Nicolas Bruna
"""Tests for the minimal read-only GGUF header reader."""

import struct
import tempfile
import unittest
from pathlib import Path

from app.gguf_reader import GGUFReadError, read_architecture_evidence


def _gguf(entries=(), *, version=3, magic=b"GGUF", truncate=False):
    data = bytearray(magic + struct.pack("<IQQ", version, 0, len(entries)))
    for key, value in entries:
        raw = value.encode("utf-8")
        data.extend(struct.pack("<Q", len(key.encode("utf-8"))))
        data.extend(key.encode("utf-8"))
        data.extend(struct.pack("<I", 8))
        data.extend(struct.pack("<Q", len(raw)))
        data.extend(raw)
    return bytes(data[:-1] if truncate else data)


class GGUFReaderTests(unittest.TestCase):
    def _read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.gguf"
            path.write_bytes(data)
            return read_architecture_evidence(path)

    def test_reads_exact_architecture_with_provenance(self):
        result = self._read(_gguf((("general.architecture", "qwen2"),)))
        self.assertEqual(result.architecture_raw, "qwen2")
        self.assertEqual(result.architecture_provenance, "GGUF general.architecture")

    def test_missing_architecture_is_explicit_none(self):
        result = self._read(_gguf((("general.type", "model"),)))
        self.assertIsNone(result.architecture_raw)
        self.assertFalse(result.present)

    def test_does_not_match_nearby_key(self):
        result = self._read(_gguf((("general.architecture.foo", "qwen2"),)))
        self.assertIsNone(result.architecture_raw)

    def test_reads_target_after_other_metadata(self):
        result = self._read(_gguf((("general.type", "model"),
                                    ("general.architecture", "qwen2"))))
        self.assertEqual(result.architecture_raw, "qwen2")

    def test_invalid_and_truncated_inputs_fail(self):
        with self.assertRaisesRegex(GGUFReadError, "magic"):
            self._read(_gguf(magic=b"NOPE"))
        with self.assertRaisesRegex(GGUFReadError, "truncated"):
            self._read(_gguf((("general.architecture", "qwen2"),), truncate=True))

    def test_unsupported_type_fails_explicitly(self):
        data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
        data.extend(struct.pack("<Q", 3) + b"key")
        data.extend(struct.pack("<I", 99))
        with self.assertRaisesRegex(GGUFReadError, "unsupported"):
            self._read(bytes(data))
