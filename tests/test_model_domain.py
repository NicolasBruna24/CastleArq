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

"""Block B8.1 tests: immutable model domain (pure representation only)."""

from __future__ import annotations

import ast
import dataclasses
import unittest
from pathlib import Path
from unittest.mock import patch

from app import model_domain as md


def _identity(**overrides):
    fields = {"name": "Qwen3-Coder-30B-A3B", **overrides}
    return md.ModelIdentity(**fields)


def _artifact(**overrides):
    fields = {
        "precision": md.ModelPrecision(),
        "quantization": md.ModelQuantization(
            md.QuantizationStatus.QUANTIZED, "Q4_K_M", 4),
        "identifier": "qwen3-coder-q4_k_m.gguf",
        "format": "GGUF",
        "storage_size_bytes": 18 * 1024 ** 3,
        **overrides,
    }
    return md.ModelArtifact(**fields)


class ModelIdentityTests(unittest.TestCase):
    def test_valid_identity(self):
        identity = _identity(
            model_id="qwen3-coder-30b-a3b", version="1.0", variant="instruct")
        self.assertEqual(identity.name, "Qwen3-Coder-30B-A3B")

    def test_optional_fields_stay_unknown(self):
        identity = _identity()
        self.assertIsNone(identity.model_id)
        self.assertIsNone(identity.version)
        self.assertIsNone(identity.variant)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            _identity(name="")

    def test_whitespace_name_is_rejected(self):
        with self.assertRaises(ValueError):
            _identity(name="   \t ")

    def test_non_string_name_is_rejected(self):
        with self.assertRaises(ValueError):
            _identity(name=42)


class ModelProvenanceTests(unittest.TestCase):
    def test_all_fields_can_be_unknown(self):
        provenance = md.ModelProvenance()
        self.assertIsNone(provenance.source)
        self.assertIsNone(provenance.repository)
        self.assertIsNone(provenance.author)

    def test_provenance_fields(self):
        provenance = md.ModelProvenance(
            source="huggingface",
            repository="Qwen/Qwen3-Coder-30B-A3B",
            author="Qwen",
        )
        self.assertEqual(provenance.repository, "Qwen/Qwen3-Coder-30B-A3B")

    def test_no_trust_fields_exist(self):
        for field_name in ("trust", "trust_score", "signature", "hashes",
                           "evidence"):
            self.assertFalse(hasattr(md.ModelProvenance, field_name))


class ModelArchitectureTests(unittest.TestCase):
    def test_unknown_everything(self):
        architecture = md.ModelArchitecture()
        self.assertIsNone(architecture.parameters)
        self.assertIsNone(architecture.active_parameters)

    def test_valid_parameters(self):
        architecture = md.ModelArchitecture(
            architecture="Transformer",
            model_type="MoE",
            parameters=30_000_000_000,
            active_parameters=3_000_000_000,
        )
        self.assertEqual(architecture.model_type, "MoE")

    def test_active_greater_than_parameters_is_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelArchitecture(parameters=3, active_parameters=30)

    def test_active_unknown_is_not_assumed_equal(self):
        architecture = md.ModelArchitecture(parameters=30_000_000_000)
        self.assertIsNone(architecture.active_parameters)

    def test_negative_parameters_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelArchitecture(parameters=-30)

    def test_zero_parameters_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelArchitecture(parameters=0)

    def test_unknown_is_never_coerced_to_zero(self):
        self.assertIsNone(md.ModelArchitecture(parameters=None).parameters)

    def test_non_integer_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelArchitecture(parameters="30B")


