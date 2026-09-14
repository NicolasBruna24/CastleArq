import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.downloads import DownloadPlanStatus
from app.main import print_local_models, print_plan
from app.model_catalog import get_catalog
from app.model_identity import (
    SOURCE_REPOSITORY_TO_MODEL_ID,
    SUPPORTED_DOWNLOAD_SOURCES,
    downloadable_locator,
    logical_model_id,
    source_repositories_for_logical_model,
)
from app.model_store import ModelStore
from app.models import ArtifactSpec, ArtifactState
from app.resolver import (
    ModelArtifactResolutionError,
    ModelArtifactResolver,
    ResolvedModelArtifact,
)


QWEN_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
QWEN_LOGICAL_ID = "qwen2.5-coder-7b-instruct"


class ModelIdentityMappingTests(unittest.TestCase):
    def test_qwen_repository_maps_to_logical_model_id(self):
        self.assertEqual(
            logical_model_id("huggingface", QWEN_REPOSITORY), QWEN_LOGICAL_ID
        )

    def test_every_mapped_target_exists_in_catalog(self):
        catalog_ids = {model.model_id for model in get_catalog()}
        for logical in SOURCE_REPOSITORY_TO_MODEL_ID.values():
            self.assertIn(logical, catalog_ids)

    def test_unknown_repository_has_no_logical_id(self):
        self.assertIsNone(logical_model_id("huggingface", "owner/repository"))
        self.assertIsNone(logical_model_id("ollama", "qwen2.5-coder:7b"))


class ListOutputTests(unittest.TestCase):
    def test_list_shows_logical_model_id_accepted_by_run_and_chat(self):
        artifact = ArtifactSpec(
            model_id=QWEN_LOGICAL_ID,
            source="huggingface",
            repository=QWEN_REPOSITORY,
            filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        )
        entry = SimpleNamespace(
            artifact=artifact,
            state=ArtifactState.VERIFIED,
            manifest_path=Path("/tmp/manifest.json"),
            message=None,
        )
        with patch("app.main.ModelStore") as store:
            store.return_value.list_artifacts.return_value = [entry]
            output = io.StringIO()
            with redirect_stdout(output):
                print_local_models()
        self.assertIn(QWEN_LOGICAL_ID, output.getvalue())


class PlanOutputTests(unittest.TestCase):
    def test_plan_uses_logical_model_id_and_keeps_repository(self):
        captured = {}

        class Planner:
            def __init__(self, *_args, **_kwargs):
                pass

            def plan(self, artifact):
                captured["artifact"] = artifact

                class Plan:
                    status = DownloadPlanStatus.READY
                    destination = "x"
                    required_bytes = 1
                    available_bytes = 2
                    existing = False
                    reasons: tuple = ()

                return Plan()

        with patch("app.main.DownloadPlanner", Planner):
            output = io.StringIO()
            with redirect_stdout(output):
                code = print_plan(QWEN_REPOSITORY, "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
        self.assertEqual(code, 0)
        self.assertEqual(captured["artifact"].model_id, QWEN_LOGICAL_ID)
        self.assertEqual(captured["artifact"].repository, QWEN_REPOSITORY)
        self.assertNotEqual(captured["artifact"].model_id, QWEN_REPOSITORY)

    def test_plan_rejects_unmapped_repository(self):
        with patch("app.main.DownloadPlanner") as planner:
            error = io.StringIO()
            with redirect_stderr(error):
                code = print_plan("owner/repository", "model.gguf")
        self.assertEqual(code, 1)
        planner.assert_not_called()


class SharedVocabularyIntegrationTests(unittest.TestCase):
    def test_catalog_store_and_resolver_share_the_logical_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory) / "models")
            artifact = ArtifactSpec(
                model_id=QWEN_LOGICAL_ID,
                source="huggingface",
                repository=QWEN_REPOSITORY,
                filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
                format="GGUF",
                quantization="Q4_K_M",
                state=ArtifactState.VERIFIED,
            )
            manifest = store.save_manifest(artifact)
            manifest.parent.joinpath(artifact.filename).write_bytes(b"model")

            resolved = ModelArtifactResolver(store).resolve(QWEN_LOGICAL_ID)

            self.assertIsInstance(resolved, ResolvedModelArtifact)
            self.assertEqual(resolved.artifact.model_id, QWEN_LOGICAL_ID)
            self.assertEqual(resolved.artifact.repository, QWEN_REPOSITORY)
            with self.assertRaisesRegex(
                ModelArtifactResolutionError, "not found"
            ):
                ModelArtifactResolver(store).resolve(QWEN_REPOSITORY)


EXPECTED_CATALOG_IDS = (
    "qwen2.5-coder-7b-instruct",
    "llama-3.1-8b-instruct",
    "deepseek-r1-distill-qwen-14b",
)


class ModelCatalogContractTests(unittest.TestCase):
    """Contract tests for the model catalog identity (audit 5.6.10 / D1)."""

    def test_every_model_has_explicit_non_empty_own_id(self):
        for model in get_catalog():
            with self.subTest(model_id=model.model_id):
                self.assertTrue(model.id)
                self.assertEqual(model.model_id, model.id)
                self.assertNotEqual(model.model_id, model.name)

    def test_catalog_model_ids_are_unique(self):
        ids = [model.model_id for model in get_catalog()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_catalog_contains_exactly_the_expected_ids(self):
        self.assertEqual(
            tuple(model.model_id for model in get_catalog()), EXPECTED_CATALOG_IDS
        )

    def test_every_catalog_id_is_a_valid_resolver_identity(self):
        for model in get_catalog():
            with self.subTest(model_id=model.model_id), tempfile.TemporaryDirectory() as d:
                store = ModelStore(Path(d) / "models")
                with self.assertRaises(ModelArtifactResolutionError):
                    ModelArtifactResolver(store).resolve(model.model_id)

    def test_mapped_model_is_downloadable_via_its_single_locator(self):
        self.assertEqual(
            downloadable_locator(QWEN_LOGICAL_ID), ("huggingface", QWEN_REPOSITORY)
        )

    def test_models_without_mapping_are_not_downloadable(self):
        for model_id in EXPECTED_CATALOG_IDS[1:]:
            with self.subTest(model_id=model_id):
                self.assertIsNone(downloadable_locator(model_id))
                self.assertEqual(source_repositories_for_logical_model(model_id), ())

    def test_downloadability_matches_the_mapping_for_every_catalog_model(self):
        for model in get_catalog():
            locators = source_repositories_for_logical_model(model.model_id)
            if len(locators) == 1 and locators[0][0] in SUPPORTED_DOWNLOAD_SOURCES:
                expected = locators[0]
            else:
                expected = None
            with self.subTest(model_id=model.model_id):
                self.assertEqual(downloadable_locator(model.model_id), expected)


if __name__ == "__main__":
    unittest.main()
