# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Opt-in CPU-only training smoke test (skipped without training extra).

Builds a tiny self-contained fixture in a temporary directory: a minimal
Transformers checkpoint plus a small JSONL dataset. No network, no GPU,
no repository fixture with downloaded weights.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

_CAUSE = None
try:
    import torch  # noqa: F401
    import transformers  # noqa: F401
    import peft  # noqa: F401
    import trl  # noqa: F401
    import datasets  # noqa: F401

    _TRAINING_AVAILABLE = True
except ImportError as _error:  # pragma: no cover - env dependent
    _TRAINING_AVAILABLE = False
    _CAUSE = _error


@unittest.skipUnless(
    _TRAINING_AVAILABLE, f"training extra not installed: {_CAUSE}"
)
class CpuSmokeTests(unittest.TestCase):
    def test_one_cpu_step_publishes_adapter(self):
        from transformers import BertConfig, BertForMaskedLM

        from castlearq.training import TrainingRequest, train_adapter_model

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "tiny-base"
            base.mkdir()
            config = BertConfig(
                vocab_size=64,
                hidden_size=32,
                num_hidden_layers=1,
                num_attention_heads=2,
                intermediate_size=64,
            )
            model = BertForMaskedLM(config)
            model.save_pretrained(str(base))
            dataset_path = root / "data.jsonl"
            with dataset_path.open("w", encoding="utf-8") as stream:
                for index in range(4):
                    stream.write(
                        json.dumps(
                            {"text": f"hello world example {index} text"}
                        )
                        + "\n"
                    )
            out = root / "adapter-out"
            result = train_adapter_model(
                TrainingRequest(
                    base_model_dir=str(base),
                    dataset_path=str(dataset_path),
                    output_dir=str(out),
                    max_steps=1,
                    lora_rank=4,
                    lora_alpha=8,
                )
            )
            self.assertTrue(
                result.success,
                msg=str(result.error.message) if result.error else "no error",
            )
            self.assertTrue((out / "training_metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
