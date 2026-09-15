
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

"""Unit tests for non-heuristic artifact selection."""

from __future__ import annotations

import unittest

from app.artifact_selection import ArtifactSelectionError, select_artifact
from app.models import ArtifactSpec


def _artifact(
    filename: str = "model-q4_k_m.gguf",
    quantization: str = "Q4_K_M",
    model_id: str = "qwen2.5-coder-7b-instruct",
) -> ArtifactSpec:
    return ArtifactSpec(
        model_id=model_id,
        source="huggingface",
        repository="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename=filename,
        format="GGUF",
        quantization=quantization,
        download_url=f"https://example.com/{filename}",
        size_bytes=1000,
        sha256="a" * 64,
    )


class ArtifactSelectionTests(unittest.TestCase):
    def test_single_artifact_without_selector(self):
        a1 = _artifact()
        self.assertIs(select_artifact([a1]), a1)

    def test_zero_artifacts_without_selector_raises(self):
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([])
        self.assertIn("No GGUF artifacts found", str(ctx.exception))

    def test_multiple_artifacts_without_selector_raises_ambiguity(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([a1, a2])
        self.assertIn("multiple artifacts", str(ctx.exception))
        self.assertIn("--quantization", str(ctx.exception))

    def test_exact_quantization_match(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        selected = select_artifact([a1, a2], quantization="Q4_K_M")
        self.assertIs(selected, a1)

    def test_quantization_match_is_case_insensitive(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        selected = select_artifact([a1, a2], quantization="q4_k_m")
        self.assertIs(selected, a1)

    def test_nonexistent_quantization_raises(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([a1], quantization="Q9_K_M")
        self.assertIn("No artifact matches quantization", str(ctx.exception))
        self.assertIn("Q9_K_M", str(ctx.exception))

    def test_ambiguous_quantization_raises_and_suggests_filename(self):
        shard1 = _artifact(filename="model-q4-00001.gguf", quantization="Q4_K_M")
        shard2 = _artifact(filename="model-q4-00002.gguf", quantization="Q4_K_M")
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([shard1, shard2], quantization="Q4_K_M")
        self.assertIn("Multiple artifacts match quantization", str(ctx.exception))
        self.assertIn("--filename", str(ctx.exception))

    def test_exact_filename_match(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        selected = select_artifact([a1, a2], filename="model-q8.gguf")
        self.assertIs(selected, a2)

    def test_nonexistent_filename_raises(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([a1], filename="missing.gguf")
        self.assertIn("No artifact matches filename", str(ctx.exception))
        self.assertIn("missing.gguf", str(ctx.exception))

    def test_both_selectors_matching_same_artifact(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        selected = select_artifact(
            [a1, a2], quantization="Q4_K_M", filename="model-q4.gguf"
        )
        self.assertIs(selected, a1)

    def test_both_selectors_conflicting_raises(self):
        a1 = _artifact(filename="model-q4.gguf", quantization="Q4_K_M")
        a2 = _artifact(filename="model-q8.gguf", quantization="Q8_0")
        with self.assertRaises(ArtifactSelectionError) as ctx:
            select_artifact([a1, a2], quantization="Q4_K_M", filename="model-q8.gguf")
        self.assertIn("No artifact matches both", str(ctx.exception))

    def test_both_selectors_disambiguates_shards(self):
        shard1 = _artifact(filename="model-q4-00001.gguf", quantization="Q4_K_M")
        shard2 = _artifact(filename="model-q4-00002.gguf", quantization="Q4_K_M")
        selected = select_artifact(
            [shard1, shard2], quantization="Q4_K_M", filename="model-q4-00001.gguf"
        )
        self.assertIs(selected, shard1)

    def test_unsafe_filename_selector_raises(self):
        a1 = _artifact()
        for unsafe in ("../model.gguf", "/tmp/model.gguf", "a/b.gguf", "a\\b.gguf", "   ", ""):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ArtifactSelectionError):
                    select_artifact([a1], filename=unsafe)

    def test_empty_quantization_selector_raises(self):
        a1 = _artifact()
        for empty in ("", "   "):
            with self.subTest(empty=empty):
                with self.assertRaises(ArtifactSelectionError):
                    select_artifact([a1], quantization=empty)

    def test_never_uses_first_match(self):
        first = _artifact(filename="first.gguf", quantization="Q4_K_M")
        second = _artifact(filename="second.gguf", quantization="Q4_K_M")
        # Without filename, it must reject rather than taking first
        with self.assertRaises(ArtifactSelectionError):
            select_artifact([first, second], quantization="Q4_K_M")


if __name__ == "__main__":
    unittest.main()

