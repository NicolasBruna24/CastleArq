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

"""B9.76.5 tests: ``--json`` for the SHOULD commands.

One envelope, four different domains. The decisive assertions are that the
domains stay separate: ``models`` reports the LEGACY catalog assessment
under its own name and never as a strict evaluation status, ``runtime``
keeps the runtime capability model, ``detect`` keeps hardware detection,
and ``plan`` keeps the download planner's own status vocabulary. UNKNOWN is
never the string ``"Unknown"``, never a silent ``null``, and never an error.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from unittest import mock

from app import main as cli

ENVELOPE_KEYS = {
    "schema",
    "schema_version",
    "command",
    "exit_code",
    "payload",
    "warnings",
    "error",
}

UNKNOWN_NOT_OBSERVED = {
    "value": None,
    "status": "unknown",
    "reason": "not_observed",
}

#: Commands that must keep rejecting ``--json`` (DEFER + serve/chat).
NOT_WIRED = (
    "diagnose",
    "verify",
    "execute",
    "run",
    "download",
    "source",
    "serve",
    "chat",
)

QWEN_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
QWEN_FILENAME = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"


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


def one_json_document(stdout: str) -> dict:
    """Parse ``stdout`` as exactly one JSON document (trailing data fails)."""
    if not stdout.strip():
        raise AssertionError("stdout is empty; JSON mode must print a document")
    document = json.loads(stdout)
    if not isinstance(document, dict):
        raise AssertionError("the document must be a JSON object")
    return document


class _ShouldCase(unittest.TestCase):
    def assert_envelope(self, document, *, command, exit_code):
        self.assertEqual(set(document), ENVELOPE_KEYS)
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], command)
        self.assertEqual(document["exit_code"], exit_code)
        self.assertEqual(document["warnings"], [])
        self.assertIsNone(document["error"])


class DetectJsonTests(_ShouldCase):
    """``detect --json``: hardware detection, never a runtime model."""

    def test_detect_json_is_one_document_with_exit_zero(self):
        human_code, human_out, _ = run_cli("detect")
        json_code, json_out, _ = run_cli("detect", "--json")
        self.assertEqual(human_code, 0)
        self.assertEqual(json_code, human_code)
        self.assertIn("CastleArq", human_out)
        document = one_json_document(json_out)
        self.assert_envelope(document, command="detect", exit_code=0)
        self.assertNotIn("CastleArq", json_out)

    def test_detect_payload_preserves_the_observed_hardware(self):
        _, out, _ = run_cli("detect", "--json")
        _, human_out, _ = run_cli("detect")
        payload = one_json_document(out)["payload"]
        for key in (
            "system",
            "cpu",
            "memory",
            "gpus",
            "runtimes",
            "backends",
            "recommendation",
        ):
            self.assertIn(key, payload)
        # An observed value is a value, and the human report agrees with it.
        for observed in (
            payload["system"]["operating_system"],
            payload["cpu"]["model"],
        ):
            self.assertEqual(observed["status"], "known")
            self.assertIn(observed["value"], human_out)
        self.assertIn("GPU", human_out)

    def test_detect_never_uses_the_string_unknown(self):
        _, out, _ = run_cli("detect", "--json")
        self.assertNotIn('"Unknown"', out)
        payload = one_json_document(out)["payload"]
        for field in (
            payload["system"]["operating_system"],
            payload["system"]["architecture"],
            payload["cpu"]["model"],
            payload["cpu"]["architecture"],
        ):
            self.assertIn(field["status"], ("known", "unknown"))
            if field["status"] == "unknown":
                self.assertEqual(field, UNKNOWN_NOT_OBSERVED)

    def test_detect_gpus_keep_their_own_vocabulary(self):
        _, out, _ = run_cli("detect", "--json")
        payload = one_json_document(out)["payload"]
        for gpu in payload["gpus"]:
            self.assertIn("pci_id", gpu)
            self.assertIn("vram_bytes", gpu)
            self.assertIn("sources", gpu)
            for key in ("name", "vendor", "driver"):
                self.assertIn(gpu[key]["status"], ("known", "unknown"))
            for key in ("pci_id", "vram_bytes", "vram_available_bytes"):
                self.assertIn(gpu[key]["status"], ("known", "unknown"))
                if gpu[key]["status"] == "unknown":
                    self.assertEqual(gpu[key], UNKNOWN_NOT_OBSERVED)
        # A recommendation is a name or a definite absence (null), never an
        # UNKNOWN structure.
        for value in payload["recommendation"].values():
            self.assertTrue(value is None or isinstance(value, str))


class RuntimeJsonTests(_ShouldCase):
    """``runtime --json``: the runtime capability model, unchanged."""

    def test_runtime_json_preserves_the_exit_code(self):
        human_code, human_out, _ = run_cli("runtime")
        json_code, json_out, _ = run_cli("runtime", "--json")
        self.assertEqual(json_code, human_code)
        self.assertIn(human_code, (0, 1))
        self.assertIn("Runtime: llama.cpp", human_out)
        document = one_json_document(json_out)
        self.assertEqual(document["exit_code"], human_code)
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertNotIn("Runtime: llama.cpp", json_out)

    def test_runtime_payload_keeps_the_runtime_model(self):
        _, out, _ = run_cli("runtime", "--json")
        payload = one_json_document(out)["payload"]
        self.assertIn("runtime", payload)
        self.assertIn("capability", payload)
        runtime = payload["runtime"]
        self.assertEqual(runtime["canonical_id"], "llama.cpp")
        # The enum travels as its value, never as its uppercase name.
        self.assertEqual(runtime["availability"], runtime["availability"].lower())
        for key in ("version", "executable_path", "build_identifier"):
            self.assertIn(runtime[key]["status"], ("known", "unknown"))
            if runtime[key]["status"] == "unknown":
                self.assertEqual(runtime[key], UNKNOWN_NOT_OBSERVED)
        capability = payload["capability"]
        if isinstance(capability, dict):
            self.assertIn("supported_formats", capability)
            self.assertIn("supported_backends", capability)

    def test_runtime_capability_absent_is_unknown_not_null(self):
        _, out, _ = run_cli("runtime", "--json")
        capability = one_json_document(out)["payload"]["capability"]
        if not isinstance(capability, dict):
            self.assertEqual(capability, UNKNOWN_NOT_OBSERVED)


class PlanJsonTests(_ShouldCase):
    """``plan --json``: the download planner's own status vocabulary."""

    def test_plan_json_preserves_exit_and_envelope(self):
        human_code, human_out, _ = run_cli("plan", QWEN_REPOSITORY, QWEN_FILENAME)
        json_code, json_out, _ = run_cli(
            "plan", QWEN_REPOSITORY, QWEN_FILENAME, "--json"
        )
        self.assertEqual(json_code, human_code)
        self.assertIn(human_code, (0, 1))
        self.assertIn("CastleArq - Offline download plan", human_out)
        document = one_json_document(json_out)
        self.assertEqual(document["exit_code"], human_code)
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertNotIn("CastleArq - Offline download plan", json_out)

    def test_plan_payload_keeps_the_planner_result(self):
        _, human_out, _ = run_cli("plan", QWEN_REPOSITORY, QWEN_FILENAME)
        _, json_out, _ = run_cli(
            "plan", QWEN_REPOSITORY, QWEN_FILENAME, "--json"
        )
        payload = one_json_document(json_out)["payload"]
        self.assertIn("artifact", payload)
        self.assertIn("plan", payload)
        self.assertEqual(payload["artifact"]["repository"], QWEN_REPOSITORY)
        self.assertEqual(payload["artifact"]["filename"], QWEN_FILENAME)
        # The planner's own status vocabulary, not a compatibility one.
        self.assertIn(
            payload["plan"]["status"],
            ("ready", "already_downloaded", "blocked", "unknown"),
        )
        self.assertIsInstance(payload["plan"]["existing"], bool)
        self.assertIsInstance(payload["plan"]["reasons"], list)
        for reason in payload["plan"]["reasons"]:
            self.assertIn(reason, human_out)

    def test_plan_unknown_is_structured_and_never_an_error(self):
        _, out, _ = run_cli(
            "plan", QWEN_REPOSITORY, QWEN_FILENAME, "--json"
        )
        document = one_json_document(out)
        plan = document["payload"]["plan"]
        # UNKNOWN is a plan status, never an error and never a failure.
        if plan["status"] == "unknown":
            self.assertIsNone(document["error"])
            self.assertNotEqual(document["exit_code"], 1)
        for key in ("destination", "required_bytes", "available_bytes"):
            self.assertIn(plan[key]["status"], ("known", "unknown"))
            if plan[key]["status"] == "unknown":
                self.assertEqual(plan[key], UNKNOWN_NOT_OBSERVED)
        self.assertNotIn('"Unknown"', out)

    def test_plan_error_is_structured_with_exit_one(self):
        human_code, human_out, _ = run_cli("plan", "not/mapped", "model.gguf")
        json_code, json_out, _ = run_cli(
            "plan", "not/mapped", "model.gguf", "--json"
        )
        self.assertEqual(human_code, 1)
        self.assertEqual(json_code, human_code)
        self.assertIn("Plan error:", human_out)
        document = one_json_document(json_out)
        self.assertEqual(document["exit_code"], 1)
        self.assertEqual(document["payload"], {})
        self.assertEqual(document["error"]["kind"], "plan_error")
        self.assertIn("not/mapped", document["error"]["message"])
        # The human line never reaches the JSON stdout.
        self.assertNotIn("Plan error:", json_out)

    def test_plan_usage_error_keeps_exit_two(self):
        human_code, _, _ = run_cli("plan")
        json_code, out, err = run_cli("plan", "--json")
        self.assertEqual(human_code, 2)
        self.assertEqual(json_code, human_code)
        document = one_json_document(out)
        self.assertEqual(document["exit_code"], 2)
        self.assertEqual(document["error"]["kind"], "usage_error")
        self.assertIn("Usage: python3 -m app.main plan", err)


