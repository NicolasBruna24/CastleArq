# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Application tests for the bounded SFT + LoRA training use case.

Every collaborator is a double: no model trains, no ML dependency is
required, and no network or GPU is touched. The runner is always a fake;
the optional CPU smoke test lives in ``test_training_cpu_smoke.py``.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from castlearq.training import (
    TrainingDependencies,
    TrainingErrorCode,
    TrainingPreparationError,
    TrainingRequest,
    train_adapter_model,
    validate_training_request,
)


def _write_checkpoint(directory: Path, *, gguf: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(
        json.dumps({"model_type": "test-lm"}), encoding="utf-8"
    )
    if gguf:
        (directory / "model.gguf").write_bytes(b"GGUF-fake")
    else:
        (directory / "model.safetensors").write_bytes(b"fake-weights")
    return directory


def _write_dataset(path: Path, rows: int = 3) -> Path:
    with path.open("w", encoding="utf-8") as stream:
        for index in range(rows):
            stream.write(
                json.dumps({"text": f"training example {index} text"}) + "\n"
            )
    return path


class _FakeRunner:
    """Records call order and writes a fake adapter into staging."""

    def __init__(self, calls: list, *, fail: Exception | None = None) -> None:
        self.calls = calls
        self.fail = fail

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        staging = kwargs["staging_dir"]
        (staging / "adapter_model.safetensors").write_bytes(b"fake-adapter")
        (staging / "adapter_config.json").write_text("{}", encoding="utf-8")
        from castlearq.training_runner import RunnerOutcome

        return RunnerOutcome(
            files=("adapter_config.json", "adapter_model.safetensors"),
            steps_completed=kwargs["max_steps"],
            final_loss=5.0,
        )


class _Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.checkpoint = _write_checkpoint(self.root / "base")
        self.dataset = _write_dataset(self.root / "data.jsonl")

    def _request(self, **overrides):
        base = dict(
            base_model_dir=str(self.checkpoint),
            dataset_path=str(self.dataset),
            output_dir=str(self.root / "adapter-out"),
            max_steps=2,
            lora_rank=4,
            lora_alpha=8,
        )
        base.update(overrides)
        return TrainingRequest(**base)


class HappyPathTests(_Case):
    def test_success_publishes_adapter_with_metadata(self):
        calls: list = []
        result = train_adapter_model(
            self._request(),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.steps_completed, 2)
        self.assertEqual(result.final_loss, 5.0)
        self.assertEqual(
            result.admission_path, "local_directory_validation"
        )
        out = Path(result.output_dir or "")
        self.assertTrue((out / "adapter_model.safetensors").exists())
        self.assertTrue((out / "training_metadata.json").exists())
        metadata = json.loads(
            (out / "training_metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["base_model_dir"], str(self.checkpoint))
        self.assertEqual(metadata["lora_rank"], 4)
        # An injected runner predating device evidence serializes as null.
        self.assertIsNone(metadata["selected_device"])
        self.assertIsNone(metadata["effective_device"])
        # The result carries the same absence without inventing a device.
        self.assertIsNone(result.selected_device)
        self.assertIsNone(result.effective_device)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_steps"], 2)
        self.assertEqual(calls[0]["lora_rank"], 4)
        self.assertEqual(calls[0]["lora_alpha"], 8)

    def test_runner_device_evidence_reaches_result(self):
        calls: list = []

        class _DeviceRunner(_FakeRunner):
            def run(self, **kwargs):
                outcome = super().run(**kwargs)
                outcome.selected_device = "xpu"
                outcome.effective_device = "xpu:0"
                return outcome

        result = train_adapter_model(
            self._request(),
            dependencies=TrainingDependencies(runner=_DeviceRunner(calls)),
        )
        self.assertTrue(result.success, msg=str(result.error))
        # Propagated from the runner outcome, never inferred by the use case.
        self.assertEqual(result.selected_device, "xpu")
        self.assertEqual(result.effective_device, "xpu:0")
        # The metadata format is unchanged and records the same evidence.
        metadata = json.loads(
            (Path(result.output_dir or "") / "training_metadata.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["selected_device"], "xpu")
        self.assertEqual(metadata["effective_device"], "xpu:0")


class OrderTests(_Case):
    def test_runner_called_after_all_validations(self):
        # An invalid dataset must fail before the runner is ever invoked.
        calls: list = []
        bad = self._request(dataset_path=str(self.root / "missing.jsonl"))
        result = train_adapter_model(
            bad, dependencies=TrainingDependencies(runner=_FakeRunner(calls))
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, TrainingErrorCode.INVALID_DATASET)
        self.assertEqual(calls, [])
        self.assertIsNone(result.output_dir)

class AdmissionTests(_Case):
    def test_denied_admission_never_invokes_runner(self):
        calls: list = []
        from types import SimpleNamespace

        denied = SimpleNamespace(status="blocked", verdict="incompatible")
        result = train_adapter_model(
            self._request(),
            admission=denied,
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, TrainingErrorCode.ADMISSION_DENIED)
        self.assertEqual(calls, [])

    def test_admitting_verdict_records_evaluation_path(self):
        calls: list = []
        from types import SimpleNamespace

        admitted = SimpleNamespace(status="evaluated", verdict="compatible")
        result = train_adapter_model(
            self._request(),
            admission=admitted,
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.admission_path, "evaluation_admission")
        self.assertEqual(len(calls), 1)

    def test_no_stale_admission_is_reused(self):
        calls: list = []
        from types import SimpleNamespace

        admitted = SimpleNamespace(status="evaluated", verdict="compatible")
        denied = SimpleNamespace(status="blocked", verdict="incompatible")
        first = train_adapter_model(
            self._request(output_dir=str(self.root / "out-1")),
            admission=admitted,
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        second = train_adapter_model(
            self._request(output_dir=str(self.root / "out-2")),
            admission=denied,
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertEqual(len(calls), 1)


class FormatRejectionTests(_Case):
    def test_gguf_directory_rejected_before_runner(self):
        calls: list = []
        gguf_dir = _write_checkpoint(self.root / "gguf-base", gguf=True)
        result = train_adapter_model(
            self._request(base_model_dir=str(gguf_dir)),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(
            result.error.code, TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT
        )
        self.assertIn("GGUF", result.error.message)
        self.assertEqual(calls, [])

    def test_missing_config_rejected(self):
        calls: list = []
        empty = self.root / "empty-base"
        empty.mkdir()
        (empty / "model.safetensors").write_bytes(b"x")
        result = train_adapter_model(
            self._request(base_model_dir=str(empty)),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(
            result.error.code, TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT
        )
        self.assertEqual(calls, [])

    def test_missing_weights_rejected(self):
        calls: list = []
        nodata = self.root / "no-weights"
        nodata.mkdir()
        (nodata / "config.json").write_text("{}", encoding="utf-8")
        result = train_adapter_model(
            self._request(base_model_dir=str(nodata)),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(
            result.error.code, TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT
        )
        self.assertEqual(calls, [])


class DatasetDestinationTests(_Case):
    def test_invalid_dataset_rows_fail_clearly(self):
        calls: list = []
        bad = self.root / "bad.jsonl"
        bad.write_text("not json\n", encoding="utf-8")
        result = train_adapter_model(
            self._request(dataset_path=str(bad)),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, TrainingErrorCode.INVALID_DATASET)
        self.assertEqual(calls, [])

    def test_nonempty_destination_not_overwritten(self):
        calls: list = []
        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "keep.txt").write_text("user data", encoding="utf-8")
        result = train_adapter_model(
            self._request(output_dir=str(occupied)),
            dependencies=TrainingDependencies(runner=_FakeRunner(calls)),
        )
        self.assertFalse(result.success)
        self.assertEqual(
            result.error.code, TrainingErrorCode.INVALID_DESTINATION
        )
        self.assertEqual(calls, [])
        self.assertEqual(
            (occupied / "keep.txt").read_text(encoding="utf-8"), "user data"
        )

    def test_invalid_steps_rejected(self):
        with self.assertRaises(TrainingPreparationError) as raised:
            validate_training_request(self._request(max_steps=0))
        self.assertEqual(
            raised.exception.code, TrainingErrorCode.INVALID_REQUEST
        )


class FailureHygieneTests(_Case):
    def test_runner_failure_publishes_nothing(self):
        calls: list = []
        boom = RuntimeError("synthetic runner defect")
        result = train_adapter_model(
            self._request(),
            dependencies=TrainingDependencies(
                runner=_FakeRunner(calls, fail=boom)
            ),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, TrainingErrorCode.RUN_FAILED)
        out = self.root / "adapter-out"
        self.assertFalse(out.exists())
        leftovers = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith("castlearq-train-")
        ]
        self.assertEqual(leftovers, [])

    def test_typed_missing_dependencies_failure(self):
        result = train_adapter_model(
            self._request(),
            dependencies=TrainingDependencies(
                runner=_AlwaysMissingRunner()
            ),
        )
        self.assertFalse(result.success)
        self.assertEqual(
            result.error.code, TrainingErrorCode.DEPENDENCIES_MISSING
        )
        self.assertFalse((self.root / "adapter-out").exists())


class _AlwaysMissingRunner:
    def run(self, **kwargs):
        raise TrainingPreparationError(
            TrainingErrorCode.DEPENDENCIES_MISSING,
            "Training dependencies are missing: torch",
        )


if __name__ == "__main__":
    unittest.main()
