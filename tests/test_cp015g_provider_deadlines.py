"""CP-015g quality — the shipped per-call deadlines fit the supported route, and a miss reads as
slowness rather than as an unavailable host.

Measured 2026-11-11 in the production-shaped scratch home ``cb-prod-home`` on the host-configured
route (Nous ``deepseek/deepseek-v4.1-flash-1017``):

* job ``job_1f3b794c126e41e295f29466425c3cce`` (four-objective plan) took 202–204 s end to end;
  the old 180 s ``plan.validate`` bound had cut its validation stage twice before
  ``COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS=600`` let it finish. Its successful validation passes
  took 36.7, 27.3 and 26.6 s.
* job ``job_10ceb7d0e0774e3dba033241930938a6`` (three-section unit) failed at 908 s with 1 of 3
  sections saved: the successful ``lesson.generate`` calls took 94.5, 95.3 and 79.3 s, and the
  next one was still outstanding at the old 300 s bound.

The numbers below are that evidence, not invented provider latency. The fakes only provide
structure; no test asserts real provider output, tokens or spend.
"""

from __future__ import annotations

import os
import threading
import unittest
from unittest import mock

from coursebook import deadline as deadline_mod
from coursebook import generation as gen
from coursebook import job_service

from tests.test_generation import NOW, GenerationTestBase

#: Wall time of the four-objective plan job on the measured route
#: (job ``job_1f3b794c…``: 202 s recorded, 204 s in the card's measurement). The old 180 s
#: ``plan.validate`` bound cut its validation stage twice.
MEASURED_PLAN_VALIDATE_SECONDS = 204.0

#: Wall time of every *successful* single-section lesson write on the recorded unit
#: (job ``job_10ceb7d0…``). The next call never returned inside the old 300 s bound.
MEASURED_LESSON_SECTION_SECONDS: tuple[float, ...] = (94.5, 95.3, 79.3)

#: Sections of the recorded unit whose lesson job failed at 908 s with 1 of 3 saved.
MEASURED_SECTION_COUNT = 3

#: Whole wall time of that job when it failed.
MEASURED_LESSON_JOB_SECONDS = 908.0


class MeasuredDeadlineTest(unittest.TestCase):
    """The resolved defaults clear the measurements the card cites (fails on 180/300)."""

    def test_plan_validate_default_is_above_the_measured_four_objective_stage(self) -> None:
        declared = gen.provider_timeout_s("coursebook.plan.validate")
        self.assertGreater(
            declared,
            MEASURED_PLAN_VALIDATE_SECONDS,
            f"the plan-validate stage took {MEASURED_PLAN_VALIDATE_SECONDS:g}s on a "
            f"four-objective plan; a {declared:g}s bound cuts a real plan and reports it as a "
            "host failure",
        )
        self.assertGreaterEqual(declared, 600.0)
        self.assertNotEqual(declared, 180.0)

    def test_lesson_generate_default_is_above_per_section_time_times_sections(self) -> None:
        declared = gen.provider_timeout_s("coursebook.lesson.generate")
        worst = max(MEASURED_LESSON_SECTION_SECONDS)
        for sections in (MEASURED_SECTION_COUNT, 4, 6):
            measured_total = worst * sections
            self.assertGreater(
                declared,
                measured_total,
                f"{sections} sections at the measured p100 {worst:g}s/section need "
                f"{measured_total:g}s; a {declared:g}s bound would cut a supported course",
            )
        self.assertGreaterEqual(declared, 1200.0)
        self.assertNotEqual(declared, 300.0)

    def test_lesson_generate_default_admits_the_whole_measured_lesson_job(self) -> None:
        # The failing job was 908 s old when one section call was cut. A bound that cannot cover
        # even that elapsed job cannot be described as fitting the route.
        self.assertGreater(
            gen.provider_timeout_s("coursebook.lesson.generate"), MEASURED_LESSON_JOB_SECONDS
        )

    def test_unit_sections_default_admits_a_multi_section_unit(self) -> None:
        # One unit-sections call authors a unit's whole section outline, so its bound is sized
        # against the same measured per-section write cost, not against one section.
        declared = gen.provider_timeout_s("coursebook.unit_sections.generate")
        self.assertGreater(declared, max(MEASURED_LESSON_SECTION_SECONDS) * MEASURED_SECTION_COUNT)
        self.assertNotEqual(declared, 240.0)

    def test_every_purpose_still_has_a_numeric_operator_variable(self) -> None:
        for purpose in gen.PROVIDER_TIMEOUT_SECONDS:
            self.assertIn(purpose, gen.PROVIDER_TIMEOUT_ENV)
            self.assertTrue(gen.PROVIDER_TIMEOUT_ENV[purpose].startswith("COURSEBOOK_"))
        self.assertEqual(
            gen.PROVIDER_TIMEOUT_ENV["coursebook.plan.validate"],
            "COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS",
        )
        self.assertEqual(
            gen.PROVIDER_TIMEOUT_ENV["coursebook.lesson.generate"],
            "COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS",
        )

    def test_an_operator_override_still_wins_over_the_new_default(self) -> None:
        with mock.patch.dict(os.environ, {"COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS": "240"}):
            self.assertEqual(gen.provider_timeout_s("coursebook.plan.validate"), 240.0)
        with mock.patch.dict(os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "600"}):
            self.assertEqual(gen.provider_timeout_s("coursebook.lesson.generate"), 600.0)


