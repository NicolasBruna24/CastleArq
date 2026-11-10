from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/tests/test_sycl_discovery.py")
t = p.read_text(encoding="utf-8")
old = '            result = discover_sycl_llama_runtime(executable_path="/opt/llama-sycl")\n'
new = '            result = castlearq.runtimes.discover_sycl_llama_runtime(executable_path="/opt/llama-sycl")\n'
t2 = t.replace(old, new)
p.write_text(t2, encoding="utf-8")
print("replaced", t.count(old), "occurrences")
