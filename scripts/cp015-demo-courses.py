#!/usr/bin/env python3
"""CP-015: author the four demo courses through the product's own create flow.

Every course here is made the way a learner makes one: `course.create` → `enrollment.create`
→ one `plan` job whose brief the Desktop sends → the generated draft approved with the kernel
digest → the world concept boards → one style chosen → the world kit → final approval → the
lessons stage → a rendered `lesson.page`. Nothing is inserted into the database directly, and no
fixture stands in for the provider: the plan author, the validator, research and the plates are
whatever the running backend is configured for, and the run record says which.

This is a driver, not a test. It talks `cb.rpc` over the isolated demo backend and writes a JSON
run record the reviewer can diff against the shelf.

    CB013_BASE=http://127.0.0.1:44501 CB013_TOKEN=cp015-demo-token \
      python3 scripts/cp015-demo-courses.py --only japanese-cafe
    ... --all --record docs/concept-parity/demo/cp015-run.json

Exit code is 0 only when every requested course reaches an approved world and an authored lesson
page; a partial run prints the exact step and job that stopped it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44501")
TOKEN = os.environ.get("CB013_TOKEN", "cp015-demo-token")
ROOT = Path(__file__).resolve().parents[1]

#: The four demo classrooms, in shelf order. Titles are plain learner copy (no ticket labels, no
#: "live reject check", no fixture names). `recipe=committed` is a bounded course a learner means
#: to finish; `scope=short` matches the four-card shelf and keeps generation honest and affordable.
COURSES: dict[str, dict] = {
    "japanese-cafe": {
        "title": "Japanese Cafe Basics",
        "goal": "Order a drink and a snack at a Japanese cafe, ask for the bill, and understand "
                "the reply, politely, at a beginner level.",
        "recipe": "committed",
        "locale": "ja-JP",
        "level": "L0",
        "subject_domain": "language",
        "scope": "short",
        "dials": {"pace": "steady", "depth": "working", "assessment": "graded",
                  "autonomy": "guided"},
        "presentation_mode": "game",
    },
    "auto-repair": {
        "title": "Auto Repair Fundamentals",
        "goal": "Replace a head gasket on a four-cylinder engine: identify the failure, remove and "
                "refit the head in the correct order, torque it to the manual's sequence, and "
                "verify the repair before handing the car back.",
        "recipe": "committed",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "repair",
        "scope": "short",
        "dials": {"pace": "steady", "depth": "working", "assessment": "graded",
                  "autonomy": "guided"},
        "presentation_mode": "game",
    },
    "astronomy": {
        "title": "Astronomy",
        "goal": "Read the night sky: find the major constellations, understand why the sky "
                "changes through the year, and explain the phases of the Moon.",
        "recipe": "committed",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "science",
        "scope": "short",
        "dials": {"pace": "steady", "depth": "working", "assessment": "graded",
                  "autonomy": "guided"},
        "presentation_mode": "game",
    },
    "sourdough": {
        "title": "Sourdough",
        "goal": "Keep a starter alive and bake a reliable open-crumb sourdough loaf at home: "
                "build the levain, develop the dough, shape, and bake with steam.",
        "recipe": "committed",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "cooking",
        "scope": "short",
        "dials": {"pace": "steady", "depth": "working", "assessment": "graded",
                  "autonomy": "guided"},
        "presentation_mode": "game",
    },
}

#: ``completed`` is the success terminal state the job service writes; the retry/cancel states are
#: terminal failures. ``succeeded`` is accepted too so a future rename does not silently hang.
TERMINAL_JOB_STATES = {"completed", "succeeded", "failed", "cancelled",
                       "interrupted_requires_retry"}
SUCCESS_JOB_STATES = {"completed", "succeeded"}


def _log(message: str) -> None:
    print(f"[cp015] {message}", flush=True)


def _request(path: str, body: dict | None = None, timeout: int = 120) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


_wire: int | None = None


def wire_version() -> int:
    global _wire
    if _wire is None:
        runtime = _request("/runtime?profile=")
        _wire = int(runtime.get("wire_version") or 0)
        if not _wire:
            raise SystemExit(f"backend reported no wire_version: {runtime}")
    return _wire


def call(method: str, payload: dict, *, revision: int | None = None, key: str | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire_version(),
        "method": method,
        "operation_id": f"cp015-{method.replace('.', '-')}-{uuid.uuid4().hex[:10]}",
        "payload": payload,
    }
    if revision is not None:
        body["expected_revision"] = revision
    if key is not None:
        body["idempotency_key"] = key
    return _request("/rpc?profile=", body)


def ok(method: str, payload: dict, *, revision: int | None = None, key: str | None = None) -> dict:
    response = call(method, payload, revision=revision, key=key)
    if not response.get("ok"):
        raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'), indent=2)}")
    return response["result"]


_N = {"n": 0}


def keyed(slug: str, step: str) -> str:
    """Stable idempotency key per course step so a re-run never mints a second row."""
    return f"cp015-{slug}-{step}"


def wait_for_job(job_id: str, *, timeout: float = 1800.0, label: str = "") -> dict:
    started = time.monotonic()
    last = ""
    while True:
        job = ok("jobs.get", {"job_id": job_id})["job"]
        state = str(job.get("state"))
        progress = json.dumps(job.get("progress") or {})[:160]
        if state != last:
            _log(f"  {label or job_id}: {state} {progress}")
            last = state
        if state in TERMINAL_JOB_STATES:
            return job
        if time.monotonic() - started > timeout:
            raise RuntimeError(f"{label or job_id} still {state} after {timeout:.0f}s")
        time.sleep(5.0)


def create_course(slug: str, spec: dict) -> dict:
    created = ok("course.create", {k: v for k, v in spec.items()}, key=keyed(slug, "create"))
    course_id = created["course_id"]
    enrollment = ok(
        "enrollment.create",
        {"course_id": course_id, "learner_label": spec["title"]},
        key=keyed(slug, "enroll"),
    )
    enrollment_id = enrollment["enrollment_id"]
    _log(f"{slug}: course {course_id} enrolment {enrollment_id}")
    return {
        "slug": slug,
        "title": spec["title"],
        "course_id": course_id,
        "draft_plan_id": created.get("plan_id"),
        "enrollment_id": enrollment_id,
        "spec": spec,
    }


def run_plan(slug: str, flow: dict) -> dict:
    spec = flow["spec"]
    brief = {
        "stage": "plan",
        "course_id": flow["course_id"],
        "enrollment_id": flow["enrollment_id"],
        "goal": spec["goal"],
        "recipe": spec["recipe"],
        "dials": spec["dials"],
        "locale": spec["locale"],
        "level": spec["level"],
        "subject_domain": spec["subject_domain"],
        "scope": spec["scope"],
    }
    job = ok("jobs.create", {"kind": "plan", "brief": brief}, key=keyed(slug, "plan"))
    job_id = job["job_id"]
    _log(f"{slug}: plan job {job_id} queued")
    final = wait_for_job(job_id, label=f"{slug} plan", timeout=2400)
    flow["plan_job_id"] = job_id
    flow["plan_job_state"] = final.get("state")
    flow["plan_job_error"] = final.get("error")
    if final.get("state") not in SUCCESS_JOB_STATES:
        raise RuntimeError(f"{slug}: plan job {job_id} ended {final.get('state')}: "
                           f"{json.dumps(final.get('error'))[:600]}")
    outline = ok("course.outline", {"enrollment_id": flow["enrollment_id"]})
    plan = outline.get("plan") or {}
    flow["plan_id"] = plan.get("plan_id")
    flow["objectives"] = [
        {"id": item["id"], "title": item.get("title"), "unit": item.get("unit_ordinal")}
        for item in outline.get("objectives") or []
    ]
    flow["validation"] = plan.get("validation")
    _log(f"{slug}: plan {flow['plan_id']} draft, {len(flow['objectives'])} objectives")
    return flow


def approve_plan(slug: str, flow: dict) -> dict:
    book = ok("parent.blueprint.read", {"course_id": flow["course_id"]})
    plan = book["plan"]
    approved = ok(
        "plan.approve",
        {"enrollment_id": flow["enrollment_id"], "plan_id": plan["plan_id"],
         "plan_hash": plan["plan_hash"]},
        revision=0,
        key=keyed(slug, "approve"),
    )
    flow["plan_approved_revision"] = approved.get("revision")
    flow["plan_hash"] = plan["plan_hash"]
    flow["plan_state"] = plan.get("state")
    _log(f"{slug}: plan approved (rev {approved.get('revision')})")
    return flow


def build_world(slug: str, flow: dict) -> dict:
    world = ok("world.read", {"course_id": flow["course_id"]})
    revision = int(world.get("revision") or 0)
    state = str((world.get("world") or {}).get("state") or "")
    _log(f"{slug}: world state {state} rev {revision}")
    if state not in ("concepts_ready", "style_selected", "kit_ready", "approved"):
        queued = ok(
            "world.generate",
            {"course_id": flow["course_id"], "stage": "concepts"},
            revision=revision,
            key=keyed(slug, "world-concepts"),
        )
        _log(f"{slug}: concepts job {queued.get('job_id')}")
        if queued.get("job_id"):
            final = wait_for_job(str(queued["job_id"]), label=f"{slug} concepts", timeout=2400)
            if final.get("state") not in SUCCESS_JOB_STATES:
                raise RuntimeError(f"{slug}: concepts job ended {final.get('state')}: "
                                   f"{json.dumps(final.get('error'))[:600]}")
        world = ok("world.read", {"course_id": flow["course_id"]})
        revision = int(world.get("revision") or 0)
        state = str((world.get("world") or {}).get("state") or "")
    concepts = world.get("concepts") or []
    flow["world_concepts"] = [
        {"style_id": item.get("style_id"), "style_hash": item.get("style_hash"),
         "name": item.get("name")}
        for item in concepts
    ]
    if state == "concepts_ready":
        if not concepts:
            raise RuntimeError(f"{slug}: concepts_ready with no concept boards")
        chosen = concepts[0]
        # The first board is the recommended grammar, not a random pick; the hash is the one the
        # backend generated, so the choice is provable.
        approved = ok(
            "world.approve",
            {"course_id": flow["course_id"], "world_id": world["world"]["world_id"]
             if "world_id" in (world.get("world") or {}) else world["world"]["id"],
             "stage": "style", "approved_hash": chosen["style_hash"]},
            revision=revision,
            key=keyed(slug, "world-style"),
        )
        _log(f"{slug}: style chosen ({chosen.get('name')}) -> {approved.get('state')}")
        world = ok("world.read", {"course_id": flow["course_id"]})
        revision = int(world.get("revision") or 0)
        state = str((world.get("world") or {}).get("state") or "")
    if state == "style_selected":
        queued = ok(
            "world.generate",
            {"course_id": flow["course_id"], "stage": "kit"},
            revision=revision,
            key=keyed(slug, "world-kit"),
        )
        _log(f"{slug}: kit job {queued.get('job_id')}")
        if queued.get("job_id"):
            final = wait_for_job(str(queued["job_id"]), label=f"{slug} kit", timeout=3000)
            if final.get("state") not in SUCCESS_JOB_STATES:
                raise RuntimeError(f"{slug}: kit job ended {final.get('state')}: "
                                   f"{json.dumps(final.get('error'))[:600]}")
        world = ok("world.read", {"course_id": flow["course_id"]})
        revision = int(world.get("revision") or 0)
        state = str((world.get("world") or {}).get("state") or "")
    flow["world_assets"] = [
        {"role": item.get("role"), "section_key": item.get("section_key"),
         "artifact_id": item.get("artifact_id"), "sha256": item.get("sha256")}
        for item in world.get("assets") or []
    ]
    if state == "kit_ready":
        approved = ok(
            "world.approve",
            {"course_id": flow["course_id"],
             "world_id": (world.get("world") or {}).get("world_id")
             or (world.get("world") or {}).get("id"),
             "stage": "final", "approved_hash": (world.get("world") or {}).get("kit_hash")},
            revision=revision,
            key=keyed(slug, "world-final"),
        )
        _log(f"{slug}: world approved -> {approved.get('state')}")
        world = ok("world.read", {"course_id": flow["course_id"]})
        state = str((world.get("world") or {}).get("state") or "")
    flow["world_state"] = state
    flow["world_revision"] = int(world.get("revision") or 0)
    flow["world_image_count"] = len(flow["world_assets"])
    if state != "approved":
        raise RuntimeError(f"{slug}: world ended {state}, not approved")
    return flow


def run_lessons(slug: str, flow: dict) -> dict:
    brief = {"stage": "lessons", "plan_id": flow["plan_id"],
             "enrollment_id": flow["enrollment_id"]}
    job = ok("jobs.create", {"kind": "plan", "brief": brief}, key=keyed(slug, "lessons"))
    job_id = job["job_id"]
    _log(f"{slug}: lessons job {job_id}")
    final = wait_for_job(job_id, label=f"{slug} lessons", timeout=3000)
    flow["lessons_job_id"] = job_id
    flow["lessons_job_state"] = final.get("state")
    flow["lessons_job_error"] = final.get("error")
    if final.get("state") not in SUCCESS_JOB_STATES:
        raise RuntimeError(f"{slug}: lessons job {job_id} ended {final.get('state')}: "
                           f"{json.dumps(final.get('error'))[:600]}")
    return flow


def render_lesson(slug: str, flow: dict) -> dict:
    outline = ok("course.outline", {"enrollment_id": flow["enrollment_id"]})
    objectives = outline.get("objectives") or []
    if not objectives:
        raise RuntimeError(f"{slug}: approved plan has no objectives")
    first = objectives[0]
    begun = ok(
        "lesson.begin",
        {"enrollment_id": flow["enrollment_id"], "objective_id": first["id"], "mode": "fresh"},
        key=keyed(slug, "begin"),
    )
    page = ok(
        "lesson.page",
        {"enrollment_id": flow["enrollment_id"], "objective_id": first["id"]},
    )
    blocks = page.get("blocks") or page.get("segments") or []
    flow["lesson_objective"] = {"id": first["id"], "title": first.get("title")}
    flow["lesson_run_id"] = begun.get("lesson_run_id")
    flow["lesson_page_state"] = page.get("state") or (page.get("page") or {}).get("state")
    flow["lesson_page_blocks"] = len(blocks)
    flow["lesson_page_media"] = len(page.get("media") or [])
    flow["lesson_check"] = bool(page.get("check"))
    _log(f"{slug}: lesson page {len(blocks)} blocks, {flow['lesson_page_media']} media, "
         f"state {flow['lesson_page_state']}")
    if not blocks:
        raise RuntimeError(f"{slug}: lesson.page served no blocks")
    return flow


def run_one(slug: str, spec: dict) -> dict:
    _log(f"=== {slug}: {spec['title']} ===")
    flow = create_course(slug, spec)
    flow = run_plan(slug, flow)
    flow = approve_plan(slug, flow)
    flow = build_world(slug, flow)
    flow = run_lessons(slug, flow)
    flow = render_lesson(slug, flow)
    flow["completed_at"] = datetime.now(timezone.utc).isoformat()
    return flow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", choices=sorted(COURSES), default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--record", help="write the run record JSON here")
    parser.add_argument("--merge", action="store_true",
                        help="merge into an existing record instead of replacing it")
    args = parser.parse_args()

    selected = sorted(COURSES) if args.all or not args.only else args.only
    record: dict = {"base": BASE, "wire_version": wire_version(), "started_at":
                    datetime.now(timezone.utc).isoformat(), "courses": {}}
    if args.merge and args.record and Path(args.record).is_file():
        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
        record.setdefault("courses", {})

    failures = []
    for slug in selected:
        try:
            record["courses"][slug] = run_one(slug, COURSES[slug])
        except Exception as exc:  # noqa: BLE001 - recorded, then reported per course
            failures.append((slug, str(exc)))
            record["courses"][slug] = {"slug": slug, "error": str(exc)}
            _log(f"{slug}: FAILED — {exc}")
        if args.record:
            Path(args.record).parent.mkdir(parents=True, exist_ok=True)
            Path(args.record).write_text(json.dumps(record, indent=2), encoding="utf-8")

    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.record:
        Path(args.record).write_text(json.dumps(record, indent=2), encoding="utf-8")
        _log(f"record: {args.record}")
    for slug, error in failures:
        _log(f"FAILED {slug}: {error.splitlines()[0]}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
