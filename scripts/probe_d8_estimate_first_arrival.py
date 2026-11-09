"""D8 probe: is the desk's estimate 'error' state reachable on a fresh enrollment?

Runs the real kernel against a throwaway HERMES_HOME and asks the two reads
`useSessionEstimate` issues, for both ways a fresh course is created:

  A. `course.create` (the in-app / learner flow) then `enrollment.create`;
  B. `parent.brief.create` (Parent Studio), which creates the course, its enrollment
     and the queued plan job in one call.

The desk only asks when it has a row *and* an outline objective, so this probe also
reads `course.outline` — case A having no objective is itself the answer for first
arrival: the read never fires.

An `ok:false` answer with a code other than NOT_FOUND puts the desk in the red
`Session length could not be read` + Retry state. NOT_FOUND is the answer
"this course has no parent brief", which the desk renders as `Session length not recorded`.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursebook import api, db  # noqa: E402
from tests.test_learner_plan_flow import learner_course_payload  # noqa: E402

PARENT_BRIEF = {
    "title": "Kitchen chemistry for a seven-year-old",
    "goal": "Explain why baking soda fizzes and predict what changes it",
    "starting_point": None,
    "age_band": "7-9",
    "reading_level": "early reader, short sentences",
    "duration_minutes": 45,
    "setting": "home",
    "materials": ["baking soda", "vinegar", "two bowls"],
    "exclusions": ["no open flame"],
    "supervision": "An adult pours the vinegar; the child measures and writes.",
    "desired_pages": 6,
    "desired_visuals": "diagrams",
    "narration": "script",
    "locale": "en-US",
    "egress_acknowledged": True,
    "redaction_requested": False,
}


def dispatch(method, payload=None, key=None):
    body = {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"probe-{method.replace('.', '-')}-{os.urandom(4).hex()}",
        "payload": payload or {},
    }
    if key:
        body["idempotency_key"] = key
    return api.dispatch(body)


def desk_state(answer):
    if answer.get("ok"):
        minutes = (answer.get("result") or {}).get("brief", {}).get("duration_minutes")
        return f"ready ≈ {minutes} min" if minutes else "none (Session length not recorded)"
    code = (answer.get("error") or {}).get("code")
    if code == "NOT_FOUND":
        return "none (Session length not recorded)"
    return f"error (Session length could not be read + Retry) — {code}"


home = tempfile.mkdtemp(prefix="d8-probe-")
os.environ["HERMES_HOME"] = home
try:
    db.migrate()
    out = {}

    # A — in-app / learner create.
    created = dispatch("course.create", learner_course_payload(), key="probe-create")
    if not created.get("ok"):
        print(json.dumps({"course_create": created}, indent=2)[:2000])
        raise SystemExit(1)
    course_a = created["result"]["course_id"]
    enrolled = dispatch(
        "enrollment.create",
        {"course_id": course_a, "learner_label": "First arrival"},
        key="probe-enroll",
    )
    enrollment_a = enrolled["result"]["enrollment_id"]
    outline_a = dispatch("course.outline", {"enrollment_id": enrollment_a})
    brief_a = dispatch("parent.brief.get", {"course_id": course_a})
    out["A_course_create"] = {
        "outline_ok": outline_a.get("ok"),
        "outline_objectives": len((outline_a.get("result") or {}).get("objectives") or []),
        "estimate_read_fires": bool((outline_a.get("result") or {}).get("objectives")),
        "parent_brief_get_code": (brief_a.get("error") or {}).get("code"),
        "desk_state_if_it_fired": desk_state(brief_a),
    }

    # B — Parent Studio create: course + enrollment + queued plan job in one call.
    parent = dispatch("parent.brief.create", {"brief": PARENT_BRIEF}, key="probe-parent-create")
    if not parent.get("ok"):
        out["B_parent_brief_create"] = {"ok": False, "error": parent.get("error")}
    else:
        course_b = parent["result"]["course_id"]
        brief_b = dispatch("parent.brief.get", {"course_id": course_b})
        out["B_parent_brief_create"] = {
            "ok": True,
            "parent_brief_get_ok": brief_b.get("ok"),
            "desk_state": desk_state(brief_b),
        }

    print(json.dumps(out, indent=2))
finally:
    os.environ.pop("HERMES_HOME", None)
    shutil.rmtree(home, ignore_errors=True)
