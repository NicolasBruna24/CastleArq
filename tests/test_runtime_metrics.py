
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

import unittest
from dataclasses import FrozenInstanceError

from app.execution import RuntimeMetricSource, RuntimeMetrics
from app.runtime_metrics import parse_llama_human_output


class RuntimeMetricsParserTests(unittest.TestCase):
    def test_parses_decimal_metrics(self):
        result = parse_llama_human_output(
            "[ Prompt: 256.2 t/s | Generation: 40.2 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 256.2)
        self.assertEqual(result.generation_tokens_per_second, 40.2)
        self.assertEqual(result.source, RuntimeMetricSource.LLAMA_HUMAN_OUTPUT)

    def test_parses_comma_decimal_metrics(self):
        result = parse_llama_human_output(
            "[ Prompt: 256,2 t/s | Generation: 40,2 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 256.2)
        self.assertEqual(result.generation_tokens_per_second, 40.2)

    def test_parses_integer_metrics(self):
        result = parse_llama_human_output("[ Prompt: 256 t/s | Generation: 40 t/s ]")
        self.assertEqual(result.prompt_tokens_per_second, 256.0)
        self.assertEqual(result.generation_tokens_per_second, 40.0)

    def test_parses_scientific_notation_with_point(self):
        result = parse_llama_human_output(
            "[ Prompt: 2.562e2 t/s | Generation: 4.02e1 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 256.2)
        self.assertEqual(result.generation_tokens_per_second, 40.2)

    def test_parses_scientific_notation_with_comma(self):
        result = parse_llama_human_output(
            "[ Prompt: 2,562e2 t/s | Generation: 4,02e1 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 256.2)
        self.assertEqual(result.generation_tokens_per_second, 40.2)

    def test_parses_mixed_decimal_separators(self):
        result = parse_llama_human_output(
            "[ Prompt: 256,2 t/s | Generation: 40.2 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 256.2)
        self.assertEqual(result.generation_tokens_per_second, 40.2)

    def test_tolerates_reasonable_spacing_and_surrounding_output(self):
        result = parse_llama_human_output(
            "response\n[  Prompt : 1.25 t / s  |  Generation : 2e1 t/s  ]\ncomplete"
        )
        self.assertEqual(result.prompt_tokens_per_second, 1.25)
        self.assertEqual(result.generation_tokens_per_second, 20.0)

    def test_parses_partial_metric_blocks(self):
        prompt_only = parse_llama_human_output("[ Prompt: 100 t/s | ]")
        generation_only = parse_llama_human_output("[ | Generation: 42 t/s ]")
        self.assertEqual(prompt_only.prompt_tokens_per_second, 100.0)
        self.assertIsNone(prompt_only.generation_tokens_per_second)
        self.assertIsNone(generation_only.prompt_tokens_per_second)
        self.assertEqual(generation_only.generation_tokens_per_second, 42.0)

    def test_multiple_valid_blocks_return_the_last(self):
        result = parse_llama_human_output(
            "[ Prompt: 10 t/s | Generation: 5 t/s ]\n"
            "[ Prompt: 20 t/s | Generation: 8 t/s ]\n"
            "[ Prompt: 30 t/s | Generation: 9 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 30.0)
        self.assertEqual(result.generation_tokens_per_second, 9.0)

    def test_fake_block_echoed_before_real_metrics_is_ignored(self):
        # Reproduces the real llama.cpp output where the echoed prompt and the
        # generated text both contain the metrics shape before the real block.
        text = (
            "> Reply with exactly this text: [ Prompt: 999 t/s | Generation: 999 t/s ]\n"
            "[ Prompt: 999 t/s | Generation: 999 t/s ]\n"
            "[ Prompt: 72,5 t/s | Generation: 9,0 t/s ]\n"
            "Exiting..."
        )
        result = parse_llama_human_output(text)
        self.assertEqual(result.prompt_tokens_per_second, 72.5)
        self.assertEqual(result.generation_tokens_per_second, 9.0)

    def test_trailing_invalid_block_does_not_hide_the_last_valid_one(self):
        result = parse_llama_human_output(
            "[ Prompt: 100 t/s | Generation: 50 t/s ]\n"
            "[ Prompt: t/s | Generation: t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 100.0)
        self.assertEqual(result.generation_tokens_per_second, 50.0)

    def test_returns_none_without_a_recognizable_block(self):
        for text in (
            "normal llama response",
            "Prompt: 123",
            "[ Prompt: 100 t/s | Generation: 42 t/s",
            "Prompt: 100 t/s | Generation: 42 t/s ]",
        ):
            with self.subTest(text=text):
                self.assertIsNone(parse_llama_human_output(text))

    def test_returns_none_for_malformed_blocks(self):
        for text in (
            "[ Prompt: t/s | Generation: 42 t/s ]",
            "[ Prompt: 100 | Generation: 42 t/s ]",
            "[ Prompt: 100 t/s Generation: 42 t/s ]",
            "[ Prompt: 100 t/s | Generation: t/s ]",
            "[ Prompt: 100 t/s | Generation: 42 ]",
            "[ Prompt: 100 t/s || Generation: 42 t/s ]",
        ):
            with self.subTest(text=text):
                self.assertIsNone(parse_llama_human_output(text))

    def test_rejects_invalid_values_without_affecting_valid_metric(self):
        cases = (
            ("[ Prompt: -1 t/s | Generation: 42 t/s ]", None, 42.0),
            ("[ Prompt: NaN t/s | Generation: 42 t/s ]", None, 42.0),
            ("[ Prompt: inf t/s | Generation: 42 t/s ]", None, 42.0),
            ("[ Prompt: Infinity t/s | Generation: 42 t/s ]", None, 42.0),
            ("[ Prompt: -inf t/s | Generation: 42 t/s ]", None, 42.0),
            ("[ Prompt: abc t/s | Generation: 42 t/s ]", None, 42.0),
        )
        for text, prompt, generation in cases:
            with self.subTest(text=text):
                result = parse_llama_human_output(text)
                self.assertEqual(result.prompt_tokens_per_second, prompt)
                self.assertEqual(result.generation_tokens_per_second, generation)

    def test_invalid_values_on_both_sides_return_none(self):
        self.assertIsNone(
            parse_llama_human_output("[ Prompt: -1 t/s | Generation: NaN t/s ]")
        )

    def test_parser_does_not_mutate_input_and_result_is_frozen(self):
        text = "[ Prompt: 100 t/s | Generation: 42 t/s ]"
        result = parse_llama_human_output(text)
        self.assertEqual(text, "[ Prompt: 100 t/s | Generation: 42 t/s ]")
        self.assertIsInstance(result, RuntimeMetrics)
        with self.assertRaises(FrozenInstanceError):
            result.prompt_tokens_per_second = 1

    def test_arbitrary_input_type_is_ignored(self):
        self.assertIsNone(parse_llama_human_output(None))


if __name__ == "__main__":
    unittest.main()
