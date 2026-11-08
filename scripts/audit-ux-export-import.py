#!/usr/bin/env python3
"""Drive the exported H-121 archive into a *fresh profile* through that profile's live backend.

This is the cross-profile half of the card: profile A (port 44319) exported the zip, this script
talks only to profile B (port 44320) over its own wire. It mints the file grant the Desktop's
folder picker would mint, previews, then imports fresh → resume → fresh and asserts the identities
stay distinct. It also reads profile B's own SQLite only to count personal rows, which have no
read method in cb.rpc.

    CB013_BASE=http://127.0.0.1:44320 CB013_TOKEN=cb013-test-token \
      python3 scripts/audit-ux-export-import.py audit/h121/exported.zip

Prints one JSON object and exits non-zero on any failed assertion.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44320")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from coursebook import db  # noqa: E402


def wire_version() -> int:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return int(json.loads(response.read()).get("wire_version") or 0)


VERSION = wire_version()


def call(method: str, payload: dict, **extra) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": VERSION,
        "method": method,
        "operation_id": f"h121-import-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    body.update(extra)
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc?profile=",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def ok(method: str, payload: dict, **extra) -> dict:
    response = call(method, payload, **extra)
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {json.dumps(response.get('error'))}")
    return response["result"]


def grant(path: Path) -> str:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/packs/grant",
        data=json.dumps({"path": str(path)}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    if not payload.get("staged_id"):
        raise SystemExit(f"grant failed: {json.dumps(payload)}")
    return payload["staged_id"]


def count(sql: str) -> int:
    with db.read() as connection:
        return int(connection.execute(sql).fetchone()[0])


def main() -> int:
    archive = Path(sys.argv[1] if len(sys.argv) > 1 else "audit/h121/exported.zip").resolve()
    db.migrate()
    evidence: dict = {"base": BASE, "wire_version": VERSION, "archive": str(archive)}
    evidence["profile_b_before"] = {
        "courses": count("SELECT COUNT(*) FROM courses"),
        "packs": count("SELECT COUNT(*) FROM packs"),
        "enrollments": count("SELECT COUNT(*) FROM enrollments"),
        "notebook_entries": count("SELECT COUNT(*) FROM notebook_entries"),
    }
    assert evidence["profile_b_before"]["courses"] == 0, "profile B is not fresh"

    staged = grant(archive)
    preview = ok("pack.preview", {"staged_id": staged})
    evidence["preview"] = {
        "pack_id": preview["manifest"]["pack_id"],
        "pack_version": preview["manifest"]["pack_version"],
        "content_hash": preview["manifest"]["content_hash"],
        "file_count": preview["integrity"]["file_count"],
        "hashes_match": preview["integrity"]["hashes_match"],
    }

    fresh_result = ok(
        "pack.import",
        {"staged_id": staged, "mode": "fresh"},
        idempotency_key=f"h121-fresh-{time.time_ns()}",
    )
    evidence["fresh"] = fresh_result

    resume_result = ok(
        "pack.import",
        {"staged_id": grant(archive), "mode": "resume"},
        idempotency_key=f"h121-resume-{time.time_ns()}",
    )
    evidence["resume"] = resume_result
    assert resume_result["course_id"] == fresh_result["course_id"], "resume created a second course"
    assert resume_result["enrollment_id"] == fresh_result["enrollment_id"], "resume changed enrollment"
    assert count("SELECT COUNT(*) FROM courses") == 1, "resume duplicated the course"

    second = ok(
        "pack.import",
        {"staged_id": grant(archive), "mode": "fresh"},
        idempotency_key=f"h121-fresh2-{time.time_ns()}",
    )
    evidence["fresh_again"] = second
    assert second["enrollment_id"] != fresh_result["enrollment_id"], "fresh reused an enrollment"
    assert second["course_id"] != fresh_result["course_id"], "fresh reused a course"
    assert second["pack_id"] == fresh_result["pack_id"], "fresh changed pack identity"

    evidence["profile_b_after"] = {
        "courses": count("SELECT COUNT(*) FROM courses"),
        "packs": count("SELECT COUNT(*) FROM packs"),
        "enrollments": count("SELECT COUNT(*) FROM enrollments"),
        "attempts": count("SELECT COUNT(*) FROM attempts"),
        "notebook_entries": count("SELECT COUNT(*) FROM notebook_entries"),
        "evidence": count("SELECT COUNT(*) FROM evidence"),
    }
    assert evidence["profile_b_after"]["packs"] == 1, "the pack was stored more than once"
    assert evidence["profile_b_after"]["courses"] == 2, "unexpected course count"
    assert evidence["profile_b_after"]["enrollments"] == 2, "unexpected enrollment count"
    assert evidence["profile_b_after"]["attempts"] == 0, "an attempt travelled with the archive"
    assert evidence["profile_b_after"]["notebook_entries"] == 0, "a notebook note travelled"
    assert evidence["profile_b_after"]["evidence"] == 0, "an observation travelled"

    library = ok("library.list", {"filter": "all", "limit": 50, "sort": "title"})
    evidence["library_rows"] = [
        {
            "course_id": row.get("course_id"),
            "enrollment_id": row.get("enrollment_id"),
            "pack_id": (row.get("provenance") or {}).get("pack_id"),
            "title": row.get("title"),
        }
        for row in library.get("items", [])
    ]
    assert len(evidence["library_rows"]) == 2, "the fresh profile should show two classrooms"

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
