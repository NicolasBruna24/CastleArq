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

"""B9.76.3 tests: ``--json`` wiring for the four MUST commands.

Covers the obligations of the block:

* every JSON document is exactly one ``castlearq.cli`` envelope built by
  ``app.json_output`` (exit parity, envelope fields, stdout purity);
* ``human exit code == json exit code`` for the relevant conditions of each
  command, without changing any existing exit code;
* strict evaluation and admission stay separate in ``compatibility --json``,
  and an operational failure is ``error.kind = "evaluation_error"`` while a
  denial stays a payload;
* ``UNKNOWN`` keeps its strict meaning: explicit unknown structures with
  architecture-backed reasons, never ``"Unknown"`` and never a bare ``null``;
* ``--json`` is rejected for every command outside this block (stderr,
  exit 2 -- parser errors are never JSON);
* the human paths keep their existing output and signatures.

The commands are exercised through ``main()`` with injected argv/streams
(the repository's established CLI harness) and through real subprocesses
where ``payload["exit_code"] == subprocess.returncode`` must hold.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app import main as cli
from app.compatibility_domain import (
    CheckStatus,
    CompatibilityCheck,
    CompatibilityResult,
    CompatibilityStatus,
    EvidenceItem,
    EvidenceKind,
)
from app.evaluate_compatibility import EvaluateModelCompatibilityResult
from app.gguf_reader import GGUFReadError
from app.model_store import ModelStore
from app.models import ArtifactSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL = "b9763-fixture"
CONTENT = b"b9763 fixture content"
DIGEST = hashlib.sha256(CONTENT).hexdigest()

#: The envelope contract ratified in B9.76.1, key for key.
ENVELOPE_KEYS = {
    "schema",
    "schema_version",
    "command",
    "exit_code",
    "payload",
    "warnings",
    "error",
}

#: Policy vocabulary the CLI JSON surface must never carry.
FORBIDDEN_TOKENS = ("ALLOW", "DENY", "ESCALATE", "WAIVER")


def run_cli(*argv):
    """Run ``main()`` with injected argv/streams; return (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["castlearq", *argv]), mock.patch.object(
        sys, "stdout", new=out
    ), mock.patch.object(sys, "stderr", new=err):
        try:
            code = cli.main()
        except SystemExit as exit_error:
            code = exit_error.code if isinstance(exit_error.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def run_subprocess(*argv, home: Path):
    """Run ``python3 -m app.main`` for real, isolated from the user's store."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    return subprocess.run(
        [sys.executable, "-m", "app.main", *argv],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def one_json_document(stdout: str) -> dict:
    """Parse ``stdout`` as exactly one JSON document (trailing data fails)."""
    if not stdout.strip():
        raise AssertionError("stdout is empty; JSON mode must print a document")
    document = json.loads(stdout)
    if not isinstance(document, dict):
        raise AssertionError("the document must be a JSON object")
    return document


def assert_envelope(test: unittest.TestCase, document: dict, *, command, exit_code):
    """Assert the ratified envelope: keys, schema, command and exit code."""
    test.assertEqual(set(document), ENVELOPE_KEYS)
    test.assertEqual(document["schema"], "castlearq.cli")
    test.assertEqual(document["schema_version"], 1)
    test.assertEqual(document["command"], command)
    test.assertEqual(document["exit_code"], exit_code)
    test.assertEqual(document["warnings"], [])


def build_fixture(
    store_root: Path,
    *,
    label: str = LABEL,
    sha256: str | None = DIGEST,
    size_bytes: int | None = len(CONTENT),
    quantization: str = "Unknown",
    filename: str | None = None,
) -> ArtifactSpec:
    """Register one imported-artifact manifest and write its file.

    Follows the same evidence rules the store and resolver already apply:
    ``content_id`` is the computed digest (identity), ``sha256`` is the
    integrity declaration, and the manifest plus the file are what
    ``list_artifacts``/``resolve`` inspect.
    """
    store = ModelStore(store_root)
    spec = ArtifactSpec(
        model_id=store._safe_model_id(label),
        source=None,
        repository=None,
        filename=filename if filename is not None else f"{label}.gguf",
        format="GGUF",
        quantization=quantization,
        size_bytes=size_bytes,
        sha256=sha256,
        content_id=DIGEST,
    )
    manifest = store.save_manifest(spec)
    (manifest.parent / spec.filename).write_bytes(CONTENT)
    return spec


def _check(name: str, status: CheckStatus, *, expected=None, observed=None,
           evidence=()):
    return CompatibilityCheck(
        name=name,
        status=status,
        expected=expected,
        observed=observed,
        evidence=tuple(evidence),
    )


def evaluation_result(
    status: CompatibilityStatus,
    checks,
    *,
    model_id="m1",
    conditions=(),
):
    """Build a real evaluated ``EvaluateModelCompatibilityResult``."""
    strict = CompatibilityResult(
        status=status,
        checks=tuple(checks),
        conditions=tuple(conditions),
    )
    return EvaluateModelCompatibilityResult(
        model_id=model_id,
        artifact=ArtifactSpec(
            model_id=model_id,
            source="huggingface",
            repository="org/repo",
            filename="model.gguf",
            format="GGUF",
            quantization="Q4_K_M",
            size_bytes=123,
            sha256=DIGEST,
        ),
        runtime="llama.cpp CLI",
        capability=None,
        evaluation=SimpleNamespace(result=strict),
        integration=None,
        status="evaluated",
        blocking_outcome=None,
    )


class StoreJsonTests(unittest.TestCase):
    """``store --json``: envelope, read-only, source, exit parity."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = Path(self.tempdir.name) / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.store_root = Path(self.tempdir.name) / "models"
        # The store report names what this machine has installed, so the
        # legacy observation is only meaningful against an isolated home.
        isolated = mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "XDG_DATA_HOME": str(self.home / ".local" / "share"),
                "XDG_CONFIG_HOME": str(self.home / ".config"),
            },
        )
        isolated.start()
        self.addCleanup(isolated.stop)

    def test_subprocess_json_is_one_document_and_exit_code_matches(self):
        proc = run_subprocess(
            "store", "--json", "--model-store", str(self.store_root),
            home=self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        document = one_json_document(proc.stdout)
        assert_envelope(self, document, command="store", exit_code=proc.returncode)
        payload = document["payload"]
        self.assertEqual(payload["path"], str(self.store_root))
        self.assertEqual(payload["source"], "cli")
        self.assertIs(payload["exists"], False)
        self.assertIs(payload["legacy_detected"], False)
        self.assertIs(payload["legacy_used"], False)
        # No human report line survives in JSON stdout.
        self.assertNotIn("Store\n", proc.stdout)
        self.assertNotIn("Legacy detected:", proc.stdout)

    def test_human_and_json_exit_codes_are_identical(self):
        human_code, human_out, _ = run_cli(
            "store", "--model-store", str(self.store_root)
        )
        json_code, json_out, _ = run_cli(
            "store", "--json", "--model-store", str(self.store_root)
        )
        self.assertEqual(human_code, json_code)
        document = one_json_document(json_out)
        assert_envelope(self, document, command="store", exit_code=json_code)
        self.assertIn("Store\n", human_out)
        self.assertNotIn("Store\n", json_out)

    def test_human_report_format_is_unchanged(self):
        code, out, _ = run_cli("store", "--model-store", str(self.store_root))
        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            [
                "Store",
                f"Path: {self.store_root}",
                "Source: cli",
                "Exists: no",
                "Legacy detected: no",
                # An explicit selection is never the legacy compatibility
                # fallback, whatever this machine happens to have installed.
                "Legacy used: no",
            ],
        )

    def test_json_mode_creates_nothing(self):
        run_cli("store", "--json", "--model-store", str(self.store_root))
        self.assertFalse(self.store_root.exists())


