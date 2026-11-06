"""Probe: does a *real* generated parent course survive parent.export?

Runs the shipped pipeline end to end in a throwaway HERMES_HOME:
  parent.brief.create -> plan job (plan_parent fixture) -> plan.approve
  -> lessons job (observation lesson, ONE rubric criterion, as the shipped
     lesson fixtures and lesson instructions produce) -> parent.final.approve
  -> parent.export

Mode "shipped" uses plan_parent.json unchanged (2 sections cover 4 objectives).
Mode "one_to_one" rewrites that plan in memory so each section covers exactly
one objective, isolating the rubric-minima question from section cardinality.

Nothing is mocked except the two LLM seams (FakeLLM), the same offline seam
tests/test_generation.py uses. Prints one JSON object.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("CB_REPO") or str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, REPO)

home = tempfile.mkdtemp(prefix="cb-probe-pack-policy-")
os.environ["HERMES_HOME"] = home

from coursebook import api, db, domain, executor, parent_authoring as authoring  # noqa: E402
from tests.kernel_support import request  # noqa: E402
from tests.test_generation import (  # noqa: E402
    FakeLLM,
    FakeSearch,
    plan_from_fixture,
    response,
    validation_from_fixture,
)
from tests.test_parent_studio import PARENT_BRIEF  # noqa: E402

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
MODE = sys.argv[1] if len(sys.argv) > 1 else "shipped"


def call(method, payload=None, **kwargs):
    return api.dispatch(request(method, payload, **kwargs))


def ok(method, payload=None, **kwargs):
    result = call(method, payload, **kwargs)
    if not result["ok"]:
        raise SystemExit(json.dumps({"stage": method, "error": result["error"]}, indent=1))
    return result["result"]


def plan_for_mode():
    # plan_from_fixture returns an LLMResponse; take its parsed document.
    document = plan_from_fixture("plan_parent")(type("R", (), {"input_text": "{}"})()).parsed
    if MODE == "shipped":
        return document
    keep = {1, 2, 3, 4}
    doc = dict(document)
    doc["objectives"] = [item for item in document["objectives"] if item["ordinal"] in keep]
    titles = {
        1: ("Warm things at home", "Parent names warm objects the child can see, one at a time."),
        2: ("Cold things at home", "Parent names cold objects the child can see, one at a time."),
        3: ("Why the kettle is a grown-up job", "Parent explains the kettle rule and the child says it back."),
        4: ("Explain one example", "The child produces one sentence about a warm or cold thing."),
    }
    doc["sections"] = [
        {
            "ordinal": ordinal,
            "title": titles[ordinal][0],
            "lesson_intent": titles[ordinal][1],
            "objective_refs": [ordinal],
            "context_needs": ["kitchen tour"],
            "source_ids": [],
        }
        for ordinal in sorted(keep)
    ]
    doc["check_plan"] = [item for item in document["check_plan"] if item["objective_ref"] in keep]
    return doc


def static_llm(document):
    def build(_request):
        return response(document, model="fake-plan-author")

    return build


def lesson_builder(rubric_criteria: int):
    """A parent observation lesson in the shape the shipped author prompt produces."""

    def build(request_obj):
        payload = json.loads(request_obj.input_text)
        section = payload.get("section") or {}
        objective = payload.get("objective") or {}
        criteria = [
            {
                "criterion": f"observable-{index + 1}",
                "weight": 1.0,
                "description": f"Observable criterion {index + 1}: the child performs the described step.",
            }
            for index in range(rubric_criteria)
        ]
        lesson = {
            "section_title": section.get("title") or "Kitchen science",
            "segments": [
                {
                    "kind": "model",
                    "heading": "Name one of each",
                    "body": "Point at the kettle: it holds hot water. Point at the fridge: it is cold inside.",
                },
                {
                    "kind": "guided",
                    "heading": "Sort the cards",
                    "body": "Put each card under the warm or cold heading and say the word out loud.",
                },
            ],
            "worked_example": {
                "prompt": "Which card belongs under warm?",
                "steps": ["Look at the picture", "Say the object name", "Choose warm"],
                "answer": "The pot card",
            },
            "learner_explanation": "You will name warm and cold things, then sort the picture cards together.",
            "check": {
                "kind": "observation",
                "stimulus": {
                    "prompt": "Which card belongs under warm?",
                    "format": "selection",
                    "choices": ["kettle card", "fridge card"],
                },
                "learner_instructions": "Watch the child choose one card.",
                "evidence_target": objective.get("evidence_target") or "recall",
                "accepted_answers": ["kettle card"],
                "rubric": criteria,
                "reference_answer": "kettle card",
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "hinted"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            },
            "parent_notes": "Point at each object before asking.",
            "supervision_notes": ["An adult stays within arm's reach for the whole activity"],
            "sources": [],
            "media": [],
        }
        return response(lesson, model="fake-parent-author")

    return build


def main():
    db.migrate()
    created = ok("parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="probe-brief")
    course_id = created["course_id"]
    enrollment_id = created["enrollment_id"]

    plan_llm = FakeLLM(
        {
            "coursebook.plan.generate": static_llm(plan_for_mode()),
            "coursebook.plan.validate": validation_from_fixture(),
        }
    )
    executor.pump_once(llm=plan_llm, search=FakeSearch(), now=NOW)
    job_id = ok("parent.brief.get", {"course_id": course_id})["plan_job"]["job_id"]
    job = ok("jobs.get", {"job_id": job_id})["job"]
    if "plan_id" not in (job.get("checkpoint") or {}):
        raise SystemExit(json.dumps({"job": job}, indent=1))
    plan_id = job["checkpoint"]["plan_id"]

    ok(
        "plan.approve",
        {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
        expected_revision=0,
    )

    lesson_job = ok(
        "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}}
    )["job_id"]
    executor.pump_once(
        llm=FakeLLM(
            {
                "coursebook.lesson.generate": lesson_builder(1),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        ),
        search=FakeSearch(),
        now=NOW,
    )
    lesson_view = ok("jobs.get", {"job_id": lesson_job})["job"]
    lesson_state = lesson_view["state"]
    if lesson_state != "completed":
        raise SystemExit(json.dumps({"lesson_job": lesson_view}, indent=1))

    with db.read() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT l.state AS lesson_state, c.rubric_json FROM gen_lessons l"
                " LEFT JOIN gen_lesson_checks g ON g.lesson_id = l.id"
                " LEFT JOIN checks c ON c.id = g.check_id ORDER BY l.created_at"
            )
        ]
        objective_count = connection.execute(
            "SELECT COUNT(*) FROM objectives WHERE plan_id = ?", (plan_id,)
        ).fetchone()[0]
    rubric_counts = [
        len((json.loads(row["rubric_json"] or "{}").get("criteria") or [])) for row in rows
    ]

    blueprint = ok("parent.blueprint.read", {"course_id": course_id})
    with db.read() as connection:
        revision = int(
            connection.execute(
                "SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)
            ).fetchone()[0]
        )
    approval = call(
        "parent.final.approve",
        {
            "enrollment_id": enrollment_id,
            "plan_id": plan_id,
            "plan_hash": blueprint["plan"]["plan_hash"],
            "content_hash": blueprint["content_hash"],
        },
        expected_revision=revision,
        idempotency_key="probe-final",
    )

    export = call("parent.export", {"enrollment_id": enrollment_id}, idempotency_key="probe-export")

    composed_summary = []
    with db.read() as connection:
        course = connection.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        plan = connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        composed = authoring.sections(connection, course, plan)
        for section in composed:
            check = section.get("check")
            rubric = authoring._load(check["rubric_json"], {}) if check is not None else {}
            objective = section.get("objective")
            criteria = authoring._load(objective["evidence_criteria_json"], []) if objective is not None else []
            notes = (section.get("notes") or {}).get("supervision_notes") or []
            composed_summary.append(
                {
                    "section": section["title"],
                    "objective": section["objective_id"],
                    "has_page": section.get("page") is not None,
                    "check_rubric": len((rubric or {}).get("criteria") or []),
                    "plan_evidence_criteria": len(criteria),
                    "supervision_notes": len(notes),
                    "composed_rubric": (
                        len(
                            authoring._check_rubric(
                                check,
                                objective,
                                section["page"],
                                section,
                                section.get("notes") or {},
                            )
                        )
                        if check is not None
                        else 0
                    ),
                }
            )

    if export["ok"]:
        result = export["result"]
        export_payload = {
            "ok": True,
            "roles": sorted({item["role"] for item in result["files"]}),
            "files": [item["name"] for item in result["files"]],
            "content_hash_matches_approval": result["content_hash"] == blueprint["content_hash"],
        }
    else:
        error = export["error"]
        details = error.get("details") or {}
        export_payload = {
            "ok": False,
            "code": error.get("code"),
            "reason": details.get("reason"),
            "problems": details.get("problems"),
            "message": error.get("message"),
        }

    print(
        json.dumps(
            {
                "mode": MODE,
                "objectives_in_plan": objective_count,
                "lesson_job_state": lesson_state,
                "lesson_states": [row["lesson_state"] for row in rows],
                "stored_rubric_criteria": rubric_counts,
                "blueprint_export": blueprint["export"],
                "final_approval_ok": approval["ok"],
                "final_approval_error": None if approval["ok"] else approval["error"],
                "composed": composed_summary,
                "export": export_payload,
            },
            indent=1,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(home, ignore_errors=True)
