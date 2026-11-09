#!/usr/bin/env python3
"""Measure that ``parent.export`` can refuse with ``changes_need_review`` at all.

Round 1 of the H-194d review asked for the reachability of the gate reason the card names. The
H-194 *edit* path cannot produce it — ``lesson.revise`` and ``plan.edit``/undo each supersede the
active approval inside their own transaction, so ``parent.export`` short-circuits earlier at
``no_final_approval``. This probe isolates the other branch of the same gate: keep an ACTIVE
approval and change the stored page text by a route that runs no command (the same direct row
mutation ``tests/test_parent_studio.py:770`` uses), then call ``parent.export``. It restores the
row and re-exports, so the course is left exactly as it was found.

    H194_FACTS=audit/h194/live/facts.gate-probe.json CB013_BASE=http://127.0.0.1:44249 \
      CB013_TOKEN=cb013-test-token python3 scripts/h194-gate-probe.py

Defaults point at the H-194 live rig (isolated home ``coursebook-test-h194-1108``, wire 20).
Override with ``H194_PROBE_DB`` / ``H194_PROBE_COURSE`` / ``H194_PROBE_ENROLLMENT``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44249")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")
DB = os.path.expanduser(
    os.environ.get(
        "H194_PROBE_DB",
        "~/.hermes/coursebook-test-h194-1108/home/plugin-data/coursebook/data.db",
    )
)
COURSE = os.environ.get("H194_PROBE_COURSE", "crs_e58e8ef3fcb54777ac4d8c17636307e5")
ENROLLMENT = os.environ.get(
    "H194_PROBE_ENROLLMENT", "enr_176897ff32584282955b085634837b2b"
)


def wire_version() -> int:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return int(json.loads(response.read()).get("wire_version") or 0)


def call(method: str, payload: dict) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire_version(),
        "method": method,
        "operation_id": f"h194-probe-{time.time_ns()}",
        "payload": payload,
        "idempotency_key": f"h194-probe-{method}-{time.time_ns()}",
    }
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc?profile=",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(DB, timeout=20)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT id, page_json FROM gen_lessons WHERE plan_id = ("
        " SELECT id FROM plans WHERE course_id = ? AND state = 'approved')"
        " AND state = 'validated' ORDER BY id LIMIT 1",
        (COURSE,),
    ).fetchone()
    if row is None:
        raise SystemExit("no validated lesson row on the probe course")
    original = row["page_json"]
    page = json.loads(original)
    page["learner_explanation"] = (page.get("learner_explanation") or "") + " Probe change."
    with connection:
        connection.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (json.dumps(page), row["id"]),
        )
    connection.close()

    before = call("parent.review.read", {"course_id": COURSE})
    export_mutated = call("parent.export", {"enrollment_id": ENROLLMENT})

    connection = sqlite3.connect(DB, timeout=20)
    with connection:
        connection.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?", (original, row["id"])
        )
    connection.close()
    export_restored = call("parent.export", {"enrollment_id": ENROLLMENT})

    restored_result = export_restored.get("result") or {}
    failure = export_mutated.get("error") or {}
    fact = {
        "phase": "changes-need-review-reachability-probe",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "db": DB,
        "backend": BASE,
        "course_id": COURSE,
        "enrollment_id": ENROLLMENT,
        "method": "direct UPDATE of the stored page text with no command that supersedes the "
        "approval (the same mutation tests/test_parent_studio.py:770 uses), then parent.export",
        "lesson_row_touched": row["id"],
        "approval_before_probe": (before.get("result") or {}).get("approval"),
        "export_status_before_probe": (before.get("result") or {}).get("export"),
        "export_with_stale_content": {
            "ok": bool(export_mutated.get("ok")),
            "code": failure.get("code"),
            "message": failure.get("message"),
            "reason": (failure.get("details") or {}).get("reason"),
            "details": failure.get("details"),
        },
        "export_after_restore": {
            "ok": bool(export_restored.get("ok")),
            "export_id": restored_result.get("export_id"),
            "content_hash": restored_result.get("content_hash"),
            "artifacts": [
                {
                    "artifact_id": item.get("artifact_id"),
                    "kind": item.get("kind"),
                    "mime": item.get("mime"),
                    "sha256": item.get("content_hash"),
                    "byte_size": item.get("bytes"),
                }
                for item in restored_result.get("artifacts") or []
            ],
            "error": export_restored.get("error"),
        },
    }
    out = os.environ.get("H194_FACTS")
    if out:
        with open(os.path.expanduser(out), "w", encoding="utf-8") as handle:
            json.dump(fact, handle, indent=2)
    print(json.dumps(fact, indent=2))
    if fact["export_with_stale_content"]["reason"] != "changes_need_review":
        raise SystemExit(
            "probe did not measure changes_need_review: "
            f"{fact['export_with_stale_content']['reason']!r}"
        )
    if not fact["export_after_restore"]["ok"]:
        raise SystemExit(f"probe restore failed: {fact['export_after_restore']['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
