#!/usr/bin/env python3
"""Print the memory and long-task rows from a raw run file."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
for row in data["rows"]:
    if "memory" in row["id"] or "longtasks" in row["id"] or row["id"] == "cold-mount":
        print(json.dumps(row, indent=2))
