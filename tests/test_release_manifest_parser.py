# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Direct tests for scripts/release_manifest.py."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_manifest.py"
PYTHON = sys.executable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import release_manifest  # noqa: E402
from unittest.mock import patch

import inspect
import urllib.error


def _run(args, cwd=None):
    """Run the script with the given args, return CompletedProcess."""
    return subprocess.run(
        [PYTHON, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestGenerate(unittest.TestCase):
    """Tests for the generate subcommand."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.manifest = self.root / "manifest.json"
        self.sums = self.root / "SHA256SUMS"
        (self.dist / "a.whl").write_bytes(b"artifact-a")
        (self.dist / "b.tar.gz").write_bytes(b"artifact-b")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_generates_manifest_and_sums(self):
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "generated")
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["package"], "castlearq")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["tag"], "v0.1.0")
        self.assertEqual(manifest["commit"], "a" * 40)
        self.assertEqual(len(manifest["artifacts"]), 2)
        lines = self.sums.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        for line in lines:
            parts = line.split("  ", 1)
            self.assertEqual(len(parts), 2)
            self.assertRegex(parts[0], r"^[0-9a-f]{64}$")

    def test_rejects_empty_artifacts_dir(self):
        empty = self.root / "empty"
        empty.mkdir()
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(empty),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no artifacts", result.stderr)

    def test_rejects_tag_version_mismatch(self):
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.2.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tag mismatch", result.stderr)

    def test_rejects_symlink(self):
        external = self.root / "external.txt"
        external.write_bytes(b"external")
        symlink = self.dist / "linked.whl"
        symlink.symlink_to(external)
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink not allowed", result.stderr)

    def test_rejects_broken_symlink(self):
        broken = self.dist / "broken.whl"
        broken.symlink_to("/tmp/nonexistent_file_xyz")
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_directory_as_artifact(self):
        (self.dist / "subdir").mkdir()
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--patterns", "*",
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)


class TestValidate(unittest.TestCase):
    """Tests for the validate subcommand."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.manifest = self.root / "manifest.json"
        self.sums = self.root / "SHA256SUMS"
        (self.dist / "a.whl").write_bytes(b"artifact-a")
        (self.dist / "b.tar.gz").write_bytes(b"artifact-b")
        result = _run([
            "generate",
            "--version", "0.1.0",
            "--tag", "v0.1.0",
            "--commit", "a" * 40,
            "--artifacts-dir", str(self.dist),
            "--manifest-out", str(self.manifest),
            "--sums-out", str(self.sums),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_valid_manifest_passes(self):
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "valid")

    def test_modified_artifact_fails(self):
        (self.dist / "a.whl").write_bytes(b"MODIFIED")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash mismatch", result.stderr)

    def test_missing_artifact_fails(self):
        (self.dist / "a.whl").unlink()
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing artifact", result.stderr)

    def test_missing_sums_fails(self):
        self.sums.unlink()
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr.lower())

    def test_altered_sums_fails(self):
        lines = self.sums.read_text().strip().split("\n")
        self.sums.write_text("0" * 64 + "  " + lines[0].split("  ", 1)[1] + "\n" + lines[1] + "\n")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash mismatch", result.stderr)

    def test_malformed_sums_line_fails(self):
        self.sums.write_text("badline\n")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed", result.stderr.lower())

    def test_sums_bad_hash_fails(self):
        lines = self.sums.read_text().strip().split("\n")
        self.sums.write_text("g" * 64 + "  " + lines[0].split("  ", 1)[1] + "\n" + lines[1] + "\n")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad sha256", result.stderr.lower())

    def test_sums_duplicate_filename_fails(self):
        lines = self.sums.read_text().strip().split("\n")
        self.sums.write_text(lines[0] + "\n" + lines[0] + "\n")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr.lower())

    def test_sums_empty_filename_fails(self):
        self.sums.write_text("a" * 64 + "  \n")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty filename", result.stderr.lower())

    def test_json_malformed_fails(self):
        self.manifest.write_text("{not valid json")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid manifest", result.stderr.lower())

    def test_invalid_hash_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["artifacts"][0]["sha256"] = "not-a-valid-hash"
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad sha256", result.stderr.lower())

    def test_duplicate_filename_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["artifacts"][1]["filename"] = manifest["artifacts"][0]["filename"]
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr.lower())

    def test_tag_version_mismatch_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["tag"] = "v0.2.0"
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tag mismatch", result.stderr.lower())

    def test_invalid_commit_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["commit"] = "not-a-commit"
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad commit", result.stderr.lower())

    def test_empty_artifacts_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["artifacts"] = []
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad artifacts", result.stderr.lower())

    def test_extra_file_fails(self):
        (self.dist / "extra.txt").write_bytes(b"extra")
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("extra artifact", result.stderr.lower())

    def test_symlink_in_dir_fails(self):
        external = self.root / "external.txt"
        external.write_bytes(b"external")
        (self.dist / "linked.whl").symlink_to(external)
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink not allowed", result.stderr.lower())

    def test_sums_symlink_fails(self):
        external = self.root / "external_sums.txt"
        external.write_text("fake")
        sums_link = self.root / "sums_link"
        sums_link.symlink_to(external)
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(sums_link),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a regular file", result.stderr.lower())

    def test_empty_dir_fails(self):
        empty = self.root / "empty_dist"
        empty.mkdir()
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(empty),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing artifact", result.stderr.lower())

    def test_sums_as_directory_fails(self):
        sums_dir = self.root / "sums_dir"
        sums_dir.mkdir()
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(sums_dir),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a regular file", result.stderr.lower())

    def test_bad_schema_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["schema_version"] = 2
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad schema", result.stderr.lower())

    def test_bad_package_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["package"] = "other"
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad package", result.stderr.lower())

    def test_empty_version_fails(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["version"] = ""
        self.manifest.write_text(json.dumps(manifest))
        result = _run([
            "validate",
            "--manifest", str(self.manifest),
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad version", result.stderr.lower())


class TestParseMarkdown(unittest.TestCase):
    """Tests for the parse_markdown_manifest function."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.wheel_hash = "078ff56056df6a8af30f14eb6de42f53e82b4b1b401ef3afafacb8770bfc21cd"
        self.sdist_hash = "07393e7e04b8f1009aef1f520b60e3ac6dd88540416391c6db6b8a007592b54a"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_manifest(self, content: str) -> Path:
        p = self.root / "v0.6.2-manifest.md"
        p.write_text(content, encoding="utf-8")
        return p

    def _parse(self, path: Path, version="0.6.2", tag="v0.6.2",
               commit="a" * 40):
        from scripts.release_manifest import parse_markdown_manifest
        return parse_markdown_manifest(path, version, tag, commit)

    def test_accepts_manifest_real_v062(self):
        """Manifiesto real de v0.6.2: nombres y hashes en texto normal."""
        manifest = self._write_manifest(f"""# CastleArq `v0.6.2` — Release Manifest

Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
These are the newly built candidates for v0.6.2.

castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}

## 3. Validation evidence
""")
        result = self._parse(manifest)
        self.assertEqual(len(result), 2)
        self.assertIn(f"{self.wheel_hash}  castlearq-0.6.2-py3-none-any.whl", result)
        self.assertIn(f"{self.sdist_hash}  castlearq-0.6.2.tar.gz", result)

    def test_rejects_missing_heading(self):
        manifest = self._write_manifest("Version: 0.6.2\nTag: v0.6.2\nCommit: " + "a" * 40 + "\n")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("candidate artifacts section not found", str(ctx.exception))

    def test_rejects_duplicate_heading(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("ambiguous", str(ctx.exception))

    def test_rejects_hash_without_pending_name(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("sin nombre de artefacto pendiente", str(ctx.exception))

    def test_rejects_unterminated_code_block(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
```
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("sin cierre válido", str(ctx.exception))

    def test_rejects_invalid_close_fence(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
```
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}
~~~
castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("sin cierre válido", str(ctx.exception))

    def test_rejects_name_without_hash_at_section_close(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl

## 3. Validation evidence
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("sin hash al cerrar", str(ctx.exception))

    def test_rejects_name_without_hash_at_eof(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("sin hash al finalizar", str(ctx.exception))

    def test_rejects_duplicate_name(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.sdist_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("duplicado", str(ctx.exception))

    def test_rejects_duplicate_hash(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.wheel_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("hash duplicado", str(ctx.exception))

    def test_rejects_malformed_hash(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: not-a-valid-hash

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("hash mal formado", str(ctx.exception))

    def test_rejects_incomplete_assignment(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}
""")
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("se esperan exactamente los dos artefactos", str(ctx.exception))

    def test_ignores_description_between_name_and_hash(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
castlearq-0.6.2-py3-none-any.whl
This is a descriptive line about the wheel.
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        result = self._parse(manifest)
        self.assertEqual(len(result), 2)

    def test_ignores_code_block_content(self):
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
```
castlearq-0.6.2-py3-none-any.whl
SHA-256: deadbeef
```
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        result = self._parse(manifest)
        self.assertEqual(len(result), 2)

    def test_header_inside_code_block_does_not_close_section(self):
        # Cabecera dentro de un bloque de código que no debe cerrar la sección.
        # El wheel y sdist están fuera del bloque; solo el header está dentro.
        manifest = self._write_manifest(f"""Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
```
### Not a real heading
```
castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
""")
        result = self._parse(manifest)
        self.assertEqual(len(result), 2)


class TestCheckPyPIStatusSignature(unittest.TestCase):
    """Interfaz explícita y consistente de check_pypi_status()."""

    def test_signature_is_explicit(self):
        sig = inspect.signature(release_manifest.check_pypi_status)
        self.assertEqual(tuple(sig.parameters), ("version", "expected_files", "sums_path"))


class TestCheckPyPIStatus(unittest.TestCase):
    """check_pypi_status sin red real: se mockea urllib.request.urlopen."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.sums = self.root / "SHA256SUMS"
        self.version = "0.1.0"
        self.expected_files = {
            f"castlearq-{self.version}-py3-none-any.whl",
            f"castlearq-{self.version}.tar.gz",
        }

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_sums(self, lines):
        self.sums.write_text("\n".join(lines) + "\n")

    def test_rejects_unexpected_names_in_sums(self):
        # SHA256SUMS trae un nombre inesperado: debe abortar, nunca
        # sustituir silenciosamente expected_files por lo leído.
        h = hashlib.sha256(b"x").hexdigest()
        self._write_sums([
            f"{h}  castlearq-{self.version}-py3-none-any.whl",
            f"{h}  nombre-inesperado.whl",
        ])
        result = release_manifest.check_pypi_status(
            self.version, self.expected_files, str(self.sums)
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("do not match", result["error"])

    def test_rejects_missing_name_in_sums(self):
        # Falta uno de los dos nombres esperados: error, no normalización.
        h = hashlib.sha256(b"x").hexdigest()
        self._write_sums([
            f"{h}  castlearq-{self.version}-py3-none-any.whl",
        ])
        result = release_manifest.check_pypi_status(
            self.version, self.expected_files, str(self.sums)
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("do not match", result["error"])

    def test_not_published_without_network(self):
        h = hashlib.sha256(b"x").hexdigest()
        self._write_sums([
            f"{h}  castlearq-{self.version}-py3-none-any.whl",
            f"{h}  castlearq-{self.version}.tar.gz",
        ])

        class _HTTPError(urllib.error.HTTPError):
            def __init__(self):
                self.code = 404

        with patch("urllib.request.urlopen", side_effect=_HTTPError()):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "not_published")

    def test_structural_error_publish_response(self):
        # Respuesta de PyPI con estructura inválida: error estructural,
        # no se trata como transitorio.
        h = hashlib.sha256(b"x").hexdigest()
        self._write_sums([
            f"{h}  castlearq-{self.version}-py3-none-any.whl",
            f"{h}  castlearq-{self.version}.tar.gz",
        ])

        class _Resp:
            def read(self):
                return b'{"urls": "not-a-list"}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=_Resp()):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("urls", result["error"])

    def test_already_published_exact_match(self):
        h = hashlib.sha256(b"x").hexdigest()
        self._write_sums([
            f"{h}  castlearq-{self.version}-py3-none-any.whl",
            f"{h}  castlearq-{self.version}.tar.gz",
        ])

        payload = {
            "urls": [
                {"filename": f"castlearq-{self.version}-py3-none-any.whl",
                 "digests": {"sha256": h}},
                {"filename": f"castlearq-{self.version}.tar.gz",
                 "digests": {"sha256": h}},
            ]
        }

        class _Resp:
            def __init__(self, data):
                self._data = json.dumps(data).encode()

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=_Resp(payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "already_published")

    def test_needs_publish_on_hash_mismatch(self):
        expected_h = hashlib.sha256(b"expected").hexdigest()
        published_h = hashlib.sha256(b"published").hexdigest()
        self._write_sums([
            f"{expected_h}  castlearq-{self.version}-py3-none-any.whl",
            f"{expected_h}  castlearq-{self.version}.tar.gz",
        ])

        payload = {
            "urls": [
                {"filename": f"castlearq-{self.version}-py3-none-any.whl",
                 "digests": {"sha256": published_h}},
                {"filename": f"castlearq-{self.version}.tar.gz",
                 "digests": {"sha256": expected_h}},
            ]
        }

        class _Resp:
            def __init__(self, data):
                self._data = json.dumps(data).encode()

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=_Resp(payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "needs_publish")


class TestVerifyArtifactHashes(unittest.TestCase):
    """verify_artifact_hashes(): hashes locales correctos e incorrectos."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.artifact = self.root / "castlearq-0.1.0-py3-none-any.whl"
        self.artifact.write_bytes(b"artifact-content")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_correct_hash(self):
        digest = hashlib.sha256(b"artifact-content").hexdigest()
        self.assertTrue(release_manifest.verify_artifact_hashes(self.artifact, digest))

    def test_incorrect_hash(self):
        self.assertFalse(release_manifest.verify_artifact_hashes(self.artifact, "0" * 64))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            release_manifest.verify_artifact_hashes(
                self.root / "no-existe.whl", "0" * 64
            )


class TestLoadSha256Sums(unittest.TestCase):
    """Validación compartida de SHA256SUMS (estricta, sin permisividad)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.sums = self.root / "SHA256SUMS"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_ok(self):
        h = hashlib.sha256(b"a").hexdigest()
        self.sums.write_text(f"{h}  castlearq-0.1.0-py3-none-any.whl\n")
        expected, err = release_manifest.load_sha256_sums(str(self.sums))
        self.assertIsNone(err)
        self.assertEqual(expected, {"castlearq-0.1.0-py3-none-any.whl": h})

    def test_load_missing_file(self):
        expected, err = release_manifest.load_sha256_sums(
            str(self.root / "no-existe")
        )
        self.assertIsNone(expected)
        self.assertIn("not found", err)

    def test_load_malformed_line(self):
        self.sums.write_text("not-valid\n")
        expected, err = release_manifest.load_sha256_sums(str(self.sums))
        self.assertIsNone(expected)
        self.assertIsNotNone(err)

    def test_load_bad_digest(self):
        self.sums.write_text("not-a-digest  castlearq-0.1.0-py3-none-any.whl\n")
        expected, err = release_manifest.load_sha256_sums(str(self.sums))
        self.assertIsNone(expected)
        self.assertIsNotNone(err)

    def test_load_duplicate_name(self):
        h = hashlib.sha256(b"a").hexdigest()
        self.sums.write_text(
            f"{h}  castlearq-0.1.0-py3-none-any.whl\n"
            f"{h}  castlearq-0.1.0-py3-none-any.whl\n"
        )
        expected, err = release_manifest.load_sha256_sums(str(self.sums))
        self.assertIsNone(expected)
        self.assertIn("duplicate", err)


class TestCheckPyPIStatusAdditional(unittest.TestCase):
    """Pruebas adicionales para check_pypi_status con respuestas PyPI inválidas."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.sums = self.root / "SHA256SUMS"
        self.version = "0.1.0"
        self.expected_files = {
            f"castlearq-{self.version}-py3-none-any.whl",
            f"castlearq-{self.version}.tar.gz",
        }
        h = hashlib.sha256(b"x").hexdigest()
        self.sums.write_text(
            f"{h}  castlearq-{self.version}-py3-none-any.whl\n"
            f"{h}  castlearq-{self.version}.tar.gz\n"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_resp(self, payload=None, raw=None):
        class _Resp:
            def __init__(self, data):
                self._data = json.dumps(data).encode() if data is not None else raw

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp(payload)

    def test_response_not_dict(self):
        with patch("urllib.request.urlopen", return_value=self._make_resp(raw=b"[1,2,3]")):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("not a JSON object", result["error"])

    def test_duplicate_filenames_in_pypi(self):
        h = hashlib.sha256(b"x").hexdigest()
        payload = {
            "urls": [
                {"filename": f"castlearq-{self.version}-py3-none-any.whl", "digests": {"sha256": h}},
                {"filename": f"castlearq-{self.version}-py3-none-any.whl", "digests": {"sha256": h}},
            ]
        }
        with patch("urllib.request.urlopen", return_value=self._make_resp(payload=payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("duplicate", result["error"])

    def test_empty_filename_in_pypi(self):
        h = hashlib.sha256(b"x").hexdigest()
        payload = {
            "urls": [
                {"filename": "", "digests": {"sha256": h}},
                {"filename": f"castlearq-{self.version}-py3-none-any.whl", "digests": {"sha256": h}},
            ]
        }
        with patch("urllib.request.urlopen", return_value=self._make_resp(payload=payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("empty or invalid filename", result["error"])

    def test_bad_sha256_length_in_pypi(self):
        h = "a" * 63
        payload = {
            "urls": [
                {"filename": f"castlearq-{self.version}-py3-none-any.whl", "digests": {"sha256": h}},
                {"filename": f"castlearq-{self.version}.tar.gz", "digests": {"sha256": hashlib.sha256(b"x").hexdigest()}},
            ]
        }
        with patch("urllib.request.urlopen", return_value=self._make_resp(payload=payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("invalid sha256 digest", result["error"])

    def test_sha256_not_hex_in_pypi(self):
        h = "g" * 64
        payload = {
            "urls": [
                {"filename": f"castlearq-{self.version}-py3-none-any.whl", "digests": {"sha256": h}},
                {"filename": f"castlearq-{self.version}.tar.gz", "digests": {"sha256": hashlib.sha256(b"x").hexdigest()}},
            ]
        }
        with patch("urllib.request.urlopen", return_value=self._make_resp(payload=payload)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("invalid sha256 digest", result["error"])


class TestParseMarkdownIdentity(unittest.TestCase):
    """Pruebas para validación de identidad en parse_markdown_manifest."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.wheel_hash = "078ff56056df6a8af30f14eb6de42f53e82b4b1b401ef3afafacb8770bfc21cd"
        self.sdist_hash = "07393e7e04b8f1009aef1f520b60e3ac6dd88540416391c6db6b8a007592b54a"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_manifest(self, content: str) -> Path:
        p = self.root / "v0.6.2-manifest.md"
        p.write_text(content, encoding="utf-8")
        return p

    def _parse(self, path: Path, version="0.6.2", tag="v0.6.2", commit="a" * 40):
        from scripts.release_manifest import parse_markdown_manifest
        return parse_markdown_manifest(path, version, tag, commit)

    def _base_manifest(self):
        return f"""# CastleArq `v0.6.2` — Release Manifest

Version: 0.6.2
Tag: v0.6.2
Commit: {"a" * 40}

### New candidate artifacts (this preparation)
These are the newly built candidates for v0.6.2.

castlearq-0.6.2-py3-none-any.whl
SHA-256: {self.wheel_hash}

castlearq-0.6.2.tar.gz
SHA-256: {self.sdist_hash}
"""

    def test_rejects_version_mismatch(self):
        content = self._base_manifest().replace("Version: 0.6.2", "Version: 0.9.9")
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("version", str(ctx.exception).lower())

    def test_rejects_tag_mismatch(self):
        content = self._base_manifest().replace("Tag: v0.6.2", "Tag: v0.9.9")
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("tag", str(ctx.exception).lower())

    def test_rejects_commit_mismatch(self):
        content = self._base_manifest().replace("Commit: " + "a" * 40, "Commit: " + "b" * 40)
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("commit", str(ctx.exception).lower())

    def test_accepts_valid_identity(self):
        manifest = self._write_manifest(self._base_manifest())
        result = self._parse(manifest)
        self.assertEqual(len(result), 2)

    def test_rejects_duplicate_version_field(self):
        content = self._base_manifest().replace(
            "Version: 0.6.2\nTag:", "Version: 0.6.2\nVersion: 0.6.2\nTag:"
        )
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_rejects_duplicate_tag_field(self):
        content = self._base_manifest().replace(
            "Tag: v0.6.2\nCommit:", "Tag: v0.6.2\nTag: v0.6.2\nCommit:"
        )
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_rejects_duplicate_commit_field(self):
        content = self._base_manifest().replace(
            "Commit: " + "a" * 40 + "\n\n###",
            "Commit: " + "a" * 40 + "\nCommit: " + "a" * 40 + "\n\n###",
        )
        manifest = self._write_manifest(content)
        with self.assertRaises(ValueError) as ctx:
            self._parse(manifest)
        self.assertIn("duplicate", str(ctx.exception).lower())


class TestValidateAdditional(unittest.TestCase):
    """Pruebas adicionales para validate sin --manifest."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.manifest = self.root / "manifest.json"
        self.sums = self.root / "SHA256SUMS"
        self.wheel = self.dist / "castlearq-0.1.0-py3-none-any.whl"
        self.sdist = self.dist / "castlearq-0.1.0.tar.gz"
        self.wheel.write_bytes(b"artifact-wheel")
        self.sdist.write_bytes(b"artifact-sdist")
        self.wheel_hash = hashlib.sha256(b"artifact-wheel").hexdigest()
        self.sdist_hash = hashlib.sha256(b"artifact-sdist").hexdigest()
        self.sums.write_text(
            f"{self.wheel_hash}  castlearq-0.1.0-py3-none-any.whl\n"
            f"{self.sdist_hash}  castlearq-0.1.0.tar.gz\n"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_validate_without_manifest_passes(self):
        result = _run([
            "validate",
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "valid")

    def test_validate_rejects_unexpected_directory(self):
        (self.dist / "unexpected_dir").mkdir()
        result = _run([
            "validate",
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected directory", result.stderr.lower())

    def test_validate_rejects_missing_artifact(self):
        self.sdist.unlink()
        result = _run([
            "validate",
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing artifact", result.stderr.lower())

    def test_validate_rejects_extra_file(self):
        (self.dist / "extra.txt").write_bytes(b"extra")
        result = _run([
            "validate",
            "--artifacts-dir", str(self.dist),
            "--sums-path", str(self.sums),
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("extra artifact", result.stderr.lower())


class TestCheckPyPIStatusHTTP(unittest.TestCase):
    """Pruebas de comportamiento HTTP en check_pypi_status."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.sums = self.root / "SHA256SUMS"
        self.version = "0.1.0"
        self.expected_files = {
            f"castlearq-{self.version}-py3-none-any.whl",
            f"castlearq-{self.version}.tar.gz",
        }
        h = hashlib.sha256(b"x").hexdigest()
        self.sums.write_text(
            f"{h}  castlearq-{self.version}-py3-none-any.whl\n"
            f"{h}  castlearq-{self.version}.tar.gz\n"
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_http_error(self, code):
        class _HTTPError(urllib.error.HTTPError):
            def __init__(self, code):
                self.code = code
                self.headers = {}
        return _HTTPError(code)

    def test_http_404_returns_not_published(self):
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(404)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "not_published")

    def test_http_5xx_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(500)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("HTTP 500", result["error"])

    def test_http_4xx_non_404_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=self._make_http_error(403)):
            result = release_manifest.check_pypi_status(
                self.version, self.expected_files, str(self.sums)
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("HTTP 403", result["error"])


if __name__ == "__main__":
    unittest.main()
