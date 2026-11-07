"""H-63 D-H63-2 — plan prose fields are cut at the JSON-schema ``maxLength``.

Measured live: a 600-char ``learner_outcome`` ending ``…do not establish,so``, a 400-char
``evidence_note`` ending ``…excluded as a`` and a 40-char ``parent.reading_level`` ending
``…chart-l批``. The provider enforces a maximum length by cutting the value, so a field that
reaches its cap has lost its ending; the independent validator then rejects the plan.

The fix has two halves, both pinned here: the plan prompts ask for a bounded length below the cap,
and a stored candidate that still lands on a cap is refused deterministically and regenerated with
the field and the safe bound named in the revision instructions.
"""

from __future__ import annotations

import json
import unittest

from coursebook import generation as gen
from coursebook import research
from tests.blueprint_support import blueprint_plan
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    NOW,
    plan_fixture,
    plan_from_fixture,
    plan_job,
    response,
    source_ids_from,
    validation_from_fixture,
)


def research_run():
    return research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test")


class PlanPromptLengthTest(unittest.TestCase):
    def test_both_plan_prompts_state_the_bounded_prose_lengths(self) -> None:
        for scope in ("single", None):
            request = gen.build_plan_request(
                goal="Sharpen a kitchen knife safely with a whetstone",
                recipe="one_off",
                dials={},
                locale="en-US",
                research_run=research_run(),
                scope=scope,
                level="adult",
                subject_domain="repair",
            )
            instructions = request.instructions
            self.assertIn("at most 450 characters", instructions)
            self.assertIn("parent.reading_level in at most 30", instructions)
            self.assertIn("has lost its ending", instructions)


class PlanProseCapRuleTest(unittest.TestCase):
    def test_a_v2_learner_outcome_on_its_cap_is_refused_as_truncated(self) -> None:
        plan = blueprint_plan(scope="single")
        plan["learner_outcome"] = "A" * 600
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan, recipe="casual", dials={}, locale=None, ledger=[], scope="single"
            )
        reasons = "\n".join(caught.exception.reasons)
        self.assertIn("learner_outcome is 600 characters", reasons)
        self.assertIn("at most 450", reasons)

    def test_a_v2_document_under_the_cap_is_not_refused_for_length(self) -> None:
        plan = blueprint_plan(scope="single")
        plan["learner_outcome"] = "A" * 599
        # The fixture is otherwise valid: the length rule is the only thing that could speak here.
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale=None, ledger=[], scope="single"
        )

    def test_a_parent_reading_level_on_its_40_char_cap_is_truncated(self) -> None:
        reasons = gen._prose_cap_reasons(
            {"reading_level": "chart-l批" + "x" * 32}, gen.PARENT_SCHEMA
        )
        self.assertTrue(reasons)
        self.assertIn("reading_level", reasons[0])
        self.assertIn("at most 30", reasons[0])

    def test_only_string_slots_at_or_above_the_prose_floor_are_judged(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "maxLength": 20},
                "note": {"type": "string", "maxLength": 40},
                "kind": {"type": "string", "enum": ["a", "b"], "maxLength": 40},
            },
        }
        reasons = gen._prose_cap_reasons(
            {"code": "x" * 20, "note": "y" * 40, "kind": "a"}, schema
        )
        self.assertEqual(len(reasons), 1)
        self.assertIn("note is 40 characters", reasons[0])


class PlanProseCapRetryTest(GenerationTestBase):
    def test_a_truncated_plan_is_regenerated_with_the_bound_in_the_revision(self) -> None:
        def truncated(request: gen.LLMRequest) -> gen.LLMResponse:
            document = plan_fixture("plan_ja", source_ids_from(request))
            document["learner_outcome"] = "x" * 600
            return response(document)

        llm = FakeLLM(
            {
                "coursebook.plan.generate": [truncated, plan_from_fixture()],
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)

        self.assertEqual(llm.calls_for("coursebook.plan.generate"), 2)
        second = [record for record in llm.requests if record.purpose == "coursebook.plan.generate"][1]
        revision = json.loads(second.input_text).get("revision_instructions") or ""
        self.assertIn("learner_outcome", revision)
        self.assertIn("at most 450", revision)
        # The regeneration is the artifact that is validated and stored — never the clipped one.
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["validation_verdict"], "pass")
        stored = self.rows("SELECT document_json FROM gen_plan_documents")[0]["document_json"]
        document = json.loads(stored)
        plan = document.get("plan") if isinstance(document.get("plan"), dict) else document
        self.assertEqual(len(plan["learner_outcome"]), len(plan_fixture("plan_ja")["learner_outcome"]))

    def test_a_plan_still_at_cap_on_the_second_attempt_is_never_drafted(self) -> None:
        def truncated(request: gen.LLMRequest) -> gen.LLMResponse:
            document = plan_fixture("plan_ja", source_ids_from(request))
            document["learner_outcome"] = "x" * 600
            return response(document)

        llm = FakeLLM(
            {
                "coursebook.plan.generate": truncated,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["validation_verdict"], "reject")
        self.assertIn("at its 600-character cap", "\n".join(result["rejection_reasons"]))
        # The independent validator was never asked to pass a document the rules already refused.
        self.assertEqual(llm.calls_for("coursebook.plan.validate"), 0)


if __name__ == "__main__":
    unittest.main()