class DeadlineReadsAsSlownessTest(GenerationTestBase):
    """A fired bound names the variable and the elapsed wait, and never reads as an outage."""

    def test_the_plan_validate_message_names_the_variable_and_the_measured_elapsed(self) -> None:
        error = gen._call_deadline_error(
            "coursebook.plan.validate",
            600.0,
            deadline_mod.DeadlineExceeded(
                "coursebook.plan.validate", 600.0, elapsed_s=204.0
            ),
        )
        text = str(error)
        self.assertEqual(error.purpose, "coursebook.plan.validate")
        self.assertIn("waited 204.0s", text)
        self.assertIn("COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS", text)
        self.assertIn("the route was slower than its declared bound", text)
        self.assertNotIn("unavailable", text.casefold())

    def test_the_unit_sections_recovery_names_the_variable_and_the_elapsed_wait(self) -> None:
        error = gen.ProviderTimeout(
            "coursebook.unit_sections.generate exceeded its 900s deadline (waited 900.0s)",
            purpose="coursebook.unit_sections.generate",
            deadline_s=900.0,
            duration_ms=900_000,
        )
        recovery = gen.unit_sections_timeout_recovery(error, unit_ordinal=2, plan_id="pln_x")
        self.assertIn("COURSEBOOK_UNIT_SECTIONS_GENERATE_TIMEOUT_SECONDS", recovery)
        self.assertIn("900", recovery)
        self.assertIn("transactional", recovery)
        self.assertIn("unit 2", recovery)

    def _stalled_lesson_job(self) -> gen.ProviderTimeout:
        plan_result = self.approved_plan()
        release = threading.Event()

        class StallingHost:
            def complete_structured(self, **kwargs):  # noqa: ANN003 - host signature
                release.wait(10.0)
                raise AssertionError("the stalled call must be cut at its deadline first")

        adapter = gen.PluginLLMAdapter(StallingHost())
        try:
            with mock.patch.dict(
                os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "0.25"}
            ):
                with self.assertRaises(gen.ProviderTimeout) as caught:
                    gen.run_lesson_job(
                        self.connection,
                        {
                            "job_id": "job-cp015g-lesson-deadline",
                            "kind": "plan",
                            "brief": {"plan_id": plan_result["plan_id"]},
                        },
                        adapter,
                        now=NOW,
                        budget=gen.CostBudget(max_calls=32),
                    )
        finally:
            release.set()
        return caught.exception

    def test_a_lesson_bound_names_the_variable_the_elapsed_wait_and_the_saved_sections(self) -> None:
        error = self._stalled_lesson_job()
        text = str(error)
        self.assertEqual(error.purpose, "coursebook.lesson.generate")
        self.assertEqual(error.deadline_s, 0.25)
        self.assertIsNotNone(error.duration_ms)
        assert error.duration_ms is not None
        self.assertGreaterEqual(int(error.duration_ms), 200)
        self.assertIn("waited", text)
        self.assertIn("COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS", text)
        self.assertIn("of 4 sections are saved", text)
        self.assertIn("the route was slower than its declared bound", text)
        # The user must be able to read this as a slow route, not as a host outage.
        self.assertNotIn("unavailable", text.casefold())

    def test_the_job_error_keeps_the_variable_and_the_elapsed_wait(self) -> None:
        error = self._stalled_lesson_job()
        record = job_service._stage_error(error)
        details = record["details"]
        self.assertEqual(record["code"], "HOST_UNAVAILABLE")
        self.assertEqual(details["purpose"], "coursebook.lesson.generate")
        self.assertIsNotNone(details["duration_ms"])
        assert details["duration_ms"] is not None
        self.assertGreaterEqual(int(details["duration_ms"]), 200)
        self.assertIn("COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS", record["message"])
        self.assertIn("waited", record["message"])

    def test_a_lesson_call_inside_the_new_bound_is_not_declared_late(self) -> None:
        # Guard the other direction: raising the default must not turn a normal answer into a
        # failure, and the no-op path stays a no-op.
        answer = gen.LLMResponse(text="{}", parsed={}, provider="fake", model="fake")
        request = gen.LLMRequest(
            purpose="coursebook.lesson.generate",
            prompt_version="test",
            system_prompt="test",
            instructions="test",
            input_text="{}",
            schema={"type": "object"},
            schema_name="test",
            max_tokens=8,
            timeout_s=gen.provider_timeout_s("coursebook.lesson.generate"),
        )
        usage = gen._Usage(gen.CostBudget(max_calls=8))
        self.assertIs(gen._call_llm(lambda _request: answer, request, usage), answer)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
