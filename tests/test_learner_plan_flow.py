"""H-02: a learner goal reaches the real plan job, approval and lessons.

These are backend/RPC cases over the real `coursebook.api.dispatch` path and a real migrated SQLite
database. They send the **same payloads** `desktop/plugin.js` sends (the JS half is asserted
separately in `test_desktop_create_flow.py`), so this file pins what the wire does with them:

* `course.create` with the v10 capability inputs, `enrollment.create`, then one `jobs.create` whose
  brief is the closed `plan_brief`;
* that job is the one the executor's plan stage can actually run, and a retried `jobs.create` with
  the same idempotency key mints no second job;
* the generated draft is approvable from the learner surface **only** with the kernel digest
  `plan.approve` fences — the generation digest `course.outline` echoes is refused;
* the lessons stage can then run against the approved plan.

No prepared pack is involved: the plan comes from the real offline generation pipeline with the
deterministic fake provider, as in `test_plan_approval.py`.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, domain, executor, generation, job_service

from tests.blueprint_support import (
    blueprint_plan,
    response as blueprint_response,
    unit_sections_document,
    validation_pass,
)
from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

GOAL = "Order coffee and ask for the bill in Kyoto, politely."
TITLE = "Coffee in Kyoto"
RECIPE = "committed"
DIALS = {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"}


def learner_plan() -> dict:
    """A schema-valid blueprint plan for the learner's short, committed course."""
    return blueprint_plan(scope="short", units=1, objectives_per_unit=3, recipe="committed")


def learner_course_payload() -> dict:
    """Exactly what `courseCreatePayload` sends for a Japanese short course at L0."""
    return {
        "title": TITLE,
        "recipe": RECIPE,
        "goal": GOAL,
        "dials": DIALS,
        "locale": "ja-JP",
        "level": "L0",
        "subject_domain": "language",
        "scope": "short",
    }


def learner_plan_brief(course_id: str, enrollment_id: str) -> dict:
    """Exactly what `planJobBrief` sends after the course and enrolment exist."""
    return {
        "stage": "plan",
        "course_id": course_id,
        "enrollment_id": enrollment_id,
        "goal": GOAL,
        "recipe": RECIPE,
        "dials": DIALS,
        "locale": "ja-JP",
        "level": "L0",
        "subject_domain": "language",
        "scope": "short",
    }


