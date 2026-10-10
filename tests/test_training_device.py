# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License").

"""Unit tests for training backend selection (XPU > CUDA > CPU).

All backends are mocked; no GPU, torch, or training stack is required.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from castlearq.training_runner import select_training_device


def _torch_double(*, xpu=None, cuda=None):
    return SimpleNamespace(xpu=xpu, cuda=cuda)


def _backend(available=True, *, raises=False):
    def _is_available():
        if raises:
            raise RuntimeError("backend probe failed")
        return available

    return SimpleNamespace(is_available=_is_available)


class SelectTrainingDeviceTests(unittest.TestCase):
    def test_xpu_available_selects_xpu(self):
        torch = _torch_double(xpu=_backend(True), cuda=_backend(True))
        self.assertEqual(select_training_device(torch), "xpu")

    def test_cuda_selected_when_xpu_unavailable(self):
        torch = _torch_double(xpu=_backend(False), cuda=_backend(True))
        self.assertEqual(select_training_device(torch), "cuda")

    def test_cpu_selected_when_neither_available(self):
        torch = _torch_double(xpu=_backend(False), cuda=_backend(False))
        self.assertEqual(select_training_device(torch), "cpu")

    def test_missing_backend_attributes_fall_back_to_cpu(self):
        self.assertEqual(select_training_device(SimpleNamespace()), "cpu")
        self.assertEqual(
            select_training_device(SimpleNamespace(xpu=None, cuda=None)), "cpu"
        )
        # xpu present but without is_available; cuda available still wins.
        torch = _torch_double(
            xpu=SimpleNamespace(), cuda=_backend(True)
        )
        self.assertEqual(select_training_device(torch), "cuda")

    def test_backend_probe_errors_do_not_crash(self):
        torch = _torch_double(
            xpu=_backend(raises=True), cuda=_backend(True)
        )
        self.assertEqual(select_training_device(torch), "cuda")
        torch = _torch_double(
            xpu=_backend(raises=True), cuda=_backend(raises=True)
        )
        self.assertEqual(select_training_device(torch), "cpu")


if __name__ == "__main__":
    unittest.main()
