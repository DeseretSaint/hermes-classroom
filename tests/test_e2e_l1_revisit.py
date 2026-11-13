"""E2E L1: a passed generated section can be checked again, as a *review*.

Reproduction (docs/ADVERSARIAL-E2E-2026-11-12.md L1): a generated lesson writes plain-string
evidence criteria and stores its real check in the ``checks`` table. ``check.open`` only knew how to
mint a check from a ``check_spec`` object inside ``evidence_criteria_json``, so once the generated
check was closed a revisit raised ``objective_not_checkable`` — and ``progression.challenge_out``
raised the same refusal. Spaced review was impossible for every generated course.

These cases run the real commands against a real migrated database:

* a closed generated check is cloned by ``check.open`` as a revisit: a new revision, the same
  stimulus/reference/rubric, ``revisit: true``;
* ``progression.challenge_out`` reaches the same clone for a generated objective;
* the revisit pass is recorded (an attempt and a layer-1 evidence row) but never moves
  ``objectives.state`` again, never writes a second independent-evidence row and never pays XP;
* ``check.get`` and ``lesson.page`` name the revisit so the lesson page and the desk can label it
  "Review" instead of "Start".
"""

from __future__ import annotations

import json
import unittest

from coursebook import domain

from tests.kernel_support import KernelCase


GENERATED_STIMULUS = {
    "prompt": "What is 2 + 2?",
    "format": "text",
}
GENERATED_REFERENCE = {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}}
GENERATED_RUBRIC = {
    "construct": "recall",
    "pass_rule": "all",
    "criteria": [{"id": "c1", "description": "Correct value"}],
}


class GeneratedRevisitCase(KernelCase):
    """A course whose objective was authored by the generator, not by a hand-written spec."""

    def generated_course(self, *, mode: str | None = None) -> dict:
        """A plan with one generated-shaped objective and a real ``checks`` row.

        The criteria carry no ``check_spec`` object — exactly what a generated lesson writes — and
        the check lives in ``checks`` the way ``generation`` writes it (audit passed, open).
        """
        payload = {"title": "Learn to count", "recipe": "committed", "goal": "Add small numbers"}
        if mode is not None:
            payload["presentation_mode"] = mode
        created = self.ok("course.create", payload)["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        objective_id = domain.record_objective(
            plan_id,
            title="Add two numbers",
            evidence_target="recall",
            criteria=[{"id": "c1", "description": "Adds two single-digit numbers"}],
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        self.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at, revisit)"
            " VALUES ('chk_generated_0001', ?, 1, 'recall', ?, ?, ?, NULL, 'passed', 'open',"
            " '2026-11-01T00:00:00Z', 0)",
            (objective_id, json.dumps(GENERATED_STIMULUS), json.dumps(GENERATED_RUBRIC),
             json.dumps(GENERATED_REFERENCE)),
        )
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "revision": revision,
        }

    def open(self, lesson: dict, *, revision: int | None = None) -> dict:
        current = int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )))
        return self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=current if revision is None else revision,
        )["result"]

    def pass_check(self, lesson: dict, *, answer: str = "4", revision: int | None = None) -> dict:
        current = int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )))
        opened = self.open(lesson, revision=current)
        response = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            answer,
            revision=opened["revision"] if revision is None else revision,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def open_objective_state(self, lesson: dict) -> str:
        return str(self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)))


