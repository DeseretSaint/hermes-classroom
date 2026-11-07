"""M1-U2 — an authored page with block ``short`` is served by ``lesson.page``.

The renderer landed first (t_d72c8a4c): ``SectionPage`` draws Textbook from ``blocks[].deep`` and
Guided from ``blocks[].short``, and disables toggling when ``views.guided`` is false. Those tests
prove the renderer over a contract document. This file proves the other half end to end: the
writer authors ``short`` beside ``deep`` in ``gen_lessons.page_json``, and ``lesson.page`` projects
that page — not the linear segment rows — so a real generated lesson reports
``state = "complete"`` with a live Guided view, while an untouched v7 row stays ``textbook_only``.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, domain, generation, lesson_document
from tests.kernel_support import KernelCase, numeric_spec

SEPARATOR = "4711"


def authored_page() -> dict:
    """A page in the shape the lesson writer produces: every deep field has an authored short."""
    return {
        "section_title": "Compute the total",
        "lesson_intent": "Add two line items and state the total.",
        "segments": [
            {
                "kind": "model",
                "heading": "Watch one addition",
                "body": "Line items are added in order. Read the first line, then the second, and "
                "keep a running total in the margin as you go.",
                "short": "Read each line in order and keep a running total in the margin.",
            },
            {
                "kind": "explain",
                "heading": "Why order matters",
                "body": "Addition is commutative, so the order of the line items does not change "
                "the total. Checking in a second order is a useful self-check.",
                "short": "Order does not change the total; checking in a second order is a self-check.",
            },
            {
                "kind": "guided",
                "heading": "Add your own pair",
                "body": "Take the two quantities from the practice stimulus, add them in the order "
                "written, then add them again in the reverse order and compare.",
                "short": "Add the two quantities, then add them again in reverse and compare.",
            },
        ],
        "worked_example": {
            "prompt": "Add the two line items on the receipt.",
            "steps": [
                "Write the first quantity in the margin",
                "Add the second quantity to it",
                "Say the total out loud",
            ],
            "answer": "The sum of the two quantities",
            "short": "Write the first quantity, add the second, then say the total.",
        },
        "learner_explanation": "The total is a sum you can check by adding the same quantities in "
        "the other order; if the two answers differ, re-read the lines before answering.",
        "learner_explanation_short": "A total you can check by adding the same quantities in the "
        "other order.",
        "sources": [],
        "media": [],
    }


def without_shorts(page: dict) -> dict:
    """The same page as a v7 row: deep only, no authored short anywhere."""
    old = json.loads(json.dumps(page))
    for segment in old["segments"]:
        segment.pop("short", None)
    old["worked_example"].pop("short", None)
    old.pop("learner_explanation_short", None)
    return old


class GuidedPageCase(KernelCase):
    def prepare(self) -> dict:
        lesson = self.prepare_lesson(numeric_spec(SEPARATOR))
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        return lesson

    def seed_generated_lesson(self, lesson: dict, page: dict, *, state: str = "validated") -> str:
        plan_hash = domain.plan_hash(lesson["plan_id"])
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
                " plan_hash, document_json, research_json, generation_state, result_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, '{}', '{}', 'validated', '{}', '2026-11-06T12:00:00Z')",
                (
                    "gpd_0001_test",
                    lesson["plan_id"],
                    lesson["course_id"],
                    "fingerprint-0001",
                    plan_hash,
                ),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, 1, ?, ?, ?, '[1]', '[]', '[]')",
                (
                    "gps_0001_test",
                    lesson["plan_id"],
                    plan_hash,
                    "Compute the total",
                    "Add two line items",
                ),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?, ?, '[]', '[]', '2026-11-06T12:00:00Z',"
                " '2026-11-06T12:00:00Z')",
                (
                    "gln_0001_test",
                    lesson["plan_id"],
                    "gps_0001_test",
                    plan_hash,
                    state,
                    json.dumps(page, ensure_ascii=False),
                ),
            )
        return "gln_0001_test"

    def read_page(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]

    def add_durable_segment(self, lesson: dict, text: str = "Braising is low and slow.") -> str:
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "mode": "resume",
            },
            idempotency_key="begin-key-guided-0001",
        )["result"]
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES ('seg_0001_guided', ?, 1, 'teaching', ?, '2026-01-01T00:00:00+00:00')",
            (run["lesson_run_id"], text),
        )
        return run["lesson_run_id"]


class AuthoredGuidedPageTest(GuidedPageCase):
    def test_a_generated_lesson_serves_a_complete_guided_document(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, authored_page())

        page = self.read_page(lesson)

        document = page["document"]
        self.assertEqual(document["state"], "complete")
        self.assertTrue(document["views"]["guided"])
        self.assertIsNone(document["view_note"])
        # The three teaching segments keep their roles and order; the worked example and the recap
        # are blocks too, and each one carries the short its author wrote.
        self.assertEqual(
            [block["role"] for block in document["blocks"]],
            ["example", "explain", "practice", "example", "recap"],
        )
        self.assertEqual(
            document["blocks"][0]["short"],
            "Read each line in order and keep a running total in the margin.",
        )
        self.assertEqual(
            document["blocks"][-1]["short"],
            "A total you can check by adding the same quantities in the other order.",
        )
        self.assertTrue(all(block["short"] for block in document["blocks"]))
        # Deep survives: Textbook and Guided are two lenses on one document, not two documents.
        self.assertIn("keep a running total in the margin as you go", document["blocks"][0]["deep"])
        # The check attaches to exactly one block, and it is the practice block.
        claiming = [block for block in document["blocks"] if block["check_id"]]
        self.assertEqual(len(claiming), 1)
        self.assertEqual(claiming[0]["role"], "practice")
        self.assertEqual(document["check_id"], lesson["check_id"])
        # The v7 fields are still served unchanged, so an older client keeps working.
        self.assertEqual(page["segments"][0]["text"], "Braising is low and slow.")
        lesson_document.validate_document(document)

    def test_the_authored_page_does_not_rewrite_the_durable_segments(self) -> None:
        lesson = self.prepare()
        run_id = self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, authored_page())
        before = self.rows("SELECT * FROM lesson_segments WHERE lesson_run_id = ?", (run_id,))

        self.read_page(lesson)

        after = self.rows("SELECT * FROM lesson_segments WHERE lesson_run_id = ?", (run_id,))
        self.assertEqual(after, before, "reading the page rewrote durable rows")
        stored = self.rows("SELECT page_json FROM gen_lessons WHERE id = 'gln_0001_test'")[0]["page_json"]
        self.assertEqual(json.loads(stored), authored_page(), "the stored page was rewritten")

    def test_a_v7_page_stays_textbook_only(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, without_shorts(authored_page()))

        document = self.read_page(lesson)["document"]

        self.assertEqual(document["state"], "textbook_only")
        self.assertFalse(document["views"]["guided"])
        self.assertTrue(document["view_note"])
        self.assertTrue(all(block["short"] is None for block in document["blocks"]))
        # The deep prose is still there: no view is lost, only the one that was never authored.
        self.assertTrue(all(block["deep"] for block in document["blocks"]))

    def test_a_section_without_a_generated_lesson_stays_textbook_only(self) -> None:
        lesson = self.prepare()  # gen_* tables exist, but no row for this objective
        self.add_durable_segment(lesson)

        document = self.read_page(lesson)["document"]

        self.assertEqual(document["state"], "textbook_only")
        self.assertFalse(document["views"]["guided"])
        self.assertEqual(document["blocks"][0]["deep"], "Braising is low and slow.")

    def test_an_unvalidated_lesson_is_not_served_as_guided(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, authored_page(), state="needs_review")

        document = self.read_page(lesson)["document"]

        # A page that never passed review is not a lens a learner is offered.
        self.assertEqual(document["state"], "textbook_only")
        self.assertFalse(document["views"]["guided"])

    def test_a_stored_page_that_no_longer_validates_falls_back_to_the_segments(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        broken = authored_page()
        broken["segments"][0]["short"] = "x" * (lesson_document.MAX_SHORT + 10)
        self.seed_generated_lesson(lesson, broken)

        document = self.read_page(lesson)["document"]

        # Refused, not repaired: the learner still gets the durable segment text and no view claims
        # a short that the validator rejected.
        self.assertEqual(document["state"], "textbook_only")
        self.assertFalse(document["views"]["guided"])
        self.assertEqual(document["blocks"][0]["deep"], "Braising is low and slow.")

    def test_no_answer_material_reaches_the_document(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, authored_page())

        document = self.read_page(lesson)["document"]

        self.assertEqual(lesson_document.answer_material(document), [])
        self.assertNotIn(SEPARATOR, lesson_document.narrative_text(document))
        check = self.rows("SELECT reference_json, rubric_json FROM checks WHERE id = ?", (lesson["check_id"],))[0]
        self.assertNotIn('"reference_answer"', json.dumps(document))
        self.assertTrue(check["reference_json"])

    def test_the_document_is_identical_on_a_second_read(self) -> None:
        lesson = self.prepare()
        self.add_durable_segment(lesson)
        self.seed_generated_lesson(lesson, authored_page())

        first = self.read_page(lesson)["document"]
        second = self.read_page(lesson)["document"]

        self.assertEqual(first, second)
        self.assertEqual(first["content_hash"], second["content_hash"])


if __name__ == "__main__":
    unittest.main()
