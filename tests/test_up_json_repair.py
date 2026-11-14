"""UP-45 — a malformed plan answer is repaired locally; a cut one is still a truncation.

The defect: ``_parse_structured`` fell back to ``json.loads`` and then raised
``GenerationRejected``. A trailing comma, a stray markdown fence or single quotes therefore ended
a plan/unit/lesson job **after** the earlier sections of that unit had already been authored and
paid for, even though the provider had written a whole document.

The change adds one local repair (``json_repair``) and, more importantly, one refusal. The library
advertises repairing *truncated* values and does exactly that — ``{"a": [1, 2,`` comes back as
``{"a": [1, 2]}`` and ``{"a":`` as ``{"a": ""}`` — so a repair run before the truncation lane
(:func:`coursebook.generation._stage_answer_with_repair`) would convert a cut answer into a
legal-looking document the provider never wrote and defeat the one re-ask that exists for it. The
ordering is the safety argument, and it is asserted here rather than described:

1. the byte bound is checked first (unchanged);
2. a document that is not *structurally complete* — unclosed string, unclosed object, dangling
   ``:`` — is refused, so the cut answer reaches the truncation lane as ``truncated``;
3. only then is a complete document whose syntax is broken repaired, and the repaired value is
   judged by the same schema and rule gates the provider's own answer is judged by;
4. the repair is recorded (``json_repaired``) on the review row, never presented as a re-ask.

Every test runs offline against a scripted seam. No provider is called and no answer is invented.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db
from coursebook import generation as gen

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    excerpt_quote_from,
    plan_fixture,
    plan_job,
    source_ids_from,
    validation_from_fixture,
)
from tests.test_generation import canonical_json

#: An answer that stops in the middle of a string value — the shape a cut answer arrives in. A
#: JSON-repair library closes the string and the object; the pipeline must not.
CUT_MID_STRING = '{"plan_schema": "coursebook.plan.v1", "goal_summary": "Order coffee polite'

#: An answer that stops after a key and its colon: nothing was written for the value.
CUT_AFTER_COLON = '{"plan_schema": "coursebook.plan.v1", "goal_summary":'


def answer(text: str, *, output_tokens: int = 900, cost: float = 0.02) -> gen.LLMResponse:
    """A provider answer whose text did not parse, with no ``parsed`` shortcut."""
    return gen.LLMResponse(
        text=text,
        parsed=None,
        provider="fake",
        model="fake-model",
        input_tokens=120,
        output_tokens=output_tokens,
        cost_usd=cost,
    )


def plan_request(*, max_tokens: int = 8000) -> gen.LLMRequest:
    """A plan-shaped request: the schema is the real one and the cap is what a cut test sets."""
    return gen.LLMRequest(
        purpose="coursebook.plan.generate",
        prompt_version="plan-prompt.v1",
        system_prompt="Write the plan.",
        instructions="Return one JSON object.",
        input_text="{}",
        schema=gen.PLAN_SCHEMA,
        schema_name="coursebook.plan.v1",
        max_tokens=max_tokens,
        timeout_s=600.0,
    )


def usage(calls: int = 8) -> gen._Usage:
    return gen._Usage(budget=gen.CostBudget(max_calls=calls, max_cost_usd=None, source="caller"))


def trailing_comma_json(document: dict) -> str:
    """The document's own JSON with one trailing comma before the closing brace."""
    text = canonical_json(document)
    assert text.endswith("}")
    return text[:-1] + ",}"


class JsonRepairTest(KernelCase):
    def test_a_trailing_comma_is_repaired_and_a_cut_answer_still_refused(self) -> None:
        # ── 1. A complete document with a trailing comma is read, without another provider call.
        document = plan_fixture("plan_ja")
        malformed = trailing_comma_json(document)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(malformed)  # the fixture is really malformed, not merely unusual
        request = plan_request()
        llm = FakeLLM({})  # a repair is local: any provider call here is a defect
        parsed, repaired_response = gen._stage_answer_with_repair(
            llm,
            request,
            answer(malformed),
            usage(),
            schema=gen.PLAN_SCHEMA,
            what="plan",
            max_bytes=gen.MAX_PLAN_BYTES,
        )
        self.assertEqual(parsed, document)
        self.assertTrue(repaired_response.json_repaired)
        self.assertEqual(
            repaired_response.shape_repair_attempts,
            0,
            "a local repair is not a re-ask and must not be counted as one",
        )
        self.assertEqual(llm.requests, [], "the repaired answer must not cost a second call")

        # ── 2. A document cut mid-string is refused before the library can close it.
        self.assertEqual(gen._repair_complete_answer(CUT_MID_STRING), (False, None))
        self.assertEqual(gen._repair_complete_answer(CUT_AFTER_COLON), (False, None))
        # The refusal is load-bearing: the library *would* have invented a document here.
        json_repair = gen._json_repair_module()
        self.assertIsNotNone(json_repair, "json_repair is a declared dependency and must be present")
        self.assertEqual(
            json_repair.loads(CUT_MID_STRING)["goal_summary"],
            "Order coffee polite",
            "the library closes a cut string, which is exactly why the completeness gate runs first",
        )

        # ── 3. A cut answer consumed its cap, so it is still a TRUNCATION, not a repaired document.
        cut_request = plan_request(max_tokens=200)
        cut_once = FakeLLM(
            {"coursebook.plan.generate": [answer(CUT_MID_STRING, output_tokens=200)]}
        )
        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            gen._stage_answer_with_repair(
                cut_once,
                cut_request,
                answer(CUT_MID_STRING, output_tokens=200),
                usage(),
                schema=gen.PLAN_SCHEMA,
                what="plan",
                max_bytes=gen.MAX_PLAN_BYTES,
            )
        self.assertEqual(caught.exception.parse_outcome, "truncated")
        self.assertTrue(caught.exception.repair_attempted)
        self.assertEqual(
            cut_once.calls_for("coursebook.plan.generate"),
            1,
            "a cut answer earns exactly one re-ask; it is never repaired into a document",
        )
        self.assertTrue(
            cut_once.requests[0].prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX),
            "the re-ask must carry the marked .cut label",
        )

    def test_the_plan_job_records_a_repaired_answer_on_its_row(self) -> None:
        course_id, _plan_id = self.new_course()

        def generate(request: gen.LLMRequest) -> gen.LLMResponse:
            document = plan_fixture(
                "plan_ja",
                source_ids_from(request),
                source_quote=excerpt_quote_from(request),
            )
            return answer(trailing_comma_json(document), output_tokens=900)

        job = plan_job(job_id="job-up45-plan")
        job["brief"]["course_id"] = course_id
        script = {
            "coursebook.plan.generate": generate,
            "coursebook.plan.validate": validation_from_fixture("validation_pass"),
        }
        connection = db.connect()
        try:
            result = gen.run_plan_job(connection, job, FakeLLM(script), FakeSearch(), now=NOW)
            self.assertEqual(result["validation_verdict"], "pass")
            row = connection.execute(
                "SELECT id, json_repaired, rejections_json FROM gen_validation_records "
                "WHERE subject_kind = 'plan' AND pass_index = -1"
            ).fetchone()
            self.assertIsNotNone(row, "the review row must exist for a plan that passed")
            assert row is not None
            self.assertEqual(int(row[1]), 1)
            self.assertTrue(json.loads(row[2])["json_repaired"]["generator"])
            record = gen.validation_record(connection, str(row[0]))
        finally:
            connection.close()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(record["json_repaired"])
        self.assertFalse(record["json_repaired_sides"]["validator"])


if __name__ == "__main__":
    unittest.main()
