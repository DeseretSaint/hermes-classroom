"""H-185 — ``lesson.page`` serves a model_assessed page with honest provenance.

The defect: ``_authored_lesson_page`` accepted only ``gen_lessons.state = 'validated'``. With no
second validator configured every generated page is ``model_assessed``, so the RPC returned no
authored page and the H-174 surface reported the lesson incomplete while instructing the learner
to re-run a job that could never change the state.

These are RPC-level tests (``lesson.page`` and ``attempt.submit``), not the internal
``generation.learner_page`` projection. They prove:

* a complete ``model_assessed`` row is served as an authored document with a provenance banner
  that says the author model assessed it and it is *not* an independent pass;
* an ``independently_validated`` row keeps its stronger provenance;
* the model-assessed page's check is usable: ``check.get`` reads it and ``attempt.submit`` grades
  one honest attempt (its audit stays ``pending``, so nothing claims an independent audit);
* a pending audit on a check that is *not* a model-assessed lesson's check is still refused;
* a genuinely incomplete generated page is not served blank and names what is missing.
"""

from __future__ import annotations

import json
import unittest

from coursebook import contracts, db, domain, generation
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

SEPARATOR = "4711"


def authored_page() -> dict:
    """A page in the shape the lesson writer produces (authored short beside each deep)."""
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
                "short": "Order does not change the total; a second order is a self-check.",
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
            "steps": ["Write the first quantity", "Add the second quantity", "Say the total"],
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


GENERATED_MEDIA = [
    {
        "kind": "visual",
        "role": "illustration",
        "purpose": "A receipt with two line items",
        "text_equivalent": "Receipt with two line items: 2 and 3.",
        "artifact_id": "art_0001_receipt",
        "mime": "image/png",
        "label": "Illustration",
        "degraded": True,
        "reason": "provider unavailable; the text equivalent is the lesson",
    }
]


class LessonPageCase(KernelCase):
    def prepare(self) -> dict:
        lesson = self.prepare_lesson(numeric_spec(SEPARATOR))
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        return lesson

    def seed_generated_lesson(
        self,
        lesson: dict,
        page: dict,
        *,
        state: str,
        media: list[dict] | None = None,
        check_id: str | None = None,
    ) -> str:
        """Insert the generation rows a served page is projected from, and link its check."""
        plan_hash = domain.plan_hash(lesson["plan_id"])
        link_check = check_id or lesson["check_id"]
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
                " plan_hash, document_json, research_json, generation_state, result_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, '{}', '{}', ?, '{}', '2026-11-06T12:00:00Z')",
                (
                    "gpd_h185_test",
                    lesson["plan_id"],
                    lesson["course_id"],
                    "fingerprint-h185",
                    plan_hash,
                    "validated" if state == "validated" else "needs_review",
                ),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, 1, ?, ?, ?, '[1]', '[]', '[]')",
                (
                    "gps_h185_test",
                    lesson["plan_id"],
                    plan_hash,
                    "Compute the total",
                    "Add two line items",
                ),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, ?, ?, ?, '[]', '2026-11-06T12:00:00Z',"
                " '2026-11-06T12:00:00Z')",
                (
                    "gln_h185_test",
                    lesson["plan_id"],
                    "gps_h185_test",
                    plan_hash,
                    state,
                    json.dumps(page, ensure_ascii=False),
                    json.dumps(media or [], ensure_ascii=False),
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, 1)",
                ("gln_h185_test", link_check),
            )
        return "gln_h185_test"

    def set_check_audit(self, check_id: str, *, state: str, audit_state: str) -> None:
        with db.transaction() as connection:
            connection.execute(
                "UPDATE checks SET state = ?, audit_state = ? WHERE id = ?",
                (state, audit_state, check_id),
            )

    def read_page(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]

    def media_children(self, document: dict) -> list[dict]:
        return [
            child
            for block in document["blocks"]
            for child in (block.get("media") or [])
        ]


