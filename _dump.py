from pathlib import Path

files = [
    Path("tests/test_selection.py"),
]

for p in files:
    print("=" * 40)
    print(p)
    print("=" * 40)
    print(p.read_text(encoding="utf-8"))
