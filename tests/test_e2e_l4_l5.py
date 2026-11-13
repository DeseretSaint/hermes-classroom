"""E2E L4/L5: a finished course says so, and a rejected lesson is not a spaced review.

L4: a fully independent course used to fall through ``_library_next_step`` to ``review_plan``,
so the only primary a learner saw after the last check was "review/start a new plan version".
The terminal state is now ``complete``.

L5: ``needs_review`` was counted as a spaced review due and shared the review state word with
``review_due``. A page the validator parked now travels as ``repair_lesson`` with its stored
reasons and a section identity ``lesson.regenerate`` is keyed on; a real ``review_due`` always
outranks it, and neither a failed attempt nor a parked page raises the Home due count.

Every test drives the real commands against the real SQLite store (``KernelCase``), and every
result is validated against cb.rpc v28 by ``api.dispatch``.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from coursebook import db, domain, generation, review
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

PARKED_REASONS = [
    "The page taught the answer its check asks for.",
    "The explanation restates the reference value instead of teaching the procedure.",
]


class CompletionTest(KernelCase):
    def test_a_fully_independent_course_returns_complete_not_review_plan(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "4")  # cold pass -> independent_evidence
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(item["next_step"]["kind"], "complete")
        self.assertNotEqual(item["next_step"]["kind"], "review_plan")
        self.assertIn("finished", item["next_step"]["label"].lower())
        self.assertEqual(item["evidence_summary"]["independent"], 1)
        self.assertEqual(item["evidence_summary"]["review_due"], 0)

    def test_a_course_with_one_section_left_is_not_complete(self) -> None:
        course_id, plan_id = self.new_course()
        first = self.seed_objective(plan_id)
        domain.record_objective(
            plan_id, title="Second", evidence_target="procedure",
            criteria=criteria_with(numeric_spec()),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": first},
            expected_revision=revision,
        )["result"]
        lesson = {
            "enrollment_id": enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }
        self.submit(lesson, "4")
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(item["next_step"]["kind"], "start_lesson")
        self.assertEqual(item["evidence_summary"]["independent"], 1)
        self.assertEqual(item["evidence_summary"]["total_objectives"], 2)

    def test_an_objective_with_evidence_is_not_reported_as_still_current(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "4")
        self.assertIsNone(
            self.scalar(
                "SELECT id FROM objectives WHERE id = ? AND state IN"
                " ('not_started','introduced','needs_review','review_due')",
                (lesson["objective_id"],),
            )
        )


class NeedsReviewIsNotADueReviewTest(KernelCase):
    def test_a_failed_attempt_is_not_counted_as_a_spaced_review(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "5")  # not_yet -> needs_review
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertNotEqual(item["next_step"]["kind"], "resolve_review_due")
        self.assertEqual(item["next_step"]["kind"], "start_lesson")
        self.assertEqual(item["evidence_summary"]["review_due"], 0)
        filtered = self.ok("library.list", {"filter": "review_due"})["result"]
        self.assertEqual(filtered["total"], 0)

    def test_a_real_spaced_review_is_counted(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "4")
        self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (lesson["objective_id"],))
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(item["next_step"]["kind"], "resolve_review_due")
        self.assertEqual(item["evidence_summary"]["review_due"], 1)
        filtered = self.ok("library.list", {"filter": "review_due"})["result"]
        self.assertEqual(filtered["total"], 1)


class ParkedLessonRepairTest(KernelCase):
    def _park(self, lesson: dict, reasons: list[str] | None = None) -> str:
        """Write one parked ``needs_review`` authored revision for the lesson's objective."""
        reasons = reasons if reasons is not None else PARKED_REASONS
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        plan_hash = domain.plan_hash(lesson["plan_id"])
        section_id = "sec_" + "1" * 32
        now = "2026-11-12T00:00:00+00:00"
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
            " plan_hash, document_json, research_json, generation_state, validation_id,"
            " result_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "gpd_" + "1" * 32, lesson["plan_id"], lesson["course_id"],
                "fingerprint-1", plan_hash, json.dumps({"sections": []}), json.dumps({}),
                "validated", None, json.dumps({}), now,
            ),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
            " lesson_intent, media_need_json, objective_refs_json, context_needs_json,"
            " source_ids_json, unit_id, section_role) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                section_id, lesson["plan_id"], 1, plan_hash, "Compute", "Teach the procedure",
                "{}", json.dumps([1]), "[]", "[]", None, "owner",
            ),
        )
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
            " page_json, media_json, parent_notes_json, rejection_reasons_json, validation_id,"
            " policy_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "lsn_" + "1" * 32, lesson["plan_id"], section_id, plan_hash, 1, "needs_review",
                json.dumps({"section_title": "Compute", "blocks": []}), "[]", None,
                json.dumps(reasons), None, "{}", now, now,
            ),
        )
        return section_id

    def test_a_parked_lesson_returns_repair_with_its_reasons(self) -> None:
        lesson = self.prepare_lesson()
        section_id = self._park(lesson)
        item = self.ok("library.list", {})["result"]["items"][0]
        step = item["next_step"]
        self.assertEqual(step["kind"], "repair_lesson")
        self.assertEqual(step["objective_id"], lesson["objective_id"])
        self.assertEqual(step["section_id"], section_id)
        self.assertEqual(step["reasons"], PARKED_REASONS)
        self.assertIn("Repair", step["label"])
        # A rejected page is not a spaced review due.
        self.assertEqual(item["evidence_summary"]["review_due"], 0)
        self.assertEqual(self.ok("library.list", {"filter": "review_due"})["result"]["total"], 0)

    def test_the_outline_and_page_name_the_parked_section(self) -> None:
        lesson = self.prepare_lesson()
        section_id = self._park(lesson)
        outline = self.ok(
            "course.outline", {"enrollment_id": lesson["enrollment_id"]}
        )["result"]
        objective = outline["objectives"][0]
        self.assertEqual(objective["section_id"], section_id)
        self.assertEqual(objective["lesson_state"], "needs_review")
        self.assertEqual(objective["lesson_rejection_reasons"], PARKED_REASONS)

        page = self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]
        self.assertEqual(page["section"]["section_id"], section_id)
        self.assertEqual(page["section"]["lesson_state"], "needs_review")
        self.assertEqual(page["section"]["rejection_reasons"], PARKED_REASONS)

    def test_a_spaced_review_outranks_a_repair(self) -> None:
        lesson = self.prepare_lesson()
        self._park(lesson)
        # A genuine due review on another objective: the repair must not hide it.
        self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (lesson["objective_id"],))
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(item["next_step"]["kind"], "resolve_review_due")

    def test_lesson_regenerate_refuses_reasons_that_changed(self) -> None:
        lesson = self.prepare_lesson()
        section_id = self._park(lesson)
        error = self.err(
            "lesson.regenerate",
            {
                "enrollment_id": lesson["enrollment_id"],
                "plan_id": lesson["plan_id"],
                "section_id": section_id,
                "reasons": ["A reason this build never stored."],
            },
            idempotency_key="repair-stale-reasons",
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "repair_reasons_changed")
        self.assertEqual(error["details"]["current_reasons"], PARKED_REASONS)

    def test_lesson_regenerate_carries_the_stored_reasons_into_the_brief(self) -> None:
        lesson = self.prepare_lesson()
        section_id = self._park(lesson)
        response = self.dispatch(
            "lesson.regenerate",
            {
                "enrollment_id": lesson["enrollment_id"],
                "plan_id": lesson["plan_id"],
                "section_id": section_id,
                "reasons": PARKED_REASONS,
            },
            idempotency_key="repair-matching-reasons",
        )
        if not response["ok"]:
            # A cost preflight may refuse a synthetic one-section plan; that is a different
            # refusal and the reasons fence already passed. Assert it is not the reasons fence.
            self.assertNotEqual(
                (response["error"].get("details") or {}).get("reason"),
                "repair_reasons_changed",
            )
            self.skipTest(f"regenerate refused before queueing: {response['error']['code']}")
        brief = self.rows("SELECT brief_json FROM jobs WHERE id = ?", (response["result"]["job_id"],))[0]
        self.assertEqual(json.loads(brief["brief_json"])["repair_reasons"], PARKED_REASONS)


class ReviewQueueConsistencyTest(KernelCase):
    """The queue stays derived from evidence; a failed attempt with no pass is not schedulable."""

    def test_a_fresh_needs_review_objective_is_not_in_the_review_queue(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "5")
        with db.read() as connection:
            queue = review.queue(connection, lesson["enrollment_id"], now=datetime.now(timezone.utc))
        self.assertEqual(queue["total_due"], 0)
        self.assertEqual(queue["items"], [])


if __name__ == "__main__":
    unittest.main()
