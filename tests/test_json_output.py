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

"""Block B9.76.2 tests: shared CLI JSON output layer (contract only)."""

from __future__ import annotations

import ast
import json
import unittest
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from castlearq import json_output as jo
from castlearq.compatibility_domain import CheckStatus, CompatibilityStatus


class EnvelopeTests(unittest.TestCase):
    def test_envelope_defaults_match_the_contract(self):
        envelope = jo.CliEnvelope(command="store", exit_code=0)
        document = envelope.to_dict()
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], "store")
        self.assertEqual(document["exit_code"], 0)
        self.assertEqual(document["payload"], {})
        self.assertEqual(document["warnings"], [])
        self.assertIsNone(document["error"])
        self.assertEqual(
            set(document),
            {"schema", "schema_version", "command", "exit_code",
             "payload", "warnings", "error"})

    def test_envelope_carries_fields_and_is_one_document(self):
        envelope = jo.CliEnvelope(
            command="compatibility",
            exit_code=1,
            payload={"evaluation": {"status": "insufficient_evidence"},
                     "admission": {"status": "evaluated",
                                   "verdict": "compatible"}},
            warnings=("legacy store notice",),
        )
        text = jo.dumps(envelope)
        self.assertTrue(text.startswith("{"))
        document = json.loads(text)
        self.assertEqual(document, envelope.to_dict())
        self.assertEqual(document["warnings"], ["legacy store notice"])
        self.assertEqual(
            document["payload"]["admission"]["verdict"], "compatible")

    def test_schema_fields_cannot_be_overridden(self):
        with self.assertRaises(TypeError):
            jo.CliEnvelope(command="list", exit_code=0, schema="other")
        envelope = jo.CliEnvelope(command="list", exit_code=0)
        with self.assertRaises(AttributeError):
            envelope.schema = "other"  # type: ignore[misc]

    def test_envelope_rejects_empty_command(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(command="", exit_code=0)
        with self.assertRaises(ValueError):
            jo.CliEnvelope(command=7, exit_code=0)  # type: ignore[arg-type]

    def test_envelope_rejects_non_integer_exit_code(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(
                command="list", exit_code="0")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            jo.CliEnvelope(command="list", exit_code=True)

    def test_envelope_rejects_non_dict_payload(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(
                command="list", exit_code=0,
                payload=[])  # type: ignore[arg-type]

    def test_envelope_rejects_non_string_warnings(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(
                command="list", exit_code=0,
                warnings=("ok", 1))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            jo.CliEnvelope(
                command="list", exit_code=0,
                warnings="ok")  # type: ignore[arg-type]

    def test_envelope_rejects_incomplete_error(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(command="compatibility", exit_code=1,
                           error={"kind": "evaluation_error"})

    def test_envelope_rejects_extra_error_keys(self):
        with self.assertRaises(ValueError):
            jo.CliEnvelope(command="compatibility", exit_code=1,
                           error={"kind": "evaluation_error",
                                  "message": "boom",
                                  "warnings": ["x"]})

    def test_warnings_list_is_accepted_and_coerced(self):
        envelope = jo.CliEnvelope(command="list", exit_code=0,
                                  warnings=["note"])
        self.assertEqual(envelope.warnings, ("note",))


class ErrorHelperTests(unittest.TestCase):
    def test_error_shape(self):
        self.assertEqual(
            jo.error("evaluation_error", "boom"),
            {"kind": "evaluation_error", "message": "boom"})

    def test_error_rejects_empty_kind_or_message(self):
        with self.assertRaises(ValueError):
            jo.error("", "boom")
        with self.assertRaises(ValueError):
            jo.error("evaluation_error", "")


class EnumSerializationTests(unittest.TestCase):
    def test_check_status_serializes_through_value(self):
        text = jo.dumps({"status": CheckStatus.PASSED})
        self.assertEqual(json.loads(text), {"status": "passed"})
        self.assertIn('"passed"', text)
        self.assertNotIn('"PASSED"', text)

    def test_compatibility_status_serializes_through_value(self):
        self.assertEqual(
            json.loads(jo.dumps(
                CompatibilityStatus.INSUFFICIENT_EVIDENCE)),
            "insufficient_evidence")

    def test_plain_enum_uses_its_value_too(self):
        class _Plain(Enum):
            MEMBER = "member_value"

        self.assertEqual(jo.serialize(_Plain.MEMBER), "member_value")


class UnknownHelperTests(unittest.TestCase):
    def test_unknown_shape(self):
        self.assertEqual(
            jo.unknown("not_observed"),
            {"value": None, "status": "unknown",
             "reason": "not_observed"})

    def test_unknown_keeps_a_provided_value(self):
        self.assertEqual(
            jo.unknown("no_checksum_declared", value="abc123"),
            {"value": "abc123", "status": "unknown",
             "reason": "no_checksum_declared"})

    def test_unknown_requires_a_reason(self):
        with self.assertRaises(ValueError):
            jo.unknown("")
        with self.assertRaises(ValueError):
            jo.unknown(7)  # type: ignore[arg-type]

    def test_none_is_not_promoted_to_unknown(self):
        self.assertIsNone(jo.serialize(None))
        document = json.loads(jo.dumps({"value": None}))
        self.assertEqual(document, {"value": None})
        self.assertNotIn("status", document)
        self.assertNotIn("reason", document)


class KnownHelperTests(unittest.TestCase):
    def test_known_shape(self):
        self.assertEqual(
            jo.known("example"),
            {"value": "example", "status": "known"})

    def test_known_none_stays_known(self):
        self.assertEqual(
            jo.known(None), {"value": None, "status": "known"})


class RecursiveSerializationTests(unittest.TestCase):
    def test_enum_in_nested_structure(self):
        document = json.loads(jo.dumps(
            {"status": CheckStatus.PASSED,
             "items": [CheckStatus.UNKNOWN]}))
        self.assertEqual(
            document, {"status": "passed", "items": ["unknown"]})

    def test_tuple_becomes_list(self):
        self.assertEqual(
            json.loads(jo.dumps({"a": ("x", "y")})),
            {"a": ["x", "y"]})

    def test_dataclass_projection(self):
        @dataclass(frozen=True)
        class _Sample:
            name: str
            status: CheckStatus

        self.assertEqual(
            jo.serialize(_Sample("s", CheckStatus.FAILED)),
            {"name": "s", "status": "failed"})

    def test_unsupported_type_raises(self):
        with self.assertRaises(TypeError):
            jo.dumps(object())


class DeterminismTests(unittest.TestCase):
    def test_same_document_serializes_identically(self):
        document = {"b": 2, "a": [CheckStatus.PASSED],
                    "nested": {"z": (1, 2), "a": jo.known("x")}}
        self.assertEqual(jo.dumps(document), jo.dumps(document))

    def test_same_envelope_serializes_identically(self):
        envelope = jo.CliEnvelope(
            command="validate", exit_code=0,
            payload={"integrity":
                     jo.unknown("no_checksum_declared")})
        self.assertEqual(jo.dumps(envelope), jo.dumps(envelope))


class LayerBoundaryTests(unittest.TestCase):
    def _source(self) -> str:
        return Path(jo.__file__).read_text(encoding="utf-8")

    def test_layer_does_not_import_the_http_api(self):
        modules: set[str] = set()
        for node in ast.walk(ast.parse(self._source())):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
        self.assertFalse(
            any(name == "api" or name.endswith(".api")
                for name in modules),
            f"HTTP API import found: {sorted(modules)}")

    def test_layer_carries_no_evaluation_policy_concepts(self):
        source = self._source()
        for token in ("ALLOW", "DENY", "ESCALATE",
                      "WAIVER_IDENTITY_UNKNOWN"):
            self.assertNotIn(token, source)
