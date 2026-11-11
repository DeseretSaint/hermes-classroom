"""CP-015g/D1-F2 — a claim the plan itself marks ``unverified`` is a declared gap, not a defect.

Measured defect (``docs/cp015g-d1-f1/run-f1-live-r2.json``, job
``job_c3a5f5ca512a4d518e7b06c924e53eed``): the authored plan marked two of its four objectives
``support: "unverified"`` with empty ``source_ids`` — exactly what the authoring contract asks for
when no supplied excerpt carries the claim — and the independent validator refused the plan under
``source_support``:

    objective:2: The setup/aim procedure is unsourced and must not be presented to a learner as
    verified content.
    objective:4: The orbital-explanation objective is unsourced and must not be presented to a
    learner as verified content.

Neither objective presents itself as verified, so there is no unsupported claim to refuse. The
validator was judging the plan's honesty instead of its assertions, and the pipeline then spent a
whole authoring cycle trying to repair a gap that only research can close.

What is pinned here:

* ``source_support`` reclassifies a rejection that names a declared gap into a *sourcing note*
  and never counts it as a rejection;
* a rejection about a ``sourced`` objective — the real over-citation defect — is untouched;
* a refusal whose only grounds were declared gaps parks the plan ``needs_review`` on the first
  attempt, with the sourcing note recorded, instead of re-authoring;
* the validator prompt states the distinction before the answer (``validation-prompt.v12`` on the merged tree);
* nothing here invents a pass: a validator that fails the criterion still produces a refusal.
"""

from __future__ import annotations

import json
import sqlite3
import unittest

from coursebook import generation as gen
from tests.test_generation import NOW, FakeSearch, plan_fixture, plan_job, response

#: The measured rejection, verbatim from the live run record.
LIVE_REJECTION = (
    "The setup/aim procedure is unsourced and must not be presented to a learner as verified content."
)
LIVE_REJECTION_TWO = (
    "The orbital-explanation objective is unsourced and must not be presented to a learner as "
    "verified content."
)


def _criteria(**verdicts: str) -> list[dict]:
    """The ten criteria, ``pass`` unless named, in the contract's order."""
    return [
        {
            "id": criterion,
            "verdict": verdicts.get(criterion, "pass"),
            "reason": f"{criterion} judged by the fixture",
        }
        for criterion in gen.VALIDATION_CRITERIA
    ]


def _report(
    *,
    rejections: list[dict],
    verdict: str = "reject",
    **criteria: str,
) -> dict:
    return {
        "verdict": verdict,
        "criteria": _criteria(**criteria),
        "rejections": rejections,
        "claim_verdicts": [],
    }


def _unverified_objective(ordinal: int, title: str) -> dict:
    return {
        "objective_id": f"obj-{ordinal}",
        "ordinal": ordinal,
        "title": title,
        "evidence_target": "procedure",
        "support": "unverified",
        "source_ids": [],
    }


class DeclaredGapDetectionTest(unittest.TestCase):
    def test_an_unverified_objective_with_no_ids_is_a_declared_gap(self) -> None:
        plan = {
            "objectives": [
                _unverified_objective(1, "Set up the telescope"),
                {
                    "objective_id": "obj-2",
                    "ordinal": 2,
                    "title": "Explain why the moons move",
                    "support": "sourced",
                    "source_ids": ["src_alpha"],
                },
            ]
        }
        self.assertEqual(
            gen.plan_declared_gaps(plan),
            {"objective:1": "Set up the telescope"},
        )

    def test_a_sourced_objective_is_never_a_gap(self) -> None:
        plan = {
            "objectives": [
                {
                    "objective_id": "obj-1",
                    "ordinal": 1,
                    "title": "Explain why the moons move",
                    "support": "sourced",
                    "source_ids": ["src_alpha"],
                }
            ]
        }
        self.assertEqual(gen.plan_declared_gaps(plan), {})

    def test_an_unverified_objective_that_still_cites_is_not_a_gap(self) -> None:
        # The authoring rule refuses this shape; the gap rule must not launder it either.
        plan = {
            "objectives": [
                {
                    "objective_id": "obj-1",
                    "ordinal": 1,
                    "title": "Something",
                    "support": "unverified",
                    "source_ids": ["src_alpha"],
                }
            ]
        }
        self.assertEqual(gen.plan_declared_gaps(plan), {})

    def test_no_objectives_is_no_gap(self) -> None:
        self.assertEqual(gen.plan_declared_gaps({}), {})


