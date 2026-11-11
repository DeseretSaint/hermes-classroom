#!/usr/bin/env python3
"""CP-015: regenerate the run record from the demo backend's own rows.

The record is evidence, so it is *read* from the backend, never assembled by hand. Review round 1
found the hand-assembled record disagreed with the database: it began eight hours after its own
``started_at``, stopped before the final attempt closed, listed three plan attempts for five
stored verdicts and invented one verdict for a plan with no validation record, undercounted
``HOST_UNAVAILABLE`` rows (three stated, six stored), and carried no per-course source or image
count. Every one of those defects is a join this module now performs.

Read-only: the backend database is opened ``mode=ro``. Nothing here authors, approves, imports or
generates anything; it only projects rows into the record and writes JSON documents.

    python3 scripts/cp015_record.py --db ~/.hermes/coursebook-test-cp015/home/plugin-data/coursebook/data.db

Writes ``docs/concept-parity/demo/cp015-run.json`` and ``cp015-live-evidence.json``. Exit code is 1
if a required count cannot be established (for example a job row with no course attribution), so a
partial projection cannot be committed as the record.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = (Path.home() / ".hermes" / "coursebook-test-cp015" / "home"
              / "plugin-data" / "coursebook" / "data.db")
DEFAULT_OUT = ROOT / "docs" / "concept-parity" / "demo"

#: Job terminal states that are not success. Kept in step with the driver's own vocabulary.
FAILURE_STATES = {"failed", "cancelled", "interrupted_requires_retry", "cancel_requested",
                  "cancelling"}

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def parse_ts(value: str | None) -> datetime:
    """Parse every timestamp shape this backend stores into an aware UTC datetime."""
    if not value:
        raise ValueError("empty timestamp")
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fmt_ts(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return fmt_ts(parse_ts(value))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def course_slots() -> dict[str, str]:
    """``{title: slug}`` from the driver's own course table, so the record and the driver agree.

    The driver is the single source of truth for which four starter courses this card authors;
    duplicating the titles here would let the two drift apart silently.
    """
    import importlib.util

    path = ROOT / "scripts" / "cp015-demo-courses.py"
    if not path.is_file():  # pragma: no cover - defensive
        return {}
    spec = importlib.util.spec_from_file_location("cp015_demo_courses", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {str(spec_["title"]): slug for slug, spec_ in module.COURSES.items()}


def authoring_model_label() -> str:
    return "host ctx.llm (nous / deepseek-v4.1-flash-1017)"


def validator_label() -> str:
    return "same model; no independent route configured -> model_assessed"


# --------------------------------------------------------------------------------------
# Backend projection (read-only)
# --------------------------------------------------------------------------------------


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params)]


def collect(db_path: Path) -> dict:
    """Read the demo backend into the plain snapshot :func:`build_record` projects."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        snapshot = {
            "courses": _rows(conn, (
                "select id, title, status, subject_domain, locale, created_at, updated_at "
                "from courses where status != 'deleted' order by created_at")),
            "jobs": _rows(conn, (
                "select id, kind, state, brief_json, error_json, created_at, updated_at "
                "from jobs order by created_at")),
            "plans": _rows(conn, (
                "select id, course_id, state, plan_hash, created_at, approved_at "
                "from plans order by created_at")),
            "validations": _rows(conn, (
                "select id, subject_id, verdict, outcome, independence, validator_model, "
                "generator_model, created_at, "
                "json_extract(rejections_json, '$.rejections') as rejections "
                "from gen_validation_records "
                "where subject_kind = 'plan' order by created_at")),
            "plan_documents": _rows(conn, (
                "select id, plan_id, course_id, validation_id, generation_state, "
                "json_extract(result_json, '$.job_id') as job_id, "
                "json_extract(result_json, '$.validation_verdict') as validation_verdict, "
                "json_extract(result_json, '$.rejection_reasons') as rejection_reasons, "
                "created_at from gen_plan_documents order by created_at")),
            "plan_units": _counts(conn, "select plan_id, count(*) as n from plan_units "
                                        "group by plan_id"),
            "objectives": _counts(conn, "select plan_id, count(*) as n from objectives "
                                        "group by plan_id"),
            "sources": _counts(conn, "select course_id, count(*) as n from sources "
                                     "group by course_id"),
            "worlds": _rows(conn, "select id, course_id, state, created_at from course_worlds"),
            "world_assets": _counts(conn, (
                "select w.course_id as course_id, count(*) as n from world_assets a "
                "join course_worlds w on w.id = a.world_id group by w.course_id")),
            "lesson_runs": _counts(conn, (
                "select e.course_id as course_id, count(*) as n from lesson_runs r "
                "join enrollments e on e.id = r.enrollment_id group by e.course_id")),
            "lessons": _counts(conn, (
                "select p.course_id as course_id, count(*) as n from gen_lessons l "
                "join plans p on p.id = l.plan_id group by p.course_id")),
            "usage_events": _rows(conn, (
                "select operation_id, duration_ms, tokens_json from usage_events "
                "order by operation_id, duration_ms")),
        }
    finally:
        conn.close()
    return snapshot


