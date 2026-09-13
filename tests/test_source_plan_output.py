import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from app.main import print_plan, print_source
from app.model_catalog import get_catalog
from app.models import ArtifactSpec, ArtifactState


def _artifact(**overrides):
    values = {
        "model_id": "qwen2.5-coder-7b-instruct",
        "source": "huggingface",
        "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "filename": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class PrintSourceTests(unittest.TestCase):
    def test_source_shows_logical_model_id_once(self):
        artifacts = [_artifact()]
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.return_value = artifacts
            output = io.StringIO()
            with redirect_stdout(output):
                code = print_source("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        self.assertEqual(code, 0)
        out = output.getvalue()
        self.assertIn("Model: qwen2.5-coder-7b-instruct", out)
        # The repository must not be presented as the model_id.
        self.assertNotIn("Model: Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", out)

    def test_source_shows_catalog_membership(self):
        artifacts = [_artifact()]
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.return_value = artifacts
            output = io.StringIO()
            with redirect_stdout(output):
                print_source("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        self.assertIn("Catalog: in catalog", output.getvalue())

    def test_source_warns_when_logical_model_not_in_catalog(self):
        artifacts = [_artifact(model_id="future-model-not-in-catalog")]
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.return_value = artifacts
            output = io.StringIO()
            with redirect_stdout(output):
                print_source("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        out = output.getvalue()
        self.assertIn("Catalog: not in catalog", out)
        self.assertIn("future-model-not-in-catalog", out)

    def test_source_rejects_unmapped_repository(self):
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.side_effect = (
                __import__("app.sources", fromlist=["SourceError"]).SourceError(
                    "Repository is not mapped to a catalog model: owner/repository"
                )
            )
            output = io.StringIO()
            with redirect_stderr(output):
                code = print_source("huggingface", "owner/repository")
        self.assertEqual(code, 1)

    def test_source_preserves_existing_artifact_fields(self):
        artifacts = _artifact(
            size_bytes=4683073536,
            sha256="a" * 64,
            download_url="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        )
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.return_value = [artifacts]
            output = io.StringIO()
            with redirect_stdout(output):
                print_source("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        out = output.getvalue()
        self.assertIn("qwen2.5-coder-7b-instruct-q4_k_m.gguf", out)
        self.assertIn("Q4_K_M", out)
        self.assertIn("4683073536", out)


class PrintPlanTests(unittest.TestCase):
    def test_plan_shows_logical_model_id(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = print_plan("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                              "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
        self.assertEqual(code, 0)
        out = output.getvalue()
        self.assertIn("Model: qwen2.5-coder-7b-instruct", out)
        self.assertIn("Repository: Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", out)
        self.assertIn("Filename: qwen2.5-coder-7b-instruct-q4_k_m.gguf", out)
        self.assertNotIn("Model: Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", out)

    def test_plan_rejects_unmapped_repository(self):
        error = io.StringIO()
        with redirect_stderr(error):
            code = print_plan("owner/repository", "model.gguf")
        self.assertEqual(code, 1)


class VocabularyCoherenceTests(unittest.TestCase):
    def test_source_model_id_is_exactly_accepted_by_resolver(self):
        from app.resolver import ModelArtifactResolver
        from app.model_store import ModelStore

        artifacts = [_artifact(state=ArtifactState.VERIFIED)]
        with patch("app.main.HuggingFaceSource") as source:
            source.return_value.discover_artifacts.return_value = artifacts
            output = io.StringIO()
            with redirect_stdout(output):
                print_source("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        shown = output.getvalue()
        catalog_ids = {model.model_id for model in get_catalog()}
        for model_id in catalog_ids:
            if f"Model: {model_id}" in shown:
                resolver = ModelArtifactResolver(ModelStore())
                resolver.resolve(model_id)  # must not raise
