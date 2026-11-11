"""H-191 follow-up: the plan validator judges all ten criteria in bounded passes.

The measured defect (``audit/adversarial/h191-validate-stall/STATUS.md``) was a single
``coursebook.plan.validate`` call: ten criterion verdicts plus a support verdict per claim, 12–16 k
completion tokens, 243–286 s against a 180 s deadline, with the plugin's ``max_tokens`` not
forwarded by the host on the route in use. A forwarded 2 000-token cap returned 2 000 tokens of
reasoning and no content, so the repair is a smaller output demand per call, not a cap.

These tests pin the shape of that repair without a provider:

* every criterion is judged exactly once, by the pass that owns it;
* a pass cannot answer a criterion (or claim) it does not own — the narrowed schema rejects it;
* the merged report is the full ten-criterion review and nothing smaller;
* one lost pass fails the whole validation, so a partial review is never recorded as a pass;
* the outcome/independence vocabulary is unchanged, and same-model validation is still
  ``model_assessed``;
* the passes run together, so the aggregate wall time is the slowest pass, not the sum.
"""
from __future__ import annotations

import json
import threading
import time
import unittest
from unittest import mock

from coursebook import generation as gen
from coursebook import research as research_mod


def plan_fixture() -> dict:
    return {
        "title": "Order coffee politely",
        "goal": "Order a coffee politely in Japanese",
        "learner_outcome": "Order one drink politely at a counter",
        "objectives": [
            {"ordinal": 1, "title": "Use ください", "evidence_target": "production", "support": "unverified"}
        ],
        "units": [{"ordinal": 1, "title": "Counter basics", "goal": "Order once"}],
        "sections": [],
    }


def build_requests(**overrides):
    kwargs = dict(
        plan=plan_fixture(),
        goal="Order a coffee politely in Japanese",
        recipe="one_off",
        dials={},
        locale="ja-JP",
        research_run=research_mod.ResearchRun(status="unavailable", queries=[], sources=[], reason="test"),
        scope="single",
    )
    kwargs.update(overrides)
    return gen.build_plan_validation_requests(**kwargs)


def report_for(criteria, *, verdict="pass", claim_items=()):
    report = {
        "verdict": verdict,
        "criteria": [
            {"id": name, "verdict": "pass", "reason": f"{name} holds on the authored plan"}
            for name in criteria
        ],
        "rejections": [],
    }
    if claim_items:
        report["claim_verdicts"] = [
            {
                "item": item,
                "source_id": None,
                "support": "unverified",
                "reason": "no supplied source carries this claim",
            }
            for item in claim_items
        ]
    return report


def report_for_request(request, *, verdict="pass"):
    """A report that answers exactly the pass it was handed, claims included."""
    claim_enum = (
        request.schema["properties"]
        .get("claim_verdicts", {})
        .get("items", {})
        .get("properties", {})
        .get("item", {})
        .get("enum")
    ) or []
    return report_for(gen.validation_pass_criteria(request), verdict=verdict, claim_items=claim_enum)


