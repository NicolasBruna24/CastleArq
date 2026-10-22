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

"""Focused tests for the SHA-256 parser embedded in `release.yml`.

The release workflow reads expected hashes from the release manifest
(`docs/release/vVERSION-manifest.md`) and writes them to ``expected.sha256``
so that downloaded GitHub Release assets can be verified.

The manifest records TWO sets of digests for the same file names:
- "Original artifacts in ``dist/``" — historical artifacts (always present)
- "New candidate artifacts (this preparation)" — the publication target

The parser MUST select only the candidate section.  The original (buggy)
code used a blind ``re.search`` over the entire document, which always
matched the historical hashes first.

These tests extract the inline Python parser directly from the YAML
workflow (no code duplication) and run it against synthetic manifests
to verify every fail-closed path.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Real digests from docs/release/v0.6.0-manifest.md — used so the test
# stays tied to actual published values.
HISTORICAL_WHL = "c008ad924e2c0d71f45687bd1b3c487999facce7e1e573e08c4dcac0a0124ebc"
HISTORICAL_SDIST = "f3903b134c479923a82fea456ca2210a8deb3a74c715f57247517bc8ff1f6a86"
CANDIDATE_WHL = "cc4bee15656aa5a6da4a81f4b2bce4d40c5a2e29cb42fc5d04dc024ad19c6757"
CANDIDATE_SDIST = "6c2dd2de3bd8dcc1e88e5590e50083062d0b76d86fc3fab081ce8dd7462b09ea"

VERSION = "0.6.0"
WHEEL_NAME = f"castlearq-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"castlearq-{VERSION}.tar.gz"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_parser_code() -> str:
    """Extract the inline Python parser from the release workflow YAML.

    The workflow step contains a bash ``<<'PY' … PY`` heredoc.  This
    function parses the YAML with PyYAML (which strips the common
    block-scalar indentation), then extracts the heredoc body.

    Returns the raw Python source so tests can execute it directly,
    without duplicating the parser logic.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "expected.sha256" in run and "<<'PY'" in run:
                m = re.search(r"<<'PY'\n(.*?)\n\s*PY\s*\n?", run, re.DOTALL)
                if m:
                    return m.group(1)
    raise AssertionError("Could not find the inline Python parser in release.yml")


def _run_parser(
    manifest_text: str, version: str = VERSION
) -> subprocess.CompletedProcess:
    """Run the extracted parser against *manifest_text*.

    The parser code is executed as a subprocess (``python3 -c <code>
    <manifest_path> <version``) so it runs in a clean environment and
    its exit code / stdout / stderr can be inspected just as the real
    workflow would see them.
    """
    code = extract_parser_code()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="-manifest.md", delete=False, encoding="utf-8"
    ) as f:
        f.write(manifest_text)
        manifest_path = f.name
    try:
        return subprocess.run(  # check=False — we inspect returncode manually.
            [sys.executable, "-c", code, manifest_path, version],
            capture_output=True,
            check=False,
            text=True,
        )
    finally:
        os.unlink(manifest_path)