class ListJsonTests(unittest.TestCase):
    """``list --json``: same artifacts, same order, explicit unknowns."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = Path(self.tempdir.name) / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.store_root = Path(self.tempdir.name) / "models"
        # zeta sorts after alpha; zeta carries a real quantization.
        build_fixture(
            self.store_root,
            label="b9763-zeta",
            quantization="Q4_K_M",
            filename="b9763-zeta-Q4_K_M.gguf",
        )
        build_fixture(
            self.store_root,
            label="b9763-alpha",
            filename="b9763-alpha-Q8_0.gguf",
        )

    def test_subprocess_json_is_one_document_and_exit_code_matches(self):
        proc = run_subprocess(
            "list", "--json", "--model-store", str(self.store_root),
            home=self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        document = one_json_document(proc.stdout)
        assert_envelope(self, document, command="list", exit_code=proc.returncode)
        payload = document["payload"]
        # A real process sees exactly the same artifacts the human report
        # shows, in the same order.
        self.assertEqual(
            [entry["model_id"] for entry in payload["artifacts"]],
            ["b9763-alpha", "b9763-zeta"],
        )
        self.assertEqual(payload["invalid_artifacts"], [])
        self.assertNotIn("CastleArq - Local models", proc.stdout)

    def test_human_and_json_exit_codes_and_selection_are_identical(self):
        human_code, human_out, _ = run_cli(
            "list", "--model-store", str(self.store_root)
        )
        json_code, json_out, _ = run_cli(
            "list", "--json", "--model-store", str(self.store_root)
        )
        self.assertEqual(human_code, 0)
        self.assertEqual(json_code, human_code)
        self.assertIn("CastleArq - Local models", human_out)
        document = one_json_document(json_out)
        assert_envelope(self, document, command="list", exit_code=json_code)
        self.assertNotIn("CastleArq - Local models", json_out)

        artifacts = document["payload"]["artifacts"]
        self.assertEqual(
            [entry["model_id"] for entry in artifacts],
            ["b9763-alpha", "b9763-zeta"],
        )
        # The human report shows the same artifacts in the same order.
        human_order = [
            line.split("filename: ", 1)[1]
            for line in human_out.splitlines()
            if "filename:" in line
        ]
        self.assertEqual(
            [entry["filename"] for entry in artifacts], human_order
        )

    def test_quantization_unknown_is_never_inferred_from_the_filename(self):
        _, json_out, _ = run_cli(
            "list", "--json", "--model-store", str(self.store_root)
        )
        artifacts = {
            entry["model_id"]: entry
            for entry in one_json_document(json_out)["payload"]["artifacts"]
        }
        alpha = artifacts["b9763-alpha"]
        self.assertEqual(
            alpha["quantization"],
            {"value": None, "status": "unknown", "reason": "not_observed"},
        )
        zeta = artifacts["b9763-zeta"]
        self.assertEqual(
            zeta["quantization"], {"value": "Q4_K_M", "status": "known"}
        )
        # No "Unknown" datum anywhere, and no invented Q-token for alpha.
        self.assertNotIn("Unknown", json_out)

    def test_status_uses_the_enum_value_and_keeps_declared_size(self):
        _, json_out, _ = run_cli(
            "list", "--json", "--model-store", str(self.store_root)
        )
        artifacts = one_json_document(json_out)["payload"]["artifacts"]
        for entry in artifacts:
            self.assertIn(
                entry["status"], ("verified", "downloaded", "not_downloaded")
            )
            self.assertEqual(entry["size_bytes"], len(CONTENT))
            self.assertIsNone(entry["problem"])


class ValidateJsonTests(unittest.TestCase):
    """``validate --json``: checks, explicit UNKNOWN reasons, exit parity."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = Path(self.tempdir.name) / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.full_root = Path(self.tempdir.name) / "full"
        self.bare_root = Path(self.tempdir.name) / "bare"
        self.empty_root = Path(self.tempdir.name) / "empty"
        build_fixture(self.full_root)
        build_fixture(self.bare_root, sha256=None, size_bytes=None)

    def test_subprocess_json_is_one_document_and_exit_code_matches(self):
        proc = run_subprocess(
            "validate", LABEL, "--json", "--model-store", str(self.full_root),
            home=self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        document = one_json_document(proc.stdout)
        assert_envelope(
            self, document, command="validate", exit_code=proc.returncode
        )
        self.assertIsNone(document["error"])

    def test_success_parity_payload_and_stdout_purity(self):
        human = run_cli("validate", LABEL, "--model-store", str(self.full_root))
        json_run = run_cli(
            "validate", LABEL, "--json", "--model-store", str(self.full_root)
        )
        self.assertEqual(human[0], 0)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="validate", exit_code=json_run[0])
        payload = document["payload"]
        self.assertEqual(
            payload["checks"],
            {"safety": "passed", "size": "passed", "integrity": "passed"},
        )
        self.assertEqual(
            payload["declared_size"], {"value": len(CONTENT), "status": "known"}
        )
        self.assertEqual(
            payload["declared_sha256"], {"value": DIGEST, "status": "known"}
        )
        self.assertEqual(payload["state"], "verified")
        self.assertIsNone(payload["problem"])
        self.assertIsNone(document["error"])
        # The human report header did not leak into JSON stdout.
        header = f"{LABEL} / {LABEL}.gguf"
        self.assertIn(header, human[1])
        self.assertNotIn(header, json_run[1])
        self.assertNotIn("Artifact state:", json_run[1])
        self.assertNotIn("integrity: PASSED", json_run[1])

    def test_unknown_validation_is_exit_zero_and_not_an_error(self):
        human = run_cli("validate", LABEL, "--model-store", str(self.bare_root))
        json_run = run_cli(
            "validate", LABEL, "--json", "--model-store", str(self.bare_root)
        )
        self.assertEqual(human[0], 0)
        self.assertEqual(json_run[0], human[0])
        self.assertIn("integrity: UNKNOWN", human[1])
        self.assertIn("size: UNKNOWN", human[1])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="validate", exit_code=0)
        payload = document["payload"]
        self.assertEqual(payload["checks"]["safety"], "passed")
        self.assertEqual(payload["checks"]["size"], "unknown")
        self.assertEqual(payload["checks"]["integrity"], "unknown")
        self.assertEqual(
            payload["declared_sha256"],
            {"value": None, "status": "unknown", "reason": "no_checksum_declared"},
        )
        self.assertEqual(
            payload["declared_size"],
            {"value": None, "status": "unknown", "reason": "no_size_declared"},
        )
        self.assertIsNone(payload["problem"])
        self.assertIsNone(document["error"])
        # UNKNOWN is never serialized as the datum "Unknown".
        self.assertNotIn("Unknown", json_run[1])

    def test_resolution_failure_is_structured_with_exit_one(self):
        human = run_cli(
            "validate", "b9763-missing", "--model-store", str(self.empty_root)
        )
        json_run = run_cli(
            "validate", "b9763-missing", "--json",
            "--model-store", str(self.empty_root),
        )
        self.assertEqual(human[0], 1)
        self.assertEqual(json_run[0], human[0])
        self.assertIn("Validation error:", human[2])
        self.assertIn("Validation error:", json_run[2])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="validate", exit_code=1)
        self.assertEqual(document["payload"], {})
        self.assertEqual(document["error"]["kind"], "validation_error")

    def test_missing_model_id_keeps_exit_two(self):
        human = run_cli("validate")
        json_run = run_cli("validate", "--json")
        self.assertEqual(human[0], 2)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="validate", exit_code=2)
        self.assertEqual(document["error"]["kind"], "usage_error")
        self.assertIn("Usage: python3 -m app.main validate <model-id>", human[2])

    def test_human_unknown_report_is_unchanged(self):
        code, out, _ = run_cli(
            "validate", LABEL, "--model-store", str(self.bare_root)
        )
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(f"{LABEL} / {LABEL}.gguf\n"))
        self.assertIn("  safety: PASSED", out)
        self.assertIn("  size: UNKNOWN", out)
        self.assertIn("  integrity: UNKNOWN", out)
        self.assertIn("    no SHA-256 is declared in the manifest;", out)
        self.assertIn("    no size is declared in the manifest;", out)
        self.assertIn("    no content comparison was performed", out)
        self.assertIn("Artifact state:", out)


