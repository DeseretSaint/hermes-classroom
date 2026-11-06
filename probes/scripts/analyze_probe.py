#!/usr/bin/env python3
"""Summarise a cb-probe JSONL log without loading huge payloads into the terminal."""
from __future__ import annotations

import json
import sys
from collections import Counter


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"event": "UNPARSEABLE", "raw": line[:200]})
    return rows


def main(path):
    rows = load(path)
    print(f"file: {path}")
    print("events:", dict(Counter(r.get("event") for r in rows)))
    ids = {}
    for r in rows:
        ev = r.get("event")
        if ev in ("tool_ids", "on_session_start", "post_llm_call", "on_session_end",
                  "post_compaction", "pre_llm_call"):
            keep = {k: v for k, v in r.items() if k not in ("ts", "event")}
            print(f"\n[{ev}]")
            for k, v in keep.items():
                s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                print(f"  {k}={s[:300]}")
    print("\n[pre_api_request summary]")
    for r in rows:
        if r.get("event") == "pre_api_request":
            print(" ", {k: r.get(k) for k in (
                "api_request_id", "turn_id", "api_call_count", "message_count",
                "system_prompt_chars", "markers", "sentinel_message_indexes",
                "sentinel_in_earlier_history", "message_roles")})


if __name__ == "__main__":
    main(sys.argv[1])
