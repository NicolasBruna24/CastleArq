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
        self.assertIn("sums mismatch", result.stderr)

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
        self.assertIn("unexpected files", result.stderr.lower())

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


if __name__ == "__main__":
    unittest.main()
