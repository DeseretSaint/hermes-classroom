"""Challenge-out is a different case of the target, never the item already answered (upgrade 16).

For a generated objective — the default recipe — ``progression.challenge_out`` used to clone the
newest closed check and call the clone a challenge, so the learner answered the exact stimulus they
had just answered. These cases hold the new rule: the served item differs from every stored check
while ``objective_id`` and the revisit semantics stay the same (a return visit is still review, not
a second independent-evidence event), and where no new case can be proved the command refuses with
``no_varied_challenge_available`` instead of replaying. ``check.open`` still returns the honest
same-item review, which the surface labels "review this item".
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
#: A generated check of a shape whose new case cannot be proved by the backend: a numeric answer
#: whose prompt names no arithmetic case to re-derive.
UNVARIED_STIMULUS = {"prompt": "Name the answer written on the page.", "format": "text"}
UNVARIED_REFERENCE = {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}}


class GeneratedChallengeCase(KernelCase):
    """A course whose objective was authored by the generator, not by a hand-written spec."""

    def generated_course(
        self,
        *,
        stimulus: dict | None = None,
        reference: dict | None = None,
        check_id: str = "chk_generated_0001",
    ) -> dict:
        payload = {"title": "Learn to count", "recipe": "committed", "goal": "Add small numbers"}
        created = self.ok("course.create", payload)["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        objective_id = domain.record_objective(
            plan_id,
            title="Add two numbers",
            evidence_target="recall",
            criteria=[{"id": "c1", "description": "Adds two small numbers"}],
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        self.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at, revisit)"
            " VALUES (?, ?, 1, 'recall', ?, ?, ?, NULL, 'passed', 'open',"
            " '2026-11-01T00:00:00Z', 0)",
            (
                check_id,
                objective_id,
                json.dumps(stimulus or GENERATED_STIMULUS),
                json.dumps(GENERATED_RUBRIC),
                json.dumps(reference or GENERATED_REFERENCE),
            ),
        )
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "revision": revision,
        }

    def current_revision(self, lesson: dict) -> int:
        return int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )))

    def open_check(self, lesson: dict) -> dict:
        return self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=self.current_revision(lesson),
        )["result"]

    def pass_check(self, lesson: dict, answer: str) -> dict:
        opened = self.open_check(lesson)
        response = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            answer,
            revision=opened["revision"],
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def challenge(self, lesson: dict) -> dict:
        return self.ok(
            "progression.challenge_out",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=self.current_revision(lesson),
        )["result"]


class GeneratedChallengeVariantTest(GeneratedChallengeCase):
    def test_a_generated_challenge_never_serves_a_seen_stimulus(self) -> None:
        lesson = self.generated_course()
        first = self.pass_check(lesson, "4")
        self.assertEqual(first["verdict"], "pass")

        challenge = self.challenge(lesson)
        self.assertIs(challenge["revisit"], True)
        self.assertEqual(challenge["check_version"], 2)

        row = self.rows("SELECT * FROM checks WHERE id = ?", (challenge["check_id"],))[0]
        served = json.loads(row["stimulus_json"])
        # Before this change the challenge cloned the answered check byte for byte.
        self.assertNotEqual(served, GENERATED_STIMULUS)
        self.assertNotEqual(served["prompt"], GENERATED_STIMULUS["prompt"])
        # Same objective, same evidence target, same revisit semantics: a return visit, not a
        # second independent-evidence event.
        self.assertEqual(row["objective_id"], lesson["objective_id"])
        self.assertEqual(row["evidence_target"], "recall")
        self.assertEqual(int(row["revisit"]), 1)
        self.assertEqual(row["state"], "open")
        # The new case's answer is the one the backend proved with it, and the grader accepts it.
        reference = json.loads(row["reference_json"])
        self.assertEqual(reference["kind"], "numeric")
        self.assertNotEqual(reference["value"], GENERATED_REFERENCE["value"])
        second = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": challenge["check_id"],
                "check_version": challenge["check_version"],
                "revision": challenge["revision"],
            },
            str(reference["value"]),
            revision=challenge["revision"],
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["result"]["verdict"], "pass")

    def test_a_second_challenge_does_not_re_serve_the_first_challenge(self) -> None:
        lesson = self.generated_course()
        self.pass_check(lesson, "4")
        first = self.challenge(lesson)
        first_stimulus = json.loads(
            self.rows("SELECT stimulus_json FROM checks WHERE id = ?", (first["check_id"],))[0][
                "stimulus_json"
            ]
        )
        self.pass_check_for(lesson, first)
        second = self.challenge(lesson)
        second_stimulus = json.loads(
            self.rows("SELECT stimulus_json FROM checks WHERE id = ?", (second["check_id"],))[0][
                "stimulus_json"
            ]
        )
        self.assertNotEqual(second_stimulus, first_stimulus)
        stored = [
            json.loads(row["stimulus_json"])
            for row in self.rows(
                "SELECT stimulus_json FROM checks WHERE objective_id = ? AND id != ?",
                (lesson["objective_id"], second["check_id"]),
            )
        ]
        self.assertNotIn(second_stimulus, stored)

    def pass_check_for(self, lesson: dict, opened: dict) -> dict:
        response = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            "6",
            revision=opened["revision"],
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def test_an_unprovable_variant_refuses_instead_of_replaying(self) -> None:
        lesson = self.generated_course(
            stimulus=UNVARIED_STIMULUS, reference=UNVARIED_REFERENCE
        )
        first = self.pass_check(lesson, "4")
        self.assertEqual(first["verdict"], "pass")
        before = self.current_revision(lesson)

        error = self.err(
            "progression.challenge_out",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=before,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "no_varied_challenge_available")
        self.assertEqual(error["details"]["objective_id"], lesson["objective_id"])
        # Nothing was written and the revision did not move: the refusal is not a half-command.
        self.assertEqual(
            int(self.scalar(
                "SELECT COUNT(*) FROM checks WHERE objective_id = ?", (lesson["objective_id"],)
            )),
            1,
        )
        self.assertEqual(self.current_revision(lesson), before)
        # The learner is not stranded: the honest same-item return still exists as a review.
        review = self.check_open_revisit(lesson, before)
        self.assertIs(review["revisit"], True)

    def check_open_revisit(self, lesson: dict, revision: int) -> dict:
        return self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=revision,
        )["result"]


if __name__ == "__main__":
    unittest.main()
