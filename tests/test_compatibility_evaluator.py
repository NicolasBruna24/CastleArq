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

"""Block B9.3 tests: functional compatibility evaluator (pure interpreter)."""

from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app import compatibility_evaluator as ce
from app.compatibility_domain import (
    CheckStatus,
    CompatibilityStatus,
    EvidenceKind,
)
from app.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from app.model_domain import (
    Model,
    ModelArchitecture,
    ModelArtifact,
    ModelCapabilities,
    ModelIdentity,
    ModelPrecision,
    ModelQuantization,
    QuantizationStatus,
)


def _model(**overrides):
    fields = {
        "identity": ModelIdentity(
            name="Qwen3-Coder-30B-A3B", model_id="qwen3-coder"),
        "architecture": ModelArchitecture(
            architecture="Transformer", model_type="MoE"),
        "capabilities": ModelCapabilities(text_generation=True),
        **overrides,
    }
    return Model(**fields)


def _artifact(**overrides):
    fields = {
        "precision": ModelPrecision(),
        "quantization": ModelQuantization(QuantizationStatus.QUANTIZED,
                                          "Q4_K_M", 4),
        "identifier": "qwen3-coder",
        "format": "GGUF",
        **overrides,
    }
    return ModelArtifact(**fields)


def _knowledge(**overrides):
    fields = {
        "name": "llama.cpp",
        "supports_artifact": True,
        "supported_formats": ("GGUF",),
        "supported_architectures": ("Transformer",),
        "supported_model_types": ("MoE",),
        "supported_backends": ("Vulkan",),
        **overrides,
    }
    return ce.RuntimeKnowledge(**fields)


def _context(**overrides):
    fields = {"runtime": _knowledge(), "backend": "Vulkan", **overrides}
    return ce.EvaluationContext(**fields)


def _hardware():
    return HardwareSnapshot(
        operating_system="Linux",
        architecture="x86_64",
        cpu=CPUInfo(model="Test CPU"),
        memory=MemoryInfo(total_bytes=48 * 1024 ** 3),
        gpus=[GPUInfo(name="Arc", vendor="Intel",
                      vram_bytes=32 * 1024 ** 3)],
    )


def _statuses(result):
    return {check.name: check.status for check in result.checks}


