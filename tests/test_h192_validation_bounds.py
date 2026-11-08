"""H-192 — plan validation output is bounded per pass, independent of plan size.

The measured defect on master ``127cce1``: ``plan_claim_labels`` emits one label per objective,
one per unit and ``plan:learner_outcome``, and every label rode on the single criteria pass. A
full-scope plan therefore demanded 13–42 claim verdicts *plus* ten criterion verdicts in one
answer: 376 896 ms / 29 386 completion tokens, then a schema violation reported as
``INTERNAL_ERROR``. Widening the deadline is not a repair.

These tests pin the repair without a provider:

* the claim set is cut into fixed-size batches, so no pass's answer grows with plan size;
* the criteria pass carries at most one batch; leftovers are claim-only passes;
* a claim-only pass may not answer a criterion, a rejection or an artifact verdict;
* the merge still produces exactly one full ten-criterion review and every claim once;
* a validator answer that violates its own narrowed schema is ``VALIDATION_FAILED``
  (non-retryable), not ``INTERNAL_ERROR``;
* a content rejection (``GenerationRejected``) is ``VALIDATION_FAILED`` (non-retryable), not
  ``INTERNAL_ERROR`` / retryable.
"""
from __future__ import annotations

import unittest

from coursebook import generation as gen
from coursebook import job_service
from coursebook import research as research_mod


def big_plan(objectives: int, units: int = 2) -> dict:
    """A plan whose claim set grows the way a full-scope blueprint's does."""
    plan = {
        "title": "Full scope",
        "goal": "Reach the goal",
        "learner_outcome": "Demonstrate the goal once",
        "objectives": [
            {"ordinal": index, "title": f"Objective {index}", "support": "unverified"}
            for index in range(1, objectives + 1)
        ],
        "units": [
            {"ordinal": index, "title": f"Unit {index}", "goal": "Advance"}
            for index in range(1, units + 1)
        ],
        "sections": [],
    }
    return plan


def build_requests(plan: dict, **overrides) -> list[gen.LLMRequest]:
    kwargs = dict(
        plan=plan,
        goal="Reach the goal",
        recipe="committed",
        dials={},
        locale="en-US",
        research_run=research_mod.ResearchRun(
            status="unavailable", queries=[], sources=[], reason="test"
        ),
        scope="full",
    )
    kwargs.update(overrides)
    return gen.build_plan_validation_requests(**kwargs)


def claim_enum(request: gen.LLMRequest) -> list[str]:
    return (
        (request.schema.get("properties", {}).get("claim_verdicts") or {})
        .get("items", {})
        .get("properties", {})
        .get("item", {})
        .get("enum")
        or []
    )


def report_for(request: gen.LLMRequest) -> dict:
    """The minimal schema-valid answer for exactly the pass that was handed."""
    owned = gen.validation_pass_criteria(request)
    labels = claim_enum(request)
    if owned:
        report = {
            "verdict": "pass",
            "criteria": [
                {"id": name, "verdict": "pass", "reason": f"{name} holds on the authored plan"}
                for name in owned
            ],
            "rejections": [],
        }
    else:
        report = {}
    if labels:
        report["claim_verdicts"] = [
            {
                "item": label,
                "source_id": None,
                "support": "unverified",
                "reason": "no supplied source carries this claim",
            }
            for label in labels
        ]
    return report


