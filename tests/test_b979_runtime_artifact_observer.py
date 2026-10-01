
# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.79: runtime artifact observer tests with an injected subprocess."""

from __future__ import annotations

import os
import subprocess
import unittest
from unittest import mock

from castlearq.runtime_artifact_evidence import ArtifactObservation
from castlearq.runtime_artifact_observer import (
    RuntimeArtifactObserver,
    RuntimeObservationError,
)

LOAD_LINE = "llama_model_loader: loaded meta data with 29 key-value pairs"
REJECT_LINE = "error loading model: unknown model architecture"


def _observe(run_process, **overrides):
    observer = RuntimeArtifactObserver(run_process)
    params = {
        "executable_path": "/usr/local/bin/llama",
        "runtime_identity": "/usr/local/bin/llama",
        "runtime_version": "llama.cpp 0.4.0-dev",
        "artifact_path": "/models/repo/abc/model.gguf",
        "artifact_reference": "abc",
        "artifact_format": "GGUF",
        "artifact_architecture": "qwen2",
        "device": "Vulkan0",
    }
    params.update(overrides)
    return observer.observe(**params)


def _completed(returncode=0, stdout=b"", stderr=b""):
    process = mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)
    return mock.Mock(return_value=process), process


class InvocationTests(unittest.TestCase):
    def test_builds_the_verified_observation_argv(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        _observe(run)
        argv = run.call_args.args[0]
        self.assertEqual(
            argv,
            [
                "/usr/local/bin/llama", "cli", "--simple-io", "--single-turn",
                "--model", "/models/repo/abc/model.gguf", "--device", "Vulkan0",
                "--prompt", "hi", "-n", "0", "-lv", "4",
            ],
        )

    def test_no_meaningful_generation_and_no_repl(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        _observe(run)
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("-n") + 1], "0")
        self.assertEqual(argv[argv.index("-lv") + 1], "4")
        self.assertIn("--single-turn", argv)

    def test_uses_a_controlled_and_bounded_process(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        _observe(run, timeout_seconds=33.0)
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs["shell"], False)
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["timeout"], 33.0)
        self.assertEqual(kwargs["env"], {"PATH": os.defpath})

    def test_does_not_hardcode_an_executable(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        _observe(run, executable_path="/opt/llama/bin/llama")
        self.assertEqual(run.call_args.args[0][0], "/opt/llama/bin/llama")


class ClassificationTests(unittest.TestCase):
    def test_positive_requires_load_marker_and_zero_exit(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.POSITIVE)
        self.assertIs(item.supports_artifact, True)

    def test_zero_exit_without_signal_is_unknown(self):
        run, _ = _completed(returncode=0, stdout=b"nothing useful", stderr=b"")
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        self.assertIsNone(item.supports_artifact)

    def test_nonzero_without_causal_signal_is_unknown(self):
        run, _ = _completed(returncode=1, stdout=b"", stderr=b"opaque failure")
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        self.assertIsNone(item.supports_artifact)

    def test_explicit_rejection_is_negative(self):
        run, _ = _completed(returncode=1, stdout=b"", stderr=REJECT_LINE.encode())
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.NEGATIVE)
        self.assertIs(item.supports_artifact, False)

    def test_rejection_marker_wins_over_zero_exit(self):
        run, _ = _completed(returncode=0, stdout=REJECT_LINE.encode())
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.NEGATIVE)

    def test_load_marker_with_nonzero_exit_is_not_positive(self):
        run, _ = _completed(returncode=2, stdout=LOAD_LINE.encode())
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)


class FailureAndContextTests(unittest.TestCase):
    def test_timeout_is_unknown(self):
        run = mock.Mock(side_effect=subprocess.TimeoutExpired(cmd="llama", timeout=1))
        item = _observe(run)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        self.assertIn("timed out", item.provenance)

    def test_launch_error_raises_producer_error(self):
        run = mock.Mock(side_effect=OSError("boom"))
        with self.assertRaises(RuntimeObservationError):
            _observe(run)

    def test_missing_device_produces_unknown_without_running(self):
        run = mock.Mock()
        item = _observe(run, device=None)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        self.assertIsNone(item.backend)
        run.assert_not_called()
        self.assertIn("device", item.provenance)

    def test_missing_artifact_path_produces_unknown_without_running(self):
        run = mock.Mock()
        item = _observe(run, artifact_path=None)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        run.assert_not_called()

    def test_missing_executable_produces_unknown_without_running(self):
        run = mock.Mock()
        item = _observe(run, executable_path=None)
        self.assertIs(item.observation, ArtifactObservation.UNKNOWN)
        run.assert_not_called()


class FieldAndProvenanceTests(unittest.TestCase):
    def test_fields_are_populated_from_inputs(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        item = _observe(run)
        self.assertEqual(item.runtime_identity, "/usr/local/bin/llama")
        self.assertEqual(item.runtime_version, "llama.cpp 0.4.0-dev")
        self.assertEqual(item.artifact_reference, "abc")
        self.assertEqual(item.artifact_format, "GGUF")
        self.assertEqual(item.artifact_architecture, "qwen2")
        self.assertEqual(item.backend, "Vulkan0")

    def test_provenance_records_the_real_operation(self):
        run, _ = _completed(returncode=0, stdout=LOAD_LINE.encode())
        item = _observe(run)
        self.assertIn("RuntimeArtifactObserver", item.provenance)
        self.assertIn("-n 0", item.provenance)
        self.assertIn("--device Vulkan0", item.provenance)


if __name__ == "__main__":
    unittest.main()
