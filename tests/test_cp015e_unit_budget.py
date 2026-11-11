"""CP-015e — the unit-sections stage budget must cover the truncation repair, and a budget stop
must never be reported as a content rejection.

Measured on the demo route (``nous`` / ``deepseek/deepseek-v4.1-flash-1017``) while authoring the
Sourdough course:

* every ``coursebook.unit_sections.validate`` answer consumed the 8 000-token completion cap
  (8 000/8 000; 8 000; 8 000), so the truncation re-ask was mandatory, not exceptional;
* the legal run was attempt 1 (generate + validate + repair) plus attempt 2 (generate + validate +
  repair) = **6** provider calls, but ``unit_sections_cost_budget`` declared 4;
* jobs ``job_98d3c0e43fcc452dad317b7757619c41`` and ``job_9d965c46213b4f9ea9872c24b08be73d``
  therefore failed ``POLICY_VIOLATION`` / ``cost_ceiling_exceeded`` at call 4 with
  ``sections_completed_count: 0`` and no checkpoint — a spend-arithmetic stop surfaced as though
  the content had been refused.

What is asserted here:

* the stage budget is sized from the same constants the pipeline spends
  (``UNIT_SECTIONS_ATTEMPTS`` x (generate + validate + ``TRUNCATION_REPAIR_CALLS``));
* a run whose validation answer is cut off on **both** attempts completes the unit — six calls, no
  ceiling stop, sections stored;
* when a caller passes a smaller ceiling the failure is a typed ``CostCeilingExceeded`` that names
  the refused purpose and the budget source, leaves no section row and no validation record, and
  carries a resume checkpoint for the same unit;
* the job error for that failure is distinguishable from a validator rejection: a distinct
  ``code``, ``details.reason`` and ``details.purpose``, and a message that starts with
  ``provider-call budget exhausted``.

No test presents invented provider output as a real call: both stages are driven by the fake LLM
seam, and the cut answers are the recorded token counts from the runs above.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen, job_service

from tests.blueprint_support import blueprint_plan, response, unit_sections_document, validation_pass
from tests.test_blueprint_units import T0, UnitStageCase
from tests.test_generation import FakeLLM


def _cut_validation_answer() -> gen.LLMResponse:
    """The measured shape: the cap is fully consumed and the JSON stops mid-object."""
    return gen.LLMResponse(
        text='{"verdict": "pass", "criteria": [{"id": "objective_alignment", "verdict": "pa',
        parsed=None,
        provider="nous",
        model="deepseek/deepseek-v4.1-flash-1017",
        input_tokens=7350,
        output_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        cost_usd=None,
    )


def _rejected_validation_answer() -> dict:
    """A grounded reject: one failing criterion plus a named rejection (a verdict, not a shape)."""
    document = validation_pass()
    document["verdict"] = "reject"
    for entry in document["criteria"]:
        if entry["id"] == "objective_alignment":
            entry["verdict"] = "fail"
            entry["reason"] = "the lesson intent does not carry the objective's construct"
    document["rejections"] = [
        {
            "item": "unit_sections",
            "criterion": "objective_alignment",
            "reason": "the lesson intent does not carry the objective's construct",
        }
    ]
    return document


class UnitBudgetArithmeticTest(unittest.TestCase):
    def test_the_stage_budget_is_sized_from_the_calls_the_stage_spends(self) -> None:
        budget = gen.unit_sections_cost_budget()
        expected = len(gen.UNIT_SECTIONS_ATTEMPTS) * (
            gen.CALLS_PER_LESSON_ATTEMPT + gen.TRUNCATION_REPAIR_CALLS
        )
        self.assertEqual(expected, 6)
        self.assertEqual(budget.max_calls, expected)
        self.assertEqual(budget.source, "declared")
        # The dollar floor still comes from the same call count, and the historic flat floor holds.
        self.assertEqual(
            budget.max_cost_usd,
            max(gen.DEFAULT_MAX_COST_USD, expected * gen.DECLARED_CALL_COST_USD),
        )

    def test_the_budget_covers_a_repair_on_every_attempt(self) -> None:
        """4 calls is now below the floor: attempt 2's validation would be refused."""
        self.assertGreater(gen.unit_sections_cost_budget().max_calls, 4)

    def test_an_operator_ceiling_still_wins(self) -> None:
        budget = gen.unit_sections_cost_budget(brief_budget_usd=0.5)
        self.assertEqual(budget.max_cost_usd, 0.5)
        self.assertEqual(budget.source, "operator_brief")

    def test_the_unit_validation_cap_is_the_measured_value_not_a_separate_one(self) -> None:
        """The 8 000-token cap holds the answer; the repair covers the first ask's overrun.

        Measured (CP-015e): the repaired answers that parsed used 1 964 and 2 749 completion
        tokens on the same 10-criterion + claim demand, so the cap is not too small for the answer
        — the first ask spends it on reasoning, which is what the bounded re-ask exists for. The
        purpose therefore keeps the shared cap instead of inventing a second one.
        """
        request = gen.build_unit_sections_validation_request(
            plan={"title": "A unit plan", "learner_outcome": "Do the thing."},
            unit={"ordinal": 1, "title": "Unit 1", "goal": "Make the next part possible."},
            objectives=[],
            sections=[],
            goal="Do the thing.",
            recipe="casual",
            locale=None,
            sources=[],
            research_status="unavailable",
        )
        self.assertEqual(request.purpose, "coursebook.unit_sections.validate")
        self.assertEqual(request.max_tokens, gen.VALIDATION_OUTPUT_TOKENS)
        self.assertEqual(gen.VALIDATION_OUTPUT_TOKENS, 8000)
        self.assertEqual(
            gen.VALIDATION_AUX_DEFAULTS["extra_body"]["max_tokens"], gen.VALIDATION_OUTPUT_TOKENS
        )


