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

"""Tests for the declarative GPU recipe catalog."""

from __future__ import annotations

import unittest

from app.gpu_diagnosis import GpuComponent
from app.gpu_recipes import GpuRecipe, find_recipe, recipe_for_component, recipes


class GpuRecipeTests(unittest.TestCase):
    def test_catalog_is_non_empty(self) -> None:
        self.assertTrue(recipes())

    def test_catalog_returns_immutable_tuple(self) -> None:
        self.assertIsInstance(recipes(), tuple)

    def test_find_kernel_driver_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.KERNEL_DRIVER,
            "linux",
        )

        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(
            recipe.id,
            "linux-llama-cpp-vulkan-kernel-driver",
        )
        self.assertEqual(recipe.component, GpuComponent.KERNEL_DRIVER)

    def test_find_drm_device_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.DRM_DEVICE,
            "linux",
        )

        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(recipe.component, GpuComponent.DRM_DEVICE)

    def test_find_vulkan_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.VULKAN_FUNCTIONAL,
            "linux",
        )

        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(recipe.component, GpuComponent.VULKAN_FUNCTIONAL)

    def test_runtime_and_backend_matching_is_case_insensitive(self) -> None:
        recipe = find_recipe(
            " LLAMA.CPP ",
            " VULKAN ",
            GpuComponent.KERNEL_DRIVER,
            " LiNuX ",
        )

        self.assertIsNotNone(recipe)

    def test_unknown_component_has_no_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.OPENCL,
            "linux",
        )

        self.assertIsNone(recipe)

    def test_unknown_runtime_has_no_recipe(self) -> None:
        recipe = find_recipe(
            "ollama",
            "vulkan",
            GpuComponent.KERNEL_DRIVER,
            "linux",
        )

        self.assertIsNone(recipe)

    def test_unknown_backend_has_no_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "cuda",
            GpuComponent.KERNEL_DRIVER,
            "linux",
        )

        self.assertIsNone(recipe)

    def test_unsupported_platform_has_no_recipe(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.KERNEL_DRIVER,
            "windows",
        )

        self.assertIsNone(recipe)

    def test_recipe_has_no_install_commands_by_default(self) -> None:
        """B3 describes recipes without pretending to provide commands yet."""
        for recipe in recipes():
            self.assertEqual(recipe.install_commands, ())

    def test_recipe_for_component_matches_find_recipe(self) -> None:
        direct = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.VULKAN_FUNCTIONAL,
            "linux",
        )
        alias = recipe_for_component(
            "llama.cpp",
            "vulkan",
            GpuComponent.VULKAN_FUNCTIONAL,
            "linux",
        )

        self.assertEqual(direct, alias)

    def test_platform_matching_is_case_insensitive(self) -> None:
        recipe = find_recipe(
            "llama.cpp",
            "vulkan",
            GpuComponent.VULKAN_FUNCTIONAL,
            "LINUX",
        )

        self.assertIsNotNone(recipe)

    def test_recipe_is_frozen(self) -> None:
        recipe = recipes()[0]

        self.assertIsInstance(recipe, GpuRecipe)

        with self.assertRaises(AttributeError):
            recipe.name = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
