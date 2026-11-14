"""Item 37 — no two sections of one unit ask the learner the same question by accident.

The plan-level duplicate gate reads only ``sourced`` objectives, and the review gate compares a
review against *its own* owner. Between them, two owner sections could ask one question for two
objectives and a review could repeat a section that is not its owner. These cases pin the unit-level
rule: an exactly equal check stimulus or worked-example prompt between two owner sections is
refused with the section it duplicates named, while a review repeating an earlier target in new
items still passes, and a near-duplicate item list is a warning rather than a refusal.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen

from tests.blueprint_support import NOW, blueprint_plan, unit_sections_document
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import (
    FakeLLM,
    check_for_objective,
    lesson_fixture,
    response,
    source_ids_from,
    validation_from_fixture,
)

T0 = NOW


def same_question_author(request: gen.LLMRequest) -> gen.LLMResponse:
    """An author that writes the fixture's one question for every section.

    A real author writes the question *this* section's objective asks; this responder is the
    defect under test — two owner sections of one unit given an identical prompt, format and
    choices.
    """
    payload = json.loads(request.input_text)
    section = payload.get("section") or {}
    objective = payload.get("objective") or {}
    lesson = lesson_fixture("lesson_ja", source_ids_from(request))
    lesson["section_title"] = section.get("title") or lesson["section_title"]
    check_for_objective(lesson, objective)
    return response(lesson, model="fake-author")


class UnitLessonsCase(UnitStageCase):
    """An approved blueprint plan with its unit-section batch stored by hand (no provider)."""

    def plan(self) -> dict:
        return blueprint_plan(scope="short", units=1, objectives_per_unit=2, reviews=[1])

    def setUp(self) -> None:
        super().setUp()
        self.plan_document = self.plan()
        _course_id, self.plan_id = self.seed(self.plan_document)

    def store_sections(self, document: dict) -> None:
        digest = gen.plan_hash(self.plan_document)
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

    def lessons_llm(self, author) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )

    def run_lessons(self, llm: FakeLLM, *, unit_ordinal: int = 1) -> dict:
        return gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": unit_ordinal}},
            llm,
            plan_id=self.plan_id,
            unit_ordinal=unit_ordinal,
            now=T0,
        )

    def generated(self, llm: FakeLLM) -> list[gen.LLMRequest]:
        return [
            request
            for request in llm.requests
            if request.purpose == "coursebook.lesson.generate"
        ]


class DuplicateCheckTest(UnitLessonsCase):
    """Two owner sections of one unit, then a review — the shape the card describes."""

    def setUp(self) -> None:
        super().setUp()
        self.store_sections(
            unit_sections_document(
                unit=self.plan_document["units"][0],
                objectives=self.plan_document["objectives"],
                reviews=1,
            )
        )

    def test_two_owner_sections_cannot_ask_the_same_question(self) -> None:
        llm = self.lessons_llm(same_question_author)
        with self.assertRaises(gen.GenerationRejected) as caught:
            self.run_lessons(llm)
        message = str(caught.exception)
        # The refusal names the section it duplicates, in a form a caller can group on.
        self.assertIn("duplicate_of_section=1", message)
        self.assertIn("section 1", message)
        self.assertIn("section 2", message)
        # The author was told on the retry, not refused blind.
        retry = self.generated(llm)[-1]
        self.assertIn("duplicate_of_section=1", retry.input_text)
        # The duplicate section stored nothing: the unit's first lesson is durable, the refused one
        # never became a lesson or a check.
        with db.read() as connection:
            lessons = connection.execute(
                "SELECT section_id FROM gen_lessons WHERE plan_id = ? ORDER BY section_id",
                (self.plan_id,),
            ).fetchall()
            second_objective_checks = connection.execute(
                "SELECT COUNT(*) AS n FROM checks WHERE objective_id = 'obj_2'"
            ).fetchone()["n"]
        self.assertEqual([row["section_id"] for row in lessons], ["sec_1"])
        self.assertEqual(int(second_objective_checks), 0)

    def test_a_review_presenting_the_owners_target_in_new_items_passes(self) -> None:
        """Repetition is a review's job: the same target, in new items, authors all three."""
        from tests.test_generation import lesson_from_request

        llm = self.lessons_llm(lesson_from_request())
        result = self.run_lessons(llm)
        self.assertEqual(result["sections_total"], 3)
        self.assertEqual(len(result["lessons"]), 3)
        self.assertEqual(result["warnings"], [])
        with db.read() as connection:
            states = connection.execute(
                "SELECT state FROM gen_lessons WHERE plan_id = ?", (self.plan_id,)
            ).fetchall()
        self.assertEqual(len(states), 3)


