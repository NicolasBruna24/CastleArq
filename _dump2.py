from pathlib import Path

files = [
    Path("/home/brunapc/LocalAI Hub/castlearq/compatibility.py"),
    Path("/home/brunapc/LocalAI Hub/castlearq/__init__.py"),
]

for p in files:
    print("=" * 40)
    print(p)
    print("=" * 40)
    print(p.read_text(encoding="utf-8"))