class CompatibilityJsonTests(unittest.TestCase):
    """``compatibility --json``: evaluation vs admission, errors, parity."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = Path(self.tempdir.name) / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.store_root = Path(self.tempdir.name) / "models"

    def _run(self, *, result=None, side_effect=None, json_mode=False):
        """Run the command through ``main()`` with a patched use case."""
        argv = ["compatibility", "m1", "--model-store", str(self.store_root)]
        if json_mode:
            argv.append("--json")
        if side_effect is not None:
            patched = mock.patch(
                "app.main.evaluate_model_compatibility", side_effect=side_effect
            )
        else:
            patched = mock.patch(
                "app.main.evaluate_model_compatibility", return_value=result
            )
        with patched:
            return run_cli(*argv)

    def test_admitted_case_exit_parity_and_evaluation_admission_separation(self):
        result = evaluation_result(
            CompatibilityStatus.COMPATIBLE,
            [
                _check(
                    "artifact format support",
                    CheckStatus.PASSED,
                    expected="gguf",
                    observed="gguf",
                    evidence=[
                        EvidenceItem(
                            source="artifact.format",
                            value="gguf",
                            kind=EvidenceKind.OBSERVED,
                        )
                    ],
                )
            ],
        )
        human = self._run(result=result)
        json_run = self._run(result=result, json_mode=True)
        self.assertEqual(human[0], 0)
        self.assertEqual(json_run[0], human[0])
        self.assertIn("Compatibility evaluation", human[1])

        document = one_json_document(json_run[1])
        assert_envelope(
            self, document, command="compatibility", exit_code=json_run[0]
        )
        payload = document["payload"]
        self.assertEqual(set(payload), {"evaluation", "admission"})
        evaluation = payload["evaluation"]
        self.assertEqual(evaluation["status"], "evaluated")
        self.assertEqual(evaluation["verdict"], "compatible")
        self.assertEqual(evaluation["model_id"], "m1")
        self.assertEqual(evaluation["runtime"], "llama.cpp CLI")
        check = evaluation["checks"][0]
        self.assertEqual(check["status"], "passed")
        self.assertEqual(check["evidence"][0]["kind"], "observed")
        self.assertEqual(
            payload["admission"],
            {"status": "evaluated", "verdict": "compatible"},
        )
        self.assertIsNone(document["error"])
        # Content identity and integrity stay separate keys on the artifact.
        artifact = evaluation["artifact"]
        self.assertEqual(artifact["sha256"], DIGEST)
        self.assertIsNone(artifact["content_id"])
        # No human report line and no policy vocabulary in JSON stdout.
        self.assertNotIn("Compatibility evaluation", json_run[1])
        for token in FORBIDDEN_TOKENS:
            self.assertNotIn(token, json_run[1])
        self.assertNotIn("evaluation_policy", json_run[1])

    def test_insufficient_evidence_with_permitting_admission_exits_zero(self):
        result = evaluation_result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [
                _check("runtime artifact support", CheckStatus.UNKNOWN),
                _check("runtime backend support", CheckStatus.UNKNOWN),
            ],
        )
        human = self._run(result=result)
        json_run = self._run(result=result, json_mode=True)
        self.assertEqual(human[0], 0)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=0)
        evaluation = document["payload"]["evaluation"]
        admission = document["payload"]["admission"]
        # Both truths are observable at the same time; UNKNOWN is not an
        # error and does not become exit 1 while admission permits.
        self.assertEqual(evaluation["verdict"], "insufficient_evidence")
        self.assertEqual(
            [check["status"] for check in evaluation["checks"]],
            ["unknown", "unknown"],
        )
        self.assertEqual(
            admission, {"status": "evaluated", "verdict": "compatible"}
        )
        self.assertIsNone(document["error"])

    def test_insufficient_evidence_with_a_real_failure_is_denied(self):
        result = evaluation_result(
            CompatibilityStatus.INSUFFICIENT_EVIDENCE,
            [
                _check(
                    "model architecture support",
                    CheckStatus.FAILED,
                    expected="llama",
                    observed="qwen2",
                ),
                _check("runtime artifact support", CheckStatus.UNKNOWN),
            ],
        )
        human = self._run(result=result)
        json_run = self._run(result=result, json_mode=True)
        self.assertEqual(human[0], 1)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=1)
        # A denial is a payload, never an error object.
        self.assertIsNone(document["error"])
        self.assertEqual(
            document["payload"]["admission"],
            {"status": "evaluated", "verdict": "insufficient_evidence"},
        )
        statuses = [
            check["status"]
            for check in document["payload"]["evaluation"]["checks"]
        ]
        self.assertEqual(statuses, ["failed", "unknown"])

    def test_incompatible_denial_is_payload_not_error(self):
        result = evaluation_result(
            CompatibilityStatus.INCOMPATIBLE,
            [
                _check(
                    "model architecture support",
                    CheckStatus.FAILED,
                    expected="llama",
                    observed="qwen2",
                )
            ],
        )
        human = self._run(result=result)
        json_run = self._run(result=result, json_mode=True)
        self.assertEqual(human[0], 1)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=1)
        self.assertIsNone(document["error"])
        self.assertEqual(document["payload"]["evaluation"]["verdict"], "incompatible")
        self.assertEqual(
            document["payload"]["admission"],
            {"status": "evaluated", "verdict": "incompatible"},
        )

    def test_evaluation_error_is_structured_not_a_verdict(self):
        human = self._run(side_effect=GGUFReadError("truncated header"))
        json_run = self._run(
            side_effect=GGUFReadError("truncated header"), json_mode=True
        )
        self.assertEqual(human[0], 1)
        self.assertEqual(json_run[0], human[0])
        self.assertIn(
            "Compatibility evaluation error: GGUFReadError: truncated header",
            human[2],
        )
        # The JSON run keeps the same stderr diagnostics...
        self.assertIn(
            "Compatibility evaluation error: GGUFReadError: truncated header",
            json_run[2],
        )
        # ...and the only stdout content is the structured envelope.
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=1)
        self.assertEqual(document["payload"], {})
        self.assertEqual(document["error"]["kind"], "evaluation_error")
        self.assertIn("truncated header", document["error"]["message"])

    def test_blocked_evaluation_is_a_payload_with_a_blocked_admission(self):
        blocked = EvaluateModelCompatibilityResult(
            model_id="m1",
            artifact=None,
            runtime="llama.cpp CLI",
            capability=None,
            evaluation=None,
            integration=None,
            status="blocked",
            blocking_outcome="Runtime is not available: llama.cpp CLI",
        )
        human = self._run(result=blocked)
        json_run = self._run(result=blocked, json_mode=True)
        self.assertEqual(human[0], 1)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=1)
        evaluation = document["payload"]["evaluation"]
        self.assertEqual(evaluation["status"], "blocked")
        self.assertIsNone(evaluation["verdict"])
        self.assertEqual(evaluation["checks"], [])
        self.assertEqual(
            evaluation["blocking_outcome"],
            "Runtime is not available: llama.cpp CLI",
        )
        self.assertEqual(
            document["payload"]["admission"],
            {"status": "blocked", "verdict": None},
        )
        self.assertIsNone(document["error"])

    def test_missing_model_id_keeps_exit_two(self):
        human = run_cli("compatibility")
        json_run = run_cli("compatibility", "--json")
        self.assertEqual(human[0], 2)
        self.assertEqual(json_run[0], human[0])
        document = one_json_document(json_run[1])
        assert_envelope(self, document, command="compatibility", exit_code=2)
        self.assertEqual(document["error"]["kind"], "usage_error")

    def test_subprocess_human_and_json_return_the_same_code(self):
        # A real (unpatched) run: whatever this machine decides -- admitted,
        # denied, blocked or an operational evaluation error -- the JSON run
        # must return the human code and carry it in the envelope.
        build_fixture(self.store_root)
        human = run_subprocess(
            "compatibility", LABEL, "--model-store", str(self.store_root),
            home=self.home,
        )
        json_run = run_subprocess(
            "compatibility", LABEL, "--json", "--model-store",
            str(self.store_root), home=self.home,
        )
        self.assertEqual(json_run.returncode, human.returncode)
        document = one_json_document(json_run.stdout)
        assert_envelope(
            self, document, command="compatibility", exit_code=json_run.returncode
        )
        self.assertNotIn("Compatibility evaluation", json_run.stdout)
        if document["error"] is None:
            self.assertEqual(set(document["payload"]), {"evaluation", "admission"})
        else:
            self.assertEqual(document["error"]["kind"], "evaluation_error")
            self.assertEqual(document["payload"], {})
        # stderr is diagnostics only, never a second document.
        self.assertNotIn('"schema"', json_run.stderr)


class JsonFlagSurfaceTests(unittest.TestCase):
    """``--json`` belongs to the four MUST commands and nowhere else."""

    NOT_WIRED = (
        "models",
        "runtime",
        "detect",
        "plan",
        "diagnose",
        "verify",
        "execute",
        "run",
        "download",
        "source",
        # ``import`` joined this surface in B9.76.4.
        "serve",
        "chat",
    )

    def test_json_is_rejected_for_every_other_command(self):
        for command in self.NOT_WIRED:
            with self.subTest(command=command):
                code, out, err = run_cli(command, "--json")
                self.assertEqual(code, 2, command)
                self.assertEqual(out, "", command)
                self.assertIn(
                    f"--json is not valid for command '{command}'", err
                )

    def test_unknown_command_with_json_is_still_an_argparse_error(self):
        code, out, err = run_cli("frobnicate", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("invalid choice", err)

    def test_help_documents_the_option_and_the_wired_commands(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("--json", out)
        self.assertIn("compatibility, validate, list and", out)

    def test_import_json_reservation_is_released_in_b9764(self):
        # B9.76.3 deliberately left ``import --json`` unwired; B9.76.4 wires
        # it. The flag itself is accepted now, so what used to be an argparse
        # rejection is the command's own usage envelope (exit 2, unchanged).
        code, out, err = run_cli("import", "--json")
        self.assertEqual(code, 2)
        self.assertNotIn("--json is not valid", err)
        document = one_json_document(out)
        assert_envelope(self, document, command="import", exit_code=2)
        self.assertEqual(document["error"]["kind"], "usage_error")


class LayerBoundaryTests(unittest.TestCase):
    """Serialization belongs to ``app.json_output``, not to the commands."""

    #: The command handlers this block had to touch. None of them may
    #: serialize JSON: they build data and the shared layer serializes it.
    CLI_MODULES = (
        "main.py",
        "compatibility.py",
        "validation_report.py",
        "resolver.py",
    )

    @staticmethod
    def _path(name: str) -> Path:
        return REPO_ROOT / "app" / name

    @staticmethod
    def _json_dumps_sites(source: str) -> list[tuple[str, int]]:
        """Return ``(enclosing function, line)`` for every ``json.dumps`` call."""
        sites: list[tuple[str, int]] = []

        def visit(node, owner: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visit(child, child.name)
                    continue
                function = getattr(child, "func", None)
                if (
                    isinstance(child, ast.Call)
                    and isinstance(function, ast.Attribute)
                    and function.attr == "dumps"
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "json"
                ):
                    sites.append((owner, child.lineno))
                visit(child, owner)

        visit(ast.parse(source), "<module>")
        return sites

    def test_no_command_module_serializes_json_on_its_own(self):
        for name in self.CLI_MODULES:
            with self.subTest(module=name):
                sites = self._json_dumps_sites(
                    self._path(name).read_text(encoding="utf-8")
                )
                self.assertEqual(sites, [], f"{name} serializes JSON on its own")

    def test_model_store_keeps_only_its_preexisting_manifest_writer(self):
        # ``app/model_store.py`` serializes a MANIFEST to disk (B9.74), which
        # predates the JSON surface and is not a CLI output serializer. The
        # point of the boundary is that B9.76.3 adds no second one.
        sites = self._json_dumps_sites(
            self._path("model_store.py").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [owner for owner, _ in sites], ["_write_manifest"]
        )

    def test_main_serializes_through_the_shared_layer(self):
        source = self._path("main.py").read_text(encoding="utf-8")
        self.assertIn("from . import json_output", source)
        self.assertIn("json_output.CliEnvelope", source)
        self.assertIn("json_output.dumps", source)
        self.assertNotIn("evaluation_policy", source)


if __name__ == "__main__":
    unittest.main()