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
    else:
        raise SystemExit(f"unknown command {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
