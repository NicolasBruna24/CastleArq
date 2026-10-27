import tempfile
import unittest
from pathlib import Path

from castlearq.chat import OpenVINOChatSession
from castlearq.conversion import OpenVINOImportService
from castlearq.model_store import ModelStore
from castlearq.resolver import ModelArtifactResolver

BUNDLE = Path("/home/brunapc/models/ovms/OpenVINO/Qwen3-8B-int4-ov")


class FakeService:
    def generate(self, *a, **k):
        raise RuntimeError("generate must not be called in this test")

    def close(self):
        self.closed = True


@unittest.skipUnless(BUNDLE.is_dir() and (BUNDLE / "openvino_model.xml").is_file(), "OpenVINO bundle not available")
class OpenVINOImportSessionIntegrationTests(unittest.TestCase):
    def test_import_verify_resolve_create_session_without_generation(self):
        with tempfile.TemporaryDirectory(prefix="ov-integration-") as td:
            store = ModelStore(Path(td))
            svc = OpenVINOImportService(store)
            result = svc.import_directory(BUNDLE, "qwen3-8b-ov-integration", precision="int4")
            self.assertTrue(result.success, result.message)

            entries = store.list_artifacts(verify=True)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertIn(entry.state.value, ("downloaded", "verified"))
            self.assertEqual(entry.artifact.backend, "openvino")
            self.assertEqual(entry.artifact.format, "OpenVINO IR")
            self.assertIsNotNone(entry.artifact.content_id)

            resolved = ModelArtifactResolver(model_store=store).resolve("qwen3-8b-ov-integration")
            self.assertTrue(resolved.imported)
            self.assertEqual(resolved.artifact.backend, "openvino")

            manifest_path = entry.manifest_path
            self.assertTrue(manifest_path.is_file())

            fake = FakeService()
            session = OpenVINOChatSession(str(manifest_path), service=fake)
            self.assertEqual(len(session.history), 0)
            session.close()
            self.assertTrue(getattr(fake, "closed", False))


if __name__ == "__main__":
    unittest.main()
