"""CP-015f: one owner check serves one review section, at both gates.

Reproduction: plan ``93cdc4ea1a52fb49`` unit 1 stored owner sections for objectives 1–3 and two
review sections (``[1, 2]`` and ``[2, 3]``). The unit stage and its independent validator both
accepted the batch; the lesson stage then refused section 5 because objective 2's owner check was
closed — after four lessons and nine provider calls had been spent.

These cases pin the rule to the batch, where it is knowable: the unit-sections gate refuses such a
batch and feeds the reason back for the one legal re-author, and the lesson stage applies the same
rule to a stored batch *before* any provider call.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen

from tests.blueprint_support import (
    NOW,
    blueprint_plan,
    response,
    unit_sections_document,
    validation_pass,
)
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import FakeLLM, lesson_from_request, validation_from_fixture

T0 = NOW

REASON = "one owner check serves one review section"


def cp015f_document(unit: dict, objectives: list[dict], *, legal: bool) -> dict:
    """A five-section batch in the shape the stored run used.

    Owners 1/2/3, then two reviews. The illegal shape reinforces objective 2 twice (``[1, 2]`` and
    ``[2, 3]``); the legal one reinforces each objective exactly once (``[1]`` and ``[2, 3]``).
    """
    document = unit_sections_document(unit=unit, objectives=objectives, reviews=2)
    if not legal:
        document["sections"][3]["reinforces"] = [1, 2]
        document["sections"][4]["reinforces"] = [2, 3]
    return document


def sections_of(document: dict) -> list[dict]:
    return [dict(section) for section in document["sections"]]


class UnitSectionsReviewRuleTest(unittest.TestCase):
    """The rule gate itself: deterministic, and stated in terms of the batch."""

    def plan(self) -> dict:
        return blueprint_plan(scope="short", units=1, objectives_per_unit=3, reviews=[2])

    def enforce(self, document: dict, *, plan: dict, existing_reviews=()) -> None:
        gen.enforce_unit_section_rules(
            sections_of(document),
            unit=plan["units"][0],
            objectives=[obj for obj in plan["objectives"]],
            plan=plan,
            recipe="casual",
            dials={},
            locale=None,
            ledger=(),
            existing_reviews=existing_reviews,
        )

    def test_two_reviews_over_one_objective_are_refused(self) -> None:
        plan = self.plan()
        document = cp015f_document(plan["units"][0], plan["objectives"], legal=False)
        with self.assertRaises(gen._RuleViolation) as caught:
            self.enforce(document, plan=plan)
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("objective 2", reasons)
        self.assertIn(REASON, reasons)

    def test_one_review_per_objective_passes(self) -> None:
        plan = self.plan()
        document = cp015f_document(plan["units"][0], plan["objectives"], legal=True)
        self.enforce(document, plan=plan)  # no exception

    def test_a_review_already_stored_counts_against_the_batch(self) -> None:
        """A unit authored in two batches cannot hide a second review over one objective."""
        plan = self.plan()
        document = cp015f_document(plan["units"][0], plan["objectives"], legal=True)
        stored_review = {"ordinal": 4, "section_role": "review", "objective_refs": [1]}
        with self.assertRaises(gen._RuleViolation) as caught:
            self.enforce(document, plan=plan, existing_reviews=[stored_review])
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("stored section 4", reasons)
        self.assertIn(REASON, reasons)


class UnitSectionsAuthoringGateTest(UnitStageCase):
    """The reason reaches the one legal re-author inside the same job."""

    def setUp(self) -> None:
        super().setUp()
        self.plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, reviews=[2])
        _course_id, self.plan_id = self.seed(self.plan)

    def llm(self, *, first_legal: bool) -> FakeLLM:
        unit = self.plan["units"][0]
        objectives = self.plan["objectives"]
        first = cp015f_document(unit, objectives, legal=first_legal)
        second = cp015f_document(unit, objectives, legal=True)
        return FakeLLM(
            {
                "coursebook.unit_sections.generate": [response(first), response(second)],
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )

    def run_job(self, llm: FakeLLM) -> dict:
        return gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=T0,
        )

    def test_the_second_attempt_is_told_which_objective_is_over_reviewed(self) -> None:
        llm = self.llm(first_legal=False)
        result = self.run_job(llm)
        self.assertEqual(result["sections"], 5)
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        retry = llm.requests[-2].input_text
        self.assertIn("objective 2", retry)
        self.assertIn(REASON, retry)

    def test_a_batch_refused_twice_stores_nothing_and_never_validates(self) -> None:
        unit = self.plan["units"][0]
        illegal = cp015f_document(unit, self.plan["objectives"], legal=False)
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(illegal),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        with self.assertRaises(gen.GenerationRejected) as caught:
            self.run_job(llm)
        self.assertIn(REASON, str(caught.exception))
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        self.assertEqual(llm.calls_for("coursebook.unit_sections.validate"), 0)
        with db.read() as connection:
            sections = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?",
                (self.plan_id,),
            ).fetchone()["n"]
            validations = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_validation_records"
                " WHERE subject_kind = 'unit_sections'"
            ).fetchone()["n"]
        self.assertEqual(int(sections), 0)
        self.assertEqual(int(validations), 0)


class StoredBatchCase(UnitStageCase):
    """A seeded approved plan plus a hand-stored unit-section batch (no provider involved)."""

    legal = False

    def setUp(self) -> None:
        super().setUp()
        self.plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, reviews=[2])
        _course_id, self.plan_id = self.seed(self.plan)
        self.store_sections(
            cp015f_document(self.plan["units"][0], self.plan["objectives"], legal=self.legal)
        )

    def store_sections(self, document: dict) -> None:
        digest = gen.plan_hash(self.plan)
        with db.transaction() as connection:
            for index, section in enumerate(document["sections"], start=1):
                role = str(section.get("role") or "owner")
                refs = (
                    [int(section["primary_objective_ref"])]
                    if role == "owner"
                    else [int(ref) for ref in section.get("reinforces") or []]
                )
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, media_need_json, objective_refs_json, context_needs_json,"
                    " source_ids_json, unit_id, section_role) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"sec_{index}",
                        self.plan_id,
                        index,
                        digest,
                        str(section["title"]),
                        str(section["lesson_intent"]),
                        json.dumps(section["media_need"]),
                        json.dumps(refs),
                        json.dumps(section.get("context_needs") or []),
                        json.dumps(section.get("source_ids") or []),
                        "unt_1",
                        role,
                    ),
                )

    def lessons_llm(self) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )

    def run_lessons(self, llm: FakeLLM) -> dict:
        return gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=T0,
        )


class IllegalStoredBatchTest(StoredBatchCase):
    legal = False

    def test_lessons_refuse_the_stored_batch_before_spending_anything(self) -> None:
        llm = self.lessons_llm()
        with self.assertRaises(gen.GenerationRejected) as caught:
            self.run_lessons(llm)
        message = str(caught.exception)
        self.assertIn("cannot be authored", message)
        self.assertIn("objective 2", message)
        self.assertIn(REASON, message)
        self.assertEqual(llm.calls_for("coursebook.lesson.generate"), 0)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
        with db.read() as connection:
            lessons = connection.execute("SELECT COUNT(*) AS n FROM gen_lessons").fetchone()["n"]
            checks = connection.execute("SELECT COUNT(*) AS n FROM checks").fetchone()["n"]
        self.assertEqual(int(lessons), 0)
        self.assertEqual(int(checks), 0)

    def test_the_unit_stage_does_not_call_the_stored_batch_reusable(self) -> None:
        llm = FakeLLM({})
        with self.assertRaises(gen.GenerationRejected) as caught:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": 1}},
                llm,
                plan_id=self.plan_id,
                unit_ordinal=1,
                now=T0,
            )
        self.assertIn(REASON, str(caught.exception))
        self.assertEqual(llm.requests, [], "a stored batch is judged without a provider call")


class LegalStoredBatchTest(StoredBatchCase):
    """The gate must not over-block: one review per objective still authors all five lessons."""

    legal = True

    def test_lessons_are_authored_for_a_legal_batch(self) -> None:
        result = self.run_lessons(self.lessons_llm())
        self.assertEqual(result["sections_total"], 5)
        self.assertEqual(len(result["lessons"]), 5)


if __name__ == "__main__":
    unittest.main()
