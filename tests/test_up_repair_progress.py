"""Upgrade 36: a failed lesson-section attempt is readable while the retry runs.

A section is refused, re-authored and refused again while the learner watches a job that says
nothing. The first sign of trouble was the parked page minutes later, so a run that would end on a
repair screen looked identical to one that was going well (``coursebook/generation.py``'s
``for attempt in range(1, LESSON_ATTEMPTS + 1)`` wrote nothing durable on a refusal).

These tests drive the real authoring path on a real migrated store — a scripted model that breaks a
named rule on attempt 1 and is clean on attempt 2 — and read the job through ``jobs.get`` while the
retry is still running. They prove the attempt row is durable *before* the retry call, that its
reason is bounded and withheld of the answer key, and that a job which has not failed yet reports
no retry at all.
"""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from coursebook import contracts, db, generation as gen
from tests.kernel_support import KernelCase
from tests.test_generation import (
    NOW,
    FakeLLM,
    FakeSearch,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    response,
    validation_from_fixture,
)

ANSWER_KEY = "こんにちは"


class RepairProgressTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.connection = db.connect()
        self.addCleanup(self.connection.close)
        gen.ensure_schema(self.connection)
        self.plan = self.authored_plan()

    # ── fixtures ────────────────────────────────────────────────────────
    def authored_plan(self) -> dict:
        llm = FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture("plan_ja"),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(
            self.connection,
            plan_job(recipe="committed", locale="ja-JP"),
            llm,
            FakeSearch(),
            now=NOW,
        )
        with db.transaction() as connection:
            connection.execute(
                "UPDATE plans SET state = 'approved', approved_at = ? WHERE id = ?",
                ("2026-11-06T12:05:00Z", result["plan_id"]),
            )
        return result

    def lessons_job(self) -> str:
        return self.ok(
            "jobs.create",
            {
                "kind": "plan",
                "brief": {
                    "stage": "lessons",
                    "plan_id": self.plan["plan_id"],
                    "recipe": "committed",
                    "locale": "ja-JP",
                },
            },
        )["result"]["job_id"]

    def activity(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]["activity"]

    # ── the acceptance ──────────────────────────────────────────────────
    def test_failed_attempt_is_readable_before_the_retry(self) -> None:
        """A rule refusal on attempt 1 leaves a row readable before attempt 2 is called."""
        job_id = self.lessons_job()
        base = lesson_from_request()
        calls = {"generate": 0}
        observed: dict[str, object] = {}

        def generate(request: gen.LLMRequest) -> gen.LLMResponse:
            calls["generate"] += 1
            draft = json.loads(base(request).text)
            if calls["generate"] == 1:
                # A named rule: the teaching arc requires a guided second pass at the target.
                draft["segments"] = [
                    segment for segment in draft["segments"] if segment.get("kind") != "guided"
                ]
                return response(draft, model="fake-author")
            if calls["generate"] == 2:
                # This is attempt 2 starting: the refusal must already be durable and readable.
                observed["during_retry"] = self.activity(job_id)
            return response(draft, model="fake-author")

        def validate(request: gen.LLMRequest) -> gen.LLMResponse:
            return validation_from_fixture()(request)

        llm = FakeLLM(
            {
                "coursebook.lesson.generate": generate,
                "coursebook.lesson.validate": validate,
            }
        )
        result = gen.run_lesson_job(
            self.connection,
            {"job_id": job_id, "kind": "plan", "brief": {"plan_id": self.plan["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )
        self.assertTrue(calls["generate"] >= 2, "attempt 2 was never reached")
        self.assertTrue(all(item["state"] != "needs_review" for item in result["lessons"]))

        during = observed.get("during_retry")  # type: ignore[assignment]
        self.assertIsInstance(during, dict, "jobs.get returned no activity while the retry ran")
        retry = during["retry"]  # type: ignore[index]
        self.assertIsNotNone(retry, "no attempt row existed before attempt 2 was called")
        self.assertEqual(retry["kind"], "lesson_section")
        self.assertEqual(retry["attempt"], 1, "the failed attempt, not the one about to run")
        self.assertEqual(retry["attempts_total"], gen.LESSON_ATTEMPTS)
        self.assertGreaterEqual(retry["section_ordinal"], 1)
        self.assertIn("guided", retry["reason"], retry["reason"])
        self.assertLessEqual(len(retry["reason"]), gen.VALIDATION_REASON_MAX_CHARS)
        self.assertEqual(retry["prompt_version"], gen.LESSON_PROMPT_VERSION)
        self.assertNotIn(ANSWER_KEY, retry["reason"], "the reason carried the answer key")

        # The row is durable, not an in-memory view: it survives a fresh read after the job.
        rows = gen.lesson_attempts(self.connection, job_id)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(int(rows[0]["attempt_index"]), 1)
        self.assertEqual(int(rows[0]["attempts_total"]), gen.LESSON_ATTEMPTS)
        # A job that finished with every section wrapped must still report its refusal, because
        # the report is about the work that happened, not the final state.
        self.assertIsNotNone(self.activity(job_id)["retry"])
        # And the object is legal on the wire's own job schema.
        job = self.ok("jobs.get", {"job_id": job_id})["result"]["job"]
        Draft202012Validator(
            {**contracts.contract("cb.jobs"), "$ref": "#/job"}, registry=contracts.registry()
        ).validate(job)
        # jobs.list serves the same job item through the refreshed cb.jobs v6 reference.
        listed = self.ok("jobs.list", {})["result"]["jobs"]
        self.assertTrue(any(item["job_id"] == job_id for item in listed))

    def test_a_job_that_has_not_failed_reports_no_retry(self) -> None:
        """A progressing job is not a retrying job: no row, no retry object."""
        job_id = self.lessons_job()
        self.assertIsNone(self.activity(job_id)["retry"])
        self.assertEqual(gen.lesson_attempts(self.connection, job_id), [])

    def test_the_reason_withholds_the_answer_key(self) -> None:
        """A validator reason that quotes the key is stored with the key withheld."""
        job_id = self.lessons_job()
        base = lesson_from_request()
        calls = {"generate": 0, "validate": 0}

        def generate(request: gen.LLMRequest) -> gen.LLMResponse:
            calls["generate"] += 1
            return base(request)

        accept = validation_from_fixture()

        def validate(request: gen.LLMRequest) -> gen.LLMResponse:
            calls["validate"] += 1
            if calls["validate"] != 1:
                return accept(request)
            report = json.loads(accept(request).text)
            # The refused draft's own key, quoted the way a model refusal does.
            reason = f"the draft restates the key {ANSWER_KEY} instead of teaching the criterion"
            report["verdict"] = "reject"
            report["rejections"] = [
                {"item": "lesson.learner_explanation", "criterion": "answer_leakage", "reason": reason}
            ]
            for entry in report.get("criteria") or []:
                if entry.get("id") == "answer_leakage":
                    entry["verdict"] = "fail"
                    entry["reason"] = reason
            return response(report, model="fake-validator")

        llm = FakeLLM(
            {
                "coursebook.lesson.generate": generate,
                "coursebook.lesson.validate": validate,
            }
        )
        gen.run_lesson_job(
            self.connection,
            {"job_id": job_id, "kind": "plan", "brief": {"plan_id": self.plan["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )
        rows = gen.lesson_attempts(self.connection, job_id)
        self.assertTrue(rows, "a validator refusal wrote no attempt row")
        reason = str(rows[0]["reason"])
        self.assertIn("[answer withheld]", reason)
        self.assertNotIn(ANSWER_KEY, reason)
        self.assertLessEqual(len(reason), gen.VALIDATION_REASON_MAX_CHARS)
