"""E2E S2/S4: units carry their own authoring context, and prerequisites gate authoring.

Design authority: ``docs/ADVERSARIAL-E2E-2026-11-12.md`` S2 and S4.

S2 measured a *payload* fact: the lesson request carried ``plan_title``, ``learner_outcome``,
``through_line`` and one ``previous_section`` title, so section 30's authoring inputs were the same
kind as section 2's and a "full" course was more of the same lesson. S4 measured an *ordering*
fact: ``run_lesson_job`` accepted any ``unit_ordinal`` and checked no prerequisite, so unit 3 could
be authored before unit 1 and its review then failed the whole unit job because unit 1's owner
checks did not exist.

Every case here is offline and deterministic: a request payload built from a hand-built plan, or a
typed refusal against a real migrated database with a fake provider that records what it was
asked. No test presents invented provider output as a real call.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, executor, generation as gen, job_service

from tests.blueprint_support import blueprint_plan
from tests.test_blueprint_units import T0, UnitStageCase


def _lesson_requests(llm) -> list[gen.LLMRequest]:
    return [request for request in llm.requests if request.purpose == "coursebook.lesson.generate"]


def _payload(request: gen.LLMRequest) -> dict:
    return json.loads(request.input_text)


def _flat_plan() -> dict:
    """A v1-shaped plan: objectives and sections, no units.

    A flat plan has no unit, and the honest payload says so (``unit: None``) instead of inventing
    one; ``taught_so_far`` is still derivable from the plan's own objective order.
    """
    return {
        "title": "A flat course",
        "learner_outcome": "Do the two observable things in order.",
        "through_line": "First the parts, then the assembly.",
        "objectives": [
            {
                "ordinal": 1,
                "title": "Name the parts of the axle",
                "evidence_target": "comprehension",
                "support": "unverified",
            },
            {
                "ordinal": 2,
                "title": "Install the axle in the frame",
                "evidence_target": "procedure",
                "support": "unverified",
            },
        ],
        "sections": [
            {"ordinal": 1, "title": "The parts", "objective_refs": [1]},
            {"ordinal": 2, "title": "Installing", "objective_refs": [2]},
        ],
    }


class LessonUnitPayloadTest(unittest.TestCase):
    """S2: the payload says where the section sits and what came before it."""

    def test_a_blueprint_objective_gets_its_unit_block_from_the_plan(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        objective = next(item for item in plan["objectives"] if int(item["ordinal"]) == 3)
        section = {
            "ordinal": 3,
            "title": "Second unit, first owner",
            "objective_refs": [3],
            "source_ids": [],
        }
        request = gen.build_lesson_request(
            plan=plan,
            section=section,
            objective=objective,
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        payload = _payload(request)
        self.assertEqual(
            payload["unit"],
            {
                "ordinal": 2,
                "title": plan["units"][1]["title"],
                "goal": plan["units"][1]["goal"],
                "prereq_unit_ordinals": [1],
            },
        )
        # Objectives 1 and 2 were taught before objective 3, oldest first.
        self.assertEqual(
            payload["taught_so_far"],
            [plan["objectives"][0]["title"], plan["objectives"][1]["title"]],
        )

    def test_a_flat_plan_gets_no_invented_unit_and_still_knows_what_was_taught(self) -> None:
        plan = _flat_plan()
        request = gen.build_lesson_request(
            plan=plan,
            section=plan["sections"][1],
            objective=plan["objectives"][1],
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        payload = _payload(request)
        self.assertIsNone(payload["unit"], "a flat plan has no unit; none may be invented")
        self.assertEqual(payload["taught_so_far"], [plan["objectives"][0]["title"]])

    def test_the_instruction_requires_the_section_to_build_on_the_blocks(self) -> None:
        plan = _flat_plan()
        request = gen.build_lesson_request(
            plan=plan,
            section=plan["sections"][1],
            objective=plan["objectives"][1],
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        self.assertIn("'taught_so_far'", request.instructions)
        self.assertIn("'unit'", request.instructions)
        self.assertIn("Build on what was already taught", request.instructions)
        # A payload change is a prompt change: the version is recorded in stored bindings.
        self.assertEqual(request.prompt_version, gen.LESSON_PROMPT_VERSION)
        self.assertEqual(gen.LESSON_PROMPT_VERSION, "lesson-prompt.v18")

    def test_taught_so_far_is_bounded_to_the_most_recent_objectives(self) -> None:
        plan = _flat_plan()
        plan["objectives"] = [
            {"ordinal": index, "title": f"Objective {index} does a thing"}
            for index in range(1, 30)
        ]
        plan["sections"] = [
            {"ordinal": index, "title": f"Section {index}", "objective_refs": [index]}
            for index in range(1, 30)
        ]
        request = gen.build_lesson_request(
            plan=plan,
            section=plan["sections"][-1],
            objective=plan["objectives"][-1],
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        payload = _payload(request)
        self.assertEqual(len(payload["taught_so_far"]), gen.LESSON_TAUGHT_SO_FAR_MAX_TITLES)
        self.assertEqual(payload["taught_so_far"][-1], "Objective 28 does a thing")


class LessonUnitContextJobTest(UnitStageCase):
    """S2 at the job level: two units, two different authoring contexts."""

    def _author_unit_sections(self, plan: dict, plan_id: str, ordinals) -> None:
        for ordinal in ordinals:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": ordinal}},
                self.section_llm(plan, unit_ordinal=ordinal),
                plan_id=plan_id,
                unit_ordinal=ordinal,
                now=T0,
            )

    def test_two_units_produce_different_unit_blocks_and_a_non_empty_taught_so_far(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        _course_id, plan_id = self.seed(plan)
        self._author_unit_sections(plan, plan_id, (1, 2))

        first = self.lesson_llm()
        gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            first,
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        second = self.lesson_llm()
        gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 2}},
            second,
            plan_id=plan_id,
            unit_ordinal=2,
            now=T0,
        )

        unit_one = [_payload(request) for request in _lesson_requests(first)]
        unit_two = [_payload(request) for request in _lesson_requests(second)]
        self.assertEqual(len(unit_one), 2)
        self.assertEqual(len(unit_two), 2)

        self.assertEqual(unit_one[0]["unit"]["ordinal"], 1)
        self.assertEqual(unit_two[0]["unit"]["ordinal"], 2)
        self.assertNotEqual(
            unit_one[0]["unit"], unit_two[0]["unit"], "two units must not share one context"
        )
        self.assertEqual(unit_two[0]["unit"]["prereq_unit_ordinals"], [1])
        # The first lesson of the course has nothing behind it; unit 2's first lesson has unit 1.
        self.assertEqual(unit_one[0]["taught_so_far"], [])
        self.assertEqual(len(unit_one[1]["taught_so_far"]), 1)
        self.assertEqual(
            unit_two[0]["taught_so_far"],
            [plan["objectives"][0]["title"], plan["objectives"][1]["title"]],
            "unit 2's first lesson is told what unit 1 taught",
        )
        # The unit goal is the unit's own, not the course-wide outcome repeated.
        self.assertEqual(unit_two[0]["unit"]["goal"], plan["units"][1]["goal"])


class PrerequisiteAuthoringGateTest(UnitStageCase):
    """S4: a unit batch waits for its declared prerequisite units, before any provider call."""

    def _three_unit_plan(self) -> dict:
        plan = blueprint_plan(scope="short", units=3, objectives_per_unit=2)
        # Unit 3 rewrites its edge to unit 1: still backwards, unique and acyclic, and it makes the
        # refusal name the unit the acceptance criterion names.
        next(item for item in plan["units"] if int(item["ordinal"]) == 3)[
            "prereq_unit_ordinals"
        ] = [1]
        return plan

    def _author_unit_sections(self, plan: dict, plan_id: str, ordinals) -> None:
        for ordinal in ordinals:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": ordinal}},
                self.section_llm(plan, unit_ordinal=ordinal),
                plan_id=plan_id,
                unit_ordinal=ordinal,
                now=T0,
            )

    def test_unit_three_with_unit_one_incomplete_is_refused_before_the_first_call(self) -> None:
        plan = self._three_unit_plan()
        _course_id, plan_id = self.seed(plan)
        # Every unit's sections exist; only the prerequisite's *lessons* are missing.
        self._author_unit_sections(plan, plan_id, (1, 2, 3))

        llm = self.lesson_llm()
        with db.read() as connection:
            usage_before = connection.execute(
                "SELECT COUNT(*) AS n FROM usage_events"
            ).fetchone()["n"]
        with self.assertRaises(gen.PrerequisiteUnitIncomplete) as caught:
            gen.run_lesson_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 3}},
                llm,
                plan_id=plan_id,
                unit_ordinal=3,
                now=T0,
            )
        error = caught.exception
        self.assertEqual(error.code, "PREREQUISITE_UNMET")
        self.assertEqual(error.unit_ordinal, 3)
        self.assertEqual([item["unit_ordinal"] for item in error.unmet_units], [1])
        self.assertEqual(error.unmet_units[0]["reason"], "lessons_unauthored")
        self.assertIn("unit 1", str(error))
        self.assertIn("0 of 2 lesson(s) authored", str(error))
        self.assertIn("no provider call was made", str(error))
        # The refusal is before the first call, and it wrote nothing.
        self.assertEqual(llm.requests, [])
        with db.read() as connection:
            lessons = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_lessons WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
            # The unit stage's calls are real spend; the refused batch spent none.
            usage_after = connection.execute(
                "SELECT COUNT(*) AS n FROM usage_events"
            ).fetchone()["n"]
        self.assertEqual(int(lessons), 0)
        self.assertEqual(int(usage_after), int(usage_before))

    def test_the_refusal_reaches_jobs_get_as_a_contract_legal_envelope(self) -> None:
        """The job surface, not only the exception: the operator reads a frozen-catalogue error."""
        plan = self._three_unit_plan()
        _course_id, plan_id = self.seed(plan)
        self._author_unit_sections(plan, plan_id, (1, 2, 3))
        llm = self.lesson_llm()
        brief = {"stage": "lessons", "plan_id": plan_id, "unit_ordinal": 3}
        job_id = job_service.create("plan", brief, now=T0)["job_id"]
        stages = executor.resolvers(llm=llm, search=None, now=T0)["plan"](brief)
        view = job_service.execute(job_id, stages, now=T0)
        self.assertEqual(view["state"], "failed")
        error = view["error"]
        self.assertEqual(error["code"], "PREREQUISITE_UNMET")
        self.assertEqual(error["category"], "state")
        self.assertFalse(error["retryable"])
        self.assertEqual(error["details"]["unit_ordinal"], 3)
        self.assertEqual(
            [item["unit_ordinal"] for item in error["details"]["unmet_units"]], [1]
        )
        self.assertEqual(llm.requests, [])

    def test_a_unit_proceeds_once_its_declared_prerequisite_is_authored(self) -> None:
        plan = self._three_unit_plan()
        _course_id, plan_id = self.seed(plan)
        self._author_unit_sections(plan, plan_id, (1, 2, 3))

        gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.lesson_llm(),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        # Unit 3 declares unit 1 only, so unit 2 being unauthored is not its blocker.
        result = gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 3}},
            self.lesson_llm(),
            plan_id=plan_id,
            unit_ordinal=3,
            now=T0,
        )
        self.assertEqual(result["unit_ordinal"], 3)
        self.assertEqual(result["sections_total"], 2)

    def test_a_partially_authored_prerequisite_names_the_shortfall(self) -> None:
        plan = self._three_unit_plan()
        _course_id, plan_id = self.seed(plan)
        self._author_unit_sections(plan, plan_id, (1, 2, 3))
        gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.lesson_llm(),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        with db.transaction() as connection:
            # One of unit 1's two lessons is removed: the state the gate must report precisely.
            section = connection.execute(
                "SELECT id FROM gen_plan_sections WHERE plan_id = ? AND unit_id = 'unt_1'"
                " ORDER BY ordinal DESC LIMIT 1",
                (plan_id,),
            ).fetchone()
            connection.execute("DELETE FROM gen_lessons WHERE section_id = ?", (section["id"],))
        llm = self.lesson_llm()
        with self.assertRaises(gen.PrerequisiteUnitIncomplete) as caught:
            gen.run_lesson_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 3}},
                llm,
                plan_id=plan_id,
                unit_ordinal=3,
                now=T0,
            )
        self.assertEqual(caught.exception.unmet_units[0]["sections_authored"], 2)
        self.assertEqual(caught.exception.unmet_units[0]["lessons_authored"], 1)
        self.assertIn("1 of 2 lesson(s) authored", str(caught.exception))
        self.assertEqual(llm.requests, [])


if __name__ == "__main__":
    unittest.main()
