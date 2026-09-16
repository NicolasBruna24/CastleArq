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

"""Block B5 tests: declarative remediation planning (no execution)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as cli
from app import remediation as rem
from app.gpu_diagnosis import GpuComponent, diagnose
from app.gpu_recipes import GpuRecipe
from app.gpu_setup import FunctionalCheck, GpuSoftwareStatus
from app.hardware import CPUInfo, HardwareSnapshot, MemoryInfo

RESOLVE = rem.RemediationActionKind.RESOLVE_COMPONENT
VERIFY = rem.RemediationActionKind.VERIFY_COMPONENT
REDIAGNOSE = rem.RemediationActionKind.REDIAGNOSE


def _status(kernel, drm, vulkan) -> GpuSoftwareStatus:
    return GpuSoftwareStatus(
        kernel_driver=FunctionalCheck(kernel, "detail", "test"),
        drm_device=FunctionalCheck(drm, "detail", "test"),
        vulkan=FunctionalCheck(vulkan, "detail", "test"),
    )


def _diagnosis(kernel, drm, vulkan, *, backend="vulkan", platform="linux"):
    return diagnose(
        _status(kernel, drm, vulkan),
        "llama.cpp",
        backend,
        platform=platform,
    )


def _full_recipe(component: GpuComponent) -> GpuRecipe:
    return GpuRecipe(
        id=f"recipe-{component.value}",
        name=f"Full remediation for {component.value}",
        runtime="llama.cpp",
        backend="vulkan",
        component=component,
        description="declarative recipe used by tests",
        install_commands=(f"install {component.value}",),
        verify_commands=(f"verify {component.value}",),
        platforms=("linux",),
    )


def _recipe_lookup(runtime, backend, component, platform):
    return _full_recipe(component)


def _hardware(gpus=()) -> HardwareSnapshot:
    return HardwareSnapshot(
        operating_system="Linux",
        architecture="x86_64",
        cpu=CPUInfo(model="Test CPU"),
        memory=MemoryInfo(total_bytes=8 * 1024 ** 3),
        gpus=list(gpus),
    )


class FullPlanTests(unittest.TestCase):
    def test_all_missing_grouped_into_single_plan(self):
        with patch("app.remediation.find_recipe", side_effect=_recipe_lookup):
            plan = rem.build_remediation_plan(_diagnosis(False, False, False))
        self.assertEqual(plan.status, rem.RemediationStatus.READY)
        self.assertEqual(len(plan.problems), 3)
        self.assertEqual(
            plan.recipe_refs,
            (
                "recipe-kernel_driver",
                "recipe-drm_device",
                "recipe-vulkan_functional",
            ),
        )
        self.assertEqual(
            [action.kind for action in plan.actions],
            [RESOLVE, RESOLVE, RESOLVE, VERIFY, VERIFY, VERIFY, REDIAGNOSE],
        )
        self.assertEqual([action.order for action in plan.actions], list(range(1, 8)))
        self.assertEqual(
            plan.install_commands,
            (
                "install kernel_driver",
                "install drm_device",
                "install vulkan_functional",
            ),
        )
        self.assertEqual(
            plan.verify_commands,
            (
                "verify kernel_driver",
                "verify drm_device",
                "verify vulkan_functional",
            ),
        )
        self.assertTrue(plan.requires_authorization)
        self.assertEqual(plan.actions[-1].kind, REDIAGNOSE)

    def test_order_is_deterministic(self):
        with patch("app.remediation.find_recipe", side_effect=_recipe_lookup):
            first = rem.build_remediation_plan(_diagnosis(False, False, False))
            second = rem.build_remediation_plan(_diagnosis(False, False, False))
        self.assertEqual(first, second)


class SingleComponentTests(unittest.TestCase):
    def test_single_missing_component_uses_catalog_recipe(self):
        plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        self.assertEqual(plan.status, rem.RemediationStatus.PARTIAL)
        self.assertEqual(len(plan.problems), 1)
        self.assertEqual(plan.recipe_refs, ("linux-llama-cpp-vulkan",))
        self.assertEqual(
            [action.kind for action in plan.actions], [RESOLVE, VERIFY, REDIAGNOSE]
        )
        resolve = plan.actions[0]
        self.assertEqual(resolve.component, GpuComponent.VULKAN_FUNCTIONAL)
        self.assertEqual(resolve.recipe_ref, "linux-llama-cpp-vulkan")
        self.assertEqual(resolve.description, "Resolve Vulkan runtime")
        self.assertEqual(plan.actions[1].description, "Verify Vulkan runtime")


class NoRecipeTests(unittest.TestCase):
    def test_missing_without_recipe_needs_research(self):
        plan = rem.build_remediation_plan(
            _diagnosis(True, True, False, platform="")
        )
        self.assertEqual(plan.status, rem.RemediationStatus.NEEDS_RESEARCH)
        self.assertEqual(len(plan.problems), 1)
        problem = plan.problems[0]
        self.assertIsNone(problem.recipe_ref)
        self.assertFalse(problem.has_install_commands)
        self.assertEqual(plan.actions, ())
        self.assertEqual(plan.recipe_refs, ())
        self.assertEqual(plan.install_commands, ())
        self.assertEqual(plan.verify_commands, ())
        self.assertFalse(plan.requires_authorization)
        self.assertTrue(
            any("research" in note for note in plan.notes), plan.notes)

    def test_no_recipe_never_invents_commands(self):
        plan = rem.build_remediation_plan(
            _diagnosis(False, False, False, platform="")
        )
        self.assertEqual(plan.status, rem.RemediationStatus.NEEDS_RESEARCH)
        self.assertEqual(plan.actions, ())
        self.assertEqual(plan.install_commands, ())
        self.assertEqual(plan.verify_commands, ())
        self.assertTrue(all(p.recipe_ref is None for p in plan.problems))


class PartialPlanTests(unittest.TestCase):
    def test_recipe_without_commands_is_partial_and_never_invents(self):
        plan = rem.build_remediation_plan(_diagnosis(False, False, False))
        self.assertEqual(plan.status, rem.RemediationStatus.PARTIAL)
        self.assertEqual(plan.install_commands, ())
        self.assertEqual(plan.verify_commands, ())
        for action in plan.actions:
            self.assertEqual(action.commands, ())
        self.assertTrue(
            any("conceptual" in note for note in plan.notes), plan.notes)
        self.assertTrue(plan.requires_authorization)

    def test_verify_commands_are_carried_in_the_plan(self):
        def verify_only(runtime, backend, component, platform):
            return GpuRecipe(
                id="verify-only",
                name="Verify-only recipe",
                runtime="llama.cpp",
                backend="vulkan",
                component=component,
                description="no install commands",
                install_commands=(),
                verify_commands=("llama --list-devices",),
                platforms=("linux",),
            )

        with patch("app.remediation.find_recipe", side_effect=verify_only):
            plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        self.assertEqual(plan.recipe_refs, ("verify-only",))
        self.assertEqual(plan.verify_commands, ("llama --list-devices",))
        verify_actions = [
            action for action in plan.actions
            if action.kind is rem.RemediationActionKind.VERIFY_COMPONENT
        ]
        self.assertEqual(verify_actions[0].commands, ("llama --list-devices",))
        self.assertEqual(plan.install_commands, ())
        self.assertEqual(plan.status, rem.RemediationStatus.PARTIAL)


class AuthorizationTests(unittest.TestCase):
    def test_partial_plan_requires_authorization(self):
        plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        self.assertTrue(plan.requires_authorization)

    def test_ready_plan_requires_authorization(self):
        with patch("app.remediation.find_recipe", side_effect=_recipe_lookup):
            plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        self.assertEqual(plan.status, rem.RemediationStatus.READY)
        self.assertTrue(plan.requires_authorization)

    def test_no_actions_means_no_authorization(self):
        plan = rem.build_remediation_plan(
            _diagnosis(True, True, False, platform="")
        )
        self.assertEqual(plan.actions, ())
        self.assertFalse(plan.requires_authorization)


class ReadyAndUnknownTests(unittest.TestCase):
    def test_ready_diagnosis_has_no_actions(self):
        plan = rem.build_remediation_plan(_diagnosis(True, True, True))
        self.assertEqual(plan.status, rem.RemediationStatus.NO_REMEDIATION)
        self.assertEqual(plan.actions, ())
        self.assertEqual(plan.problems, ())
        self.assertFalse(plan.requires_authorization)
        self.assertTrue(plan.notes)

    def test_unknown_maps_to_no_action_required_yet(self):
        diagnosis = diagnose(None, "llama.cpp", "vulkan", platform="linux")
        plan = rem.build_remediation_plan(diagnosis)
        self.assertEqual(
            plan.status, rem.RemediationStatus.NO_ACTION_REQUIRED_YET)

    def test_unknown_generates_no_actions_or_commands(self):
        diagnosis = diagnose(None, "llama.cpp", "vulkan", platform="linux")
        plan = rem.build_remediation_plan(diagnosis)
        self.assertEqual(plan.actions, ())
        self.assertEqual(plan.problems, ())
        self.assertEqual(plan.install_commands, ())
        self.assertEqual(plan.verify_commands, ())
        self.assertEqual(plan.recipe_refs, ())
        self.assertFalse(plan.requires_authorization)
        self.assertFalse(
            any(
                action.kind in (RESOLVE, VERIFY, REDIAGNOSE)
                for action in plan.actions
            )
        )

    def test_unknown_keeps_warnings_and_explains_uncertainty(self):
        diagnosis = diagnose(None, "llama.cpp", "vulkan", platform="linux")
        plan = rem.build_remediation_plan(diagnosis)
        self.assertTrue(plan.warnings)
        self.assertEqual(plan.warnings, diagnosis.warnings)
        self.assertTrue(
            any("UNKNOWN" in note for note in plan.notes), plan.notes)

    def test_objective_records_context(self):
        plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        self.assertIn("llama.cpp", plan.objective)
        self.assertIn("vulkan", plan.objective)
        self.assertIn("linux", plan.objective)


class ImmutabilityTests(unittest.TestCase):
    def test_plan_models_are_frozen(self):
        plan = rem.build_remediation_plan(_diagnosis(True, True, False))
        with self.assertRaises(AttributeError):
            plan.status = rem.RemediationStatus.READY
        with self.assertRaises(AttributeError):
            plan.actions[0].order = 99
        with self.assertRaises(AttributeError):
            plan.problems[0].recipe_ref = "changed"
        self.assertIsInstance(plan.actions, tuple)
        self.assertIsInstance(plan.problems, tuple)


class NoExecutionTests(unittest.TestCase):
    """B5 builds data only: no shell, no subprocess, no packages, no files."""

    def test_source_has_no_execution_or_network_surface(self):
        source = Path(rem.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed_imports = {
            (0, "__future__"): {"annotations"},
            (0, "dataclasses"): {"dataclass"},
            (0, "enum"): {"Enum"},
            (1, "gpu_diagnosis"): {
                "DiagnosisResult",
                "DiagnosisStatus",
                "GpuComponent",
                "MissingComponent",
            },
            (1, "gpu_recipes"): {"GpuRecipe", "find_recipe"},
        }
        allowed_calls = {
            "dataclass",
            "RemediationPlan",
            "RemediationProblem",
            "RemediationAction",
            "_objective",
            "_component_label",
            "_no_remediation_plan",
            "_problems_and_recipes",
            "find_recipe",
            "bool",
            "any",
            "all",
            "tuple",
        }
        allowed_methods = {"append", "extend", "get"}
        for node in ast.walk(tree):
            with self.subTest(
                node=type(node).__name__, line=getattr(node, "lineno", 0)
            ):
                self.assertNotIsInstance(node, ast.Import)
                if isinstance(node, ast.ImportFrom):
                    key = (node.level, node.module)
                    self.assertIn(key, allowed_imports)
                    for alias in node.names:
                        self.assertIn(alias.name, allowed_imports[key])
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertIn(node.func.id, allowed_calls)
                    else:
                        self.assertIsInstance(node.func, ast.Attribute)
                        self.assertIn(node.func.attr, allowed_methods)
                    self.assertFalse(any(k.arg == "shell" for k in node.keywords))

    def test_module_has_no_execution_helpers(self):
        for name in ("subprocess", "os", "shutil", "socket", "urllib"):
            self.assertFalse(hasattr(rem, name), name)


class CliIntegrationTests(unittest.TestCase):
    def _report(self, software):
        return cli.build_gpu_diagnosis_report(
            hardware=_hardware(),
            software=software,
            runtime="llama.cpp / llama.app",
            backend="Vulkan",
            platform="linux",
        )

    def test_diagnose_report_shows_declarative_plan(self):
        report = self._report(_status(False, False, False))
        text = cli.format_gpu_diagnosis_report(report)
        self.assertIn("Remediation plan", text)
        self.assertIn("1. Resolve Kernel driver", text)
        self.assertIn("4. Verify Kernel driver", text)
        self.assertIn("7. Re-run GPU diagnosis", text)
        self.assertIn("Authorization required: yes", text)
        self.assertIn("No actions have been executed.", text)

    def test_diagnose_report_never_executes_the_plan(self):
        report = self._report(_status(False, False, False))
        self.assertTrue(report.plan.requires_authorization)
        self.assertEqual(report.plan.recipe_refs, (
            "linux-llama-cpp-vulkan-kernel-driver",
            "linux-llama-cpp-vulkan-drm-device",
            "linux-llama-cpp-vulkan",
        ))
        for action in report.plan.actions:
            self.assertIsInstance(action.commands, tuple)


if __name__ == "__main__":
    unittest.main()
