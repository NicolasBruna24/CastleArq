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

"""Observability v1 contract tests for successful ``POST /v1/run``."""

import json
import unittest
from datetime import datetime, timezone

from castlearq.api import ChatTurnResponseDTO, run_response_from_execution
from castlearq.execution import ExecutionDiagnostics, ExecutionResult
from castlearq.execution import RuntimeMetrics, RuntimeMetricSource


def _diagnostics(**overrides):
    now = datetime.now(timezone.utc)
    fields = {
        "started_at": now,
        "finished_at": now,
        "elapsed_seconds": 12.34,
        "stdout_bytes": 1234,
        "stderr_bytes": 56,
        "exit_code": 0,
        "timed_out": False,
        "terminated_normally": True,
    }
    fields.update(overrides)
    return ExecutionDiagnostics(**fields)


class ObservabilityContractTests(unittest.TestCase):
    def test_full_data_projects_all_fields(self):
        result = ExecutionResult(
            True, 0, "hello", "",
            diagnostics=_diagnostics(),
            runtime_metrics=RuntimeMetrics(
                prompt_tokens=10,
                generated_tokens=20,
                prompt_tokens_per_second=40.5,
                generation_tokens_per_second=18.2,
                load_time_seconds=1.5,
                total_time_seconds=3.5,
                source=RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
            ),
        )
        payload = run_response_from_execution("m", result).to_dict()
        self.assertEqual(payload["model_id"], "m")
        self.assertEqual(payload["output"], "hello")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["execution"]["elapsed_seconds"], 12.34)
        self.assertEqual(payload["execution"]["stdout_bytes"], 1234)
        self.assertEqual(payload["execution"]["stderr_bytes"], 56)
        self.assertFalse(payload["execution"]["timed_out"])
        self.assertTrue(payload["execution"]["terminated_normally"])
        metrics = payload["runtime_metrics"]
        self.assertEqual(metrics["prompt_tokens"], 10)
        self.assertEqual(metrics["generated_tokens"], 20)
        self.assertEqual(metrics["prompt_tokens_per_second"], 40.5)
        self.assertEqual(metrics["generation_tokens_per_second"], 18.2)
        self.assertEqual(metrics["load_time_seconds"], 1.5)
        self.assertEqual(metrics["total_time_seconds"], 3.5)
        self.assertEqual(metrics["source"], "llama_human_output")
        json.dumps(payload)

    def test_partial_metrics_stay_null(self):
        result = ExecutionResult(
            True, 0, "out", "",
            diagnostics=_diagnostics(),
            runtime_metrics=RuntimeMetrics(
                prompt_tokens_per_second=40.5,
                source=RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
            ),
        )
        payload = run_response_from_execution("m", result).to_dict()
        metrics = payload["runtime_metrics"]
        self.assertEqual(metrics["prompt_tokens_per_second"], 40.5)
        self.assertIsNone(metrics["generated_tokens"])
        self.assertIsNone(metrics["prompt_tokens"])
        self.assertIsNone(metrics["generation_tokens_per_second"])
        self.assertIsNone(metrics["load_time_seconds"])
        self.assertIsNone(metrics["total_time_seconds"])

    def test_both_absent_serialize_as_null_without_zeros(self):
        result = ExecutionResult(True, 0, "out", "")
        payload = run_response_from_execution("m", result).to_dict()
        self.assertIn("execution", payload)
        self.assertIn("runtime_metrics", payload)
        self.assertIsNone(payload["execution"])
        self.assertIsNone(payload["runtime_metrics"])
        raw = json.dumps(payload)
        self.assertIn('"execution": null', raw)
        self.assertIn('"runtime_metrics": null', raw)

    def test_allow_list_exposes_no_timestamps_or_internals(self):
        result = ExecutionResult(
            True, 0, "out", "",
            diagnostics=_diagnostics(),
            runtime_metrics=RuntimeMetrics(
                prompt_tokens_per_second=1.0,
                source=RuntimeMetricSource.LLAMA_HUMAN_OUTPUT,
            ),
        )
        payload = run_response_from_execution("m", result).to_dict()
        self.assertEqual(
            sorted(payload["execution"]),
            ["elapsed_seconds", "stderr_bytes", "stdout_bytes",
             "terminated_normally", "timed_out"],
        )
        self.assertEqual(
            sorted(payload["runtime_metrics"]),
            ["generated_tokens", "generation_tokens_per_second",
             "load_time_seconds", "prompt_tokens",
             "prompt_tokens_per_second", "source", "total_time_seconds"],
        )
        flat = json.dumps(payload)
        for forbidden in ("started_at", "finished_at", "argv", "environ",
                          "traceback", "/tmp/", "executable"):
            self.assertNotIn(forbidden, flat)

    def test_success_keeps_legacy_keys_and_adds_only_two(self):
        result = ExecutionResult(
            True, 0, "out", "", warnings=("w1",),
            diagnostics=_diagnostics(),
            runtime_metrics=RuntimeMetrics(
                source=RuntimeMetricSource.UNAVAILABLE,
            ),
        )
        payload = run_response_from_execution("m", result).to_dict()
        self.assertEqual(
            sorted(payload),
            ["execution", "exit_code", "model_id", "output",
             "runtime_metrics", "warnings"],
        )
        self.assertEqual(payload["warnings"], ["w1"])
        self.assertEqual(payload["runtime_metrics"]["source"], "unavailable")

    def test_chat_turn_dto_excludes_new_fields(self):
        payload = ChatTurnResponseDTO(
            session_id="s", response="r", turn_count=1).to_dict()
        self.assertEqual(
            sorted(payload), ["response", "session_id", "turn_count"])

    def test_error_bodies_carry_no_observability_envelope(self):
        from castlearq.api import _admission_denied_body
        from castlearq.api import _evaluation_failed_body
        from castlearq.execute_model import EvaluationAdmission
        admission = EvaluationAdmission(status="evaluated",
                                        verdict="compatible")
        denied = _admission_denied_body(admission)
        self.assertNotIn("execution", denied)
        self.assertNotIn("runtime_metrics", denied)
        failed = _evaluation_failed_body()
        self.assertNotIn("execution", failed)
        self.assertNotIn("runtime_metrics", failed)


if __name__ == "__main__":
    unittest.main()
