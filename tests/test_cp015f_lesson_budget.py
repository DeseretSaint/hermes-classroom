"""CP-015e follow-up — the lesson-stage budget must count the truncation repair.

``lesson_cost_budget`` sized ``4n`` calls per plan (2 attempts x generate + validate) while the
pipeline legally spends one more call per attempt: ``_validation_answer_with_repair`` re-asks a
validator answer that was cut off by the 8 000-token completion cap. CP-015b measured that on the
demo route during the Sourdough run — five ``coursebook.lesson.validate`` answers were cut and
repaired for a four-lesson job — so the repair is the normal path there, and a ceiling that
excludes it refuses a run that behaved exactly as designed.

What is asserted here:

* ``lesson_calls`` / ``lesson_cost_budget`` are sized from the calls the stage actually spends
  (``LESSON_ATTEMPTS`` x (generate + validate + ``TRUNCATION_REPAIR_CALLS``) = 6 per section), and
  the dollar floor follows the same count;
* a four-section job whose validation answer is cut on **both** attempts per section completes in
  exactly 24 calls with the production default budget — 16 (the old arithmetic) refuses it;
* the re-ask is the marked ``.cut`` request, never a silent second validator;
* the preflight states a truthful worst-legal maximum for the largest plan the contract allows.

The cut answers use the measured shape (cap fully consumed, JSON stops mid-object) and the stage is
driven by the fake provider seam in ``tests/test_generation.py`` — no test presents invented
provider output as a real call.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen

from tests.test_generation import (
    FakeLLM,
    GenerationTestBase,
    NOW,
    lesson_from_request,
    validation_from_fixture,
)


def _cut_validation_answer(request: gen.LLMRequest) -> gen.LLMResponse:
    """The measured shape: the cap is fully consumed and the JSON stops mid-object."""
    return gen.LLMResponse(
        text='{"verdict": "pass", "criteria": [{"id": "objective_alignment", "verdict": "pa',
        parsed=None,
        provider="nous",
        model="deepseek/deepseek-v4.1-flash-1017",
        input_tokens=7350,
        output_tokens=int(request.max_tokens),
        cost_usd=0.032,
    )


class LessonBudgetArithmeticTest(unittest.TestCase):
    def test_the_budget_is_sized_from_the_calls_the_stage_spends(self) -> None:
        per_section = gen.LESSON_ATTEMPTS * (
            gen.CALLS_PER_LESSON_ATTEMPT + gen.TRUNCATION_REPAIR_CALLS
        )
        self.assertEqual(per_section, 6)
        self.assertEqual(gen.lesson_calls(1), (2, 6))
        self.assertEqual(gen.lesson_calls(5), (10, 30))
        self.assertEqual(gen.lesson_cost_budget(5).max_calls, 30)
        self.assertEqual(gen.lesson_cost_budget(8).max_calls, 48)

    def test_the_dollar_floor_follows_the_same_count(self) -> None:
        five = gen.lesson_cost_budget(5)
        five_cost = five.max_cost_usd
        assert five_cost is not None
        self.assertAlmostEqual(five_cost, 30 * gen.DECLARED_CALL_COST_USD)
        self.assertAlmostEqual(five_cost, 1.20)
        eight = gen.lesson_cost_budget(8)
        eight_cost = eight.max_cost_usd
        assert eight_cost is not None
        self.assertAlmostEqual(eight_cost, 48 * gen.DECLARED_CALL_COST_USD)
        self.assertEqual(five.source, "declared")
        # A two-section plan still sits on the historic flat floor.
        self.assertEqual(gen.lesson_cost_budget(2).max_cost_usd, gen.DEFAULT_MAX_COST_USD)

    def test_a_caller_can_still_declare_a_tighter_ceiling(self) -> None:
        budget = gen.lesson_cost_budget(5, brief_budget_usd=0.5)
        self.assertEqual(budget.max_cost_usd, 0.5)
        self.assertEqual(budget.source, "operator_brief")

    def test_the_preflight_maximum_is_the_worst_legal_path(self) -> None:
        preflight = gen.preflight_lesson_cost(8)
        self.assertEqual(preflight.minimum_calls, 16)
        self.assertEqual(preflight.maximum_calls, 48)
        self.assertTrue(preflight.fits_minimum)
        self.assertTrue(preflight.fits_maximum)
        self.assertAlmostEqual(preflight.maximum_cost_usd, 48 * gen.DECLARED_CALL_COST_USD)


class LessonBudgetStageTest(GenerationTestBase):
    """The real lesson pipeline, at the production default budget."""

    def _cut_on_both_attempts(self, sections: int) -> FakeLLM:
        """Per section: attempt 1 = generate + cut validate + rejecting repair.

        Attempt 2 = generate + cut validate + passing repair. Both attempts of every section
        therefore spend their legal truncation re-ask.
        """
        cut = _cut_validation_answer
        reject = validation_from_fixture("validation_reject_check")
        passed = validation_from_fixture()
        script: list = []
        for _ in range(sections):
            script.extend([cut, reject, cut, passed])
        return FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                "coursebook.lesson.validate": script,
            }
        )

    def _run_at_the_production_default(self, plan_result: dict, llm: FakeLLM) -> dict:
        return gen.run_lesson_job(
            self.connection,
            {
                "job_id": "job-lesson-repair",
                "kind": "plan",
                "brief": {"plan_id": plan_result["plan_id"]},
            },
            llm,
            now=NOW,
        )

    def test_a_repair_on_both_attempts_completes_the_plan_in_six_calls_per_section(self) -> None:
        plan_result = self.approved_plan()
        sections = self.count("gen_plan_sections")
        self.assertEqual(sections, 4)
        llm = self._cut_on_both_attempts(sections)

        result = self._run_at_the_production_default(plan_result, llm)

        # 4 sections x 2 attempts x (generate + validate + one repair) = 24 calls, and the 24th
        # call is admitted: the ceiling is the true worst legal path, not 16.
        self.assertEqual(llm.calls_for("coursebook.lesson.generate"), 8)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 16)
        self.assertEqual(result["usage"]["calls"], 24)
        self.assertEqual(len(result["lessons"]), 4)
        self.assertEqual(self.count("gen_lessons"), 4)

    def test_the_reask_is_the_marked_cut_request(self) -> None:
        plan_result = self.approved_plan()
        llm = self._cut_on_both_attempts(self.count("gen_plan_sections"))
        self._run_at_the_production_default(plan_result, llm)

        validate_requests = [
            request
            for request in llm.requests
            if request.purpose == "coursebook.lesson.validate"
        ]
        self.assertEqual(len(validate_requests), 16)
        # First ask of each attempt is unmarked; the re-ask carries the ``.cut`` prompt version.
        self.assertEqual(
            [
                request.prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX)
                for request in validate_requests
            ],
            [False, True] * 8,
        )

    def test_the_old_four_call_arithmetic_refuses_this_legal_run(self) -> None:
        """4n is not a bound on the pipeline: it aborts a run that spent only legal calls."""
        plan_result = self.approved_plan()
        llm = self._cut_on_both_attempts(self.count("gen_plan_sections"))

        with self.assertRaises(gen.CostCeilingExceeded) as raised:
            gen.run_lesson_job(
                self.connection,
                {
                    "job_id": "job-lesson-old-ceiling",
                    "kind": "plan",
                    "brief": {"plan_id": plan_result["plan_id"]},
                },
                llm,
                now=NOW,
                budget=gen.CostBudget(max_calls=16, max_cost_usd=None, source="caller"),
            )
        self.assertEqual(raised.exception.purpose, "coursebook.lesson.validate")
        # Sixteen is the whole ceiling: the job is refused before its 17th call, while the legal
        # run needs 24. No lesson row is lost on that path, but the run is wasted.
        self.assertEqual(len(llm.requests), 16)


if __name__ == "__main__":
    unittest.main()
