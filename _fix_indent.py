from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/tests/test_sycl_discovery.py")
lines = p.read_text(encoding="utf-8").splitlines()
idx = next(i for i, l in enumerate(lines) if l.strip() == "def test_sycl_disponible(self):")
lines.insert(idx, "class SyclDiscoveryTests(unittest.TestCase):")
main_idx = next(i for i, l in enumerate(lines) if l.strip() == 'if __name__ == "__main__":')
for i in range(idx + 1, main_idx):
    if lines[i].strip() == "":
        continue
    lines[i] = "    " + lines[i]
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("done")
