# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared construction and validation for one-shot execution runners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeGuard

from .execution import ExecutionTarget
from .runner import ExecutionRunner, ExecutionRunnerLike, LlamaCppRunner
from .runtimes import RuntimeCapability
from .sycl_runner import SyclLlamaRunner

__all__ = [
    "ExecutionRunner",
    "RunnerFactoryDependencies",
    "RunnerFactoryError",
    "create_runner",
]


class RunnerFactoryError(Exception):
    """A runner could not be validated or constructed for the selected target."""


def _build_sycl_runner(capability: RuntimeCapability) -> ExecutionRunner:
    from .sycl_runner import build_sycl_runner

    return build_sycl_runner(capability=capability)


@dataclass(frozen=True)
class RunnerFactoryDependencies:
    """Typed construction seams for runner-factory tests and compositions."""

    llama_cpp_factory: (
        Callable[[RuntimeCapability], ExecutionRunner] | None
    ) = None
    sycl_factory: Callable[[RuntimeCapability], ExecutionRunner] | None = None


def _is_execution_runner(candidate: object) -> TypeGuard[ExecutionRunnerLike]:
    return callable(getattr(candidate, "run", None))


def _validate_runner(
    runner: object,
    backend: str,
) -> ExecutionRunnerLike:
    if not _is_execution_runner(runner):
        raise RunnerFactoryError(
            "Injected runner must provide a callable run method"
        )
    if backend == "SYCL" and not isinstance(runner, SyclLlamaRunner):
        raise RunnerFactoryError(
            "Injected runner is not a SyclLlamaRunner; cannot satisfy SYCL target"
        )
    if backend in {"CPU", "Vulkan"} and isinstance(runner, SyclLlamaRunner):
        raise RunnerFactoryError(
            f"SyclLlamaRunner cannot satisfy {backend} target"
        )
    return runner


def create_runner(
    capability: RuntimeCapability,
    target: ExecutionTarget,
    *,
    configured_runner: ExecutionRunnerLike | None = None,
    dependencies: RunnerFactoryDependencies | None = None,
) -> ExecutionRunnerLike:
    """Validate an injected runner or construct the runner for ``target``.

    CPU and Vulkan use ``LlamaCppRunner``; SYCL uses the existing
    ``build_sycl_runner`` integration. No backend fallback is attempted.
    """
    if not isinstance(capability, RuntimeCapability):
        raise RunnerFactoryError("Runtime capability has an invalid type")
    if not isinstance(target, ExecutionTarget):
        raise RunnerFactoryError("Execution target has an invalid type")
    if not capability.invocable:
        raise RunnerFactoryError("Runtime capability is not invocable")
    if not capability.supports_runtime_name(target.runtime):
        raise RunnerFactoryError(
            "Execution target runtime does not match the runtime capability"
        )

    backend = target.backend
    if backend not in {"CPU", "Vulkan", "SYCL"}:
        raise RunnerFactoryError(
            f"Unsupported backend: {backend!r}. Supported backends are: "
            "CPU, Vulkan, SYCL"
        )
    if backend not in capability.supported_backends:
        raise RunnerFactoryError(
            f"Runtime capability does not support target backend {backend!r}"
        )
    if backend == "SYCL" and capability.name != "llama.cpp SYCL":
        raise RunnerFactoryError(
            "SYCL target requires a llama.cpp SYCL runtime capability"
        )

    if configured_runner is not None:
        return _validate_runner(configured_runner, backend)

    deps = dependencies if dependencies is not None else RunnerFactoryDependencies()
    factory = (
        deps.sycl_factory
        if backend == "SYCL"
        else deps.llama_cpp_factory
    )
    if factory is None:
        factory = _build_sycl_runner if backend == "SYCL" else LlamaCppRunner
    try:
        runner = factory(capability)
    except (OSError, ValueError) as error:
        raise RunnerFactoryError(
            f"Unable to construct {backend} runner: {error}"
        ) from error
    return _validate_runner(runner, backend)
