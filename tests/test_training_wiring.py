# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Wiring tests for the bounded training composition root.

Training dependencies compose through ``application_wiring`` exactly like
the execute path, and execute wiring behavior is unchanged.
"""

from __future__ import annotations

import unittest

from castlearq import application_wiring as wiring
from castlearq.training import TrainingDependencies


class ComposeTrainingTests(unittest.TestCase):
    def test_compose_returns_training_dependencies(self):
        deps = wiring.compose_training_dependencies()
        self.assertIsInstance(deps, TrainingDependencies)
        self.assertIsNotNone(deps.runner)

    def test_compose_prefers_injected_runner(self):
        sentinel = object()
        deps = wiring.compose_training_dependencies(runner=sentinel)
        self.assertIs(deps.runner, sentinel)

    def test_compose_is_fresh_each_call(self):
        first = wiring.compose_training_dependencies()
        second = wiring.compose_training_dependencies()
        self.assertIsNot(first, second)
        self.assertIsNot(first.runner, second.runner)

    def test_execute_composition_still_binds_llama_runner(self):
        from castlearq.runner import LlamaCppRunner

        deps = wiring.compose_execute_model_dependencies()
        self.assertIsInstance(deps.runner, LlamaCppRunner)


if __name__ == "__main__":
    unittest.main()
