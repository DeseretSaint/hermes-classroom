"""CP-015 — a validator answer cut off by the completion cap is re-asked once, not failed.

Measured on the demo authoring route (``nous`` / ``deepseek-v4.1-flash``) while creating four real
courses: of nine ``coursebook.plan.validate`` calls, four consumed the whole 4 000-token cap and
three of those arrived unusable —

* ``plan validation is not valid JSON: Unterminated string starting at at line 1`` (astronomy),
* ``plan validation is not valid JSON: Expecting value at line 1`` (auto-repair),
* ``plan validation was empty`` (japanese-cafe).

Every one was stored ``VALIDATION_FAILED`` / non-retryable with ``repair_attempted: false``: the
operator was told a permanent rejection happened when in fact the route had spent its answer
budget on reasoning and never stated a verdict. Three of the four courses died of it.

What is asserted here:

* a cut-off answer (recorded completion tokens at the cap) is re-asked exactly once, on the same
  demand, under a marked ``.cut`` prompt version, and the pass's answer is then judged on merits;
* an *empty* answer that consumed the cap counts as cut off — that is the measured third shape;
* a malformed answer that stayed well under its cap is **not** retried (a resample would buy the
  same shape);
* a second cut-off answer is still a typed :class:`generation.ModelOutputInvalid`, never a verdict,
  and never a third call;
* the cap itself is pinned to the measured value, so a silent regression to 4 000 fails here.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen

#: One plan-validation pass's criteria, taken from the shipped grouping rather than hand-typed.
CRITERIA = gen.VALIDATION_CRITERIA_PASSES[0]


def _request() -> gen.LLMRequest:
    return gen.LLMRequest(
        purpose="coursebook.plan.validate",
        prompt_version=gen.VALIDATION_PROMPT_VERSION,
        system_prompt="you are the independent validator",
        instructions=gen.validation_pass_instructions(subject="plan", criteria=CRITERIA),
        input_text="{}",
        schema=gen.validation_pass_schema(CRITERIA),
        schema_name="coursebook_validation_v1",
        max_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        timeout_s=120.0,
    )


def _document() -> dict:
    """A schema-valid pass answer: every criterion this pass owns, passed, nothing else."""
    return {
        "verdict": "pass",
        "criteria": [
            {"id": criterion, "verdict": "pass", "reason": "the artifact shows this concretely"}
            for criterion in CRITERIA
        ],
        "rejections": [],
    }


def _cut_answer() -> gen.LLMResponse:
    """The measured astronomy shape: JSON that stops mid-string because the cap ran out."""
    return gen.LLMResponse(
        text='{"verdict": "pass", "criteria": [{"id": "objective_alignment", "verdict": "pa',
        parsed=None,
        provider="nous",
        model="deepseek/deepseek-v4.1-flash-1017",
        input_tokens=6862,
        output_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        cost_usd=None,
    )


def _empty_answer() -> gen.LLMResponse:
    """The measured japanese-cafe shape: the whole cap spent on reasoning, no content at all."""
    return gen.LLMResponse(
        text="",
        parsed=None,
        provider="nous",
        model="deepseek/deepseek-v4.1-flash-1017",
        input_tokens=6822,
        output_tokens=gen.VALIDATION_OUTPUT_TOKENS,
        cost_usd=None,
    )


def _good_answer() -> gen.LLMResponse:
    document = _document()
    return gen.LLMResponse(
        text=gen.canonical_json(document),
        parsed=document,
        provider="nous",
        model="deepseek/deepseek-v4.1-flash-1017",
        input_tokens=6862,
        output_tokens=3814,
        cost_usd=None,
    )


class _Scripted:
    """Provider double: hands out pre-built responses in order and records every request."""

    def __init__(self, *answers: gen.LLMResponse) -> None:
        self.answers = list(answers)
        self.requests: list[gen.LLMRequest] = []

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        self.requests.append(request)
        if not self.answers:
            raise AssertionError("provider called more times than the script allows")
        return self.answers.pop(0)


def _usage() -> gen._Usage:
    return gen._Usage(budget=gen.default_cost_budget(max_calls=8))


class TruncationRepairTests(unittest.TestCase):
    def test_a_cut_off_answer_is_re_asked_once_on_the_same_demand(self) -> None:
        first = _cut_answer()
        provider = _Scripted(_good_answer())
        request = _request()
        usage = _usage()

        document, answered = gen._validation_answer_with_repair(
            provider, request, first, usage, what="plan validation"
        )

        self.assertEqual([entry["id"] for entry in document["criteria"]], list(CRITERIA))
        # The first answer was handed in; exactly one provider call is the re-ask.
        self.assertEqual(len(provider.requests), 1)
        retry = provider.requests[0]
        # Same demand, same schema: the re-ask cannot widen the reviewed set.
        self.assertEqual(retry.schema, request.schema)
        self.assertEqual(retry.max_tokens, request.max_tokens)
        self.assertEqual(retry.purpose, request.purpose)
        # Different instruction text under a marked label (docs/GENERATION.md §1).
        self.assertTrue(retry.prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX))
        self.assertNotEqual(retry.prompt_version, request.prompt_version)
        self.assertIn("cut off", retry.instructions)
        # A repaired answer is never presented as first-time clean.
        self.assertEqual(answered.shape_repair_attempts, 1)
        # The handed-in cut answer was not a provider call here; only the re-ask is recorded.
        self.assertEqual(len(usage.calls), 1)

    def test_an_empty_answer_that_used_the_whole_cap_counts_as_cut_off(self) -> None:
        provider = _Scripted(_empty_answer(), _good_answer())
        request = _request()

        document, answered = gen._validation_answer_with_repair(
            provider, request, provider(request), _usage(), what="plan validation"
        )

        self.assertEqual(len(document["criteria"]), len(CRITERIA))
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(answered.shape_repair_attempts, 1)

    def test_a_malformed_answer_under_the_cap_is_not_re_asked(self) -> None:
        short = gen.LLMResponse(
            text='{"verdict": "pass"',
            parsed=None,
            provider="nous",
            model="deepseek/deepseek-v4.1-flash-1017",
            input_tokens=6000,
            output_tokens=180,
            cost_usd=None,
        )
        provider = _Scripted(short)

        with self.assertRaises(gen.ModelOutputInvalid) as raised:
            gen._validation_answer_with_repair(
                provider, _request(), provider(_request()), _usage(), what="plan validation"
            )

        self.assertEqual(len(provider.requests), 1)
        self.assertFalse(raised.exception.repair_attempted)

    def test_a_second_cut_off_answer_is_typed_and_never_a_third_call(self) -> None:
        first = _cut_answer()
        provider = _Scripted(_cut_answer())

        with self.assertRaises(gen.ModelOutputInvalid):
            gen._validation_answer_with_repair(
                provider, _request(), first, _usage(), what="plan validation"
            )

        self.assertEqual(len(provider.requests), 1)
        self.assertTrue(
            provider.requests[0].prompt_version.endswith(gen.TRUNCATION_REPAIR_PROMPT_SUFFIX)
        )

    def test_the_completion_cap_is_pinned_to_the_measured_value(self) -> None:
        # 4 000 was the measured truncating cap on the demo route; a return to it fails here.
        self.assertEqual(gen.VALIDATION_OUTPUT_TOKENS, 8000)
        self.assertEqual(gen.VALIDATION_AUX_DEFAULTS["extra_body"]["max_tokens"], 8000)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
