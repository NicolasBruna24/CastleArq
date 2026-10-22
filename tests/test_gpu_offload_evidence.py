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

"""Focused unit tests for the internal GPU offload evidence classifier.

Synthetic strings only; no llama.cpp execution and no model loading.
"""

import unittest

from castlearq.api import run_response_from_execution
from castlearq.execution import ExecutionResult
from castlearq.offload_evidence import (
    SUPPORTED_RUNTIME_VERSION,
    GpuOffloadEvidence,
    OffloadStatus,
    assess_gpu_offload,
)


VERSION = SUPPORTED_RUNTIME_VERSION
FINAL = "load_tensors: offloaded 23/23 layers to GPU"
PARTIAL = "load_tensors: offloaded 12/23 layers to GPU"
INTERMEDIATE = (
    "load_tensors: offloading output layer to GPU\n"
    "load_tensors: offloading 21 repeating layers to GPU"
)


class AssessGpuOffloadTests(unittest.TestCase):
    def test_exact_positive_sample_is_confirmed(self):
        evidence = assess_gpu_offload(
            "out", f"info\n{FINAL}\nmore", 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.CONFIRMED)
        self.assertEqual(evidence.evidence_category, "final_count")
        self.assertEqual(evidence.offloaded_layers, 23)
        self.assertEqual(evidence.total_layers, 23)
        self.assertEqual(evidence.source_stream, "stderr")

    def test_partial_positive_sample_is_confirmed(self):
        evidence = assess_gpu_offload(
            "", PARTIAL, 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.CONFIRMED)
        self.assertEqual(evidence.offloaded_layers, 12)
        self.assertEqual(evidence.total_layers, 23)

    def test_no_final_count_is_unknown(self):
        evidence = assess_gpu_offload(
            "some output", "more output", 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "no_final_count")
        self.assertIsNone(evidence.offloaded_layers)

    def test_intermediate_only_is_unknown(self):
        evidence = assess_gpu_offload(
            "", INTERMEDIATE, 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "no_final_count")

    def test_duplicate_identical_finals_are_confirmed(self):
        evidence = assess_gpu_offload(
            FINAL, f"x\n{FINAL}\n{FINAL}", 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.CONFIRMED)
        self.assertEqual(evidence.offloaded_layers, 23)
        self.assertEqual(evidence.source_stream, "stderr")

    def test_stdout_only_report_records_stdout_stream(self):
        evidence = assess_gpu_offload(
            f"info\n{FINAL}\nmore", "", 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.CONFIRMED)
        self.assertEqual(evidence.source_stream, "stdout")
        self.assertEqual(evidence.offloaded_layers, 23)
        self.assertEqual(evidence.total_layers, 23)

    def test_conflicting_finals_are_unknown(self):
        evidence = assess_gpu_offload(
            FINAL, PARTIAL, 0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category,
                         "conflicting_reports")

    def test_malformed_counts_are_unknown(self):
        for text in (
            "load_tensors: offloaded 24/23 layers to GPU",
            "load_tensors: offloaded 1/0 layers to GPU",
            "load_tensors: offloaded X/23 layers to GPU",
        ):
            with self.subTest(text=text):
                evidence = assess_gpu_offload(
                    "", text, 0, runtime_version=VERSION)
                self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)

    def test_zero_count_stays_unknown(self):
        evidence = assess_gpu_offload(
            "", "load_tensors: offloaded 0/23 layers to GPU",
            0, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "unvalidated_zero")
        self.assertNotEqual(evidence.status, OffloadStatus.NOT_CONFIRMED)

    def test_not_confirmed_never_emitted(self):
        for text in (FINAL, PARTIAL,
                     "load_tensors: offloaded 0/23 layers to GPU", ""):
            evidence = assess_gpu_offload(
                "", text, 0, runtime_version=VERSION)
            self.assertNotEqual(evidence.status,
                                OffloadStatus.NOT_CONFIRMED)

    def test_unknown_and_missing_version_is_unknown(self):
        for version in (None, "", "  ", "bogus", "version: bogus"):
            with self.subTest(version=version):
                evidence = assess_gpu_offload(
                    "", FINAL, 0, runtime_version=version)
                self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
                self.assertEqual(evidence.evidence_category,
                                 "unsupported_version")

    def test_version_prefix_is_accepted(self):
        evidence = assess_gpu_offload(
            "", FINAL, 0, runtime_version=f"version: {VERSION}")
        self.assertEqual(evidence.status, OffloadStatus.CONFIRMED)

    def test_nonzero_exit_is_unknown(self):
        evidence = assess_gpu_offload(
            "", FINAL, 1, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "nonzero_exit")

    def test_timeout_is_unknown(self):
        evidence = assess_gpu_offload(
            "", FINAL, None, timed_out=True, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "timeout")

    def test_launch_failure_is_unknown(self):
        evidence = assess_gpu_offload(
            None, None, None, launch_failed=True,
            runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "launch_failure")

    def test_not_executed_is_unknown(self):
        evidence = assess_gpu_offload(
            None, None, None, not_executed=True,
            runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)
        self.assertEqual(evidence.evidence_category, "not_executed")

    def test_valid_line_with_failure_is_unknown(self):
        evidence = assess_gpu_offload(
            FINAL, FINAL, 2, runtime_version=VERSION)
        self.assertEqual(evidence.status, OffloadStatus.UNKNOWN)

    def test_requested_values_never_prove_gpu_use(self):
        evidence = assess_gpu_offload(
            "", FINAL, 0, runtime_version=VERSION)
        self.assertIsInstance(evidence, GpuOffloadEvidence)
        for forbidden in ("gpu_used", "gpu_offload",
                          "device_utilization"):
            self.assertFalse(hasattr(evidence, forbidden))


class ResultCompatibilityTests(unittest.TestCase):
    def test_existing_constructors_default_to_none(self):
        result = ExecutionResult(True, 0, "out", "err")
        self.assertIsNone(result.offload_evidence)

    def test_public_api_keys_unchanged(self):
        from datetime import datetime, timezone

        from castlearq.execution import ExecutionDiagnostics

        diagnostics = ExecutionDiagnostics(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_seconds=1.0,
            stdout_bytes=3,
            stderr_bytes=0,
            exit_code=0,
            timed_out=False,
            terminated_normally=True,
        )
        result = ExecutionResult(
            True, 0, "out", "",
            diagnostics=diagnostics,
            offload_evidence=assess_gpu_offload(
                "", FINAL, 0, runtime_version=VERSION),
        )
        dto = run_response_from_execution("model", result)
        import dataclasses
        names = sorted(f.name for f in dataclasses.fields(dto))
        self.assertEqual(
            names,
            ["execution", "exit_code", "model_id", "output",
             "runtime_metrics", "warnings"])
        self.assertEqual(
            sorted(dto.execution.keys()),
            ["elapsed_seconds", "stderr_bytes", "stdout_bytes",
             "terminated_normally", "timed_out"])


if __name__ == "__main__":
    unittest.main()

