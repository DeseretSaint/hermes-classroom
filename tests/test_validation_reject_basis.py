"""``t_0affea08`` — a declared ``reject`` must name something the pass judged.

H-192b split plan validation into passes of five criteria. A recorded ten-criterion answer that
rejects ``evidence_target_fit`` (a pass-2 criterion) was narrowed for pass 1 to

    declared = "reject"; failed = []; unknown = []; rejections = []

and ``validation_verdict`` honoured the declared verdict: ``reject`` with no failed criterion and
no reason. H-182/D1 then treated that as a repairable refusal and re-authored the whole plan on
``_feedback``'s generic "without itemised reasons" hint — a full authoring call and a second
research-to-plan cycle bought by an answer that never named a rule. Whether it happened at all was
decided by thread order, so ``tests.test_validation_shape_repair`` failed 2 runs in 3 on identical
code.

The decision these tests pin (``docs/DECISION-VALIDATION-REJECT-BASIS.md``):

* a declared ``reject`` still blocks a pass — the declared verdict is never converted into ``pass``;
* a declared ``reject`` is a verdict only when this pass's own answer grounds it: one of its
  criteria is ``fail`` or ``unknown``, or it names a rejection;
* an ungrounded ``reject`` is not a verdict and is typed as ``ModelOutputInvalid`` →
  ``VALIDATION_FAILED`` (non-retryable) — no second authoring call, no validation record, and no
  refusal record presented to a reviewer;
* the rule is stated in the pass instructions before the answer (``validation-prompt.v5``), so it
  is a stated contract, not an unstated schema trap (the H-191 lesson).

Everything here runs against the real pipeline and the real command surface with deterministic
seams: no provider is called and no model behaviour is invented.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db
from coursebook import generation as gen
from coursebook import job_service

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    fixture,
    plan_from_fixture,
    plan_job,
)
from tests.test_validation_shape_repair import _narrow_to_pass


def pass_request(criteria: tuple[str, ...] = gen.VALIDATION_CRITERIA[:5]) -> gen.LLMRequest:
    """One criteria pass, built the way ``build_plan_validation_requests`` builds it."""
    return gen.LLMRequest(
        purpose="coursebook.plan.validate",
        prompt_version=gen.VALIDATION_PROMPT_VERSION,
        system_prompt=gen.VALIDATION_SYSTEM_PROMPT,
        instructions=gen.validation_pass_instructions(subject="plan", criteria=criteria),
        input_text="{}",
        schema=gen.validation_pass_schema(criteria),
        schema_name="coursebook_validation_v1",
        max_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        timeout_s=180.0,
    )


def claim_pass_request(labels: tuple[str, ...]) -> gen.LLMRequest:
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
        max_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        timeout_s=180.0,
    )


def answer(
    verdict: str,
    criteria: tuple[str, ...],
    *,
    nonpass: dict[str, str] | None = None,
    rejections: list[dict] | None = None,
) -> dict:
    """A schema-valid pass answer; ``nonpass`` maps a criterion id to ``fail``/``unknown``."""
    nonpass = nonpass or {}
    return {
        "verdict": verdict,
        "criteria": [
            {
                "id": criterion,
                "verdict": nonpass.get(criterion, "pass"),
                "reason": "judged by this fixture",
            }
            for criterion in criteria
        ],
        "rejections": list(rejections or []),
    }


def response_for(document: dict) -> gen.LLMResponse:
    return gen.LLMResponse(
        text=json.dumps(document),
        parsed=json.loads(json.dumps(document)),
        provider="nous",
        model="second-opinion-model",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.01,
    )


def merged_verdict(
    *, nonpass: dict[str, str] | None = None, rejections: list[dict] | None = None
) -> dict:
    """Run both real passes' answers through the real merge and ``validation_verdict``.

    ``validation_verdict`` reads one full ten-criterion report, which only
    :func:`gen.merge_validation_reports` produces. Each pass declares ``reject`` only when its own
    batch grounds it — the rule these tests exist to pin.
    """
    nonpass = nonpass or {}
    rejections = rejections or []
    passes = []
    for owned in gen.VALIDATION_CRITERIA_PASSES:
        batch_nonpass = {key: value for key, value in nonpass.items() if key in owned}
        batch_rejections = [
            entry for entry in rejections if entry.get("criterion") in owned
        ]
        grounded = bool(batch_nonpass or batch_rejections)
        passes.append(
            (
                owned,
                answer(
                    "reject" if grounded else "pass",
                    owned,
                    nonpass=batch_nonpass,
                    rejections=batch_rejections,
                ),
            )
        )
    return gen.validation_verdict(
        gen.merge_validation_reports(passes), research_status="ok"
    )


class DeclaredRejectBasisTest(unittest.TestCase):
    """One pass's own answer decides whether its declared ``reject`` is a verdict."""

    def test_a_reject_that_fails_nothing_is_not_a_verdict(self) -> None:
        request = pass_request()
        document = answer("reject", gen.VALIDATION_CRITERIA[:5])

        with self.assertRaises(gen.ModelOutputInvalid) as raised:
            gen._parse_validation_answer(
                response_for(document), request, what="plan validation"
            )

        error = raised.exception
        self.assertEqual(error.code, "VALIDATION_FAILED")
        self.assertEqual(job_service._error_code(error), "VALIDATION_FAILED")
        self.assertEqual(error.purpose, "coursebook.plan.validate")
        self.assertFalse(job_service._stage_error(error)["retryable"])
        self.assertIn("declared reject", error.violation or "")
        # The rule is stated in the pass instructions, so the typed failure costs no second call.
        self.assertFalse(error.repair_attempted)
        self.assertIn("VALIDATION_FAILED", request.instructions)

    def test_a_reject_grounded_in_a_failed_criterion_is_still_a_refusal(self) -> None:
        request = pass_request()
        document = answer(
            "reject", gen.VALIDATION_CRITERIA[:5], nonpass={"answer_uniqueness": "fail"}
        )

        parsed = gen._parse_validation_answer(
            response_for(document), request, what="plan validation"
        )
        verdict = merged_verdict(nonpass={"answer_uniqueness": "fail"})

        self.assertEqual(parsed["verdict"], "reject")
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(verdict["failed"], ["answer_uniqueness"])
        self.assertEqual(gen._refusal_reasons(verdict), ["criteria failed: answer_uniqueness"])

    def test_a_reject_grounded_in_an_unknown_criterion_reads_as_a_reason(self) -> None:
        """The old fallback rendered this as ``"criteria failed: "`` with nothing after it."""
        request = pass_request()
        document = answer(
            "reject", gen.VALIDATION_CRITERIA[:5], nonpass={"source_support": "unknown"}
        )

        parsed = gen._parse_validation_answer(
            response_for(document), request, what="plan validation"
        )
        verdict = merged_verdict(nonpass={"source_support": "unknown"})
        reasons = gen._refusal_reasons(verdict)

        self.assertEqual(parsed["verdict"], "reject")
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(verdict["failed"], [])
        self.assertEqual(verdict["unknown"], ["source_support"])
        self.assertTrue(reasons)
        self.assertEqual(reasons, ["criteria could not be verified: source_support"])
        self.assertNotIn("criteria failed: ", reasons)

    def test_a_reject_grounded_in_a_rejection_carries_the_item_and_the_fix(self) -> None:
        request = pass_request()
        document = answer(
            "reject",
            gen.VALIDATION_CRITERIA[:5],
            rejections=[
                {
                    "item": "check:1",
                    "criterion": "answer_uniqueness",
                    "reason": "two choices both satisfy the stimulus",
                    "fix_hint": "name the moment so only one opener fits",
                }
            ],
        )

        parsed = gen._parse_validation_answer(
            response_for(document), request, what="plan validation"
        )
        verdict = merged_verdict(
            rejections=[
                {
                    "item": "check:1",
                    "criterion": "answer_uniqueness",
                    "reason": "two choices both satisfy the stimulus",
                    "fix_hint": "name the moment so only one opener fits",
                }
            ]
        )

        self.assertEqual(parsed["verdict"], "reject")
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(
            gen._refusal_reasons(verdict),
            ["check:1: two choices both satisfy the stimulus"],
        )
        feedback = gen._feedback(verdict)
        self.assertIn("check:1", feedback)
        self.assertIn("fix: name the moment so only one opener fits", feedback)
        self.assertNotIn("without itemised reasons", feedback)

    def test_a_claim_only_pass_carries_no_verdict_to_ground(self) -> None:
        request = claim_pass_request(("objective:1",))
        document = {
            "claim_verdicts": [
                {"item": "objective:1", "support": "unverified", "reason": "not assessed"}
            ]
        }

        parsed = gen._parse_validation_answer(
            response_for(document), request, what="plan validation"
        )

        self.assertEqual(parsed, document)

    def test_the_pass_instructions_state_the_rule_before_the_answer(self) -> None:
        text = gen.validation_pass_instructions(
            subject="plan", criteria=gen.VALIDATION_CRITERIA[:5]
        )

        self.assertIn("Set the top-level 'verdict' to 'pass'", text)
        self.assertIn("at least one rejection", text)
        self.assertIn("VALIDATION_FAILED", text)
        # Nothing is demanded of a claim-only pass: it returns no verdict at all.
        claim_text = gen.validation_pass_instructions(
            subject="plan", criteria=(), claim_labels=("objective:1",)
        )
        self.assertNotIn("Set the top-level 'verdict'", claim_text)

    def test_the_wide_lesson_and_unit_instruction_states_the_same_rule(self) -> None:
        """``_declared_reject_problem`` enforces the rule on every criteria pass, so both prompt
        builders must state it: the plan passes use ``validation_pass_instructions``, the lesson
        and unit-sections passes use ``_validation_instructions``."""
        for subject in ("lesson and its learner page", "unit sections"):
            text = gen._validation_instructions(
                subject=subject, criteria=gen.VALIDATION_CRITERIA
            )
            self.assertIn("Set the top-level 'verdict' to 'pass'", text)
            self.assertIn("at least one rejection", text)
            self.assertIn("VALIDATION_FAILED", text)


