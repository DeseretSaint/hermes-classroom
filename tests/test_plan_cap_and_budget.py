"""E2E G3/G4 — the plan's completion cap and job budget scale with the declared scope.

Two flat constants made a full plan fragile:

* **G3** — ``max_tokens=12000 if blueprint else 4000``. One short-course cap was applied to a
  40-objective/12-unit plan, and the plan answer was parsed with ``_parse_structured`` and no
  ``.cut`` re-ask, while the unit-sections and lesson stages both already used
  ``_stage_answer_with_repair``. A plan cut at the cap therefore ended the job with a
  ``GenerationRejected`` after the whole answer had been paid for.
* **G4** — ``CostBudget(max_calls=32, max_cost_usd=0.75)`` against a validation plan that scales
  from 2 passes (1 objective) to 14 passes (40 objectives / 12 units). Attempt 1 alone is
  1 + 14 calls and attempt 2 reserves 14 more, so the $0.75 ceiling stopped the job at call 19.

These tests pin the three fixes: the cap is chosen by the scope's objective band; a cut plan answer
is re-asked once under the marked ``.cut`` label; and the job's ``max_calls``/``max_cost_usd`` are
sized from the plan's own validation pass plan, the way ``lesson_cost_budget`` sizes lessons.
"""

from __future__ import annotations

import threading
import unittest

from coursebook import generation as gen
from coursebook import research
from tests.blueprint_support import blueprint_plan
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    NOW,
    plan_job,
    response,
    validation_from_fixture,
)


def research_run():
    return research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test")


class PlanCompletionCapTest(unittest.TestCase):
    """G3, first half: the cap is a function of the scope band, not one constant."""

    def request_for(self, scope: str | None) -> gen.LLMRequest:
        return gen.build_plan_request(
            goal="Hold a ten minute conversation in Japanese",
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_run=research_run(),
            scope=scope,
            level="L0",
            subject_domain="language",
        )

    def test_the_cap_grows_with_the_scope_band(self) -> None:
        single = self.request_for("single").max_tokens
        short = self.request_for("short").max_tokens
        full = self.request_for("full").max_tokens
        self.assertEqual(single, gen.PLAN_OUTPUT_TOKENS_BY_SCOPE["single"])
        self.assertEqual(short, gen.PLAN_OUTPUT_TOKENS_BY_SCOPE["short"])
        self.assertEqual(full, gen.PLAN_OUTPUT_TOKENS_BY_SCOPE["full"])
        # The flat 12000 was a short-course cap; a full plan must be allowed the larger answer.
        self.assertGreater(full, short)
        self.assertGreater(short, single)

    def test_an_unscoped_pre_blueprint_plan_keeps_its_own_cap(self) -> None:
        self.assertEqual(self.request_for(None).max_tokens, gen.PLAN_OUTPUT_TOKENS_UNSCOPED)

    def test_an_unknown_scope_is_refused_rather_than_unbounded(self) -> None:
        with self.assertRaises(gen.GenerationRejected):
            gen.plan_output_tokens("term")


