#!/usr/bin/env python3
"""Write a deterministic large filler query for the compression probe."""
from __future__ import annotations

import sys
from pathlib import Path

target = Path(sys.argv[1])
words = []
i = 0
while sum(len(w) + 1 for w in words) < 24000:
    i += 1
    words.append(f"filler{i:04d}.")
target.write_text(
    "Read this long passage once, then reply with the single word OK. Do not summarize it now.\n\n"
    + " ".join(words),
    encoding="utf-8",
)
print(f"{target}: {target.stat().st_size} bytes, {i} filler tokens")
