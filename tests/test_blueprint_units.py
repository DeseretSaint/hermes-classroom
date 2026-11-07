"""H-21b: plan schema v2 and unit-scoped authoring stages.

Design authority: ``docs/COURSE-BLUEPRINT.md`` §5, §7, §12 item 7. Every case here is a fact the
kernel can prove offline: a rule refusal, a stored row count, a reused checkpoint, or a cancelled
stage that spent nothing. No test presents invented provider output as a real call.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, domain, executor, generation as gen, job_service

from tests.blueprint_support import (
    NOW,
    blueprint_plan,
    response,
    unit_sections_document,
    validation_pass,
)
from tests.kernel_support import KernelCase
from tests.test_generation import FakeLLM, lesson_from_request, validation_from_fixture

T0 = NOW


def _plan_rules(plan: dict, *, recipe: str = "casual", ledger=(), locale=None, scope=None) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe=recipe,
        dials={},
        locale=locale,
        ledger=list(ledger),
        scope=scope if scope is not None else plan.get("scope"),
    )


class PlanSchemaV2RulesTest(unittest.TestCase):
    """§12 item 7: the scope boundary matrix and the one-off shape."""

    def test_scope_boundary_matrix(self) -> None:
        cases = [
            ("single", 1, 1, True),
            ("single", 1, 2, False),
            ("short", 2, 3, True),
            ("short", 3, 2, True),
            ("short", 4, 1, False),
            ("full", 2, 6, True),
            ("full", 1, 12, False),
            ("full", 2, 5, False),
        ]
        for scope, units, per_unit, accepted in cases:
            with self.subTest(scope=scope, units=units, per_unit=per_unit):
                plan = blueprint_plan(scope=scope, units=units, objectives_per_unit=per_unit)
                if accepted:
                    _plan_rules(plan, scope=scope)
                else:
                    with self.assertRaises(gen._RuleViolation):
                        _plan_rules(plan, scope=scope)

    def test_one_off_is_exactly_one_objective_and_one_verification(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="one_off")
        _plan_rules(plan, recipe="one_off", scope="single")
        self.assertEqual(len(plan["objectives"]), 1)
        self.assertEqual(plan["check_plan"][0]["kind"], "verification")

        two = blueprint_plan(scope="single", units=1, objectives_per_unit=2, recipe="one_off")
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(two, recipe="one_off", scope="single")
        self.assertTrue(any("exactly one" in reason for reason in caught.exception.reasons))

    def test_check_plan_v2_has_no_count_or_independent_evidence(self) -> None:
        self.assertNotIn("count", gen.CHECK_PLAN_SCHEMA_V2["properties"])
        self.assertNotIn("independent_evidence", gen.CHECK_PLAN_SCHEMA_V2["properties"])
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        plan["check_plan"][0]["count"] = 2
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(plan, scope="single")
        self.assertTrue(any("removed v1 field" in reason for reason in caught.exception.reasons))

    def test_target_lessons_must_fit_the_declared_schedule(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        plan["time_estimate"]["weeks"] = 1
        plan["time_estimate"]["sessions_per_week"] = 1
        plan["units"][0]["target_lessons"] = 2
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(plan, scope="single")
        self.assertTrue(any("allows" in reason for reason in caught.exception.reasons))

    def test_prerequisite_edges_point_backwards(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        plan["units"][0]["prereq_unit_ordinals"] = [2]
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(plan, scope="short")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("strictly lower", reasons)
        self.assertIn("unit 1 cannot declare", reasons)


class UnitStageCase(KernelCase):
    """A migrated profile database plus a seeded, approved blueprint plan."""

    def setUp(self) -> None:
        super().setUp()
        with db.transaction() as connection:
            gen.ensure_schema(connection)

    def seed(
        self,
        plan: dict,
        *,
        recipe: str = "casual",
        approved: bool = True,
    ) -> tuple[str, str]:
        course_id = "crs_blueprint_test"
        plan_id = "pln_blueprint_test"
        digest = gen.plan_hash(plan)
        stamp = T0.isoformat()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, dials_json, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    course_id,
                    plan["title"],
                    recipe,
                    plan["learner_outcome"],
                    "{}",
                    "active",
                    0,
                    stamp,
                    stamp,
                ),
            )
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json,"
                " created_at, approved_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    plan_id,
                    course_id,
                    1,
                    "approved" if approved else "draft",
                    digest,
                    "{}",
                    stamp,
                    stamp if approved else None,
                ),
            )
            unit_ids: dict[int, str] = {}
            for unit in plan["units"]:
                unit_id = f"unt_{unit['ordinal']}"
                unit_ids[int(unit["ordinal"])] = unit_id
                connection.execute(
                    "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                    " prereq_unit_ordinals_json, target_lessons, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        unit_id,
                        plan_id,
                        int(unit["ordinal"]),
                        unit["title"],
                        unit["goal"],
                        json.dumps(unit.get("prereq_unit_ordinals") or []),
                        int(unit["target_lessons"]),
                        stamp,
                    ),
                )
            for objective in plan["objectives"]:
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at, unit_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"obj_{objective['ordinal']}",
                        plan_id,
                        int(objective["ordinal"]),
                        objective["title"],
                        objective["evidence_target"],
                        json.dumps(objective["evidence_criteria"]),
                        "not_started",
                        1,
                        stamp,
                        unit_ids[int(objective["unit_ref"])],
                    ),
                )
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
                " plan_hash, document_json, research_json, generation_state, validation_id,"
                " result_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "gpd_blueprint_test",
                    plan_id,
                    course_id,
                    "fp-blueprint-test",
                    digest,
                    json.dumps(
                        {
                            "plan": plan,
                            "recipe": recipe,
                            "dials": {},
                            "locale": None,
                            "level": None,
                            "subject_domain": None,
                            "scope": plan.get("scope"),
                            "pipeline_version": gen.PIPELINE_VERSION,
                        }
                    ),
                    json.dumps({"status": "unavailable", "sources": [], "queries": [], "failures": []}),
                    "draft",
                    None,
                    "{}",
                    stamp,
                ),
            )
        return course_id, plan_id

    def unit(self, plan: dict, ordinal: int) -> dict:
        return next(item for item in plan["units"] if int(item["ordinal"]) == ordinal)

    def objectives_for(self, plan: dict, ordinal: int) -> list[dict]:
        return [
            item for item in plan["objectives"] if int(item["unit_ref"]) == ordinal
        ]

    def section_llm(self, plan: dict, *, unit_ordinal: int) -> FakeLLM:
        unit = self.unit(plan, unit_ordinal)
        objectives = self.objectives_for(plan, unit_ordinal)
        reviews = int(unit["target_lessons"]) - len(objectives)
        document = unit_sections_document(unit=unit, objectives=objectives, reviews=max(0, reviews))
        return FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )

    def lesson_llm(self, *, fail_on: int | None = None) -> FakeLLM:
        calls = {"n": 0}

        def author(request):
            calls["n"] += 1
            if fail_on is not None and calls["n"] == fail_on:
                raise gen.ProviderTimeout("provider deadline hit")
            return lesson_from_request()(request)

        return FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )


class UnitSectionsStageTest(UnitStageCase):
    def test_unit_sections_are_stored_with_role_and_unit(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2, reviews=[1, 0])
        _course_id, plan_id = self.seed(plan)
        llm = self.section_llm(plan, unit_ordinal=1)
        result = gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        self.assertEqual(result["unit_ordinal"], 1)
        self.assertEqual(result["sections"], 3)  # 2 owners + 1 review
        self.assertEqual(result["owners"], 2)
        self.assertEqual(result["reviews"], 1)
        with db.read() as connection:
            rows = connection.execute(
                "SELECT section_role, unit_id, objective_refs_json FROM gen_plan_sections"
                " WHERE plan_id = ? ORDER BY ordinal",
                (plan_id,),
            ).fetchall()
        self.assertEqual([row["section_role"] for row in rows], ["owner", "owner", "review"])
        self.assertTrue(all(row["unit_id"] == "unt_1" for row in rows))
        self.assertEqual(json.loads(rows[0]["objective_refs_json"]), [1])
        self.assertEqual(json.loads(rows[2]["objective_refs_json"]), [1, 2])

    def test_rerunning_the_unit_reuses_every_row_and_spends_nothing(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, plan_id = self.seed(plan)
        gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.section_llm(plan, unit_ordinal=1),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        reuse_llm = FakeLLM({})
        result = gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            reuse_llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        self.assertTrue(result["reused"])
        self.assertEqual(reuse_llm.requests, [])
        with db.read() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
        self.assertEqual(int(count), 1)

    def test_a_rule_failing_unit_batch_writes_no_rows_and_fails_the_job(self) -> None:
        """D1/H-42: the unit stage is transactional over its unit.

        The fixture is H-40's partial-batch shape: unit 2 needs two owner sections and the model
        returns one, twice. The batch is discarded, the job fails with the same reasons, and the
        untouched objective still reads ``not_started`` with no check on both learner surfaces.
        """
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        course_id, plan_id = self.seed(plan)
        stamp = T0.isoformat()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO enrollments (id, course_id, learner_label, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                ("enr_d1", course_id, "Learner", "active", 0, stamp, stamp),
            )
        unit_two = next(item for item in plan["units"] if int(item["ordinal"]) == 2)
        authored = [
            objective for objective in plan["objectives"] if int(objective["unit_ref"]) == 2
        ][:1]  # 1 of 2 owner sections: the failing batch
        incomplete = unit_sections_document(unit=unit_two, objectives=authored)
        llm = FakeLLM({"coursebook.unit_sections.generate": response(incomplete)})
        brief = {"stage": "unit_sections", "plan_id": plan_id, "unit_ordinal": 2}
        job_id = job_service.create("plan", brief, now=T0)["job_id"]
        stages = executor.resolvers(llm=llm, search=None, now=T0)["plan"](brief)
        view = job_service.execute(job_id, stages, now=T0)

        self.assertEqual(view["state"], "failed")
        message = view["error"]["message"]
        self.assertIn("objective 4 has no owner section", message)
        self.assertIn("unit 2 targets 2 lesson(s); this batch would leave 1 section(s)", message)
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        with db.read() as connection:
            rows = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE unit_id = 'unt_2'"
            ).fetchone()["n"]
        self.assertEqual(int(rows), 0, "a failed unit batch must leave no durable section row")

        status, outline = domain.course_outline(
            {"enrollment_id": "enr_d1"}, {"contract": "cb.rpc", "contract_version": 11}
        )
        self.assertEqual(status, 0)
        objective = next(item for item in outline["objectives"] if int(item["ordinal"]) == 4)
        self.assertEqual(objective["state"], "not_started")
        self.assertEqual(objective["check_state"], "none")
        status, page = domain.lesson_page(
            {"enrollment_id": "enr_d1", "objective_id": objective["objective_id"]},
            {"contract": "cb.rpc", "contract_version": 11},
        )
        self.assertEqual(status, 0)
        self.assertEqual(page["state"], "not_started")
        self.assertIsNone(page["document"]["check_id"])
        self.assertEqual(page["checks"], [])

        # Cleanly resumable: the same brief run with a complete batch authors the whole unit,
        # because the failed attempt left nothing to be mistaken for finished work.
        retry = gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 2}},
            self.section_llm(plan, unit_ordinal=2),
            plan_id=plan_id,
            unit_ordinal=2,
            now=T0,
        )
        self.assertEqual(retry["sections"], 2)
        self.assertEqual(retry["owners"], 2)
        with db.read() as connection:
            rows = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE unit_id = 'unt_2'"
            ).fetchone()["n"]
        self.assertEqual(int(rows), 2)

    def test_a_validator_rejected_unit_batch_is_discarded_not_parked(self) -> None:
        """The same transactional rule covers a validator rejection, not just rule violations."""
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, plan_id = self.seed(plan)
        document = unit_sections_document(
            unit=plan["units"][0], objectives=plan["objectives"]
        )
        rejected = validation_pass()
        rejected["verdict"] = "reject"
        rejected["rejections"] = [
            {
                "item": "unit_sections",
                "criterion": "objective_alignment",
                "reason": "the lesson intent does not carry the construct",
            }
        ]
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": response(rejected),
            }
        )
        with self.assertRaises(gen.GenerationRejected) as caught:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                llm,
                plan_id=plan_id,
                unit_ordinal=1,
                now=T0,
            )
        self.assertIn("does not carry the construct", str(caught.exception))
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        with db.read() as connection:
            rows = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
            validations = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_validation_records"
                " WHERE subject_kind = 'unit_sections'"
            ).fetchone()["n"]
        self.assertEqual(int(rows), 0)
        self.assertEqual(int(validations), 0, "a discarded batch records no validation")


class BlueprintPlanJobTest(UnitStageCase):
    def plan_llm(self, plan: dict) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.plan.generate": response(plan),
                "coursebook.plan.validate": response(validation_pass()),
            }
        )

    def plan_brief(self, plan: dict) -> dict:
        return {
            "stage": "plan",
            "goal": "Do the scoped thing",
            "recipe": "casual",
            "dials": {},
            "locale": None,
            "scope": plan["scope"],
        }

    def test_the_blueprint_stage_writes_units_and_no_sections(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=3)
        result = gen.run_plan_job(
            db.connect(),
            {"job_id": None, "brief": self.plan_brief(plan)},
            self.plan_llm(plan),
            None,
            now=T0,
        )
        self.assertEqual(result["plan_schema"], gen.PLAN_SCHEMA_V2_NAME)
        self.assertEqual(result["units"], 2)
        self.assertEqual(result["objectives"], 6)
        self.assertEqual(result["sections"], 0)
        self.assertEqual(result["next_unit_ordinal"], 1)
        with db.read() as connection:
            units = connection.execute("SELECT COUNT(*) AS n FROM plan_units").fetchone()["n"]
            objectives = connection.execute(
                "SELECT COUNT(*) AS n FROM objectives WHERE unit_id IS NOT NULL"
            ).fetchone()["n"]
            sections = connection.execute("SELECT COUNT(*) AS n FROM gen_plan_sections").fetchone()["n"]
            document = connection.execute("SELECT document_json FROM gen_plan_documents").fetchone()
        self.assertEqual(int(units), 2)
        self.assertEqual(int(objectives), 6)
        self.assertEqual(int(sections), 0, "sections are authored by the unit stage, not the plan")
        stored = json.loads(document["document_json"])["plan"]
        self.assertEqual(stored["plan_schema"], gen.PLAN_SCHEMA_V2_NAME)

    def test_the_executor_never_chains_the_next_unit(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=3)
        brief = self.plan_brief(plan)
        job_id = job_service.create("plan", brief, now=T0)["job_id"]
        stages = executor.resolvers(llm=self.plan_llm(plan), search=None, now=T0)["plan"](brief)
        view = job_service.execute(job_id, stages, now=T0)
        self.assertEqual(view["state"], "completed")
        self.assertEqual(view["checkpoint"]["units"], 2)
        self.assertEqual(view["checkpoint"]["next_unit_ordinal"], 1)
        with db.read() as connection:
            jobs = connection.execute("SELECT kind, brief_json FROM jobs").fetchall()
            sections = connection.execute("SELECT COUNT(*) AS n FROM gen_plan_sections").fetchone()["n"]
        self.assertEqual(len(jobs), 1, "the plan stage must not enqueue a unit job")
        for row in jobs:
            self.assertNotEqual(json.loads(row["brief_json"]).get("stage"), "unit_sections")
        self.assertEqual(int(sections), 0)


class UnitScopedLessonsTest(UnitStageCase):
    def test_lessons_cover_only_the_requested_unit(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        _course_id, plan_id = self.seed(plan)
        for ordinal in (1, 2):
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": ordinal}},
                self.section_llm(plan, unit_ordinal=ordinal),
                plan_id=plan_id,
                unit_ordinal=ordinal,
                now=T0,
            )
        result = gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.lesson_llm(),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        self.assertEqual(result["unit_ordinal"], 1)
        self.assertEqual(result["sections_total"], 2)
        self.assertEqual(result["next_unit_ordinal"], 2)
        with db.read() as connection:
            unit1 = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_lessons l JOIN gen_plan_sections s"
                " ON s.id = l.section_id WHERE s.unit_id = 'unt_1'"
            ).fetchone()["n"]
            unit2 = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_lessons l JOIN gen_plan_sections s"
                " ON s.id = l.section_id WHERE s.unit_id = 'unt_2'"
            ).fetchone()["n"]
        self.assertEqual(int(unit1), 2)
        self.assertEqual(int(unit2), 0, "a lessons job must never author another unit")

    def test_partial_unit_resume_reuses_authored_lessons(self) -> None:
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=2)
        plan["scope"] = "short"
        plan["time_estimate"]["weeks"] = 24
        _course_id, plan_id = self.seed(plan)
        gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.section_llm(plan, unit_ordinal=1),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        with self.assertRaises(gen.ProviderTimeout):
            gen.run_lesson_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                self.lesson_llm(fail_on=2),
                plan_id=plan_id,
                unit_ordinal=1,
                now=T0,
            )
        resume_llm = self.lesson_llm()
        result = gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            resume_llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        self.assertEqual(sum(1 for item in result["lessons"] if item.get("reused")), 1)
        self.assertEqual(resume_llm.calls_for("coursebook.lesson.generate"), 1)
        with db.read() as connection:
            lessons = connection.execute("SELECT COUNT(*) AS n FROM gen_lessons").fetchone()["n"]
            checks = connection.execute("SELECT COUNT(*) AS n FROM checks").fetchone()["n"]
        self.assertEqual(int(lessons), 2)
        self.assertEqual(int(checks), 2, "the retry must not duplicate a check")

    def test_cancel_at_a_unit_boundary_leaves_durable_rows_and_starts_nothing(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=1)
        _course_id, plan_id = self.seed(plan)
        gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            self.section_llm(plan, unit_ordinal=1),
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )
        brief = {"stage": "unit_sections", "plan_id": plan_id, "unit_ordinal": 2}
        created = job_service.create("plan", brief, now=T0)
        job_id = created["job_id"]
        lease = job_service.claim(job_id, owner="unit-test", now=T0)
        job_service.request_cancel(job_id, now=T0)
        stage = executor.resolvers(llm=FakeLLM({}), search=None, now=T0)["plan"](brief)[0]
        with self.assertRaises(job_service.JobCancelled):
            stage.run(lease)
        with db.read() as connection:
            unit2 = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE unit_id = 'unt_2'"
            ).fetchone()["n"]
            unit1 = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE unit_id = 'unt_1'"
            ).fetchone()["n"]
        self.assertEqual(int(unit2), 0)
        self.assertEqual(int(unit1), 1, "already authored work stays durable across a cancel")


class OutlineProjectionTest(UnitStageCase):
    def outline(self, plan_id: str, enrollment_id: str = "enr_test") -> dict:
        status, result = domain.course_outline(
            {"enrollment_id": enrollment_id}, {"contract": "cb.rpc", "contract_version": 11}
        )
        self.assertEqual(status, 0)
        return result

    def library_item(self, enrollment_id: str) -> dict:
        status, result = domain.library_list({}, {"contract": "cb.rpc", "contract_version": 11})
        self.assertEqual(status, 0)
        return next(
            item for item in result["items"] if item["enrollment_id"] == enrollment_id
        )

    def seed_enrollment(self, course_id: str) -> str:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO enrollments (id, course_id, learner_label, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    "enr_test",
                    course_id,
                    "Learner",
                    "active",
                    0,
                    T0.isoformat(),
                    T0.isoformat(),
                ),
            )
        return "enr_test"

    def test_a_blueprint_plan_projects_its_units(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        course_id, plan_id = self.seed(plan)
        enrollment_id = self.seed_enrollment(course_id)
        outline = self.outline(plan_id, enrollment_id)
        units = outline["plan"]["units"]
        self.assertEqual([unit["ordinal"] for unit in units], [1, 2])
        self.assertEqual([unit["title"] for unit in units], [u["title"] for u in plan["units"]])
        self.assertEqual(len(units[0]["objectives"]), 2)
        self.assertEqual(units[0]["prerequisite_state"], "no_edges")
        self.assertEqual(units[1]["prereq_unit_ordinals"], [1])
        self.assertEqual(units[1]["prerequisite_state"], "unmet")
        self.assertEqual(
            set(units[0].keys()),
            {
                "ordinal",
                "title",
                "goal",
                "prereq_unit_ordinals",
                "prerequisite_state",
                "unmet",
                "objectives",
            },
        )
        # The library card names the unit the learner is currently on.
        label = self.library_item(enrollment_id)["subtitle"]
        self.assertTrue(label.startswith("Unit 1 of 2"), label)
        self.assertIn(plan["units"][0]["title"], label)

    def test_a_legacy_plan_projects_one_implicit_unit(self) -> None:
        stamp = T0.isoformat()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, dials_json, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("crs_legacy", "Legacy course", "casual", "Learn a thing", "{}", "active", 0, stamp, stamp),
            )
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json,"
                " created_at, approved_at) VALUES (?,?,?,?,?,?,?,?)",
                ("pln_legacy", "crs_legacy", 1, "approved", "0" * 64, "{}", stamp, stamp),
            )
            for ordinal in (1, 2):
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        f"obj_legacy_{ordinal}",
                        "pln_legacy",
                        ordinal,
                        f"Legacy objective {ordinal}",
                        "comprehension",
                        "[]",
                        "not_started",
                        1,
                        stamp,
                    ),
                )
            connection.execute(
                "INSERT INTO enrollments (id, course_id, learner_label, status, revision,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                ("enr_legacy", "crs_legacy", "Learner", "active", 0, stamp, stamp),
            )
        outline = self.outline("pln_legacy", "enr_legacy")
        units = outline["plan"]["units"]
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["title"], "Legacy course")
        self.assertEqual(units[0]["prerequisite_state"], "no_edges")
        self.assertEqual(len(units[0]["objectives"]), 2)
        # No unit rows: the library card keeps the learner label it already had.
        self.assertEqual(self.library_item("enr_legacy")["subtitle"], "Learner")


if __name__ == "__main__":
    unittest.main()
