# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for B9.67 stage 2: resolving imported artifacts by sanitized label."""

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from castlearq.importing import ImportStatus, LocalArtifactImporter
from castlearq.model_catalog import get_catalog
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec, ArtifactState
from castlearq.resolver import ModelArtifactResolutionError, ModelArtifactResolver


def _gguf(architecture="qwen2") -> bytes:
    """Minimal GGUF the existing reader accepts."""
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    key = b"general.architecture"
    raw = architecture.encode("utf-8")
    data += struct.pack("<Q", len(key)) + key
    data += struct.pack("<I", 8)
    data += struct.pack("<Q", len(raw)) + raw
    return bytes(data)


MODEL = _gguf()


class _ResolverCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = ModelStore(self.root / "models")
        self.importer = LocalArtifactImporter(self.store)
        self.sources = self.root / "external"
        self.sources.mkdir()
        self.resolver = ModelArtifactResolver(self.store)

    def _import(self, name="model.gguf", data=MODEL, label=None):
        path = self.sources / name
        path.write_bytes(data)
        result = self.importer.import_artifact(path, label=label)
        self.assertEqual(result.status, ImportStatus.IMPORTED, result.error)
        return result

class CatalogRegressionTests(_ResolverCase):
    """The catalog path must be unchanged by stage 2."""

    def _catalog_artifact(self, **kwargs):
        model = get_catalog()[0]
        values = {
            "model_id": model.model_id,
            "source": "huggingface",
            "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            "filename": "model.Q4_K_M.gguf",
            "format": "GGUF",
            "quantization": "Q4_K_M",
        }
        values.update(kwargs)
        return ArtifactSpec(**values)

    def _store(self, artifact):
        manifest = self.store.save_manifest(artifact)
        (manifest.parent / artifact.filename).write_bytes(b"model")
        return manifest

    def test_catalog_resolution_is_unchanged(self):
        model = get_catalog()[0]
        artifact = self._catalog_artifact()
        self._store(artifact)
        result = self.resolver.resolve(model.model_id)
        self.assertEqual(result.model, model)
        self.assertEqual(result.artifact, artifact)

    def test_catalog_resolution_reports_imported_false(self):
        model = get_catalog()[0]
        self._store(self._catalog_artifact())
        self.assertFalse(self.resolver.resolve(model.model_id).imported)

    def test_catalog_model_id_is_the_real_catalog_id(self):
        model = get_catalog()[0]
        self._store(self._catalog_artifact())
        result = self.resolver.resolve(model.model_id)
        self.assertEqual(result.model.id, model.id)
        self.assertIsNotNone(result.model.id)

    def test_catalog_artifact_id_is_still_provenance_derived(self):
        artifact = self._catalog_artifact()
        self._store(artifact)
        self.assertIsNone(artifact.content_id)
        self.assertNotEqual(
            artifact.artifact_id, hashlib.sha256(b"model").hexdigest()
        )

    def test_unknown_label_still_fails_closed(self):
        with self.assertRaisesRegex(ModelArtifactResolutionError, "not found"):
            self.resolver.resolve("unknown-model")

    def test_resolution_does_not_create_store_entries(self):
        before = set(self.store.root.rglob("*")) if self.store.root.exists() else set()
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("unknown-model")
        after = set(self.store.root.rglob("*")) if self.store.root.exists() else set()
        self.assertEqual(after, before)


