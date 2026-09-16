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

"""Block B2 tests: pure diagnosis/recommendation (no hardware, no I/O)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from app import gpu_diagnosis as dg
from app.gpu_setup import FunctionalCheck, GpuSoftwareStatus
from app.hardware import GPUInfo


def _check(passed):
    return FunctionalCheck(passed, "detail", "test")


def _status(kernel, drm, vulkan):
    return GpuSoftwareStatus(
        kernel_driver=_check(kernel),
        drm_device=_check(drm),
        vulkan=_check(vulkan),
    )


class MatrixTests(unittest.TestCase):
    def test_all_true_is_ready(self):
        result = dg.diagnose(_status(True, True, True), "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.READY)
        self.assertEqual(result.missing_components, ())
        self.assertEqual(result.warnings, ())
        rec = dg.recommend(result)
        self.assertEqual(rec.status, dg.DiagnosisStatus.READY)
        self.assertIsNone(rec.recipe_ref)
        self.assertEqual(rec.verify_commands, ())

    def test_each_false_component_is_missing(self):
        cases = (
            ((False, True, True), dg.GpuComponent.KERNEL_DRIVER),
            ((True, False, True), dg.GpuComponent.DRM_DEVICE),
            ((True, True, False), dg.GpuComponent.VULKAN_FUNCTIONAL),
        )
        for values, component in cases:
            with self.subTest(values=values):
                result = dg.diagnose(
                    _status(*values), "llama.cpp", "Vulkan", platform="linux")
                self.assertEqual(result.status, dg.DiagnosisStatus.MISSING_COMPONENT)
                self.assertEqual(
                    [m.component for m in result.missing_components], [component])
                rec = dg.recommend(result)
                self.assertEqual(rec.status, dg.DiagnosisStatus.MISSING_COMPONENT)
                self.assertIsNotNone(rec.recipe_ref)
                self.assertEqual(rec.recipe_refs, (rec.recipe_ref,))

    def test_each_none_is_unknown_never_missing(self):
        for values in ((None, True, True), (True, None, True), (True, True, None)):
            with self.subTest(values=values):
                result = dg.diagnose(_status(*values), "llama.cpp", "Vulkan")
                self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)
                self.assertEqual(result.missing_components, ())

    def test_false_prevails_over_none(self):
        result = dg.diagnose(_status(False, None, None), "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(len(result.missing_components), 1)

    def test_all_none_is_unknown(self):
        result = dg.diagnose(_status(None, None, None), "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)
        self.assertEqual(result.missing_components, ())

    def test_cpu_is_ready_without_gpu_software(self):
        result = dg.diagnose(_status(None, None, None), "llama.cpp", "CPU")
        self.assertEqual(result.status, dg.DiagnosisStatus.READY)
        self.assertEqual(result.missing_components, ())

    def test_cpu_is_ready_even_with_all_false_gpu_facts(self):
        result = dg.diagnose(_status(False, False, False), "llama.cpp", "CPU")
        self.assertEqual(result.status, dg.DiagnosisStatus.READY)
        self.assertEqual(result.missing_components, ())

    def test_all_false_lists_every_missing_component(self):
        result = dg.diagnose(_status(False, False, False), "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(
            [m.component for m in result.missing_components],
            [
                dg.GpuComponent.KERNEL_DRIVER,
                dg.GpuComponent.DRM_DEVICE,
                dg.GpuComponent.VULKAN_FUNCTIONAL,
            ],
        )

    def test_missing_component_carries_explicit_evidence(self):
        check = FunctionalCheck(False, "no render nodes", "filesystem:/dev/dri")
        status = GpuSoftwareStatus(kernel_driver=check)
        result = dg.diagnose(status, "llama.cpp", "Vulkan")
        (missing,) = result.missing_components
        self.assertIs(missing.evidence, check)
        self.assertEqual(missing.component, dg.GpuComponent.KERNEL_DRIVER)
        self.assertEqual(missing.required_by, "llama.cpp + Vulkan")

    def test_cpu_is_ready_even_with_all_true_gpu_facts(self):
        result = dg.diagnose(_status(True, True, True), "llama.cpp", "CPU")
        self.assertEqual(result.status, dg.DiagnosisStatus.READY)
        self.assertEqual(result.missing_components, ())
        self.assertEqual(result.warnings, ())


class MissingComponentInvariantTests(unittest.TestCase):
    """Only explicit absence evidence may become a MissingComponent."""

    def test_explicit_false_evidence_is_valid(self):
        evidence = FunctionalCheck(
            False, "no Vulkan device", "llama --list-devices")
        missing = dg.MissingComponent(
            dg.GpuComponent.VULKAN_FUNCTIONAL, evidence, "llama.cpp + Vulkan")
        self.assertIs(missing.evidence, evidence)

    def test_true_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            dg.MissingComponent(
                dg.GpuComponent.VULKAN_FUNCTIONAL,
                _check(True),
                "llama.cpp + Vulkan")

    def test_unknown_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            dg.MissingComponent(
                dg.GpuComponent.VULKAN_FUNCTIONAL,
                _check(None),
                "llama.cpp + Vulkan")


class VendorSeparationTests(unittest.TestCase):
    """GPU vendor lives in GPUInfo and must never change the diagnosis."""

    _GPUS = (
        None,
        GPUInfo(vendor="Intel", name="Arc B580", pci_id="8086:e20b", driver="xe"),
        GPUInfo(vendor="NVIDIA", name="RTX 3060", pci_id="10de:2503", driver="nvidia"),
        GPUInfo(vendor="AMD", name="Radeon RX 6700", pci_id="1002:73df", driver="amdgpu"),
    )

    def test_vendor_never_alters_the_diagnosis(self):
        for facts in (
            (True, True, True),
            (False, False, False),
            (True, None, False),
            (None, None, None),
            (True, None, True),
        ):
            baseline = dg.diagnose(_status(*facts), "llama.cpp", "Vulkan")
            for gpu in self._GPUS:
                with self.subTest(facts=facts, gpu=gpu):
                    result = dg.diagnose(
                        _status(*facts), "llama.cpp", "Vulkan", gpu=gpu)
                    self.assertEqual(result, baseline)

    def test_vendor_never_alters_the_matrix(self):
        software = _status(True, True, True)
        for runtime, backend, expected in (
            ("llama.cpp", "CPU", dg.DiagnosisStatus.READY),
            ("llama.cpp", "Vulkan", dg.DiagnosisStatus.READY),
            ("Ollama", "Vulkan", dg.DiagnosisStatus.UNKNOWN),
            ("llama.cpp", "CUDA", dg.DiagnosisStatus.UNKNOWN),
            ("llama.cpp", "ROCm", dg.DiagnosisStatus.UNKNOWN),
        ):
            baseline = dg.diagnose(software, runtime, backend)
            self.assertEqual(baseline.status, expected)
            for gpu in self._GPUS:
                with self.subTest(runtime=runtime, backend=backend, gpu=gpu):
                    self.assertEqual(
                        dg.diagnose(software, runtime, backend, gpu=gpu), baseline)


class MatrixKeyTests(unittest.TestCase):
    def test_requirements_lookup_is_case_and_space_insensitive(self):
        expected = [
            dg.GpuComponent.KERNEL_DRIVER,
            dg.GpuComponent.DRM_DEVICE,
            dg.GpuComponent.VULKAN_FUNCTIONAL,
        ]
        for runtime, backend in (
            ("llama.cpp", "Vulkan"),
            ("llama.cpp", "vulkan"),
            ("LLAMA.CPP", "VULKAN"),
            (" llama.cpp ", " Vulkan "),
        ):
            with self.subTest(runtime=runtime, backend=backend):
                requirements = dg.requirements_for(runtime, backend)
                self.assertEqual(
                    [r.component for r in requirements], expected)

    def test_cpu_requires_no_gpu_components(self):
        self.assertEqual(dg.requirements_for("llama.cpp", "CPU"), ())
        self.assertEqual(dg.requirements_for("llama.cpp", "cpu"), ())

    def test_unmodelled_pairs_have_no_requirements(self):
        for runtime, backend in (
            ("Ollama", "Vulkan"),
            ("llama.cpp", "CUDA"),
            ("llama.cpp", "ROCm"),
            ("NVIDIA", "Vulkan"),
            ("AMD", "Vulkan"),
        ):
            with self.subTest(runtime=runtime, backend=backend):
                self.assertIsNone(dg.requirements_for(runtime, backend))


class NoneSoftwareTests(unittest.TestCase):
    def test_none_software_vulkan_is_unknown_never_missing(self):
        result = dg.diagnose(None, "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)
        self.assertEqual(result.missing_components, ())
        self.assertTrue(result.warnings)

    def test_none_software_cpu_is_ready(self):
        result = dg.diagnose(None, "llama.cpp", "CPU")
        self.assertEqual(result.status, dg.DiagnosisStatus.READY)
        self.assertEqual(result.missing_components, ())
        self.assertEqual(result.warnings, ())

    def test_diagnosis_is_deterministic(self):
        first = dg.diagnose(_status(True, None, False), "llama.cpp", "Vulkan")
        second = dg.diagnose(
            _status(True, None, False), " llama.cpp ", " vulkan ")
        self.assertEqual(first.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(first, second)

    def test_gpu_info_is_context_only_h1(self):
        gpu = GPUInfo(name="Intel Arc B580", vendor="Intel", driver="xe")
        base = dg.diagnose(_status(True, True, True), "llama.cpp", "Vulkan")
        with_context = dg.diagnose(
            _status(True, True, True), "llama.cpp", "Vulkan", gpu=gpu)
        self.assertEqual(with_context, base)
        self.assertEqual(with_context.status, dg.DiagnosisStatus.READY)


class UnknownMatrixTests(unittest.TestCase):
    def test_unmodelled_combinations_are_unknown(self):
        for runtime, backend in (
            ("Ollama", "Vulkan"),
            ("llama.cpp", "CUDA"),
            ("llama.cpp", "ROCm"),
            ("NVIDIA", "Vulkan"),
            ("AMD", "Vulkan"),
            ("llama.cpp", "Vulkan-NVIDIA"),
        ):
            with self.subTest(runtime=runtime, backend=backend):
                result = dg.diagnose(_status(False, False, False), runtime, backend)
                self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)
                self.assertEqual(result.missing_components, ())
                self.assertTrue(result.warnings)

    def test_vendor_is_not_a_backend(self):
        for backend in ("NVIDIA", "AMD"):
            result = dg.diagnose(_status(True, True, True), "llama.cpp", backend)
            self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)


class DiagnosisContextTests(unittest.TestCase):
    """A diagnosis must retain enough context to resolve a recipe later."""

    def test_diagnosis_retains_canonical_context(self):
        result = dg.diagnose(
            _status(True, True, True), " llama.cpp ", " Vulkan ")
        self.assertEqual(result.runtime, "llama.cpp")
        self.assertEqual(result.backend, "vulkan")
        self.assertEqual(result.platform, "")

    def test_diagnosis_retains_explicit_platform(self):
        result = dg.diagnose(
            _status(True, True, True), "llama.cpp", "Vulkan",
            platform=" LiNuX ")
        self.assertEqual(result.platform, "linux")

    def test_diagnosis_platform_is_unknown_by_default(self):
        """No operating system is assumed: the default platform is unknown."""
        result = dg.diagnose(_status(False, True, True), "llama.cpp", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(result.platform, "")
        rec = dg.recommend(result)
        self.assertIsNone(rec.recipe_ref)
        self.assertEqual(rec.recipe_refs, ())

    def test_unmodelled_diagnosis_retains_context(self):
        result = dg.diagnose(_status(True, True, True), "Ollama", "Vulkan")
        self.assertEqual(result.runtime, "ollama")
        self.assertEqual(result.backend, "vulkan")


class RecommendTests(unittest.TestCase):
    def test_recommend_ready_and_unknown_have_no_recipe(self):
        diagnoses = (
            dg.diagnose(_status(True, True, True), "llama.cpp", "Vulkan"),
            dg.diagnose(_status(None, None, None), "llama.cpp", "Vulkan"),
            dg.diagnose(None, "llama.cpp", "Vulkan"),
        )
        for diagnosis in diagnoses:
            with self.subTest(status=diagnosis.status):
                rec = dg.recommend(diagnosis)
                self.assertEqual(rec.status, diagnosis.status)
                self.assertEqual(
                    rec.missing_components, diagnosis.missing_components)
                self.assertEqual(rec.warnings, diagnosis.warnings)
                self.assertIsNone(rec.recipe_ref)
                self.assertEqual(rec.recipe_refs, ())
                self.assertEqual(rec.verify_commands, ())

    def test_recommend_unknown_has_no_recipe(self):
        result = dg.diagnose(_status(False, False, False), "Ollama", "Vulkan")
        self.assertEqual(result.status, dg.DiagnosisStatus.UNKNOWN)
        rec = dg.recommend(result)
        self.assertIsNone(rec.recipe_ref)
        self.assertEqual(rec.recipe_refs, ())

    def test_recommend_propagates_missing_components_and_warnings(self):
        result = dg.diagnose(_status(True, False, None), "llama.cpp", "Vulkan")
        rec = dg.recommend(result)
        self.assertEqual(rec.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(rec.missing_components, result.missing_components)
        self.assertEqual(rec.warnings, result.warnings)

    def test_recommend_missing_component_resolves_recipe(self):
        result = dg.diagnose(
            _status(True, False, True), "llama.cpp", "Vulkan",
            platform="linux")
        rec = dg.recommend(result)
        self.assertEqual(rec.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(
            rec.recipe_ref, "linux-llama-cpp-vulkan-drm-device")
        self.assertEqual(
            rec.recipe_refs, ("linux-llama-cpp-vulkan-drm-device",))
        self.assertEqual(rec.missing_components, result.missing_components)

    def test_recommend_keeps_a_recipe_per_missing_component(self):
        result = dg.diagnose(
            _status(False, False, False), "llama.cpp", "Vulkan",
            platform="linux")
        self.assertEqual(len(result.missing_components), 3)
        rec = dg.recommend(result)
        self.assertEqual(len(rec.recipe_refs), 3)
        self.assertEqual(len(set(rec.recipe_refs)), 3)
        self.assertEqual(rec.recipe_ref, rec.recipe_refs[0])

    def test_recommend_unsupported_or_unknown_platform_has_no_recipe(self):
        for platform in ("windows", ""):
            with self.subTest(platform=platform):
                result = dg.diagnose(
                    _status(False, True, True), "llama.cpp", "Vulkan",
                    platform=platform)
                self.assertEqual(
                    result.status, dg.DiagnosisStatus.MISSING_COMPONENT)
                rec = dg.recommend(result)
                self.assertIsNone(rec.recipe_ref)
                self.assertEqual(rec.recipe_refs, ())
                # A missing component without a compatible recipe is not an
                # error: the missing component is still preserved.
                self.assertEqual(
                    len(rec.missing_components), 1)

    def test_recommend_missing_component_state_is_explicit(self):
        result = dg.diagnose(_status(False, None, None), "llama.cpp", "Vulkan")
        rec = dg.recommend(result)
        self.assertEqual(rec.status, dg.DiagnosisStatus.MISSING_COMPONENT)
        self.assertEqual(len(rec.missing_components), 1)
        self.assertEqual(
            rec.warnings,
            ("drm_device status unknown", "vulkan_functional status unknown"))


class ModelTests(unittest.TestCase):
    def test_models_are_immutable_per_field(self):
        objs = (
            dg.SoftwareRequirement(
                dg.GpuComponent.DRM_DEVICE, "llama.cpp + Vulkan", "why"),
            dg.MissingComponent(
                dg.GpuComponent.DRM_DEVICE, _check(False), "llama.cpp + Vulkan"),
            dg.DiagnosisResult(dg.DiagnosisStatus.READY),
            dg.Recommendation(dg.DiagnosisStatus.READY),
        )
        field_names = (
            "status", "component", "required_for", "why", "evidence",
            "required_by", "missing_components", "warnings",
            "recipe_ref", "verify_commands", "recipe_refs",
            "runtime", "backend", "platform",
        )
        for obj in objs:
            for field_name in field_names:
                if not hasattr(obj, field_name):
                    continue
                with self.subTest(model=type(obj).__name__, field=field_name):
                    with self.assertRaises(AttributeError):
                        setattr(obj, field_name, None)

    def test_missing_component_recommends_recipe_without_install(self):
        result = dg.diagnose(
            _status(False, True, True), "llama.cpp", "Vulkan",
            platform="linux")
        rec = dg.recommend(result)
        self.assertEqual(
            rec.recipe_ref, "linux-llama-cpp-vulkan-kernel-driver")
        # B3 recipes are declarative: no install command is surfaced or run
        # and the catalog currently defines no verify commands yet.
        self.assertEqual(rec.verify_commands, ())

    def test_models_are_immutable(self):
        result = dg.diagnose(
            _status(False, True, True), "llama.cpp", "Vulkan",
            platform="linux")
        rec = dg.recommend(result)
        with self.assertRaises(AttributeError):
            result.missing_components = ()  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            rec.recipe_refs = ()  # type: ignore[misc]

    def test_side_effect_safety(self):
        source = Path(dg.__file__).read_text(encoding="utf-8")
        # AST ignores license comments, including the Apache URL. Allow only
        # model imports from detection modules plus the pure recipe lookup,
        # never probe functions or anything performing I/O.
        tree = ast.parse(source)
        allowed_imports = {
            (0, "__future__"): {"annotations"},
            (0, "dataclasses"): {"dataclass"},
            (0, "enum"): {"Enum"},
            (1, "gpu_setup"): {"FunctionalCheck", "GpuSoftwareStatus"},
            (1, "hardware"): {"GPUInfo"},
            (1, "gpu_recipes"): {"find_recipe"},
        }
        allowed_calls = {
            "dataclass", "ValueError", "SoftwareRequirement",
            "MissingComponent", "DiagnosisResult", "Recommendation",
            "_canonical", "requirements_for", "getattr", "tuple",
            "find_recipe",
        }
        allowed_methods = {"strip", "lower", "get", "append", "extend"}
        for node in ast.walk(tree):
            with self.subTest(node=type(node).__name__, line=getattr(node, "lineno", 0)):
                self.assertNotIsInstance(node, ast.Import)
                if isinstance(node, ast.ImportFrom):
                    key = (node.level, node.module)
                    self.assertIn(key, allowed_imports)
                    for alias in node.names:
                        self.assertIn(alias.name, allowed_imports[key])
                        self.assertIsNone(alias.asname)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertIn(node.func.id, allowed_calls)
                    else:
                        self.assertIsInstance(node.func, ast.Attribute)
                        self.assertIn(node.func.attr, allowed_methods)
                    self.assertFalse(any(k.arg == "shell" for k in node.keywords))


if __name__ == "__main__":
    unittest.main()
