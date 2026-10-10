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

"""Training runners for the bounded SFT + LoRA prototype.

This module is import-safe WITHOUT the ML stack installed: it imports only
the standard library at module top level. Heavy dependencies
(torch/transformers/peft/trl) are imported lazily inside
:meth:`SftLoraRunner.run`, so ordinary CastleArq commands keep working when
the ``training`` extra is absent. A missing stack raises
``TrainingPreparationError`` with ``DEPENDENCIES_MISSING`` instead of an
``ImportError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .training import TrainingErrorCode, TrainingPreparationError


@dataclass
class RunnerOutcome:
    """What the use case needs from any training runner."""

    files: tuple[str, ...] = ()
    steps_completed: int = 0
    final_loss: float | None = None
    # Backend evidence. ``selected_device`` is the ``select_training_device()``
    # choice (``"xpu"``/``"cuda"``/``"cpu"``); ``effective_device`` is the
    # device the initialized Trainer reports (``trainer.args.device``), or
    # ``None`` when that evidence is unavailable (e.g. reading it raised, or
    # an injected/mock runner does not provide it). ``None`` serializes as
    # JSON ``null`` and must never be read as claiming a device.
    selected_device: str | None = None
    effective_device: str | None = None


def select_training_device(torch_module: Any | None = None) -> str:
    """Choose the training backend: XPU, then CUDA, then CPU.

    Defensive against CPU-only ``torch`` builds without an ``xpu``
    attribute; never raises for missing backends.
    """
    if torch_module is None:
        import torch as torch_module  # lazy: training stack is optional

    xpu = getattr(torch_module, "xpu", None)
    try:
        is_xpu_available = getattr(xpu, "is_available", None)
        if callable(is_xpu_available) and bool(is_xpu_available()):
            return "xpu"
    except Exception:
        pass
    cuda = getattr(torch_module, "cuda", None)
    try:
        is_cuda_available = getattr(cuda, "is_available", None)
        if callable(is_cuda_available) and bool(is_cuda_available()):
            return "cuda"
    except Exception:
        pass
    return "cpu"


class SftLoraRunner:
    """Bounded SFT + LoRA runner using the lazily imported ML stack."""

    #: Minimum versions that match the validated experiment environment.
    REQUIRED = ("torch", "transformers", "peft", "trl", "datasets")

    def check_dependencies(self) -> None:
        """Raise a typed failure when the training stack is unavailable."""
        missing: list[str] = []
        for name in self.REQUIRED:
            try:
                __import__(name)
            except ImportError:
                missing.append(name)
        if missing:
            raise TrainingPreparationError(
                TrainingErrorCode.DEPENDENCIES_MISSING,
                "Training dependencies are missing: "
                + ", ".join(missing)
                + ". Install CastleArq with the 'training' extra "
                "(pip install 'castlearq[training]') and retry; ordinary "
                "CastleArq commands are unaffected.",
            )

    def run(
        self,
        *,
        base_model_dir: Path,
        dataset_rows: list[dict[str, str]],
        staging_dir: Path,
        max_steps: int,
        lora_rank: int,
        lora_alpha: int,
    ) -> RunnerOutcome:
        """Run bounded SFT + LoRA and write the adapter into staging_dir."""
        self.check_dependencies()
        # Lazy imports: the training stack is optional and must never be
        # on CastleArq's import-time path.
        import torch
        from datasets import Dataset as HfDataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer

        texts = [row["text"] for row in dataset_rows]
        dataset = HfDataset.from_dict({"text": texts})
        # Single authority for backend selection: XPU, then CUDA, then
        # CPU. The Trainer (via Accelerate ``use_cpu`` below) resolves
        # XPU/CUDA automatically, so the runner records the same choice
        # and passes the matching ``use_cpu`` flag to keep both
        # consistent. No ``device`` argument exists on SFTConfig.
        device = select_training_device(torch)
        model = AutoModelForCausalLM.from_pretrained(str(base_model_dir))
        # Device moves stay with the Trainer/Accelerate: an explicit
        # ``model.to(...)`` here would fight ``prepare_model`` placement,
        # so the runner only records the selected backend and lets
        # ``use_cpu`` below keep the Trainer consistent with it.
        tokenizer = AutoTokenizer.from_pretrained(str(base_model_dir))
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        peft_config = LoraConfig(
            r=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=0.0,
            bias="none",
            task_type="CAUSAL_LM",
        )
        args = SFTConfig(
            output_dir=str(staging_dir),
            max_steps=max_steps,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=1e-4,
            logging_steps=1,
            save_strategy="no",
            report_to="none",
            seed=0,
            dataset_text_field="text",
            use_cpu=(device == "cpu"),
        )
        trainer = SFTTrainer(
            model=model,
            args=args,
            train_dataset=dataset,
            peft_config=peft_config,
            processing_class=tokenizer,
        )
        # Effective-device evidence: what the initialized Trainer reports,
        # not a restatement of the selection above. A failed read stays
        # ``None`` (unknown) rather than echoing ``device``.
        try:
            effective_device = str(trainer.args.device)
        except Exception:
            effective_device = None
        trainer.train()
        trainer.save_model(str(staging_dir))
        produced = sorted(
            path.name
            for path in staging_dir.iterdir()
            if path.is_file() and path.name != "training_metadata.json"
        )
        history = getattr(trainer.state, "log_history", []) or []
        final_loss: float | None = None
        for entry in reversed(history):
            if isinstance(entry, dict) and entry.get("loss") is not None:
                try:
                    final_loss = float(entry["loss"])
                except (TypeError, ValueError):
                    final_loss = None
                break
        return RunnerOutcome(
            files=tuple(produced),
            steps_completed=int(
                getattr(getattr(trainer, "state", None), "global_step", 0)
                or 0
            ),
            final_loss=final_loss,
            selected_device=device,
            effective_device=effective_device,
        )


__all__ = ["RunnerOutcome", "SftLoraRunner", "select_training_device"]