def _counts(conn: sqlite3.Connection, sql: str) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    return {str(row[0]): int(row[1]) for row in conn.execute(sql)}


# --------------------------------------------------------------------------------------
# Record projection
# --------------------------------------------------------------------------------------


def _job_course(job: dict, plan_course: dict[str, str] | None = None) -> str | None:
    """The course a job belongs to.

    A plan job's brief names ``course_id``; a lessons or unit-sections job names
    ``enrollment_id`` and ``plan_id`` only. Those rows used to be dropped as unattributed, which
    made the record refuse the whole projection the moment a course reached lessons (CP-015b).
    The plan's own row is the authority, so the brief's ``plan_id`` resolves through it.
    """
    try:
        brief = json.loads(job.get("brief_json") or "{}")
    except (TypeError, ValueError):
        return None
    value = brief.get("course_id")
    if value:
        return str(value)
    plan_id = brief.get("plan_id")
    if plan_id and plan_course:
        resolved = plan_course.get(str(plan_id))
        if resolved:
            return str(resolved)
    return None


def _error(job: dict) -> dict:
    try:
        payload = json.loads(job.get("error_json") or "{}")
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_record(snapshot: dict, *, base: str, wire_version: int,
                 authoring_model: str, validator: str) -> dict:
    """Project a backend snapshot into the committed run record."""
    slots = course_slots()

    # ---- courses keyed by the card's four slots -------------------------------------------------
    courses: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    for row in snapshot.get("courses") or []:
        title = str(row.get("title") or "")
        slug = slots.get(title) or _slug(title)
        entry = courses.setdefault(slug, {
            "title": title,
            "course_id": None,
            "course_ids": [],
            "plan_approved": False,
            "units": 0,
            "pages": 0,
            "sources": 0,
            "images": 0,
            "planned_units": 0,
            "planned_objectives": 0,
            "world_approved": False,
            "lesson_runs": 0,
            "exported": False,
            "export_note": "exports are written as files, not backend rows; none is recorded here",
            "job_ids": [],
            "plan_attempts": [],
            "last_error": None,
        })
        entry["course_ids"].append(row["id"])
        entry["course_id"] = row["id"]  # newest row for the slot wins (rows are created-ordered)
        by_id[row["id"]] = entry

    plans = snapshot.get("plans") or []
    plan_by_id = {plan["id"]: plan for plan in plans}
    validations = snapshot.get("validations") or []
    validation_by_plan = {item["subject_id"]: item for item in validations}
    units = snapshot.get("plan_units") or {}
    objectives = snapshot.get("objectives") or {}

    # ---- jobs: every row, attributed to its course ---------------------------------------------
    plan_course: dict[str, str] = {
        str(plan["id"]): str(plan.get("course_id") or "") for plan in plans
    }
    jobs: list[dict] = []
    unattributed: list[str] = []
    for job in snapshot.get("jobs") or []:
        course_id = _job_course(job, plan_course)
        error = _error(job)
        raw_details = error.get("details")
        details: dict = raw_details if isinstance(raw_details, dict) else {}
        purpose = details.get("purpose") or error.get("purpose")
        record_job = {
            "id": job["id"],
            "kind": job["kind"],
            "state": job["state"],
            "course_id": course_id,
            "purpose": purpose,
            "error_code": error.get("code"),
            "error_message": error.get("message"),
            "created_at": fmt_ts(job["created_at"]),
            "updated_at": fmt_ts(job["updated_at"]),
        }
        jobs.append(record_job)
        entry = by_id.get(course_id or "")
        if entry is None:
            unattributed.append(job["id"])
            continue
        entry["job_ids"].append(job["id"])

    if unattributed:
        raise ValueError(
            "job rows carry no course attribution and cannot be placed in the record: "
            + ", ".join(unattributed)
        )

    # ---- plans: stored verdicts first, then authored plans the validator never judged ----------
    attempts: list[dict] = []
    validated_plans: set[str] = set()
    # A validation record is written at the same instant its job closes, so a plan whose
    # generation document was replaced can still name the job that produced its verdict.
    job_at = {(job["course_id"], job["updated_at"]): job["id"] for job in jobs}
    for item in validations:
        plan_id = str(item["subject_id"])
        plan = plan_by_id.get(plan_id) or {}
        entry = by_id.get(str(plan.get("course_id") or ""))
        rejections = _object_list(item.get("rejections"))
        reasons = [_reason_text(rejection) for rejection in rejections] or _reasons(plan_id, snapshot)
        attempt = {
            "plan_id": plan_id,
            "course_id": plan.get("course_id"),
            "validated": True,
            "validation_id": item["id"],
            "verdict": item["verdict"],
            "outcome": item.get("outcome"),
            "independence": item.get("independence"),
            "validator_model": item.get("validator_model"),
            "generator_model": item.get("generator_model"),
            "created_at": fmt_ts(item["created_at"]),
            "job_id": (_document_job(snapshot, plan_id)
                       or job_at.get((plan.get("course_id"), fmt_ts(item["created_at"])))
                       or _nearest_job(jobs, plan.get("course_id"), item["created_at"])),
            "reasons": reasons,
            "rejections": rejections,
            "claimed_verdict": None,
            "claimed_reasons": [],
            "unvalidated_reason": None,
        }
        attempts.append(attempt)
        validated_plans.add(plan_id)
        if entry is not None:
            entry["plan_attempts"].append(attempt)

    for document in snapshot.get("plan_documents") or []:
        plan_id = str(document["plan_id"])
        if plan_id in validated_plans:
            continue
        entry = by_id.get(str(document.get("course_id") or ""))
        claimed = _maybe_list(document.get("rejection_reasons"))
        claimed_verdict = document.get("validation_verdict")
        attempt = {
            "plan_id": plan_id,
            "course_id": document.get("course_id"),
            "validated": False,
            "validation_id": None,
            "verdict": None,
            "outcome": None,
            "independence": None,
            "validator_model": None,
            "generator_model": None,
            "created_at": fmt_ts(document["created_at"]),
            "job_id": document.get("job_id"),
            # The plan document's own result JSON can claim a verdict, but no stored validation
            # record backs it. It is reported here as a claim, never as the verdict.
            "reasons": [],
            "rejections": [],
            "claimed_verdict": claimed_verdict,
            "claimed_reasons": claimed,
            "unvalidated_reason": (
                "no gen_validation_records row exists for this plan"
                + (f"; the plan document claims verdict {claimed_verdict!r} with "
                   f"{len(claimed)} reason(s), which no stored validation record backs"
                   if claimed_verdict or claimed else "")
            ),
        }
        attempts.append(attempt)
        if entry is not None:
            entry["plan_attempts"].append(attempt)

    # ---- per-course counts and delivered state -------------------------------------------------
    worlds = snapshot.get("worlds") or []
    world_approved = {str(world["course_id"]) for world in worlds
                      if str(world.get("state")) == "approved"}
    source_counts = snapshot.get("sources") or {}
    image_counts = snapshot.get("world_assets") or {}
    lesson_run_counts = snapshot.get("lesson_runs") or {}
    lesson_counts = snapshot.get("lessons") or {}

    for slug, entry in courses.items():
        course_ids = entry["course_ids"]
        entry["sources"] = sum(int(source_counts.get(cid, 0)) for cid in course_ids)
        entry["images"] = sum(int(image_counts.get(cid, 0)) for cid in course_ids)
        entry["lesson_runs"] = sum(int(lesson_run_counts.get(cid, 0)) for cid in course_ids)
        entry["world_approved"] = any(cid in world_approved for cid in course_ids)

        approved = [plan for plan in plans
                    if plan.get("course_id") in course_ids and plan.get("state") == "approved"]
        entry["plan_approved"] = bool(approved)
        if approved:
            plan_id = str(approved[-1]["id"])
            entry["units"] = int(units.get(plan_id, 0))
            entry["pages"] = int(lesson_counts.get(str(approved[-1]["course_id"]), 0))
        authored = [plan["id"] for plan in plans if plan.get("course_id") in course_ids]
        entry["planned_units"] = max((int(units.get(pid, 0)) for pid in authored), default=0)
        entry["planned_objectives"] = max((int(objectives.get(pid, 0)) for pid in authored),
                                          default=0)
        entry["job_ids"].sort()
        entry["last_error"] = _last_error(entry, jobs, attempts)

    # ---- aggregate counts and the outcome sentence ---------------------------------------------
    host_rows = [job for job in jobs if job["error_code"] == "HOST_UNAVAILABLE"]
    by_purpose: dict[str, int] = {}
    for job in host_rows:
        key = str(job.get("purpose") or "unspecified")
        by_purpose[key] = by_purpose.get(key, 0) + 1
    by_state: dict[str, int] = {}
    for job in jobs:
        by_state[job["state"]] = by_state.get(job["state"], 0) + 1

    stamps = [parse_ts(job["created_at"]) for job in jobs]
    stamps += [parse_ts(job["updated_at"]) for job in jobs]
    stamps += [parse_ts(item["created_at"]) for item in validations]
    stamps += [parse_ts(document["created_at"]) for document in snapshot.get("plan_documents") or []]
    stamps += [parse_ts(plan["created_at"]) for plan in plans]
    if not stamps:  # pragma: no cover - defensive
        raise ValueError("the backend contains no rows to record")
    started_at = fmt_ts(min(stamps))
    finished_at = fmt_ts(max(stamps))

    unvalidated = [attempt for attempt in attempts if not attempt["validated"]]
    approved_count = sum(1 for entry in courses.values() if entry["plan_approved"])

    #: Rejections are counted by the criterion the stored verdict names. The sentence is computed
    #: from the rows only: an earlier version ended with a prose diagnosis of *why* every plan was
    #: rejected, and that sentence outlived the rule change it described (CP-015b found it still
    #: claiming the source_support conflict after the excerpt fix removed that class entirely).
    by_criterion: dict[str, int] = {}
    for attempt in attempts:
        for rejection in attempt.get("rejections") or []:
            key = str(rejection.get("criterion") or "unnamed")
            by_criterion[key] = by_criterion.get(key, 0) + 1
    by_verdict: dict[str, int] = {}
    for item in validations:
        key = str(item["verdict"])
        by_verdict[key] = by_verdict.get(key, 0) + 1
    latest = max(attempts, key=lambda item: parse_ts(item["created_at"]), default=None)

    outcome = (
        f"{approved_count} of {len(courses)} courses reached an approved plan. "
        f"The backend holds {len(jobs)} plan jobs; "
        f"{len(host_rows)} jobs ended HOST_UNAVAILABLE"
        + (f" ({', '.join(f'{count} {purpose}' for purpose, count in sorted(by_purpose.items()))})"
           if host_rows else "")
        + f", {len(validations)} plan verdicts are stored "
        f"({', '.join(f'{count} {verdict}' for verdict, count in sorted(by_verdict.items())) or 'none'})"
        + (f", and {len(unvalidated)} authored plan(s) have no validation record "
           f"({', '.join(item['plan_id'] for item in unvalidated)})" if unvalidated else "")
        + ". Rejections by criterion: "
        + (", ".join(f"{criterion} {count}"
                     for criterion, count in sorted(by_criterion.items(),
                                                    key=lambda item: (-item[1], item[0])))
           or "none")
        + (f". The latest stored verdict is plan {latest['plan_id']} "
           f"({latest.get('verdict')}) with {len(latest.get('rejections') or [])} reason(s)"
           if latest else "")
        + ". Every count here is a stored row; nothing was hand-written to fill it."
    )

    return {
        "base": base,
        "wire_version": wire_version,
        "backend": "isolated `hermes serve --isolated` on the disposable starter-course home",
        "authoring_model": authoring_model,
        "validator": validator,
        "record_source": (
            "generated by scripts/cp015_record.py from the demo backend DB (read-only); "
            "every job, validation and per-course count is a stored row"
        ),
        "started_at": started_at,
        "finished_at": finished_at,
        "counts": {
            "jobs": len(jobs),
            "jobs_by_state": by_state,
            "host_unavailable": len(host_rows),
            "host_unavailable_by_purpose": by_purpose,
            "validation_records": len(validations),
            "validation_verdicts": by_verdict,
            "rejections_by_criterion": by_criterion,
            "plans": len(plans),
            "plans_without_validation": len(unvalidated),
        },
        "jobs": jobs,
        "validations": [
            {
                "id": item["id"],
                "plan_id": str(item["subject_id"]),
                "course_id": str((plan_by_id.get(str(item["subject_id"])) or {})
                                 .get("course_id") or ""),
                "verdict": item["verdict"],
                "outcome": item.get("outcome"),
                "independence": item.get("independence"),
                "validator_model": item.get("validator_model"),
                "generator_model": item.get("generator_model"),
                "created_at": fmt_ts(item["created_at"]),
            }
            for item in validations
        ],
        "plan_attempts": attempts,
        "courses": courses,
        "outcome": outcome,
    }


