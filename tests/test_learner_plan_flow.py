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

from coursebook import db, domain, generation, job_service

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
                        "coursebook.plan.validate": blueprint_response(validation_pass()),
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
        finally:
            connection.close()
        self.assertEqual(result["course_id"], flow["course_id"])
        self.assertEqual(result["status"], "draft")
        # The generated draft is the newest version; the course.create draft stays version 1.
        self.assertEqual(int(result["plan_version"]), 2)
        outline = self.ok("course.outline", {"enrollment_id": flow["enrollment_id"]})["result"]
        self.assertEqual(outline["plan"]["plan_id"], result["plan_id"])
        self.assertEqual(outline["plan"]["state"], "draft")
        self.assertGreater(len(outline["objectives"]), 0)

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
                        "coursebook.plan.validate": blueprint_response(validation_pass()),
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
                        "coursebook.unit_sections.validate": blueprint_response(validation_pass()),
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


if __name__ == "__main__":
    unittest.main()