class SurfaceAndParityTests(_ShouldCase):
    """stdout purity, exit parity and DEFER protection for the four."""

    def test_stdout_is_exactly_one_document_for_every_wired_command(self):
        for argv in (
            ("models", "--json"),
            ("runtime", "--json"),
            ("detect", "--json"),
            ("plan", QWEN_REPOSITORY, QWEN_FILENAME, "--json"),
        ):
            with self.subTest(command=argv[0]):
                code, out, _ = run_cli(*argv)
                document = one_json_document(out)
                self.assertEqual(document["command"], argv[0])
                self.assertEqual(document["exit_code"], code)
                self.assertEqual(document["schema"], "castlearq.cli")
                self.assertEqual(document["schema_version"], 1)
                # Human report labels never appear; plain domain values
                # (a backend literally named "CPU") may, and are not text.
                for human_label in (
                    "CastleArq -",
                    "Status: ",
                    "Model ID: ",
                    "Download: ",
                    "Quantization: ",
                    "Destination: ",
                    "Available disk: ",
                    "Existing: ",
                    "Reasons: ",
                    "Reason: ",
                    "Warning: ",
                    "Problem: ",
                    "Launcher: ",
                    "Capabilities:",
                    "  Recommended runtime: ",
                ):
                    self.assertNotIn(human_label, out)

    def test_exit_parity_between_human_and_json(self):
        for argv in (
            ("models",),
            ("runtime",),
            ("detect",),
            ("plan", QWEN_REPOSITORY, QWEN_FILENAME),
            ("plan", "not/mapped", "model.gguf"),
            ("plan",),
        ):
            with self.subTest(command=" ".join(argv)):
                human_code, _, _ = run_cli(*argv)
                json_code, out, _ = run_cli(*argv, "--json")
                self.assertEqual(json_code, human_code)
                self.assertEqual(one_json_document(out)["exit_code"], human_code)

    def test_human_output_is_untouched_for_every_command(self):
        code, out, _ = run_cli("detect")
        self.assertEqual(code, 0)
        self.assertIn("CastleArq", out)
        self.assertIn("System", out)
        self.assertIn("Recommendation", out)

        code, out, _ = run_cli("models")
        self.assertEqual(code, 0)
        self.assertIn("CastleArq - Model recommendations", out)

        code, out, _ = run_cli("plan", QWEN_REPOSITORY, QWEN_FILENAME)
        self.assertEqual(code, 0)
        self.assertIn("CastleArq - Offline download plan", out)
        self.assertIn("  Status: ", out)
        self.assertIn("  Network: offline", out)

    def test_json_stays_rejected_for_deferred_commands(self):
        for command in NOT_WIRED:
            with self.subTest(command=command):
                code, out, err = run_cli(command, "--json")
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn(
                    f"--json is not valid for command '{command}'", err
                )

    def test_wired_commands_are_exactly_the_ratified_set(self):
        self.assertEqual(
            cli._JSON_COMMANDS,
            (
                "compatibility",
                "validate",
                "list",
                "store",
                "import",
                "models",
                "runtime",
                "detect",
                "plan",
            ),
        )


if __name__ == "__main__":
    unittest.main()