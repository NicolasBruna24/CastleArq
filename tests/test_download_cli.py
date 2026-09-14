"""Tests for the Fase 5 ``download`` CLI wiring."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.downloads import (
    DownloadPlan,
    DownloadPlanStatus,
    DownloadResult,
    DownloadResultStatus,
)
from app.main import run_download
from app.models import ArtifactSpec


def _artifact(**overrides):
    values = {
        "model_id": "qwen2.5-coder-7b-instruct",
        "source": "huggingface",
        "repository": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "filename": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "size_bytes": 10,
        "sha256": "a" * 64,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


def _plan(artifact, **overrides):
    values = {
        "artifact": artifact,
        "destination": Path("/models/qwen/artifact/model.gguf"),
        "status": DownloadPlanStatus.READY,
        "reasons": (),
        "available_bytes": 100,
        "required_bytes": 10,
        "existing": False,
    }
    values.update(overrides)
    return DownloadPlan(**values)


def _source_factory(artifacts):
    def factory():
        source = Mock()
        source.discover_artifacts.return_value = artifacts
        return source

    return factory


def _planner_factory(plan):
    def factory():
        planner = Mock()
        planner.plan.return_value = plan
        return planner

    return factory


def _downloader_factory(result):
    downloader = Mock()
    downloader.download.return_value = result

    def factory(_store):
        return downloader

    factory.downloader = downloader
    return factory


class RunDownloadTests(unittest.TestCase):
    def setUp(self):
        self.artifact = _artifact()

    def _run(self, **kwargs):
        kwargs.setdefault("out", io.StringIO())
        kwargs.setdefault("err", io.StringIO())
        code = run_download("qwen2.5-coder-7b-instruct", **kwargs)
        return code, kwargs["out"].getvalue(), kwargs["err"].getvalue()

    def test_missing_model_id_is_usage_error(self):
        err = io.StringIO()
        self.assertEqual(run_download(None, err=err), 2)
        self.assertEqual(run_download("", err=err), 2)
        self.assertIn("Usage", err.getvalue())

    def test_unknown_model_id_is_rejected(self):
        err = io.StringIO()
        self.assertEqual(run_download("unknown-model", err=err), 1)
        self.assertIn("no unique source repository", err.getvalue())

    def test_repository_id_is_rejected_as_identity(self):
        err = io.StringIO()
        self.assertEqual(
            run_download("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", err=err), 1
        )
        self.assertIn("no unique source repository", err.getvalue())

    def test_source_error_is_operational_error(self):
        from app.sources import SourceError

        def factory():
            source = Mock()
            source.discover_artifacts.side_effect = SourceError("boom")
            return source

        out = io.StringIO()
        err = io.StringIO()
        code = run_download(
            "qwen2.5-coder-7b-instruct",
            source_factory=factory,
            out=out,
            err=err,
        )
        self.assertEqual(code, 1)
        self.assertIn("boom", err.getvalue())

    def test_mismatched_discovered_model_id_is_rejected(self):
        wrong = _artifact(model_id="other/model")
        code, out, err = self._run(source_factory=_source_factory([wrong]))
        self.assertEqual(code, 1)
        self.assertIn("does not match", err)

    def test_ready_plan_invokes_downloader_and_succeeds(self):
        plan = _plan(self.artifact)
        result = DownloadResult(
            True, DownloadResultStatus.SUCCESS, plan.destination, 10
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 0)
        self.assertIn("Model: qwen2.5-coder-7b-instruct", out)
        self.assertIn("Artifact: qwen2.5-coder-7b-instruct-q4_k_m.gguf", out)
        self.assertIn("Planning download...", out)
        self.assertIn("Downloading...", out)
        self.assertIn("Download complete.", out)
        self.assertIn("SHA-256 verified.", out)
        self.assertIn("Artifact state: downloaded", out)

    def test_already_downloaded_is_successful_noop(self):
        plan = _plan(self.artifact, status=DownloadPlanStatus.ALREADY_DOWNLOADED)
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 0)
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 0)
        self.assertIn("already downloaded", out.lower())
        downloader_factory.downloader.download.assert_not_called()

    def test_blocked_plan_shows_reasons_and_skips_downloader(self):
        plan = _plan(
            self.artifact,
            status=DownloadPlanStatus.BLOCKED,
            reasons=("Insufficient available disk space",),
        )
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 0)
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 1)
        self.assertIn("Insufficient available disk space", err)
        downloader_factory.downloader.download.assert_not_called()

    def test_unknown_plan_is_rejected_safely(self):
        plan = _plan(self.artifact, status=DownloadPlanStatus.UNKNOWN)
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 0)
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown", err.lower())
        downloader_factory.downloader.download.assert_not_called()

    def test_downloader_http_error_is_reported(self):
        plan = _plan(self.artifact)
        result = DownloadResult(
            False, DownloadResultStatus.HTTP_ERROR, plan.destination, 0, "HTTP 404"
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 1)
        self.assertIn("HTTP 404", err)

    def test_downloader_network_error_is_reported(self):
        plan = _plan(self.artifact)
        result = DownloadResult(
            False, DownloadResultStatus.NETWORK_ERROR, plan.destination, 0, "boom"
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 1)
        self.assertIn("boom", err)

    def test_downloader_filesystem_error_is_reported(self):
        plan = _plan(self.artifact)
        result = DownloadResult(
            False, DownloadResultStatus.FILESYSTEM_ERROR, plan.destination, 0, "ro"
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 1)
        self.assertIn("filesystem", err.lower())

    def test_checksum_mismatch_is_explicit(self):
        plan = _plan(self.artifact)
        result = DownloadResult(
            False,
            DownloadResultStatus.CHECKSUM_MISMATCH,
            plan.destination,
            10,
            "bad sha",
        )
        code, out, err = self._run(
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 1)
        self.assertIn("SHA-256", err)

    def test_repository_id_never_resolves_even_when_discovery_succeeds(self):
        from app.model_store import ModelStore
        from app.resolver import (
            ModelArtifactResolutionError,
            ModelArtifactResolver,
        )

        with self.assertRaises(ModelArtifactResolutionError):
            ModelArtifactResolver(ModelStore()).resolve(
                "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
            )


    def test_zero_artifacts_lists_and_stops(self):
        code, out, err = self._run(source_factory=_source_factory([]))
        self.assertEqual(code, 1)
        self.assertIn("No GGUF artifacts found", out)

    def test_multiple_artifacts_without_selector_lists_and_stops_without_download(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        second = _artifact(filename="b-q8.gguf", quantization="Q8_0")
        planner = Mock()
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, Path("/x"), 1)
        )
        code, out, err = self._run(
            source_factory=_source_factory([first, second]),
            planner_factory=lambda: planner,
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 1)
        self.assertIn("a-q4.gguf", out)
        self.assertIn("b-q8.gguf", out)
        self.assertIn("specify --quantization or --filename", err)
        downloader_factory.downloader.download.assert_not_called()
        planner.plan.assert_not_called()

    def test_explicit_quantization_selects_and_downloads(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        second = _artifact(filename="b-q8.gguf", quantization="Q8_0")
        plan = _plan(first)
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 10)
        )
        code, out, err = self._run(
            quantization="Q4_K_M",
            source_factory=_source_factory([first, second]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 0)
        self.assertIn("Artifact: a-q4.gguf", out)
        downloader_factory.downloader.download.assert_called_once()

    def test_explicit_filename_selects_and_downloads(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        second = _artifact(filename="b-q8.gguf", quantization="Q8_0")
        plan = _plan(second)
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 10)
        )
        code, out, err = self._run(
            filename="b-q8.gguf",
            source_factory=_source_factory([first, second]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 0)
        self.assertIn("Artifact: b-q8.gguf", out)
        downloader_factory.downloader.download.assert_called_once()

    def test_explicit_quantization_invalid_fails(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        planner = Mock()
        code, out, err = self._run(
            quantization="Q9_K_M",
            source_factory=_source_factory([first]),
            planner_factory=lambda: planner,
        )
        self.assertEqual(code, 1)
        self.assertIn("No artifact matches quantization 'Q9_K_M'", err)
        planner.plan.assert_not_called()

    def test_both_selectors_matching_succeeds(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        second = _artifact(filename="b-q8.gguf", quantization="Q8_0")
        plan = _plan(first)
        downloader_factory = _downloader_factory(
            DownloadResult(True, DownloadResultStatus.SUCCESS, plan.destination, 10)
        )
        code, out, err = self._run(
            quantization="Q4_K_M",
            filename="a-q4.gguf",
            source_factory=_source_factory([first, second]),
            planner_factory=_planner_factory(plan),
            downloader_factory=downloader_factory,
        )
        self.assertEqual(code, 0)
        self.assertIn("Artifact: a-q4.gguf", out)
        downloader_factory.downloader.download.assert_called_once()

    def test_both_selectors_conflicting_fails(self):
        first = _artifact(filename="a-q4.gguf", quantization="Q4_K_M")
        second = _artifact(filename="b-q8.gguf", quantization="Q8_0")
        planner = Mock()
        code, out, err = self._run(
            quantization="Q4_K_M",
            filename="b-q8.gguf",
            source_factory=_source_factory([first, second]),
            planner_factory=lambda: planner,
        )
        self.assertEqual(code, 1)
        self.assertIn("No artifact matches both", err)
        planner.plan.assert_not_called()

    def test_ambiguous_quantization_fails_without_calling_planner(self):
        shard1 = _artifact(filename="model-q4-00001.gguf", quantization="Q4_K_M")
        shard2 = _artifact(filename="model-q4-00002.gguf", quantization="Q4_K_M")
        planner = Mock()
        code, out, err = self._run(
            quantization="Q4_K_M",
            source_factory=_source_factory([shard1, shard2]),
            planner_factory=lambda: planner,
        )
        self.assertEqual(code, 1)
        self.assertIn("Multiple artifacts match quantization 'Q4_K_M'", err)
        self.assertIn("--filename", err)
        planner.plan.assert_not_called()


class DownloadablePredicateGateTests(unittest.TestCase):
    """``run_download``'s initial gate must match ``downloadable_locator``."""

    def _run(self, model_id, **kwargs):
        kwargs.setdefault("out", io.StringIO())
        kwargs.setdefault("err", io.StringIO())
        source = Mock()
        source.discover_artifacts.return_value = []
        kwargs.setdefault("source_factory", lambda: source)
        code = run_download(model_id, **kwargs)
        return code, kwargs["err"].getvalue(), source

    def test_zero_mappings_is_rejected_without_discovery(self):
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", {}):
            code, err, source = self._run("some-model")
        self.assertEqual(code, 1)
        self.assertIn("no unique source repository", err)
        source.discover_artifacts.assert_not_called()

    def test_single_huggingface_mapping_uses_that_locator(self):
        mapping = {("huggingface", "owner/repo"): "some-model"}
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping):
            code, err, source = self._run("some-model")
        source.discover_artifacts.assert_called_once_with("owner/repo")
        self.assertNotIn("no unique source repository", err)
        self.assertNotIn("unsupported source", err)

    def test_multiple_mappings_never_pick_the_first(self):
        mapping = {
            ("huggingface", "owner/one"): "some-model",
            ("huggingface", "owner/two"): "some-model",
        }
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping):
            code, err, source = self._run("some-model")
        self.assertEqual(code, 1)
        self.assertIn("no unique source repository", err)
        source.discover_artifacts.assert_not_called()

    def test_unsupported_source_is_rejected_before_discovery(self):
        mapping = {("ollama", "qwen2.5-coder:7b"): "some-model"}
        with patch("app.model_identity.SOURCE_REPOSITORY_TO_MODEL_ID", mapping):
            code, err, source = self._run("some-model")
        self.assertEqual(code, 1)
        self.assertIn("unsupported source", err)
        source.discover_artifacts.assert_not_called()

    def test_real_qwen_mapping_reaches_discovery(self):
        code, err, source = self._run("qwen2.5-coder-7b-instruct")
        source.discover_artifacts.assert_called_once_with(
            "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
        )
        self.assertNotIn("no unique source repository", err)
        self.assertNotIn("unsupported source", err)


if __name__ == "__main__":
    unittest.main()
