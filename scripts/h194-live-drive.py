#!/usr/bin/env python3
"""H-194 live run: seed one real parent course and read the fine-tune wire after the UI acts.

The course is authored by the running isolated backend (real provider, real job tick), never by a
fixture. This script only drives `cb.rpc` and prints facts; the UI actions themselves are driven
by ``scripts/h194-live.mjs`` through the real Desktop renderer.

    CB013_BASE=http://127.0.0.1:44249 python3 scripts/h194-live-drive.py seed
    CB013_BASE=http://127.0.0.1:44249 python3 scripts/h194-live-drive.py status
    CB013_BASE=http://127.0.0.1:44249 python3 scripts/h194-live-drive.py verify
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44249")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")
STATE = os.environ.get("H194_STATE", "/tmp/h194-live-state.json")

BRIEF = {
    "title": "Counting to ten in Japanese",
    "goal": "Say and recognise the numbers one to ten in Japanese",
    "starting_point": "Knows the numbers one to ten in English",
    "age_band": "8-10",
    "reading_level": "independent",
    "duration_minutes": 20,
    "setting": "home",
    "materials": ["a notebook", "a pencil"],
    "exclusions": [],
    "supervision": "An adult is nearby.",
    "desired_pages": 2,
    "desired_visuals": "none",
    "narration": "none",
    "locale": "en-US",
    "egress_acknowledged": True,
    "redaction_requested": False,
}
# `parent_brief` has no `subject_domain` key, so the capability policy resolves the domain from the
# locale: a brief with only a locale is a *language* course. That is why the rig brief is a language
# topic — a measuring/algebra brief declared only by locale is validated against the language plan
# and its validator rejects it (`reason: plan_not_validated` on `plan.approve`).


def wire_version() -> int:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return int(json.loads(response.read()).get("wire_version") or 0)


def call(method: str, payload: dict, expected_revision: int | None = None, key: str | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire_version(),
        "method": method,
        "operation_id": f"h194-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    if key:
        body["idempotency_key"] = key
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc?profile=",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def ok(method: str, payload: dict, expected_revision: int | None = None, key: str | None = None) -> dict:
    response = call(method, payload, expected_revision, key)
    if not response.get("ok"):
        raise SystemExit(f"{method} refused: {json.dumps(response.get('error'), indent=2)}")
    return response["result"]


def save(state: dict) -> None:
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    print(json.dumps(state, indent=2))


def load() -> dict:
    with open(STATE, encoding="utf-8") as handle:
        return json.load(handle)


def wait_job(job_id: str, limit_s: int = 900) -> dict:
    deadline = time.time() + limit_s
    while time.time() < deadline:
        response = call("jobs.get", {"job_id": job_id})
        if not response.get("ok"):
            raise SystemExit(f"jobs.get refused: {json.dumps(response.get('error'), indent=2)}")
        job = response["result"].get("job") or response["result"]
        state = str(job.get("state"))
        print(f"  job {job_id}: {state}", flush=True)
        if state in {"completed", "completed_late", "failed", "cancelled", "interrupted_requires_retry"}:
            return job
        time.sleep(3)
    raise SystemExit(f"job {job_id} did not settle within {limit_s}s")


def seed() -> dict:
    created = ok("parent.brief.create", {"brief": BRIEF}, key=f"h194-brief-{time.time_ns()}")
    state = {
        "course_id": created["course_id"],
        "enrollment_id": created["enrollment_id"],
        "plan_job_id": created["job_id"],
    }
    print("plan job", created["job_id"], flush=True)
    plan_job = wait_job(created["job_id"])
    if plan_job.get("state") != "completed":
        save({**state, "plan_job": plan_job})
        raise SystemExit("the plan job did not complete")
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return state


def approve_plan(state: dict) -> dict:
    outline = ok("course.outline", {"enrollment_id": state["enrollment_id"]})
    book = ok("parent.blueprint.read", {"course_id": state["course_id"]})
    plan = outline["plan"]
    plan_hash = (book.get("plan") or {}).get("plan_hash") or plan["plan_hash"]
    result = ok(
        "plan.approve",
        {"enrollment_id": state["enrollment_id"], "plan_id": plan["plan_id"], "plan_hash": plan_hash},
        expected_revision=state.get("revision", 0),
        key=f"h194-approve-plan-{time.time_ns()}",
    )
    state.update(
        {
            "plan_id": plan["plan_id"],
            "plan_hash": plan_hash,
            "revision": result.get("revision"),
            "objectives": [
                {"objective_id": row["objective_id"], "title": row["title"]} for row in outline["objectives"]
            ],
        }
    )
    save(state)
    return state


def generate(state: dict) -> dict:
    job = ok(
        "jobs.create",
        {
            "kind": "plan",
            "brief": {
                "stage": "lessons",
                "plan_id": state["plan_id"],
                "enrollment_id": state["enrollment_id"],
            },
        },
        key=f"h194-lessons-{state['plan_id']}",
    )
    print("lessons job", job["job_id"], flush=True)
    state["lessons_job_id"] = job["job_id"]
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    settled = wait_job(job["job_id"])
    state["lessons_state"] = settled.get("state")
    save(state)
    return state


def approve_final(state: dict) -> dict:
    book = ok("parent.blueprint.read", {"course_id": state["course_id"]})
    result = ok(
        "parent.final.approve",
        {
            "enrollment_id": state["enrollment_id"],
            "plan_id": state["plan_id"],
            "plan_hash": (book.get("plan") or {}).get("plan_hash"),
            "content_hash": book.get("content_hash"),
        },
        expected_revision=state.get("revision", 0),
        key=f"h194-final-{time.time_ns()}",
    )
    state["revision"] = result.get("revision")
    state["final_approval"] = result.get("state")
    state["content_hash"] = result.get("content_hash")
    save(state)
    return state


def status() -> dict:
    state = load()
    review = ok("parent.review.read", {"course_id": state["course_id"]})
    outline = ok("course.outline", {"enrollment_id": state["enrollment_id"]})
    book = ok("parent.blueprint.read", {"course_id": state["course_id"]})
    fact = {
        "course_id": state["course_id"],
        "enrollment_id": state["enrollment_id"],
        "plan_state": (outline.get("plan") or {}).get("state"),
        "plan_hash": (book.get("plan") or {}).get("plan_hash"),
        "objectives": [
            {"objective_id": row["objective_id"], "ordinal": row["ordinal"], "title": row["title"]}
            for row in outline.get("objectives") or []
        ],
        "approval": review.get("approval"),
        "export": review.get("export"),
        "content_hash": review.get("content_hash"),
        "plan_revisions": [
            {"revision_id": row["revision_id"], "kind": row["kind"], "state": row["state"], "changed_fields": row["changed_fields"]}
            for row in review.get("plan_revisions") or []
        ],
        "lesson_revisions": review.get("lesson_revisions") or [],
    }
    print(json.dumps(fact, indent=2))
    return fact


def verify() -> dict:
    """After the UI edits: the untouched section still serves a page; export is gated."""
    state = load()
    outline = ok("course.outline", {"enrollment_id": state["enrollment_id"]})
    objectives = outline.get("objectives") or []
    served = []
    for row in objectives:
        page = ok(
            "lesson.page",
            {"enrollment_id": state["enrollment_id"], "objective_id": row["objective_id"]},
        )
        document = page.get("document") or {}
        served.append(
            {
                "objective_id": row["objective_id"],
                "title": row["title"],
                "blocks": len(document.get("blocks") or []),
                "state": page.get("state"),
                "provenance": (page.get("provenance") or {}).get("outcome"),
                "check_enabled": (page.get("provenance") or {}).get("check_enabled"),
            }
        )
    review = ok("parent.review.read", {"course_id": state["course_id"]})
    fact = {
        "served_sections": served,
        "export": review.get("export"),
        "approval": review.get("approval"),
        "content_hash": review.get("content_hash"),
        "plan_revision_count": len(review.get("plan_revisions") or []),
    }
    print(json.dumps(fact, indent=2))
    return fact


def resume(job_id: str) -> dict:
    """Continue from a plan job that was queued before this process stopped polling."""
    job = wait_job(job_id)
    brief = job.get("brief") or {}
    state = {
        "course_id": brief.get("course_id"),
        "enrollment_id": brief.get("enrollment_id"),
        "plan_job_id": job_id,
        "plan_job_state": job.get("state"),
    }
    if not state["course_id"]:
        raise SystemExit(f"job {job_id} carries no course_id in its brief")
    save(state)
    if job.get("state") != "completed":
        raise SystemExit("the plan job did not complete")
    approve_plan(state)
    generate(state)
    approve_final(load())
    status()
    return state


def _state_with_edits() -> dict:
    """Load the seed state and derive which section the UI edited and which one it did not.

    The seed records the objective ids in plan order. The live UI phase edits the FIRST row and
    only that row; everything else is untouched, so the untouched section is the next id in the
    recorded order. This is read from state, never guessed by title.
    """
    state = load()
    ids = [row["objective_id"] for row in state.get("objectives") or []]
    if len(ids) < 2:
        raise SystemExit(f"state {STATE} carries {len(ids)} objectives; the pass needs at least two")
    state["edited_objective_id"] = ids[0]
    state["untouched_objective_id"] = ids[1]
    return state


def _edited_objective_id(state: dict) -> tuple[str, str]:
    """Return (edited_id, how) from the edit phase's own facts, never from a guess.

    ``scripts/h194-live.mjs`` records ``editor.objectiveId`` — the section it actually opened and
    saved. The untouched section is then any *other* objective on the live outline. Falls back to
    the seeded first/second ids only when the facts file is absent.
    """
    facts_path = os.environ.get("H194_EDIT_FACTS", "audit/h194/live/facts.edit.json")
    try:
        with open(facts_path, encoding="utf-8") as handle:
            facts = json.load(handle)
        edited = (facts.get("editor") or {}).get("objectiveId")
        if edited:
            return str(edited), f"facts.edit.json:{facts_path}"
    except FileNotFoundError:
        pass
    return state["edited_objective_id"], "state.objectives[0] (facts.edit.json missing)"


def continue_untouched() -> dict:
    """After the UI edit + reorder and BEFORE approval: read the untouched section, then export.

    Calls the two commands a read of an unedited section goes through (``lesson.page`` then
    ``lesson.begin``) and then ``parent.export``. The whole sequence is timestamped and carries the
    enrollment id plus the live approval/export views at call time, so the order is auditable.
    H-194's stated gate reason is ``changes_need_review``; when the measured reason differs this is
    recorded as ``reason_matches_h194_gate: false`` with the exact backend error — it is a measured
    deviation, not a softened pass.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    state = _state_with_edits()
    edited, edited_source = _edited_objective_id(state)
    outline = ok("course.outline", {"enrollment_id": state["enrollment_id"]})
    titles = {row["objective_id"]: row["title"] for row in outline.get("objectives") or []}
    candidates = [row["objective_id"] for row in outline.get("objectives") or [] if row["objective_id"] != edited]
    if not candidates:
        raise SystemExit(f"no untouched objective on the live outline; edited={edited} titles={sorted(titles)}")
    untouched = candidates[0]

    # The live gate views the UI reads, captured at the same moment as the untouched read.
    review_before = ok("parent.review.read", {"course_id": state["course_id"]})

    page = ok("lesson.page", {"enrollment_id": state["enrollment_id"], "objective_id": untouched})
    document = page.get("document") or {}
    begin = ok(
        "lesson.begin",
        {"enrollment_id": state["enrollment_id"], "objective_id": untouched, "mode": "resume"},
        key=f"h194-untouched-begin-{time.time_ns()}",
    )

    export_response = call(
        "parent.export",
        {"enrollment_id": state["enrollment_id"]},
        key=f"h194-export-blocked-{time.time_ns()}",
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    refusal = export_response.get("error") or {}
    reason = (refusal.get("details") or {}).get("reason")
    blob = json.dumps(refusal)
    fact = {
        "phase": "continue-untouched",
        "started_at": started_at,
        "finished_at": finished_at,
        "course_id": state["course_id"],
        "enrollment_id": state["enrollment_id"],
        "edited_objective_id": edited,
        "edited_objective_source": edited_source,
        "untouched_objective_id": untouched,
        "untouched_title": titles[untouched],
        "approval_at_read": review_before.get("approval"),
        "export_status_at_read": review_before.get("export"),
        "plan_revisions_at_read": [
            {"revision_id": row["revision_id"], "kind": row["kind"], "state": row["state"]}
            for row in review_before.get("plan_revisions") or []
        ],
        "lesson_revisions_at_read": review_before.get("lesson_revisions"),
        "untouched_page": {
            "state": page.get("state"),
            "document_state": document.get("state"),
            "section_title": document.get("section_title"),
            "block_count": len(document.get("blocks") or []),
            "document_id": document.get("document_id"),
        },
        "untouched_begin": {
            "lesson_run_id": begin.get("lesson_run_id"),
            "run_state": begin.get("run_state"),
            "resume": begin.get("resume"),
            "revision": begin.get("revision"),
        },
        "export_before_approval": {
            "ok": bool(export_response.get("ok")),
            "code": refusal.get("code"),
            "message": refusal.get("message"),
            "reason": reason,
            "reason_source": "error.details.reason",
            "details": refusal.get("details"),
        },
        "expected_reason": "changes_need_review",
        "reason_matches_h194_gate": reason == "changes_need_review",
    }
    out = os.environ.get("H194_FACTS")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(fact, handle, indent=2)
    print(json.dumps(fact, indent=2))
    if export_response.get("ok"):
        raise SystemExit("parent.export SUCCEEDED before approval; the H-194 review gate did not hold")
    if reason != "changes_need_review" and "changes_need_review" not in blob:
        print(
            f"WARNING: parent.export refused with {reason!r}, not the card's expected "
            f"'changes_need_review'. Recorded as a measured deviation. Full error: {blob}",
            flush=True,
        )
    return fact


def export_now() -> dict:
    """After the UI approval: ``parent.export`` must now succeed and write a stored pack."""
    started_at = datetime.now(timezone.utc).isoformat()
    state = _state_with_edits()
    response = call(
        "parent.export",
        {"enrollment_id": state["enrollment_id"]},
        key=f"h194-export-allowed-{time.time_ns()}",
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    refusal = response.get("error") or {}
    result = response.get("result") or {}
    artifacts = [
        {"kind": item.get("kind"), "filename": item.get("filename"), "sha256": item.get("sha256"),
         "byte_size": item.get("byte_size")}
        for item in result.get("artifacts") or []
    ]
    fact = {
        "phase": "export-after-approval",
        "started_at": started_at,
        "finished_at": finished_at,
        "course_id": state["course_id"],
        "enrollment_id": state["enrollment_id"],
        "export_ok": bool(response.get("ok")),
        "error": refusal or None,
        "pack_id": result.get("pack_id"),
        "content_hash": result.get("content_hash"),
        "export_id": result.get("export_id"),
        "artifacts": artifacts,
    }
    out = os.environ.get("H194_FACTS")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(fact, handle, indent=2)
    print(json.dumps(fact, indent=2))
    if not response.get("ok"):
        raise SystemExit(f"parent.export refused after approval: {json.dumps(refusal)}")
    return fact


def preapprove() -> dict:
    """Give an already-approved real plan its active lesson-set approval (rig preparation only).

    Some real courses reached an approved plan with generated pages but no active
    ``final_approvals`` row (their earlier approval was invalidated by an edit). H-194 needs the
    export gate to start READY so the fine-tune pass can prove it turns ready → changes_need_review
    → ready. This calls the same backend command the UI's approve button calls.
    """
    state = load()
    book = ok("parent.blueprint.read", {"course_id": state["course_id"]})
    result = ok(
        "parent.final.approve",
        {
            "enrollment_id": state["enrollment_id"],
            "plan_id": state["plan_id"] if state.get("plan_id") else (book.get("plan") or {}).get("plan_id"),
            "plan_hash": (book.get("plan") or {}).get("plan_hash"),
            "content_hash": book.get("content_hash"),
        },
        expected_revision=state.get("revision", 0),
        key=f"h194-preapprove-{time.time_ns()}",
    )
    state["revision"] = result.get("revision")
    state["final_approval"] = result.get("state")
    state["content_hash"] = result.get("content_hash")
    save(state)
    export = call("parent.export", {"enrollment_id": state["enrollment_id"]},
                  key=f"h194-preapprove-export-{time.time_ns()}")
    fact = {"approval": state["final_approval"], "content_hash": state["content_hash"],
            "export_ok": bool(export.get("ok")), "export_error": export.get("error")}
    print(json.dumps(fact, indent=2))
    return fact


def export_enrollment(enrollment_id: str) -> dict:
    """Measure ``parent.export`` for any real enrollment (used to prove the success path elsewhere)."""
    started_at = datetime.now(timezone.utc).isoformat()
    response = call(
        "parent.export",
        {"enrollment_id": enrollment_id},
        key=f"h194-export-{enrollment_id}-{time.time_ns()}",
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    refusal = response.get("error") or {}
    result = response.get("result") or {}
    fact = {
        "phase": "export-enrollment",
        "started_at": started_at,
        "finished_at": finished_at,
        "enrollment_id": enrollment_id,
        "export_ok": bool(response.get("ok")),
        "error": refusal or None,
        "pack_id": result.get("pack_id"),
        "content_hash": result.get("content_hash"),
        "export_id": result.get("export_id"),
        "artifacts": [
            {"kind": item.get("kind"), "filename": item.get("filename"), "sha256": item.get("sha256"),
             "byte_size": item.get("byte_size")}
            for item in result.get("artifacts") or []
        ],
    }
    out = os.environ.get("H194_FACTS")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(fact, handle, indent=2)
    print(json.dumps(fact, indent=2))
    return fact


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "seed":
        state = seed()
        approve_plan(state)
        generate(state)
        approve_final(load())
        status()
    elif command == "resume":
        resume(sys.argv[2])
    elif command == "status":
        status()
    elif command == "verify":
        verify()
    elif command == "continue-untouched":
        continue_untouched()
    elif command == "export":
        export_now()
    elif command == "export-enrollment":
        export_enrollment(sys.argv[2])
    elif command == "preapprove":
        preapprove()
    else:
        raise SystemExit(f"unknown command {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
