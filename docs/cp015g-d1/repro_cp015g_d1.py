"""CP-015g/D1 live reproduction over the mounted plugin RPC route.

Drives the installed backend the way the Desktop half does — course.create, enrollment.create,
jobs.create(kind=plan), then polls jobs.get — with the CP-015g brief: a backyard-observatory goal,
Short course, Game presentation. No plan text, fixture or authored content is supplied here; the
product's own generator and validator do the work.

Usage:
    python3 repro_cp015g_d1.py --port 44319 --token cp015g-d1-token [--out run.json]
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

CONTRACT = "cb.rpc"
CONTRACT_VERSION = 26

GOAL = "Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night"


def rpc(port: int, token: str, method: str, payload: dict, *, key: str | None = None) -> dict:
    body = {
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "method": method,
        "operation_id": f"cp015g-d1-{method.replace('.', '-')}-{os.urandom(4).hex()}",
        "payload": payload,
    }
    if key:
        body["idempotency_key"] = key
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/plugins/coursebook/rpc",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    record: dict = {"goal": GOAL, "scope": "short", "presentation_mode": "game"}
    run = os.urandom(3).hex()
    record["run"] = run
    brief = {
        "title": "Backyard observatory",
        "recipe": "casual",
        "goal": GOAL,
        "dials": {"depth": "working"},
        "locale": "en-US",
        "subject_domain": None,
        "scope": "short",
        "presentation_mode": "game",
    }
    created = rpc(args.port, args.token, "course.create", brief, key=f"cp015g-d1-course-{run}")
    record["course_create"] = created
    if not created.get("ok"):
        print(json.dumps(record, indent=2))
        return 1
    course_id = created["result"]["course_id"]

    enrolled = rpc(
        args.port,
        args.token,
        "enrollment.create",
        {"course_id": course_id, "learner_label": "Observatory"},
        key=f"cp015g-d1-enroll-{run}",
    )
    record["enrollment_create"] = enrolled
    if not enrolled.get("ok"):
        print(json.dumps(record, indent=2))
        return 1
    enrollment_id = enrolled["result"]["enrollment_id"]

    plan_brief = {
        "stage": "plan",
        "course_id": course_id,
        "enrollment_id": enrollment_id,
        "goal": GOAL,
        "recipe": "casual",
        "dials": brief["dials"],
        "locale": "en-US",
        "scope": "short",
    }
    job = rpc(args.port, args.token, "jobs.create", {"kind": "plan", "brief": plan_brief}, key=f"cp015g-d1-job-{run}")
    record["jobs_create"] = job
    if not job.get("ok"):
        print(json.dumps(record, indent=2))
        return 1
    job_id = job["result"]["job_id"]
    record["job_id"] = job_id

    started = time.time()
    last_state = None
    while time.time() - started < args.timeout:
        state = rpc(args.port, args.token, "jobs.get", {"job_id": job_id})
        payload = (state.get("result") or {}) if state.get("ok") else {}
        job_row = payload.get("job") or payload
        current = job_row.get("state")
        if current != last_state:
            print(f"job {job_id} state={current} t={time.time() - started:.0f}s", flush=True)
            last_state = current
        if current in ("succeeded", "failed", "cancelled", "blocked", "completed"):
            record["jobs_get"] = state
            break
        time.sleep(3)
    else:
        record["jobs_get"] = {"timeout": True, "last_state": last_state}

    # The reads a parent would use after approval: did an approvable plan actually land?
    outline = rpc(args.port, args.token, "course.outline", {"enrollment_id": enrollment_id})
    record["course_outline"] = outline
    surface = rpc(args.port, args.token, "course.surface", {"enrollment_id": enrollment_id})
    record["course_surface"] = surface

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
    print(json.dumps(
        {
            "job_id": job_id,
            "state": ((record.get("jobs_get") or {}).get("result") or {}).get("state"),
            "error": ((record.get("jobs_get") or {}).get("result") or {}).get("error"),
            "outline_ok": outline.get("ok"),
            "outline_objectives": len(((outline.get("result") or {}).get("objectives") or [])),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
