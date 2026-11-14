"""The starting rung is derived from the attempt record (upgrade 18).

The due date used to be "last pass plus the rung the evidence target's ladder names", so a
first-try pass with no help and a pass that needed two tries, a hint and a retry were given the
same next interval. The ladder is a product default, not a measured forgetting curve
(``AUDIT.md`` R9/R10), so the honest fix is a *declared* table: the attempt record decides how
many rungs the pass earned, the learner is told which rule produced the date in their own words,
and no pass is ever scheduled further out than the target's own ladder allows.

Before this change both items report ``interval_days == ladder[0]``. After it the hinted item
keeps the ladder's first rung and the cold first-try item earns the second one.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, mastery_path, review
from tests.kernel_support import KernelCase, numeric_spec


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class ReviewIntervalCase(KernelCase):
    def prepare(self, count: int = 1) -> dict:
        """One course, ``count`` procedure objectives and an approved plan."""
        course_id, plan_id = self.new_course()
        objective_ids = [self.seed_objective(plan_id, numeric_spec("42.7")) for _ in range(count)]
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "objective_ids": objective_ids,
            "revision": revision,
        }

    def open_check(self, lesson: dict, objective_id: str) -> dict:
        revision_value = self.scalar("SELECT revision FROM enrollments WHERE id = ?",
                                     (lesson["enrollment_id"],))
        self.assertIsInstance(revision_value, int)
        revision = int(revision_value)  # type: ignore[arg-type]  # narrowed by assertIsInstance
        opened = self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        return {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": objective_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }

    def add_hint(self, enrollment_id: str, objective_id: str, *, shown: bool = False,
                 created_at: str | None = None) -> None:
        """The durable help event the pane and the chat hook both write before the next answer."""
        kind = "answer_shown" if shown else "hint_request"
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
                " evidence_class, created_at) VALUES (?, ?, ?, NULL, 1, ?, 'hinted', ?)",
                (f"evd_{kind}_{objective_id[-6:]}", enrollment_id, objective_id, kind,
                 created_at or _iso()),
            )

    def answer(self, lesson: dict, objective_id: str, text: str = "42.7") -> dict:
        opened = self.open_check(lesson, objective_id)
        return self.submit(opened, text)["result"]

    def item(self, enrollment_id: str, objective_id: str) -> dict:
        with db.read() as connection:
            item = review.item(connection, enrollment_id, objective_id)
        self.assertIsNotNone(item)
        return item if item is not None else {}


class StartingRungTest(ReviewIntervalCase):
    def test_a_hinted_pass_starts_one_rung_lower_than_a_cold_pass(self) -> None:
        lesson = self.prepare(2)
        hinted_id, cold_id = lesson["objective_ids"]
        ladder = mastery_path.LADDERS["procedure"]

        # Objective 1: the learner takes a hint and then answers. The pass is real, the help is
        # durable, and the classification is `hinted` — never cold.
        self.add_hint(lesson["enrollment_id"], hinted_id)
        hinted = self.answer(lesson, hinted_id)
        self.assertEqual(hinted["verdict"], "pass")
        self.assertEqual(hinted["evidence_class"], "hinted")

        # Objective 2: first try, no help.
        cold = self.answer(lesson, cold_id)
        self.assertEqual(cold["verdict"], "pass")
        self.assertEqual(cold["evidence_class"], "cold")

        hinted_item = self.item(lesson["enrollment_id"], hinted_id)
        cold_item = self.item(lesson["enrollment_id"], cold_id)

        # Before: both were ladder[0]. The hinted pass keeps the ladder's first rung; the pass
        # that needed no help earns one rung more.
        self.assertEqual(hinted_item["step"], 0)
        self.assertEqual(hinted_item["interval_days"], ladder[0])
        self.assertEqual(cold_item["step"], 1)
        self.assertEqual(cold_item["interval_days"], ladder[1])
        self.assertGreater(cold_item["interval_days"], hinted_item["interval_days"])
        # Neither pass may jump to the end of the target's ladder.
        self.assertNotEqual(cold_item["interval_days"], ladder[-1])
        self.assertEqual(cold_item["ladder_days"], list(ladder))

    def test_a_pass_after_a_miss_returns_on_the_short_beat(self) -> None:
        lesson = self.prepare(1)
        objective_id = lesson["objective_ids"][0]
        ladder = mastery_path.LADDERS["procedure"]

        # Miss, then a hinted pass: the record says the pass was not earned first time.
        first = self.answer(lesson, objective_id, "5")
        self.assertEqual(first["verdict"], "not_yet")
        self.backdate(objective_id, days=2)
        self.add_hint(lesson["enrollment_id"], objective_id)
        second = self.answer(lesson, objective_id)
        self.assertEqual(second["verdict"], "pass")
        self.assertEqual(second["evidence_class"], "hinted")

        item = self.item(lesson["enrollment_id"], objective_id)
        self.assertEqual(item["interval_days"], review.MISS_RETURN_DAYS)
        self.assertLess(item["interval_days"], ladder[0])
        self.assertEqual(item["step"], 0)

    def test_a_shown_answer_returns_on_the_short_beat(self) -> None:
        lesson = self.prepare(1)
        objective_id = lesson["objective_ids"][0]
        self.add_hint(lesson["enrollment_id"], objective_id, shown=True)
        result = self.answer(lesson, objective_id)
        self.assertEqual(result["evidence_class"], "answer_shown")

        item = self.item(lesson["enrollment_id"], objective_id)
        self.assertEqual(item["interval_days"], review.MISS_RETURN_DAYS)

    def test_the_reason_is_the_learner_s_words_not_the_pipeline_s(self) -> None:
        lesson = self.prepare(2)
        hinted_id, cold_id = lesson["objective_ids"]
        self.add_hint(lesson["enrollment_id"], hinted_id)
        self.answer(lesson, hinted_id)
        self.answer(lesson, cold_id)

        hinted_item = self.item(lesson["enrollment_id"], hinted_id)
        cold_item = self.item(lesson["enrollment_id"], cold_id)
        self.assertIn("hint", hinted_item["interval_reason"])
        self.assertIn("first try", cold_item["interval_reason"])
        # A learner surface never carries the scheduler's words.
        for item in (hinted_item, cold_item):
            reason = str(item["interval_reason"])
            for pipeline_word in ("cold", "hinted", "answer_shown", "evidence_class",
                                  "objective", "attempt", "ladder", "rung", "step"):
                self.assertNotIn(pipeline_word, reason.lower())

    def test_an_objective_with_no_attempt_record_earns_no_extra_rung(self) -> None:
        """A hand-seeded layer-2 pass has no attempt record; it keeps the ladder's first rung."""
        lesson = self.prepare(1)
        objective_id = lesson["objective_ids"][0]
        ladder = mastery_path.LADDERS["procedure"]
        self.execute(
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
            " evidence_class, created_at) VALUES ('evd_seeded', ?, ?, NULL, 2,"
            " 'independent_evidence', 'cold', ?)",
            (lesson["enrollment_id"], objective_id, _iso(1)),
        )
        self.execute("UPDATE objectives SET state = 'independent_evidence' WHERE id = ?",
                     (objective_id,))
        item = self.item(lesson["enrollment_id"], objective_id)
        self.assertEqual(item["interval_days"], ladder[0])
        self.assertIsNone(item["interval_reason"])

    def backdate(self, objective_id: str, days: float) -> None:
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 1"
            " AND kind = 'attempt'",
            (_iso(days), objective_id),
        )


if __name__ == "__main__":
    unittest.main()
