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

"""B9.22 tests for the Execute Model composition root (real collaborators).

``tests/test_execute_model.py`` proves the use case with doubles; this module
proves the composition point itself: ``compose_execute_model_dependencies`` in
``app/application_wiring.py`` binds REAL infrastructure and the resulting
``ExecuteModelDependencies`` drives the REAL ``execute_model`` end to end —
real store, real catalog, real resolver, real legacy gate, real preflight,
real selector and the real ``LlamaCppRunner``. Nothing runs a model, downloads
an artifact or spawns a subprocess: the run stops inside the runner's own
input validation because the composed capability points at an absent
executable.

    W1 the composition returns a complete ``ExecuteModelDependencies``
    W2 ``runner`` is the concrete ``LlamaCppRunner`` (a ``ModelRunner``)
    W3 ``preflight_factory`` is the real ``ArtifactExecutionPreflight``
    W4 ``selector`` is the real ``RuntimeBackendSelector``
    W5 ``model_store`` is the real ``ModelStore``
    W6 ``models`` is the real catalog of ``get_catalog()``
    W7 structural boundary: composition root -> use case only; no product
       caller was created by this block; the use case keeps its B9.20 imports
    W8 the composed value feeds ``execute_model`` without ``_Harness``
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import application_wiring as wiring
from app import execute_model as em
from app.execution import (
    ArtifactExecutionPreflight,
    ExecutionErrorCode,
    ExecutionResult,
)
from app.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from app.model_catalog import get_catalog
from app.model_store import ModelStore
from app.models import ArtifactSpec, ArtifactState, ModelSpec
from app.runner import LlamaCppRunner, ModelRunner
from app.runtimes import BackendStatus, PromptInputMode, RuntimeCapability
from app.selection import RuntimeBackendSelector

# Files allowed to name the Execute composition function. Every other file in
# ``app/`` must stay unaware of it: B9.22 established the composition
# boundary; B9.23 authorized ``main.py`` as the first Product Caller; other
# Application/Infrastructure modules must not consume the composition root.
_COMPOSITION_ENTRY_POINTS = frozenset({"application_wiring.py", "main.py"})


def _capability(
    *,
    backends: tuple[str, ...] = ("CPU", "Vulkan"),
    executable_path: str = "/test-only/llama",
) -> RuntimeCapability:
    """An invocable capability whose executable deliberately does not exist."""
    arguments = tuple(
        (backend, "Vulkan0" if backend == "Vulkan" else "none")
        for backend in backends
    )
    return RuntimeCapability(
        name="llama.cpp CLI",
        executable_path=executable_path,
        version="wiring-test",
        supported_formats=("GGUF",),
        supported_backends=backends,
        prompt_input_modes=(PromptInputMode.ARGUMENT,),
        supports_one_shot=True,
        available=True,
        compatibility_names=("llama.cpp / llama.app",),
        backend_arguments=arguments,
    )


def _hardware(*, vram: int | None = 32 * 1024**3, ram: int = 48 * 1024**3):
    """Hardware snapshot favouring Vulkan, mirroring the integration fixture."""
    gpus = (
        [
            GPUInfo(
                name="Test Vulkan GPU",
                vendor="Test",
                vram_bytes=vram,
                vram_available_bytes=vram,
                backends=["Vulkan"],
            )
        ]
        if vram is not None
        else []
    )
    return HardwareSnapshot(
        operating_system="test",
        architecture="x86_64",
        cpu=CPUInfo(model="test"),
        memory=MemoryInfo(total_bytes=ram),
        gpus=gpus,
    )


class _Detection:
    """Stands in for ``detect_llama_capability`` and records every call."""

    def __init__(self, *capabilities: RuntimeCapability) -> None:
        self._queue = list(capabilities)
        self.calls = 0

    def __call__(self) -> RuntimeCapability:
        self.calls += 1
        if self._queue:
            return self._queue.pop(0)
        return _capability()


def _compose(
    detection: _Detection, store: ModelStore | None = None
) -> em.ExecuteModelDependencies:
    """Run the real composition root, patching only its environment seams.

    ``detect_llama_capability`` (machine probing) is replaced by ``detection``;
    the default model store is redirected to ``store`` when a test owns a
    temporary one. Every other collaborator — catalog, preflight, selector,
    runner — is constructed for real by the composition root itself.
    """
    with mock.patch.object(
        wiring, "detect_llama_capability", detection
    ), mock.patch.object(
        wiring,
        "ModelStore",
        (lambda: store) if store is not None else ModelStore,
    ):
        return wiring.compose_execute_model_dependencies()


class CompositionShapeTests(unittest.TestCase):
    """W1–W6: what the composition root binds, and to what."""

    def setUp(self) -> None:
        self.detection = _Detection()
        self.deps = _compose(self.detection)

    def test_w1_composition_returns_complete_execute_model_dependencies(self):
        self.assertIs(type(self.deps), em.ExecuteModelDependencies)
        for field in (
            "model_store",
            "models",
            "capability_provider",
            "preflight_factory",
            "selector",
            "runner",
        ):
            self.assertIsNotNone(getattr(self.deps, field), field)
        # B9.22 §9: the transitional legacy gate stays the Application default;
        # the composition root injects no duplicate compatibility glue.
        self.assertIsNone(self.deps.compatibility_provider)

    def test_w2_runner_is_the_concrete_production_model_runner(self):
        self.assertIsInstance(self.deps.runner, ModelRunner)
        self.assertIs(type(self.deps.runner), LlamaCppRunner)
        # Production process runner bound at construction: no test double.
        self.assertIs(self.deps.runner._run_process, subprocess.run)

    def test_w3_preflight_factory_is_the_real_preflight(self):
        self.assertIs(self.deps.preflight_factory, ArtifactExecutionPreflight)
        preflight = self.deps.preflight_factory(self.deps.model_store)
        self.assertIs(type(preflight), ArtifactExecutionPreflight)
        self.assertIs(preflight.model_store, self.deps.model_store)

    def test_w4_selector_is_the_real_selector(self):
        self.assertIs(type(self.deps.selector), RuntimeBackendSelector)

    def test_w5_model_store_is_the_real_store(self):
        self.assertIs(type(self.deps.model_store), ModelStore)
        self.assertTrue(self.deps.model_store.root.is_absolute())

    def test_w6_models_are_the_real_catalog(self):
        self.assertIs(self.deps.models, get_catalog())
        self.assertTrue(self.deps.models)
        self.assertTrue(
            all(isinstance(item, ModelSpec) for item in self.deps.models)
        )

    def test_composition_is_exported_by_the_wiring_module(self):
        self.assertIn("compose_execute_model_dependencies", wiring.__all__)


class CapabilityIdentityTests(unittest.TestCase):
    """B9.22 §5: one detection per composition, shared by provider and runner."""

    def test_provider_and_runner_share_one_capability_instance(self):
        capability = _capability()
        deps = _compose(_Detection(capability))
        self.assertIs(deps.capability_provider(), capability)
        self.assertIs(deps.runner.capability, capability)
        # Repeated provider calls return the identity; they never re-detect.
        self.assertIs(deps.capability_provider(), deps.capability_provider())
        self.assertIs(deps.capability_provider(), deps.runner.capability)

    def test_detection_happens_exactly_once_per_composition(self):
        detection = _Detection()
        deps = _compose(detection)
        for _ in range(3):
            deps.capability_provider()
        self.assertEqual(detection.calls, 1)

    def test_no_global_cache_two_compositions_detect_independently(self):
        first_detection = _Detection(_capability())
        second_detection = _Detection(_capability())
        first = _compose(first_detection)
        second = _compose(second_detection)
        self.assertEqual(first_detection.calls, 1)
        self.assertEqual(second_detection.calls, 1)
        self.assertIsNot(first, second)
        self.assertIsNot(first.capability_provider(), second.capability_provider())
        self.assertIsNot(first.runner.capability, second.runner.capability)
        self.assertIsNot(first.runner, second.runner)

    def test_detection_seam_is_production_capability_provider(self):
        capability = _capability()
        with mock.patch.object(
            wiring, "production_capability_provider", return_value=capability
        ) as probe:
            deps = _compose(_Detection())
        probe.assert_called_once_with()
        self.assertIs(deps.capability_provider(), capability)
        self.assertIs(deps.runner.capability, capability)

    def test_production_capability_provider_never_caches(self):
        capability = _capability()
        with mock.patch.object(
            wiring, "detect_llama_capability", return_value=capability
        ) as detect:
            self.assertIs(wiring.production_capability_provider(), capability)
            self.assertIs(wiring.production_capability_provider(), capability)
        self.assertEqual(detect.call_count, 2)


class ApplicationBoundaryTests(unittest.TestCase):
    """W7: structural checks on the direction of every dependency."""

    SOURCE = Path("app/execute_model.py").read_text(encoding="utf-8")
    WIRING_SOURCE = Path("app/application_wiring.py").read_text(encoding="utf-8")

    @staticmethod
    def _imported_modules(source: str) -> set[str]:
        modules: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
                modules.add("app." + node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name)
                    modules.add("app." + alias.name)
        return modules

    def test_use_case_imports_stay_the_b9_20_baseline(self):
        # B9.22 added nothing to the Application boundary: in particular the
        # use case never imports the composition root (one-way dependency) and
        # still knows no infrastructure concretion.
        modules = self._imported_modules(self.SOURCE)
        for banned in (
            "app.application_wiring",
            "application_wiring",
            "subprocess",
            "app.run_service",
            "app.main",
            "app.api",
            "app.cli",
            "app.execution_service",
        ):
            self.assertNotIn(banned, modules)
        self.assertNotIn("LlamaCppRunner", self.SOURCE)

    def test_composition_root_imports_the_use_case_and_real_collaborators(self):
        modules = self._imported_modules(self.WIRING_SOURCE)
        for required in (
            "app.execute_model",
            "app.model_store",
            "app.model_catalog",
            "app.execution",
            "app.selection",
            "app.runner",
            "app.runtimes",
        ):
            self.assertIn(required, modules)

    def test_no_unauthorized_module_composes_execute_dependencies(self):
        # Only the authorized entry points (Composition Root and the B9.23
        # Product Caller) may name it; Application/Infrastructure must not.
        offenders = [
            str(path)
            for path in sorted(Path("app").rglob("*.py"))
            if path.name not in _COMPOSITION_ENTRY_POINTS
            and "compose_execute_model_dependencies"
            in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


class ComposedFeedTests(unittest.TestCase):
    """W8: the composed value drives a real ``execute_model`` invocation."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = ModelStore(Path(self.tempdir.name) / "models")
        self.model = get_catalog()[0]
        self.content = b"synthetic GGUF wiring artifact"
        self.artifact = ArtifactSpec(
            model_id=self.model.model_id,
            source="huggingface",
            repository="owner/repository",
            filename="model.Q4_K_M.gguf",
            format="GGUF",
            quantization="Q4_K_M",
            size_bytes=len(self.content),
            sha256=hashlib.sha256(self.content).hexdigest(),
            state=ArtifactState.DOWNLOADED,
        )
        manifest = self.store.save_manifest(self.artifact)
        self.artifact_path = manifest.parent / self.artifact.filename
        self.artifact_path.write_bytes(self.content)

    def test_unknown_model_fails_closed_in_resolution(self):
        detection = _Detection()
        with mock.patch("subprocess.run") as run_process:
            deps = _compose(detection, store=self.store)
            with self.assertRaises(em.ExecutePreparationError) as caught:
                em.execute_model(
                    "model-that-does-not-exist", "prompt", dependencies=deps
                )
        run_process.assert_not_called()
        self.assertIn(
            "Model not found in the local catalog", str(caught.exception)
        )
        self.assertEqual(caught.exception.warnings, ())

    def test_composed_dependencies_drive_the_real_pipeline(self):
        detection = _Detection(
            _capability(executable_path=str(Path(self.tempdir.name) / "llama"))
        )
        real_validate = ArtifactExecutionPreflight.validate
        real_select = RuntimeBackendSelector.select
        # subprocess.run is patched before composition so the runner binds the
        # spy: any launch attempt would be recorded, and none may happen.
        with mock.patch("subprocess.run") as run_process:
            deps = _compose(detection, store=self.store)
            with (
                mock.patch.object(
                    em, "detect_hardware", return_value=_hardware()
                ),
                mock.patch.object(
                    em,
                    "detect_backends",
                    return_value=[
                        BackendStatus("Vulkan", True),
                        BackendStatus("CPU", True),
                    ],
                ),
                mock.patch.object(
                    ArtifactExecutionPreflight,
                    "validate",
                    autospec=True,
                    side_effect=real_validate,
                ) as validate,
                mock.patch.object(
                    RuntimeBackendSelector,
                    "select",
                    autospec=True,
                    side_effect=real_select,
                ) as select,
            ):
                result = em.execute_model(
                    self.model.model_id,
                    "wiring prompt",
                    dependencies=deps,
                )

        # No process was spawned anywhere in the composed pipeline.
        run_process.assert_not_called()

        # The real preflight validated the real manifest artifact with the
        # composed store (W3 + W5, observed on the live invocation).
        self.assertEqual(validate.call_count, 1)
        preflight_instance, validated = validate.call_args.args
        self.assertIs(type(preflight_instance), ArtifactExecutionPreflight)
        self.assertIs(preflight_instance.model_store, self.store)
        self.assertEqual(validated, self.artifact)

        # The real selector received the composed capability: identity with
        # what the runner holds and what the provider returns (B9.22 §5).
        self.assertEqual(select.call_count, 1)
        selector_instance, _compatibility, capability, executable = (
            select.call_args.args
        )
        self.assertIs(type(selector_instance), RuntimeBackendSelector)
        self.assertIs(selector_instance, deps.selector)
        self.assertIs(capability, deps.runner.capability)
        self.assertIs(capability, deps.capability_provider())
        self.assertIs(executable.artifact, validated)
        self.assertEqual(executable.path, self.artifact_path)
        self.assertTrue(executable.size_verified)
        self.assertTrue(executable.checksum_verified)

        # Detection ran once, at composition; the provider only hands out the
        # identity afterwards.
        self.assertEqual(detection.calls, 1)

        # The real runner ran the whole way to its own input validation and
        # failed closed on the absent executable: no model, no subprocess.
        self.assertIs(type(result), ExecutionResult)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, ExecutionErrorCode.EXECUTABLE_MISSING)


if __name__ == "__main__":
    unittest.main()
