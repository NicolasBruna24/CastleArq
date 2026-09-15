
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

import hashlib
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from app.downloads import (
    DownloadPlan,
    DownloadPlanStatus,
    DownloadResultStatus,
    DownloadPlanner,
    Downloader,
)
from app.model_store import ModelStore, UnsafePathError
from app.models import ArtifactSpec


def artifact(**overrides) -> ArtifactSpec:
    values = {
        "model_id": "qwen/coder",
        "source": "huggingface",
        "repository": "owner/repository",
        "filename": "model.Q4_K_M.gguf",
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "download_url": (
            "https://huggingface.co/owner/repository/resolve/main/"
            "model.Q4_K_M.gguf"
        ),
        "size_bytes": 10,
    }
    values.update(overrides)
    return ArtifactSpec(**values)


class Response:
    def __init__(self, chunks, status=200, headers=None):
        self.chunks = iter(chunks)
        self.closed = False
        self.status = status
        self.headers = headers or {}

    def read(self, _size):
        return next(self.chunks, b"")

    def close(self):
        self.closed = True


def resume_response(chunks, start, end, total):
    return Response(
        chunks,
        status=206,
        headers={"Content-Range": f"bytes {start}-{end}/{total}"},
    )


class DownloaderTests(unittest.TestCase):
    def make_plan(self, root, spec=None):
        spec = spec or artifact()
        return DownloadPlanner(ModelStore(Path(root)), lambda _path: 100).plan(spec)

    def test_success_streams_and_publishes_final_file(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            content = b"abcdef"
            spec = artifact(
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
            plan = self.make_plan(directory, spec)
            result = Downloader(
                store, opener=lambda _url, _timeout: Response([b"abc", b"def"])
            ).download(plan)
            self.assertTrue(result.success)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(result.bytes_downloaded, 6)
            self.assertEqual(result.destination.read_bytes(), b"abcdef")
            self.assertFalse(result.destination.with_name(result.destination.name + ".part").exists())

    def test_checksum_mismatch_preserves_new_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(sha256="0" * 64))
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"0123456789"]),
            ).download(plan)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            self.assertEqual(result.status, DownloadResultStatus.CHECKSUM_MISMATCH)
            self.assertFalse(plan.destination.exists())
            self.assertEqual(partial.read_bytes(), b"0123456789")

    def test_sha256_none_publishes_without_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(sha256=None))
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"0123456789"]),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(plan.destination.read_bytes(), b"0123456789")

    def test_checksum_comparison_accepts_uppercase_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"0123456789"
            plan = self.make_plan(
                directory,
                artifact(sha256=hashlib.sha256(content).hexdigest().upper()),
            )
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([content]),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)

    def test_non_ready_plans_do_not_open_url(self):
        for status in (
            DownloadPlanStatus.BLOCKED,
            DownloadPlanStatus.UNKNOWN,
            DownloadPlanStatus.ALREADY_DOWNLOADED,
        ):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                spec = artifact(size_bytes=None)
                plan = self.make_plan(directory, spec)
                if status != DownloadPlanStatus.UNKNOWN:
                    plan = type(plan)(plan.artifact, plan.destination, status, (), None, None, False)
                called = []
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: called.append(True),
                ).download(plan)
                self.assertEqual(result.status, DownloadResultStatus.PLAN_REJECTED)
                self.assertEqual(called, [])

    def test_existing_final_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact()
            plan = self.make_plan(directory, spec)
            final = plan.destination
            final.parent.mkdir(parents=True)
            final.write_bytes(b"existing")
            called = []
            result = Downloader(
                store, opener=lambda *_args: called.append(True)
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.ALREADY_EXISTS)
            self.assertEqual(final.read_bytes(), b"existing")
            self.assertEqual(called, [])

    def test_existing_part_is_preserved_and_not_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            plan = self.make_plan(directory)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.parent.mkdir(parents=True)
            partial.write_bytes(b"old")
            called = []
            result = Downloader(
                store,
                opener=lambda *_args: (called.append(True), Response([], status=200))[1],
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.RESUME_NOT_SUPPORTED)
            self.assertEqual(partial.read_bytes(), b"old")
            self.assertEqual(called, [True])

    def test_resume_sends_exact_range_and_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=10)
            plan = self.make_plan(directory, spec)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            requests = []

            def opener(url, timeout, headers):
                requests.append((url, timeout, headers))
                return resume_response([b"567890"], 4, 9, 10)

            result = Downloader(store, opener=opener).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(requests[0][2], {"Range": "bytes=4-"})
            self.assertEqual(plan.destination.read_bytes(), b"1234567890")
            self.assertFalse(partial.exists())

    def test_complete_part_with_correct_checksum_is_published_without_http(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"1234567890"
            plan = self.make_plan(
                directory,
                artifact(
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                ),
            )
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(content)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: self.fail("HTTP must not be called"),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(plan.destination.read_bytes(), content)
            self.assertFalse(partial.exists())

    def test_complete_part_with_wrong_checksum_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"1234567890"
            plan = self.make_plan(
                directory,
                artifact(size_bytes=len(content), sha256="0" * 64),
            )
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(content)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: self.fail("HTTP must not be called"),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.CHECKSUM_MISMATCH)
            self.assertEqual(partial.read_bytes(), content)
            self.assertFalse(plan.destination.exists())

    def test_resume_correct_checksum_hashes_complete_file(self):
        with tempfile.TemporaryDirectory() as directory:
            original = b"1234"
            suffix = b"567890"
            content = original + suffix
            plan = self.make_plan(
                directory,
                artifact(
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                ),
            )
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(original)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: resume_response([suffix], 4, 9, 10),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(plan.destination.read_bytes(), content)

    def test_resume_wrong_checksum_preserves_complete_part(self):
        with tempfile.TemporaryDirectory() as directory:
            original = b"1234"
            suffix = b"567890"
            plan = self.make_plan(
                directory,
                artifact(size_bytes=10, sha256="0" * 64),
            )
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(original)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: resume_response([suffix], 4, 9, 10),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.CHECKSUM_MISMATCH)
            self.assertEqual(partial.read_bytes(), original + suffix)
            self.assertFalse(plan.destination.exists())

    def test_resume_uses_observed_total_without_mutating_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = artifact(size_bytes=None)
            store = ModelStore(Path(directory))
            plan = self.make_plan(directory, spec)
            plan = DownloadPlan(
                spec,
                plan.destination,
                DownloadPlanStatus.READY,
                (),
                100,
                None,
                True,
            )
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            result = Downloader(
                store,
                opener=lambda *_args: resume_response([b"567890"], 4, 9, 10),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(plan.destination.read_bytes(), b"1234567890")
            self.assertIsNone(plan.artifact.size_bytes)

    def test_resume_200_does_not_modify_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            original = b"partial"
            partial.write_bytes(original)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"full"], status=200),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.RESUME_NOT_SUPPORTED)
            self.assertEqual(partial.read_bytes(), original)
            self.assertFalse(plan.destination.exists())

    def test_resume_416_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"partial")

            def opener(url, _timeout, _headers):
                raise HTTPError(url, 416, "range invalid", {}, None)

            result = Downloader(ModelStore(Path(directory)), opener=opener).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.RANGE_NOT_SATISFIABLE)
            self.assertEqual(partial.read_bytes(), b"partial")
            self.assertFalse(plan.destination.exists())

    def test_resume_206_without_content_range_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"partial")
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"new"], status=206),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.INVALID_CONTENT_RANGE)
            self.assertEqual(partial.read_bytes(), b"partial")

    def test_resume_wildcard_content_range_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            original = b"1234"
            partial.write_bytes(original)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response(
                    [b"new"],
                    status=206,
                    headers={"Content-Range": "bytes 4-9/*"},
                ),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.INVALID_CONTENT_RANGE)
            self.assertEqual(partial.read_bytes(), original)
            self.assertFalse(plan.destination.exists())

    def test_resume_invalid_content_range_preserves_partial(self):
        cases = (
            "bytes 8-9/10",
            "bytes 4-3/10",
            "items 4-9/10",
            "bytes 4-9/20",
            "invalid",
        )
        for content_range in cases:
            with self.subTest(content_range=content_range):
                with tempfile.TemporaryDirectory() as directory:
                    plan = self.make_plan(directory)
                    plan.destination.parent.mkdir(parents=True)
                    partial = plan.destination.with_name(plan.destination.name + ".part")
                    partial.write_bytes(b"1234")
                    result = Downloader(
                        ModelStore(Path(directory)),
                        opener=lambda *_args, value=content_range: Response(
                            [b"new"], status=206, headers={"Content-Range": value}
                        ),
                    ).download(plan)
                    self.assertEqual(result.status, DownloadResultStatus.INVALID_CONTENT_RANGE)
                    self.assertEqual(partial.read_bytes(), b"1234")

    def test_partial_larger_than_expected_does_not_open_http(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(size_bytes=4))
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"12345")
            called = []
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: called.append(True),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.PARTIAL_TOO_LARGE)
            self.assertEqual(partial.read_bytes(), b"12345")
            self.assertEqual(called, [])

    def test_partial_equal_expected_is_not_published_or_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(size_bytes=4))
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: self.fail("HTTP must not be called"),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.PARTIAL_COMPLETE_UNVERIFIED)
            self.assertEqual(partial.read_bytes(), b"1234")
            self.assertFalse(plan.destination.exists())

    def test_resume_read_error_preserves_received_progress(self):
        class BrokenResumeResponse(Response):
            def read(self, _size):
                if not hasattr(self, "sent"):
                    self.sent = True
                    return b"567"
                raise OSError("resume read failed")

        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: BrokenResumeResponse(
                    [], status=206, headers={"Content-Range": "bytes 4-9/10"}
                ),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertEqual(partial.read_bytes(), b"1234567")

    def test_resume_write_error_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            with patch("app.downloads.downloader.os.write", side_effect=OSError("write failed")):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: resume_response([b"567"], 4, 9, 10),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertEqual(partial.read_bytes(), b"1234")

    def test_resume_fsync_error_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            with patch("app.downloads.downloader.os.fsync", side_effect=OSError("fsync failed")):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: resume_response([b"567890"], 4, 9, 10),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertEqual(partial.read_bytes(), b"1234567890")

    def test_resume_final_size_mismatch_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(size_bytes=10))
            plan.destination.parent.mkdir(parents=True)
            partial = plan.destination.with_name(plan.destination.name + ".part")
            partial.write_bytes(b"1234")
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: resume_response([b"567"], 4, 9, 10),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SIZE_MISMATCH)
            self.assertEqual(partial.read_bytes(), b"1234567")

    def test_initial_state_has_no_final_or_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(
                plan.destination.with_name(plan.destination.name + ".part").exists()
            )

    def test_http_error_cleans_own_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)

            def opener(url, _timeout):
                raise HTTPError(url, 404, "not found", {}, None)

            result = Downloader(ModelStore(Path(directory)), opener=opener).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.HTTP_ERROR)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_http_500_cleans_own_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)

            def opener(url, _timeout):
                raise HTTPError(url, 500, "server error", {}, None)

            result = Downloader(ModelStore(Path(directory)), opener=opener).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.HTTP_ERROR)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_read_error_cleans_own_part(self):
        class BrokenResponse(Response):
            def read(self, _size):
                raise OSError("read failed")

        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: BrokenResponse([]),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_size_mismatch_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(size_bytes=5))
            result = Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"abc"]),
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SIZE_MISMATCH)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_write_error_cleans_own_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            with patch("app.downloads.downloader.os.write", side_effect=OSError("write failed")):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: Response([b"data"]),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_part_fsync_error_cleans_own_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            with patch("app.downloads.downloader.os.fsync", side_effect=OSError("fsync failed")):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: Response([b"data"]),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.NETWORK_ERROR)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(result.destination.name + ".part").exists())

    def test_link_error_cleans_own_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            with patch("app.downloads.downloader.os.link", side_effect=OSError("link failed")):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: Response([b"0123456789"]),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.FILESYSTEM_ERROR)
            self.assertFalse(plan.destination.exists())
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_unlink_error_leaves_published_artifact_and_part(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            with patch("app.downloads.downloader.os.unlink", side_effect=OSError("unlink failed")):
                with self.assertRaises(OSError):
                    Downloader(
                        ModelStore(Path(directory)),
                        opener=lambda *_args: Response([b"0123456789"]),
                    ).download(plan)
            self.assertTrue(plan.destination.exists())
            self.assertEqual(plan.destination.read_bytes(), b"0123456789")
            self.assertTrue(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_link_file_exists_preserves_file_created_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory)
            final_content = b"created-before-publication"

            def link_with_existing_destination(_source, destination, **_kwargs):
                plan.destination.write_bytes(final_content)
                raise FileExistsError("destination appeared")

            with patch("app.downloads.downloader.os.link", side_effect=link_with_existing_destination):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: Response([b"0123456789"]),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.ALREADY_EXISTS)
            self.assertEqual(plan.destination.read_bytes(), final_content)
            self.assertFalse(plan.destination.with_name(plan.destination.name + ".part").exists())

    def test_partial_write_completes_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(directory, artifact(size_bytes=6))
            real_write = __import__("os").write
            calls = []

            def partial_write(fd, data):
                calls.append(bytes(data))
                if len(calls) == 1:
                    return real_write(fd, data[:2])
                return real_write(fd, data)

            with patch("app.downloads.downloader.os.write", side_effect=partial_write):
                result = Downloader(
                    ModelStore(Path(directory)),
                    opener=lambda *_args: Response([b"abcdef"]),
                ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(plan.destination.read_bytes(), b"abcdef")
            self.assertGreaterEqual(len(calls), 2)

    def test_artifact_spec_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"data"
            spec = artifact(
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
            plan = self.make_plan(directory, spec)
            before = repr(plan.artifact)
            Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([content]),
            ).download(plan)
            self.assertEqual(repr(plan.artifact), before)

    def test_manifest_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            content = b"0123456789"
            spec = artifact(sha256=hashlib.sha256(content).hexdigest())
            manifest = store.save_manifest(spec)
            before = manifest.read_bytes()
            plan = DownloadPlanner(store, lambda _path: 100).plan(spec)
            Downloader(
                store,
                opener=lambda *_args: Response([content]),
            ).download(plan)
            self.assertEqual(manifest.read_bytes(), before)

    def test_invalid_url_is_rejected_before_opening(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = self.make_plan(
                directory,
                artifact(download_url="http://huggingface.co/owner/repository/resolve/main/model.Q4_K_M.gguf"),
            )
            called = []
            result = Downloader(
                ModelStore(Path(directory)), opener=lambda *_args: called.append(True)
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.PLAN_REJECTED)
            self.assertEqual(called, [])

    def test_symlink_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            store = ModelStore(root)
            (root / "qwen__coder").symlink_to(outside, target_is_directory=True)
            spec = artifact()
            plan = DownloadPlan(
                spec,
                root / "qwen__coder" / spec.artifact_id / spec.filename,
                DownloadPlanStatus.READY,
                (),
                100,
                spec.size_bytes,
                False,
            )
            with self.assertRaises(UnsafePathError):
                Downloader(store, opener=lambda *_args: Response([b"data"])).download(plan)

    def test_part_symlink_is_rejected_without_http(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            store = ModelStore(root)
            spec = artifact()
            artifact_dir = root / "qwen__coder" / spec.artifact_id
            artifact_dir.mkdir(parents=True)
            target = Path(outside) / "target"
            target.write_bytes(b"outside")
            partial = artifact_dir / f"{spec.filename}.part"
            partial.symlink_to(target)
            plan = DownloadPlan(
                spec,
                artifact_dir / spec.filename,
                DownloadPlanStatus.READY,
                (),
                100,
                spec.size_bytes,
                False,
            )
            called = []
            with self.assertRaises(UnsafePathError):
                Downloader(
                    store, opener=lambda *_args: called.append(True)
                ).download(plan)
            self.assertEqual(called, [])
            self.assertTrue(partial.is_symlink())

    def test_final_symlink_is_rejected_without_http(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            store = ModelStore(root)
            spec = artifact()
            artifact_dir = root / "qwen__coder" / spec.artifact_id
            artifact_dir.mkdir(parents=True)
            target = Path(outside) / "target"
            target.write_bytes(b"outside")
            final = artifact_dir / spec.filename
            final.symlink_to(target)
            plan = DownloadPlan(
                spec,
                final,
                DownloadPlanStatus.READY,
                (),
                100,
                spec.size_bytes,
                False,
            )
            called = []
            with self.assertRaises(UnsafePathError):
                Downloader(
                    store, opener=lambda *_args: called.append(True)
                ).download(plan)
            self.assertEqual(called, [])
            self.assertTrue(final.is_symlink())


if __name__ == "__main__":
    unittest.main()
