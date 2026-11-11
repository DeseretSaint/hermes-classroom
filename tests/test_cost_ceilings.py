"""H-17 — sized cost ceilings and a typed, resumable ``CostCeilingExceeded``.

The audit (ADVERSARIAL-AUDIT-ROUND2 P1-6) found a flat $0.75 ceiling beside a call ceiling that
scaled to 32: eight sections aborted at call 24 with no recovery hint. These tests pin the two
halves of the fix at the level the kernel operates on:

* the ceiling is *sized* from the plan's section count and declared attempts, and a job whose
  minimum cannot fit is refused before it spends anything;
* a mid-course abort persists a typed checkpoint naming the completed sections, the spend and the
  three legal actions, and a resume reuses those sections instead of re-authoring them;
* a call whose provider reported no cost is charged at the declared estimate, never zero.

Every test is offline: the fake LLM is deterministic and no provider is called.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from coursebook import db
from coursebook import generation as gen
from coursebook import job_service
from tests.kernel_support import KernelCase
from tests.test_generation import (
    NOW,
    FakeLLM,
    GenerationTestBase,
    lesson_from_request,
    validation_from_fixture,
)


def _costly(builder, cost: float = gen.DECLARED_CALL_COST_USD):
    """Wrap a fixture builder so every response reports the same per-call cost."""

    def build(request):
        response = builder(request)
        response.cost_usd = cost
        return response

    return build


class SizedCeilingTest(unittest.TestCase):
    """The arithmetic, before any job exists."""

    def test_a_small_course_fits_the_sized_ceiling(self) -> None:
        preflight = gen.preflight_lesson_cost(4)
        self.assertTrue(preflight.fits_minimum)
        self.assertTrue(preflight.fits_maximum)
        # 4 sections x 2 calls/attempt = 8 minimum; x 2 attempts x 3 calls (generate + validate +
        # truncation re-ask) = 24 worst legal.
        self.assertEqual(preflight.minimum_calls, 8)
        self.assertEqual(preflight.maximum_calls, 24)
        self.assertEqual(gen.lesson_cost_budget(4).max_calls, 24)
        self.assertLessEqual(preflight.minimum_cost_usd, preflight.max_cost_usd)

    def test_the_dollar_ceiling_scales_with_the_plan(self) -> None:
        small = gen.lesson_cost_budget(2)
        medium = gen.lesson_cost_budget(5)
        full = gen.lesson_cost_budget(8)
        # The old flat 0.75 is the floor; anything above two sections must size above it.
        self.assertEqual(small.max_cost_usd, gen.DEFAULT_MAX_COST_USD)
        medium_cost = medium.max_cost_usd
        full_cost = full.max_cost_usd
        assert medium_cost is not None and full_cost is not None
        self.assertAlmostEqual(medium_cost, 30 * gen.DECLARED_CALL_COST_USD)
        self.assertAlmostEqual(full_cost, 48 * gen.DECLARED_CALL_COST_USD)
        self.assertGreater(full.max_cost_usd, gen.DEFAULT_MAX_COST_USD)
        # The audit's exact arithmetic: 8 sections x 6 calls (repair counted) x the measured $0.032
        # was above the flat ceiling. The declared estimate keeps the new ceiling above it.
        self.assertGreater(full.max_cost_usd, 24 * 0.032)

    def test_a_large_course_is_refused_before_it_starts(self) -> None:
        # A future full-course plan at the old flat ceiling: 64 sections need 128 calls minimum.
        budget = gen.CostBudget(max_calls=256, max_cost_usd=0.75)
        preflight = gen.preflight_lesson_cost(64, budget=budget)
        self.assertFalse(preflight.fits_minimum)
        self.assertEqual(preflight.minimum_calls, 128)
        self.assertAlmostEqual(preflight.minimum_cost_usd, 5.12)
        with self.assertRaises(gen.CostPreflightRefused) as raised:
            gen.assert_cost_preflight(64, budget=budget)
        error = raised.exception
        self.assertEqual(error.preflight.section_count, 64)
        self.assertIn("Nothing was spent", str(error))
        self.assertIn(gen.JOB_MAX_COST_ENV, str(error))
        checkpoint = error.to_checkpoint()
        self.assertEqual(checkpoint["kind"], "cost_preflight_refused")
        self.assertEqual(checkpoint["preflight"]["minimum_calls"], 128)
        self.assertEqual(checkpoint["actions"], list(gen.COST_ACTIONS))

    def test_operator_ceilings_are_recorded_with_their_source(self) -> None:
        self.assertEqual(gen.lesson_cost_budget(4).source, "declared")
        with mock.patch.dict(os.environ, {gen.JOB_MAX_COST_ENV: "2.5"}):
            budget = gen.lesson_cost_budget(4)
            self.assertEqual(budget.max_cost_usd, 2.5)
            self.assertEqual(budget.source, "operator_env")
            # A per-job brief decision beats the deployment variable.
            brief = gen.lesson_cost_budget(4, brief_budget_usd=9.0)
            self.assertEqual(brief.max_cost_usd, 9.0)
            self.assertEqual(brief.source, "operator_brief")
            with self.assertRaises(gen.GenerationRejected):
                gen.lesson_cost_budget(4, brief_budget_usd="cheap")
            with self.assertRaises(gen.GenerationRejected):
                gen.lesson_cost_budget(4, brief_budget_usd=0)


class LessonCostRecoveryTest(GenerationTestBase):
    """A mid-course abort leaves durable work and a resume that does not pay for it twice."""

    def lesson_script(self, validate, generate=None) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate or lesson_from_request(),
                "coursebook.lesson.validate": validate,
            }
        )

    def job(self, plan_result: dict, job_id: str = "job-lesson-cost") -> dict:
        return {
            "job_id": job_id,
            "kind": "plan",
            "brief": {"stage": "lessons", "plan_id": plan_result["plan_id"]},
        }

    def test_preflight_refuses_a_lesson_job_before_the_first_call(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(validation_from_fixture())
        usage_before = self.count("usage_events")
        with self.assertRaises(gen.CostPreflightRefused):
            gen.run_lesson_job(
                self.connection,
                self.job(plan_result),
                llm,
                now=NOW,
                budget=gen.CostBudget(max_calls=32, max_cost_usd=0.1),
            )
        self.assertEqual(llm.requests, [])
        self.assertEqual(self.count("usage_events"), usage_before)  # the plan job's spend only
        self.assertEqual(self.count("gen_lessons"), 0)

    def test_mid_course_abort_preserves_completed_pages_and_names_the_actions(self) -> None:
        plan_result = self.approved_plan()
        # Section 1 and 2 each need a rejected attempt then a pass (4 calls each = $0.16 each).
        # Section 3 aborts on its first retry: the ceiling is below the worst legal cost but above
        # the preflight minimum, which is exactly the audit's "started and failed halfway" case.
        rejecting = validation_from_fixture("validation_reject_check")
        passing = validation_from_fixture()
        # Reject only the first attempt of each section, then accept.
        script = {"n": 0}

        def alternating(request):
            script["n"] += 1
            builder = rejecting if script["n"] % 2 else passing
            return _costly(builder)(request)

        llm = self.lesson_script(alternating, generate=_costly(lesson_from_request()))
        with self.assertRaises(gen.CostCeilingExceeded) as raised:
            gen.run_lesson_job(
                self.connection,
                self.job(plan_result),
                llm,
                now=NOW,
                budget=gen.CostBudget(max_calls=32, max_cost_usd=0.4),
            )
        error = raised.exception
        self.assertEqual(error.sections_total, 4)
        self.assertGreaterEqual(len(error.sections_completed), 1)
        self.assertLess(len(error.sections_completed), 4)  # the abort really is mid-course
        self.assertEqual(len(error.sections_completed), 2)
        self.assertEqual(self.count("gen_lessons"), 2)  # the authored pages survive
        self.assertIn("2 of 4 sections are saved", str(error))
        self.assertIn("raise the budget", str(error))
        checkpoint = error.to_checkpoint()
        self.assertEqual(checkpoint["kind"], "cost_ceiling_exceeded")
        self.assertEqual(checkpoint["sections_completed_count"], 2)
        self.assertEqual(checkpoint["sections_total"], 4)
        self.assertEqual(checkpoint["actions"], ["continue_remaining", "raise_budget", "stop"])
        self.assertEqual(checkpoint["resume"]["brief"]["plan_id"], plan_result["plan_id"])
        # Real spend is recorded, never hidden by the abort: one event per call the provider took.
        self.assertEqual(checkpoint["calls"], error.calls)
        self.assertGreaterEqual(error.calls, 8)  # two full sections plus the aborted work
        self.assertGreater(checkpoint["known_cost_usd"], 0.0)
        self.assertLessEqual(checkpoint["known_cost_usd"], 0.4 + gen.DECLARED_CALL_COST_USD)

    def test_resume_continues_remaining_sections_without_duplication(self) -> None:
        plan_result = self.approved_plan()
        rejecting = validation_from_fixture("validation_reject_check")
        passing = validation_from_fixture()
        script = {"n": 0}

        def alternating(request):
            script["n"] += 1
            builder = rejecting if script["n"] % 2 else passing
            return _costly(builder)(request)

        stalling = self.lesson_script(alternating, generate=_costly(lesson_from_request()))
        with self.assertRaises(gen.CostCeilingExceeded):
            gen.run_lesson_job(
                self.connection,
                self.job(plan_result),
                stalling,
                now=NOW,
                budget=gen.CostBudget(max_calls=32, max_cost_usd=0.4),
            )
        authored_before = self.count("gen_lessons")
        usage_before = self.count("usage_events")
        self.assertEqual(authored_before, 2)

        # "continue_remaining": a new job for the same plan, default sized budget.
        healthy = self.lesson_script(passing, generate=_costly(lesson_from_request()))
        result = gen.run_lesson_job(
            self.connection,
            self.job(plan_result, job_id="job-lesson-cost-resume"),
            healthy,
            now=NOW,
        )
        self.assertEqual(len(result["lessons"]), 4)
        self.assertEqual(sum(1 for item in result["lessons"] if item["reused"]), 2)
        # Only the two missing sections were authored (and charged).
        self.assertEqual(healthy.calls_for("coursebook.lesson.generate"), 2)
        self.assertEqual(healthy.calls_for("coursebook.lesson.validate"), 2)
        self.assertEqual(self.count("gen_lessons"), 4)  # no duplicates
        self.assertEqual(self.count("usage_events") - usage_before, 4)
        self.assertEqual(result["budget"]["source"], "declared")

    def test_the_configured_ceiling_is_recorded_in_the_usage_view(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(validation_from_fixture(), generate=_costly(lesson_from_request()))
        with mock.patch.dict(os.environ, {gen.JOB_MAX_COST_ENV: "2.5"}):
            result = gen.run_lesson_job(self.connection, self.job(plan_result), llm, now=NOW)
        self.assertEqual(result["budget"], {"max_calls": 24, "max_cost_usd": 2.5, "source": "operator_env"})
        self.assertEqual(result["usage"]["budget"]["max_cost_usd"], 2.5)
        self.assertTrue(result["preflight"]["fits_maximum"])


class UnknownCostTest(unittest.TestCase):
    """A missing cost is charged at the declared estimate, never treated as zero."""

    def _request(self) -> gen.LLMRequest:
        return gen.build_lesson_request(
            plan={}, section={"source_ids": []}, objective=None, recipe="casual",
            dials={}, locale=None, sources=[],
        )

    def test_unknown_cost_consumes_the_ceiling_at_the_declared_estimate(self) -> None:
        usage = gen._Usage(gen.CostBudget(max_calls=64, max_cost_usd=0.1))
        request = self._request()
        with self.assertRaises(gen.CostCeilingExceeded):
            for _ in range(10):
                usage.before_call(request)
                usage.record(request, gen.LLMResponse(text="{}", cost_usd=None), 1)
        # 0.1 / 0.04 = 2.5 -> the third call crosses the ceiling; zero-cost accounting would
        # have allowed all ten.
        self.assertEqual(len(usage.calls), 3)
        summary = usage.summary()
        self.assertIsNone(summary["cost_usd"])  # unknown stays unknown
        self.assertEqual(summary["unknown_calls"], 3)
        self.assertAlmostEqual(summary["estimated_cost_usd"], 0.12)
        self.assertTrue(summary["unknown_cost"])

    def test_recorded_cost_is_never_replaced_by_the_estimate(self) -> None:
        usage = gen._Usage(gen.CostBudget(max_calls=64, max_cost_usd=1.0))
        request = self._request()
        usage.before_call(request)
        usage.record(request, gen.LLMResponse(text="{}", cost_usd=0.003), 1)
        self.assertEqual(usage.known_cost, 0.003)
        self.assertEqual(usage.unknown_calls, 0)
        self.assertAlmostEqual(usage.summary()["estimated_cost_usd"], 0.003)


class JobViewRecoveryTest(KernelCase):
    """``jobs.get`` is the view an operator decides from: it must carry the typed checkpoint."""

    def _job(self) -> str:
        created = self.ok("jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": "plan-x-01"}})
        return created["result"]["job_id"]

    def test_jobs_create_refuses_a_lessons_job_that_cannot_pay_its_minimum(self) -> None:
        connection = db.connect()
        try:
            gen.ensure_schema(connection)  # the generation tables are owned by this module
        finally:
            connection.close()
        course_id, plan_id = self.new_course()
        # Eight sections: the plan cap today, and the case the audit measured.
        for ordinal in range(1, 9):
            self.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                " objective_refs_json) VALUES (?, ?, ?, 'hash', ?, 'intent', '[]')",
                (f"sec_{ordinal}", plan_id, ordinal, f"Section {ordinal}"),
            )
        with mock.patch.dict(os.environ, {gen.JOB_MAX_COST_ENV: "0.2"}):
            error = self.err(
                "jobs.create",
                {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}},
            )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "cost_preflight_insufficient")
        self.assertEqual(error["details"]["minimum_calls"], 16)
        self.assertEqual(error["details"]["max_cost_usd"], 0.2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 0)
        # The same brief with an explicit operator raise is accepted.
        created = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id, "budget_usd": 2.0}},
        )
        self.assertEqual(created["result"]["state"], "queued")

    def test_a_failed_cost_job_exposes_completed_sections_spend_and_actions(self) -> None:
        job_id = self._job()
        request = gen.build_lesson_request(
            plan={}, section={"source_ids": []}, objective=None, recipe="casual",
            dials={}, locale=None, sources=[],
        )
        usage = gen._Usage(gen.CostBudget(max_calls=32, max_cost_usd=0.4, source="declared"))
        usage.before_call(request)
        usage.record(request, gen.LLMResponse(text="{}", cost_usd=0.32), 1)
        error = gen.CostCeilingExceeded("spend 0.4000 USD exceeded the 0.4000 USD ceiling")
        error.attach_checkpoint(
            plan_id="plan-x-01",
            sections_completed=["sec_1", "sec_2"],
            sections_total=4,
            usage=usage,
            budget=gen.CostBudget(max_calls=32, max_cost_usd=0.4, source="declared"),
            recovery="2 of 4 sections are saved; continue, raise the budget, or stop",
        )

        lease = job_service.claim(job_id, owner="worker-test", now=NOW)
        job_service.fail(lease, job_service._stage_error(error), checkpoint=job_service._stage_checkpoint(error), now=NOW)

        job = self.ok("jobs.get", {"job_id": job_id})["result"]["job"]
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["error"]["code"], "POLICY_VIOLATION")
        self.assertEqual(job["error"]["details"]["reason"], "cost_ceiling_exceeded")
        self.assertEqual(job["error"]["details"]["sections_completed_count"], 2)
        self.assertEqual(job["error"]["details"]["actions"], ["continue_remaining", "raise_budget", "stop"])
        checkpoint = job["checkpoint"]
        self.assertEqual(checkpoint["kind"], "cost_ceiling_exceeded")
        self.assertEqual(checkpoint["sections_completed"], ["sec_1", "sec_2"])
        self.assertEqual(checkpoint["sections_completed_count"], 2)
        self.assertEqual(checkpoint["sections_total"], 4)
        self.assertEqual(checkpoint["resume"]["brief"], {"stage": "lessons", "plan_id": "plan-x-01"})
        self.assertEqual(checkpoint["raise_budget"]["brief_field"], "brief.budget_usd")


if __name__ == "__main__":
    unittest.main()