class ModelPrecisionTests(unittest.TestCase):
    def test_f32_valid(self):
        precision = md.ModelPrecision("F32", 32)
        self.assertEqual(precision.name, "F32")
        self.assertEqual(precision.bits, 32)

    def test_f16_valid(self):
        self.assertEqual(md.ModelPrecision("F16", 16).name, "F16")

    def test_bf16_valid(self):
        precision = md.ModelPrecision("BF16", 16)
        self.assertEqual(precision.name, "BF16")
        self.assertEqual(precision.bits, 16)

    def test_positive_bits_required(self):
        for bits in (0, -16):
            with self.assertRaises(ValueError):
                md.ModelPrecision(bits=bits)

    def test_unknown_bits_allowed(self):
        self.assertIsNone(md.ModelPrecision("F8").bits)

    def test_unknown_name_allowed(self):
        self.assertIsNone(md.ModelPrecision(bits=32).name)

    def test_fully_unknown(self):
        precision = md.ModelPrecision()
        self.assertIsNone(precision.name)
        self.assertIsNone(precision.bits)

    def test_non_integer_bits_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelPrecision(bits="16")

    def test_no_closed_enum_of_precisions(self):
        self.assertFalse(hasattr(md, "PrecisionType"))


class ModelQuantizationTests(unittest.TestCase):
    STATUS = md.QuantizationStatus

    def test_unknown_status(self):
        quantization = md.ModelQuantization(self.STATUS.UNKNOWN)
        self.assertIs(quantization.status, self.STATUS.UNKNOWN)
        self.assertIsNone(quantization.method)
        self.assertIsNone(quantization.nominal_bits)

    def test_not_quantized_status(self):
        quantization = md.ModelQuantization(self.STATUS.NOT_QUANTIZED)
        self.assertIs(quantization.status, self.STATUS.NOT_QUANTIZED)

    def test_quantized_status(self):
        quantization = md.ModelQuantization(self.STATUS.QUANTIZED)
        self.assertIs(quantization.status, self.STATUS.QUANTIZED)

    def test_q4_k_m_with_four_bits(self):
        quantization = md.ModelQuantization(
            self.STATUS.QUANTIZED, "Q4_K_M", 4)
        self.assertEqual(quantization.method, "Q4_K_M")
        self.assertEqual(quantization.nominal_bits, 4)

    def test_q8_0_with_eight_bits(self):
        quantization = md.ModelQuantization(
            self.STATUS.QUANTIZED, "Q8_0", 8)
        self.assertEqual(quantization.nominal_bits, 8)

    def test_quantized_with_unknown_method(self):
        quantization = md.ModelQuantization(self.STATUS.QUANTIZED, None, 4)
        self.assertIsNone(quantization.method)
        self.assertEqual(quantization.nominal_bits, 4)

    def test_quantized_with_unknown_nominal_bits(self):
        quantization = md.ModelQuantization(self.STATUS.QUANTIZED, "Q6_K")
        self.assertEqual(quantization.method, "Q6_K")
        self.assertIsNone(quantization.nominal_bits)

    def test_quantized_with_fully_unknown_details(self):
        quantization = md.ModelQuantization(self.STATUS.QUANTIZED)
        self.assertIsNone(quantization.method)
        self.assertIsNone(quantization.nominal_bits)

    def test_not_quantized_forbids_method(self):
        with self.assertRaises(ValueError):
            md.ModelQuantization(self.STATUS.NOT_QUANTIZED, "Q4_K_M", None)

    def test_not_quantized_forbids_nominal_bits(self):
        with self.assertRaises(ValueError):
            md.ModelQuantization(self.STATUS.NOT_QUANTIZED, None, 4)

    def test_negative_nominal_bits_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelQuantization(self.STATUS.QUANTIZED, "Q4_K_M", -4)

    def test_zero_nominal_bits_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelQuantization(self.STATUS.QUANTIZED, nominal_bits=0)

    def test_status_is_mandatory(self):
        with self.assertRaises(ValueError):
            md.ModelQuantization(status=None)

    def test_no_artificial_none_token(self):
        quantization = md.ModelQuantization(self.STATUS.NOT_QUANTIZED)
        self.assertNotEqual(quantization.method, "none")
        self.assertIsNone(quantization.method)

    def test_unknown_and_not_quantized_are_different_values(self):
        unknown = md.ModelQuantization(self.STATUS.UNKNOWN)
        not_quantized = md.ModelQuantization(self.STATUS.NOT_QUANTIZED)
        self.assertNotEqual(unknown, not_quantized)
        self.assertNotEqual(unknown.status, not_quantized.status)

    def test_no_closed_enum_of_methods(self):
        self.assertFalse(hasattr(md, "QuantizationMethod"))

    def test_nominal_bits_is_not_memory(self):
        for field_name in ("actual_bits_per_parameter",
                           "bytes_per_weight", "memory_bytes"):
            self.assertFalse(hasattr(md.ModelQuantization, field_name))


