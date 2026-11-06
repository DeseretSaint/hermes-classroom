"""Review queue scheduling and evidence-layer queries against a real database."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, domain, evidence, review
from tests.kernel_support import KernelCase, criteria_with, numeric_spec


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class ReviewCase(KernelCase):
    def prepare_multi(self, count: int = 3) -> dict:
        course_id, plan_id = self.new_course()
        objective_ids = [
            self.seed_objective(plan_id, numeric_spec("42.7")) for _ in range(count)
        ]
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id, "plan_id": plan_id, "enrollment_id": enrollment_id,
            "objective_ids": objective_ids, "revision": revision,
        }

    def pass_objective(self, lesson: dict, objective_id: str, answer: str = "42.7") -> dict:
        revision = int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)))
        opened = self.ok(
            "check.open", {"enrollment_id": lesson["enrollment_id"], "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        response = self.submit(
            {"enrollment_id": lesson["enrollment_id"], "check_id": opened["check_id"],
             "check_version": opened["check_version"], "revision": opened["revision"]},
            answer,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def backdate(self, objective_id: str, days: float = 10) -> None:
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 2",
            (_iso(days), objective_id),
        )


class ReviewQueueTest(ReviewCase):
    def test_a_cold_pass_schedules_a_review_and_overdue_is_reported(self) -> None:
        lesson = self.prepare_multi(1)
        self.pass_objective(lesson, lesson["objective_ids"][0])
        self.backdate(lesson["objective_ids"][0], days=10)
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"])
        self.assertEqual(queue["total_due"], 1)
        item = queue["items"][0]
        self.assertTrue(item["overdue"])
        self.assertEqual(item["interval_days"], 3)  # procedure ladder, first step
        self.assertEqual(item["evidence_target"], "procedure")

    def test_an_upcoming_review_is_not_overdue(self) -> None:
        lesson = self.prepare_multi(1)
        self.pass_objective(lesson, lesson["objective_ids"][0])
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"])
        self.assertEqual(queue["total_due"], 0)
        self.assertEqual(queue["total_scheduled"], 1)
        self.assertFalse(queue["items"][0]["overdue"])

    def test_cap_bounds_the_items_but_never_the_counts(self) -> None:
        lesson = self.prepare_multi(3)
        for objective_id in lesson["objective_ids"]:
            self.pass_objective(lesson, objective_id)
            self.backdate(objective_id, days=10)
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"], cap=2)
        self.assertEqual(len(queue["items"]), 2)
        self.assertEqual(queue["total_due"], 3)
        self.assertEqual(queue["cap"], 2)

    def test_snooze_restarts_the_interval_from_now(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        with db.transaction() as connection:
            review.apply_action(connection, enrollment_id=lesson["enrollment_id"],
                                objective_id=objective_id, action="snooze")
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"])
        self.assertEqual(queue["total_due"], 0)
        self.assertFalse(queue["items"][0]["overdue"])

    def test_stretch_advances_the_ladder_step(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        with db.transaction() as connection:
            review.apply_action(connection, enrollment_id=lesson["enrollment_id"],
                                objective_id=objective_id, action="stretch")
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"])
        self.assertEqual(queue["items"][0]["interval_days"], 7)  # second step of the procedure ladder
        self.assertEqual(queue["items"][0]["step"], 1)

    def test_drop_removes_the_item_and_resume_puts_it_back(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        with db.transaction() as connection:
            review.apply_action(connection, enrollment_id=lesson["enrollment_id"],
                                objective_id=objective_id, action="drop")
        with db.read() as connection:
            self.assertEqual(review.queue(connection, lesson["enrollment_id"])["total_due"], 0)
        with db.transaction() as connection:
            review.apply_action(connection, enrollment_id=lesson["enrollment_id"],
                                objective_id=objective_id, action="resume")
        with db.read() as connection:
            self.assertEqual(review.queue(connection, lesson["enrollment_id"])["total_due"], 1)

    def test_refresh_due_marks_the_contracted_state_once(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        with db.transaction() as connection:
            first = review.refresh_due(connection, lesson["enrollment_id"])
            second = review.refresh_due(connection, lesson["enrollment_id"])
        self.assertEqual(first["count"], 1)
        self.assertEqual(second["count"], 0)  # idempotent: needs_review/review_due are not re-marked
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "review_due")

    def test_the_library_surfaces_the_due_review_after_a_tick(self) -> None:
        lesson = self.prepare_multi(1)
        self.pass_objective(lesson, lesson["objective_ids"][0])
        self.backdate(lesson["objective_ids"][0], days=10)
        listed = self.ok("library.list", {"filter": "review_due"})["result"]
        self.assertEqual(listed["items"][0]["evidence_summary"]["review_due"], 1)
        self.assertEqual(listed["items"][0]["next_step"]["kind"], "resolve_review_due")

    def test_a_cold_pass_on_a_due_review_is_delayed_evidence(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective_id,))
        result = self.pass_objective(lesson, objective_id)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
                         "delayed_evidence")
        self.assertEqual(
            self.scalar("SELECT kind FROM evidence WHERE layer = 2 AND objective_id = ?"
                        " ORDER BY created_at DESC LIMIT 1", (objective_id,)),
            "delayed_retrieval",
        )


class EvidenceLayerTest(ReviewCase):
    def test_l1_returns_the_attempt_and_never_the_reference(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        with db.read() as connection:
            l1 = evidence.layer1(connection, lesson["enrollment_id"], objective_id=objective_id)
        self.assertEqual(len(l1["attempts"]), 1)
        attempt = l1["attempts"][0]
        self.assertEqual(attempt["verdict"], "pass")
        self.assertNotIn("reference", attempt)
        self.assertNotIn("reference", attempt["provenance"])
        self.assertIn("answer", attempt)

    def test_l2_links_only_cold_independent_evidence(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        # A hint first: the pass must not become independent evidence.
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
                " evidence_class, created_at) VALUES ('evd_hint', ?, ?, NULL, 1, 'hint_request',"
                " 'hinted', ?)",
                (lesson["enrollment_id"], objective_id, _iso()),
            )
        self.pass_objective(lesson, objective_id)
        with db.read() as connection:
            l2 = evidence.layer2(connection, lesson["enrollment_id"], objective_id=objective_id)
        item = l2["objectives"][0]
        self.assertFalse(item["independent"])
        self.assertEqual(item["L2_evidence_ids"], [])
        self.assertEqual(item["attempt_classes"], {"hinted": 1})

    def test_l2_reports_independent_evidence_for_a_cold_pass(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        with db.read() as connection:
            l2 = evidence.layer2(connection, lesson["enrollment_id"], objective_id=objective_id)
            l1 = evidence.layer1(connection, lesson["enrollment_id"], objective_id=objective_id)
            linked = connection.execute(
                "SELECT attempt_id FROM evidence WHERE id = ?", (l2["objectives"][0]["L2_evidence_ids"][0],)
            ).fetchone()
        item = l2["objectives"][0]
        self.assertTrue(item["independent"])
        self.assertEqual(len(item["L2_evidence_ids"]), 1)
        l1_ids = {attempt["attempt_id"] for attempt in l1["attempts"]}
        self.assertIn(linked["attempt_id"], l1_ids)

    def test_l3_is_a_recommendation_and_says_it_is_not_a_persona(self) -> None:
        lesson = self.prepare_multi(2)
        self.pass_objective(lesson, lesson["objective_ids"][0])
        with db.read() as connection:
            l3 = evidence.layer3(connection, lesson["enrollment_id"])
        self.assertFalse(l3["is_persona"])
        self.assertTrue(l3["recommendations"])
        self.assertTrue(any(r["kind"] == "needs_independent_evidence" for r in l3["recommendations"]))

    def test_disputes_are_first_class_and_keep_the_original_verdict(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id, answer="1")  # wrong answer, keeps check open
        attempt_id = self.rows("SELECT id FROM attempts")[0]["id"]
        self.ok("attempt.dispute", {"attempt_id": attempt_id, "note": "I meant 42.7 with a unit."})
        with db.read() as connection:
            disputes = evidence.disputes(connection, lesson["enrollment_id"])
            l1 = evidence.layer1(connection, lesson["enrollment_id"], objective_id=objective_id)
        self.assertEqual(disputes["count"], 1)
        self.assertEqual(disputes["disputes"][0]["state"], "open")
        self.assertEqual(disputes["disputes"][0]["attempt_id"], attempt_id)
        # The verdict and evidence class are untouched by a dispute.
        self.assertEqual(self.scalar("SELECT verdict FROM attempts WHERE id = ?", (attempt_id,)), "not_yet")
        self.assertEqual(l1["attempts"][0]["dispute_count"], 1)

    def test_bundle_returns_all_three_layers_and_disputes(self) -> None:
        lesson = self.prepare_multi(1)
        self.pass_objective(lesson, lesson["objective_ids"][0])
        with db.read() as connection:
            bundle = evidence.bundle(connection, lesson["enrollment_id"])
        self.assertEqual(set(bundle), {"l1", "l2", "l3", "disputes"})


if __name__ == "__main__":
    unittest.main()
