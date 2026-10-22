# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Focused tests for requested-target provenance carried inside execution
diagnostics. The new ``requested_backend`` and ``requested_device_argument``
fields are internal-only: they must never leak into the public ``/v1/run``
response shape.

These tests deliberately avoid real inference, downloads, model loading, and
any dependency installation.

They prove:

* A CPU execution records the requested backend and the resolved device
  argument (``none``).
* A Vulkan execution records the selected backend and the resolved device
  argument (``Vulkan0``).
* Missing or unavailable target information stays explicitly absent (``None``),
  never fabricated.
* Existing diagnostics/execution-result construction stays compatible.
* The public ``POST /v1/run`` response keeps exactly its ratified keys.
* Requested device information is never represented as proof of actual GPU
  use.
"""

import json
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from castlearq.api import run_response_from_execution
from castlearq.execution import (
    ExecutableArtifact,
    ExecutionDiagnostics,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTarget,
    RuntimeMetrics,
)
from pathlib import Path
from castlearq.models import ArtifactSpec, ArtifactState
from castlearq.runner import LlamaCppRunner
from castlearq.runtimes import (
    PromptInputMode,
    RuntimeCapability,
)


def capability(executable_path: str) -> RuntimeCapability:
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path=executable_path,
        version="test",
        supported_formats=("GGUF",),
        supported_backends=("CPU", "Vulkan"),
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        compatibility_names=("llama.cpp / llama.app",),
        backend_arguments=(("CPU", "none"), ("Vulkan", "Vulkan0")),
    )


def artifact() -> ArtifactSpec:
    return ArtifactSpec(
        model_id="model",
        source="huggingface",
        repository="owner/repo",
        filename="model.gguf",
        format="GGUF",
        state=ArtifactState.VERIFIED,
    )


class RequestedTargetProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        executable = root / "llama"
        executable.write_text("test executable")
        executable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        model = root / "model.gguf"
        model.write_bytes(b"model")
        self.spec = artifact()
        self.executable_artifact = ExecutableArtifact(
            self.spec, model, False, False
        )
        self.capability = capability(str(executable))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_with(self, target: ExecutionTarget) -> ExecutionResult:
        runner = LlamaCppRunner(
            self.capability,
            Mock(return_value=Mock(returncode=0, stdout=b"o", stderr=b"e")),
        )
        request = ExecutionRequest(self.spec, "hello", target=target)
        return runner.run(self.executable_artifact, target, request)

    # ------------------------------------------------------------------
    # Backward compatibility with existing callers
    # ------------------------------------------------------------------
    def test_execution_target_unchanged_two_field_constructor(self):
        target = ExecutionTarget("llama.cpp CLI", "CPU")
        self.assertEqual(target.runtime, "llama.cpp CLI")
        self.assertEqual(target.backend, "CPU")
        self.assertIsNone(target.requested_backend)
        self.assertIsNone(target.requested_device_argument)

    def test_existing_diagnostics_construction_still_works(self):
        # The ratified execution contract reads ExecutionDiagnostics with the
        # original eight fields; new optional fields must not break it.
        diagnostics = ExecutionDiagnostics(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_seconds=1.0,
            stdout_bytes=1,
            stderr_bytes=1,
            exit_code=0,
            timed_out=False,
            terminated_normally=True,
        )
        self.assertEqual(
            diagnostics,
            ExecutionDiagnostics(
                started_at=diagnostics.started_at,
                finished_at=diagnostics.finished_at,
                elapsed_seconds=1.0,
                stdout_bytes=1,
                stderr_bytes=1,
                exit_code=0,
                timed_out=False,
                terminated_normally=True,
            ),
        )

    def test_existence_result_construction_with_new_diagnostics(self):
        diagnostics = ExecutionDiagnostics(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_seconds=1.0,
            stdout_bytes=1,
            stderr_bytes=1,
            exit_code=0,
            timed_out=False,
            terminated_normally=True,
            requested_backend="CPU",
            requested_device_argument="none",
        )
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="o",
            stderr="e",
            diagnostics=diagnostics,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.diagnostics.requested_backend, "CPU")
        self.assertEqual(result.diagnostics.requested_device_argument, "none")

    # ------------------------------------------------------------------
    # Public /v1/run response shape is unchanged
    # ------------------------------------------------------------------
    def test_public_v1_run_response_shape_unchanged(self):
        diagnostics = ExecutionDiagnostics(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_seconds=1.0,
            stdout_bytes=1,
            stderr_bytes=1,
            exit_code=0,
            timed_out=False,
            terminated_normally=True,
            requested_backend="Vulkan",
            requested_device_argument="Vulkan0",
        )
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="o",
            stderr="e",
            diagnostics=diagnostics,
        )
        payload = run_response_from_execution("model", result).to_dict()

        # Ratified keys only; no runtime_metrics envelope, no new top-level or
        # nested key is introduced by this change.
        self.assertEqual(
            sorted(payload),
            ["execution", "exit_code", "model_id", "output", "runtime_metrics", "warnings"],
        )
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["model_id"], "model")
        self.assertEqual(payload["output"], "o")
        self.assertEqual(payload["warnings"], [])

        # The allow-list projection inside ``execution`` is still the five
        # ratified fields and does not carry the requested-target provenance.
        self.assertEqual(
            sorted(payload["execution"]),
            ["elapsed_seconds", "stderr_bytes", "stdout_bytes", "terminated_normally", "timed_out"],
        )
        self.assertIsNone(payload["runtime_metrics"])

    # ------------------------------------------------------------------
    # Requested device information is never presented as GPU use
    # ------------------------------------------------------------------
    def test_requested_device_information_is_not_gpu_use_proof(self):
        target = ExecutionTarget(
            runtime="llama.cpp CLI",
            backend="Vulkan",
            requested_backend="Vulkan",
            requested_device_argument="Vulkan0",
        )
        result = self.run_with(target)

        # The diagnostics carry *requested* target provenance only. There is no
        # field that asserts actual hardware utilization.
        self.assertEqual(result.diagnostics.requested_device_argument, "Vulkan0")
        self.assertFalse(hasattr(result.diagnostics, "gpu_used"))
        self.assertFalse(hasattr(result.diagnostics, "gpu_offload"))
        self.assertFalse(hasattr(result.diagnostics, "device_utilization"))
        self.assertIsNone(result.runtime_metrics)

        # Same on the public projection: the requested fields never escape the
        # allow-list used by the API projection.
        self.assertNotIn(
            "requested_backend",
            run_response_from_execution("model", result).to_dict()["execution"],
        )

    # ------------------------------------------------------------------
    # CPU execution
    # ------------------------------------------------------------------
    def test_cpu_execution_records_requested_backend_and_device_argument(self):
        target = ExecutionTarget(
            runtime="llama.cpp CLI",
            backend="CPU",
            requested_backend="CPU",
            requested_device_argument="none",
        )
        result = self.run_with(target)

        self.assertTrue(result.success)
        self.assertEqual(result.diagnostics.requested_backend, "CPU")
        self.assertEqual(result.diagnostics.requested_device_argument, "none")

    # ------------------------------------------------------------------
    # Vulkan execution
    # ------------------------------------------------------------------
    def test_vulkan_execution_records_selected_backend_and_resolved_device(self):
        target = ExecutionTarget(
            runtime="llama.cpp CLI",
            backend="Vulkan",
            requested_backend="Vulkan",
            requested_device_argument="Vulkan0",
        )
        result = self.run_with(target)

        self.assertTrue(result.success)
        self.assertEqual(result.diagnostics.requested_backend, "Vulkan")
        self.assertEqual(result.diagnostics.requested_device_argument, "Vulkan0")

    # ------------------------------------------------------------------
    # Explicit absence when target information is unavailable
    # ------------------------------------------------------------------
    def test_missing_target_information_is_explicitly_absent(self):
        # Intentionally WITHOUT the requested provenance fields: the runner
        # must keep them as explicit None rather than inventing a backend.
        target = ExecutionTarget(runtime="llama.cpp CLI", backend="CPU")
        result = self.run_with(target)

        self.assertTrue(result.success)
        self.assertIsNone(result.diagnostics.requested_backend)
        self.assertIsNone(result.diagnostics.requested_device_argument)




