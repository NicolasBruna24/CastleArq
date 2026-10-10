# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Tests for training device evidence in outcomes and metadata.

No GPU, torch, or training stack is required: the runner's heavy
dependencies are stubbed in ``sys.modules`` and the Trainer/model/tokenizer
collaborators are fakes. Nothing here touches real hardware.
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

from castlearq.training import (
    TrainingDependencies,
    TrainingRequest,
    train_adapter_model,
)


def _install_training_stack_stub(*, device_report=None, device_raises=False):
    """Install stub torch/datasets/peft/transformers/trl modules."""
    captured = {}

    torch_stub = types.ModuleType("torch")
    datasets_stub = types.ModuleType("datasets")

    class _FakeHfDataset:
        @staticmethod
        def from_dict(mapping):
            return dict(mapping)

    datasets_stub.Dataset = _FakeHfDataset
    peft_stub = types.ModuleType("peft")

    class _FakeLoraConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    peft_stub.LoraConfig = _FakeLoraConfig
    transformers_stub = types.ModuleType("transformers")

    class _FakeModel:
        @staticmethod
        def from_pretrained(path):
            return SimpleNamespace(path=path)

    class _FakeTokenizer:
        pad_token = None
        eos_token = "<eos>"

        @staticmethod
        def from_pretrained(path):
            return _FakeTokenizer()

    transformers_stub.AutoModelForCausalLM = _FakeModel
    transformers_stub.AutoTokenizer = _FakeTokenizer
    trl_stub = types.ModuleType("trl")

    class SFTConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class _FakeState:
        global_step = 1
        log_history = [{"loss": 2.5}]

    class _FakeTrainer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            if device_raises:
                failing = type(
                    "FailingArgs",
                    (),
                    {"device": property(lambda self: 1 / 0)},
                )
                self.args = failing()
            else:
                self.args = SimpleNamespace(device=device_report)
            self.state = _FakeState()

        def train(self):
            return None

        def save_model(self, path):
            Path(path).mkdir(parents=True, exist_ok=True)
            (Path(path) / "adapter_model.safetensors").write_bytes(b"x")

    trl_stub.SFTConfig = SFTConfig
    trl_stub.SFTTrainer = _FakeTrainer

    for name, module in (
        ("torch", torch_stub),
        ("datasets", datasets_stub),
        ("peft", peft_stub),
        ("transformers", transformers_stub),
        ("trl", trl_stub),
    ):
        sys.modules[name] = module
    return captured


def _xpu_torch():
    return SimpleNamespace(
        xpu=SimpleNamespace(is_available=lambda: True),
        cuda=SimpleNamespace(is_available=lambda: False),
    )


class DeviceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        base = self.root / "base"
        base.mkdir()
        (base / "config.json").write_text("{}", encoding="utf-8")
        (base / "model.safetensors").write_bytes(b"x")
        dataset = self.root / "data.jsonl"
        dataset.write_text(
            json.dumps({"text": "hello world training text"}) + "\n",
            encoding="utf-8",
        )
        self._saved_modules = dict(sys.modules)
        self.addCleanup(self._restore_modules)

    def _restore_modules(self):
        for name in ("torch", "datasets", "peft", "transformers", "trl"):
            sys.modules.pop(name, None)
        sys.modules.update(self._saved_modules)

    def _request(self, out_name="adapter-out"):
        return TrainingRequest(
            base_model_dir=str(self.root / "base"),
            dataset_path=str(self.root / "data.jsonl"),
            output_dir=str(self.root / out_name),
            max_steps=1,
            lora_rank=4,
            lora_alpha=8,
        )

    def test_runner_outcome_carries_selected_and_effective_device(self):
        from castlearq.training_runner import SftLoraRunner

        captured = _install_training_stack_stub(device_report="xpu:0")
        sys.modules["torch"] = _xpu_torch()
        runner = SftLoraRunner()
        runner.check_dependencies = lambda: None
        staging = self.root / "staging"
        staging.mkdir()
        outcome = runner.run(
            base_model_dir=self.root / "base",
            dataset_rows=[{"text": "hello world training text"}],
            staging_dir=staging,
            max_steps=1,
            lora_rank=4,
            lora_alpha=8,
        )
        self.assertEqual(outcome.selected_device, "xpu")
        self.assertEqual(outcome.effective_device, "xpu:0")
        # Selection precedence is unchanged and consistent with the flag.
        self.assertFalse(captured["use_cpu"])

    def test_effective_device_failure_stays_unknown(self):
        from castlearq.training_runner import SftLoraRunner

        _install_training_stack_stub(device_report=None, device_raises=True)
        sys.modules["torch"] = _xpu_torch()
        runner = SftLoraRunner()
        runner.check_dependencies = lambda: None
        staging = self.root / "staging"
        staging.mkdir()
        outcome = runner.run(
            base_model_dir=self.root / "base",
            dataset_rows=[{"text": "hello world training text"}],
            staging_dir=staging,
            max_steps=1,
            lora_rank=4,
            lora_alpha=8,
        )
        # Never echo the selection when the Trainer read fails.
        self.assertEqual(outcome.selected_device, "xpu")
        self.assertIsNone(outcome.effective_device)

    def test_metadata_persists_both_device_fields(self):
        _install_training_stack_stub(device_report="xpu:0")
        sys.modules["torch"] = _xpu_torch()
        from castlearq.training_runner import SftLoraRunner

        runner = SftLoraRunner()
        runner.check_dependencies = lambda: None
        result = train_adapter_model(
            self._request("out-evidence"),
            dependencies=TrainingDependencies(runner=runner),
        )
        self.assertTrue(result.success, msg=str(result.error))
        metadata = json.loads(
            (Path(str(result.output_dir)) / "training_metadata.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["selected_device"], "xpu")
        self.assertEqual(metadata["effective_device"], "xpu:0")

    def test_legacy_mock_runner_without_device_fields_stays_safe(self):
        from castlearq.training_runner import RunnerOutcome

        class _LegacyRunner:
            def run(self, **kwargs):
                staging = kwargs["staging_dir"]
                (staging / "adapter_model.safetensors").write_bytes(b"x")
                outcome = RunnerOutcome(
                    files=("adapter_model.safetensors",),
                    steps_completed=1,
                    final_loss=3.0,
                )
                # Simulate a runner predating the fields entirely.
                del outcome.selected_device
                del outcome.effective_device
                return outcome

        result = train_adapter_model(
            self._request("out-legacy"),
            dependencies=TrainingDependencies(runner=_LegacyRunner()),
        )
        self.assertTrue(result.success, msg=str(result.error))
        metadata = json.loads(
            (Path(str(result.output_dir)) / "training_metadata.json")
            .read_text(encoding="utf-8")
        )
        self.assertIsNone(metadata["selected_device"])
        self.assertIsNone(metadata["effective_device"])


if __name__ == "__main__":
    unittest.main()
