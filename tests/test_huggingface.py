
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

import json
import unittest
from urllib.error import HTTPError

from app.models import ArtifactState
from app.sources.huggingface import HuggingFaceSource, SourceError, detect_quantization


def source(payload):
    return HuggingFaceSource(
        transport=lambda _url, _timeout: json.dumps(payload).encode(),
        model_id_provider=lambda _repository: "test/model",
    )


def default_source(payload):
    return HuggingFaceSource(transport=lambda _url, _timeout: json.dumps(payload).encode())


def source_responses(model_payload, tree_payload):
    def transport(url, _timeout):
        payload = tree_payload if "/tree/" in url else model_payload
        return json.dumps(payload).encode()

    return HuggingFaceSource(
        transport=transport,
        model_id_provider=lambda _repository: "test/model",
    )


class HuggingFaceTests(unittest.TestCase):
    def test_default_mapping_assigns_logical_model_id(self):
        artifact = default_source({"siblings": [
            {"rfilename": "model.Q4_K_M.gguf", "size": 10, "lfs": {"sha256": "a" * 64}},
        ]}).discover_artifacts("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")[0]
        self.assertEqual(artifact.model_id, "qwen2.5-coder-7b-instruct")
        self.assertEqual(artifact.repository, "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
        self.assertNotEqual(artifact.model_id, artifact.repository)

    def test_unmapped_repository_has_no_logical_identity(self):
        with self.assertRaisesRegex(SourceError, "not mapped"):
            default_source({"siblings": []}).discover_artifacts("owner/repository")
    def test_repository_and_artifact_resolution(self):
        result = source({"siblings": [
            {"rfilename": "model.Q4_K_M.gguf", "size": 10, "lfs": {"sha256": "a" * 64}},
            {"rfilename": "README.md", "size": 1},
        ]}).discover_artifacts("owner/repository")
        self.assertEqual(len(result), 1)
        artifact = result[0]
        self.assertEqual(artifact.source, "huggingface")
        self.assertEqual(artifact.quantization, "Q4_K_M")
        self.assertEqual(artifact.state, ArtifactState.NOT_DOWNLOADED)
        self.assertEqual(artifact.sha256, "a" * 64)

    def test_quantization_patterns_and_unknown(self):
        self.assertEqual(detect_quantization("foo.Q2_K.gguf"), "Q2_K")
        self.assertEqual(detect_quantization("foo.Q3_K_M.gguf"), "Q3_K_M")
        self.assertEqual(detect_quantization("foo.Q4_K_M.gguf"), "Q4_K_M")
        self.assertEqual(detect_quantization("foo.Q5_K_M.gguf"), "Q5_K_M")
        self.assertEqual(detect_quantization("foo.Q6_K.gguf"), "Q6_K")
        self.assertEqual(detect_quantization("foo-q8_0.gguf"), "Q8_0")
        self.assertEqual(detect_quantization("foo-q4_0.gguf"), "Q4_0")
        self.assertEqual(detect_quantization("foo-q4_0-00001-of-00002.gguf"), "Q4_0")
        self.assertEqual(detect_quantization("foo-q5_0.gguf"), "Q5_0")
        self.assertEqual(detect_quantization("foo-q5_0-00001-of-00002.gguf"), "Q5_0")
        self.assertEqual(detect_quantization("foo.gguf"), "Unknown")

    def test_invalid_repository_and_filename(self):
        with self.assertRaises(SourceError):
            source({"siblings": []}).discover_artifacts("../bad")
        with self.assertRaises(SourceError):
            source({"siblings": [{"rfilename": "../model.gguf"}]}).discover_artifacts("owner/repo")

    def test_invalid_size_and_hash(self):
        with self.assertRaises(SourceError):
            source({"siblings": [{"rfilename": "model.gguf", "size": -1}]}).discover_artifacts("owner/repo")
        with self.assertRaises(SourceError):
            source({"siblings": [{"rfilename": "model.gguf", "lfs": {"sha256": "bad"}}]}).discover_artifacts("owner/repo")

    def test_missing_files_and_invalid_json(self):
        self.assertEqual(source({"siblings": []}).discover_artifacts("owner/repo"), [])
        with self.assertRaises(SourceError):
            HuggingFaceSource(
                transport=lambda _url, _timeout: b"invalid",
                model_id_provider=lambda _repository: "test/model",
            ).discover_artifacts("owner/repo")

    def test_no_checksum_is_none(self):
        artifact = source({"files": [{"path": "model.Q8_0.gguf"}]}).discover_artifacts("owner/repo")[0]
        self.assertIsNone(artifact.sha256)
        self.assertIsNone(artifact.size_bytes)

    def test_transport_does_not_receive_artifact_url(self):
        calls = []
        def transport(url, _timeout):
            calls.append(url)
            return b'{"siblings": []}'
        HuggingFaceSource(
            transport=transport, model_id_provider=lambda _repository: "test/model"
        ).discover_artifacts("owner/repo")
        self.assertEqual(len(calls), 1)
        self.assertIn("/api/models/owner/repo", calls[0])
        self.assertNotIn("/resolve/", calls[0])

    def test_api_host_must_be_huggingface_https(self):
        provider = lambda _repository: "test/model"  # noqa: E731
        with self.assertRaises(SourceError):
            HuggingFaceSource(api_base="http://huggingface.co/api", transport=lambda *_: b"{}", model_id_provider=provider).discover_artifacts("owner/repo")
        with self.assertRaises(SourceError):
            HuggingFaceSource(api_base="https://evil.example/api", transport=lambda *_: b"{}", model_id_provider=provider).discover_artifacts("owner/repo")

    def test_http_errors_and_timeout_are_controlled(self):
        def not_found(url, _timeout):
            raise HTTPError(url, 404, "not found", {}, None)

        def server_error(url, _timeout):
            raise HTTPError(url, 500, "server error", {}, None)

        for transport in (not_found, server_error):
            with self.assertRaises(SourceError):
                HuggingFaceSource(
                    transport=transport, model_id_provider=lambda _repository: "test/model"
                ).discover_artifacts("owner/repo")
        with self.assertRaises(SourceError):
            HuggingFaceSource(
                transport=lambda _url, _timeout: (_ for _ in ()).throw(
                    TimeoutError("timeout")
                ),
                model_id_provider=lambda _repository: "test/model",
            ).discover_artifacts("owner/repo")

    def test_url_and_artifact_metadata_are_safe(self):
        artifact = source(
            {"siblings": [{"rfilename": "foo-Q4_K_M.gguf", "size": 0}]}
        ).discover_artifacts("owner/repository")[0]
        self.assertTrue(artifact.download_url.startswith("https://huggingface.co/"))
        self.assertEqual(artifact.size_bytes, 0)

    def test_tree_metadata_enriches_gguf_artifact(self):
        sha256 = "b" * 64
        artifact = source_responses(
            {"siblings": [{"rfilename": "model.Q4_K_M.gguf"}]},
            [{"path": "model.Q4_K_M.gguf", "size": 12, "lfs": {
                "size": 12, "oid": sha256
            }}],
        ).discover_artifacts("owner/repository")[0]
        self.assertEqual(artifact.size_bytes, 12)
        self.assertEqual(artifact.sha256, sha256)

    def test_tree_uses_lfs_size_when_size_is_missing(self):
        artifact = source_responses(
            {"siblings": [{"rfilename": "model.Q4_K_M.gguf"}]},
            [{"path": "model.Q4_K_M.gguf", "lfs": {
                "size": 13, "oid": "c" * 64
            }}],
        ).discover_artifacts("owner/repository")[0]
        self.assertEqual(artifact.size_bytes, 13)

    def test_tree_without_lfs_preserves_unknown_metadata(self):
        artifact = source_responses(
            {"siblings": [{"rfilename": "model.Q4_K_M.gguf"}]},
            [{"path": "model.Q4_K_M.gguf", "size": 14}],
        ).discover_artifacts("owner/repository")[0]
        self.assertEqual(artifact.size_bytes, 14)
        self.assertIsNone(artifact.sha256)

    def test_invalid_tree_oid_is_not_accepted_as_sha256(self):
        artifact = source_responses(
            {"siblings": [{"rfilename": "model.Q4_K_M.gguf"}]},
            [{"path": "model.Q4_K_M.gguf", "size": 15, "lfs": {
                "oid": "not-a-sha256", "xetHash": "d" * 64
            }}],
        ).discover_artifacts("owner/repository")[0]
        self.assertIsNone(artifact.sha256)

    def test_tree_selects_exact_filename_among_multiple_files(self):
        artifact = source_responses(
            {"siblings": [
                {"rfilename": "other.Q4_K_M.gguf"},
                {"rfilename": "target.Q4_K_M.gguf"},
            ]},
            [
                {"path": "other.Q4_K_M.gguf", "size": 16, "lfs": {"oid": "e" * 64}},
                {"path": "target.Q4_K_M.gguf", "size": 17, "lfs": {"oid": "f" * 64}},
            ],
        ).discover_artifacts("owner/repository")
        self.assertEqual([(item.filename, item.size_bytes, item.sha256) for item in artifact], [
            ("other.Q4_K_M.gguf", 16, "e" * 64),
            ("target.Q4_K_M.gguf", 17, "f" * 64),
        ])

    def test_tree_does_not_use_xet_hash_as_sha256(self):
        artifact = source_responses(
            {"siblings": [{"rfilename": "model.Q4_K_M.gguf"}]},
            [{"path": "model.Q4_K_M.gguf", "size": 18, "xetHash": "a" * 64}],
        ).discover_artifacts("owner/repository")[0]
        self.assertIsNone(artifact.sha256)


if __name__ == "__main__":
    unittest.main()
