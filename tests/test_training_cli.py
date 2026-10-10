# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""CLI tests for the bounded ``train`` command.

The command stays thin: usage errors exit 2, training failures exit 1
with a typed code, and the heavy work belongs to the use case.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq import main as cli
from castlearq.training import TrainingErrorCode, TrainingResult


def _checkpoint(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text("{}", encoding="utf-8")
    (directory / "model.safetensors").write_bytes(b"x")
    return directory


def _dataset(path: Path) -> Path:
    path.write_text(
        json.dumps({"text": "hello world training text"}) + "\n",
        encoding="utf-8",
    )
    return path


class TrainCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_missing_args_is_usage_error(self):
        self.assertEqual(cli.train_command(None, None, None), 2)

    def test_success_prints_summary_and_returns_zero(self):
        base = _checkpoint(self.root / "base")
        data = _dataset(self.root / "data.jsonl")
        out = self.root / "adapter"
        ok = TrainingResult(
            success=True,
            output_dir=str(out),
            base_model_dir=str(base),
            files=("adapter_model.safetensors", "training_metadata.json"),
            steps_completed=2,
            final_loss=4.5,
            selected_device="xpu",
            effective_device="xpu:0",
        )
        printed = io.StringIO()
        with mock.patch(
            "castlearq.main.compose_training_dependencies"
        ) as composed, mock.patch(
            "castlearq.training.train_adapter_model", return_value=ok
        ) as trained, contextlib.redirect_stdout(printed):
            code = cli.train_command(
                str(base), str(data), str(out), max_steps=2
            )
        self.assertEqual(code, 0)
        self.assertEqual(composed.call_count, 1)
        request = trained.call_args[0][0]
        self.assertEqual(request.base_model_dir, str(base))
        self.assertEqual(request.max_steps, 2)
        # The success summary must expose adapter dir, metadata path and
        # the actual device evidence without inspecting any other file.
        summary = printed.getvalue()
        self.assertIn(f"Trained adapter in {out}", summary)
        self.assertIn("steps=2", summary)
        self.assertIn("loss=4.5000", summary)
        self.assertIn("selected_device=xpu", summary)
        self.assertIn("effective_device=xpu:0", summary)
        self.assertIn(
            f"Metadata: {out / 'training_metadata.json'}", summary
        )

    def test_success_reports_unavailable_device_neutrally(self):
        base = _checkpoint(self.root / "base")
        data = _dataset(self.root / "data.jsonl")
        out = self.root / "adapter"
        ok = TrainingResult(
            success=True,
            output_dir=str(out),
            base_model_dir=str(base),
            files=("adapter_model.safetensors", "training_metadata.json"),
            steps_completed=1,
        )
        printed = io.StringIO()
        with mock.patch(
            "castlearq.main.compose_training_dependencies"
        ), mock.patch(
            "castlearq.training.train_adapter_model", return_value=ok
        ), contextlib.redirect_stdout(printed):
            code = cli.train_command(str(base), str(data), str(out))
        self.assertEqual(code, 0)
        summary = printed.getvalue()
        # Missing evidence is rendered as an explicit neutral value and
        # no device is ever invented.
        self.assertIn("selected_device=unavailable", summary)
        self.assertIn("effective_device=unavailable", summary)
        self.assertNotIn("xpu", summary)
        self.assertNotIn("cuda", summary)
        self.assertIn(
            f"Metadata: {out / 'training_metadata.json'}", summary
        )

    def test_failure_returns_one_with_typed_code(self):
        base = _checkpoint(self.root / "base")
        data = _dataset(self.root / "data.jsonl")
        out = self.root / "adapter"
        bad = TrainingResult(
            success=False,
            base_model_dir=str(base),
            error=mock.Mock(
                code=TrainingErrorCode.UNSUPPORTED_MODEL_FORMAT,
                message="GGUF weights are not a Transformers checkpoint",
            ),
        )
        with mock.patch(
            "castlearq.main.compose_training_dependencies"
        ), mock.patch(
            "castlearq.training.train_adapter_model", return_value=bad
        ):
            code = cli.train_command(str(base), str(data), str(out))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
