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

"""Declarative GPU software recipes.

This module maps known missing GPU software components to installation and
verification instructions. It does not execute commands, inspect hardware,
touch the filesystem, or access the network.
"""

from __future__ import annotations

from dataclasses import dataclass

from .gpu_diagnosis import GpuComponent


@dataclass(frozen=True)
class GpuRecipe:
    """Declarative instructions for addressing one GPU software component."""

    id: str
    name: str
    runtime: str
    backend: str
    component: GpuComponent
    description: str
    install_commands: tuple[str, ...] = ()
    verify_commands: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()

    def supports_platform(self, platform: str) -> bool:
        """Return whether this recipe explicitly supports a platform."""
        return platform.strip().lower() in {
            item.strip().lower() for item in self.platforms
        }


_RECIPES: tuple[GpuRecipe, ...] = (
    GpuRecipe(
        id="linux-llama-cpp-vulkan-kernel-driver",
        name="Linux GPU kernel driver for Vulkan",
        runtime="llama.cpp",
        backend="vulkan",
        component=GpuComponent.KERNEL_DRIVER,
        description=(
            "Install and configure the Linux GPU kernel driver required "
            "for the selected Vulkan workload."
        ),
        platforms=("linux",),
    ),
    GpuRecipe(
        id="linux-llama-cpp-vulkan-drm-device",
        name="Linux DRM render device",
        runtime="llama.cpp",
        backend="vulkan",
        component=GpuComponent.DRM_DEVICE,
        description=(
            "Provide the Linux DRM/render device required for Vulkan "
            "userspace access to the GPU."
        ),
        platforms=("linux",),
    ),
    GpuRecipe(
        id="linux-llama-cpp-vulkan",
        name="Linux Vulkan runtime",
        runtime="llama.cpp",
        backend="vulkan",
        component=GpuComponent.VULKAN_FUNCTIONAL,
        description=(
            "Install or repair the Vulkan userspace/runtime components "
            "required by the selected workload."
        ),
        platforms=("linux",),
    ),
)


def _canonical(value: str) -> str:
    return value.strip().lower()


def recipes() -> tuple[GpuRecipe, ...]:
    """Return the complete immutable recipe catalog."""
    return _RECIPES


def find_recipe(
    runtime: str,
    backend: str,
    component: GpuComponent,
    platform: str,
) -> GpuRecipe | None:
    """Find a recipe matching runtime, backend, component and platform."""
    runtime_key = _canonical(runtime)
    backend_key = _canonical(backend)

    for recipe in _RECIPES:
        if (
            _canonical(recipe.runtime) == runtime_key
            and _canonical(recipe.backend) == backend_key
            and recipe.component is component
            and recipe.supports_platform(platform)
        ):
            return recipe

    return None


def recipe_for_component(
    runtime: str,
    backend: str,
    component: GpuComponent,
    platform: str,
) -> GpuRecipe | None:
    """Alias for :func:`find_recipe` with domain-oriented naming."""
    return find_recipe(runtime, backend, component, platform)
