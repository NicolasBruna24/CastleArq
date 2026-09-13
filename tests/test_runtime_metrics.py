import unittest
from dataclasses import FrozenInstanceError

from app.execution import RuntimeMetricSource, RuntimeMetrics
from app.runtime_metrics import parse_llama_human_output


class RuntimeMetricsParserTests(unittest.TestCase):
    def test_parses_decimal_metrics(self):
        result = parse_llama_human_output(
            "[ Prompt: 100.5 t/s | Generation: 42.25 t/s ]"
        )
        self.assertEqual(result.prompt_tokens_per_second, 100.5)
        self.assertEqual(result.generation_tokens_per_second, 42.25)
        self.assertEqual(result.source, RuntimeMetricSource.LLAMA_HUMAN_OUTPUT)

    def test_parses_integer_metrics(self):
        result = parse_llama_human_output("[ Prompt: 100 t/s | Generation: 42 t/s ]")
        self.assertEqual(result.prompt_tokens_per_second, 100.0)
        self.assertEqual(result.generation_tokens_per_second, 42.0)

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
