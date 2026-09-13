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
from app.model_identity import SOURCE_REPOSITORY_TO_MODEL_ID, logical_model_id
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


if __name__ == "__main__":
    unittest.main()
