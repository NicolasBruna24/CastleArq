from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/castlearq/runtimes.py")
t = p.read_text(encoding="utf-8")
old = '        compatibility_names=("llama.cpp",),'
new = '        compatibility_names=("llama.cpp / llama.app", "llama.cpp"),'
count = t.count(old)
t2 = t.replace(old, new)
p.write_text(t2, encoding="utf-8")
print("replaced", count, "occurrences")
