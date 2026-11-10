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
import hashlib
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
        "dials": {"pace": "steady", "depth": "deep", "assessment": "graded",
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
        "dials": {"pace": "steady", "depth": "deep", "assessment": "graded",
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
        "dials": {"pace": "steady", "depth": "deep", "assessment": "graded",
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
        "dials": {"pace": "steady", "depth": "deep", "assessment": "graded",
                  "autonomy": "guided"},
        "presentation_mode": "game",
    },
}

#: ``completed`` is the success terminal state the job service writes; the retry/cancel states are
#: terminal failures. ``succeeded`` is accepted too so a future rename does not silently hang.
TERMINAL_JOB_STATES = {"completed", "succeeded", "failed", "cancelled",
                       "interrupted_requires_retry"}
SUCCESS_JOB_STATES = {"completed", "succeeded"}


#: How many authored plans one demo course may burn before the driver reports the rejection.
#: A validator reject is grounded in named defects, and re-authoring is the learner's own path; the
#: limit keeps a run from looping on an author model that cannot satisfy the contract.
PLAN_ATTEMPTS = 3

#: Per-attempt bound on a plan job. The provider call can outlive the job's own deadline
#: (CP-044), so the driver refuses to wait on one attempt longer than this.
PLAN_ATTEMPT_TIMEOUT_S = 300.0


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


_key_scope: dict[str, str] = {"scope": ""}


def keyed(slug: str, step: str) -> str:
    """Stable idempotency key per course step so a re-run never mints a second row.

    The key is scoped to the course instance the run is working on: a re-run of the same course
    is the same key, while a freshly created course (after a data reset, or because the brief
    changed) is a different scope. Without the scope a re-created course would collide on the
    old enrollment/plan/attempt keys, which the kernel refuses as an idempotency conflict.
    """
    scope = _key_scope["scope"]
    return f"cp015-{slug}-{scope + '-' if scope else ''}{step}"


def spec_key(slug: str, spec: dict) -> str:
    """``course.create`` key that also covers the brief.

    A re-run with the same brief is the same course (the key is stable). A re-run whose goal,
    scope or dials changed is a *different* course, and reusing the old key would be refused as an
    idempotency conflict; the brief digest keeps both properties without minting a duplicate.
    """
    digest = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"cp015-{slug}-create-{digest}"


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
    created = ok("course.create", {k: v for k, v in spec.items()}, key=spec_key(slug, spec))
    course_id = created["course_id"]
    _key_scope["scope"] = hashlib.sha256(course_id.encode("utf-8")).hexdigest()[:10]
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


def _objectives(outline: dict) -> list[dict]:
    """The outline's objectives, in the shape this driver uses (``id`` = the stored key).

    ``course.outline`` answers ``objective_id`` (the scheduling key) and the unit each objective
    belongs to is carried on ``plan.units[].objectives[]``; the driver's own field is ``id`` so the
    flow record reads the same for a v1 plan (flat ``objectives``) and a blueprint plan.
    """
    unit_of: dict[str, int] = {}
    for unit in (outline.get("plan") or {}).get("units") or []:
        for objective in unit.get("objectives") or []:
            unit_of[str(objective.get("objective_id"))] = int(unit.get("ordinal") or 0)
    objectives: list[dict] = []
    for item in outline.get("objectives") or []:
        key = str(item.get("objective_id") or item.get("id") or "")
        if not key:
            raise RuntimeError(f"outline objective without an id: {json.dumps(item)[:300]}")
        objectives.append(
            {
                "id": key,
                "title": item.get("title"),
                "unit": item.get("unit_ordinal") or unit_of.get(key),
                "evidence_target": item.get("evidence_target"),
            }
        )
    return objectives


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
    flow.setdefault("plan_attempts", [])
    # A rejected plan is a real verdict, not an error to paper over: regenerating is what a learner
    # does, and every attempt's verdict is recorded so the record never claims a first-time pass.
    for attempt in range(1, PLAN_ATTEMPTS + 1):
        key = keyed(slug, "plan") if attempt == 1 else keyed(slug, f"plan-retry{attempt - 1}")
        job = ok("jobs.create", {"kind": "plan", "brief": brief}, key=key)
        job_id = job["job_id"]
        _log(f"{slug}: plan job {job_id} queued (attempt {attempt})")
        # CP-044 owns the job deadline that never cancels a hanging provider call. Until it lands,
        # this driver bounds each attempt itself so one hang costs minutes, not the ~650 s a
        # provider call can outlive the job's own limit.
        final = wait_for_job(job_id, label=f"{slug} plan", timeout=PLAN_ATTEMPT_TIMEOUT_S)
        flow["plan_job_id"] = job_id
        flow["plan_job_state"] = final.get("state")
        flow["plan_job_error"] = final.get("error")
        if final.get("state") not in SUCCESS_JOB_STATES:
            raise RuntimeError(f"{slug}: plan job {job_id} ended {final.get('state')}: "
                               f"{json.dumps(final.get('error'))[:600]}")
        outline = ok("course.outline", {"enrollment_id": flow["enrollment_id"]})
        plan = outline.get("plan") or {}
        validation = plan.get("validation") or {}
        flow["plan_attempts"].append(
            {
                "job_id": job_id,
                "plan_id": plan.get("plan_id"),
                "plan_hash": plan.get("plan_hash"),
                "state": plan.get("state"),
                "verdict": validation.get("verdict"),
                "outcome": validation.get("outcome"),
                "independence": validation.get("independence"),
                "approvable": validation.get("approvable"),
                "reasons": validation.get("reasons"),
            }
        )
        flow["plan_id"] = plan.get("plan_id")
        flow["objectives"] = _objectives(outline)
        flow["validation"] = validation
        _log(f"{slug}: plan {flow['plan_id']} {plan.get('state')}, "
             f"verdict {validation.get('verdict')}, {len(flow['objectives'])} objectives")
        if not flow["objectives"]:
            # A draft row with no objectives is what `course.create` writes before authoring. It
            # is never a course, and the approval gate now refuses it (plan_empty); treat it as a
            # failed attempt rather than a plan to approve.
            _log(f"{slug}: plan {flow['plan_id']} carries no objectives; not approvable")
            continue
        if validation.get("approvable"):
            return flow
        if attempt < PLAN_ATTEMPTS:
            _log(f"{slug}: plan not approvable; regenerating "
                 f"({len(validation.get('reasons') or [])} reasons recorded)")
    reasons = flow["validation"].get("reasons") or []
    raise RuntimeError(
        f"{slug}: plan still not approvable after {PLAN_ATTEMPTS} authored plans: "
        + "; ".join(str(reason) for reason in reasons[:6])
    )


def approve_plan(slug: str, flow: dict) -> dict:
    book = ok("parent.blueprint.read", {"course_id": flow["course_id"]})
    plan = book["plan"]
    validation = plan.get("validation") or flow.get("validation") or {}
    if not validation.get("approvable"):
        raise RuntimeError(
            f"{slug}: refusing to approve a plan the validator did not clear "
            f"(verdict {validation.get('verdict')}): "
            + "; ".join(str(reason) for reason in (validation.get("reasons") or [])[:4])
        )
    if not flow.get("objectives"):
        raise RuntimeError(f"{slug}: refusing to approve a plan with no objectives")
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


def render_lesson(slug: str, flow: dict, *, after_world: bool = False) -> dict:
    outline = ok("course.outline", {"enrollment_id": flow["enrollment_id"]})
    objectives = _objectives(outline)
    if not objectives:
        raise RuntimeError(f"{slug}: approved plan has no objectives")
    first = objectives[0]
    begun = ok(
        "lesson.begin",
        {"enrollment_id": flow["enrollment_id"], "objective_id": first["id"], "mode": "fresh"},
        key=keyed(slug, "begin-after-world" if after_world else "begin"),
    )
    page = ok(
        "lesson.page",
        {"enrollment_id": flow["enrollment_id"], "objective_id": first["id"]},
    )
    blocks = page.get("blocks") or page.get("segments") or []
    suffix = "_after_world" if after_world else ""
    flow[f"lesson_run_id{suffix}"] = begun.get("lesson_run_id")
    flow[f"lesson_page_state{suffix}"] = page.get("state") or (page.get("page") or {}).get("state")
    flow[f"lesson_page_blocks{suffix}"] = len(blocks)
    flow[f"lesson_page_media{suffix}"] = len(page.get("media") or [])
    flow[f"lesson_check{suffix}"] = bool(page.get("check"))
    if not after_world:
        flow["lesson_objective"] = {"id": first["id"], "title": first.get("title")}
    _log(f"{slug}: lesson page{' after world' if after_world else ''} {len(blocks)} blocks, "
         f"{flow[f'lesson_page_media{suffix}']} media, state {flow[f'lesson_page_state{suffix}']}")
    if not blocks:
        raise RuntimeError(f"{slug}: lesson.page served no blocks")
    return flow


def export_course(slug: str, flow: dict, copy_to: Path | None = None) -> dict:
    """Package the course through ``course.export`` and optionally copy the zip out.

    The export gate is the product's own: an approved plan plus pages a validator cleared (or a
    human approved) and a content hash the caller reviewed. Nothing here bypasses it.
    """
    read = ok("course.export.read", {"enrollment_id": flow["enrollment_id"]})
    if not read.get("ready"):
        raise RuntimeError(
            f"{slug}: export not ready: {read.get('blocked_reason')} "
            f"{read.get('blocked_message')} {read.get('problems')}"
        )
    digest = str(read["content_hash"])
    exported = ok(
        "course.export",
        {"enrollment_id": flow["enrollment_id"], "expected_content_hash": digest},
        key=keyed(slug, "export"),
    )
    flow["export"] = {
        "export_id": exported.get("export_id"),
        "pack_id": (exported.get("pack") or {}).get("pack_id"),
        "pack_version": (exported.get("pack") or {}).get("pack_version"),
        "manifest_hash": (exported.get("pack") or {}).get("manifest_hash"),
        "content_hash": exported.get("content_hash"),
        "files": len(exported.get("files") or []),
        "license": (exported.get("license") or {}).get("license_id")
        or (exported.get("license") or {}).get("id"),
    }
    root = Path(os.environ.get("CP015_EXPORT_ROOT",
                               str(Path(os.environ.get("CP015_HOME", "")).expanduser()
                                   / "plugin-data/coursebook/pack-exports")))
    pack_id = flow["export"]["pack_id"]
    candidates = sorted(root.glob(f"{pack_id}-*.zip"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError(f"{slug}: course.export wrote no archive under {root}")
    source = candidates[-1]
    flow["export"]["archive"] = str(source)
    flow["export"]["archive_bytes"] = source.stat().st_size
    if copy_to is not None:
        copy_to.mkdir(parents=True, exist_ok=True)
        destination = copy_to / f"{slug}.zip"
        destination.write_bytes(source.read_bytes())
        flow["export"]["copied_to"] = str(destination)

    # The pack gate is the product's own: `pack.preview` runs packs.validate_manifest on the
    # written archive, so this records that the artifact really is an importable pack rather than
    # a zip we produced. The title and licence it would ship with are recorded with it.
    granted = _request("/packs/grant", {"path": str(source)})
    if not granted.get("ok"):
        raise RuntimeError(f"{slug}: pack grant refused: {json.dumps(granted.get('error'))[:400]}")
    preview = ok("pack.preview", {"staged_id": granted["staged_id"]})
    manifest = preview.get("manifest") or {}
    flow["export"]["pack"] = {
        "pack_id": manifest.get("pack_id"),
        "pack_version": manifest.get("pack_version"),
        "title": manifest.get("title"),
        "license_id": (manifest.get("license") or {}).get("id"),
        "redistribution": (manifest.get("license") or {}).get("redistribution"),
        "content_hash": manifest.get("content_hash"),
        "files": len(manifest.get("files") or []),
        "hashes_match": (preview.get("integrity") or {}).get("hashes_match"),
    }
    # Owner ruling 2026-11-10: these are starter courses, not demo data. Nothing user-visible may
    # say demo, sample or fixture — checked on the manifest fields a learner would read.
    visible = " ".join(str(manifest.get(key) or "") for key in ("title", "summary", "attribution"))
    for word in ("demo", "sample", "fixture"):
        if word in visible.lower():
            raise RuntimeError(f"{slug}: exported pack is labelled with {word!r}: {visible[:200]}")
    _log(f"{slug}: exported {pack_id} ({flow['export'].get('archive_bytes')} bytes, "
         f"{flow['export']['files']} files) validated as pack "
         f"{manifest.get('pack_id')} title={manifest.get('title')!r} "
         f"license={(manifest.get('license') or {}).get('id')!r}")
    return flow


def run_one(slug: str, spec: dict) -> dict:
    _log(f"=== {slug}: {spec['title']} ===")
    flow = create_course(slug, spec)
    try:
        flow = run_plan(slug, flow)
        flow = approve_plan(slug, flow)
        # Order matters (supervisor ruling 2026-11-10): one authored lesson page proves the plan
        # is teachable before any image-provider call is spent on a world kit.
        flow = run_lessons(slug, flow)
        flow = render_lesson(slug, flow)
        flow = build_world(slug, flow)
        # Re-read the page after the kit: the same objective now has its world media, and the
        # record must show the media actually resolves rather than only that files exist.
        flow = render_lesson(slug, flow, after_world=True)
    except Exception as exc:  # noqa: BLE001 - the partial flow is the evidence
        # A per-attempt verdict list is the evidence a reviewer needs; without this the record
        # keeps only the first line of the last failure.
        exc.partial_flow = flow  # type: ignore[attr-defined]
        raise
    flow["completed_at"] = datetime.now(timezone.utc).isoformat()
    return flow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", choices=sorted(COURSES), default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--record", help="write the run record JSON here")
    parser.add_argument("--merge", action="store_true",
                        help="merge into an existing record instead of replacing it")
    parser.add_argument("--export-only", action="store_true",
                        help="export the courses already in --record; generate nothing")
    parser.add_argument("--copy-exports", metavar="DIR",
                        help="copy each exported zip into DIR (committed seed directory)")
    args = parser.parse_args()

    selected = sorted(COURSES) if args.all or not args.only else args.only
    record: dict = {"base": BASE, "wire_version": wire_version(), "started_at":
                    datetime.now(timezone.utc).isoformat(), "courses": {}}
    if args.merge and args.record and Path(args.record).is_file():
        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
        record.setdefault("courses", {})

    failures = []
    copy_to = Path(args.copy_exports) if args.copy_exports else None
    if args.export_only:
        if not args.record or not Path(args.record).is_file():
            raise SystemExit("--export-only needs an existing --record")
        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
        for slug, flow in (record.get("courses") or {}).items():
            if flow.get("error") or not flow.get("enrollment_id"):
                _log(f"{slug}: skipped (no completed course in the record)")
                continue
            if args.only and slug not in args.only:
                continue
            try:
                export_course(slug, flow, copy_to=copy_to)
            except Exception as exc:  # noqa: BLE001
                failures.append((slug, str(exc)))
                flow["export_error"] = str(exc)
                _log(f"{slug}: export FAILED — {exc}")
        Path(args.record).write_text(json.dumps(record, indent=2), encoding="utf-8")
        for slug, error in failures:
            _log(f"FAILED {slug}: {error.splitlines()[0]}")
        return 1 if failures else 0

    for slug in selected:
        try:
            flow = run_one(slug, COURSES[slug])
            record["courses"][slug] = flow
            if copy_to is not None:
                try:
                    export_course(slug, flow, copy_to=copy_to)
                except Exception as exc:  # noqa: BLE001 - the course stays recorded
                    failures.append((slug, f"export: {exc}"))
                    flow["export_error"] = str(exc)
                    _log(f"{slug}: export FAILED — {exc}")
        except Exception as exc:  # noqa: BLE001 - recorded, then reported per course
            failures.append((slug, str(exc)))
            partial = getattr(exc, "partial_flow", None)
            if isinstance(partial, dict):
                partial["error"] = str(exc)
                record["courses"][slug] = partial
            else:
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