class ImportedResolutionTests(_ResolverCase):
    def test_imported_artifact_resolves_by_sanitized_label(self):
        imported = self._import("My Local Model!.gguf", label="My Local Model!")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.artifact.content_id, imported.content_id)

    def test_imported_resolution_reports_imported_true(self):
        imported = self._import(label="lab")
        self.assertTrue(self.resolver.resolve(imported.sanitized_label).imported)

    def test_imported_model_id_is_none(self):
        imported = self._import(label="lab")
        self.assertIsNone(self.resolver.resolve(imported.sanitized_label).model.id)

    def test_imported_model_name_is_the_sanitized_label(self):
        imported = self._import(label="My Local Model!")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.model.name, imported.sanitized_label)
        self.assertEqual(result.model.name, "My_Local_Model_")

    def test_artifact_model_id_holds_the_sanitized_label(self):
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.artifact.model_id, imported.sanitized_label)

    def test_content_id_is_preserved(self):
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.artifact.content_id, imported.content_id)
        self.assertEqual(
            result.artifact.content_id, hashlib.sha256(MODEL).hexdigest()
        )

    def test_resolved_path_is_the_managed_file_inside_the_store(self):
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.path, imported.destination)
        self.assertTrue(str(result.path).startswith(str(self.store.root)))

    def test_resolution_never_points_at_the_external_path(self):
        source = self.sources / "external.gguf"
        source.write_bytes(MODEL)
        imported = self.importer.import_artifact(source, label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertNotEqual(result.path, source)
        self.assertNotEqual(result.path.resolve(), source.resolve())

    def test_resolved_path_exists_and_matches_the_content(self):
        imported = self._import(label="lab")
        path = self.resolver.resolve(imported.sanitized_label).path
        self.assertTrue(path.is_file())
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(), imported.content_id
        )



class SelectorTests(_ResolverCase):
    def test_filename_selector_disambiguates_imported(self):
        first = self._import("a.gguf", MODEL, label="shared")
        second = self._import("b.gguf", _gguf("llama"), label="shared")
        self.assertNotEqual(first.content_id, second.content_id)

        result = self.resolver.resolve("shared", filename="b.gguf")
        self.assertEqual(result.artifact.filename, "b.gguf")
        self.assertEqual(result.artifact.content_id, second.content_id)

    def test_ambiguous_label_without_selector_fails_closed(self):
        self._import("a.gguf", MODEL, label="shared")
        self._import("b.gguf", _gguf("llama"), label="shared")
        with self.assertRaisesRegex(ModelArtifactResolutionError, "multiple"):
            self.resolver.resolve("shared")

    def test_unmatched_filename_selector_fails(self):
        self._import(label="lab")
        with self.assertRaisesRegex(
            ModelArtifactResolutionError, "No artifact matches filename"
        ):
            self.resolver.resolve("lab", filename="absent.gguf")

    def test_unmatched_quantization_selector_fails(self):
        self._import(label="lab")
        with self.assertRaisesRegex(
            ModelArtifactResolutionError, "No artifact matches quantization"
        ):
            self.resolver.resolve("lab", quantization="Q4_K_M")

    def test_quantization_selector_keeps_its_semantics(self):
        """An imported artifact has no derived quantization, so Q4 never matches."""


class SecurityTests(_ResolverCase):
    def test_external_path_is_not_accepted_as_a_selector(self):
        self._import(label="lab")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve(str(self.sources / "model.gguf"))

    def test_absolute_external_path_does_not_resolve(self):
        self._import(label="lab")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("/home/user/model.gguf")

    def test_external_path_import_is_not_implicit_resolution(self):
        source = self.sources / "loose.gguf"
        source.write_bytes(MODEL)
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve(str(source))
        self.assertEqual(self.store.list_artifacts(), [])

    def test_traversal_selector_does_not_escape(self):
        self._import(label="lab")
        for label in ("../outside", "..", "a/../../b"):
            with self.assertRaises(ModelArtifactResolutionError):
                self.resolver.resolve(label)

    def test_symlinked_managed_file_is_not_resolved(self):
        imported = self._import(label="lab")
        outside = self.root / "outside.gguf"
        outside.write_bytes(MODEL)
        imported.destination.unlink()
        imported.destination.symlink_to(outside)
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_symlinked_directory_does_not_resolve(self):
        imported = self._import(label="lab")
        label_dir = self.store.root / "lab"
        outside = self.root / "outside-dir"
        outside.mkdir()
        # Replace the real label directory with a symlink pointing outside.
        (label_dir).rename(outside / "real")
        label_dir.symlink_to(outside / "real", target_is_directory=True)
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_inconsistent_manifest_does_not_resolve(self):
        imported = self._import(label="lab")
        manifest = imported.destination.parent / "manifest.json"
        manifest.write_text("{ not valid json", encoding="utf-8")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_manifest_missing_required_field_does_not_resolve(self):
        imported = self._import(label="lab")
        manifest = imported.destination.parent / "manifest.json"
        manifest.write_text('{"filename": "model.gguf"}', encoding="utf-8")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_missing_managed_file_does_not_resolve(self):
        imported = self._import(label="lab")
        imported.destination.unlink()
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_partial_only_import_does_not_resolve(self):
        imported = self._import(label="lab")
        directory = imported.destination.parent
        imported.destination.unlink()
        (directory / "manifest.json").unlink()
        (directory / f"{imported.filename}.part").write_bytes(MODEL)
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab")

    def test_catalog_artifact_is_never_treated_as_imported(self):
        catalog = get_catalog()[0]
        artifact = ArtifactSpec(
            model_id=catalog.model_id, source="huggingface",
            repository="owner/repo", filename="catalog.gguf",
            format="GGUF", quantization="Q4_K_M",
        )
        manifest = self.store.save_manifest(artifact)
        (manifest.parent / artifact.filename).write_bytes(b"model")
        # The label is not a catalog id, so the imported lookup must not find it.
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve(catalog.model_id, filename="absent.gguf")
        self.assertFalse(self.resolver.resolve(catalog.model_id).imported)


