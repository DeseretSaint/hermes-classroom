#!/usr/bin/env python3
"""CP-015c-ja: one further lessons pass on the approved Japanese Cafe plan.

Every page here is made by the product's own flow: `lesson.regenerate` (the same route a parent
uses to replace a page the validator parked) for the three owner sections, then one `jobs.create`
lessons job for the unit, which authors the review section under CP-015j. Nothing is written to
the database directly and no prompt is edited.

    CB013_BASE=http://127.0.0.1:44601 CB013_TOKEN=… CP015_HOME=<isolated home> \
      python3 scripts/cp015c-resume.py --record <scratch>/cp015c-resume.json

Exit code 0 only when every section ends in a validated state; a parked page prints the exact
rejection reasons the kernel stored.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44601")
TOKEN = os.environ.get("CB013_TOKEN", "cp015-demo-token")
HOME = Path(os.environ.get("CP015_HOME", "")).expanduser()
PLAN_ID = "pln_5dde08c973f94cc0a444caa77a09d53c"
ENROLLMENT_ID = "enr_2bc4905ab3974e7bbc1afe02cb0b21fc"
TERMINAL = {"completed", "succeeded", "failed", "cancelled", "interrupted_requires_retry"}
SUCCESS = {"completed", "succeeded"}
RUN = os.environ.get("CP015C_RUN_ID") or uuid.uuid4().hex[:6]


def log(message: str) -> None:
    print(f"[cp015c] {message}", flush=True)


def request(path: str, body: dict | None = None, timeout: int = 120) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


_wire: int | None = None


def wire() -> int:
    global _wire
    if _wire is None:
        _wire = int(request("/runtime?profile=")["wire_version"])
    return _wire


def call(method: str, payload: dict, key: str | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire(),
        "method": method,
        "operation_id": f"cp015c-{method.replace('.', '-')}-{uuid.uuid4().hex[:10]}",
        "payload": payload,
    }
    if key:
        body["idempotency_key"] = key
    return request("/rpc?profile=", body)


def ok(method: str, payload: dict, key: str | None = None) -> dict:
    response = call(method, payload, key=key)
    if not response.get("ok"):
        raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'))[:800]}")
    return response["result"]


def wait(job_id: str, *, timeout: float = 1800.0) -> dict:
    started = time.monotonic()
    last = ""
    while True:
        job = ok("jobs.get", {"job_id": job_id})["job"]
        state = str(job.get("state"))
        if state != last:
            log(f"  {job_id}: {state} {json.dumps(job.get('progress') or {})[:120]}")
            last = state
        if state in TERMINAL:
            return job
        if time.monotonic() - started > timeout:
            raise RuntimeError(f"{job_id} still {state} after {timeout:.0f}s")
        time.sleep(5.0)


def db_path() -> Path:
    return HOME / "plugin-data/coursebook/data.db"


def sections() -> list[dict]:
    connection = sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, ordinal, title, section_role FROM gen_plan_sections"
            " WHERE plan_id = ? ORDER BY ordinal",
            (PLAN_ID,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def lesson_state(section_id: str) -> dict:
    connection = sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT id, version, state, rejection_reasons_json, validation_id FROM gen_lessons"
            " WHERE section_id = ? ORDER BY version DESC LIMIT 1",
            (section_id,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", help="write the pass evidence here")
    parser.add_argument("--skip-owners", action="store_true")
    args = parser.parse_args()

    evidence: dict = {
        "plan_id": PLAN_ID,
        "enrollment_id": ENROLLMENT_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "wire_version": wire(),
        "run": RUN,
        "owners": [],
        "review": None,
    }
    rows = sections()
    evidence["sections_before"] = [
        {**row, "lesson": lesson_state(str(row["id"]))} for row in rows
    ]
    owners = [row for row in rows if str(row.get("section_role") or "owner") == "owner"]

    if not args.skip_owners:
        for row in owners:
            section_id = str(row["id"])
            log(f"regenerate section {row['ordinal']}: {row['title']}")
            result = ok(
                "lesson.regenerate",
                {"enrollment_id": ENROLLMENT_ID, "plan_id": PLAN_ID, "section_id": section_id},
                key=f"cp015c-ja-regen-{section_id}-{RUN}",
            )
            job_id = str(result["job_id"])
            final = wait(job_id)
            state = lesson_state(section_id)
            entry = {
                "ordinal": int(row["ordinal"]),
                "section_id": section_id,
                "job_id": job_id,
                "job_state": final.get("state"),
                "job_error": final.get("error"),
                "job_result": final.get("result"),
                "lesson": state,
            }
            evidence["owners"].append(entry)
            log(f"  -> lesson v{state.get('version')} {state.get('state')}")

    # One unit-level lessons job: with the owner pages parked, CP-015j authors the review section
    # against the latest closed owner check instead of ending the job VALIDATION_FAILED.
    log("lessons job for unit 1 (review section)")
    queued = ok(
        "jobs.create",
        {"kind": "plan", "brief": {"stage": "lessons", "plan_id": PLAN_ID,
                                   "enrollment_id": ENROLLMENT_ID, "unit_ordinal": 1}},
        key=f"cp015c-ja-review-{RUN}",
    )
    review_job = str(queued["job_id"])
    final = wait(review_job, timeout=1800)
    evidence["review"] = {
        "job_id": review_job,
        "job_state": final.get("state"),
        "job_error": final.get("error"),
        "job_result": final.get("result"),
        "sections_after": [
            {**row, "lesson": lesson_state(str(row["id"]))} for row in sections()
        ],
    }
    log(f"  -> review job {final.get('state')}")

    export = ok("course.export.read", {"enrollment_id": ENROLLMENT_ID})
    evidence["export_read"] = {
        key: export.get(key)
        for key in ("ready", "blocked_reason", "blocked_message", "problems", "content_hash",
                    "sections")
    }
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.record:
        Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        Path(args.record).write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
        log(f"record: {args.record}")

    parked = [
        row for row in evidence["review"]["sections_after"]
        if str((row.get("lesson") or {}).get("state")) not in ("validated",)
    ]
    log(f"parked sections: {[row['ordinal'] for row in parked]}")
    return 0 if not parked else 1


if __name__ == "__main__":
    sys.exit(main())
