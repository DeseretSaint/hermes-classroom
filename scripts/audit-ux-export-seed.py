#!/usr/bin/env python3
"""Seed the isolated H-121 rig with one exportable authored course (and one blocked course).

Everything visible to a learner is written the way the real product writes it where the real
product has a command: the course and enrollment come from ``course.create`` /
``enrollment.create`` over the live wire, and the plan approval is ``plan.approve``. The only
direct writes are the generation staging rows (``gen_plan_documents``/``gen_plan_sections``/
``gen_lessons``/``checks``), which a live backend only creates by running the lessons job against a
model; no model is available to this rig, so those rows are staged exactly as
``tests/test_course_export`` stages them. The export itself, its hash, its archive and the import are
then driven through the running backend and the Desktop UI, not through this script.

    HERMES_HOME=~/.hermes/coursebook-test-h121/home \
    CB013_BASE=http://127.0.0.1:44319 CB013_TOKEN=cb013-test-token \
      python3 scripts/audit-ux-export-seed.py

Prints one JSON object: the ids and the notebook/observation markers it planted.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44319")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")

HERE = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(HERE))

from coursebook import db, domain, generation  # noqa: E402

NOW = "2026-11-08T08:00:00Z"
GEN_HASH = "sha256:" + "b" * 64
NOTE_MARKER = "H121-PRIVATE-NOTE-should-never-export"
ATTEMPT_MARKER = "H121-PRIVATE-ANSWER-should-never-export"


def wire_version() -> int:
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return int(json.loads(response.read()).get("wire_version") or 0)


def call(method: str, payload: dict, expected_revision: int | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire_version(),
        "method": method,
        "operation_id": f"h121-seed-{method.replace('.', '-')}-{time.time_ns()}",
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


def ok(method: str, payload: dict, **kwargs) -> dict:
    response = call(method, payload, **kwargs)
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {json.dumps(response.get('error'))}")
    return response["result"]


def page_document(title: str) -> dict:
    return {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [
            {
                "kind": "explain",
                "heading": "Why the sear matters",
                "body": "Browning builds the flavour the braise will carry for two hours.",
            },
            {
                "kind": "model",
                "heading": "What good looks like",
                "body": "The ribs are dark brown on every face before they meet the liquid.",
            },
        ],
        "worked_example": {
            "prompt": "The pan is only warm.",
            "steps": ["Wait until the oil shimmers", "Lay the ribs away from you"],
            "answer": "Wait for the shimmer",
        },
        "learner_explanation": "Choose the moment that actually sears the meat.",
        "check": {
            "kind": "observation",
            "stimulus": {
                "prompt": "In one sentence, describe the moment the ribs go into the pan.",
                "format": "short_text",
            },
            "learner_instructions": "Write one sentence.",
            "evidence_target": "production",
            "scaffolds": {},
            "assistance_policy": {},
        },
        "sources": [],
        "media": [],
        "parent_notes": "Ask why a cold pan cannot sear.",
        "supervision_notes": ["Use the back burner"],
    }


def stage_lessons(course_id: str, plan_id: str, objective_ids: list[str]) -> None:
    with db.read() as connection:
        generation.ensure_schema(connection)
    with db.transaction() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
            " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
            " validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
            (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
        )
        for ordinal, objective_id in enumerate(objective_ids, start=1):
            section_id = f"sec_{ordinal}_{plan_id}"
            lesson_id = f"lsn_{ordinal}_{plan_id}"
            check_id = f"chk_{ordinal}_{plan_id}"
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, ?, ?, ?, 'Sear first, then braise.', ?, '[]', '[]')",
                (section_id, plan_id, ordinal, GEN_HASH, f"Section {ordinal}: the sear", f"[{ordinal}]"),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, parent_notes_json, rejection_reasons_json,"
                " validation_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', '{}', '[]', NULL, ?, ?)",
                (
                    lesson_id,
                    plan_id,
                    section_id,
                    GEN_HASH,
                    json.dumps(page_document(f"Section {ordinal}: the sear")),
                    NOW,
                    NOW,
                ),
            )
            connection.execute(
                "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                " rubric_json, reference_json, locale, audit_state, state, created_at)"
                " VALUES (?, ?, 1, 'production', ?, ?, ?, 'en-US', 'passed', 'open', ?)",
                (
                    check_id,
                    objective_id,
                    json.dumps({"prompt": "When do the ribs go into the pan?", "format": "selection"}),
                    json.dumps(
                        {
                            "criteria": [
                                {"criterion": "a", "description": "Browns every face"},
                                {"criterion": "b", "description": "Keeps the heat steady"},
                                {"criterion": "c", "description": "Does not crowd the pan"},
                            ]
                        }
                    ),
                    json.dumps(
                        {
                            "reference_answer": "When the oil shimmers and the pan is hot",
                            "accepted_answers": [],
                            "accepted_alternatives": [],
                        }
                    ),
                    NOW,
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, ?)",
                (lesson_id, check_id, ordinal),
            )


def seed_course(*, title: str, approve: bool) -> dict:
    created = ok(
        "course.create",
        {
            "title": title,
            "recipe": "committed",
            "goal": "Braise short ribs at home without a pressure cooker.",
            "locale": "en-US",
        },
    )
    course_id = created["course_id"]
    plan_id = created["plan_id"]
    objective_ids = []
    for ordinal in (1, 2):
        objective_ids.append(
            domain.record_objective(
                plan_id,
                title=f"Objective {ordinal}: sear and braise",
                evidence_target="production",
                criteria=[
                    {
                        "id": "c1",
                        "description": "graded criterion",
                        "check_spec": {
                            "audit_state": "passed",
                            "stimulus": {"prompt": "Compute the answer."},
                            "reference": {
                                "kind": "numeric",
                                "value": "4",
                                "tolerance": {"abs": "0"},
                            },
                            "rubric": {
                                "construct": "procedure",
                                "pass_rule": "all",
                                "criteria": [{"id": "c1", "description": "Correct value"}],
                            },
                        },
                    }
                ],
            )
        )
    enrollment = ok(
        "enrollment.create", {"course_id": course_id, "learner_label": "H-121 learner"}
    )
    enrollment_id = enrollment["enrollment_id"]
    if approve:
        with db.read() as connection:
            plan_hash = domain.plan_hash(plan_id)
        ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": plan_hash},
            expected_revision=0,
        )
        stage_lessons(course_id, plan_id, objective_ids)
        domain.record_observation(
            enrollment_id,
            objective_ids[0],
            evidence_class="parent_reported",
            note=ATTEMPT_MARKER,
        )
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO notebook_entries (id, enrollment_id, objective_id, lesson_run_id,"
                " kind, excerpt, note, tags_json, source_ref, created_at, updated_at)"
                " VALUES ('nbt_h121', ?, ?, NULL, 'personal_note', ?, ?, '[]', NULL, ?, ?)",
                (enrollment_id, objective_ids[0], NOTE_MARKER, NOTE_MARKER, NOW, NOW),
            )
    read = ok("course.export.read", {"enrollment_id": enrollment_id})
    return {
        "course_id": course_id,
        "plan_id": plan_id,
        "enrollment_id": enrollment_id,
        "objective_ids": objective_ids,
        "export_read": read,
    }


def main() -> int:
    db.migrate()
    approved = seed_course(title="Braising at home, H-121", approve=True)
    blocked = seed_course(title="Unapproved draft, H-121", approve=False)
    print(
        json.dumps(
            {
                "approved": approved,
                "blocked": blocked,
                "markers": {"note": NOTE_MARKER, "answer": ATTEMPT_MARKER},
                "db": str(db.database_path()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
