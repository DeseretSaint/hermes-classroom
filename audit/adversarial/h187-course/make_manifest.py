#!/usr/bin/env python3
"""Hash the H-187 preparation evidence and record the tree it was produced on."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ac36aad4")
EVIDENCE = REPO / "audit" / "adversarial" / "h187-course"
FILES = [
    "STATUS.md",
    "build_course.py",
    "verify_course.py",
    "rehearse_media_path.py",
    "downstream_targets.py",
    "course_facts.json",
    "verification.json",
    "rehearsal_media_path.json",
    "downstream_media_targets.json",
]


def main() -> int:
    entries = []
    for name in FILES:
        path = EVIDENCE / name
        entries.append({
            "path": f"audit/adversarial/h187-course/{name}",
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest = {
        "task": "t_ac36aad4",
        "head": head,
        "media_bytes_generated": 0,
        "prepared_store": "/home/deseretsaint/.hermes/h187-course/home",
        "files": entries,
    }
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