class PartitionTest(unittest.TestCase):
    def test_every_criterion_is_owned_by_exactly_one_pass(self) -> None:
        owned = [name for batch in gen.VALIDATION_CRITERIA_PASSES for name in batch]
        self.assertEqual(len(owned), len(set(owned)), "a criterion is judged twice")
        self.assertEqual(tuple(owned), gen.VALIDATION_CRITERIA, "the reviewed set changed")

    def test_each_pass_demands_only_its_own_criteria(self) -> None:
        requests = build_requests()
        self.assertEqual(len(requests), len(gen.VALIDATION_CRITERIA_PASSES))
        for request, owned in zip(requests, gen.VALIDATION_CRITERIA_PASSES):
            self.assertEqual(gen.validation_pass_criteria(request), owned)
            criteria_schema = request.schema["properties"]["criteria"]
            self.assertEqual(criteria_schema["minItems"], len(owned))
            self.assertEqual(criteria_schema["maxItems"], len(owned))
            self.assertEqual(criteria_schema["items"]["properties"]["id"]["enum"], list(owned))
            self.assertEqual(
                request.schema["properties"]["rejections"]["items"]["properties"]["criterion"]["enum"],
                list(owned),
            )
            self.assertIn(owned[0], request.instructions)

    def test_a_pass_answers_with_its_own_criteria_only(self) -> None:
        for request in build_requests():
            gen.validate_artifact(request.schema, report_for_request(request), what="pass")  # no raise

    def test_a_pass_may_not_answer_a_criterion_it_does_not_own(self) -> None:
        # Built directly on a narrowed pass so the assertion does not depend on the shipped layout.
        owned = ("objective_alignment",)
        schema = gen.validation_pass_schema(owned)
        foreign = next(name for name in gen.VALIDATION_CRITERIA if name not in owned)
        payload = report_for([*owned, foreign])
        with self.assertRaises(gen.GenerationRejected) as raised:
            gen.validate_artifact(schema, payload, what="pass")
        self.assertIn("criteria", str(raised.exception))

    def test_a_pass_that_owns_no_claim_may_not_return_claim_verdicts(self) -> None:
        # The shipped layout gives the one pass the plan's claims, so a criteria-only pass is built
        # here directly: the narrowed schema is what forbids claim verdicts, not the layout.
        schema = gen.validation_pass_schema(gen.VALIDATION_CRITERIA, ())
        self.assertNotIn("claim_verdicts", schema["properties"])
        payload = report_for(gen.VALIDATION_CRITERIA, claim_items=("objective:1",))
        with self.assertRaises(gen.GenerationRejected):
            gen.validate_artifact(schema, payload, what="pass")

    def test_claim_labels_are_deterministic_and_judged_once(self) -> None:
        plan = plan_fixture()
        plan["objectives"].append({"ordinal": 2, "title": "Ask for the bill"})
        plan["units"].append({"ordinal": 2, "title": "Paying"})
        labels = gen.plan_claim_labels(plan)
        self.assertEqual(labels, ["objective:1", "objective:2", "unit:1", "unit:2", "plan:learner_outcome"])
        demanded: list[str] = []
        for request in build_requests(plan=plan):
            enum = request.schema["properties"].get("claim_verdicts", {}).get("items", {}).get(
                "properties", {}
            ).get("item", {}).get("enum")
            if enum:
                demanded.extend(enum)
        self.assertEqual(sorted(demanded), sorted(labels))
        self.assertEqual(len(demanded), len(set(demanded)), "a claim is judged by two passes")


class MergeTest(unittest.TestCase):
    def test_the_merged_report_is_the_full_ten_criterion_review(self) -> None:
        requests = build_requests()
        merged = gen.merge_validation_reports(
            [
                (gen.validation_pass_criteria(request), report_for(gen.validation_pass_criteria(request)))
                for request in requests
            ]
        )
        self.assertEqual([entry["id"] for entry in merged["criteria"]], list(gen.VALIDATION_CRITERIA))
        self.assertEqual(merged["verdict"], "pass")
        verdict = gen.validation_verdict(merged, research_status="unavailable")
        self.assertEqual(verdict["verdict"], "pass")
        self.assertEqual(verdict["criteria"], merged["criteria"])

    def test_a_pass_that_omits_one_of_its_criteria_is_not_a_smaller_review(self) -> None:
        requests = build_requests()
        reports = []
        for index, request in enumerate(requests):
            owned = gen.validation_pass_criteria(request)
            report = report_for(owned if index else owned[:-1])
            reports.append((owned, report))
        with self.assertRaises(gen.GenerationRejected) as raised:
            gen.merge_validation_reports(reports)
        self.assertIn("omitted criteria", str(raised.exception))
        self.assertIn(gen.VALIDATION_CRITERIA_PASSES[0][-1], str(raised.exception))

    def test_one_rejected_pass_rejects_the_whole_validation(self) -> None:
        requests = build_requests()
        reports = []
        for index, request in enumerate(requests):
            owned = gen.validation_pass_criteria(request)
            reports.append((owned, report_for(owned, verdict="reject" if index == 0 else "pass")))
        merged = gen.merge_validation_reports(reports)
        self.assertEqual(merged["verdict"], "reject")
        self.assertEqual(
            gen.validation_verdict(merged, research_status="unavailable")["outcome"],
            gen.OUTCOME_REJECTED,
        )

    def test_a_report_from_a_pass_cannot_widen_the_review(self) -> None:
        requests = build_requests()
        # A report that answers every criterion in the first pass is filtered to that pass's pair.
        merged = gen.merge_validation_reports(
            [
                (gen.validation_pass_criteria(request), report_for(gen.VALIDATION_CRITERIA))
                for request in requests
            ]
        )
        self.assertEqual([entry["id"] for entry in merged["criteria"]], list(gen.VALIDATION_CRITERIA))
        # CP-015a: the reviewed set is eleven criteria (goal_capability_disclosure added).
        self.assertEqual(len(merged["criteria"]), len(gen.VALIDATION_CRITERIA))

    def test_same_model_validation_is_still_model_assessed(self) -> None:
        requests = build_requests()
        merged = gen.merge_validation_reports(
            [(gen.validation_pass_criteria(request), report_for(gen.validation_pass_criteria(request)))
             for request in requests]
        )
        identity = {"model": "z-ai/glm-5.3-flash", "provider": "nous"}
        independence = gen.validation_independence(identity, dict(identity))
        verdict = gen.validation_verdict(merged, research_status="ok", independence=independence)
        self.assertEqual(independence, gen.INDEPENDENCE_SAME_MODEL)
        self.assertEqual(verdict["outcome"], gen.OUTCOME_MODEL_ASSESSED)
        self.assertFalse(verdict["independent"])


