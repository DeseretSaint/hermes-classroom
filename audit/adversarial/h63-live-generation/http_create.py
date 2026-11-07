#!/usr/bin/env python3
"""Create a course, enrollment and plan job over the live HTTP cb.rpc transport.

Mirrors desktop/plugin.js::startLearnerPlan (course.create -> enrollment.create -> jobs.create)
against an isolated backend. Prints the ids and the raw envelopes as JSON.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44229")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")


def runtime() -> dict:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def call(method: str, payload: dict, key: str, expected_revision=None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": int(runtime()["wire_version"]),
        "method": method,
        "operation_id": f"h63-http-{method.replace('.', '-')}-{time.time_ns()}",
        "idempotency_key": key,
        "payload": payload,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc?profile=",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    out = {
        "base": BASE,
        "runtime": runtime(),
        "tag": os.environ.get("H63_TAG", "topic4-http"),
        "goal": os.environ.get("H63_GOAL", "How does a bicycle derailleur index through its gears?"),
        "title": os.environ.get("H63_TITLE", "Bicycle derailleur indexing (HTTP)"),
    }
    key = f"h63-{out['tag']}-{time.time_ns()}"
    course = call("course.create", {
        "title": out["title"], "recipe": "one_off", "goal": out["goal"],
        "dials": {"depth": "working", "pace": "light", "assessment": "none", "autonomy": "guided"},
        "subject_domain": "repair", "scope": "single",
    }, f"{key}-course")
    out["course"] = course
    course_id = course["result"]["course_id"]

    enrollment = call("enrollment.create",
                      {"course_id": course_id, "learner_label": out["title"]}, f"{key}-enroll")
    out["enrollment"] = enrollment
    enrollment_id = enrollment["result"]["enrollment_id"]

    job = call("jobs.create", {"kind": "plan", "brief": {
        "stage": "plan", "course_id": course_id, "enrollment_id": enrollment_id,
        "goal": out["goal"], "recipe": "one_off",
        "dials": {"depth": "working", "pace": "light", "assessment": "none", "autonomy": "guided"},
        "subject_domain": "repair", "scope": "single",
    }}, f"{key}-plan")
    out["job"] = job
    out["ids"] = {"course_id": course_id, "enrollment_id": enrollment_id,
                  "job_id": job["result"]["job_id"]}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
