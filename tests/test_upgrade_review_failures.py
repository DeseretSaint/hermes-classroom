"""A miss and a hinted pass enter the review queue (upgrade 17).

The queue used to be built only from a layer-2 cold pass, so ``needs_review`` after a miss and
``introduced`` after a hinted pass produced no item at all: the objectives that most need retrieval
were the only ones never scheduled. These tests hold the new rule and the boundary it must not
cross — scheduling a return is not evidence, so a hinted pass still writes no layer-2 row.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, review
from tests.kernel_support import KernelCase, numeric_spec


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class ReviewFailureCase(KernelCase):
    def backdate_attempt(self, objective_id: str, days: float) -> None:
        """Age the learner-time record of every committed attempt for this objective."""
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 1"
            " AND kind = 'attempt'",
            (_iso(days), objective_id),
        )

    def add_hint(self, lesson: dict) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
                " evidence_class, created_at) VALUES ('evd_hint', ?, ?, NULL, 1, 'hint_request',"
                " 'hinted', ?)",
                (lesson["enrollment_id"], lesson["objective_id"], _iso()),
            )

    def queue(self, enrollment_id: str, **kwargs) -> dict:
        with db.read() as connection:
            return review.queue(connection, enrollment_id, **kwargs)


class MissSchedulesAShortReturnTest(ReviewFailureCase):
    def test_a_needs_review_objective_is_due_after_a_miss(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        response = self.submit(lesson, "5")
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["verdict"], "not_yet")
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "needs_review")
        # No cold pass exists: before this change the queue had nothing to derive and omitted it.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 0)
        self.backdate_attempt(lesson["objective_id"], days=2)

        queue = self.queue(lesson["enrollment_id"])
        self.assertEqual(queue["total_due"], 1)
        item = queue["items"][0]
        self.assertEqual(item["objective_id"], lesson["objective_id"])
        self.assertEqual(item["state"], "needs_review")
        # The short beat, not the procedure ladder's first rung (3 days).
        self.assertEqual(item["interval_days"], 1)
        self.assertEqual(item["step"], 0)
        self.assertEqual(item["ladder_days"][0], 1)
        self.assertTrue(item["overdue"])

    def test_a_fresh_miss_is_scheduled_without_inflating_the_overdue_count(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        self.submit(lesson, "5")

        queue = self.queue(lesson["enrollment_id"])
        # Scheduled, so the return is real — but not yet overdue, so a struggle is not a backlog.
        self.assertEqual(queue["total_scheduled"], 1)
        self.assertEqual(queue["total_due"], 0)
        self.assertFalse(queue["items"][0]["overdue"])
        self.assertEqual(queue["items"][0]["interval_days"], 1)

    def test_the_single_item_view_matches_the_queue_for_a_miss(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        self.submit(lesson, "5")
        self.backdate_attempt(lesson["objective_id"], days=2)
        with db.read() as connection:
            single = review.item(connection, lesson["enrollment_id"], lesson["objective_id"])
        self.assertIsNotNone(single)
        assert single is not None
        self.assertEqual(single["interval_days"], 1)
        self.assertTrue(single["overdue"])


class HintedPassSchedulesAShorterReturnTest(ReviewFailureCase):
    def test_a_hinted_pass_returns_one_rung_before_a_cold_pass(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        cold = self.submit(lesson, "42.7")
        self.assertEqual(cold["result"]["verdict"], "pass")
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "independent_evidence")
        cold_item = self.queue(lesson["enrollment_id"])["items"][0]
        self.assertEqual(cold_item["interval_days"], 3)  # procedure ladder, first cold rung
        self.backdate_attempt(lesson["objective_id"], days=10)

        # A second check on the same objective, answered after a hint: a pass that is not cold.
        revision_value = self.scalar("SELECT revision FROM enrollments WHERE id = ?",
                                     (lesson["enrollment_id"],))
        self.assertIsInstance(revision_value, int)
        revision = int(revision_value)  # type: ignore[arg-type]  # narrowed by assertIsInstance
        opened = self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=revision,
        )["result"]
        self.add_hint(lesson)
        second = self.submit(
            {"enrollment_id": lesson["enrollment_id"], "check_id": opened["check_id"],
             "check_version": opened["check_version"], "revision": opened["revision"]},
            "42.7", key="key-hinted-return",
        )["result"]
        self.assertEqual(second["verdict"], "pass")
        self.assertEqual(second["evidence_class"], "hinted")
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "independent_evidence")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 1)

        item = self.queue(lesson["enrollment_id"])["items"][0]
        # One rung before the rung a cold pass would have left behind: a cold second pass writes
        # `delayed_retrieval` and advances to step 1 (ladder[1] = 7); the hinted pass does not
        # advance, so the return stays on the gate rung. The clock restarts at the hinted attempt.
        self.assertEqual(item["step"], 0)
        self.assertEqual(item["interval_days"], 3)
        self.assertEqual(item["interval_days"], cold_item["interval_days"])
        self.assertNotEqual(item["interval_days"], 7)
        self.assertEqual(item["ladder_days"], [3, 7, 16, 35])
        self.assertFalse(item["overdue"])
        self.assertEqual(item["last_evidence_at"],
                         self.scalar("SELECT created_at FROM evidence WHERE objective_id = ?"
                                     " AND layer = 1 AND kind = 'attempt'"
                                     " ORDER BY created_at DESC LIMIT 1",
                                     (lesson["objective_id"],)))


class IntroducedObjectiveGetsAColdRecheckTest(ReviewFailureCase):
    def test_an_introduced_objective_is_scheduled_for_a_cold_recheck(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        self.add_hint(lesson)
        result = self.submit(lesson, "42.7")["result"]
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "hinted")
        # Introduced by a hinted pass: access may advance, independence may not be claimed.
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "introduced")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 0)

        queue = self.queue(lesson["enrollment_id"])
        self.assertEqual(queue["total_scheduled"], 1)
        item = queue["items"][0]
        self.assertEqual(item["state"], "introduced")
        self.assertEqual(item["interval_days"], 3)  # the cold re-check is the ladder's first rung
        self.assertFalse(item["overdue"])


if __name__ == "__main__":
    unittest.main()
