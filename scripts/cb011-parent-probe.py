#!/usr/bin/env python3
"""Drive the Parent Studio (cb.rpc v6) surface against the live isolated backend.

The probe is deliberately explicit: it reads the wire version and implemented methods from
``/runtime`` instead of pinning one, shows every refusal code/reason it receives, and never
invents a result. It walks the exact sequence the Desktop studio calls, so a reviewer can replay
the same calls the UI made.

    scripts/cb011-parent-probe.py plan     # brief -> queued job -> poll -> draft plan
    scripts/cb011-parent-probe.py full     # the whole authoring path, printing each shape
    scripts/cb011-parent-probe.py revise   # re-approval path: replan -> draft edit -> export gate

Environment: CB013_BASE (default http://127.0.0.1:44219), CB013_TOKEN (default cb013-test-token),
CB011_COURSE_ID to continue an existing course, CB011_WAIT seconds for job completion (default 900).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44219")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")
WAIT = float(os.environ.get("CB011_WAIT", "900"))
LOG: list[dict] = []


def _request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:  # a refusal is data, not a crash
        return json.loads(error.read())


WIRE = _request("GET", "/api/plugins/coursebook/runtime?profile=")
VERSION = int(WIRE.get("wire_version") or 1)


def call(method: str, payload: dict, *, expected_revision: int | None = None,
         idempotency_key: str | None = None) -> dict:
    body: dict = {
        "contract": "cb.rpc",
        "contract_version": VERSION,
        "method": method,
        "operation_id": f"cb011-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    response = _request("POST", "/api/plugins/coursebook/rpc?profile=", body)
    LOG.append({"method": method, "request": payload, "response": response})
    flag = "ok " if response.get("ok") else "REFUSED"
    detail = ""
    if not response.get("ok"):
        error = response.get("error") or {}
        detail = f" {error.get('code')}: {error.get('message')} {json.dumps(error.get('details') or {})}"
    print(f"{flag} {method}{detail}")
    return response


def result(method_response: dict) -> dict:
    return method_response.get("result") or {}


def wait_job(job_id: str, label: str) -> dict:
    deadline = time.time() + WAIT
    last = None
    while time.time() < deadline:
        response = call("jobs.get", {"job_id": job_id})
        job = result(response).get("job") or {}
        state = job.get("state")
        if state != last:
            print(f"   {label} job {job_id} -> {state} {json.dumps(job.get('progress') or {})}")
            last = state
        if state in ("completed", "failed", "cancelled", "completed_late", "interrupted_requires_retry"):
            if job.get("error"):
                print(f"   error: {json.dumps(job['error'])}")
            return job
        time.sleep(float(os.environ.get("CB011_POLL", "2")))
    print(f"   TIMEOUT waiting for {label} job {job_id} (last state {last})")
    return {"job_id": job_id, "state": last}


BRIEF = {
    "title": "Kitchen fractions for a 9-year-old",
    "goal": "Halves, quarters and eighths of a real object, taught at the kitchen table with a knife "
            "and a measuring cup. The parent demonstrates, the child explains what they did.",
    "starting_point": "Counts to 100, reads a recipe with help, knows what a half looks like on a clock.",
    "age_band": "8-10",
    "reading_level": "Year 3, short sentences, decodable words",
    "duration_minutes": 25,
    "setting": "home",
    "materials": ["one apple", "plastic knife", "measuring cup", "paper plate"],
    "exclusions": ["no knife work by the child", "no nuts", "no timed pressure"],
    "supervision": "An adult holds the knife; the child places pieces and explains each cut.",
    "desired_pages": 3,
    "desired_visuals": "diagrams",
    "narration": "script",
    "locale": "en",
    "egress_acknowledged": True,
    "redaction_requested": False,
}


def create_brief() -> dict:
    key = f"cb011-brief-{time.time_ns()}"
    response = call("parent.brief.create", {"brief": BRIEF}, idempotency_key=key)
    created = result(response)
    print("   created:", json.dumps(created))
    return created


def read_brief(course_id: str) -> dict:
    response = call("parent.brief.get", {"course_id": course_id})
    return result(response)


def outline(enrollment_id: str) -> dict:
    return result(call("course.outline", {"enrollment_id": enrollment_id}))


def blueprint(course_id: str) -> dict:
    return result(call("parent.blueprint.read", {"course_id": course_id}))


def phase_plan(course_id: str | None = None) -> dict:
    if course_id:
        brief = read_brief(course_id)
    else:
        created = create_brief()
        course_id = created["course_id"]
        brief = read_brief(course_id)
    print("   brief:", json.dumps({k: v for k, v in brief.items() if k != "brief"}))
    print("   typed brief keys:", sorted((brief.get("brief") or {}).keys()))
    plan_job = brief.get("plan_job") or {}
    if plan_job.get("state") not in ("completed", None):
        wait_job(plan_job["job_id"], "plan")
    return {"course_id": course_id, "brief": brief}


def phase_full(course_id: str) -> dict:
    brief = read_brief(course_id)
    enrollment_id = brief.get("enrollment_id") or (brief.get("brief") or {}).get("enrollment_id")
    plan_job = brief.get("plan_job") or {}
    if plan_job.get("state") != "completed":
        wait_job(plan_job["job_id"], "plan")
    current = outline(enrollment_id)
    print("   outline plan:", json.dumps(current.get("plan")))
    plan = current.get("plan") or {}
    # The fence value is the digest recomputed from the plan rows, served by parent.blueprint.read;
    # course.outline echoes the digest generation stored with the plan document.
    book = blueprint(course_id)
    fence_hash = (book.get("plan") or {}).get("plan_hash") or plan.get("plan_hash")
    print("   fence hash:", fence_hash)
    revision = int(current.get("revision") or 0)

    # Draft edit: retitle the first objective, fenced on the hash the parent saw.
    objectives = current.get("objectives") or []
    if objectives and plan.get("state") == "draft":
        edit = call(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan["plan_id"],
                "expected_plan_hash": fence_hash,
                "objective_edits": [{"objective_id": objectives[0]["objective_id"],
                                     "title": (objectives[0]["title"] + " (kitchen table)")[:300]}],
            },
            expected_revision=revision,
            idempotency_key=f"cb011-edit-{time.time_ns()}",
        )
        if edit.get("ok"):
            revision = int(result(edit)["revision"])
            fence_hash = result(edit)["plan_hash"]
            plan = {**plan, "plan_hash": fence_hash}
            current = outline(enrollment_id)
            print("   after edit plan:", json.dumps(current.get("plan")))

    if plan.get("state") == "draft":
        approved = call(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan["plan_id"], "plan_hash": fence_hash},
            expected_revision=revision,
            idempotency_key=f"cb011-approve-{time.time_ns()}",
        )
        if approved.get("ok"):
            revision = int(result(approved)["revision"])
    current = outline(enrollment_id)
    print("   plan state after approve:", (current.get("plan") or {}).get("state"))

    lessons = call(
        "jobs.create",
        {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan["plan_id"]}},
        idempotency_key=f"cb011-lessons-{time.time_ns()}",
    )
    job_id = result(lessons).get("job_id")
    if job_id:
        wait_job(job_id, "lessons")

    book = blueprint(course_id)
    print("   blueprint plan:", json.dumps(book.get("plan")))
    print("   approval:", json.dumps(book.get("approval")))
    print("   export:", json.dumps(book.get("export")))
    for tab, files in (book.get("tabs") or {}).items():
        print(f"   tab {tab}: {len(files)} file(s)", [f.get("title") for f in files])
    print("   sources:", len(book.get("sources") or []))
    return {"course_id": course_id, "enrollment_id": enrollment_id, "revision": revision,
            "book": book, "plan": plan, "job_id": job_id}


def current_revision(enrollment_id: str) -> int:
    """The enrollment revision the studio fences its own commands on.

    ``library.list`` is where the studio's parent-course rows get ``revision`` (``course.outline``
    is deliberately revision 0: opening an outline must never move state).
    """
    listing = result(call("library.list", {"filter": "all", "recipe": "parent", "limit": 100,
                                           "sort": "recent"}))
    for item in listing.get("items") or []:
        if item.get("enrollment_id") == enrollment_id:
            return int(item.get("revision") or 0)
    raise SystemExit(f"enrollment {enrollment_id} is not in the parent library listing")


def phase_approve_and_export(course_id: str) -> dict:
    brief = read_brief(course_id)
    enrollment_id = brief.get("enrollment_id")
    book = blueprint(course_id)
    plan = book.get("plan") or {}
    if not enrollment_id:
        print(f"   course {course_id} has no enrollment to approve")
        return {"course_id": course_id, "book": book, "export": {}}
    # parent.final.approve is revision-fenced like every other lesson mutation (cb.rpc v6
    # allOf: idempotency_key + expected_revision). Read the revision the Desktop studio reads
    # (course.outline) instead of sending the command without one.
    revision = current_revision(enrollment_id)
    payload = {
        "enrollment_id": enrollment_id,
        "plan_id": plan.get("plan_id"),
        "plan_hash": plan.get("plan_hash"),
        "content_hash": book.get("content_hash"),
        "note": "Parent reviewed the pages, the answer guide and the narration script.",
    }
    final = call(
        "parent.final.approve",
        payload,
        expected_revision=revision,
        idempotency_key=f"cb011-final-{time.time_ns()}",
    )
    if not final.get("ok") and (final.get("error") or {}).get("code") == "STALE_REVISION":
        # The course moved between the read and the command: re-read and send the new fence
        # once, which is what the studio's stale-revision refresh does.
        revision = current_revision(enrollment_id)
        print(f"   retrying parent.final.approve at revision {revision}")
        final = call(
            "parent.final.approve",
            payload,
            expected_revision=revision,
            idempotency_key=f"cb011-final-{time.time_ns()}",
        )
    if final.get("ok"):
        revision = int(result(final)["revision"])
    book = blueprint(course_id)
    print("   revision:", revision)
    print("   approval:", json.dumps(book.get("approval")))
    print("   export:", json.dumps(book.get("export")))
    exported = call("parent.export", {"enrollment_id": enrollment_id},
                    idempotency_key=f"cb011-export-{time.time_ns()}")
    if exported.get("ok"):
        payload = result(exported)
        print("   exported:", json.dumps({k: v for k, v in payload.items() if k not in ("files", "artifacts")}))
        print("   files:", json.dumps([{k: f[k] for k in ("role", "name", "bytes", "mime")} for f in payload.get("files") or []]))
        print("   artifacts:", json.dumps([{k: a[k] for k in ("artifact_id", "kind", "bytes")} for a in payload.get("artifacts") or []]))
        for artifact in payload.get("artifacts") or []:
            facts = result(call("artifact.get", {"artifact_id": artifact["artifact_id"]}))
            print("   artifact.get:", json.dumps({k: facts.get(k) for k in ("artifact_id", "mime", "bytes", "content_hash")}))
    return {"course_id": course_id, "book": book, "export": result(exported)}


def phase_reflection(course_id: str) -> dict:
    recorded = call(
        "parent.reflection.record",
        {"course_id": course_id, "difficulty": "about_right",
         "revisit_note": "The quarter-to-eighth cut needed a second demonstration.",
         "apply_to_next_draft": True},
        idempotency_key=f"cb011-reflect-{time.time_ns()}",
    )
    listed = call("parent.reflection.list", {"course_id": course_id})
    print("   reflections:", json.dumps(result(listed)))
    return {"recorded": result(recorded), "list": result(listed)}


def phase_revise(course_id: str) -> dict:
    """After an active final approval: replan, edit the draft, observe the export gate."""
    brief = read_brief(course_id)
    enrollment_id = brief.get("enrollment_id")
    before = blueprint(course_id)
    print("   BEFORE approval:", json.dumps(before.get("approval")))
    print("   BEFORE export:", json.dumps(before.get("export")))
    current = outline(enrollment_id)
    plan = current.get("plan") or {}
    revision = int(current.get("revision") or 0)
    objectives = current.get("objectives") or []
    changes = [{"objective_id": o["objective_id"], "change": "keep"} for o in objectives]
    if changes:
        changes[0] = {**changes[0], "change": "retitle", "title": "Halves at the kitchen table (revised)"}
    replan = call("plan.replan", {"enrollment_id": enrollment_id, "objective_changes": changes},
                  expected_revision=revision, idempotency_key=f"cb011-replan-{time.time_ns()}")
    if replan.get("ok"):
        revision = int(result(replan)["revision"])
    current = outline(enrollment_id)
    plan = current.get("plan") or {}
    print("   replanned plan:", json.dumps(plan))
    mid = blueprint(course_id)
    revise_hash = (mid.get("plan") or {}).get("plan_hash") or plan.get("plan_hash")
    print("   AFTER replan approval:", json.dumps(mid.get("approval")))
    print("   AFTER replan export:", json.dumps(mid.get("export")))
    edited = call(
        "parent.plan.edit",
        {"enrollment_id": enrollment_id, "plan_id": plan.get("plan_id"),
         "expected_plan_hash": revise_hash,
         "course_title": "Kitchen fractions, revised"},
        expected_revision=revision, idempotency_key=f"cb011-revise-{time.time_ns()}",
    )
    if edited.get("ok"):
        revision = int(result(edited)["revision"])
    after = blueprint(course_id)
    print("   AFTER edit approval:", json.dumps(after.get("approval")))
    print("   AFTER edit export:", json.dumps(after.get("export")))
    blocked = call("parent.export", {"enrollment_id": enrollment_id},
                   idempotency_key=f"cb011-export-blocked-{time.time_ns()}")
    return {"before": before, "after_replan": mid, "after_edit": after,
            "export_refusal": blocked}


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "plan"
    course_id = os.environ.get("CB011_COURSE_ID") or sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CB011_COURSE_ID")
    out: dict = {"wire_version": VERSION, "phase": phase}
    if phase == "plan":
        out.update(phase_plan(course_id))
    elif phase == "full":
        out.update(phase_plan(course_id))
        out.update(phase_full(out["course_id"]))
    elif phase == "approve":
        out.update(phase_approve_and_export(course_id))
    elif phase == "reflect":
        out.update(phase_reflection(course_id))
    elif phase == "revise":
        out.update(phase_revise(course_id))
    else:
        print(f"unknown phase {phase!r}", file=sys.stderr)
        return 2
    path = os.environ.get("CB011_LOG")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"wire": WIRE, "calls": LOG, "result": out}, handle, indent=2)
        print(f"trace: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