class ModelArtifactTests(unittest.TestCase):
    def test_valid_artifact(self):
        artifact = _artifact()
        self.assertEqual(artifact.format, "GGUF")
        self.assertEqual(artifact.quantization.method, "Q4_K_M")
        self.assertIsNone(artifact.precision.name)

    def test_storage_size_none(self):
        artifact = _artifact(storage_size_bytes=None)
        self.assertIsNone(artifact.storage_size_bytes)

    def test_storage_size_zero_allowed(self):
        artifact = _artifact(storage_size_bytes=0)
        self.assertEqual(artifact.storage_size_bytes, 0)

    def test_negative_storage_size_rejected(self):
        with self.assertRaises(ValueError):
            _artifact(storage_size_bytes=-1)

    def test_precision_and_quantization_are_required_domain_types(self):
        with self.assertRaises(ValueError):
            _artifact(precision="BF16")
        with self.assertRaises(ValueError):
            _artifact(quantization="Q4_K_M")

    def test_case_1_known_precision_without_quantization(self):
        artifact = _artifact(
            format="Safetensors",
            precision=md.ModelPrecision("BF16", 16),
            quantization=md.ModelQuantization(
                md.QuantizationStatus.NOT_QUANTIZED),
        )
        self.assertEqual(artifact.precision.name, "BF16")
        self.assertIs(
            artifact.quantization.status,
            md.QuantizationStatus.NOT_QUANTIZED)

    def test_case_2_quantized_gguf(self):
        artifact = _artifact()
        self.assertEqual(artifact.format, "GGUF")
        self.assertIs(
            artifact.quantization.status,
            md.QuantizationStatus.QUANTIZED)

    def test_case_3_fully_unknown(self):
        artifact = _artifact(
            format="GGUF",
            precision=md.ModelPrecision(),
            quantization=md.ModelQuantization(
                md.QuantizationStatus.UNKNOWN),
        )
        self.assertIsNone(artifact.precision.name)
        self.assertIs(
            artifact.quantization.status, md.QuantizationStatus.UNKNOWN)

    def test_case_4_known_precision_and_known_quantization(self):
        artifact = _artifact(
            precision=md.ModelPrecision("BF16", 16),
            quantization=md.ModelQuantization(
                md.QuantizationStatus.QUANTIZED, "Q4_K_M", 4),
        )
        self.assertEqual(artifact.precision.name, "BF16")
        self.assertEqual(artifact.quantization.method, "Q4_K_M")

    def test_quantized_does_not_invent_base_precision(self):
        """GGUF + Q4_K_M must not imply precision = FP4 / 4 bits."""
        artifact = _artifact()
        self.assertIsNone(artifact.precision.name)
        self.assertIsNone(artifact.precision.bits)
        self.assertEqual(artifact.quantization.nominal_bits, 4)

    def test_identifier_can_be_unknown(self):
        self.assertIsNone(_artifact(identifier=None).identifier)

    def test_storage_is_not_runtime_memory(self):
        for field_name in ("runtime_memory", "vram_required", "ram_required",
                           "estimated_memory"):
            self.assertFalse(hasattr(md.ModelArtifact, field_name))


class ModelCapabilitiesTests(unittest.TestCase):
    def test_all_unknown_by_default(self):
        capabilities = md.ModelCapabilities()
        self.assertIsNone(capabilities.text_generation)
        self.assertIsNone(capabilities.code_generation)
        self.assertIsNone(capabilities.vision)
        self.assertIsNone(capabilities.embeddings)
        self.assertIsNone(capabilities.tool_use)

    def test_mixed_states(self):
        capabilities = md.ModelCapabilities(
            text_generation=True,
            code_generation=True,
            vision=False,
            embeddings=None,
            tool_use=None,
        )
        self.assertTrue(capabilities.text_generation)
        self.assertFalse(capabilities.vision)
        self.assertIsNone(capabilities.embeddings)

    def test_non_bool_rejected(self):
        with self.assertRaises(ValueError):
            md.ModelCapabilities(vision="yes")