class UnitBudgetStageTest(UnitStageCase):
    """The stage itself, against a migrated database and the fake provider seam."""

    def _plan(self) -> tuple[str, str, dict]:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        course_id, plan_id = self.seed(plan)
        return course_id, plan_id, plan

    def _cut_twice(self, plan: dict, *, verdicts: list[dict]) -> FakeLLM:
        """Cut the first answer of both attempts; answer the ``.cut`` re-ask from *verdicts*."""
        document = unit_sections_document(unit=plan["units"][0], objectives=plan["objectives"])
        return FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": [
                    _cut_validation_answer(),
                    response(verdicts[0]),
                    _cut_validation_answer(),
                    response(verdicts[1]),
                ],
            }
        )

    def test_a_cut_answer_on_both_attempts_still_completes_the_unit(self) -> None:
        _course_id, plan_id, plan = self._plan()
        llm = self._cut_twice(plan, verdicts=[_rejected_validation_answer(), validation_pass()])

        result = gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=T0,
        )

        # Two attempts, each generate + validate + one repair. The old four-call ceiling refused
        # the fifth call and lost the unit.
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        self.assertEqual(llm.calls_for("coursebook.unit_sections.validate"), 4)
        self.assertEqual(result["usage"]["calls"], 6)
        self.assertEqual(result["sections"], 1)
        self.assertEqual(result["validation_verdict"], "pass")
        # Each attempt's second validation call is the marked re-ask, never a silent second pass.
        validate_requests = [
            request
            for request in llm.requests
            if request.purpose == "coursebook.unit_sections.validate"
        ]
        self.assertEqual(len(validate_requests), 4)
        self.assertEqual(
            [request.prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX)
             for request in validate_requests],
            [False, True, False, True],
        )
        # The approved batch is stored with its validation record attached.
        with db.read() as connection:
            record = connection.execute(
                "SELECT * FROM gen_validation_records WHERE subject_kind = 'unit_sections'"
            ).fetchone()
            sections = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
        self.assertIsNotNone(record)
        self.assertEqual(record["verdict"], "pass")
        self.assertEqual(int(sections), 1)

    def test_a_smaller_caller_ceiling_stops_the_stage_as_a_budget_stop(self) -> None:
        _course_id, plan_id, plan = self._plan()
        llm = self._cut_twice(plan, verdicts=[_rejected_validation_answer(), validation_pass()])
        budget = gen.CostBudget(max_calls=4, max_cost_usd=None, source="caller")

        with self.assertRaises(gen.CostCeilingExceeded) as caught:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                llm,
                plan_id=plan_id,
                unit_ordinal=1,
                now=T0,
                budget=budget,
            )

        exc = caught.exception
        # The refused call is named: this is the second attempt's validation, i.e. the repair slot
        # the shipped budget now pays for.
        self.assertEqual(exc.purpose, "coursebook.unit_sections.validate")
        self.assertEqual(exc.budget_source, "caller")
        self.assertEqual(exc.max_calls, 4)
        self.assertEqual(exc.calls, 4)
        self.assertIn("provider-call budget exhausted", str(exc))
        self.assertIn("was validated or rejected", str(exc))
        # Nothing was persisted: the unit is transactional, so a budget stop loses no partial batch
        # and must say so rather than implying a validator refused the sections.
        self.assertEqual(exc.sections_completed, [])
        with db.read() as connection:
            sections = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
            validations = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_validation_records"
                " WHERE subject_kind = 'unit_sections'"
            ).fetchone()["n"]
        self.assertEqual(int(sections), 0)
        self.assertEqual(int(validations), 0)

    def test_the_budget_stop_checkpoint_resumes_the_same_unit(self) -> None:
        _course_id, plan_id, plan = self._plan()
        llm = self._cut_twice(plan, verdicts=[_rejected_validation_answer(), validation_pass()])
        with self.assertRaises(gen.CostCeilingExceeded) as caught:
            gen.run_unit_sections_job(
                db.connect(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                llm,
                plan_id=plan_id,
                unit_ordinal=1,
                now=T0,
                budget=gen.CostBudget(max_calls=4, max_cost_usd=None, source="caller"),
            )
        checkpoint = caught.exception.to_checkpoint()
        self.assertEqual(checkpoint["kind"], "cost_ceiling_exceeded")
        self.assertEqual(checkpoint["sections_completed_count"], 0)
        self.assertEqual(checkpoint["refused_purpose"], "coursebook.unit_sections.validate")
        self.assertEqual(checkpoint["budget_source"], "caller")
        self.assertEqual(
            checkpoint["resume"],
            {
                "method": "jobs.create",
                "brief": {
                    "stage": "unit_sections",
                    "plan_id": plan_id,
                    "unit_ordinal": 1,
                },
            },
        )
        self.assertIn("budget_usd", checkpoint["raise_budget"]["brief_field"])


class BudgetStopIsNotARejectionTest(unittest.TestCase):
    """The job error must not let a spend ceiling read as a content verdict (CP-015e ask 3)."""

    def test_a_budget_stop_and_a_validator_rejection_have_different_job_errors(self) -> None:
        budget_stop = gen.CostCeilingExceeded(
            "provider-call budget exhausted before coursebook.unit_sections.validate: the job "
            "already made 4 provider calls",
            purpose="coursebook.unit_sections.validate",
            budget_source="declared",
        )
        budget_stop.max_calls = 4
        budget_stop.calls = 4
        budget_stop.sections_total = 1
        budget_stop.estimated_cost_usd = 0.16

        rejected = gen.GenerationRejected(
            "unit 1 sections failed validation: the lesson intent does not carry the construct"
        )

        budget_error = job_service._stage_error(budget_stop)
        reject_error = job_service._stage_error(rejected)

        # Different codes, and neither is the other's shape.
        self.assertEqual(budget_error["code"], "POLICY_VIOLATION")
        self.assertEqual(reject_error["code"], "VALIDATION_FAILED")
        self.assertNotEqual(budget_error["code"], reject_error["code"])

        # The budget stop names its arithmetic: what was spent, against which ceiling, on which call.
        self.assertEqual(budget_error["details"]["reason"], "cost_ceiling_exceeded")
        self.assertEqual(budget_error["details"]["budget_source"], "declared")
        self.assertEqual(
            budget_error["details"]["purpose"], "coursebook.unit_sections.validate"
        )
        self.assertEqual(budget_error["details"]["max_calls"], 4)
        self.assertEqual(budget_error["details"]["sections_completed_count"], 0)
        self.assertIn("actions", budget_error["details"])
        self.assertIn("budget exhausted", budget_error["message"])

        # A rejection states a content rule and carries no budget arithmetic at all.
        self.assertNotIn("reason", reject_error.get("details", {}))
        self.assertNotIn("max_calls", reject_error.get("details", {}))
        self.assertIn("does not carry the construct", reject_error["message"])

    def test_the_budget_stop_is_never_retryable(self) -> None:
        """Repeating the same request hits the same ceiling; the checkpoint is the next step."""
        exc = gen.CostCeilingExceeded(
            "provider-call budget exhausted", purpose="coursebook.unit_sections.validate"
        )
        error = job_service._stage_error(exc)
        self.assertFalse(error["retryable"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
