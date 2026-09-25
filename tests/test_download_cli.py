
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

"""Tests for the Fase 5 ``download`` CLI wiring."""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.downloads import (
    Downloader,
    DownloadPlan,
    DownloadPlanStatus,
    DownloadResult,
    DownloadResultStatus,
)
from app.main import run_download
from app.model_store import ModelStore, UnsafePathError
from app.models import ArtifactSpec, ArtifactState
from app.resolver import ModelArtifactResolver


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
        # A temporary store keeps every success path off the real user store.
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.store = ModelStore(Path(self._tempdir.name) / "models")

    def _run(self, **kwargs):
        kwargs.setdefault("out", io.StringIO())
        kwargs.setdefault("err", io.StringIO())
        kwargs.setdefault("model_store", self.store)
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
        # B9.40: the successful transfer also registers the manifest, and the
        # store discovers exactly the downloaded artifact through it.
        self.assertIn("Registered manifest:", out)
        entries = self.store.list_artifacts()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].artifact.model_id, "qwen2.5-coder-7b-instruct")
        self.assertEqual(
            entries[0].artifact.filename, "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        )
        self.assertEqual(entries[0].artifact.quantization, "Q4_K_M")

    def test_downloader_failure_does_not_persist_a_manifest(self):
        plan = _plan(self.artifact)
        store = Mock(spec=ModelStore)
        result = DownloadResult(
            False, DownloadResultStatus.NETWORK_ERROR, plan.destination, 0, "boom"
        )
        code, out, err = self._run(
            model_store=store,
            source_factory=_source_factory([self.artifact]),
            planner_factory=_planner_factory(plan),
            downloader_factory=_downloader_factory(result),
        )
        self.assertEqual(code, 1)
        self.assertIn("boom", err)
        store.save_manifest.assert_not_called()
        self.assertNotIn("Download complete.", out)
        self.assertNotIn("Registered manifest:", out)

    def test_persistence_failure_is_reported_and_fails_the_command(self):
        for error in (UnsafePathError("unsafe store path"), OSError("read-only")):
            with self.subTest(error=type(error).__name__):
                store = Mock(spec=ModelStore)
                store.save_manifest.side_effect = error
                plan = _plan(self.artifact)
                result = DownloadResult(
                    True, DownloadResultStatus.SUCCESS, plan.destination, 10
                )
                code, out, err = self._run(
                    model_store=store,
                    source_factory=_source_factory([self.artifact]),
                    planner_factory=_planner_factory(plan),
                    downloader_factory=_downloader_factory(result),
                )
                self.assertEqual(code, 1)
                self.assertIn("manifest could not be persisted", err)
                self.assertIn(str(error), err)
                store.save_manifest.assert_called_once_with(self.artifact)
                # A download whose manifest was not persisted is never
                # reported as a complete success (B9.40, no rollback).
                self.assertNotIn("Download complete.", out)
                self.assertNotIn("Registered manifest:", out)

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


class _FakeHttpResponse:
    """Minimal stand-in for the ``Downloader`` opener's response object."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._sent = False
        self.status = 200
        self.headers: dict[str, str] = {}

    def read(self, _size: int = -1) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        return self._payload

    def close(self) -> None:
        return None


class ArtifactRegistrationVerticalTests(unittest.TestCase):
    """B9.40: the download flow itself registers the artifact in the store.

    Real ``DownloadPlanner``, real ``Downloader``, real ``ModelStore`` and real
    ``ModelArtifactResolver``; only HTTP is simulated through the ``Downloader``
    opener seam. ``save_manifest`` is never called by the test: the artifact
    must be discoverable and resolvable purely as a consequence of the
    download flow.
    """

    CONTENT = b"synthetic GGUF payload for the B9.40 vertical slice"
    REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
    FILENAME = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    MODEL_ID = "qwen2.5-coder-7b-instruct"

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.store = ModelStore(Path(self._tempdir.name) / "models")
        self.artifact = ArtifactSpec(
            model_id=self.MODEL_ID,
            source="huggingface",
            repository=self.REPOSITORY,
            filename=self.FILENAME,
            format="GGUF",
            quantization="Q4_K_M",
            download_url=(
                f"https://huggingface.co/{self.REPOSITORY}"
                f"/resolve/main/{self.FILENAME}"
            ),
            size_bytes=len(self.CONTENT),
            sha256=hashlib.sha256(self.CONTENT).hexdigest(),
        )

    def _opener(self, url, timeout, headers=None):
        self.assertTrue(url.startswith("https://huggingface.co/"), url)
        return _FakeHttpResponse(self.CONTENT)

    def test_download_registers_the_artifact_without_manual_persistence(self):
        out, err = io.StringIO(), io.StringIO()
        code = run_download(
            self.MODEL_ID,
            model_store=self.store,
            source_factory=_source_factory([self.artifact]),
            downloader_factory=lambda store: Downloader(store, opener=self._opener),
            out=out,
            err=err,
        )
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("Download complete.", out.getvalue())
        self.assertIn("Registered manifest:", out.getvalue())

        # 1. The physical file was published by the real downloader.
        published = (
            self.store.root
            / self.MODEL_ID
            / self.artifact.artifact_id
            / self.FILENAME
        )
        self.assertTrue(published.exists())
        self.assertEqual(published.read_bytes(), self.CONTENT)

        # 2. The manifest exists because of the flow, not because of the test.
        manifest = published.parent / "manifest.json"
        self.assertTrue(manifest.exists())

        # 3. The store discovers exactly one artifact and derives VERIFIED.
        entries = self.store.list_artifacts()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].artifact.model_id, self.MODEL_ID)
        self.assertEqual(entries[0].artifact.filename, self.FILENAME)
        self.assertEqual(entries[0].state, ArtifactState.VERIFIED)

        # 4. The resolver can resolve the freshly downloaded artifact.
        resolved = ModelArtifactResolver(self.store).resolve(
            self.MODEL_ID, quantization="Q4_K_M"
        )
        self.assertEqual(resolved.artifact.filename, self.FILENAME)
        self.assertEqual(resolved.artifact.artifact_id, self.artifact.artifact_id)

    def test_second_run_sees_the_registered_artifact(self):
        """The registered manifest closes the cycle: no second transfer."""
        first_out, first_err = io.StringIO(), io.StringIO()
        first_code = run_download(
            self.MODEL_ID,
            model_store=self.store,
            source_factory=_source_factory([self.artifact]),
            downloader_factory=lambda store: Downloader(store, opener=self._opener),
            out=first_out,
            err=first_err,
        )
        self.assertEqual(first_code, 0, first_err.getvalue())

        spy = Mock(wraps=Downloader(self.store, opener=self._opener))
        second_out, second_err = io.StringIO(), io.StringIO()
        second_code = run_download(
            self.MODEL_ID,
            model_store=self.store,
            source_factory=_source_factory([self.artifact]),
            downloader_factory=lambda store: spy,
            out=second_out,
            err=second_err,
        )
        self.assertEqual(second_code, 0, second_err.getvalue())
        self.assertIn("Artifact already downloaded.", second_out.getvalue())
        spy.download.assert_not_called()
        self.assertEqual(len(self.store.list_artifacts()), 1)


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