class DeclaredGapReclassificationTest(unittest.TestCase):
    def verdict(self, report: dict, plan: dict) -> dict:
        return gen.validation_verdict(
            report,
            research_status="ok",
            declared_gaps=gen.plan_declared_gaps(plan),
        )

    def plan(self) -> dict:
        return {
            "objectives": [
                _unverified_objective(1, "Choose a telescope"),
                _unverified_objective(2, "Set up and aim the telescope"),
                _unverified_objective(3, "Observe the moons on two nights"),
                _unverified_objective(4, "Explain why the moons move"),
            ]
        }

    def test_the_live_gap_rejection_becomes_a_sourcing_note(self) -> None:
        report = _report(
            rejections=[
                {"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION},
                {"item": "objective:4", "criterion": "source_support", "reason": LIVE_REJECTION_TWO},
            ],
            source_support="fail",
        )
        verdict = self.verdict(report, self.plan())

        self.assertEqual(verdict["rejections"], [], "a declared gap is not a rejection")
        self.assertEqual(
            [note["item"] for note in verdict["sourcing_notes"]],
            ["objective:2", "objective:4"],
        )
        self.assertEqual(
            verdict["sourcing_notes"][0]["validator_reason"], LIVE_REJECTION,
            "the validator's own words are kept beside the note",
        )
        # No pass is invented: the validator still failed the plan, so the plan is refused.
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(verdict["outcome"], gen.OUTCOME_REJECTED)
        self.assertTrue(verdict["gap_only_refusal"])

    def test_an_underscore_or_space_locator_matches_the_same_claim(self) -> None:
        for item in ("objective_2", "objective 2", "OBJECTIVE:2"):
            report = _report(
                rejections=[{"item": item, "criterion": "source_support", "reason": LIVE_REJECTION}],
                source_support="fail",
            )
            verdict = self.verdict(report, self.plan())
            self.assertEqual(
                [note["item"] for note in verdict["sourcing_notes"]],
                ["objective:2"],
                item,
            )

    def test_a_sourced_objective_keeps_its_rejection(self) -> None:
        plan = {
            "objectives": [
                {
                    "objective_id": "obj-3",
                    "ordinal": 3,
                    "title": "Observe the moons on two nights",
                    "support": "sourced",
                    "source_ids": ["src_alpha"],
                }
            ]
        }
        report = _report(
            rejections=[
                {
                    "item": "objective:3",
                    "criterion": "source_support",
                    "reason": "It is marked sourced, but the supplied excerpt does not show this.",
                }
            ],
            source_support="fail",
        )
        verdict = self.verdict(report, plan)
        self.assertEqual(len(verdict["rejections"]), 1)
        self.assertEqual(verdict["sourcing_notes"], [])
        self.assertFalse(verdict["gap_only_refusal"])

    def test_a_mixed_refusal_keeps_the_real_defect_and_records_the_gap(self) -> None:
        plan = {
            "objectives": [
                _unverified_objective(2, "Set up and aim the telescope"),
                {
                    "objective_id": "obj-3",
                    "ordinal": 3,
                    "title": "Observe the moons on two nights",
                    "support": "sourced",
                    "source_ids": ["src_alpha"],
                },
            ]
        }
        report = _report(
            rejections=[
                {"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION},
                {
                    "item": "objective:3",
                    "criterion": "source_support",
                    "reason": "The cited excerpt does not carry this claim.",
                },
            ],
            source_support="fail",
        )
        verdict = self.verdict(report, plan)
        self.assertEqual([entry["item"] for entry in verdict["rejections"]], ["objective:3"])
        self.assertEqual([note["item"] for note in verdict["sourcing_notes"]], ["objective:2"])
        self.assertFalse(verdict["gap_only_refusal"])

    def test_another_criterion_is_never_reclassified(self) -> None:
        report = _report(
            rejections=[
                {
                    "item": "objective:2",
                    "criterion": "factual_correctness",
                    "reason": "The supplied excerpt contradicts this claim.",
                }
            ],
            factual_correctness="fail",
        )
        verdict = self.verdict(report, self.plan())
        self.assertEqual(len(verdict["rejections"]), 1)
        self.assertEqual(verdict["sourcing_notes"], [])
        self.assertFalse(verdict["gap_only_refusal"])

    def test_the_rule_does_not_bite_without_a_plan(self) -> None:
        # Every other artifact kind (lesson, unit sections) calls without `declared_gaps`.
        report = _report(
            rejections=[{"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION}],
            source_support="fail",
        )
        verdict = gen.validation_verdict(report, research_status="ok")
        self.assertEqual(len(verdict["rejections"]), 1)
        self.assertEqual(verdict["sourcing_notes"], [])

    def test_a_declared_pass_with_only_gap_rejections_passes_and_discloses_the_gap(self) -> None:
        # The shape `validation-prompt.v12` asks for: the validator marks the claim unverified and
        # names it, but does not refuse the plan for it.
        report = _report(
            rejections=[{"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION}],
            verdict="pass",
        )
        verdict = self.verdict(report, self.plan())
        self.assertEqual(verdict["verdict"], "pass")
        self.assertEqual(verdict["outcome"], gen.OUTCOME_MODEL_ASSESSED)
        self.assertEqual([note["item"] for note in verdict["sourcing_notes"]], ["objective:2"])

    def test_a_failing_other_criterion_keeps_the_refusal_out_of_gap_only(self) -> None:
        report = _report(
            rejections=[{"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION}],
            source_support="fail",
            answer_uniqueness="fail",
        )
        verdict = self.verdict(report, self.plan())
        self.assertFalse(verdict["gap_only_refusal"])
        # The real failure is still named first; the gap is appended, never substituted for it.
        reasons = gen._refusal_reasons(verdict)
        self.assertEqual(reasons[0], "criteria failed: answer_uniqueness, source_support")
        self.assertIn("declared sourcing gap", reasons[-1])

    def test_the_refusal_reason_speaks_about_the_gap_not_a_bare_criterion(self) -> None:
        report = _report(
            rejections=[
                {"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION}
            ],
            source_support="fail",
        )
        verdict = self.verdict(report, self.plan())
        reasons = gen._refusal_reasons(verdict)
        self.assertEqual(len(reasons), 1)
        self.assertIn("declared sourcing gap", reasons[0])
        self.assertIn("Set up and aim the telescope", reasons[0])
        self.assertNotIn("criteria failed", reasons[0])

    def test_the_repair_feedback_never_asks_for_an_invented_citation(self) -> None:
        report = _report(
            rejections=[
                {"item": "objective:2", "criterion": "source_support", "reason": LIVE_REJECTION},
                {
                    "item": "objective:3",
                    "criterion": "source_support",
                    "reason": "The cited excerpt does not carry this claim.",
                },
            ],
            source_support="fail",
        )
        plan = {
            "objectives": [
                _unverified_objective(2, "Set up and aim the telescope"),
                {
                    "objective_id": "obj-3",
                    "ordinal": 3,
                    "title": "Observe the moons on two nights",
                    "support": "sourced",
                    "source_ids": ["src_alpha"],
                },
            ]
        }
        feedback = gen._feedback(self.verdict(report, plan))
        self.assertIn("do not invent a citation", feedback)


def _answer_for(request: gen.LLMRequest, *, gap_labels: tuple[str, ...]) -> dict:
    """A schema-legal validator answer for one narrowed plan pass.

    The pass that owns ``source_support`` returns the measured refusal for every declared-gap
    label it was asked about; every other pass passes. Claim verdicts keep the gap honest:
    ``unverified`` with a reason.
    """
    properties = (request.schema or {}).get("properties") or {}
    criteria_enum = (
        (((properties.get("criteria") or {}).get("items") or {}).get("properties") or {})
        .get("id", {})
        .get("enum")
        or []
    )
    claim_enum = (
        (((properties.get("claim_verdicts") or {}).get("items") or {}).get("properties") or {})
        .get("item", {})
        .get("enum")
        or []
    )
    claim_verdicts = [
        {"item": label, "support": "unverified", "reason": "no supplied excerpt carries this claim"}
        for label in claim_enum
    ]
    if not criteria_enum:
        return {"claim_verdicts": claim_verdicts}
    own_gaps = [label for label in claim_enum if label in gap_labels]
    rejecting = "source_support" in criteria_enum and bool(own_gaps)
    document: dict = {
        "verdict": "reject" if rejecting else "pass",
        "criteria": [
            {
                "id": criterion,
                "verdict": "fail" if (rejecting and criterion == "source_support") else "pass",
                "reason": (
                    LIVE_REJECTION
                    if (rejecting and criterion == "source_support")
                    else "nothing in the artifact contradicts this criterion"
                ),
            }
            for criterion in criteria_enum
        ],
        "rejections": (
            [
                {"item": label, "criterion": "source_support", "reason": LIVE_REJECTION}
                for label in own_gaps
            ]
            if rejecting
            else []
        ),
    }
    if claim_enum:
        # A pass with no claim labels has no ``claim_verdicts`` property at all
        # (``validation_pass_schema``), so the key must be absent, not empty.
        document["claim_verdicts"] = claim_verdicts
    return document


class GapRefusingSeam:
    """Scripted route: the fixture plan, and a validator that refuses only declared gaps."""

    def __init__(self, gap_labels: tuple[str, ...]) -> None:
        self.gap_labels = gap_labels
        self.calls: list[gen.LLMRequest] = []

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        self.calls.append(request)
        if request.purpose == "coursebook.plan.generate":
            # The plan the live run authored: every objective declared unverified, no ids.
            return response(plan_fixture("plan_ja", ()))
        return response(_answer_for(request, gap_labels=self.gap_labels))


class PlanStageParksOnADeclaredGapTest(unittest.TestCase):
    """The pipeline half: a gap-only refusal is not repaired by regenerating."""

    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def run_plan(self, seam) -> dict:
        return gen.run_plan_job(self.connection, plan_job(), seam, FakeSearch(), now=NOW)

    def seam(self, *, gap_labels: tuple[str, ...]):
        return GapRefusingSeam(gap_labels)

    def test_a_gap_only_refusal_parks_needs_review_without_a_second_authoring_call(self) -> None:
        seam = self.seam(gap_labels=("objective:1",))
        result = self.run_plan(seam)

        generate_calls = [
            request for request in seam.calls if request.purpose == "coursebook.plan.generate"
        ]
        self.assertEqual(len(generate_calls), 1, "the plan is not re-authored for a declared gap")
        self.assertEqual(result["validation"]["outcome"], gen.OUTCOME_REJECTED)
        self.assertEqual(result["validation_verdict"], "reject")

        notes = result["sourcing_notes"]
        self.assertEqual([note["item"] for note in notes], ["objective:1"])
        self.assertEqual(notes[0]["validator_reason"], LIVE_REJECTION)
        self.assertEqual(
            result["rejection_reasons"],
            [
                f"objective:1: declared sourcing gap — {notes[0]['claim']!r} is marked unverified "
                "and no supplied excerpt carries it; that is recorded, not a validation defect. "
                "Next: re-research the claim, narrow the objective, or approve the lesson with it "
                "labelled unverified."
            ],
        )
        self.assertTrue(
            any("declared sourcing gap" in warning for warning in result["warnings"])
        )
        self.assertTrue(
            any("was not re-authored" in warning for warning in result["warnings"])
        )

    def test_a_real_over_citation_still_earns_the_second_attempt(self) -> None:
        # The control: a sourced objective the excerpt does not carry is the defect D1-F1
        # removed, and it is still repaired by re-authoring.
        calls: list[gen.LLMRequest] = []

        def answer(request: gen.LLMRequest) -> gen.LLMResponse:
            calls.append(request)
            if request.purpose == "coursebook.plan.generate":
                return response(plan_fixture("plan_ja", ()))
            document = _answer_for(request, gap_labels=("objective:1",))
            # No declared gap is named, so the pass cannot launder the refusal.
            for entry in document.get("rejections") or []:
                entry["item"] = "plan.goal"
            return response(document)

        result = gen.run_plan_job(self.connection, plan_job(), answer, FakeSearch(), now=NOW)

        generate_calls = [
            request for request in calls if request.purpose == "coursebook.plan.generate"
        ]
        self.assertEqual(len(generate_calls), 2, "a real defect still costs the repair attempt")
        self.assertEqual(result["sourcing_notes"], [])


class PromptStatesTheRuleTest(unittest.TestCase):
    def test_the_label_advances(self) -> None:
        self.assertEqual(gen.VALIDATION_PROMPT_VERSION, "validation-prompt.v12")

    def test_the_plan_pass_states_the_distinction(self) -> None:
        text = gen.validation_pass_instructions(
            subject="plan", criteria=gen.VALIDATION_CRITERIA[:5], claim_labels=("objective:2",)
        )
        self.assertIn("never against the gaps it declares", text)
        self.assertIn("do not reject source_support", text)
        self.assertIn("is not carried by the excerpt it cites", text)

    def test_the_lesson_pass_is_unchanged(self) -> None:
        text = gen.validation_pass_instructions(
            subject="lesson and its learner page", criteria=gen.VALIDATION_CRITERIA
        )
        self.assertNotIn("never against the gaps it declares", text)

    def test_every_plan_pass_carries_the_rule(self) -> None:
        plan = plan_fixture("plan_ja", ())
        requests = gen.build_plan_validation_requests(
            plan=plan,
            goal="Order coffee in Japanese",
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_run=gen.ResearchRun(
                status="ok", sources=[], queries=[], failures=[], reason=None
            ),
        )
        self.assertTrue(requests)
        for request in requests:
            self.assertIn("never against the gaps it declares", request.instructions)
            self.assertEqual(request.prompt_version, "validation-prompt.v12")


if __name__ == "__main__":
    unittest.main()
