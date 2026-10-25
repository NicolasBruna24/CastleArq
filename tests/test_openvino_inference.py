import json
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

from castlearq.model_store import ModelStore
from castlearq.openvino_inference import OpenVINOInferenceService, MissingDependencyError, InvalidArtifactError, PipelineInitError, GenerationError


def make_artifact(tmp_path, fmt="OpenVINO IR", filename="openvino_model.xml"):
    d = tmp_path / "art"
    d.mkdir()
    manifest = {
        "model_id": "m",
        "source": "openvino-export",
        "repository": "r",
        "filename": filename,
        "format": fmt,
        "quantization": "FP16",
        "files": [],
        "files_sha256": None,
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    (d / filename).write_text("<xml/>")
    (d / "openvino_model.bin").write_bytes(b"\x00")
    return d / "manifest.json"


def fake_artifact(fmt="OpenVINO IR", filename="openvino_model.xml"):
    return SimpleNamespace(state=SimpleNamespace(value="downloaded"), format=fmt, filename=filename)


def test_generation_ok(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(texts=["hello"])))
    res = svc.generate(mp, "Hi", device="GPU", max_new_tokens=4)
    assert res.text == "hello"
    assert res.device == "GPU"


def test_reject_gguf(tmp_path):
    mp = make_artifact(tmp_path, fmt="GGUF")
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact(fmt="GGUF")
    svc = OpenVINOInferenceService(store)
    try:
        svc.generate(mp, "Hi")
        assert False
    except InvalidArtifactError:
        pass


def test_missing_dep(tmp_path, monkeypatch):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    import builtins
    real_import = builtins.__import__
    def fake(name, *a, **k):
        if name == "openvino_genai":
            raise ImportError("no")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    svc = OpenVINOInferenceService(store)
    try:
        svc.generate(mp, "Hi")
        assert False
    except MissingDependencyError:
        pass


def test_pipeline_init_error(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        svc.generate(mp, "Hi")
        assert False
    except PipelineInitError:
        pass


def test_generation_error(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    bad = mock.Mock()
    bad.generate.side_effect = RuntimeError("genfail")
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: bad)
    try:
        svc.generate(mp, "Hi")
        assert False
    except GenerationError:
        pass


def test_max_tokens_validation(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock())
    try:
        svc.generate(mp, "Hi", max_new_tokens=0)
        assert False
    except ValueError:
        pass


def test_no_fallback_cpu(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    calls = []
    def factory(d, dev):
        calls.append(dev)
        raise RuntimeError("gpu fail")
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    try:
        svc.generate(mp, "Hi", device="GPU")
    except PipelineInitError:
        pass
    assert calls == ["GPU"]
def test_extract_text_multiple_sequences(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(texts=["first", "second"])))
    res = svc.generate(mp, "Hi")
    assert res.text == "first"


def test_extract_text_string_fallback(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: "direct"))
    res = svc.generate(mp, "Hi")
    assert res.text == "direct"


def test_extract_text_empty_texts_raises(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(texts=[])))
    try:
        svc.generate(mp, "Hi")
        assert False
    except GenerationError:
        pass


def test_extract_text_missing_texts_raises(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(foo="bar")))
    try:
        svc.generate(mp, "Hi")
        assert False
    except GenerationError:
        pass


def test_extract_text_invalid_not_stringified(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: 42))
    try:
        svc.generate(mp, "Hi")
        assert False
    except GenerationError:
        pass


import threading


def test_cache_reuse_same_key(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    calls = []
    def factory(d, dev):
        calls.append((str(d), dev))
        m = mock.Mock()
        m.generate.return_value = SimpleNamespace(texts=["ok"])
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    r1 = svc.generate(mp, "Hi")
    r2 = svc.generate(mp, "Hi2")
    assert r1.text == "ok" and r2.text == "ok"
    assert len(calls) == 1


def test_cache_replace_on_device_change(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    calls = []
    def factory(d, dev):
        calls.append(dev)
        m = mock.Mock()
        m.generate.return_value = SimpleNamespace(texts=["ok"])
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    svc.generate(mp, "Hi", device="CPU")
    svc.generate(mp, "Hi", device="GPU")
    assert calls == ["CPU", "GPU"]


def test_generation_mutual_exclusion(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    def make_pipeline():
        m = mock.Mock()
        def gen(prompt, max_new_tokens=None):
            started.set()
            release.wait(timeout=5)
            return SimpleNamespace(texts=["ok"])
        m.generate.side_effect = gen
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: make_pipeline())
    errors = []
    def worker1():
        try:
            svc.generate(mp, "Hi")
        except Exception as e:
            errors.append(e)
    def worker2():
        started.wait(timeout=5)
        second_started.set()
        try:
            svc.generate(mp, "Hi2")
        except Exception as e:
            errors.append(e)
    t1 = threading.Thread(target=worker1)
    t2 = threading.Thread(target=worker2)
    t1.start()
    t2.start()
    release.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert not errors
    assert not t1.is_alive() and not t2.is_alive()


def test_init_concurrent_same_key_no_duplicate(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    init_count = [0]
    init_lock = threading.Lock()
    gate = threading.Event()
    def factory(d, dev):
        with init_lock:
            init_count[0] += 1
        gate.wait(timeout=5)
        m = mock.Mock()
        m.generate.return_value = SimpleNamespace(texts=["ok"])
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    results = []
    def worker():
        try:
            results.append(svc.generate(mp, "Hi").text)
        except Exception as e:
            results.append(e)
    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    for _ in range(100):
        if init_count[0] >= 1:
            break
        threading.Event().wait(0.01)
    gate.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert init_count[0] == 1
    assert results == ["ok", "ok"]


def test_recovery_after_generation_error(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    calls = {"n": 0}
    def factory(d, dev):
        m = mock.Mock()
        def gen(prompt, max_new_tokens=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return SimpleNamespace(texts=["ok"])
        m.generate.side_effect = gen
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    try:
        svc.generate(mp, "Hi")
        assert False
    except GenerationError:
        pass
    r = svc.generate(mp, "Hi2")
    assert r.text == "ok"


def test_instance_isolation(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    svc1 = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(texts=["a"])))
    svc2 = OpenVINOInferenceService(store, pipeline_factory=lambda d, dev: mock.Mock(generate=lambda p, max_new_tokens=None: SimpleNamespace(texts=["b"])))
    assert svc1.generate(mp, "Hi").text == "a"
    assert svc2.generate(mp, "Hi").text == "b"


def test_close_does_not_invalidate_during_generation(tmp_path):
    mp = make_artifact(tmp_path)
    store = ModelStore(tmp_path)
    store.inspect_manifest = lambda p, verify=True: fake_artifact()
    started = threading.Event()
    release = threading.Event()
    def factory(d, dev):
        m = mock.Mock()
        def gen(prompt, max_new_tokens=None):
            started.set()
            release.wait(timeout=5)
            return SimpleNamespace(texts=["ok"])
        m.generate.side_effect = gen
        return m
    svc = OpenVINOInferenceService(store, pipeline_factory=factory)
    res = []
    def worker():
        res.append(svc.generate(mp, "Hi"))
    t = threading.Thread(target=worker)
    t.start()
    started.wait(timeout=5)
    svc.close()
    release.set()
    t.join(timeout=5)
    assert res and res[0].text == "ok"