class IdentityTests(unittest.TestCase):
    def test_matching_identity_passes(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(
            _statuses(result)["artifact-model identity"], CheckStatus.PASSED)

    def test_explicit_mismatch_is_incompatible(self):
        model = _model(identity=ModelIdentity(
            name="Other", model_id="other-model"))
        result = ce.evaluate(model, _artifact(), _context())
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertIs(
            _statuses(result)["artifact-model identity"], CheckStatus.FAILED)

    def test_insufficient_identity_is_unknown_not_failed(self):
        model = _model(identity=ModelIdentity(name="Only A Name"))
        result = ce.evaluate(model, _artifact(), _context())
        self.assertIs(
            _statuses(result)["artifact-model identity"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_bare_identifier_vs_name_never_proves_identity(self):
        """A filename-like identifier equal to the model name is still
        UNKNOWN: names alone are the weaker signal."""
        model = _model(identity=ModelIdentity(name="qwen3-coder"))
        result = ce.evaluate(model, _artifact(), _context())
        self.assertIs(
            _statuses(result)["artifact-model identity"], CheckStatus.UNKNOWN)


class FormatTests(unittest.TestCase):
    def test_supported_format_passes(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(
            _statuses(result)["artifact format support"], CheckStatus.PASSED)

    def test_explicitly_unsupported_format_is_incompatible(self):
        context = _context(runtime=_knowledge(
            unsupported_formats=("GGUF",), supported_formats=()))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertIs(
            _statuses(result)["artifact format support"], CheckStatus.FAILED)

    def test_unknown_format_support_is_insufficient_evidence(self):
        context = _context(runtime=_knowledge())
        result = ce.evaluate(
            _model(), _artifact(format="EXOTIC"), context)
        self.assertIs(
            _statuses(result)["artifact format support"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_unknown_artifact_format_is_not_unsupported(self):
        context = _context(runtime=_knowledge(unsupported_formats=("ONNX",)))
        result = ce.evaluate(_model(), _artifact(format=None), context)
        self.assertIs(
            _statuses(result)["artifact format support"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_quantization_name_does_not_imply_format(self):
        artifact = _artifact(format=None)
        context = _context(runtime=_knowledge(supported_formats=("GGUF",)))
        result = ce.evaluate(_model(), artifact, context)
        self.assertIs(
            _statuses(result)["artifact format support"], CheckStatus.UNKNOWN)


class ArchitectureTests(unittest.TestCase):
    def test_supported_architecture_passes(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(
            _statuses(result)["model architecture support"],
            CheckStatus.PASSED)

    def test_explicitly_unsupported_architecture_is_incompatible(self):
        context = _context(runtime=_knowledge(
            unsupported_architectures=("Transformer",),
            supported_architectures=()))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)

    def test_unknown_architecture_is_insufficient_evidence(self):
        model = _model(architecture=ModelArchitecture())
        result = ce.evaluate(model, _artifact(), _context())
        self.assertIs(
            _statuses(result)["model architecture support"],
            CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_no_string_similarity_inference(self):
        """'Transformer-X' must not match 'Transformer' by similarity."""
        model = _model(architecture=ModelArchitecture(
            architecture="Transformer-X"))
        context = _context(
            runtime=_knowledge(supported_architectures=("Transformer",)))
        result = ce.evaluate(model, _artifact(), context)
        self.assertIs(
            _statuses(result)["model architecture support"],
            CheckStatus.UNKNOWN)


class RuntimeBackendTests(unittest.TestCase):
    def test_explicit_runtime_support_passes(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(
            _statuses(result)["runtime artifact support"], CheckStatus.PASSED)

    def test_explicit_runtime_rejection_is_incompatible(self):
        context = _context(runtime=_knowledge(supports_artifact=False))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertIs(
            _statuses(result)["runtime artifact support"], CheckStatus.FAILED)

    def test_unknown_runtime_support_is_insufficient_evidence(self):
        context = _context(runtime=_knowledge(supports_artifact=None))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(
            _statuses(result)["runtime artifact support"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_explicit_backend_support_passes(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(
            _statuses(result)["runtime backend support"], CheckStatus.PASSED)

    def test_explicit_backend_rejection_is_incompatible(self):
        context = _context(runtime=_knowledge(
            unsupported_backends=("Vulkan",), supported_backends=()))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)

    def test_unknown_backend_is_insufficient_evidence(self):
        context = _context(
            backend="Vulkan", runtime=_knowledge(supported_backends=()))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(
            _statuses(result)["runtime backend support"], CheckStatus.UNKNOWN)

    def test_gpu_presence_does_not_imply_backend_support(self):
        """Hardware carries GPUs, yet backend stays UNKNOWN: the evaluator
        never reads hardware for functional conclusions."""
        context = _context(
            backend="Vulkan",
            runtime=_knowledge(supported_backends=()),
            hardware=_hardware())
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertTrue(context.hardware.gpus)
        self.assertIs(
            _statuses(result)["runtime backend support"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)


class KnowledgeValidationTests(unittest.TestCase):
    """Malformed capability knowledge fails fast, never becomes UNKNOWN."""

    def test_contradictory_supported_unsupported_rejected(self):
        for supported_label, unsupported_label in (
            ("supported_formats", "unsupported_formats"),
            ("supported_architectures", "unsupported_architectures"),
            ("supported_model_types", "unsupported_model_types"),
            ("supported_backends", "unsupported_backends"),
        ):
            with self.assertRaises(ValueError):
                _knowledge(**{supported_label: ("X",),
                              unsupported_label: ("X",)})

    def test_invalid_name_rejected(self):
        for name in ("", "   "):
            with self.assertRaises(ValueError):
                _knowledge(name=name)

    def test_non_bool_supports_artifact_rejected(self):
        with self.assertRaises(ValueError):
            _knowledge(supports_artifact="yes")

    def test_unknown_capability_name_rejected(self):
        with self.assertRaises(ValueError):
            _context(required_capabilities=("telepathy",))

    def test_blank_backend_rejected(self):
        for backend in ("", "  "):
            with self.assertRaises(ValueError):
                _context(backend=backend)

    def test_invalid_runtime_and_hardware_types_rejected(self):
        with self.assertRaises(ValueError):
            _context(runtime=object())
        with self.assertRaises(ValueError):
            _context(hardware=object())


class CapabilitiesTests(unittest.TestCase):
    def _required(self, **capabilities):
        model = _model(capabilities=ModelCapabilities(**capabilities))
        context = _context(
            required_capabilities=("text_generation",))
        return ce.evaluate(model, _artifact(), context)

    def test_required_capability_true_passes(self):
        result = self._required(text_generation=True)
        self.assertIs(
            _statuses(result)["model capability: text_generation"],
            CheckStatus.PASSED)

    def test_required_capability_false_fails(self):
        result = self._required(text_generation=False)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertIs(
            _statuses(result)["model capability: text_generation"],
            CheckStatus.FAILED)

    def test_required_capability_none_is_unknown(self):
        model = _model(capabilities=ModelCapabilities())
        context = _context(required_capabilities=("vision",))
        result = ce.evaluate(model, _artifact(), context)
        self.assertIs(
            _statuses(result)["model capability: vision"], CheckStatus.UNKNOWN)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_optional_unknown_capability_does_not_invalidate(self):
        """Non-required capabilities are never checked at all."""
        result = ce.evaluate(_model(), _artifact(), _context())
        names = [check.name for check in result.checks]
        self.assertNotIn("model capability: vision", names)
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)

    def test_no_default_text_generation_requirement(self):
        model = _model(capabilities=ModelCapabilities())
        result = ce.evaluate(model, _artifact(), _context())
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)


class AggregationTests(unittest.TestCase):
    def test_determinant_failure_wins_over_unknown(self):
        model = _model(architecture=ModelArchitecture())
        context = _context(runtime=_knowledge(
            unsupported_formats=("GGUF",), supported_formats=()))
        result = ce.evaluate(model, _artifact(), context)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)
        statuses = _statuses(result)
        self.assertIs(statuses["artifact format support"], CheckStatus.FAILED)
        self.assertIs(
            statuses["model architecture support"], CheckStatus.UNKNOWN)

    def test_required_unknown_yields_insufficient_evidence(self):
        context = _context(
            runtime=_knowledge(supported_formats=()))
        result = ce.evaluate(_model(), _artifact(), context)
        self.assertIs(
            result.status, CompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_all_required_pass_yields_compatible(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(result.conditions, ())
        self.assertTrue(all(
            check.status is CheckStatus.PASSED for check in result.checks))

    def test_no_scores_or_thresholds(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        for forbidden in ("score", "compatibility_score", "percentage"):
            self.assertFalse(hasattr(result, forbidden))

    def test_deterministic_repeated_calls(self):
        first = ce.evaluate(_model(), _artifact(), _context())
        second = ce.evaluate(_model(), _artifact(), _context())
        self.assertEqual(first, second)


class EvidencePurityTests(unittest.TestCase):
    def test_every_check_carries_evidence(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        self.assertGreaterEqual(len(result.checks), 5)
        for check in result.checks:
            self.assertTrue(check.evidence, check.name)
            for item in check.evidence:
                self.assertIsInstance(item.kind, EvidenceKind)

    def test_kind_never_upgraded(self):
        result = ce.evaluate(_model(), _artifact(), _context())
        kinds = {item.kind for check in result.checks
                 for item in check.evidence}
        self.assertEqual(kinds, {EvidenceKind.OBSERVED})

    def test_inputs_are_not_mutated(self):
        model, artifact, context = _model(), _artifact(), _context()
        before = (copy.deepcopy(model), copy.deepcopy(artifact),
                  copy.deepcopy(context))
        ce.evaluate(model, artifact, context)
        self.assertEqual(
            (model, artifact, context), (before[0], before[1], before[2]))
        self.assertIsInstance(context.required_capabilities, tuple)

    def test_no_resource_conclusions_from_storage_or_bits(self):
        hardware = _hardware()  # 32 GiB VRAM, 48 GiB RAM
        context = _context(hardware=hardware)
        artifact = _artifact(storage_size_bytes=18 * 1024 ** 3)
        result = ce.evaluate(_model(), artifact, context)
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)
        names = [check.name.lower() for check in result.checks]
        joined = " ".join(names)
        for word in ("vram", "memory", "ram", "kv", "offload", "storage"):
            self.assertNotIn(word, joined)

    def test_module_has_no_io_or_execution_surface(self):
        source = Path(ce.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed_modules = {"__future__", "dataclasses"}
        allowed_local = {
            "compatibility_domain", "hardware", "model_domain"}
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertTrue(
                    node.module in allowed_modules
                    or (node.level == 1 and node.module in allowed_local),
                    node.module)

    def test_no_side_effects_under_hostile_patches(self):
        def explode(*args, **kwargs):
            raise AssertionError("B9.3 must never execute anything")

        with patch("subprocess.run", side_effect=explode), patch(
            "subprocess.Popen", side_effect=explode
        ), patch("os.system", side_effect=explode), patch(
            "socket.socket", side_effect=explode
        ), patch("urllib.request.urlopen", side_effect=explode):
            result = ce.evaluate(_model(), _artifact(), _context())
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)


if __name__ == "__main__":
    unittest.main()
