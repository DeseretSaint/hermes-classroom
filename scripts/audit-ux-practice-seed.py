#!/usr/bin/env python3
"""Seed one real conversation practice into an isolated Desktop capture rig.

This is rig setup, not product code. It drives the backend's own commands - `course.create`,
`plan.approve`, `check.open`, `lesson.begin`, `practice.start` - and the same chat-hook entry point
the tutor uses (`coursebook.turn.pre_turn`) to append learner turns, so the Desktop reads a section,
a session and a transcript the backend really wrote. Nothing is inserted with hand-written SQL and
no fixture file stands in for a route.

    HERMES_HOME=<rig home> python3 scripts/audit-ux-practice-seed.py [--reset]

Writes `audit/ux/practice-seed.json` with every id it created and the transcript it stored.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import api, bindings, db, domain, turn  # noqa: E402
from tests.kernel_support import criteria_with, request  # noqa: E402
from tests.test_conversation_practice import practice_spec  # noqa: E402

OUT = ROOT / "audit" / "ux" / "practice-seed.json"

COURSE_TITLE = "Buy a train ticket (practice)"
OBJECTIVE_TITLE = "Buy one train ticket at the station counter"
TURNS = [
    "One ticket to Kyoto, please.",
    "How much is it?",
    "Thank you. Where is platform four?",
]


def call(method: str, payload: dict | None = None, **kwargs) -> dict:
    response = api.dispatch(request(method, payload, **kwargs))
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {json.dumps(response.get('error'), indent=2)}")
    return response


def find_existing(plan_id: str) -> dict | None:
    """Reuse a previously seeded course instead of stacking a second one in the rig."""
    with db.read() as connection:
        row = connection.execute(
            "SELECT id FROM objectives WHERE plan_id = ? AND title = ? LIMIT 1",
            (plan_id, OBJECTIVE_TITLE),
        ).fetchone()
    return dict(row) if row is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="seed even if this rig already has one")
    args = parser.parse_args()

    home = os.environ.get("HERMES_HOME")
    if not home:
        raise SystemExit("HERMES_HOME must name the capture rig's home")
    db.migrate()

    # A rig seed always creates its own course: reusing an approved plan would have to re-approve
    # it, and this script's job is one unambiguous practice for the capture to point at.
    created = call(
        "course.create",
        {
            "title": COURSE_TITLE,
            "recipe": "committed",
            "goal": "Buy one train ticket at a station counter",
        },
    )["result"]
    course_id, plan_id = created["course_id"], created["plan_id"]
    objective_id = domain.record_objective(
        plan_id,
        title=OBJECTIVE_TITLE,
        evidence_target="production",
        criteria=criteria_with(practice_spec()),
    )
    enrollment = call(
        "enrollment.create", {"course_id": course_id, "learner_label": "Practice rig"}
    )["result"]
    enrollment_id = enrollment["enrollment_id"]
    revision = call(
        "plan.approve",
        {
            "enrollment_id": enrollment_id,
            "plan_id": plan_id,
            "plan_hash": domain.plan_hash(plan_id),
        },
        expected_revision=0,
    )["result"]["revision"]
    opened = call(
        "check.open",
        {"enrollment_id": enrollment_id, "objective_id": objective_id},
        expected_revision=revision,
    )["result"]
    run = call(
        "lesson.begin",
        {"enrollment_id": enrollment_id, "objective_id": objective_id, "mode": "fresh"},
        idempotency_key=f"seed-begin-{enrollment_id[-8:]}",
    )["result"]
    # `check.open` and `lesson.begin` can move the enrollment; the write below fences on the
    # revision the last read reported, never on the one this script started with.
    live_revision = int(opened.get("revision", revision))
    stored_session_id = f"seed-practice-{enrollment_id[-8:]}"
    bindings.bind_session(
        stored_session_id=stored_session_id,
        enrollment_id=enrollment_id,
        objective_id=objective_id,
        lesson_run_id=run["lesson_run_id"],
        profile="default",
    )
    # One teaching segment, written by the same post-turn observer a real lesson uses, so the
    # section page has a document and mounts its check slot (an empty document renders no check).
    with db.read() as connection:
        live = connection.execute(
            "SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)
        ).fetchone()
    turn.record_assistant_snapshot(
        session_id=stored_session_id,
        assistant_response=(
            "At a station counter you ask for one ticket to Kyoto, then ask the price and where "
            "platform four is. Say each line out loud before you start the practice."
        ),
        nonce="seed-teaching-1",
        revision=int(live["revision"]),
    )
    started = call(
        "practice.start",
        {"enrollment_id": enrollment_id, "objective_id": objective_id},
        expected_revision=live_revision,
        idempotency_key=f"seed-start-{enrollment_id[-8:]}",
    )["result"]
    for text in TURNS:
        turn.pre_turn(stored_session_id, text)
    state = call(
        "practice.state", {"enrollment_id": enrollment_id, "objective_id": objective_id}
    )["result"]

    record = {
        "generated_by": "scripts/audit-ux-practice-seed.py",
        "home": home,
        "course_id": course_id,
        "course_title": COURSE_TITLE,
        "plan_id": plan_id,
        "objective_id": objective_id,
        "objective_title": OBJECTIVE_TITLE,
        "enrollment_id": enrollment_id,
        "check_id": opened["check_id"],
        "check_version": opened["check_version"],
        "revision": revision,
        "lesson_run_id": run["lesson_run_id"],
        "stored_session_id": stored_session_id,
        "session_id": started["session_id"],
        "learner_turns_written": len(TURNS),
        "turns_said": TURNS,
        "practice_state_after_seed": {
            "state": state.get("state"),
            "learner_turns": state.get("learner_turns"),
            "remaining": state.get("remaining"),
            "awaiting_tutor": state.get("awaiting_tutor"),
            "transcript": state.get("transcript"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in (
        "course_id", "objective_id", "enrollment_id", "check_id", "session_id",
        "learner_turns_written",
    )}, indent=2))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
