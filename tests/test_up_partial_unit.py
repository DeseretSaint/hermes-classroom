"""Upgrade 35: a refused unit batch keeps the sections that passed their own gate.

The card's acceptance is the first test: a unit of five whose sections 4 and 5 fail the
per-section gate stores three rows, the next request names only objectives 4-5, and
``unit_authoring_state`` still reports that unit as next.

The adversarial note is covered by the other two: a persisted half-unit is exactly the dead
artifact the transactional rule replaced, so the partial state is fenced in ``lesson.page``, in
``course.export.read`` and in the unit-complete count in this same change. Without those fences the
change would be worse than re-authoring, and these tests would pass while a learner could still be
served a half-covered unit.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from coursebook import db, domain, generation as gen, pack_flow

from tests.blueprint_support import (
    NOW,
    blueprint_plan,
    response,
    unit_sections_document,
    validation_pass,
)
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import FakeLLM

T0 = NOW


def refused_tail_document(plan: dict) -> dict:
    """A five-section unit whose last two sections break their own (per-section) rules.

    Section 4's ``lesson_intent`` is clipped mid-sentence — schema-valid, editorially truncated —
    and section 5 cites an id that was never fetched. Everything about sections 1-3 is honest, so a
    unit stage that throws the whole batch away is paying twice for work that never had a problem.
    """
    unit = plan["units"][0]
    document = unit_sections_document(unit=unit, objectives=plan["objectives"])
    sections = document["sections"]
    sections[3]["lesson_intent"] = " ".join(str(sections[3]["lesson_intent"]).split()[:4])
    sections[4]["source_ids"] = ["src_never_fetched"]
    return document


class PartialUnitTest(UnitStageCase):
    def test_three_of_five_sections_survive_a_refused_batch(self) -> None:
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=5)
        course_id, plan_id = self.seed(plan)
        document = refused_tail_document(plan)
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        connection = db.connect()
        try:
            with self.assertRaises(gen.GenerationRejected) as caught:
                gen.run_unit_sections_job(
                    connection,
                    {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                    llm,
                    plan_id=plan_id,
                    unit_ordinal=1,
                    now=T0,
                )
            message = str(caught.exception)
            self.assertIn("src_never_fetched", message)
            self.assertIn("follow refused section", message)
            self.assertIn("sections that passed its own rules are stored", message)

            # 1. Three of the five sections are durable, in their authored order.
            stored = connection.execute(
                "SELECT ordinal, objective_refs_json, section_role FROM gen_plan_sections"
                " WHERE plan_id = ? AND unit_id = 'unt_1' ORDER BY ordinal",
                (plan_id,),
            ).fetchall()
            self.assertEqual(len(stored), 3, "the three sections that passed are kept")
            self.assertEqual(
                [json.loads(row["objective_refs_json"]) for row in stored], [[1], [2], [3]]
            )
            self.assertEqual([row["section_role"] for row in stored], ["owner", "owner", "owner"])

            # 2. The unit is durably marked partial, with the refused sections' own reasons.
            partial = connection.execute(
                "SELECT reasons_json FROM gen_unit_partials WHERE plan_id = ? AND unit_id = 'unt_1'",
                (plan_id,),
            ).fetchall()
            self.assertEqual(len(partial), 1)
            reasons = json.loads(partial[0]["reasons_json"])
            self.assertTrue(any("src_never_fetched" in reason for reason in reasons), reasons)
            self.assertTrue(
                any("objective 4 has no owner section" in reason for reason in reasons), reasons
            )

            # 3. The next job's request names only objectives 4-5 — and it was made in this job's
            #    second attempt, so the refusal already stopped the re-authoring of 1-3.
            requests = [
                request
                for request in llm.requests
                if request.purpose == "coursebook.unit_sections.generate"
            ]
            self.assertEqual(len(requests), 2)
            second = json.loads(requests[1].input_text)
            self.assertEqual(
                [int(item["ordinal"]) for item in second["objectives"]], [4, 5]
            )
            self.assertEqual(second["already_authored"]["owner_objectives"], [1, 2, 3])

            # 4. Unit completeness still reports this unit as the next thing to author.
            state = gen.unit_authoring_state(connection, plan_id)
            self.assertIsNotNone(state)
            self.assertEqual(state["next_unit_ordinal"], 1)
            self.assertEqual(state["units_complete"], [])
            self.assertTrue(state["next_unit"]["partial"])
            self.assertEqual(state["next_unit"]["sections"], 3)
            self.assertFalse(state["complete"])
        finally:
            connection.close()

    def _seed_partial_unit(self) -> tuple[str, str]:
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=5)
        course_id, plan_id = self.seed(plan)
        document = refused_tail_document(plan)
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        connection = db.connect()
        try:
            with self.assertRaises(gen.GenerationRejected):
                gen.run_unit_sections_job(
                    connection,
                    {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                    llm,
                    plan_id=plan_id,
                    unit_ordinal=1,
                    now=T0,
                )
        finally:
            connection.close()
        stamp = T0.isoformat()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO enrollments (id, course_id, learner_label, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                ("enr_partial", course_id, "Learner", "active", 0, stamp, stamp),
            )
        return course_id, plan_id

    def test_a_unit_resumes_its_review_slots_without_its_stored_owners(self) -> None:
        """A prefix that stops before the reviews leaves owner coverage complete.

        The resumed request must ask for the review slots that remain (not ``target - 0``) and the
        per-section gate must judge a review against the unit's owner ordinals, not against an
        empty "missing objectives" list.
        """
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, reviews=[2])
        _course_id, plan_id = self.seed(plan)
        unit = plan["units"][0]
        objectives = plan["objectives"]
        refused_review = unit_sections_document(unit=unit, objectives=objectives, reviews=2)
        refused_review["sections"][3]["source_ids"] = ["src_never_fetched"]
        legal_reviews = unit_sections_document(unit=unit, objectives=objectives, reviews=2)
        first_llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(refused_review),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        connection = db.connect()
        try:
            with self.assertRaises(gen.GenerationRejected):
                gen.run_unit_sections_job(
                    connection,
                    {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                    first_llm,
                    plan_id=plan_id,
                    unit_ordinal=1,
                    now=T0,
                )
            stored = connection.execute(
                "SELECT section_role FROM gen_plan_sections WHERE unit_id = 'unt_1' ORDER BY ordinal"
            ).fetchall()
            self.assertEqual([row["section_role"] for row in stored], ["owner", "owner", "owner"])

            second_llm = FakeLLM(
                {
                    "coursebook.unit_sections.generate": response(legal_reviews),
                    "coursebook.unit_sections.validate": response(validation_pass()),
                }
            )
            result = gen.run_unit_sections_job(
                connection,
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                second_llm,
                plan_id=plan_id,
                unit_ordinal=1,
                now=T0,
            )
            request = json.loads(second_llm.requests[0].input_text)
            self.assertEqual(request["objectives"], [])
            self.assertEqual(request["already_authored"]["owner_objectives"], [1, 2, 3])
            self.assertEqual(request["rules"]["review_sections"], 2)
            self.assertEqual(result["sections"], 5)
            self.assertEqual((result["owners"], result["reviews"]), (3, 2))
            roles = [
                row["section_role"]
                for row in connection.execute(
                    "SELECT section_role FROM gen_plan_sections WHERE unit_id = 'unt_1'"
                    " ORDER BY ordinal"
                ).fetchall()
            ]
            self.assertEqual(roles, ["owner", "owner", "owner", "review", "review"])
            self.assertEqual(
                int(
                    connection.execute(
                        "SELECT COUNT(*) AS n FROM gen_unit_partials WHERE unit_id = 'unt_1'"
                    ).fetchone()["n"]
                ),
                0,
            )
        finally:
            connection.close()

    def test_a_partial_unit_is_fenced_from_the_learner_page(self) -> None:
        _course_id, plan_id = self._seed_partial_unit()
        # A served page can exist beside a partial unit (a section-scoped job may have written
        # one), so the fence is proven with an authored page object rather than with an empty
        # section: `lesson.page` must refuse it because the unit's marker is present.
        fake_authored = {
            "page": {"section_title": "Objective 1: the observable thing"},
            "state": "validated",
            "validation_id": None,
            "media": [],
            "lesson_id": "gln_fake",
            "version": 1,
        }
        with mock.patch.object(domain, "_authored_lesson_page", return_value=dict(fake_authored)):
            # Called directly: the seeded objective id is a fixture id, and the contract's
            # identifier shape is not what this test is about.
            status, page = domain.lesson_page(
                {"enrollment_id": "enr_partial", "objective_id": "obj_1"},
                {"contract": "cb.rpc", "contract_version": 11},
            )
        self.assertEqual(status, 0)
        self.assertEqual(page["document"]["blocks"], [])
        self.assertEqual(page["document"]["view_note"], domain._VIEW_NOTE_UNIT_PARTIAL)
        self.assertIsNone(page["document"]["check_id"])
        # The learner-facing note names no job, stage or reason code.
        for token in ("unit_sections", "job", "partial", plan_id):
            self.assertNotIn(token, page["document"]["view_note"])

    def test_a_partial_unit_is_fenced_from_course_export(self) -> None:
        _course_id, _plan_id = self._seed_partial_unit()
        read = self.ok(
            "course.export.read", {"enrollment_id": "enr_partial"}
        )["result"]
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "unit_still_partial")
        self.assertIn("still being prepared", read["blocked_message"])
        error = self.err(
            "course.export",
            {
                "enrollment_id": "enr_partial",
                "expected_content_hash": "sha256:" + "0" * 64,
            },
            idempotency_key="key-partial-unit",
        )
        self.assertEqual(error["details"]["reason"], "unit_still_partial")

    def test_a_partial_unit_cannot_be_given_lessons(self) -> None:
        _course_id, plan_id = self._seed_partial_unit()
        lesson_llm = FakeLLM({})
        connection = db.connect()
        try:
            with self.assertRaises(gen.GenerationRejected) as caught:
                gen.run_lesson_job(
                    connection,
                    {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                    lesson_llm,
                    plan_id=plan_id,
                    unit_ordinal=1,
                    now=T0,
                )
        finally:
            connection.close()
        self.assertIn("only part of its sections", str(caught.exception))
        self.assertEqual(lesson_llm.requests, [], "the refusal spends nothing")


if __name__ == "__main__":
    unittest.main()