class PlanCutAnswerRepairTest(GenerationTestBase):
    """G3, second half: a plan cut at the cap is re-asked, not rejected outright."""

    def cut_answer(self, request: gen.LLMRequest) -> gen.LLMResponse:
        """An answer that consumed its whole completion budget and arrived mid-JSON."""
        return gen.LLMResponse(
            text='{"plan_schema": "coursebook.plan.v2", "scope": "single", "title": "A sco',
            parsed=None,
            provider="fake",
            model="fake-model",
            input_tokens=120,
            # The provider's own count is the truncation signal (there is no finish_reason here).
            output_tokens=int(request.max_tokens),
            cost_usd=0.01,
        )

    def test_a_cut_plan_answer_is_re_asked_under_the_cut_label(self) -> None:
        lock = threading.Lock()
        seen = {"n": 0}

        def author(request: gen.LLMRequest) -> gen.LLMResponse:
            with lock:
                seen["n"] += 1
                first = seen["n"] == 1
            if first:
                return self.cut_answer(request)
            # A committed single-session course: the committed recipe applies, but the band has no
            # review slot (E2E S3), so the plan schedules none. The one-off variant would fail the
            # committed recipe rule the job actually applies.
            return response(blueprint_plan(scope="single", recipe="committed"))

        llm = FakeLLM(
            {
                "coursebook.plan.generate": author,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(
            self.connection, plan_job(scope="single"), llm, FakeSearch(), now=NOW
        )

        # Two authoring calls: the cut answer and its one re-ask. The job reaches a validated
        # draft instead of the old GenerationRejected / INTERNAL_ERROR dead end.
        self.assertEqual(llm.calls_for("coursebook.plan.generate"), 2)
        generates = [
            request for request in llm.requests if request.purpose == "coursebook.plan.generate"
        ]
        self.assertTrue(generates[1].prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX))
        self.assertIn("cut off before it finished", generates[1].instructions)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["validation_verdict"], "pass")

    def test_a_short_malformed_plan_answer_is_not_called_truncated(self) -> None:
        """The repair is for a cut answer only; a short bad answer stays a rejection."""
        short = gen.LLMResponse(
            text="not json",
            parsed=None,
            provider="fake",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.01,
        )
        llm = FakeLLM(
            {
                "coursebook.plan.generate": short,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        with self.assertRaises(gen.GenerationRejected):
            gen.run_plan_job(
                self.connection, plan_job(scope="single"), llm, FakeSearch(), now=NOW
            )
        self.assertEqual(llm.calls_for("coursebook.plan.generate"), 1)


class PlanBudgetScalesWithPassPlanTest(GenerationTestBase):
    """G4: the call and dollar ceilings are sized from the validation pass plan."""

    def full_plan(self) -> dict:
        """A legal full-band plan at the band's ceiling: 40 objectives in 10 units."""
        return blueprint_plan(
            scope="full", units=10, objectives_per_unit=4, recipe="committed"
        )

    def test_a_forty_objective_plan_builds_fourteen_validation_passes(self) -> None:
        plan = self.full_plan()
        claims = gen.plan_claim_labels(plan)
        # 40 objectives + 10 units + the learner outcome.
        self.assertEqual(len(claims), 51)
        passes = gen.plan_pass_count(claims)
        self.assertEqual(passes, 14)
        # The task's acceptance floor: two attempts of one generate plus every pass, plus slack.
        budget = gen.plan_cost_budget("full", claims=claims)
        self.assertGreaterEqual(budget.max_calls, 2 * (1 + passes) + 4)
        # And the ceiling is the stage's own worst legal path, not the floor with a round number.
        self.assertEqual(budget.max_calls, gen.plan_calls(passes)[1])
        # Unknown-cost calls are charged at DECLARED_CALL_COST_USD, so the dollar ceiling has to
        # cover that many calls; the flat $0.75 would have tripped at call 19.
        dollar_ceiling = budget.max_cost_usd
        assert dollar_ceiling is not None
        self.assertGreaterEqual(
            dollar_ceiling, budget.max_calls * gen.DECLARED_CALL_COST_USD
        )

    def test_the_band_sized_budget_already_covers_the_worst_legal_plan(self) -> None:
        """A job must be payable before its first call, when no candidate exists yet."""
        for scope in ("single", "short", "full", None):
            band = gen.plan_cost_budget(scope)
            self.assertGreaterEqual(band.max_calls, 2 * (1 + gen.plan_pass_count(gen.plan_claim_band(scope))) + 4)
        self.assertEqual(gen.plan_cost_budget("full").max_calls, gen.plan_calls(14)[1])

    def test_a_wide_candidate_raises_a_narrow_band_budget(self) -> None:
        """A parent plan can carry more objectives than its scope band; the candidate wins."""
        narrow = gen.plan_cost_budget("single")
        wide = gen.plan_cost_budget("single", claims=gen.plan_claim_labels(self.full_plan()))
        self.assertGreater(wide.max_calls, narrow.max_calls)

    def test_a_full_plan_job_records_its_sized_budget(self) -> None:
        llm = FakeLLM(
            {
                "coursebook.plan.generate": lambda request: response(self.full_plan()),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(
            self.connection,
            plan_job(scope="full", goal="Hold a ten minute conversation in Japanese"),
            llm,
            FakeSearch(),
            now=NOW,
        )
        self.assertEqual(result["validation_verdict"], "pass")
        usage = result["usage"]
        self.assertEqual(usage["budget"]["source"], "declared")
        self.assertEqual(usage["budget"]["max_calls"], gen.plan_calls(14)[1])
        # One generation and one call per validation pass, and nothing refused.
        self.assertEqual(usage["calls"], 1 + 14)
        self.assertEqual(llm.calls_for("coursebook.plan.validate"), 14)

    def test_one_validator_refusal_does_not_die_of_budget(self) -> None:
        """Attempt 1 is refused on every pass; attempt 2 re-authors and validates inside budget."""
        plan = self.full_plan()
        rejecting = validation_from_fixture("validation_reject_hazard")
        passing = validation_from_fixture("validation_pass")
        lock = threading.Lock()
        seen = {"n": 0}
        passes = gen.plan_pass_count(gen.plan_claim_labels(plan))

        def validator(request: gen.LLMRequest) -> gen.LLMResponse:
            with lock:
                seen["n"] += 1
                index = seen["n"]
            # Every pass of attempt 1 rejects; every pass of attempt 2 passes.
            return rejecting(request) if index <= passes else passing(request)

        llm = FakeLLM(
            {
                "coursebook.plan.generate": lambda request: response(plan),
                "coursebook.plan.validate": validator,
            }
        )
        result = gen.run_plan_job(
            self.connection,
            plan_job(scope="full", goal="Hold a ten minute conversation in Japanese"),
            llm,
            FakeSearch(),
            now=NOW,
        )

        # Two authoring attempts and both validation waves were paid for, and the job finished
        # with a verdict instead of a cost-ceiling abort.
        self.assertEqual(llm.calls_for("coursebook.plan.generate"), 2)
        self.assertEqual(llm.calls_for("coursebook.plan.validate"), 2 * passes)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["validation_verdict"], "pass")
        budget = result["usage"]["budget"]
        self.assertGreaterEqual(budget["max_calls"], result["usage"]["calls"])

    def test_an_operator_ceiling_still_wins(self) -> None:
        budget = gen.plan_cost_budget("full", brief_budget_usd=0.5)
        self.assertEqual(budget.max_cost_usd, 0.5)
        self.assertEqual(budget.source, "operator_brief")


if __name__ == "__main__":
    unittest.main()
