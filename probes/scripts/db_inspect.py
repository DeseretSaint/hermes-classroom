#!/usr/bin/env python3
"""Read-only inspection of a Hermes profile state.db for probe evidence."""
from __future__ import annotations

import argparse
import json
import sqlite3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--session", required=True)
    ap.add_argument("--needle", default="CB_INJECTED_SENTINEL")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, role, active, content, api_content, display_kind, timestamp "
        "FROM messages WHERE session_id=? ORDER BY id", (args.session,)
    ).fetchall()
    print(f"messages: {len(rows)}")
    for r in rows[: args.limit]:
        content = r["content"] or ""
        api = r["api_content"] or ""
        print(json.dumps({
            "id": r["id"], "role": r["role"], "active": r["active"],
            "content_chars": len(content),
            "api_content_chars": len(api),
            "needle_in_content": args.needle in content,
            "needle_in_api_content": args.needle in api,
            "content_head": content[:160],
            "api_content_head": api[:200],
            "timestamp": r["timestamp"],
        }, ensure_ascii=False))
    meta = conn.execute(
        "SELECT * FROM sessions WHERE id=?", (args.session,)
    ).fetchone()
    if meta is not None:
        d = {k: meta[k] for k in meta.keys()}
        for k in list(d):
            if isinstance(d[k], str) and len(d[k]) > 200:
                d[k] = d[k][:200] + "…"
        print("session_row:", json.dumps(d, ensure_ascii=False, default=str)[:1500])


if __name__ == "__main__":
    main()