class IdentitySeparationTests(_ResolverCase):
    def test_label_is_never_copied_to_model_id(self):
        imported = self._import(label="My Local Model!")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertIsNone(result.model.id)
        self.assertNotEqual(result.model.id, result.artifact.model_id)

    def test_artifact_model_id_is_not_logical_identity(self):
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.model.name, result.artifact.model_id)
        self.assertIsNone(result.model.id)

    def test_model_id_fallback_is_not_an_identity_claim(self):
        """`ModelSpec.model_id` still falls back to name; that is not identity."""
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertEqual(result.model.model_id, result.model.name)
        self.assertIsNone(result.model.id)

    def test_imported_flag_is_independent_of_model_id(self):
        imported = self._import(label="lab")
        result = self.resolver.resolve(imported.sanitized_label)
        self.assertTrue(result.imported)
        self.assertIsNone(result.model.id)
        self.assertIsNotNone(result.artifact.content_id)

    def test_integrity_declaration_stays_unknown(self):
        self._import(label="lab")
        result = self.resolver.resolve("lab")
        self.assertIsNone(result.artifact.sha256)

    def test_evaluate_result_module_is_untouched_by_stage_two(self):
        """Stage 2 must not change admission; imported is still propagatable."""
        import castlearq.evaluate_compatibility as module
        import inspect as inspect_module
        source = inspect_module.getsource(module)
        self.assertIn("imported", source)

        imported = self._import(label="lab")
        self.assertEqual(imported.artifact.quantization, "Unknown")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("lab", quantization="Q4_K_M")

    def test_same_label_and_filename_distinct_content_stays_ambiguous(self):
        """Documented limitation: no content-hash selector exists yet."""
        self._import("same.gguf", MODEL, label="shared")
        self._import("same.gguf", _gguf("llama"), label="shared")
        with self.assertRaises(ModelArtifactResolutionError):
            self.resolver.resolve("shared", filename="same.gguf")

    def test_imported_without_label_falls_back_to_filename(self):
        self._import("named.gguf")
        result = self.resolver.resolve("named.gguf")
        self.assertTrue(result.imported)
        self.assertEqual(result.model.name, "named.gguf")

    def test_imported_and_catalog_coexist(self):
        catalog = get_catalog()[0]
        catalog_artifact = ArtifactSpec(
            model_id=catalog.model_id, source="huggingface",
            repository="owner/repo", filename="catalog.gguf",
            format="GGUF", quantization="Q4_K_M",
        )
        manifest = self.store.save_manifest(catalog_artifact)
        (manifest.parent / catalog_artifact.filename).write_bytes(b"model")
        imported = self._import(label="lab")
        self.assertFalse(self.resolver.resolve(catalog.model_id).imported)
        self.assertTrue(self.resolver.resolve(imported.sanitized_label).imported)