class ModelTests(unittest.TestCase):
    def _model(self, **overrides):
        fields = {"identity": _identity(), **overrides}
        return md.Model(**fields)

    def test_model_without_artifacts(self):
        model = self._model()
        self.assertEqual(model.artifacts, ())

    def test_model_with_one_artifact(self):
        model = self._model(artifacts=(_artifact(),))
        self.assertEqual(len(model.artifacts), 1)

    def test_model_with_multiple_artifacts(self):
        model = self._model(artifacts=(
            _artifact(identifier="q4"),
            _artifact(identifier="q8", quantization=md.ModelQuantization(
                md.QuantizationStatus.QUANTIZED, "Q8_0", 8)),
            _artifact(identifier="bf16", format="Safetensors",
                      precision=md.ModelPrecision("BF16", 16),
                      quantization=md.ModelQuantization(
                          md.QuantizationStatus.NOT_QUANTIZED)),
        ))
        self.assertEqual(len(model.artifacts), 3)

    def test_list_artifacts_are_frozen_into_a_tuple(self):
        model = self._model(artifacts=[_artifact()])
        self.assertIsInstance(model.artifacts, tuple)

    def test_max_context_valid(self):
        model = self._model(max_context=262144)
        self.assertEqual(model.max_context, 262144)

    def test_max_context_unknown(self):
        self.assertIsNone(self._model(max_context=None).max_context)

    def test_max_context_invalid_rejected(self):
        for value in (0, -1, "256k"):
            with self.assertRaises(ValueError):
                self._model(max_context=value)

    def test_wrong_section_types_rejected(self):
        with self.assertRaises(ValueError):
            self._model(identity="Qwen")
        with self.assertRaises(ValueError):
            self._model(provenance="huggingface")
        with self.assertRaises(ValueError):
            self._model(architecture={"parameters": 30})
        with self.assertRaises(ValueError):
            self._model(capabilities=["vision"])

    def test_non_artifact_members_rejected(self):
        with self.assertRaises(ValueError):
            self._model(artifacts=("q4_k_m.gguf",))

    def test_frozen_structures(self):
        model = self._model(
            provenance=md.ModelProvenance(source="huggingface"),
            architecture=md.ModelArchitecture(parameters=30_000_000_000),
            capabilities=md.ModelCapabilities(text_generation=True),
            max_context=262144,
            artifacts=(_artifact(),),
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            model.max_context = 1
        with self.assertRaises(dataclasses.FrozenInstanceError):
            model.identity.model_id = "x"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            model.artifacts[0].storage_size_bytes = 1
        with self.assertRaises(AttributeError):
            model.artifacts.append(_artifact())
        with self.assertRaises(TypeError):
            model.artifacts[0] = _artifact()

    def test_model_carries_no_conclusions(self):
        for field_name in ("compatible", "can_run", "recommended_gpu",
                           "recommended_vram", "recommended_ram",
                           "estimated_memory", "performance"):
            self.assertFalse(hasattr(md.Model, field_name))

    def test_unknown_is_never_invented_by_constructors(self):
        model = self._model()
        self.assertIsNone(model.provenance.source)
        self.assertIsNone(model.architecture.parameters)
        self.assertIsNone(model.architecture.active_parameters)
        self.assertIsNone(model.capabilities.vision)
        self.assertIsNone(model.max_context)


class PurityTests(unittest.TestCase):
    """B8.1 must be a pure domain: no I/O, no execution surface."""

    def test_module_imports_are_pure(self):
        source = Path(md.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertIn(
                    node.module, {"__future__", "dataclasses", "enum"})

    def test_no_io_helpers_exposed(self):
        for name in ("subprocess", "os", "socket", "urllib", "requests"):
            self.assertFalse(hasattr(md, name), name)

    def test_no_executable_surface(self):
        def explode(*args, **kwargs):
            raise AssertionError("B8.1 must never execute anything")

        with patch("subprocess.run", side_effect=explode), patch(
            "socket.socket", side_effect=explode
        ):
            model = md.Model(identity=_identity())
        self.assertEqual(model.artifacts, ())


if __name__ == "__main__":
    unittest.main()