class MultiPassAggregationTest(unittest.TestCase):
    """The aggregation path, exercised with a local layout so cover exists for N > 1.

    The shipped grouping is one pass (see ``VALIDATION_CRITERIA_PASSES``), but the merge and the
    runner must stay correct for a caller that narrows the demand further.
    """

    PAIRS = tuple(
        (gen.VALIDATION_CRITERIA[index], gen.VALIDATION_CRITERIA[index + 1])
        # CP-015a: the criteria count is odd (eleven), so the last criterion has no partner in this
        # local pair layout. It is owned by the shipped 6/5 split; this fixture only needs a legal
        # multi-pass shape, and it asserts pass count, aggregation and loss handling, not coverage.
        for index in range(0, len(gen.VALIDATION_CRITERIA) - 1, 2)
    )

    def build_pair_requests(self):
        with mock.patch.object(gen, "VALIDATION_CRITERIA_PASSES", self.PAIRS):
            return build_requests()

    def test_the_passes_run_together_and_one_loss_fails_the_whole_validation(self) -> None:
        requests = self.build_pair_requests()
        self.assertEqual(len(requests), len(self.PAIRS))

        def slow_then_fail(request):
            time.sleep(0.2)
            if request is requests[2]:
                raise gen.ProviderTimeout("pass lost", purpose=request.purpose, deadline_s=180.0)
            report = report_for_request(request)
            return gen.LLMResponse(
                text=json.dumps(report),
                parsed=report,
                provider="fake",
                model="fake-validator",
                input_tokens=10,
                output_tokens=20,
                cost_usd=0.0,
            )

        seen: list[str] = []
        lock = threading.Lock()

        def llm(request):
            with lock:
                seen.append(request.purpose)
            return slow_then_fail(request)

        usage = gen._Usage(gen.CostBudget(max_calls=32, max_cost_usd=None))
        started = time.monotonic()
        with self.assertRaises(gen.ProviderTimeout):
            gen._run_validation_passes(llm, requests, usage)
        elapsed = time.monotonic() - started
        self.assertEqual(len(seen), len(requests), "every pass is submitted, none skipped")
        # Five 0.2 s passes run together: sequential would be 1.0 s.
        self.assertLess(elapsed, 0.8)
        self.assertEqual(len(usage.calls), len(requests) - 1)  # the lost pass recorded no call

    def test_the_call_ceiling_is_reserved_across_threads(self) -> None:
        requests = self.build_pair_requests()
        usage = gen._Usage(gen.CostBudget(max_calls=2, max_cost_usd=None))

        def llm(request):
            time.sleep(0.05)
            report = report_for_request(request)
            return gen.LLMResponse(
                text=json.dumps(report),
                parsed=report,
                provider="fake",
                model="fake-validator",
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
            )

        with self.assertRaises(gen.CostCeilingExceeded):
            gen._run_validation_passes(llm, requests, usage)
        self.assertLessEqual(len(usage.calls), 2)


if __name__ == "__main__":
    unittest.main()
