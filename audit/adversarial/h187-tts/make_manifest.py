#!/usr/bin/env python3
"""Pin every evidence file's sha256, plus the live store's artifact and DB digests."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ce380228")
EVIDENCE = REPO / "audit" / "adversarial" / "h187-tts"
STORE = Path("/home/deseretsaint/.hermes/h187-course/home/plugin-data/coursebook")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


files = []
for path in sorted(EVIDENCE.rglob("*")):
    if not path.is_file() or path.name == "manifest.json":
        continue
    files.append({"path": str(path.relative_to(EVIDENCE)), "bytes": path.stat().st_size, "sha256": digest(path)})

stored = STORE / "artifacts" / "objects" / "20" / "208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c"
manifest = {
    "kind": "manifest",
    "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "branch": "wt/t_ce380228",
    "files": files,
    "store_artifact": {
        "path": str(stored),
        "exists": stored.is_file(),
        "bytes": stored.stat().st_size if stored.is_file() else None,
        "sha256": digest(stored) if stored.is_file() else None,
    },
    "store_db_sha256": digest(STORE / "data.db"),
}
(EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