class CheckOpenRevisitTest(GeneratedRevisitCase):
    def test_a_closed_generated_check_reopens_as_a_revisit(self) -> None:
        lesson = self.generated_course()
        first = self.pass_check(lesson)
        self.assertEqual(first["verdict"], "pass")
        self.assertEqual(self.open_objective_state(lesson), "independent_evidence")
        before = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))

        revisit = self.open(lesson)
        self.assertIs(revisit["revisit"], True)
        self.assertEqual(revisit["check_version"], 2)
        self.assertNotEqual(revisit["check_id"], "chk_generated_0001")
        self.assertEqual(revisit["revision"], int(before) + 1)

        row = self.rows("SELECT * FROM checks WHERE id = ?", (revisit["check_id"],))[0]
        self.assertEqual(row["state"], "open")
        self.assertEqual(int(row["revisit"]), 1)
        self.assertEqual(json.loads(row["stimulus_json"]), GENERATED_STIMULUS)
        self.assertEqual(json.loads(row["reference_json"]), GENERATED_REFERENCE)
        self.assertEqual(json.loads(row["rubric_json"]), GENERATED_RUBRIC)
        # The closed original stays closed and untouched; the revisit is a new revision of it.
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = 'chk_generated_0001'"), "closed"
        )
        # A second open of the same objective returns the same open revisit, not a stack of them.
        again = self.open(lesson)
        self.assertEqual(again["check_id"], revisit["check_id"])
        self.assertIs(again["revisit"], True)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM checks WHERE objective_id = ?",
                                     (lesson["objective_id"],)), 2)

    def test_a_revisit_pass_moves_no_state_and_pays_no_second_xp(self) -> None:
        lesson = self.generated_course(mode="game")
        first = self.pass_check(lesson)
        state_after_first = self.open_objective_state(lesson)
        awarded = self.ok(
            "engagement.award",
            {
                "course_id": lesson["course_id"],
                "enrollment_id": lesson["enrollment_id"],
                "action_kind": "check_submitted",
                "action_id": first["attempt_id"],
            },
        )["result"]
        self.assertIs(awarded["awarded"], True)
        xp_after_first = int(awarded["xp_total"])
        attempts_before = int(self.scalar("SELECT COUNT(*) FROM attempts"))

        revisit = self.open(lesson)
        second = self.pass_check(lesson)
        self.assertEqual(second["verdict"], "pass")
        self.assertEqual(self.open_objective_state(lesson), state_after_first)
        self.assertEqual(self.scalar(
            "SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)
        ), "independent_evidence")
        # A layer-2 independent/delayed row would be a second evidence transition; there is none.
        self.assertEqual(self.scalar(
            "SELECT COUNT(*) FROM evidence WHERE enrollment_id = ? AND objective_id = ? AND layer = 2",
            (lesson["enrollment_id"], lesson["objective_id"]),
        ), 1)
        # The pass is still a real recorded attempt (layer 1), not a silent no-op.
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM attempts")), attempts_before + 1)
        self.assertEqual(self.scalar(
            "SELECT state FROM checks WHERE id = ?", (revisit["check_id"],)
        ), "closed")
        # XP is keyed by attempt id, so the revisit attempt is a *different* action id. It is
        # refused as review rather than paid a second time.
        error = self.err(
            "engagement.award",
            {
                "course_id": lesson["course_id"],
                "enrollment_id": lesson["enrollment_id"],
                "action_kind": "check_submitted",
                "action_id": second["attempt_id"],
            },
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "revisit_pays_no_xp")
        read = self.ok(
            "engagement.read",
            {"course_id": lesson["course_id"], "enrollment_id": lesson["enrollment_id"]},
        )["result"]
        self.assertEqual(int(read["xp_total"]), xp_after_first)

    def test_challenge_out_reaches_a_generated_objective_as_a_revisit(self) -> None:
        lesson = self.generated_course()
        self.pass_check(lesson)
        current = int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )))
        challenge = self.ok(
            "progression.challenge_out",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=current,
        )["result"]
        self.assertIs(challenge["revisit"], True)
        self.assertEqual(challenge["check_version"], 2)
        row = self.rows("SELECT * FROM checks WHERE id = ?", (challenge["check_id"],))[0]
        self.assertEqual(json.loads(row["stimulus_json"]), GENERATED_STIMULUS)
        self.assertEqual(int(row["revisit"]), 1)

    def test_reads_name_the_revisit(self) -> None:
        lesson = self.generated_course()
        self.pass_check(lesson)
        revisit = self.open(lesson)
        served = self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]
        self.assertEqual(served["check_id"], revisit["check_id"])
        self.assertIs(served["revisit"], True)
        page = self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]
        row = next(item for item in page["checks"] if item["check_id"] == revisit["check_id"])
        self.assertIs(row["revisit"], True)
        # The pass that had been recorded is still served as a closed, non-revisit row.
        original = next(item for item in page["checks"] if item["check_id"] == "chk_generated_0001")
        self.assertIs(original["revisit"], False)

    def test_an_objective_with_no_authored_check_is_still_not_checkable(self) -> None:
        course_id, plan_id = self.new_course()
        objective_id = domain.record_objective(
            plan_id, title="No check", evidence_target="recall", criteria=[]
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        error = self.err(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )
        self.assertEqual(error["details"]["reason"], "objective_not_checkable")


if __name__ == "__main__":
    unittest.main()
