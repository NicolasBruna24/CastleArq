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

"""P1.3 tests: the CLI ``validate`` surface.

These tests freeze the P1.2 contract as implemented:

* SHA-256 present + matching  -> ``integrity: PASSED``, exit 0
* SHA-256 present + differing -> ``integrity: FAILED``, exit 1
* neither integrity identifier -> ``integrity: UNKNOWN``, exit 0
* ``size_bytes`` absent       -> ``size: UNKNOWN``, exit 0
* preflight refusal          -> ``safety: FAILED``, exit 1
* missing model-id           -> exit 2

The decisive assertions distinguish a missing integrity identifier from a
failed integrity or safety check; only the former remains ``UNKNOWN`` and
exits 0.
"""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from castlearq import main as cli
from castlearq.execution import (
    ArtifactExecutionPreflight,
    ArtifactPreflightError,
    PreflightErrorCode,
)
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState, ModelSpec
from castlearq.resolver import ModelArtifactResolver

MODEL_ID = "qwen2.5-coder-7b-instruct"
FILENAME = "qwen2.5-coder-7b-instruct-Q4_K_M.gguf"
CONTENT = b"model"


def artifact(**overrides) -> ArtifactSpec:
    values = {
        "model_id": MODEL_ID,
        "source": "huggingface",
        "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "filename": FILENAME,
        "format": "GGUF",
        "quantization": "Q4_K_M",
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class ValidateCommandTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = ModelStore(Path(self.tempdir.name) / "models")
        self.spec = artifact()
        self.manifest = self.store.save_manifest(self.spec)
        self.directory = self.manifest.parent
        self.final = self.directory / self.spec.filename
        self.model = ModelSpec(
            name="Qwen2.5 Coder 7B Instruct",
            id=MODEL_ID,
            family="qwen",
            context_length=32768,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def run_validate(self, model_id=MODEL_ID, **kwargs):
        """Invoke validate_command against the temporary store."""
        resolver = ModelArtifactResolver(self.store, (self.model,))
        out, err = io.StringIO(), io.StringIO()
        code = cli.validate_command(
            model_id,
            out=out,
            err=err,
            resolver=resolver,
            preflight=ArtifactExecutionPreflight(self.store),
            store=self.store,
            **kwargs,
        )
        return code, out.getvalue(), err.getvalue()

    # --- Case A: SHA-256 present and matching ---------------------------

    def test_matching_sha256_reports_integrity_passed(self):
        self.final.write_bytes(CONTENT)
        self.store.save_manifest(artifact(sha256=hashlib.sha256(CONTENT).hexdigest()))
        code, out, _ = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 0)
        self.assertIn("safety: PASSED", out)
        self.assertIn("integrity: PASSED", out)
        self.assertIn("Artifact state: VERIFIED", out)

    def test_matching_content_id_reports_integrity_passed(self):
        store = ModelStore(Path(self.tempdir.name) / "content-id-models")
        spec = artifact(content_id=hashlib.sha256(CONTENT).hexdigest())
        manifest = store.save_manifest(spec)
        (manifest.parent / FILENAME).write_bytes(CONTENT)
        resolver = ModelArtifactResolver(store, (self.model,))
        out, err = io.StringIO(), io.StringIO()
        code = cli.validate_command(
            MODEL_ID,
            out=out,
            err=err,
            resolver=resolver,
            preflight=ArtifactExecutionPreflight(store),
            store=store,
            quantization="Q4_K_M",
        )
        self.assertEqual(code, 0)
        self.assertIn("integrity: PASSED", out.getvalue())
        self.assertIn("Artifact state: VERIFIED", out.getvalue())

    # --- Case B: SHA-256 present and wrong ------------------------------

    def test_wrong_sha256_is_refused_by_resolution(self):
        """A declared SHA-256 that does not match makes ``inspect_manifest``
        derive ``FAILED``, and the resolver refuses it before preflight runs.
        The command therefore reports a resolution failure and exits 1. This
        is the existing resolver policy, unchanged by ``validate``."""
        self.final.write_bytes(CONTENT)
        self.store.save_manifest(artifact(sha256="0" * 64))
        code, out, err = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 1)
        self.assertIn("Validation error:", err)
        self.assertNotIn("integrity: PASSED", out)

    def test_checksum_mismatch_during_preflight_reports_integrity_failed(self):
        """The content can change between resolution and preflight. When the
        existing preflight detects that with ``CHECKSUM_MISMATCH``, the
        integrity dimension is reported FAILED and the exit code is 1."""
        self.final.write_bytes(CONTENT)
        self.store.save_manifest(
            artifact(sha256=hashlib.sha256(CONTENT).hexdigest())
        )

        class _CorruptingPreflight(ArtifactExecutionPreflight):
            """Real preflight; the file changes between resolve and validate."""

            def validate(self, artifact):
                self.model_store._artifact_directory(
                    artifact
                ).joinpath(artifact.filename).write_bytes(b"tampered")
                return super().validate(artifact)

        resolver = ModelArtifactResolver(self.store, (self.model,))
        out, err = io.StringIO(), io.StringIO()
        code = cli.validate_command(
            MODEL_ID,
            out=out,
            err=err,
            resolver=resolver,
            preflight=_CorruptingPreflight(self.store),
            store=self.store,
            quantization="Q4_K_M",
        )
        self.assertEqual(code, 1)
        self.assertIn("integrity: FAILED", out.getvalue())
        self.assertIn("checksum_mismatch", out.getvalue())
        # Safety passed: the artifact was reachable and openable.
        self.assertIn("safety: PASSED", out.getvalue())

    # --- Case C: SHA-256 absent -----------------------------------------

    def test_absent_sha256_reports_integrity_unknown_and_succeeds(self):
        self.final.write_bytes(CONTENT)
        code, out, _ = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 0)
        self.assertIn("safety: PASSED", out)
        self.assertIn("integrity: UNKNOWN", out)
        # The integrity line must never claim a pass.
        self.assertNotIn("integrity: PASSED", out)
        # ...and it must never claim the checksum was verified.
        self.assertNotIn("verified", out.lower())
        # The absence of evidence is stated explicitly.
        self.assertIn("no SHA-256 is declared in the manifest;", out)
        self.assertIn("no content comparison was performed", out)
        # DOWNLOADED is context, not a validation verdict.
        self.assertIn("Artifact state: DOWNLOADED", out)

    # --- Case D: filesystem / preflight failure -------------------------

    def test_missing_artifact_is_refused_by_resolution(self):
        """No final file: ``inspect_manifest`` derives NOT_DOWNLOADED and the
        existing resolver refuses it. Exit 1, nothing reported as passed."""
        code, out, err = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 1)
        self.assertIn("Validation error:", err)
        self.assertNotIn("safety: PASSED", out)

    def test_partial_only_artifact_is_refused_by_resolution(self):
        """A `.part` file derives DOWNLOADING, which the resolver refuses."""
        (self.directory / f"{FILENAME}.part").write_bytes(b"part")
        code, out, err = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 1)
        self.assertIn("Validation error:", err)
        self.assertNotIn("safety: PASSED", out)

    def test_symlinked_artifact_is_refused_by_resolution(self):
        """A symlinked artifact is an unsafe path; the store refuses it."""
        outside = self.directory / "outside"
        outside.write_bytes(CONTENT)
        self.final.symlink_to(outside)
        code, out, err = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 1)
        self.assertNotIn("safety: PASSED", out)
        self.assertNotIn("integrity: PASSED", out)
        self.assertTrue(err or "safety: FAILED" in out)

    def test_preflight_filesystem_failure_reports_safety_failed(self):
        """The artifact can disappear or become unsafe between resolution and
        preflight. The existing preflight detects that and the safety
        dimension is reported FAILED with its own PreflightErrorCode."""
        self.final.write_bytes(CONTENT)

        class _VanishingPreflight(ArtifactExecutionPreflight):
            """Real preflight; the file is removed after resolution."""

            def validate(self, artifact):
                self.model_store._artifact_directory(
                    artifact
                ).joinpath(artifact.filename).unlink()
                return super().validate(artifact)

        resolver = ModelArtifactResolver(self.store, (self.model,))
        out, err = io.StringIO(), io.StringIO()
        code = cli.validate_command(
            MODEL_ID,
            out=out,
            err=err,
            resolver=resolver,
            preflight=_VanishingPreflight(self.store),
            store=self.store,
            quantization="Q4_K_M",
        )
        self.assertEqual(code, 1)
        self.assertIn("safety: FAILED", out.getvalue())
        self.assertIn("missing_artifact", out.getvalue())
        # Integrity was never established, so it is never claimed.
        self.assertNotIn("integrity: PASSED", out.getvalue())

    def test_non_regular_artifact_is_not_treated_as_missing_integrity(self):
        self.final.write_bytes(CONTENT)

        class _NonRegularPreflight(ArtifactExecutionPreflight):
            def validate(self, artifact):
                path = self.model_store._artifact_directory(artifact) / artifact.filename
                path.unlink()
                os.mkfifo(path)
                return super().validate(artifact)

        resolver = ModelArtifactResolver(self.store, (self.model,))
        out, err = io.StringIO(), io.StringIO()
        code = cli.validate_command(
            MODEL_ID,
            out=out,
            err=err,
            resolver=resolver,
            preflight=_NonRegularPreflight(self.store),
            store=self.store,
            quantization="Q4_K_M",
        )
        self.assertEqual(code, 1)
        self.assertIn("safety: FAILED", out.getvalue())
        self.assertIn("invalid_artifact", out.getvalue())

    # --- Declared size ---------------------------------------------------

    def test_declared_matching_size_reports_passed(self):
        self.final.write_bytes(CONTENT)
        self.store.save_manifest(artifact(size_bytes=len(CONTENT)))
        code, out, _ = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 0)
        self.assertIn("size: PASSED", out)
        self.assertIn("integrity: UNKNOWN", out)

    def test_absent_size_reports_unknown_without_failing(self):
        self.final.write_bytes(CONTENT)
        code, out, _ = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 0)
        self.assertIn("size: UNKNOWN", out)
        self.assertIn("integrity: UNKNOWN", out)
        self.assertNotIn("size: PASSED", out)
        self.assertNotIn("size: FAILED", out)

    def test_declared_wrong_size_is_refused_by_resolution(self):
        self.final.write_bytes(CONTENT)
        self.store.save_manifest(artifact(size_bytes=999))
        code, out, err = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 1)
        self.assertIn("Validation error:", err)
        self.assertNotIn("size: PASSED", out)

    # --- Resolution and usage ---------------------------------------------

    def test_unknown_model_is_a_resolution_failure(self):
        self.final.write_bytes(CONTENT)
        code, _, err = self.run_validate(model_id="does-not-exist")
        self.assertEqual(code, 1)
        self.assertIn("Validation error:", err)

    def test_missing_model_id_is_a_usage_error(self):
        code, _, err = self.run_validate(model_id=None)
        self.assertEqual(code, 2)
        self.assertIn("Usage:", err)

    def test_blank_model_id_is_a_usage_error(self):
        code, _, err = self.run_validate(model_id="   ")
        self.assertEqual(code, 2)
        self.assertIn("Usage:", err)

    # --- Read-only guarantee ----------------------------------------------

    def test_validation_does_not_modify_the_store(self):
        self.final.write_bytes(CONTENT)
        before = {
            path: path.stat().st_mtime_ns
            for path in self.store.root.rglob("*")
            if path.is_file()
        }
        manifest_before = self.manifest.read_bytes()
        self.run_validate(quantization="Q4_K_M")
        after = {
            path: path.stat().st_mtime_ns
            for path in self.store.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(manifest_before, self.manifest.read_bytes())

    # --- Execution of a checksum-less artifact is unaffected -------------

    def test_absent_sha256_reports_unknown_and_preflight_rejects(self):
        """`validate` reports integrity UNKNOWN and exits 0 for an artifact
        without identifiers; the same artifact is rejected by preflight
        (fail-closed) because it cannot be verified for execution.
        """
        self.final.write_bytes(CONTENT)
        code, out, _ = self.run_validate(quantization="Q4_K_M")
        self.assertEqual(code, 0)
        self.assertIn("safety: PASSED", out)
        self.assertIn("integrity: UNKNOWN", out)
        self.assertNotIn("integrity: PASSED", out)
        self.assertNotIn("verified", out.lower())
        self.assertIn("no SHA-256 is declared in the manifest;", out)
        self.assertIn("no content comparison was performed", out)
        self.assertIn("Artifact state: DOWNLOADED", out)

        # Preflight must reject: no integrity identifiers means fail-closed.
        with self.assertRaises(ArtifactPreflightError) as ctx:
            ArtifactExecutionPreflight(self.store).validate(self.spec)
        self.assertEqual(
            ctx.exception.code,
            PreflightErrorCode.MISSING_INTEGRITY_IDENTIFIERS,
        )

        self.assertEqual(
            self.store.inspect_manifest(self.manifest).state,
            ArtifactState.DOWNLOADED,
        )


if __name__ == "__main__":
    unittest.main()
