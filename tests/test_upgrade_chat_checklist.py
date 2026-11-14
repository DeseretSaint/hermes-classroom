"""Upgrade 20: a typed chat answer to a checklist check reaches the confirmation lane.

Measured defect at HEAD (``docs/UPGRADES-50-2026-11-14.md`` §20): ``turn.pre_turn`` submitted
every chat answer as ``{"kind": "text"}``. A verification checklist stores ``rubric_only``, the
confirmation lane only accepts a ``selection``, and this build configures no open-lane grader, so
a typed answer fell to the open lane, failed closed to ``needs_retry``, and told the learner about
a grading outage on every retry while nothing advanced.

The fix (``docs/CHAT-CHECK-GATE.md``) makes the chat lane check-shaped:

* a verification checklist is collected as **numbered steps** and submitted as a ``selection``
  (membership only — no model reads the prose, and an unnumbered sentence is refused, never
  ticked);
* a ``rubric_only`` check that is not a checklist is refused with a readable sentence before
  anything is submitted, instead of looping on ``needs_retry``.

These cases run the real gate: real dispatcher, real migrated database, no provider.
"""

from __future__ import annotations

import unittest

from coursebook import grading, turn

from tests.kernel_support import KernelCase

_STORED = "stored-lesson-checklist"


def verification_spec() -> dict:
    """A three-step verification checklist: ``rubric_only`` reference over declared items."""
    return {
        "audit_state": "passed",
        "stimulus": {
            "prompt": "Tick each step only after you have done it with the manual open.",
            "format": "verification",
            "items": [
                {"id": "item_1", "label": "Pad model printed in the manual written down"},
                {"id": "item_2", "label": "Worn pad removed with the named fastener"},
                {"id": "item_3", "label": "Second person confirmed a firm lever and a free wheel"},
            ],
        },
        "reference": {"kind": "rubric_only"},
        "rubric": {
            "construct": "procedure",
            "pass_rule": "all",
            "criteria": [{"id": "c1", "description": "Every step confirmed"}],
        },
    }


def open_response_spec() -> dict:
    """A ``rubric_only`` check that is *not* a checklist: only the unconfigured aux lane grades it."""
    return {
        "audit_state": "passed",
        "stimulus": {"prompt": "Write a short procedure for seating the pad."},
        "reference": {"kind": "rubric_only"},
        "rubric": {
            "construct": "production",
            "pass_rule": "all",
            "criteria": [{"id": "c1", "description": "Procedure is workable"}],
        },
    }


class ChatChecklistCase(KernelCase):
    """A prepared lesson bound to one stored chat id, as the host hook sees it."""

    def prepare_bound(self, spec: dict) -> dict:
        lesson = self.prepare_lesson(spec)
        run_id = "run_chat_checklist"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00', NULL)",
            (run_id, lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at,"
            " lesson_run_id, objective_id) VALUES ('bnd_chat_checklist', ?, 'cinder', 'conn-1', 'rt-1',"
            " ?, 'cwd-fp', NULL, 'active', 0, '2026-01-01T00:00:00+00:00', ?, ?)",
            (lesson["enrollment_id"], _STORED, run_id, lesson["objective_id"]),
        )
        lesson["run_id"] = run_id
        return lesson

    def attempts(self, check_id: str) -> list[dict]:
        return self.rows("SELECT * FROM attempts WHERE check_id = ? ORDER BY rowid", (check_id,))

    def revision_of(self, enrollment_id: str) -> int:
        return int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)))

    def check_state(self, check_id: str) -> str:
        return str(self.scalar("SELECT state FROM checks WHERE id = ?", (check_id,)))