class ModelAssessedLessonPageTest(LessonPageCase):
    def test_model_assessed_page_is_served_with_provenance_and_media(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(
            lesson,
            authored_page(),
            state="model_assessed",
            media=GENERATED_MEDIA,
        )
        self.set_check_audit(lesson["check_id"], state="open", audit_state="pending")

        page = self.read_page(lesson)

        # The authored document is served, not the empty segment fallback.
        document = page["document"]
        self.assertEqual(document["state"], "complete")
        self.assertTrue(document["views"]["guided"])
        self.assertGreaterEqual(len(document["blocks"]), 4)
        self.assertEqual(document["check_id"], lesson["check_id"])

        # Provenance is present, honest, and never a validation claim.
        provenance = page["provenance"]
        self.assertEqual(provenance["outcome"], "model_assessed")
        self.assertFalse(provenance["independent"])
        self.assertTrue(provenance["check_enabled"])
        self.assertTrue(provenance["warning"])
        self.assertIn("not independent", provenance["warning"])
        self.assertNotIn("independently_validated", json.dumps(provenance))
        # The warning names the honest negation ("not independently validated"); it never states
        # that a second model validated the page.
        self.assertNotIn("validated by a second model", json.dumps(provenance))

        # The generated media merged into the document with its text equivalent and honest
        # degraded reason, not the authoring spec the page snapshot still holds.
        media = self.media_children(document)
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["artifact_id"], "art_0001_receipt")
        self.assertEqual(media[0]["text_equivalent"], "Receipt with two line items: 2 and 3.")
        self.assertTrue(media[0]["degraded"])

    def test_validated_page_keeps_independent_provenance(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(lesson, authored_page(), state="validated")

        page = self.read_page(lesson)

        self.assertEqual(page["document"]["state"], "complete")
        self.assertEqual(page["provenance"]["outcome"], "independently_validated")
        self.assertTrue(page["provenance"]["independent"])
        self.assertIsNone(page["provenance"]["warning"])

    def test_the_model_assessed_check_can_be_read_and_attempted(self) -> None:
        lesson = self.prepare()
        self.seed_generated_lesson(lesson, authored_page(), state="model_assessed")
        self.set_check_audit(lesson["check_id"], state="open", audit_state="pending")

        # The question is readable (check.get has no state gate).
        question = self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]},
        )["result"]
        self.assertEqual(question["check_id"], lesson["check_id"])
        self.assertEqual(question["audit_state"], "pending")

        # One honest attempt is graded against the authored reference: the page is usable.
        submitted = self.submit(lesson, SEPARATOR)
        self.assertTrue(submitted["ok"], submitted.get("error"))
        result = submitted["result"]
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "cold")
        # The audit is still pending: nothing recorded the same-model pass as an independent one.
        self.assertEqual(
            self.scalar("SELECT audit_state FROM checks WHERE id = ?", (lesson["check_id"],)),
            "pending",
        )

    def test_a_pending_audit_outside_model_assessed_is_still_refused(self) -> None:
        lesson = self.prepare()  # check.open created the check with audit_state = passed
        self.set_check_audit(lesson["check_id"], state="open", audit_state="pending")

        error = self.submit(lesson, SEPARATOR)["error"]

        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "check_not_audited")

    def test_an_incomplete_generated_page_is_not_served_blank(self) -> None:
        lesson = self.prepare()
        empty = dict(authored_page())
        empty["segments"] = []
        empty.pop("worked_example")
        empty.pop("learner_explanation")
        self.seed_generated_lesson(lesson, empty, state="model_assessed")
        self.set_check_audit(lesson["check_id"], state="open", audit_state="pending")

        page = self.read_page(lesson)

        # No fabricated page: the document is empty and names the missing piece; provenance stays
        # null because no authored document was served.
        self.assertEqual(page["document"]["blocks"], [])
        self.assertIsNone(page["provenance"])
        self.assertIn("missing teaching segments", page["document"]["view_note"] or "")


class LessonPageSectionTotalTest(LessonPageCase):
    """E2E U3b: the stop chip's denominator is the course's own section count.

    ``lesson.page.section.sections_total`` is projected from the current plan inside the read
    transaction and validated against cb.rpc v28's response schema. It is the plan's objective
    count — the number of stops in the course the learner is actually enrolled in — never the
    page's block count (which is what the old chip wrongly divided by) and never a pack's
    manifest count.
    """

    def test_the_page_reports_the_plans_objective_count(self) -> None:
        # Objectives are authored on the draft, then the plan is approved: the count the page
        # reports is the approved plan's own objective count.
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id, numeric_spec(SEPARATOR))
        for title in ("Second stop", "Third stop"):
            domain.record_objective(
                plan_id,
                title=title,
                evidence_target="recall",
                criteria=criteria_with(numeric_spec()),
            )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        lesson = {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.seed_generated_lesson(lesson, authored_page(), state="model_assessed")
        self.set_check_audit(lesson["check_id"], state="open", audit_state="pending")
        with db.read() as connection:
            objectives = int(
                connection.execute(
                    "SELECT COUNT(*) FROM objectives WHERE plan_id = ?", (plan_id,)
                ).fetchone()[0]
            )
        self.assertEqual(objectives, 3)

        # The response is contract-validated by `api.dispatch`; a field the schema forbids or a
        # value outside its bounds would make this read fail rather than reach the assertion.
        page = self.read_page(lesson)

        self.assertEqual(page["section"]["ordinal"], 1)
        self.assertEqual(page["section"]["sections_total"], objectives)
        # The block count is the step readout's denominator and must not be substituted here.
        self.assertNotEqual(page["section"]["sections_total"], len(page["document"]["blocks"]))

    def test_a_v27_page_without_the_field_still_validates(self) -> None:
        """Additive means additive: the field is optional, so an older server keeps its shape."""
        lesson = self.prepare()
        page = self.read_page(lesson)
        section = dict(page["section"])
        section.pop("sections_total", None)
        contracts.validate_response_payload("lesson.page", {**page, "section": section})


if __name__ == "__main__":
    unittest.main()
