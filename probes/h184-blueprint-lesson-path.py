#!/usr/bin/env python3
"""H-184 evidence probe — the Desktop's lessons payload reaches a served lesson page.

Reproduces the reported defect path end to end against a throwaway profile database:

1. create a course from a goal (the same payload ``courseCreatePayload`` sends),
2. let the real plan job run through the executor pump and read the stored plan state,
3. approve the plan with the kernel digest ``plan.approve`` fences,
4. post **exactly** what ``generateLessons`` posts — ``{stage:'lessons', plan_id,
   enrollment_id}`` with no ``unit_ordinal`` — and pump it,
5. print the stored plan state, the chosen ``unit_ordinal``, and one authored ``lesson.page``.

Everything is offline: the deterministic fixture model stands in for the provider, and the
scratch home is deleted at exit. This is evidence capture; the assertions live in
``tests/test_learner_plan_flow.py``.

    python3 probes/h184-blueprint-lesson-path.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOAL = "Order coffee and ask for the bill in Kyoto, politely."


def main() -> int:
    home = tempfile.mkdtemp(prefix="cb-h184-")
    os.environ["HERMES_HOME"] = home
    try:
        return _run()
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _dispatch(method, payload, *, expected_revision=None, idempotency_key=None):
    from coursebook import api

    body = {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"op-h184-{method.replace('.', '-')}-{os.urandom(4).hex()}",
        "payload": payload,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    response = api.dispatch(body)
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {json.dumps(response.get('error'))}")
    return response["result"]


def _run() -> int:
    from coursebook import db, domain, executor, generation
    from tests.blueprint_support import (
        blueprint_plan,
        response as blueprint_response,
        unit_sections_document,
        validation_pass,
    )
    from tests.test_generation import (
        FakeLLM,
        FakeSearch,
        NOW,
        lesson_from_request,
        validation_from_fixture,
    )

    db.migrate()

    plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, recipe="committed")
    course = _dispatch(
        "course.create",
        {
            "title": "Coffee in Kyoto",
            "recipe": "committed",
            "goal": GOAL,
            "dials": {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"},
            "locale": "ja-JP",
            "level": "L0",
            "subject_domain": "language",
            "scope": "short",
        },
        idempotency_key="h184-create",
    )
    enrollment = _dispatch(
        "enrollment.create",
        {"course_id": course["course_id"], "learner_label": "Coffee in Kyoto"},
        idempotency_key="h184-enroll",
    )
    plan_brief = {
        "stage": "plan",
        "course_id": course["course_id"],
        "enrollment_id": enrollment["enrollment_id"],
        "goal": GOAL,
        "recipe": "committed",
        "dials": {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"},
        "locale": "ja-JP",
        "level": "L0",
        "subject_domain": "language",
        "scope": "short",
    }
    plan_job = _dispatch(
        "jobs.create", {"kind": "plan", "brief": plan_brief}, idempotency_key="h184-plan"
    )
    executor.pump_once(
        llm=FakeLLM(
            {
                "coursebook.plan.generate": blueprint_response(plan),
                "coursebook.plan.validate": blueprint_response(
                    validation_pass(), model="fake-independent-validator"
                ),
            }
        ),
        search=FakeSearch(),
        now=NOW,
    )
    plan_run = _dispatch("jobs.get", {"job_id": plan_job["job_id"]})["job"]
    plan_id = plan_run["checkpoint"]["plan_id"]

    book = _dispatch("parent.blueprint.read", {"course_id": course["course_id"]})
    state_before = _dispatch("parent.blueprint.read", {"course_id": course["course_id"]})["plan"]
    _dispatch(
        "plan.approve",
        {
            "enrollment_id": enrollment["enrollment_id"],
            "plan_id": plan_id,
            "plan_hash": book["plan"]["plan_hash"],
        },
        expected_revision=0,
        idempotency_key="h184-approve",
    )

    # Exactly `generateLessons` in desktop/plugin.js: no unit_ordinal anywhere.
    desktop_payload = {
        "stage": "lessons",
        "plan_id": plan_id,
        "enrollment_id": enrollment["enrollment_id"],
    }
    lessons_job = _dispatch(
        "jobs.create",
        {"kind": "plan", "brief": desktop_payload},
        idempotency_key=f"cb-lessons-{plan_id}",
    )

    unit = plan["units"][0]
    objectives = [item for item in plan["objectives"] if int(item["unit_ref"]) == 1]
    lesson_llm = FakeLLM(
        {
            "coursebook.unit_sections.generate": blueprint_response(
                unit_sections_document(unit=unit, objectives=objectives)
            ),
            "coursebook.unit_sections.validate": blueprint_response(
                validation_pass(), model="fake-independent-validator"
            ),
            "coursebook.lesson.generate": lesson_from_request(),
            "coursebook.lesson.validate": validation_from_fixture("validation_pass"),
        }
    )
    executor.pump_once(llm=lesson_llm, search=FakeSearch(), now=NOW)

    run = _dispatch("jobs.get", {"job_id": lessons_job["job_id"]})["job"]
    plan_state = _dispatch("parent.blueprint.read", {"course_id": course["course_id"]})["plan"]
    unit_state = None
    with db.read() as connection:
        unit_state = generation.unit_authoring_state(connection, plan_id)
        row = connection.execute(
            "SELECT l.id, l.state, l.page_json FROM gen_lessons l"
            " JOIN gen_plan_sections s ON s.id = l.section_id"
            " WHERE s.plan_id = ? ORDER BY s.ordinal LIMIT 1",
            (plan_id,),
        ).fetchone()
    page = json.loads(str(row["page_json"])) if row is not None else None

    print("=== exact Desktop payload (`generateLessons`) ===")
    print(json.dumps(desktop_payload, indent=2))
    print("\n=== stored plan state before the lessons job ===")
    print(
        json.dumps(
            {
                "plan_id": state_before["plan_id"],
                "state": state_before["state"],
                "plan_hash": state_before["plan_hash"],
            },
            indent=2,
        )
    )
    print("\n=== plan state after the lessons job ===")
    print(json.dumps({"plan_id": plan_state["plan_id"], "state": plan_state["state"], "plan_hash": plan_state["plan_hash"]}, indent=2))
    print("\n=== lessons job ===")
    print(json.dumps({"job_id": run["job_id"], "state": run["state"], "checkpoint": run["checkpoint"]}, indent=2))
    print("\n=== chosen unit_ordinal ===")
    print(json.dumps({"chosen": run["checkpoint"].get("unit_ordinal"), "resolved_next": unit_state}, indent=2))
    print("\n=== authored lesson.page (first lesson) ===")
    print(
        json.dumps(
            {
                "lesson_id": row["id"] if row is not None else None,
                "state": row["state"] if row is not None else None,
                "section_title": page.get("section_title") if page else None,
                "segments": len(page.get("segments") or []) if page else 0,
                "page_bytes": len(json.dumps(page)) if page else 0,
            },
            indent=2,
        )
    )
    ok = (
        run["state"] == "completed"
        and run["checkpoint"].get("unit_ordinal") == 1
        and run["checkpoint"].get("lessons") == 3
        and page is not None
        and bool(page.get("segments"))
    )
    print(f"\nH-184 path reaches an authored page: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