class ChatAnswerToVerificationCheckTest(ChatChecklistCase):
    """The acceptance case: numbered steps produce a selection, a verdict, and no ``needs_retry``."""

    def test_a_chat_answer_to_a_verification_check_reaches_the_confirmation_lane(self) -> None:
        lesson = self.prepare_bound(verification_spec())
        before_revision = self.revision_of(lesson["enrollment_id"])

        outcome = turn.pre_turn(_STORED, "I did steps 1, 2 and 3.")

        self.assertNotEqual(outcome.verdict, "needs_retry")
        self.assertEqual(outcome.verdict, "pass")
        self.assertIsNotNone(outcome.hook, outcome)
        self.assertIn("context", outcome.hook)
        self.assertIn("correct", str(outcome.hook["context"]))
        self.assertNotIn("grading outage", str(outcome.hook.get("message") or ""))

        rows = self.attempts(lesson["check_id"])
        self.assertEqual(len(rows), 1, rows)
        # The chat lane collected a selection, not a text answer (the HEAD defect).
        self.assertEqual(rows[0]["answer_kind"], "selection")
        self.assertIn("item_1", str(rows[0]["answer_json"]))
        self.assertIn("item_3", str(rows[0]["answer_json"]))
        self.assertEqual(rows[0]["verdict"], "pass")
        self.assertEqual(rows[0]["evidence_class"], "self_reported")
        self.assertEqual(self.check_state(lesson["check_id"]), "closed")
        self.assertEqual(self.revision_of(lesson["enrollment_id"]), before_revision + 1)

    def test_a_subset_of_the_steps_is_a_partial_confirmation_not_a_needs_retry(self) -> None:
        lesson = self.prepare_bound(verification_spec())

        outcome = turn.pre_turn(_STORED, "1-2")

        self.assertEqual(outcome.verdict, "partial")
        rows = self.attempts(lesson["check_id"])
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["answer_kind"], "selection")
        self.assertIn("item_1", str(rows[0]["answer_json"]))
        self.assertNotIn("item_3", str(rows[0]["answer_json"]))

    def test_unnumbered_prose_is_refused_before_any_attempt(self) -> None:
        """The adversarial note: "all of them" must not be read as a tick-list."""
        lesson = self.prepare_bound(verification_spec())
        before_revision = self.revision_of(lesson["enrollment_id"])

        outcome = turn.pre_turn(_STORED, "all done, I did all of them")

        self.assertEqual(outcome.hook.get("action"), "block")
        message = str(outcome.hook["message"])
        self.assertIn("by number", message)
        self.assertIn("1. Pad model printed in the manual written down", message)
        self.assertNotIn("grading outage", message)
        self.assertNotIn("needs_retry", message)
        self.assertEqual(self.attempts(lesson["check_id"]), [])
        self.assertEqual(self.revision_of(lesson["enrollment_id"]), before_revision)
        self.assertEqual(self.check_state(lesson["check_id"]), "open")

    def test_the_numbered_steps_are_the_declared_item_ids_in_order(self) -> None:
        items = verification_spec()["stimulus"]["items"]
        self.assertEqual(grading.parse_confirmation_numbers("3, 1", items), ["item_1", "item_3"])
        self.assertEqual(grading.parse_confirmation_numbers("one through three", items),
                         ["item_1", "item_2", "item_3"])
        # Out-of-range and non-number numbers never become a tick.
        self.assertEqual(grading.parse_confirmation_numbers("4", items), [])
        self.assertEqual(grading.parse_confirmation_numbers("all of them", items), [])


class UncollectableCheckIsRefusedTest(ChatChecklistCase):
    """A ``rubric_only`` check this build cannot grade is refused, not looped on ``needs_retry``."""

    def test_a_rubric_only_open_response_is_refused_before_submit(self) -> None:
        lesson = self.prepare_bound(open_response_spec())
        before_revision = self.revision_of(lesson["enrollment_id"])

        outcome = turn.pre_turn(_STORED, "Seat the pad square, then tighten to the manual's torque.")

        self.assertEqual(outcome.verdict, None)
        self.assertEqual(outcome.hook.get("action"), "block")
        message = str(outcome.hook["message"])
        self.assertEqual(message, grading.CHAT_CHECK_UNCOLLECTABLE)
        self.assertNotIn("grading outage", message)
        # Nothing was submitted: no attempt row, no revision, the check is still open.
        self.assertEqual(self.attempts(lesson["check_id"]), [])
        self.assertEqual(self.revision_of(lesson["enrollment_id"]), before_revision)
        self.assertEqual(self.check_state(lesson["check_id"]), "open")

    def test_the_chat_lane_still_collects_a_closed_form_check(self) -> None:
        lesson = self.prepare_bound(
            {
                "audit_state": "passed",
                "stimulus": {"prompt": "Compute the answer."},
                "reference": {"kind": "numeric", "value": "42.7", "tolerance": {"abs": "0"}},
                "rubric": {
                    "construct": "procedure",
                    "pass_rule": "all",
                    "criteria": [{"id": "c1", "description": "Correct value"}],
                },
            }
        )

        outcome = turn.pre_turn(_STORED, "42.7")

        self.assertEqual(outcome.verdict, "pass")
        rows = self.attempts(lesson["check_id"])
        self.assertEqual(rows[0]["answer_kind"], "text")

    def test_a_checklist_is_collectable_and_an_uncolllectable_check_is_not(self) -> None:
        checklist = verification_spec()
        self.assertIsNone(
            grading.chat_collection_refusal(checklist["reference"], checklist["stimulus"])
        )
        open_response = open_response_spec()
        self.assertEqual(
            grading.chat_collection_refusal(open_response["reference"], open_response["stimulus"]),
            grading.CHAT_CHECK_UNCOLLECTABLE,
        )

    def test_a_parent_recipe_checklist_is_refused_in_chat(self) -> None:
        """A parent enrollment records observations, never a child's numbered ticks."""
        lesson = self.prepare_lesson(verification_spec(), recipe="parent")
        run_id = "run_chat_checklist_parent"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00', NULL)",
            (run_id, lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at,"
            " lesson_run_id, objective_id) VALUES ('bnd_parent_checklist', ?, 'cinder', 'conn-1',"
            " 'rt-1', ?, 'cwd-fp', NULL, 'active', 0, '2026-01-01T00:00:00+00:00', ?, ?)",
            (lesson["enrollment_id"], _STORED, run_id, lesson["objective_id"]),
        )

        outcome = turn.pre_turn(_STORED, "1, 2, 3")

        self.assertEqual(outcome.hook.get("action"), "block")
        self.assertEqual(outcome.hook["message"], grading.CHAT_CHECK_PARENT_REPORTED)
        self.assertEqual(self.attempts(lesson["check_id"]), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
