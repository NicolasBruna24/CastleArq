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

"""B9.80 tests."""
from __future__ import annotations
import dataclasses
import unittest
from pathlib import Path
from castlearq.discovery import DiscoveredArtifact, DiscoveryError
from castlearq.discovery import ModelCandidate, ModelDiscovery, ModelVariant
def _candidate(**over):
    base = {"provider_id": "hf", "repository": "owner/repo"}
    base.update(over)
    return ModelCandidate(**base)


def _artifact(**over):
    base = {"repository": "owner/repo", "filename": "m-Q4_K_M.gguf"}
    base.update(over)
    return DiscoveredArtifact(**base)


class FakeDiscovery(ModelDiscovery):
    def __init__(self, cands, variants):
        self.cands = cands
        self.variants = variants
        self.seen = {}

    def search(self, query, *, limit=20, cursor=None):
        self.seen.update(query=query, limit=limit, cursor=cursor)
        return (self.cands, "opaque-2")

    def inspect(self, repository):
        self.seen["repository"] = repository
        return self.variants


class CandidateTests(unittest.TestCase):
    def test_valid_minimal(self):
        c = _candidate()
        self.assertEqual((c.provider_id, c.tags, c.has_gguf), ("hf", (), False))

    def test_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            _candidate().provider_id = "x"  # type: ignore[misc]

    def test_optional_fields(self):
        c = _candidate(author="a", tags=("x",), has_gguf=True)
        self.assertEqual(c.author, "a")
        self.assertTrue(c.has_gguf)

    def test_no_l2_l3(self):
        for f in ("catalog_model_id", "local_path", "state", "content_id",
                  "verified_sha256", "verdict", "admission", "execution"):
            self.assertNotIn(f, ModelCandidate.__dataclass_fields__)


class VariantTests(unittest.TestCase):
    def test_valid(self):
        v = ModelVariant(candidate=_candidate(),
                         declared_quantization="Q4_K_M",
                         artifacts=(_artifact(),))
        self.assertEqual(len(v.artifacts), 1)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            ModelVariant(candidate=_candidate(),
                         declared_quantization="Q4_K_M", artifacts=())

    def test_declared_not_verified(self):
        self.assertIn("declared_quantization", ModelVariant.__dataclass_fields__)
        self.assertNotIn("verified_quantization", ModelVariant.__dataclass_fields__)


class ArtifactTests(unittest.TestCase):
    def test_valid(self):
        a = _artifact(declared_quantization="Q4_K_M", declared_size=10,
                      declared_sha256="ab", revision="main")
        self.assertEqual(a.declared_size, 10)

    def test_no_local_state(self):
        for f in ("local_path", "state", "content_id", "verdict",
                  "verified_quantization", "verified_sha256"):
            self.assertNotIn(f, DiscoveredArtifact.__dataclass_fields__)

    def test_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            _artifact().filename = "z"  # type: ignore[misc]


class PortTests(unittest.TestCase):
    def test_methods(self):
        self.assertIn("search", ModelDiscovery.__abstractmethods__)
        self.assertIn("inspect", ModelDiscovery.__abstractmethods__)

    def test_fake(self):
        c = _candidate()
        v = ModelVariant(candidate=c, declared_quantization="Q4_K_M",
                         artifacts=(_artifact(),))
        fk = FakeDiscovery((c,), (v,))
        cands, nxt = fk.search("llama", limit=5, cursor="opaque-1")
        self.assertEqual(cands, (c,))
        self.assertEqual((nxt, fk.seen["limit"], fk.seen["cursor"]),
                         ("opaque-2", 5, "opaque-1"))
        self.assertEqual(fk.inspect("owner/repo"), (v,))

    def test_no_hf(self):
        src = Path("castlearq/discovery.py").read_text(encoding="utf-8")
        self.assertNotIn("huggingface", src.lower())


class IsolationTests(unittest.TestCase):
    def test_no_deps(self):
        low = Path("castlearq/discovery.py").read_text(encoding="utf-8").lower()
        for bad in ("modelstore", "downloader", "downloadplanner",
                    "runtime_artifact", "huggingface"):
            self.assertNotIn(bad, low)

    def test_error(self):
        from castlearq.sources.huggingface import SourceError
        self.assertTrue(issubclass(DiscoveryError, Exception))
        self.assertIsNot(DiscoveryError, SourceError)


if __name__ == "__main__":
    unittest.main()
