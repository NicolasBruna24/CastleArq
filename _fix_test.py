from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/tests/test_selector_sycl_isolation.py")
t = p.read_text(encoding="utf-8")

t = t.replace("_select(", "_target(")
t = t.replace("target = SELECTOR.select(_compatibility(backend=\"CPU\"), capability, _executable())", "target = SELECTOR.select(_compatibility(backend=\"CPU\"), capability, _executable()).target")
t = t.replace("result = SELECTOR.select(", "target = SELECTOR.select(")

p.write_text(t, encoding="utf-8")
print("ok")
