#!/usr/bin/env python3
"""Assertions for probe 1b (in-place compression ids).

Reads `probes/raw/p1/compress_long/`, checks that /compress compacted the transcript,
that `post_compaction` fired exactly once with `kind=summarize`, and that the next turn
still carried the same session_id/task_id with a fresh turn_id. Prints JSON; exit 1 on FAIL.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def load_log(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def main() -> int:
    out = Path(sys.argv[1])
    sid = sys.argv[2]

    compress_text = (out / "compress_long.txt").read_text(encoding="utf-8", errors="replace")
    events = load_log(out / "events_compress_long.jsonl")
    after = load_log(out / "events_after_compact.jsonl")

    compaction = [r for r in events if r.get("event") == "post_compaction"]
    compacted = re.search(r"Compressed:\s*(\d+)\s*→\s*(\d+)\s*messages", compress_text)
    turns_after = [r for r in after if r.get("event") == "pre_llm_call"]

    checks = {
        "compress_reports_compaction": bool(compacted),
        "messages_removed": int(compacted.group(1)) - int(compacted.group(2)) if compacted else 0,
        "post_compaction_fired_once": len(compaction) == 1,
        "post_compaction_kind_summarize": bool(compaction) and compaction[0].get("kind") == "summarize",
        "post_compaction_same_session": bool(compaction) and compaction[0].get("session_id") == sid,
        "post_compaction_removed_messages_positive": bool(compaction)
        and (compaction[0].get("messages_removed") or 0) > 0,
        "turn_after_compaction_observed": len(turns_after) >= 1,
        "session_id_survives": all(r.get("session_id") == sid for r in turns_after) and bool(turns_after),
        "task_id_survives": all(r.get("task_id") == sid for r in turns_after) and bool(turns_after),
        "turn_id_fresh_after_compaction": all(
            r.get("turn_id", "").startswith(sid + ":") for r in turns_after
        ) and len({r.get("turn_id") for r in turns_after}) == len(turns_after),
    }
    ok = all(v for k, v in checks.items() if k != "messages_removed")
    result = {
        "probe": "p1-compaction",
        "status": "PASS" if ok else "FAIL",
        "checks": checks,
        "compaction": compaction[0] if compaction else None,
    }
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
