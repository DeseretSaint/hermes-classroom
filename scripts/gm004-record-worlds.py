"""Record the GM-004 staged worlds as the dispatcher sees them.

Writes `docs/visual-review/gm-004/staged-worlds.json`: one `world.read` projection plus the
`library.list` row (the enrollment the Desktop sees) per staged course. Run it against the
preserved rig state, in the same environment as `scripts/gm004-stage-worlds.py`.

    HERMES_HOME="$HOME/.hermes/coursebook-test-gm004-203620/home" \
    GM004_WORKTREE="$PWD" \
      python3 scripts/gm004-record-worlds.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

OUT = Path(os.environ.get("GM004_OUT", "docs/visual-review/gm-004/staged-worlds.json"))

COURSES = (
    ("japanese_demo (course-world frames)", "Japanese affection and register — an L0 demonstration classroom"),
    ("head_gasket (course-world-headgasket frames)", "Replace a head gasket"),
    ("sample_classroom (studio-concepts frames)", "Japanese affection and register — a Sample L0 classroom"),
)

os.environ.setdefault("HERMES_COURSEBOOK_SINGLE_HOME", "1")
sys.path.insert(0, os.environ.get("GM004_WORKTREE", os.getcwd()))

from coursebook import api, db, domain, world  # noqa: E402

db.ensure_schema()
domain.ensure_registered()
world.ensure_registered()


def dispatch(method: str, payload: dict) -> dict:
    body = {
        "contract": api.RPC_CONTRACT, "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method, "operation_id": f"gm004-record-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    return api.dispatch(body)


def course_id(title: str) -> str:
    with db.read() as connection:
        row = connection.execute(
            "SELECT c.id AS id FROM courses c"
            " LEFT JOIN enrollments e ON e.course_id = c.id AND e.status = 'active'"
            " WHERE c.title = ? AND c.status != 'deleted'"
            " ORDER BY (e.id IS NULL) ASC, e.updated_at DESC, c.rowid DESC LIMIT 1",
            (title,),
        ).fetchone()
    return row["id"]


record = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "kind": "world.read + library.list through the real cb.rpc dispatcher",
    "seam": "deterministic provider-shaped media seam; returns flat tonal swatch PNGs, no scene, no text, no numbers. Live model capture not produced.",
    "courses": {},
}

for label, title in COURSES:
    cid = course_id(title)
    read = dispatch("world.read", {"course_id": cid})
    library = dispatch("library.list", {"query": title, "limit": 10})
    rows = [r for r in (library.get("result") or {}).get("items", []) if r["course_id"] == cid]
    record["courses"][label] = {
        "course_id": cid,
        "ok": read.get("ok"),
        "result": read.get("result"),
        "error": read.get("error"),
        "library_rows": [
            {k: r.get(k) for k in ("enrollment_id", "enrollment_status", "course_status", "title")}
            for r in rows
        ] or "no library row (not enrolled / archived)",
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(record, indent=2) + "\n")
print(f"wrote {OUT} ({len(record['courses'])} courses)")
