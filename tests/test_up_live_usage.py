"""UP-40 — a live job's spend is visible while the job is still spending.

The lesson stage wrote its ``usage_events`` rows once, after the whole section loop, so a learner
watching a ten-minute job read ``calls: 0`` and no cost until the stage had already ended. The
number a cancel decision needed was always zero while it mattered.

These tests drive the real lesson pipeline with the fake provider seam and read the activity object
``jobs.get`` returns *from inside* a provider call: section 2's authoring starts only after section
1's generate and validate have returned, so the two rows must already be durable at that moment.

The plan under test is the recorded Japanese fixture (four sections — the v1 plan schema's floor;
a three-section plan is not an authorable v1 document). The read is taken at exactly the moment the
card names: section 1 finished, section 2's first call just issued.

The flush is bookkeeping, never the spend decision: one test makes the incremental write raise and
proves the job still completes with the in-memory totals intact and every row landing in the
end-of-stage write.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from coursebook import generation as gen
from coursebook import progress as progress_view

from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    NOW,
    lesson_from_request,
    plan_fixture,
    plan_job,
    response,
    validation_from_fixture,
)

T0 = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
JOB_ID = "job-up40-live-usage"


def _live_activity(connection, job_id: str) -> dict:
    """The ``jobs.get`` activity object for a running job, read through the real read model.

    ``activity_with_usage`` is exactly what ``jobs.get`` calls: ``activity_for`` plus the
    ``usage_events`` sum for this job id. The row is the shape the durable jobs table holds; these
    tests drive the stage directly, so the job row itself is not the subject of the assertion.
    """
    row = {
        "id": job_id,
        "state": "running",
        "progress_json": json.dumps({"stage": "lessons"}),
        "brief_json": json.dumps({"stage": "lessons"}),
        "created_at": "2026-11-06T11:59:00Z",
        "updated_at": None,
    }
    return progress_view.activity_with_usage(connection, row, now=T0)


class LiveUsageTest(GenerationTestBase):
    """A learner's cost meter reads the truth mid-stage, not after it."""

    def _approved_plan(self) -> dict:
        document = plan_fixture("plan_ja")
        llm = FakeLLM(
            {
                "coursebook.plan.generate": lambda request: response(document),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)
        self.connection.execute(
            "UPDATE plans SET state = 'approved', approved_at = ? WHERE id = ?",
            ("2026-11-06T12:05:00Z", result["plan_id"]),
        )
        self.assertGreaterEqual(self.count("gen_plan_sections"), 3)
        return result

    def _lesson_job(self, plan_id: str, attempt: str = "attempt-1") -> dict:
        return {"job_id": JOB_ID, "attempt_id": attempt, "brief": {"plan_id": plan_id}}

    def _lesson_llm(self, generate) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )

    def test_mid_stage_cost_is_visible(self) -> None:
        """After section 1, before section 2 is called: two calls and a non-zero cost."""
        plan_result = self._approved_plan()
        probes: list[dict] = []

        def author_section(request: gen.LLMRequest) -> gen.LLMResponse:
            # ``FakeLLM`` records the request before answering it, so this is the instant the
            # second section's authoring begins: section 1's generate *and* validate returned.
            made = sum(1 for item in llm.requests if item.purpose == "coursebook.lesson.generate")
            if made == 2:
                probes.append(_live_activity(self.connection, JOB_ID))
            return author(request)

        author = lesson_from_request()
        llm = self._lesson_llm(author_section)
        gen.run_lesson_job(self.connection, self._lesson_job(plan_result["plan_id"]), llm, now=NOW)

        self.assertEqual(len(probes), 1, "the second section was authored exactly once")
        usage = probes[0]["usage"]
        self.assertEqual(usage["calls"], 2, "section 1's two calls are already durable")
        self.assertIsNotNone(usage["cost_usd"])
        self.assertGreater(usage["cost_usd"], 0.0, "a non-zero cost, not the old zero")
        self.assertEqual(usage["unknown_cost_calls"], 0)
        self.assertEqual(usage["tokens"]["input"], 240)
        self.assertEqual(usage["tokens"]["output"], 480)
        self.assertEqual(probes[0]["stage"], "lessons")

    def test_the_end_of_stage_write_does_not_double_count(self) -> None:
        """Two calls per section make two rows: the incremental and stage flushes are idempotent."""
        plan_result = self._approved_plan()
        sections = self.count("gen_plan_sections")
        llm = self._lesson_llm(lesson_from_request())
        result = gen.run_lesson_job(
            self.connection, self._lesson_job(plan_result["plan_id"]), llm, now=NOW
        )

        rows = self.connection.execute(
            "SELECT id FROM usage_events WHERE operation_id = ?", (JOB_ID,)
        ).fetchall()
        self.assertEqual(len(rows), 2 * sections, "generate + validate per section, each once")
        self.assertEqual(len({row["id"] for row in rows}), len(rows), "no primary-key collision")
        usage = _live_activity(self.connection, JOB_ID)["usage"]
        self.assertEqual(usage["calls"], 2 * sections)
        self.assertAlmostEqual(usage["cost_usd"], 0.01 * 2 * sections, places=6)
        self.assertEqual(result["usage"]["calls"], 2 * sections)
        self.assertAlmostEqual(result["usage"]["cost_usd"], 0.01 * 2 * sections, places=6)

    def test_a_failed_flush_never_changes_the_spend_or_the_job(self) -> None:
        """A write that raises is retried at the stage end; the in-memory total is the authority."""
        plan_result = self._approved_plan()
        sections = self.count("gen_plan_sections")
        llm = self._lesson_llm(lesson_from_request())
        real_persist = gen._persist_usage_calls
        failures: list[BaseException] = []

        def flaky_persist(connection, job_id, calls, now):
            # The first (incremental) write fails; the end-of-stage path calls ``pending_calls``
            # again and therefore retries the very same rows.
            if not failures:
                failures.append(RuntimeError("database is locked"))
                raise failures[0]
            return real_persist(connection, job_id, calls, now)

        with mock.patch.object(gen, "_persist_usage_calls", flaky_persist):
            result = gen.run_lesson_job(
                self.connection, self._lesson_job(plan_result["plan_id"]), llm, now=NOW
            )

        self.assertTrue(failures, "the failing write was actually exercised")
        self.assertEqual(len(result["lessons"]), sections, "the job completed regardless")
        self.assertEqual(result["usage"]["calls"], 2 * sections)
        self.assertAlmostEqual(result["usage"]["cost_usd"], 0.01 * 2 * sections, places=6)
        usage = _live_activity(self.connection, JOB_ID)["usage"]
        self.assertEqual(usage["calls"], 2 * sections, "every row landed in the stage-end write")
        self.assertAlmostEqual(usage["cost_usd"], 0.01 * 2 * sections, places=6)

    def test_a_retried_attempt_does_not_collide_with_the_first_attempt(self) -> None:
        """A job keeps its id across attempts; the row ids must not swallow the retry's spend."""
        plan_result = self._approved_plan()
        sections_before = self.count("gen_plan_sections")
        first = self._lesson_llm(lesson_from_request())
        gen.run_lesson_job(self.connection, self._lesson_job(plan_result["plan_id"]), first, now=NOW)

        # The retry reuses the job id with a new attempt and regenerates one section, which is the
        # paying path: its two calls must count as spend, not collide with attempt 1's row ids.
        sections = self.rows("SELECT id, ordinal FROM gen_plan_sections ORDER BY ordinal")
        second = self._lesson_llm(lesson_from_request())
        retry_job = {
            "job_id": JOB_ID,
            "attempt_id": "attempt-2",
            "brief": {
                "plan_id": plan_result["plan_id"],
                "regenerate": True,
                "section_id": sections[0]["id"],
            },
        }
        gen.run_lesson_job(self.connection, retry_job, second, now=NOW)

        self.assertEqual(len(second.requests), 2, "the retry's two calls are its own attempt")
        rows = self.connection.execute(
            "SELECT id FROM usage_events WHERE operation_id = ?", (JOB_ID,)
        ).fetchall()
        self.assertEqual(
            len(rows), 2 * sections_before + 2, "attempt 1 plus the retry's two calls"
        )
        usage = _live_activity(self.connection, JOB_ID)["usage"]
        self.assertEqual(usage["calls"], 2 * sections_before + 2)
        self.assertEqual(usage["calls"], len(rows), "the retry's spend is counted, never dropped")


if __name__ == "__main__":
    unittest.main()