def _document_job(snapshot: dict, plan_id: str) -> str | None:
    for document in snapshot.get("plan_documents") or []:
        if str(document["plan_id"]) == plan_id:
            return document.get("job_id")
    return None


def _nearest_job(jobs: list[dict], course_id, at, window_s: float = 15.0) -> str | None:
    """The job that closed closest to a stored verdict (generation writes a sub-second offset)."""
    if not course_id or not at:
        return None
    target = parse_ts(at)
    best: tuple[float, str] | None = None
    for job in jobs:
        if job.get("course_id") != course_id:
            continue
        delta = abs((parse_ts(job["updated_at"]) - target).total_seconds())
        if delta <= window_s and (best is None or delta < best[0]):
            best = (delta, job["id"])
    return best[1] if best else None


def _reasons(plan_id: str, snapshot: dict) -> list[str]:
    for document in snapshot.get("plan_documents") or []:
        if str(document["plan_id"]) == plan_id:
            return _maybe_list(document.get("rejection_reasons"))
    return []


def _maybe_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _object_list(value) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _reason_text(rejection: dict) -> str:
    item = str(rejection.get("item") or rejection.get("criterion") or "").strip()
    reason = str(rejection.get("reason") or rejection.get("criterion") or "").strip()
    if item and reason:
        return f"{item}: {reason}"
    return reason or item