class LearnerPlanFlowTest(KernelCase):
    # ── the create → job sequence ───────────────────────────────────────────
    def create_with_plan_job(self) -> dict:
        created = self.ok("course.create", learner_course_payload(), idempotency_key="cb-create-1")
        course_id = created["result"]["course_id"]
        draft_plan_id = created["result"]["plan_id"]
        enrolled = self.ok(
            "enrollment.create",
            {"course_id": course_id, "learner_label": TITLE},
            idempotency_key="cb-create-1-enroll",
        )
        enrollment_id = enrolled["result"]["enrollment_id"]
        brief = learner_plan_brief(course_id, enrollment_id)
        job = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key="cb-create-1-plan",
        )
        return {
            "course_id": course_id,
            "draft_plan_id": draft_plan_id,
            "enrollment_id": enrollment_id,
            "brief": brief,
            "job_id": job["result"]["job_id"],
        }

    def test_course_stores_the_declared_capability_inputs(self) -> None:
        flow = self.create_with_plan_job()
        course = self.ok("course.get", {"course_id": flow["course_id"]})["result"]["course"]
        self.assertEqual(course["level"], "L0")
        self.assertEqual(course["subject_domain"], "language")
        self.assertEqual(course["scope"], "short")
        self.assertEqual(course["locale"], "ja-JP")

    def test_the_job_is_queued_with_the_declared_brief(self) -> None:
        flow = self.create_with_plan_job()
        job = self.ok("jobs.get", {"job_id": flow["job_id"]})["result"]["job"]
        self.assertEqual(job["kind"], "plan")
        self.assertEqual(job["state"], "queued")
        for field, value in flow["brief"].items():
            self.assertEqual(job["brief"][field], value, field)

    def test_a_cancelled_job_is_terminal_and_a_new_key_is_a_new_job(self) -> None:
        flow = self.create_with_plan_job()
        cancelled = self.ok("jobs.cancel", {"job_id": flow["job_id"]})["result"]
        self.assertEqual(cancelled["state"], "cancelled")
        # Cancelling again is a typed refusal, not a silent state change.
        error = self.err("jobs.cancel", {"job_id": flow["job_id"]})
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")
        # Recovery uses a fresh key: the cancelled job is not "resumed" by pretending.
        second = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": flow["brief"]},
            idempotency_key="cb-create-1-plan-retry",
        )["result"]
        self.assertNotEqual(second["job_id"], flow["job_id"])
        self.assertEqual(second["state"], "queued")
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs WHERE kind = 'plan'")), 2)

    def test_a_retried_create_mints_no_second_job(self) -> None:
        flow = self.create_with_plan_job()
        again = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": flow["brief"]},
            idempotency_key="cb-create-1-plan",
        )
        self.assertEqual(again["result"]["job_id"], flow["job_id"])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM jobs WHERE kind = 'plan'")), 1
        )

    def test_jobs_list_reattaches_by_enrollment(self) -> None:
        flow = self.create_with_plan_job()
        listed = self.ok("jobs.list", {"enrollment_id": flow["enrollment_id"], "kind": ["plan"]})
        ids = [job["job_id"] for job in listed["result"]["jobs"]]
        self.assertEqual(ids, [flow["job_id"]])

    def test_a_brief_outside_the_closed_schema_is_refused(self) -> None:
        flow = self.create_with_plan_job()
        bad = dict(flow["brief"])
        bad["invented_input"] = "typo"
        error = self.err(
            "jobs.create", {"kind": "plan", "brief": bad}, idempotency_key="cb-create-bad"
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")

    def test_the_plan_stage_runs_against_the_created_course(self) -> None:
        flow = self.create_with_plan_job()
        job = plan_job(job_id=flow["job_id"])
        job["brief"] = dict(flow["brief"])
        connection = db.connect()
        try:
            result = generation.run_plan_job(
                connection,
                job,
                FakeLLM(
                    {
                        "coursebook.plan.generate": blueprint_response(learner_plan()),
                        "coursebook.plan.validate": blueprint_response(
                            validation_pass(), model="fake-independent-validator"
                        ),
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
        finally:
            connection.close()
        self.assertEqual(result["course_id"], flow["course_id"])
        self.assertEqual(result["status"], "draft")
        # H-190: the authored document lands on the plan id ``course.create`` already returned.
        # Generation must not mint a second plan beside the course's empty draft, because the
        # learner surface approves the id it was handed at creation.
        self.assertEqual(result["plan_id"], flow["draft_plan_id"])
        self.assertEqual(int(result["plan_version"]), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) AS n FROM plans WHERE course_id = ?", (flow["course_id"],)),
            1,
        )
        outline = self.ok("course.outline", {"enrollment_id": flow["enrollment_id"]})["result"]
        self.assertEqual(outline["plan"]["plan_id"], flow["draft_plan_id"])
        self.assertEqual(outline["plan"]["state"], "draft")
        self.assertGreater(len(outline["objectives"]), 0)
        # The id the caller holds is approvable, and a read on it carries the authored
        # objectives. Before H-190 this id pointed at the empty course.create draft and
        # ``plan.approve`` refused with "an empty plan cannot be approved".
        connection = db.connect()
        try:
            authored = generation.plan_document(connection, flow["draft_plan_id"])
        finally:
            connection.close()
        self.assertEqual(authored["plan_id"], flow["draft_plan_id"])
        self.assertGreater(len(authored["objectives"]), 0)
        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": flow["enrollment_id"],
                "plan_id": flow["draft_plan_id"],
                "plan_hash": domain.plan_hash(flow["draft_plan_id"]),
            },
            expected_revision=0,
            idempotency_key="cb-h190-approve-created-id",
        )
        self.assertEqual(approved["result"]["revision"], 1)
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (flow["draft_plan_id"],)), "approved"
        )

    # ── the hash rule ───────────────────────────────────────────────────────
    def generated_draft(self) -> dict:
        flow = self.create_with_plan_job()
        job = plan_job(job_id=flow["job_id"])
        job["brief"] = dict(flow["brief"])
        connection = db.connect()
        try:
            generated = generation.run_plan_job(
                connection,
                job,
                FakeLLM(
                    {
                        "coursebook.plan.generate": blueprint_response(learner_plan()),
                        "coursebook.plan.validate": blueprint_response(
                            validation_pass(), model="fake-independent-validator"
                        ),
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
        finally:
            connection.close()
        flow["generated"] = generated
        return flow

    def test_the_generation_digest_is_refused_by_plan_approve(self) -> None:
        flow = self.generated_draft()
        outline = self.ok("course.outline", {"enrollment_id": flow["enrollment_id"]})["result"]
        generation_digest = outline["plan"]["plan_hash"]
        # `course.outline` echoes the digest generation stored; `plan.approve` fences on the kernel
        # digest recomputed from the plan rows. They are different functions.
        self.assertEqual(generation_digest, flow["generated"]["plan_hash"])
        error = self.err(
            "plan.approve",
            {
                "enrollment_id": flow["enrollment_id"],
                "plan_id": outline["plan"]["plan_id"],
                "plan_hash": generation_digest,
            },
            expected_revision=0,
            idempotency_key="cb-approve-generation-digest",
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertIn("current_plan_hash", error["details"])
        self.assertNotEqual(error["details"]["current_plan_hash"], generation_digest)

    def test_the_learner_surface_approves_a_real_generated_plan(self) -> None:
        flow = self.generated_draft()
        plan_id = flow["generated"]["plan_id"]
        # What `parent.blueprint.read` serves, which `StudioPlanView.approvePlan` sends.
        book = self.ok("parent.blueprint.read", {"course_id": flow["course_id"]})["result"]
        self.assertEqual(book["plan"]["plan_id"], plan_id)
        kernel_hash = book["plan"]["plan_hash"]
        self.assertEqual(kernel_hash, domain.plan_hash(plan_id))

        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": flow["enrollment_id"],
                "plan_id": plan_id,
                "plan_hash": kernel_hash,
            },
            expected_revision=0,
            idempotency_key="cb-plan-approve",
        )
        self.assertEqual(approved["result"]["revision"], 1)
        self.assertEqual(approved["result"]["plan_hash"], kernel_hash)
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (plan_id,)), "approved"
        )

    def test_lessons_stage_runs_against_the_approved_plan(self) -> None:
        flow = self.generated_draft()
        plan_id = flow["generated"]["plan_id"]
        book = self.ok("parent.blueprint.read", {"course_id": flow["course_id"]})["result"]
        self.ok(
            "plan.approve",
            {
                "enrollment_id": flow["enrollment_id"],
                "plan_id": plan_id,
                "plan_hash": book["plan"]["plan_hash"],
            },
            expected_revision=0,
            idempotency_key="cb-plan-approve",
        )
        lessons_brief = {
            "stage": "lessons",
            "plan_id": plan_id,
            "enrollment_id": flow["enrollment_id"],
            "unit_ordinal": 1,
        }
        job = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": lessons_brief},
            idempotency_key=f"cb-lessons-{plan_id}",
        )["result"]
        self.assertEqual(
            self.ok(
                "jobs.create",
                {"kind": "plan", "brief": lessons_brief},
                idempotency_key=f"cb-lessons-{plan_id}",
            )["result"]["job_id"],
            job["job_id"],
        )
        plan = learner_plan()
        unit = plan["units"][0]
        objectives = [item for item in plan["objectives"] if int(item["unit_ref"]) == 1]
        connection = db.connect()
        try:
            # A blueprint plan has no sections until the unit stage authors them.
            generation.run_unit_sections_job(
                connection,
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                FakeLLM(
                    {
                        "coursebook.unit_sections.generate": blueprint_response(
                            unit_sections_document(unit=unit, objectives=objectives)
                        ),
                        "coursebook.unit_sections.validate": blueprint_response(
                            validation_pass(), model="fake-independent-validator"
                        ),
                    }
                ),
                plan_id=plan_id,
                unit_ordinal=1,
                now=NOW,
            )
            result = generation.run_lesson_job(
                connection,
                {"job_id": job["job_id"], "brief": lessons_brief},
                FakeLLM(
                    {
                        "coursebook.lesson.generate": lesson_from_request(),
                        "coursebook.lesson.validate": validation_from_fixture("validation_pass"),
                    }
                ),
                plan_id=plan_id,
                unit_ordinal=1,
                now=NOW,
                budget=generation.CostBudget(max_calls=32),
            )
        finally:
            connection.close()
        self.assertEqual(result["plan_id"], plan_id)
        self.assertEqual(result["unit_ordinal"], 1)
        self.assertGreater(len(result.get("lessons") or []), 0)


