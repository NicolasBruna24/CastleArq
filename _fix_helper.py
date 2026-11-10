from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/castlearq/run_service.py")
lines = p.read_text(encoding="utf-8").splitlines()

# The helper block is between "def _select_runner" and the next "model_id: str,"
helper_start = next(i for i, l in enumerate(lines) if l.strip() == "def _select_runner(capability, target, configured_runner=None):")
helper_end = next(i for i, l in enumerate(lines) if i > helper_start and l.strip() == "model_id: str,")
# helper_end points at "model_id: str," (line 341); helper block is lines [helper_start..helper_end-1]
helper_block = lines[helper_start:helper_end]
# Remove trailing blank lines from helper block
while helper_block and helper_block[-1].strip() == "":
    helper_block.pop()
helper_block.append("")  # trailing blank

# Remove helper block from current location
del lines[helper_start:helper_end]

# Now find "def run_once(" (should be at the position where helper was)
run_once_idx = next(i for i, l in enumerate(lines) if l.strip() == "def run_once(")
# Insert helper block before run_once (with a blank line separator)
insert_at = run_once_idx
# Ensure blank line before
if insert_at > 0 and lines[insert_at - 1].strip() != "":
    lines.insert(insert_at, "")
    insert_at += 1
lines[insert_at:insert_at] = helper_block

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("done; helper lines:", len(helper_block))
