import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from castlearq.sycl_runner import SyclLlamaRunner

from castlearq.execution import ExecutionErrorCode

from castlearq.offload_evidence import GpuOffloadEvidence, OffloadStatus, assess_gpu_offload

import subprocess

def make_completed(stdout=b"out", stderr=b"err", rc=0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = rc
    return m


def test_args_and_env():
    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    fake = make_completed()
    calls = []
    def rp(*a, **k):
        calls.append((a, k))
        return fake
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider, run_process=rp, gpu_layers=5, ctx_size=10, n_predict=3)
    art = SimpleNamespace(path="/m/model.gguf")
    before = dict(os.environ)
    res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=7))
    assert res.success is True
    argv = calls[0][0][0]
    assert argv[0] == "/bin/llama-cli"
    assert "cli" not in argv
    assert "--device" in argv and argv[argv.index("--device") + 1] == "SYCL0"
    assert "-ngl" in argv and argv[argv.index("-ngl") + 1] == "5"
    assert "-c" in argv and argv[argv.index("-c") + 1] == "10"
    assert "-n" in argv and argv[argv.index("-n") + 1] == "3"
    assert calls[0][1]["env"] == {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    assert os.environ == before


def test_failure_code():
    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    fake = make_completed(rc=1)
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider, run_process=lambda *a, **k: fake)
    art = SimpleNamespace(path="/m/model.gguf")
    res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=7))
    assert res.success is False
    assert res.exit_code == 1
    assert res.error.code == ExecutionErrorCode.INVALID_REQUEST


def test_env_error():
    from castlearq.sycl_environment import SyclEnvironmentError
    provider = MagicMock()
    provider.load.side_effect = SyclEnvironmentError("boom")
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider)
    art = SimpleNamespace(path="/m/model.gguf")
    res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=7))
    assert res.success is False


def test_timeout():
    """Test that timeout is respected in the runner."""
    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider, timeout_seconds=1)
    art = SimpleNamespace(path="/m/model.gguf")
    with patch.object(runner, "_run_process") as mock_rp:
        mock_rp.side_effect = subprocess.TimeoutExpired("/bin/llama-cli", 1)
        res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=10))
        assert res.success is False
        assert res.diagnostics.timed_out is True
        assert res.error.code == ExecutionErrorCode.TIMEOUT


def test_os_launch_error():
    """Test that OSError when launching the executable is handled."""
    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider)
    art = SimpleNamespace(path="/m/model.gguf")
    with patch.object(runner, "_run_process") as mock_rp:
        mock_rp.side_effect = OSError("failed to execute")
        res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=10))
        assert res.success is False
        assert res.error.code == ExecutionErrorCode.EXECUTABLE_MISSING


def test_env_not_modified():
    """Test that os.environ is not modified by the runner."""
    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}
    before = dict(os.environ)
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider)
    art = SimpleNamespace(path="/m/model.gguf")
    res = runner.run(art, request=SimpleNamespace(prompt="hi", timeout_seconds=7))
    assert os.environ == before


def test_successful_sycl_execution_has_offload_evidence():
    """Test that a successful SYCL run produces offload_evidence."""
    from unittest.mock import MagicMock
    from castlearq.sycl_runner import SyclLlamaRunner

    from castlearq.execution import ExecutionErrorCode
    from castlearq.offload_evidence import OffloadStatus

    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}

    # Create capability with correct runtime version for SYCL
    capability = type("Capability", (), {
        "runtime_version": "0.7.0-dev (build 11776, commit ead9f3205)",
        "supported_backends": ("SYCL",),
    })()

    calls = []
    # Fake output with the load_tensors pattern that assess_gpu_offload expects
    fake_stdout = "load_tensors: offloaded 23/23 layers to GPU"
    fake_stderr = b""
    def rp(*a, **k):
        calls.append((a, k))
        fake = MagicMock()
        fake.stdout = fake_stdout
        fake.stderr = fake_stderr
        fake.returncode = 0
        return fake
    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider, 
                     runtime_version="0.7.0-dev (build 11776, commit ead9f3205)", run_process=rp)

    art = SimpleNamespace(path="/m/model.gguf")
    res = runner.run(art, request=None)

    assert res.success is True
    assert res.offload_evidence is not None
    assert res.offload_evidence.status == OffloadStatus.CONFIRMED
    assert res.offload_evidence.backend == "SYCL"
    assert res.offload_evidence.offloaded_layers == 23
    assert res.offload_evidence.total_layers == 23
    assert res.offload_evidence.evidence_category == "final_count"
    # Pattern is in stdout only, so source_stream is "stdout"
    assert res.offload_evidence.source_stream == "stdout"


def test_sycl_timeout_has_offload_evidence_timeout():
    """Test that SYCL timeout sets offload_evidence with timeout category."""
    from unittest.mock import MagicMock, patch
    from castlearq.sycl_runner import SyclLlamaRunner

    from castlearq.execution import ExecutionErrorCode
    from castlearq.offload_evidence import OffloadStatus

    provider = MagicMock()
    provider.load.return_value = {"PATH": "x", "LD_LIBRARY_PATH": "y", "ONEAPI_ROOT": "z"}

    runner = SyclLlamaRunner("/bin/llama-cli", "/opt/setvars.sh", env_provider=provider, timeout_seconds=1)
    art = SimpleNamespace(path="/m/model.gguf")

    with patch.object(runner, "_run_process") as mock_rp:
        mock_rp.side_effect = subprocess.TimeoutExpired("/bin/llama-cli", 1)
        res = runner.run(art, request=None)

        assert res.success is False
        assert res.diagnostics.timed_out is True
        assert res.offload_evidence is not None
        assert res.offload_evidence.evidence_category == "timeout"
        # When timed_out=True, the classifier short-circuits before checking backend
        assert res.offload_evidence.backend is None
        assert res.error.code == ExecutionErrorCode.TIMEOUT


def test_sycl_not_executed_has_offload_evidence():
    """Test that not executed SYCL runs have offload_evidence."""
    from castlearq.offload_evidence import assess_gpu_offload, OffloadStatus

    # When not_executed=True, backend is None (fails-closed)
    evidence = assess_gpu_offload(
        None, None, None, not_executed=True,
        runtime_version="0.7.0-dev (build 11776, commit ead9f3205)",
        backend="SYCL",
    )

    assert evidence.status == OffloadStatus.UNKNOWN
    assert evidence.evidence_category == "not_executed"
    # When not_executed=True, backend is None (the classifier fails-closed
    # before checking backend version compatibility)
    assert evidence.backend is None


if __name__ == "__main__":
    import unittest
    unittest.main()
