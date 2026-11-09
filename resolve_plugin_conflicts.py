"""Resolve the three plugin.js conflict hunks between H-183 (ours) and H-189 (theirs).

Policy: H-183 is the truth sweep (copy + dead controls); H-189 is the authored home
(motion + hierarchy). Neither is optional, so:
  hunk 1 — keep BOTH hook declarations (pet from H-183, arrival from H-189);
  hunk 2 — keep the run line (H-183) AND the hierarchy comment (H-189);
  hunk 3 — take H-189's inline node renderer, which supersedes the plain PathStop list.
"""
from pathlib import Path

path = Path("desktop/plugin.js")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

hunks = []
i = 0
cur = None
while i < len(lines):
    line = lines[i]
    if line.startswith("<<<<<<<"):
        cur = {"ours": [], "theirs": []}
        side = "ours"
    elif line.startswith("=======") and cur is not None:
        side = "theirs"
    elif line.startswith(">>>>>>>") and cur is not None:
        hunks.append(cur)
        cur = None
    elif cur is not None:
        cur[side].append(line)
    i += 1

assert len(hunks) == 3, f"expected 3 hunks, found {len(hunks)}"

choice = [hunks[0]["ours"] + hunks[0]["theirs"], hunks[1]["ours"] + hunks[1]["theirs"], hunks[2]["theirs"]]

out = []
i = 0
idx = 0
cur = None
while i < len(lines):
    line = lines[i]
    if line.startswith("<<<<<<<"):
        out.extend(choice[idx])
        idx += 1
        cur = True
    elif cur:
        if line.startswith(">>>>>>>"):
            cur = None
    else:
        out.append(line)
    i += 1

path.write_text("".join(out), encoding="utf-8")
print("resolved", idx, "hunks")