class ClaimBatchingTest(unittest.TestCase):
    def test_no_pass_demands_more_claims_than_the_fixed_batch(self) -> None:
        for objectives in (3, 20, 60):
            requests = build_requests(big_plan(objectives))
            for request in requests:
                limit = (
                    gen.CLAIM_VERDICTS_PER_PASS
                    if gen.validation_pass_criteria(request)
                    else gen.CLAIM_ONLY_VERDICTS_PER_PASS
                )
                self.assertLessEqual(
                    len(claim_enum(request)),
                    limit,
                    f"{len(claim_enum(request))} claims in one answer for {objectives} objectives",
                )

    def test_the_criteria_pass_keeps_the_whole_ten_criterion_review(self) -> None:
        requests = build_requests(big_plan(20))
        self.assertEqual(gen.validation_pass_criteria(requests[0]), gen.VALIDATION_CRITERIA)

    def test_leftover_claims_become_claim_only_passes(self) -> None:
        plan = big_plan(20)
        labels = gen.plan_claim_labels(plan)
        requests = build_requests(plan)
        criteria_passes = len(gen.VALIDATION_CRITERIA_PASSES)
        leftover = max(0, len(labels) - criteria_passes * gen.CLAIM_VERDICTS_PER_PASS)
        expected = criteria_passes + -(-leftover // gen.CLAIM_ONLY_VERDICTS_PER_PASS)
        self.assertEqual(len(requests), expected)
        for request in requests[1:]:
            self.assertEqual(gen.validation_pass_criteria(request), ())
            self.assertNotIn("criteria", request.schema["properties"])
            self.assertNotIn("rejections", request.schema["properties"])
            self.assertNotIn("verdict", request.schema["properties"])

    def test_every_claim_is_judged_exactly_once(self) -> None:
        plan = big_plan(20)
        labels = gen.plan_claim_labels(plan)
        demanded: list[str] = []
        for request in build_requests(plan):
            demanded.extend(claim_enum(request))
        self.assertEqual(sorted(demanded), sorted(labels))
        self.assertEqual(len(demanded), len(set(demanded)))

    def test_a_small_plan_still_makes_one_call(self) -> None:
        # Single/short plans measured 3–5 claim labels; they must not pay for extra passes.
        plan = big_plan(2, units=1)
        self.assertLessEqual(len(gen.plan_claim_labels(plan)), gen.CLAIM_VERDICTS_PER_PASS)
        self.assertEqual(len(build_requests(plan)), 1)

    def test_a_claim_only_pass_is_told_it_rules_on_no_criterion(self) -> None:
        request = build_requests(big_plan(20))[1]
        self.assertIn("no criteria", request.instructions)
        self.assertIn("no overall verdict", request.instructions)
        for label in claim_enum(request):
            self.assertIn(label, request.instructions)

    def test_a_claim_only_schema_rejects_a_criterion_answer(self) -> None:
        request = build_requests(big_plan(20))[1]
        report = report_for(request)
        report["criteria"] = [
            {"id": gen.VALIDATION_CRITERIA[0], "verdict": "pass", "reason": "stray"}
        ]
        with self.assertRaises(gen.GenerationRejected):
            gen.validate_artifact(request.schema, report, what="pass")


class MergedReviewTest(unittest.TestCase):
    def test_the_merge_is_the_full_review_and_every_claim(self) -> None:
        plan = big_plan(20)
        requests = build_requests(plan)
        merged = gen.merge_validation_reports(
            [(gen.validation_pass_criteria(request), report_for(request)) for request in requests]
        )
        self.assertEqual(
            [entry["id"] for entry in merged["criteria"]], list(gen.VALIDATION_CRITERIA)
        )
        self.assertEqual(merged["verdict"], "pass")
        self.assertEqual(len(merged["claim_verdicts"]), len(gen.plan_claim_labels(plan)))
        verdict = gen.validation_verdict(merged, research_status="unavailable")
        self.assertEqual(verdict["verdict"], "pass")

    def test_a_claim_only_report_cannot_reject_the_artifact(self) -> None:
        plan = big_plan(20)
        requests = build_requests(plan)
        reports = []
        for index, request in enumerate(requests):
            report = report_for(request)
            if index > 0:
                # A raw report cannot smuggle a verdict or rejection through a claim-only pass:
                # the pass owns no criterion, so its artifact-level fields are ignored.
                report["verdict"] = "reject"
                report["rejections"] = [
                    {"item": "plan", "criterion": gen.VALIDATION_CRITERIA[0], "reason": "x"}
                ]
            reports.append((gen.validation_pass_criteria(request), report))
        merged = gen.merge_validation_reports(reports)
        self.assertEqual(merged["verdict"], "pass")
        self.assertEqual(merged["rejections"], [])

    def test_merge_never_invents_the_claims_of_a_missing_pass(self) -> None:
        plan = big_plan(20)
        requests = build_requests(plan)
        reports = [
            (gen.validation_pass_criteria(request), report_for(request))
            for request in requests[:-1]
        ]
        merged = gen.merge_validation_reports(reports)
        # The claim set is incomplete, but criteria are complete: merge itself only guarantees
        # criteria. The pipeline's demand is that a lost pass (timeout/error) fails validation
        # before merge; this test pins that the merge never invents the missing claims.
        self.assertEqual(
            len(merged["claim_verdicts"]),
            len(gen.plan_claim_labels(plan)) - len(claim_enum(requests[-1])),
        )


class ShapeAndRejectionLabelsTest(unittest.TestCase):
    def _request(self, labels: tuple[str, ...]) -> gen.LLMRequest:
        return gen.LLMRequest(
            purpose="coursebook.plan.validate",
            prompt_version=gen.VALIDATION_PROMPT_VERSION,
            system_prompt=gen.VALIDATION_SYSTEM_PROMPT,
            instructions=gen.validation_pass_instructions(
                subject="plan", criteria=(), claim_labels=labels
            ),
            input_text="{}",
            schema=gen.validation_pass_schema((), labels),
            schema_name="coursebook_validation_v1",
            max_tokens=2000,
            timeout_s=180.0,
        )

    def test_a_plan_validator_shape_violation_is_validation_failed(self) -> None:
        request = self._request(("objective:1",))
        response = gen.LLMResponse(
            text="{}",
            parsed={"claim_verdicts": []},  # minItems: 1 for this pass
            provider="nous",
            model="validator",
        )
        with self.assertRaises(gen.ModelOutputInvalid) as raised:
            gen._parse_validation_answer(response, request, what="plan validation")
        error = raised.exception
        self.assertEqual(error.code, "VALIDATION_FAILED")
        self.assertEqual(job_service._error_code(error), "VALIDATION_FAILED")
        self.assertEqual(error.purpose, "coursebook.plan.validate")
        self.assertFalse(job_service._stage_error(error)["retryable"])

    def test_a_content_rejection_is_validation_failed_not_retryable(self) -> None:
        rejected = gen.GenerationRejected(
            "unit 2 self_study delivery promises 'one supervised run' but its evidence_note "
            "requires a second supervised run"
        )
        error = job_service._stage_error(rejected)
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["category"], "validation")
        self.assertFalse(error["retryable"])
        self.assertIn("evidence_note", error["message"])

    def test_a_provider_outage_keeps_its_retryable_label(self) -> None:
        error = job_service._stage_error(gen.ProviderFailure("boom", purpose="coursebook.plan.validate"))
        self.assertEqual(error["code"], "HOST_UNAVAILABLE")
        self.assertTrue(error["retryable"])