class UnitScopeTest(UnitLessonsCase):
    """The rule is two sections of **one unit**; a later unit may re-ask on purpose (spiral)."""

    def plan(self) -> dict:
        return blueprint_plan(scope="short", units=2, objectives_per_unit=1, reviews=[0, 0])

    def setUp(self) -> None:
        super().setUp()
        for unit in self.plan_document["units"]:
            objectives = [
                objective
                for objective in self.plan_document["objectives"]
                if int(objective["unit_ref"]) == int(unit["ordinal"])
            ]
            self.store_sections(
                unit_sections_document(unit=unit, objectives=objectives), unit=unit
            )

    def store_sections(self, document: dict, *, unit: dict | None = None) -> None:  # type: ignore[override]
        unit_ref = int((unit or {}).get("ordinal") or document["unit_ref"])
        digest = gen.plan_hash(self.plan_document)
        with db.transaction() as connection:
            for section in document["sections"]:
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, media_need_json, objective_refs_json, context_needs_json,"
                    " source_ids_json, unit_id, section_role) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"sec_u{unit_ref}",
                        self.plan_id,
                        unit_ref,
                        digest,
                        str(section["title"]),
                        str(section["lesson_intent"]),
                        json.dumps(section["media_need"]),
                        json.dumps([int(section["primary_objective_ref"])]),
                        json.dumps(section.get("context_needs") or []),
                        json.dumps(section.get("source_ids") or []),
                        f"unt_{unit_ref}",
                        "owner",
                    ),
                )

    def test_the_same_question_in_a_later_unit_is_not_compared(self) -> None:
        for unit_ordinal in (1, 2):
            llm = self.lessons_llm(same_question_author)
            result = self.run_lessons(llm, unit_ordinal=unit_ordinal)
            self.assertEqual(result["sections_total"], 1)
            self.assertEqual(len(result["lessons"]), 1)


class DuplicateRuleUnitTest(unittest.TestCase):
    """The rule itself: pure, deterministic, and stated in terms of the unit's sections."""

    def stimulus(self, prompt: str, labels: list[str] | None = None) -> dict:
        return {
            "prompt": prompt,
            "format": "verification",
            "choices": [],
            "items": [
                {"id": f"item_{index}", "label": label}
                for index, label in enumerate(labels or [], start=1)
            ],
        }

    def prior(self, stimulus: dict, *, ordinal: int = 1, role: str = "owner") -> dict:
        return {
            "section_id": f"sec_{ordinal}",
            "ordinal": ordinal,
            "section_role": role,
            "stimulus": stimulus,
            "worked_example": {"prompt": "A first example"},
        }

    def section(self, *, ordinal: int = 2, role: str = "owner") -> dict:
        return {"section_id": f"sec_{ordinal}", "ordinal": ordinal, "section_role": role}

    def test_an_exact_duplicate_between_two_owners_is_refused(self) -> None:
        stimulus = self.stimulus("Tick each step for the pressure vessel.")
        problems, warnings = gen.unit_duplicate_stimulus_problems(
            section=self.section(),
            check={"stimulus": stimulus},
            worked_example={"prompt": "A second example"},
            prior=[self.prior(stimulus)],
        )
        self.assertEqual(warnings, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("duplicate_of_section=1", problems[0])

    def test_a_review_is_exempt_from_refusal_but_still_warned(self) -> None:
        stimulus = self.stimulus("Tick each step for the pressure vessel.")
        problems, warnings = gen.unit_duplicate_stimulus_problems(
            section=self.section(role="review"),
            check={"stimulus": stimulus},
            worked_example={"prompt": "A second example"},
            prior=[self.prior(stimulus)],
        )
        self.assertEqual(problems, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("duplicate_of_section=1", warnings[0])

    def test_the_reviews_own_owner_is_left_to_the_variant_gate(self) -> None:
        """S3 already refuses an exact copy of the owner; the pair is not reported twice."""
        stimulus = self.stimulus("Tick each step for the pressure vessel.")
        problems, warnings = gen.unit_duplicate_stimulus_problems(
            section=self.section(role="review"),
            check={"stimulus": stimulus},
            worked_example={"prompt": "A first example"},
            prior=[self.prior(stimulus)],
            own_target_section_id="sec_1",
        )
        self.assertEqual((problems, warnings), ([], []))

    def test_nearly_the_same_item_labels_are_a_warning_not_a_refusal(self) -> None:
        shared = ["Step one", "Step two", "Step three"]
        prior_stimulus = self.stimulus("Tick each step for the vessel.", shared)
        stimulus = self.stimulus("Which steps did you complete?", shared)
        problems, warnings = gen.unit_duplicate_stimulus_problems(
            section=self.section(),
            check={"stimulus": stimulus},
            worked_example={"prompt": "A different example"},
            prior=[self.prior(prior_stimulus)],
        )
        self.assertEqual(problems, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("near_duplicate_of_section=1", warnings[0])

    def test_a_different_question_over_different_items_is_silent(self) -> None:
        prior_stimulus = self.stimulus("Tick each step for the vessel.", ["Step one"])
        stimulus = self.stimulus("Tick each step for the pump.", ["Step two"])
        problems, warnings = gen.unit_duplicate_stimulus_problems(
            section=self.section(),
            check={"stimulus": stimulus},
            worked_example={"prompt": "A different example"},
            prior=[self.prior(prior_stimulus)],
        )
        self.assertEqual((problems, warnings), ([], []))


if __name__ == "__main__":
    unittest.main()