def make_manifest(
    candidate_w: str = CANDIDATE_WHL,
    candidate_s: str = CANDIDATE_SDIST,
    historical_w: str = HISTORICAL_WHL,
    historical_s: str = HISTORICAL_SDIST,
    include_historical: bool = True,
    include_candidate: bool = True,
    candidate_heading: str = "### New candidate artifacts (this preparation)",
    extra_candidate_lines: str = "",
) -> str:
    """Build a synthetic manifest with configurable sections.

    By default the manifest mirrors the real v0.6.0 structure: historical
    hashes in "Original artifacts" followed by candidate hashes in "New
    candidate artifacts (this preparation)".
    """
    parts = [
        "# CastleArq `v0.6.0` — Release Manifest\n\n",
        "## 2. Distribution artifacts\n\n",
    ]

    if include_historical:
        parts.append("### Original artifacts in `dist/`\n\n```text\n")
        parts.append(f"{WHEEL_NAME}\nSHA-256: {historical_w}\n\n")
        parts.append(f"{SDIST_NAME}\nSHA-256: {historical_s}\n")
        parts.append("```\n\n")

    if include_candidate:
        parts.append(candidate_heading + "\n\n```text\n")
        parts.append(f"{WHEEL_NAME}\nSHA-256: {candidate_w}\n\n")
        parts.append(f"{SDIST_NAME}\nSHA-256: {candidate_s}\n")
        if extra_candidate_lines:
            parts.append(extra_candidate_lines)
        parts.append("```\n\n")

    parts.append("## 3. Validation evidence\n\n```\n```\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Extraction guard
# ---------------------------------------------------------------------------


class TestParserExtraction(unittest.TestCase):
    """Verify that the parser is extractable from the workflow YAML."""

    def test_parser_code_extractable(self):
        code = extract_parser_code()
        self.assertTrue(code.strip(), "Extracted parser code must not be empty")

    def test_parser_code_is_valid_python(self):
        code = extract_parser_code()
        compile(code, "<extracted>", "exec")  # raises SyntaxError on failure


# ---------------------------------------------------------------------------
# Core extraction tests
# ---------------------------------------------------------------------------


class TestManifestHashSelection(unittest.TestCase):
    """Verify the parser selects candidate hashes, not historical ones."""

    def test_candidate_hashes_selected_not_historical(self):
        """Historical hashes must never appear when candidates exist."""
        manifest = make_manifest()
        result = _run_parser(manifest)
        self.assertEqual(
            result.returncode, 0,
            f"Parser failed unexpectedly:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn(CANDIDATE_WHL, result.stdout)
        self.assertIn(CANDIDATE_SDIST, result.stdout)
        self.assertNotIn(HISTORICAL_WHL, result.stdout)
        self.assertNotIn(HISTORICAL_SDIST, result.stdout)

    def test_both_candidate_hashes_selected(self):
        """Exactly two lines — one per artifact — both using candidate digests."""
        manifest = make_manifest()
        result = _run_parser(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        self.assertEqual(len(lines), 2, f"Expected 2 lines, got {len(lines)}: {lines}")
        self.assertTrue(any(WHEEL_NAME in l for l in lines))
        self.assertTrue(any(SDIST_NAME in l for l in lines))


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------


class TestParserFailClosed(unittest.TestCase):
    """Verify the parser fails explicitly on malformed or ambiguous manifests."""

    def test_missing_candidate_section_fails(self):
        """Absent candidate section -> exit 1 with 'candidate' in stderr."""
        manifest = make_manifest(include_candidate=False)
        result = _run_parser(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("candidate", result.stderr.lower())

    def test_missing_hash_for_wheel_fails(self):
        """No SHA-256 value for the wheel in candidate section -> fail."""
        manifest = make_manifest()
        manifest = manifest.replace(
            f"SHA-256: {CANDIDATE_WHL}", "SHA-256: ",
        )
        result = _run_parser(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no sha-256", result.stderr.lower())

    def test_malformed_hash_fails(self):
        """A hash that is not 64 hex chars -> 'no SHA-256' error."""
        manifest = make_manifest(candidate_w="not-a-valid-hex-string")
        result = _run_parser(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no sha-256", result.stderr.lower())

    def test_short_hash_fails(self):
        """A 63-char hash (off by one) must fail — no partial matches."""
        short_hash = CANDIDATE_WHL[:-1]
        manifest = make_manifest(candidate_w=short_hash)
        result = _run_parser(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no sha-256", result.stderr.lower())

    def test_duplicate_hashes_in_candidate_section_fails(self):
        """Two SHA-256 values for same artifact in candidate -> fail."""
        extra_line = (
            f"castlearq-0.6.0-py3-none-any.whl\n"
            f"SHA-256: {HISTORICAL_WHL}\n\n"
        )
        manifest = make_manifest(extra_candidate_lines=extra_line)
        result = _run_parser(manifest)
        self.assertNotEqual(result.returncode, 0, "Duplicate must cause failure")
        self.assertIn("multiple", result.stderr.lower())

    def test_version_mismatch_fails(self):
        """Wrong version arg -> filenames don't match -> 'no sha-256' error."""
        manifest = make_manifest()
        result = _run_parser(manifest, version="0.7.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no sha-256", result.stderr.lower())


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestParserOutputFormat(unittest.TestCase):
    """Verify output format compatibility with sha256sum."""

    def test_output_format_is_sha256sum_compatible(self):
        """Each line: '<64-hex>  dist/<filename>' (two spaces, lowercase)."""
        manifest = make_manifest()
        result = _run_parser(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in result.stdout.strip().split("\n"):
            self.assertRegex(
                line,
                r"^[0-9a-f]{64}  dist/castlearq-0.6.0.*$",
                f"Line does not match sha256sum format: {line}",
            )

    def test_hashes_are_lowercased(self):
        """Parser must emit lowercase hex (sha256sum convention)."""
        manifest = make_manifest(
            candidate_w=CANDIDATE_WHL.upper(),
            candidate_s=CANDIDATE_SDIST.upper(),
        )
        result = _run_parser(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(CANDIDATE_WHL, result.stdout)
        self.assertIn(CANDIDATE_SDIST, result.stdout)
        self.assertNotIn(CANDIDATE_WHL.upper(), result.stdout)
        self.assertNotIn(CANDIDATE_SDIST.upper(), result.stdout)


if __name__ == "__main__":
    unittest.main()