class ShortClaimAtomTest(unittest.TestCase):
    """H-192b: sentence punctuation is not a claim.

    A live single-scope lesson was parked ``needs_review`` because its ``blocks[1].short`` ended
    with ``3:00.`` while the deep text said ``3:00``: the old atom pattern swallowed the period and
    the completeness gate read a false new claim. The gate must still catch a quantity the deep
    text genuinely lacks.
    """

    def test_sentence_final_punctuation_is_not_a_new_claim(self) -> None:
        deep = "A finish time between 2:30 and 3:00 is the target for this recipe."
        short = "The target finish time is 2:30 to 3:00."
        self.assertEqual(gen._short_problems([{"short": short, "deep": deep}]), [])

    def test_a_quantity_the_deep_text_lacks_is_still_a_new_claim(self) -> None:
        deep = "A finish time between 2:30 and 3:00 is the target for this recipe."
        short = "Target a finish time of 4:00 for this recipe."
        problems = gen._short_problems([{"short": short, "deep": deep}])
        self.assertTrue(problems)
        self.assertIn("4:00", problems[0])


class CommittedGradedCheckPromptTest(unittest.TestCase):
    """H-192b: the plan prompt states the rule the kernel enforces.

    ``enforce_plan_rules`` refuses a committed plan with no ``quiz`` check. Both plan prompts used
    to ask only for spaced review and independent evidence, so a compliant model could answer
    without a quiz and be rejected by a rule it was never told — measured live: two committed
    attempts failed with ``committed courses need graded checks`` and no plan document was written.
    """

    def test_both_plan_prompts_state_the_graded_check_rule(self) -> None:
        for builder in (gen._plan_instructions, gen._plan_instructions_v2):
            with self.subTest(builder=builder.__name__):
                committed = builder(
                    recipe="committed",
                    dials={},
                    locale="en-US",
                    research_status="ok",
                    scope="short",
                )
                self.assertIn("graded quiz check", committed)
                one_off = builder(
                    recipe="one_off",
                    dials={},
                    locale="en-US",
                    research_status="ok",
                    scope="short",
                )
                self.assertNotIn("graded quiz check", one_off)


if __name__ == "__main__":
    unittest.main()
