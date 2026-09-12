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
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False

    def read(self, _size):
        return next(self.chunks, b"")

    def close(self):
        self.closed = True


class DownloaderTests(unittest.TestCase):
    def make_plan(self, root, spec=None):
        spec = spec or artifact()
        return DownloadPlanner(ModelStore(Path(root)), lambda _path: 100).plan(spec)

    def test_success_streams_and_publishes_final_file(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact(size_bytes=6)
            plan = self.make_plan(directory, spec)
            result = Downloader(
                store, opener=lambda _url, _timeout: Response([b"abc", b"def"])
            ).download(plan)
            self.assertTrue(result.success)
            self.assertEqual(result.status, DownloadResultStatus.SUCCESS)
            self.assertEqual(result.bytes_downloaded, 6)
            self.assertEqual(result.destination.read_bytes(), b"abcdef")
            self.assertFalse(result.destination.with_name(result.destination.name + ".part").exists())

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
                store, opener=lambda *_args: called.append(True)
            ).download(plan)
            self.assertEqual(result.status, DownloadResultStatus.PARTIAL_EXISTS)
            self.assertEqual(partial.read_bytes(), b"old")
            self.assertEqual(called, [])

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
            plan = self.make_plan(directory, artifact(size_bytes=4))
            before = repr(plan.artifact)
            Downloader(
                ModelStore(Path(directory)),
                opener=lambda *_args: Response([b"data"]),
            ).download(plan)
            self.assertEqual(repr(plan.artifact), before)

    def test_manifest_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ModelStore(Path(directory))
            spec = artifact()
            manifest = store.save_manifest(spec)
            before = manifest.read_bytes()
            plan = DownloadPlanner(store, lambda _path: 100).plan(spec)
            Downloader(
                store,
                opener=lambda *_args: Response([b"0123456789"]),
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
