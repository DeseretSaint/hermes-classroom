"""CP-015d: the plan validator is given the rubric a narrowed plan is judged by.

CP-015b ran an R-2-compliant Sourdough plan through the real create flow and got a stored
``reject`` on ``objective_alignment`` and ``internal_contradiction``. The plan had done exactly
what the author rule asks — narrowed ``learner_outcome``, plus prefixed ``exclusions`` for every
goal capability the ledger could not support — and ``goal_capability_disclosure`` passed. The two
legacy criteria failed because the pass was handed criterion *names* and a curriculum-sequence
paragraph, nothing that said a disclosed gap is not misalignment. The model read the raw goal
sentence as the yardstick.

What is pinned here:

* both plan passes state the rubric for ``objective_alignment``, ``internal_contradiction`` and
  ``goal_capability_disclosure``, and the disclosure rule quotes the exclusion prefix verbatim;
* a scripted validator that follows that rubric passes the disclosed-gap plan, and the same plan
  with one capability missing from both objectives and exclusions rejects on
  ``goal_capability_disclosure`` and on nothing else;
* the deterministic outcome-integrity gate (c1) still refuses an outcome that promises a
  capability its own exclusions remove — the rubric change does not weaken it;
* an honest 11-criterion, 3-objective answer fits ``MAX_VALIDATION_BYTES``, and the per-answer
  bound is derived from the pass schema, so a schema-legal answer cannot fail on byte count
  before the schema judges it (the measured 36 895-byte / 24 576-byte failure).
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from coursebook import research as research_mod

from tests import blueprint_support

GOAL = (
    "Keep a starter alive and bake a reliable open-crumb sourdough loaf at home: "
    "build the levain, develop the dough, shape, and bake with steam."
)

#: The narrowed outcome the author rule asks for: it promises only what the ledger supports.
NARROWED_OUTCOME = (
    "Keep a sourdough starter alive and active at home, and tell when it is ready to bake with."
)

#: The old contradiction, kept here only to prove the deterministic gate still refuses it.
PROMISING_OUTCOME = (
    "Keep a sourdough starter alive and active at home, then bake a reliable open-crumb sourdough "
    "loaf: build the levain, develop the dough, shape it, and bake with steam."
)

DISCLOSED_EXCLUSIONS = [
    "Not covered — no supporting source: levain",
    "Not covered — no supporting source: dough development",
    "Not covered — no supporting source: shaping",
    "Not covered — no supporting source: steam baking",
    "Not covered — no supporting source: open crumb",
]


def _plan(*, exclusions, outcome: str = NARROWED_OUTCOME, objectives: int = 3) -> dict:
    plan = blueprint_support.blueprint_plan(
        scope="short", units=1, objectives_per_unit=objectives
    )
    plan["learner_outcome"] = outcome
    plan["exclusions"] = list(exclusions)
    # The one capability the narrowed outcome keeps must be covered by an objective.
    plan["objectives"][0]["title"] = "Explain how a starter is made and kept active"
    plan["objectives"][0]["evidence_criteria"] = [
        "States what a starter is and how it is kept active, in the learner's own words"
    ]
    return plan


def _requests(plan: dict) -> list[gen.LLMRequest]:
    return gen.build_plan_validation_requests(
        plan=plan,
        goal=GOAL,
        recipe="casual",
        dials={},
        locale="en-US",
        research_run=research_mod.ResearchRun(
            status="ok", queries=[], sources=[], reason="fixture"
        ),
        scope="short",
    )


def _claim_labels(request: gen.LLMRequest) -> list[str]:
    return (
        (request.schema.get("properties", {}).get("claim_verdicts") or {})
        .get("items", {})
        .get("properties", {})
        .get("item", {})
        .get("enum")
        or []
    )


def _hidden_capability(plan: dict) -> str | None:
    """The rubric, scripted: a goal capability no objective covers and no prefixed exclusion names."""
    covered = " ".join(
        f"{objective.get('title', '')} {' '.join(objective.get('evidence_criteria') or [])}"
        for objective in plan.get("objectives") or []
    ).casefold()
    disclosed = " ".join(
        str(entry)
        for entry in plan.get("exclusions") or []
        if str(entry).startswith(gen.EXCLUSION_PREFIX)
    ).casefold()
    for capability in ("levain", "dough", "shap", "steam", "open crumb", "starter"):
        if capability in GOAL.casefold() and capability not in covered and capability not in disclosed:
            return capability
    return None


def _answer(request: gen.LLMRequest, plan: dict) -> dict:
    """A scripted validator that follows the rubric stated in the pass it was handed."""
    owned = gen.validation_pass_criteria(request)
    document: dict = {
        "verdict": "pass",
        "criteria": [
            {
                "id": criterion,
                "verdict": "pass",
                "reason": f"{criterion} holds on the plan's own declared outcome and parts",
            }
            for criterion in owned
        ],
        "rejections": [],
    }
    if "goal_capability_disclosure" in owned:
        hidden = _hidden_capability(plan)
        if hidden is not None:
            document["verdict"] = "reject"
            for entry in document["criteria"]:
                if entry["id"] == "goal_capability_disclosure":
                    entry["verdict"] = "fail"
                    entry["reason"] = (
                        f"the goal names {hidden} but no objective covers it and no exclusion "
                        "begins with the disclosure prefix"
                    )
            document["rejections"] = [
                {
                    "item": "plan.exclusions",
                    "criterion": "goal_capability_disclosure",
                    "reason": (
                        f"The goal names {hidden}, and no objective covers it and no "
                        "exclusion begins with the disclosure prefix."
                    ),
                }
            ]
    labels = _claim_labels(request)
    if labels:
        document["claim_verdicts"] = [
            {
                "item": label,
                "source_id": None,
                "support": "unverified",
                "reason": "no supplied source carries this claim",
            }
            for label in labels
        ]
    return document


def _verdict(plan: dict) -> tuple[dict, list[gen.LLMRequest]]:
    requests = _requests(plan)
    reports = []
    for request in requests:
        document = _answer(request, plan)
        response = gen.LLMResponse(
            text=gen.canonical_json(document),
            parsed=document,
            provider="fixture",
            model="scripted-validator",
        )
        parsed = gen._parse_validation_answer(response, request, what="plan validation")
        reports.append((gen.validation_pass_criteria(request), parsed))
    verdict = gen.validation_verdict(
        gen.merge_validation_reports(reports), research_status="ok"
    )
    return verdict, requests


class RubricTextTest(unittest.TestCase):
    """The pass the validator answers must state the rule it is judged by (H-191)."""

    def setUp(self) -> None:
        self.requests = _requests(_plan(exclusions=DISCLOSED_EXCLUSIONS))

    def _instructions_for(self, criterion: str) -> str:
        for request in self.requests:
            if criterion in gen.validation_pass_criteria(request):
                return request.instructions
        raise AssertionError(f"no plan pass owns {criterion}")

    def test_objective_alignment_is_judged_against_the_plan_not_the_raw_goal(self) -> None:
        text = self._instructions_for("objective_alignment")
        self.assertIn("objective_alignment", text)
        self.assertIn(
            "not against every capability the raw goal sentence names", text
        )
        self.assertIn(
            "a capability that appears only in a prefixed exclusions entry is disclosed scope, "
            "not misalignment",
            text,
        )
        self.assertIn("it is never an objective_alignment failure", text)
        # The criterion keeps its other jobs.
        self.assertIn("every unit after the first must name the earlier unit(s)", text)
        self.assertIn("each objective must advance the learner_outcome", text)

    def test_internal_contradiction_reads_the_plans_own_parts(self) -> None:
        text = self._instructions_for("internal_contradiction")
        self.assertIn("internal_contradiction", text)
        self.assertIn("over the plan's own parts against each other", text)
        self.assertIn("cannot both hold", text)
        self.assertIn("a disclosed limit, not a contradiction with the goal", text)
        self.assertIn("Do not reject on this criterion for a disclosed gap", text)

    def test_the_disclosure_rule_quotes_the_prefix_exactly(self) -> None:
        text = self._instructions_for("goal_capability_disclosure")
        self.assertIn(gen.EXCLUSION_PREFIX, text)
        self.assertEqual(gen.EXCLUSION_PREFIX, "Not covered — no supporting source:")
        self.assertIn("appears in neither is a reject", text)
        self.assertIn("disclosed, not covered", text)

    def test_the_wide_plan_builder_states_the_same_rubrics(self) -> None:
        text = gen._validation_instructions(subject="plan", criteria=gen.VALIDATION_CRITERIA)
        for marker in (
            "not against every capability the raw goal sentence names",
            "over the plan's own parts against each other",
            gen.EXCLUSION_PREFIX,
        ):
            self.assertIn(marker, text)
        lesson = gen._validation_instructions(
            subject="lesson and its learner page", criteria=gen.LESSON_VALIDATION_CRITERIA
        )
        self.assertNotIn("raw goal sentence", lesson)
        self.assertNotIn("plan's own parts", lesson)

    def test_the_criterion_set_is_not_widened(self) -> None:
        self.assertEqual(
            gen.VALIDATION_CRITERIA,
            (
                "objective_alignment",
                "goal_capability_disclosure",
                "source_support",
                "factual_correctness",
                "answer_uniqueness",
                "alternative_coverage",
                "rubric_consistency",
                "internal_contradiction",
                "answer_leakage",
                "hazard_age_appropriateness",
                "evidence_target_fit",
            ),
        )
        for batch in gen.VALIDATION_CRITERIA_PASSES:
            self.assertLessEqual(len(batch), gen.VALIDATION_CRITERIA_PER_PASS_MAX)
        self.assertNotIn("goal_capability_disclosure", gen.LESSON_VALIDATION_CRITERIA)

    def test_the_version_advanced_for_the_new_instruction_text(self) -> None:
        # v7 (CP-015d) is the narrowed-plan rubric; v8 (CP-015g) adds the unit-sections rule that
        # one unit is judged against its own goal and objectives, and drops the whole-course
        # learner_outcome from the unit-stage brief.
        self.assertEqual(gen.VALIDATION_PROMPT_VERSION, "validation-prompt.v8")


class DisclosedGapVerdictTest(unittest.TestCase):
    """A disclosed gap is the intended outcome; a hidden one is the failure c2 names."""

    def test_the_disclosed_gap_plan_passes_when_the_validator_follows_the_rubric(self) -> None:
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        # The deterministic outcome-integrity gate (c1) accepts the narrowed plan.
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale="en-US", ledger=[], scope="short"
        )
        self.assertIsNone(_hidden_capability(plan))
        verdict, response = _verdict(plan)
        self.assertEqual(verdict["verdict"], "pass", verdict["rejections"])
        self.assertEqual(verdict["failed"], [])
        self.assertEqual(verdict["rejections"], [])
        for request in response:
            if "objective_alignment" in gen.validation_pass_criteria(request):
                self.assertIn("disclosed scope, not misalignment", request.instructions)

    def test_the_undisclosed_gap_plan_rejects_on_disclosure_only(self) -> None:
        hidden = [entry for entry in DISCLOSED_EXCLUSIONS if "shaping" not in entry]
        plan = _plan(exclusions=hidden)
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale="en-US", ledger=[], scope="short"
        )
        self.assertEqual(_hidden_capability(plan), "shap")
        verdict, _ = _verdict(plan)
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(verdict["failed"], ["goal_capability_disclosure"])
        self.assertEqual(
            [entry["criterion"] for entry in verdict["rejections"]],
            ["goal_capability_disclosure"],
        )

    def test_the_legacy_criterion_names_never_carry_the_disclosed_gap(self) -> None:
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        verdict, _ = _verdict(plan)
        self.assertNotIn("objective_alignment", verdict["failed"])
        self.assertNotIn("internal_contradiction", verdict["failed"])

    def test_the_deterministic_gate_still_refuses_a_promise_its_exclusions_remove(self) -> None:
        # CP-015d must not trade c1 for a kinder rubric: an outcome that promises shaping while an
        # exclusion removes it is still refused before any model is asked.
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS, outcome=PROMISING_OUTCOME)
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan, recipe="casual", dials={}, locale="en-US", ledger=[], scope="short"
            )
        self.assertIn("outcome integrity", "\n".join(caught.exception.reasons))


class ValidationAnswerBoundTest(unittest.TestCase):
    """The output bound is sized by the pass schema, not by a stage-wide constant."""

    def test_an_honest_eleven_criterion_three_objective_answer_fits_the_constant(self) -> None:
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        labels = gen.plan_claim_labels(plan)
        self.assertEqual(len([label for label in labels if label.startswith("objective:")]), 3)
        document = {
            "verdict": "pass",
            "criteria": [
                {
                    "id": criterion,
                    "verdict": "pass",
                    "reason": (
                        f"{criterion} is visible in the plan's own declared outcome, objectives "
                        "and checks; the reason names the artifact feature it rests on"
                    )[: gen.VALIDATION_REASON_MAX_CHARS],
                }
                for criterion in gen.VALIDATION_CRITERIA
            ],
            "rejections": [],
            "claim_verdicts": [
                {
                    "item": label,
                    "source_id": None,
                    "support": "unverified",
                    "reason": "no supplied source carries this claim",
                }
                for label in labels
            ],
        }
        answer = gen.canonical_json(document)
        size = len(answer.encode("utf-8"))
        self.assertLess(
            size,
            gen.MAX_VALIDATION_BYTES,
            f"an honest 11-criterion, 3-objective answer is {size} bytes",
        )
        request = gen.LLMRequest(
            purpose="coursebook.plan.validate",
            prompt_version=gen.VALIDATION_PROMPT_VERSION,
            system_prompt=gen.VALIDATION_SYSTEM_PROMPT,
            instructions=gen._validation_instructions(
                subject="plan", criteria=gen.VALIDATION_CRITERIA
            ),
            input_text="{}",
            schema=gen.VALIDATION_SCHEMA,
            schema_name="coursebook_validation_v1",
            max_tokens=gen.VALIDATION_OUTPUT_TOKENS,
            timeout_s=180.0,
        )
        response = gen.LLMResponse(text=answer, parsed=document, provider="fixture")
        parsed = gen._parse_validation_answer(response, request, what="plan validation")
        self.assertEqual(len(parsed["criteria"]), len(gen.VALIDATION_CRITERIA))

    def test_the_bound_is_derived_from_the_pass_schema(self) -> None:
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        for request in _requests(plan):
            bound = gen.validation_answer_bound(request.schema)
            self.assertGreaterEqual(bound, gen.MAX_VALIDATION_BYTES)
            # The largest answer the pass schema admits fits the derived bound by construction.
            owned = gen.validation_pass_criteria(request)
            labels = _claim_labels(request)
            document: dict = {"verdict": "pass"}
            if owned:
                document["criteria"] = [
                    {
                        "id": criterion,
                        "verdict": "pass",
                        "reason": "r" * gen.VALIDATION_REASON_MAX_CHARS,
                    }
                    for criterion in owned
                ]
                rejections = request.schema["properties"]["rejections"]["maxItems"]
                document["rejections"] = [
                    {
                        "item": "i" * 80,
                        "criterion": owned[index % len(owned)],
                        "reason": "r" * gen.VALIDATION_REASON_MAX_CHARS,
                        "fix_hint": "f" * gen.VALIDATION_REASON_MAX_CHARS,
                    }
                    for index in range(rejections)
                ]
            if labels:
                document["claim_verdicts"] = [
                    {
                        "item": label,
                        "source_id": "s" * 64,
                        "support": "unverified",
                        "evidence_quote": "q" * 300,
                        "reason": "r" * gen.VALIDATION_REASON_MAX_CHARS,
                        "excerpt": "e" * 600,
                    }
                    for label in labels
                ]
            answer = gen.canonical_json(document)
            gen.validate_artifact(request.schema, document, what="maximum legal answer")
            self.assertLessEqual(
                len(answer.encode("utf-8")),
                bound,
                "the derived bound must admit every schema-legal answer",
            )

    def test_the_measured_byte_count_no_longer_fails_an_honest_pass_first(self) -> None:
        # CP-015b's 36 895-byte answer was refused at the 24 576-byte gate before the schema saw
        # it. The criteria pass's derived bound now admits schema-legal output and the schema is
        # the gate that judges its shape (reasons <= 240 characters, one rejection per judged item).
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        criteria_pass = next(
            request
            for request in _requests(plan)
            if "objective_alignment" in gen.validation_pass_criteria(request)
        )
        self.assertGreater(gen.validation_answer_bound(criteria_pass.schema), 36_895)
        self.assertEqual(
            criteria_pass.schema["properties"]["rejections"]["maxItems"],
            len(gen.validation_pass_criteria(criteria_pass))
            + len(_claim_labels(criteria_pass)),
        )

    def test_the_prompt_states_the_reason_bound_the_schema_enforces(self) -> None:
        plan = _plan(exclusions=DISCLOSED_EXCLUSIONS)
        marker = f"at most {gen.VALIDATION_REASON_MAX_CHARS} characters"
        for request in _requests(plan):
            self.assertIn(marker, request.instructions)
            self.assertNotIn("at most 200 characters", request.instructions)
            schema = request.schema
            self.assertEqual(
                schema["properties"]["criteria"]["items"]["properties"]["reason"]["maxLength"],
                gen.VALIDATION_REASON_MAX_CHARS,
            )


if __name__ == "__main__":
    unittest.main()