def _last_error(entry: dict, jobs: list[dict], attempts: list[dict]) -> str | None:
    """The stopping condition for this course, named from the rows (never paraphrased).

    It is the *latest* thing that happened, not the worst. An approved course whose last attempt
    passed used to keep reporting an earlier reject as its "last error", which reads as a failure
    the course did not have (CP-015b: Sourdough approved, record still naming the 04:51 reject).
    """
    course_jobs = [job for job in jobs if job["id"] in set(entry["job_ids"])]
    course_attempts = [attempt for attempt in attempts
                       if attempt.get("course_id") == entry["course_id"]]
    latest_attempt = (max(course_attempts, key=lambda item: parse_ts(item["created_at"]))
                      if course_attempts else None)
    latest_job = (max(course_jobs, key=lambda job: parse_ts(job["updated_at"]))
                  if course_jobs else None)

    def _attempt_line(attempt: dict) -> str:
        if not attempt["validated"]:
            return f"plan {attempt['plan_id']} authored, validation never produced a verdict"
        if attempt["verdict"] == "pass":
            return f"plan {attempt['plan_id']} passed validation ({attempt.get('validation_id')})"
        return (f"plan {attempt['plan_id']} rejected by the validator with "
                f"{len(attempt.get('reasons') or [])} reason(s)")

    attempt_at = parse_ts(latest_attempt["created_at"]) if latest_attempt else None
    job_at = parse_ts(latest_job["updated_at"]) if latest_job else None
    if latest_attempt is not None and attempt_at is not None and (
            job_at is None or attempt_at >= job_at):
        if latest_attempt["validated"] and latest_attempt["verdict"] == "pass" \
                and entry["plan_approved"]:
            return None
        return _attempt_line(latest_attempt)
    if latest_job is not None and latest_job["state"] in FAILURE_STATES:
        code = f" ({latest_job['error_code']})" if latest_job.get("error_code") else ""
        return f"{latest_job['id']} ended {latest_job['state']}{code}"
    return None