class LearnerPlanJobServiceTest(KernelCase):
    """The job service's own idempotency rule, without the RPC envelope on top."""

    def test_create_is_idempotent_on_the_operation_id(self) -> None:
        first = job_service.create("plan", learner_plan_brief("course_x", "enr_x"), operation_id="op-1")
        second = job_service.create("plan", learner_plan_brief("course_x", "enr_x"), operation_id="op-1")
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs")), 1)


class LearnerBlueprintLessonPathTest(KernelCase):
    """H-184: the Desktop's lessons payload reaches an authored page.

    ``generateLessons`` posts ``{stage:'lessons', plan_id, enrollment_id}`` with **no**
    ``unit_ordinal``. These cases send that exact payload through ``jobs.create`` and the real
    pump, then read the stored rows. No unit is hand-inserted into the brief, and the approval
    gate is still the one ``plan.approve`` binds.
    """

    def plan_llm(self, plan: dict) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.plan.generate": blueprint_response(plan),
                "coursebook.plan.validate": blueprint_response(
                    validation_pass(), model="fake-independent-validator"
                ),
            }
        )

    def section_llm(self, plan: dict, unit_ordinal: int) -> FakeLLM:
        unit = next(item for item in plan["units"] if int(item["ordinal"]) == unit_ordinal)
        objectives = [
            item for item in plan["objectives"] if int(item["unit_ref"]) == unit_ordinal
        ]
        reviews = int(unit["target_lessons"]) - len(objectives)
        return FakeLLM(
            {
                "coursebook.unit_sections.generate": blueprint_response(
                    unit_sections_document(unit=unit, objectives=objectives, reviews=max(0, reviews))
                ),
                "coursebook.unit_sections.validate": blueprint_response(
                    validation_pass(), model="fake-independent-validator"
                ),
            }
        )

    def lesson_llm(self, *, fail_on: int | None = None) -> FakeLLM:
        calls = {"n": 0}

        def author(request):  # noqa: ANN001 - the same seam FakeLLM drives
            calls["n"] += 1
            if fail_on is not None and calls["n"] == fail_on:
                raise generation.ProviderTimeout("provider deadline hit")
            return lesson_from_request()(request)

        return FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture("validation_pass"),
            }
        )

    def path_llm(self, plan: dict, units: list[int], *, fail_on: int | None = None) -> FakeLLM:
        script: dict = {}
        for ordinal in units:
            script.update(self.section_llm(plan, ordinal).script)
        script.update(self.lesson_llm(fail_on=fail_on).script)
        return FakeLLM(script)

    def approved_blueprint_plan(self, plan: dict, *, approve: bool = True) -> dict:
        """course → enrollment → plan job (pumped) → approval, all through the RPC path."""
        created = self.ok("course.create", learner_course_payload(), idempotency_key="cb-create-1")
        course_id = created["result"]["course_id"]
        enrollment_id = self.new_enrollment(course_id, label=TITLE)
        brief = learner_plan_brief(course_id, enrollment_id)
        plan_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": brief}, idempotency_key="cb-create-1-plan"
        )["result"]["job_id"]
        executor.pump_once(llm=self.plan_llm(plan), search=FakeSearch(), now=NOW)
        plan_run = self.ok("jobs.get", {"job_id": plan_job_id})["result"]["job"]
        self.assertEqual(plan_run["state"], "completed")
        plan_id = plan_run["checkpoint"]["plan_id"]
        # What `parent.blueprint.read` serves, which the approve button sends.
        book = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        self.assertEqual(book["plan"]["plan_id"], plan_id)
        self.assertEqual(book["plan"]["state"], "draft")
        if approve:
            approved = self.ok(
                "plan.approve",
                {
                    "enrollment_id": enrollment_id,
                    "plan_id": plan_id,
                    "plan_hash": book["plan"]["plan_hash"],
                },
                expected_revision=0,
                idempotency_key="cb-plan-approve",
            )["result"]
            self.assertEqual(approved["plan_hash"], domain.plan_hash(plan_id))
        return {
            "course_id": course_id,
            "enrollment_id": enrollment_id,
            "plan_id": plan_id,
            "plan_job_id": plan_job_id,
        }

    def desktop_lessons_brief(self, flow: dict) -> dict:
        """Exactly ``generateLessons``'s brief: no unit_ordinal, by design."""
        return {
            "stage": "lessons",
            "plan_id": flow["plan_id"],
            "enrollment_id": flow["enrollment_id"],
        }

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]

    def stored_lessons(self, plan_id: str) -> list[dict]:
        with db.read() as connection:
            rows = connection.execute(
                "SELECT l.id, l.state, l.page_json FROM gen_lessons l"
                " JOIN gen_plan_sections s ON s.id = l.section_id"
                " WHERE s.plan_id = ? ORDER BY s.ordinal",
                (plan_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── one unit: the Desktop payload authors a servable page ────────────────
    def test_the_desktop_lessons_payload_authors_a_page(self) -> None:
        plan = learner_plan()
        flow = self.approved_blueprint_plan(plan)
        brief = self.desktop_lessons_brief(flow)
        job_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}",
        )["result"]["job_id"]

        # The plan's own job is done; the lessons job is the only queued work the pump sees.
        points_before = self.ok("parent.blueprint.read", {"course_id": flow["course_id"]})["result"]
        plans_before = int(self.scalar("SELECT COUNT(*) FROM plans"))
        executor.pump_once(llm=self.path_llm(plan, [1]), search=FakeSearch(), now=NOW)

        run = self.job(job_id)
        self.assertEqual(run["state"], "completed", run.get("error"))
        self.assertEqual(run["checkpoint"]["unit_ordinal"], 1)
        self.assertEqual(run["checkpoint"]["sections_total"], 3)
        self.assertEqual(run["checkpoint"]["lessons"], 3)
        self.assertEqual(run["checkpoint"]["next_unit_ordinal"], None)
        self.assertTrue(run["checkpoint"]["units_complete_all"])
        self.assertEqual(run["checkpoint"]["last_stage"], "lessons")
        self.assertEqual(run["progress"]["steps_done"], 2)
        self.assertEqual(run["progress"]["steps_total"], 2)

        lessons = self.stored_lessons(flow["plan_id"])
        self.assertEqual(len(lessons), 3)
        for lesson in lessons:
            page = json.loads(str(lesson["page_json"]))
            self.assertTrue(page.get("segments"), "the authored page has no content")
            self.assertTrue(page.get("section_title"))

        # Nothing invented behind the bridge: the same plan row, still approved, one plan version.
        after = self.ok("parent.blueprint.read", {"course_id": flow["course_id"]})["result"]
        self.assertEqual(after["plan"]["plan_id"], points_before["plan"]["plan_id"])
        self.assertEqual(after["plan"]["plan_hash"], points_before["plan"]["plan_hash"])
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (flow["plan_id"],)), "approved"
        )
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM plans")), plans_before)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs")), 2)

        # Same key, same job: a double click replays, it does not queue a second spend.
        replay = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}",
        )["result"]
        self.assertEqual(replay["job_id"], job_id)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs")), 2)

    # ── no approval, no lesson ────────────────────────────────────────────────
    def test_an_unapproved_plan_still_authors_nothing(self) -> None:
        plan = learner_plan()
        flow = self.approved_blueprint_plan(plan, approve=False)
        brief = self.desktop_lessons_brief(flow)
        job_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}",
        )["result"]["job_id"]
        executor.pump_once(llm=self.path_llm(plan, [1]), search=FakeSearch(), now=NOW)

        run = self.job(job_id)
        self.assertEqual(run["state"], "failed")
        self.assertIn("approved", (run["error"] or {}).get("message", ""))
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_plan_sections")), 0)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_lessons")), 0)

    # ── multiple units: one job authors one unit, and says which one is next ──
    def test_multiple_units_are_offered_one_at_a_time_with_honest_state(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=3, recipe="committed")
        flow = self.approved_blueprint_plan(plan)
        brief = self.desktop_lessons_brief(flow)

        first_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}-1",
        )["result"]["job_id"]
        executor.pump_once(llm=self.path_llm(plan, [1]), search=FakeSearch(), now=NOW)
        first = self.job(first_id)
        self.assertEqual(first["state"], "completed", first.get("error"))
        self.assertEqual(first["checkpoint"]["unit_ordinal"], 1)
        self.assertEqual(first["checkpoint"]["next_unit_ordinal"], 2)
        self.assertEqual(first["checkpoint"]["units_complete"], [1])
        self.assertEqual(first["checkpoint"]["units_total"], 2)
        self.assertFalse(first["checkpoint"]["units_complete_all"])
        self.assertEqual(first["checkpoint"]["next_unit_to_author"], 2)
        self.assertEqual(len(self.stored_lessons(flow["plan_id"])), 3)

        # The next unit is a fresh job with a fresh key — exactly what the path surface offers.
        second_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}-2",
        )["result"]["job_id"]
        executor.pump_once(llm=self.path_llm(plan, [2]), search=FakeSearch(), now=NOW)
        second = self.job(second_id)
        self.assertEqual(second["state"], "completed", second.get("error"))
        self.assertEqual(second["checkpoint"]["unit_ordinal"], 2)
        self.assertEqual(second["checkpoint"]["next_unit_ordinal"], None)
        self.assertEqual(second["checkpoint"]["units_complete"], [1, 2])
        self.assertTrue(second["checkpoint"]["units_complete_all"])
        self.assertEqual(len(self.stored_lessons(flow["plan_id"])), 6)

        # A plan whose every unit is authored is an honest no-op, not a failure or a fake pass.
        third_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}-3",
        )["result"]["job_id"]
        no_calls = FakeLLM({})
        executor.pump_once(llm=no_calls, search=FakeSearch(), now=NOW)
        third = self.job(third_id)
        self.assertEqual(third["state"], "completed", third.get("error"))
        self.assertEqual(no_calls.requests, [], "a complete course must spend nothing")
        self.assertTrue(third["checkpoint"]["units_complete_all"])
        self.assertEqual(third["checkpoint"]["units_complete"], [1, 2])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_lessons")), 6)

    # ── retry: the failed unit resumes instead of skipping ahead ─────────────
    def test_a_timed_out_lesson_stage_resumes_the_same_unit_on_retry(self) -> None:
        plan = learner_plan()
        flow = self.approved_blueprint_plan(plan)
        brief = self.desktop_lessons_brief(flow)
        first_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}",
        )["result"]["job_id"]
        executor.pump_once(
            llm=self.path_llm(plan, [1], fail_on=2), search=FakeSearch(), now=NOW
        )
        failed = self.job(first_id)
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["checkpoint"]["unit_ordinal"], 1)
        self.assertEqual(len(self.stored_lessons(flow["plan_id"])), 1, "the first lesson is durable")
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_plan_sections")), 3)

        retry_llm = self.path_llm(plan, [1])
        retry_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-lessons-{flow['plan_id']}-retry",
        )["result"]["job_id"]
        executor.pump_once(llm=retry_llm, search=FakeSearch(), now=NOW)
        retried = self.job(retry_id)
        self.assertEqual(retried["state"], "completed", retried.get("error"))
        # The retry resumed unit 1, not unit 2, and re-authored only the two missing lessons.
        self.assertEqual(retried["checkpoint"]["unit_ordinal"], 1)
        self.assertEqual(retry_llm.calls_for("coursebook.lesson.generate"), 2)
        self.assertEqual(len(self.stored_lessons(flow["plan_id"])), 3)

    # ── no unit dimension: a pre-blueprint plan still authors every section ───
    def test_a_legacy_plan_without_units_keeps_the_one_stage_path(self) -> None:
        brief = {
            "goal": "Order coffee in Japanese",
            "recipe": "committed",
            "dials": {},
            "level": "L0",
            "locale": "ja-JP",
        }
        plan_job_id = self.ok("jobs.create", {"kind": "plan", "brief": brief})["result"]["job_id"]
        plan_llm = FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture("plan_ja"),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        executor.pump_once(llm=plan_llm, search=FakeSearch(), now=NOW)
        run = self.job(plan_job_id)
        self.assertEqual(run["state"], "completed", run.get("error"))
        plan_id = run["checkpoint"]["plan_id"]
        course_id = str(self.scalar("SELECT course_id FROM plans WHERE id = ?", (plan_id,)))
        enrollment_id = self.new_enrollment(course_id, label="Learner")
        self.assertEqual(self.approve(enrollment_id, plan_id, 0), 1)

        lessons_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}},
        )["result"]["job_id"]
        lesson_llm = FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        executor.pump_once(llm=lesson_llm, search=FakeSearch(), now=NOW)
        legacy = self.job(lessons_id)
        self.assertEqual(legacy["state"], "completed", legacy.get("error"))
        self.assertIsNone(legacy["checkpoint"]["unit_ordinal"])
        self.assertTrue(legacy["checkpoint"]["units_none"])
        self.assertEqual(len(self.stored_lessons(plan_id)), 4)


if __name__ == "__main__":
    unittest.main()
