"""t_3a3c6ea1 — a parked ``needs_review`` page is not presented as a servable lesson.

The defect, found while closing t_82572eb0: a section whose only authored revision is parked for
review (``gen_lessons.state = 'needs_review'``, two recorded gate reasons) returned
``document.state: "empty"`` with ``view_note: "This section has no teaching content yet."``.
The refusal itself is correct (H-185/H-194: an unapproved page is never served), but the copy is
false — the section *does* have an authored page — and Studio → Pages listed that parked page as
an ordinary learner page with no marker.

These are RPC-level tests against a real SQLite database:

* a parked page is still not served (empty document, no blocks, null ``check_id``, no provenance)
  and the note names the review state instead of "no teaching content";
* a section that never had an authored page keeps the original "no teaching content" copy;
* parking a *newer* edit over a cleared revision still serves the cleared revision (H-194);
* ``parent.blueprint.read`` names the parked section in the Pages tab so the file is never
  shown as an ordinary learner page, and leaves every served section unmarked.
"""

from __future__ import annotations

import hashlib
import json
import unittest

from coursebook import db, domain

from tests.test_h194_fine_tune import FineTuneCase
from tests.test_lesson_page_model_assessed import (
    SEPARATOR,
    LessonPageCase,
    authored_page,
)

EMPTY_COPY = "This section has no teaching content yet."


class ParkedLessonPageTest(LessonPageCase):
    def test_a_parked_page_is_not_served_and_the_note_names_review(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(lesson, authored_page(), state="needs_review")
        # The live row: the gate stored the check closed with a failed audit.
        self.set_check_audit(lesson["check_id"], state="closed", audit_state="failed")

        page = self.read_page(lesson)
        document = page["document"]

        # Nothing is served: no blocks, no check, no provenance claim.
        self.assertEqual(document["state"], "empty")
        self.assertEqual(document["blocks"], [])
        self.assertIsNone(document["check_id"])
        self.assertIsNone(page["provenance"])
        self.assertFalse(document["views"]["guided"])

        # The copy names the real state and never claims nothing was authored.
        self.assertIn("awaiting review", document["view_note"])
        self.assertNotIn("no teaching content", document["view_note"])
        self.assertNotEqual(document["view_note"], EMPTY_COPY)

        # The authored text is not on the wire at all.
        self.assertNotIn("Read each line in order", json.dumps(document))

    def test_a_section_with_no_authored_page_keeps_the_empty_copy(self) -> None:
        lesson = self.prepare()

        page = self.read_page(lesson)

        self.assertEqual(page["document"]["state"], "empty")
        self.assertEqual(page["document"]["view_note"], EMPTY_COPY)

    def test_a_parked_edit_over_a_cleared_revision_still_serves_the_cleared_page(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(lesson, authored_page(), state="validated")
        plan_hash = domain.plan_hash(lesson["plan_id"])
        # A newer authored edit that the gate parked; the version-1 page stays served.
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES ('gln_parked_v2', ?, 'gps_h185_test', ?, 2, 'needs_review', ?, '[]',"
                " ?, '2026-11-06T13:00:00Z', '2026-11-06T13:00:00Z')",
                (
                    lesson["plan_id"],
                    plan_hash,
                    json.dumps(authored_page(), ensure_ascii=False),
                    json.dumps(["learner-facing narrative carries the reference answer"]),
                ),
            )

        page = self.read_page(lesson)

        self.assertEqual(page["document"]["state"], "complete")
        self.assertIsNone(page["document"]["view_note"])
        self.assertEqual(page["document"]["check_id"], lesson["check_id"])
        self.assertEqual(page["provenance"]["outcome"], "independently_validated")

    def test_the_parked_check_cannot_be_opened_from_the_page(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(lesson, authored_page(), state="needs_review")
        self.set_check_audit(lesson["check_id"], state="closed", audit_state="failed")

        page = self.read_page(lesson)

        # The page carries no check reference, so a learner surface has nothing to open.
        self.assertIsNone(page["document"]["check_id"])
        # And the stored check was not reopened as a side effect of reading the page.
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)),
            "closed",
        )


class ParkedBlueprintPagesTest(FineTuneCase):
    """The Pages tab (``parent.blueprint.read``) must name a parked section as parked."""

    def page_hash(self, section_id: str) -> str:
        stored = self.scalar(
            "SELECT page_json FROM gen_lessons WHERE section_id = ? ORDER BY version DESC LIMIT 1",
            (section_id,),
        )
        page = json.loads(str(stored))
        return "sha256:" + hashlib.sha256(
            json.dumps(page, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def park_one_section(self, course: dict) -> str:
        section = course["sections"][0]
        self.ok(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section["id"],
                "expected_page_hash": self.page_hash(section["id"]),
                "title": "A sharper first section",
                "page": {"section_title": "A sharper first section"},
            },
            expected_revision=course["revision"],
            idempotency_key="t3a3-park-revise",
        )
        return section["id"]

    def test_a_parked_section_is_marked_in_the_pages_tab(self) -> None:
        course = self.authored_course()
        section_id = self.park_one_section(course)

        book = self.ok("parent.blueprint.read", {"course_id": course["course_id"]})["result"]
        states = {row["section_id"]: row["lesson_state"] for row in book["sections"]}
        self.assertEqual(states[section_id], "needs_review")

        parked_objective = next(
            row["objective_id"] for row in book["sections"] if row["section_id"] == section_id
        )
        learner_pages = {file["objective_id"]: file for file in book["tabs"]["learner_pages"]}
        parked_file = learner_pages[parked_objective]
        self.assertTrue(
            parked_file["title"].startswith("Needs review · "),
            parked_file["title"],
        )
        # The marker travels with every tab that shows this section's authored text.
        for role in ("parent_guide", "answers", "narration"):
            titles = [
                file["title"]
                for file in book["tabs"].get(role, [])
                if file["objective_id"] == parked_objective
            ]
            for title in titles:
                self.assertTrue(title.startswith("Needs review · "), title)

        # A served section's file is not marked.
        for objective_id, file in learner_pages.items():
            if objective_id == parked_objective:
                continue
            self.assertFalse(file["title"].startswith("Needs review"), file["title"])

    def test_the_parked_page_is_still_not_served_to_the_learner(self) -> None:
        course = self.authored_course()
        section_id = self.park_one_section(course)
        objective_id = self.scalar(
            "SELECT id FROM objectives WHERE plan_id = ? AND ordinal = 1", (course["plan_id"],)
        )

        # The version-1 page was validated, so the learner keeps that cleared page; the parked
        # version-2 edit is never served.
        page = self.ok(
            "lesson.page",
            {"enrollment_id": course["enrollment_id"], "objective_id": objective_id},
        )["result"]
        self.assertEqual(page["document"]["state"], "complete")
        self.assertNotIn("A sharper first section", json.dumps(page["document"]))
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM gen_lessons WHERE section_id = ? AND state = 'needs_review'",
                (section_id,),
            ),
            1,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