# --------------------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------------------


def build_evidence(record: dict, snapshot: dict, *, demo_home: str) -> dict:
    """The raw-row companion: same job and validation set, with the provider calls behind it."""
    job_ids = {job["id"] for job in record["jobs"]}
    return {
        "captured_at": record["finished_at"],
        "backend": f"{record['base']} (isolated hermes serve, wire cb.rpc v{record['wire_version']})",
        "demo_home": demo_home,
        "provider_route": f"{record['authoring_model']}; validator {record['validator']}",
        "record_source": record["record_source"],
        "jobs": record["jobs"],
        "validations": record["validations"],
        "usage_events": [event for event in snapshot.get("usage_events") or []
                         if event["operation_id"] in job_ids],
    }


def write_records(db_path: Path, out_dir: Path, *, base: str, wire_version: int) -> tuple[Path, Path]:
    snapshot = collect(db_path)
    record = build_record(snapshot, base=base, wire_version=wire_version,
                          authoring_model=authoring_model_label(),
                          validator=validator_label())
    evidence = build_evidence(record, snapshot, demo_home=str(db_path.parents[2]))
    run_path = out_dir / "cp015-run.json"
    evidence_path = out_dir / "cp015-live-evidence.json"
    run_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return run_path, evidence_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--base", default="http://127.0.0.1:44501")
    parser.add_argument("--wire-version", type=int, default=25)
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"[cp015-record] no database at {args.db}", file=sys.stderr)
        return 1
    run_path, evidence_path = write_records(
        args.db, args.out, base=args.base, wire_version=args.wire_version)
    record = json.loads(run_path.read_text(encoding="utf-8"))
    print(f"[cp015-record] {record['counts']['jobs']} jobs, "
          f"{record['counts']['validation_records']} verdicts, "
          f"{record['counts']['host_unavailable']} HOST_UNAVAILABLE -> {run_path}")
    print(f"[cp015-record] evidence -> {evidence_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