class UngroundedRefusalDoesNotReauthorTest(KernelCase):
    """The plan job: an ungrounded ``reject`` spends nothing more and records no refusal."""

    def counts(self, table: str) -> int:
        connection = db.connect()
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            connection.close()

    def test_an_ungrounded_reject_fails_the_job_without_a_second_authoring_call(self) -> None:
        course_id, _placeholder = self.new_course()
        author_calls: list[gen.LLMRequest] = []

        def validator(request: gen.LLMRequest) -> gen.LLMResponse:
            return response_for(answer("reject", gen.validation_pass_criteria(request)))

        def author(request: gen.LLMRequest) -> gen.LLMResponse:
            author_calls.append(request)
            return plan_from_fixture("plan_ja")(request)

        job = plan_job(job_id="job-reject-basis")
        job["brief"]["course_id"] = course_id
        connection = db.connect()
        try:
            with self.assertRaises(gen.ModelOutputInvalid) as raised:
                gen.run_plan_job(
                    connection,
                    job,
                    FakeLLM(
                        {
                            "coursebook.plan.generate": author,
                            "coursebook.plan.validate": validator,
                        }
                    ),
                    FakeSearch(),
                    now=NOW,
                )
        finally:
            connection.close()

        error = raised.exception
        self.assertEqual(error.code, "VALIDATION_FAILED")
        self.assertIn("declared reject", error.violation or "")
        # H-182/D1's repair loop is not entered: there is no rule to repair.
        self.assertEqual(len(author_calls), 1)
        # Nothing is persisted that a reviewer could read as a refusal: no plan document exists.
        # CP-015g/D1: the failed *validation attempt* is recorded — with ``parse_outcome``
        # ``verdict_violation`` and no verdict stored — so the operator can audit what the
        # validator said. It is not a rejection of the plan.
        self.assertEqual(self.counts("gen_plan_documents"), 0)
        records = self.rows("SELECT * FROM gen_validation_records")
        self.assertEqual(len(records), 2, "one row per validation pass that carried no verdict")
        for record in records:
            self.assertEqual(record["verdict"], "invalid")
            self.assertEqual(record["parse_outcome"], "verdict_violation")
            self.assertEqual(record["repair_attempted"], 0)

    def test_a_grounded_refusal_still_re_authors_once(self) -> None:
        """H-182/D1 is untouched: a refusal with reasons is still a repairable plan."""
        from tests.test_generation import validation_from_fixture

        course_id, _placeholder = self.new_course()
        calls: list[str] = []

        def author(request: gen.LLMRequest) -> gen.LLMResponse:
            calls.append(request.purpose)
            return plan_from_fixture("plan_ja")(request)

        def validator(request: gen.LLMRequest) -> gen.LLMResponse:
            return validation_from_fixture("validation_reject_hazard")(request)

        job = plan_job(job_id="job-grounded-reject")
        job["brief"]["course_id"] = course_id
        connection = db.connect()
        try:
            result = gen.run_plan_job(
                connection,
                job,
                FakeLLM(
                    {
                        "coursebook.plan.generate": author,
                        "coursebook.plan.validate": validator,
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
        finally:
            connection.close()

        self.assertEqual(result["validation_verdict"], "reject")
        self.assertEqual(calls, ["coursebook.plan.generate", "coursebook.plan.generate"])


class NarrowedRecordedAnswerTest(unittest.TestCase):
    """The H-208 interaction, from the answer-shape side: deterministic, by contract.

    The recorded answer rejects ``evidence_target_fit`` (pass 2). Narrowed for pass 1 it declares
    ``reject`` with nothing behind it. Before ``t_0affea08`` that was a refusal H-182 re-authored,
    so the outcome depended on which pass thread reached the seam first. It is now a typed
    contract failure of the non-owning pass on every run, and the answer still reaches the owning
    pass unchanged (where the measured 81-character ``item`` is the violation under test).
    """

    def test_the_non_owning_pass_is_a_typed_failure_every_time(self) -> None:
        recorded = fixture("validation_measured_item_81")
        owning = tuple(gen.VALIDATION_CRITERIA[5:])
        non_owning = gen.VALIDATION_CRITERIA[:5]

        self.assertEqual((recorded.get("rejections") or [{}])[0].get("criterion"), "evidence_target_fit")

        for _ in range(10):
            request = pass_request(non_owning)
            document = _narrow_to_pass(json.loads(json.dumps(recorded)), request)
            self.assertEqual(document["verdict"], "reject")
            self.assertTrue(all(entry["verdict"] == "pass" for entry in document["criteria"]))
            self.assertEqual(document["rejections"], [])
            with self.assertRaises(gen.ModelOutputInvalid) as raised:
                gen._parse_validation_answer(
                    response_for(document), request, what="plan validation"
                )
            self.assertIn("declared reject", raised.exception.violation or "")

        # The owning pass keeps the record — and the measured over-long item — intact.
        owning_document = _narrow_to_pass(json.loads(json.dumps(recorded)), pass_request(owning))
        self.assertEqual(owning_document["verdict"], "reject")
        self.assertEqual(len(owning_document["rejections"]), 1)
        with self.assertRaises(gen.ModelOutputInvalid) as raised:
            gen._parse_validation_answer(
                response_for(owning_document), pass_request(owning), what="plan validation"
            )
        # Its failure is the measured 81-character shape violation, not a verdict violation.
        self.assertIn("rejections/0/item", str(raised.exception.violation))
        self.assertIn("too long", str(raised.exception.violation))
        self.assertNotIn("declared reject", raised.exception.violation or "")


if __name__ == "__main__":
    unittest.main()
