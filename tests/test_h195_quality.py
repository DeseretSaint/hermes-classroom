"""H-195 — the authoring contract: through-line, teaching floor, provenance.

The implementation lives in ``coursebook/generation.py`` (commit ``b1f04eb``, carried onto master
by H-195a). These tests do not re-test the plan/lesson jobs end to end — ``tests/test_generation.py``
already does that 87 times. They pin the three things H-195 added and that nothing else guards:

1. **Through-line and prerequisite assumptions** are schema-required on both plan schemas and are
   refused by ``enforce_plan_rules`` when absent, too thin, or when the plan drifts into generic
   study skills the goal did not ask for.
2. **The teaching floor** is deterministic: arc, worked steps, lesson-specific headings and a
   prose floor. It refuses an outline; it never scores prose quality.
3. **Provenance** lands on every artifact the pipeline hands out — and the only model identity
   recorded is the one the provider reported. An unbound host raises the typed rejection instead
   of producing a canned document.

Every test runs offline against the fake provider; no test claims a live call.

Run: ``python3 -m unittest tests.test_h195_quality``
"""

from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from coursebook import generation as gen
from tests.blueprint_support import blueprint_plan
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    _unsourced,
    fixture,
    lesson_from_request,
    plan_fixture,
    plan_job,
    response,
    source_ids_from,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def v1_plan() -> dict:
    """The v1 (legacy, unscoped) plan fixture with no citations, ready for the rule set."""
    return _unsourced(fixture("plan_ja"))


class ThroughLineSchemaTest(unittest.TestCase):
    """The arc and the starting assumptions are fields, not decoration."""

    def test_both_plan_schemas_require_the_two_fields(self) -> None:
        for name, schema in (("v1", gen.PLAN_SCHEMA_V1), ("v2", gen.PLAN_SCHEMA_V2)):
            with self.subTest(schema=name):
                self.assertIn("through_line", schema["required"])
                self.assertIn("prerequisite_assumptions", schema["required"])
                self.assertEqual(
                    schema["properties"]["through_line"]["minLength"],
                    gen.THROUGH_LINE_SCHEMA["minLength"],
                )
                self.assertEqual(
                    schema["properties"]["prerequisite_assumptions"]["minItems"], 1
                )

    def test_the_authored_fixtures_validate(self) -> None:
        from jsonschema import Draft202012Validator

        for name, document, schema in (
            ("plan_ja", fixture("plan_ja"), gen.PLAN_SCHEMA_V1),
            ("blueprint_plan", blueprint_plan(), gen.PLAN_SCHEMA_V2),
        ):
            with self.subTest(plan=name):
                errors = [
                    f"{list(error.path)}: {error.message}"
                    for error in Draft202012Validator(schema).iter_errors(document)
                ]
                self.assertEqual(errors, [])

    def test_a_plan_without_a_through_line_is_refused(self) -> None:
        document = v1_plan()
        document.pop("through_line")
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(document, recipe="committed", dials={}, locale="ja-JP", ledger=[])
        self.assertTrue(any("through_line" in reason for reason in caught.exception.reasons))

    def test_a_through_line_too_short_to_state_an_arc_is_refused(self) -> None:
        document = v1_plan()
        document["through_line"] = "Learn things."
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(document, recipe="committed", dials={}, locale="ja-JP", ledger=[])
        joined = " ".join(caught.exception.reasons)
        self.assertIn("through_line", joined)
        self.assertIn("too short", joined)

    def test_empty_prerequisite_assumptions_are_refused(self) -> None:
        document = v1_plan()
        document["prerequisite_assumptions"] = []
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(document, recipe="committed", dials={}, locale="ja-JP", ledger=[])
        self.assertTrue(
            any("prerequisite_assumptions" in reason for reason in caught.exception.reasons)
        )

    def test_blank_prerequisite_entries_do_not_count(self) -> None:
        document = v1_plan()
        document["prerequisite_assumptions"] = ["   ", ""]
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(document, recipe="committed", dials={}, locale="ja-JP", ledger=[])
        self.assertTrue(
            any("prerequisite_assumptions" in reason for reason in caught.exception.reasons)
        )


class GenericStudyDriftTest(unittest.TestCase):
    """A course that drifts into study skills is a different course — unless the goal asked."""

    def drifted(self) -> dict:
        document = v1_plan()
        document["objectives"][0]["title"] = "Time management for a café visit"
        return document

    def test_drift_the_goal_does_not_name_is_refused(self) -> None:
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                self.drifted(),
                recipe="committed",
                dials={},
                locale="ja-JP",
                ledger=[],
                goal="Order coffee in Japanese",
            )
        joined = " ".join(caught.exception.reasons)
        self.assertIn("generic study skills", joined)
        self.assertIn("time management", joined)

    def test_drift_the_goal_itself_names_is_allowed(self) -> None:
        # The same objective is honest when the owner asked for that course. The rule must not
        # refuse a real course about time management.
        gen.enforce_plan_rules(
            self.drifted(),
            recipe="committed",
            dials={},
            locale="ja-JP",
            ledger=[],
            goal="Build a time management routine for shift work",
        )

    def test_section_intents_are_checked_too(self) -> None:
        document = v1_plan()
        document["sections"][0]["lesson_intent"] = "Cover note-taking as a study habit."
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                document,
                recipe="committed",
                dials={},
                locale="ja-JP",
                ledger=[],
                goal="Order coffee in Japanese",
            )
        self.assertTrue(
            any("sections[].lesson_intent" in reason for reason in caught.exception.reasons)
        )


class TeachingFloorTest(unittest.TestCase):
    """The floor is deterministic and structural: it refuses an outline, never a style."""

    def lesson(self) -> dict:
        return {
            "section_title": "A section",
            "segments": [
                {
                    "kind": "model",
                    "heading": "Name the two parts",
                    "body": "A" * 200,
                    "short": "Name the two parts.",
                },
                {
                    "kind": "guided",
                    "heading": "Try it with one example",
                    "body": "B" * 260,
                    "short": "Try it with one example.",
                },
            ],
            "worked_example": {
                "prompt": "Do it once",
                "steps": ["First step", "Second step"],
                "answer": "the answer",
                "short": "Do it once.",
            },
            "learner_explanation": "You will do the thing twice.",
        }

    def test_the_floor_parameters_are_the_documented_ones(self) -> None:
        self.assertEqual(gen.MIN_TEACHING_PROSE_CHARS, 400)
        self.assertEqual(gen.MIN_SINGLE_SEGMENT_CHARS, 120)
        self.assertEqual(gen.MAX_SINGLE_SEGMENT_CHARS, 1200)
        self.assertIn("overview", gen.GENERIC_LESSON_HEADINGS)
        self.assertIn("key takeaways", gen.GENERIC_LESSON_HEADINGS)
        self.assertIn("lorem ipsum", gen.PLACEHOLDER_LESSON_PHRASES)
        # The depth floor is deterministic: it is not a VALIDATION_CRITERIA entry. (CP-015a took the
        # count to eleven with goal_capability_disclosure; this floor is still not one of them.)
        self.assertEqual(len(gen.VALIDATION_CRITERIA), 11)
        self.assertNotIn("teaching_depth", gen.VALIDATION_CRITERIA)

    def test_a_lesson_that_meets_the_floor_has_no_problems(self) -> None:
        self.assertEqual(gen.teaching_quality_problems(self.lesson()), [])

    def test_the_authored_lesson_fixtures_clear_the_floor(self) -> None:
        for name in (
            "lesson_ja",
            "lesson_fr",
            "lesson_one_off",
            "lesson_parent_safe",
            "lesson_parent_unsafe",
        ):
            with self.subTest(fixture=name):
                self.assertEqual(gen.teaching_quality_problems(fixture(name)), [])

    def test_an_outline_below_the_prose_floor_is_refused(self) -> None:
        lesson = self.lesson()
        for segment in lesson["segments"]:
            segment["body"] = segment["body"][:100]
        problems = gen.teaching_quality_problems(lesson)
        self.assertTrue(any("teaching prose is" in problem for problem in problems), problems)
        self.assertTrue(any("longest segment body" in problem for problem in problems), problems)

    def test_a_missing_model_or_guided_segment_breaks_the_arc(self) -> None:
        for kind in ("model", "guided"):
            with self.subTest(missing=kind):
                lesson = self.lesson()
                lesson["segments"] = [
                    segment for segment in lesson["segments"] if segment["kind"] != kind
                ]
                problems = gen.teaching_quality_problems(lesson)
                self.assertTrue(any("teaching arc" in problem for problem in problems), problems)

    def test_a_one_step_worked_example_is_refused(self) -> None:
        lesson = self.lesson()
        lesson["worked_example"]["steps"] = ["Only step"]
        problems = gen.teaching_quality_problems(lesson)
        self.assertTrue(any("fewer than two steps" in problem for problem in problems), problems)

    def test_generic_headings_are_refused_after_folding(self) -> None:
        for heading in ("Overview", "Key Points", "key-takeaways", "Summary"):
            with self.subTest(heading=heading):
                lesson = self.lesson()
                lesson["segments"][0]["heading"] = heading
                problems = gen.teaching_quality_problems(lesson)
                self.assertTrue(
                    any("generic template heading" in problem for problem in problems), problems
                )

    def test_two_segments_with_the_same_heading_are_refused(self) -> None:
        lesson = self.lesson()
        lesson["segments"][1]["heading"] = lesson["segments"][0]["heading"]
        problems = gen.teaching_quality_problems(lesson)
        self.assertTrue(any("two segments share the heading" in problem for problem in problems))

    def test_placeholder_prose_is_refused(self) -> None:
        lesson = self.lesson()
        lesson["segments"][1]["body"] = "Lorem ipsum " + lesson["segments"][1]["body"]
        problems = gen.teaching_quality_problems(lesson)
        self.assertTrue(any("boilerplate phrase" in problem for problem in problems), problems)


class PlanProvenanceTest(GenerationTestBase):
    """`generation_provenance()` records the provider's report on every artifact."""

    def run_plan(self, model: str | None = "fake-model") -> dict:
        def authored(request: gen.LLMRequest) -> gen.LLMResponse:
            payload = plan_fixture("plan_ja", source_ids_from(request))
            # Built directly so the ``model: None`` case is expressible: a fake provider that
            # reports no model is exactly the unbound-host shape this test needs.
            return gen.LLMResponse(
                text=json.dumps(payload, ensure_ascii=False),
                parsed=payload,
                provider="fake" if model else None,
                model=model,
                input_tokens=120,
                output_tokens=240,
                cost_usd=0.01,
            )

        llm = FakeLLM(
            {
                "coursebook.plan.generate": authored,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        return gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)

    def test_the_plan_job_result_names_the_model_the_provider_reported(self) -> None:
        result = self.run_plan()
        generation = result["generation"]
        self.assertEqual(generation["provider"], "fake")
        self.assertEqual(generation["model"], "fake-model")
        self.assertTrue(generation["known"])
        self.assertEqual(generation["prompt_version"], gen.PLAN_PROMPT_VERSION)
        self.assertEqual(generation["pipeline_version"], gen.PIPELINE_VERSION)
        self.assertEqual(gen.PIPELINE_VERSION, "cb.gen.v2")

    def test_the_approval_block_carries_the_generator_identity(self) -> None:
        result = self.run_plan()
        approval = result["approval_provenance"]
        self.assertEqual(approval["generator"], {"provider": "fake", "model": "fake-model",
                                                 "known": True})
        self.assertEqual(approval["prompt_version"], gen.PLAN_PROMPT_VERSION)

    def test_the_plan_document_reads_back_the_same_generation_block(self) -> None:
        result = self.run_plan()
        document = gen.plan_document(self.connection, result["plan_id"])
        self.assertEqual(document["generation"], result["generation"])

    def test_an_unreported_model_is_unknown_and_never_invented(self) -> None:
        result = self.run_plan(model=None)
        generation = result["generation"]
        self.assertIsNone(generation["model"])
        self.assertIsNone(generation["provider"])
        self.assertFalse(generation["known"])

    def test_an_unbound_host_raises_the_typed_rejection_and_writes_no_document(self) -> None:
        # The host seam returns something that is not an LLMResponse: there is no model to bind
        # provenance to, so the pipeline must refuse rather than hand out a canned plan.
        def unbound(request: gen.LLMRequest):
            return None

        with self.assertRaises(gen.GenerationRejected):
            gen.run_plan_job(
                self.connection,
                plan_job(job_id="job-unbound"),
                unbound,  # type: ignore[arg-type]  # deliberately not an LLMResponse
                FakeSearch(),
            )
        self.assertEqual(self.count("plans"), 0)

    def test_no_host_llm_bound_is_refused_loudly(self) -> None:
        with mock.patch.object(gen, "_HOST_LLM", None):
            with self.assertRaises(gen.GenerationRejected) as caught:
                gen.host_llm()
        self.assertIn("no host LLM bound", str(caught.exception))


class LessonProvenanceTest(GenerationTestBase):
    """Each lesson summary records what wrote it, from the provider's report."""

    def test_every_lesson_summary_carries_its_generation_block(self) -> None:
        plan = self.approved_plan()
        llm = FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request("lesson_ja"),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        result = gen.run_lesson_job(
            self.connection,
            {"job_id": "job-h195-lesson", "kind": "plan",
             "brief": {"plan_id": plan["plan_id"]}},
            llm,
            budget=gen.CostBudget(max_calls=32),
        )
        self.assertTrue(result["lessons"])
        for summary in result["lessons"]:
            generation = summary["generation"]
            self.assertEqual(generation["provider"], "fake")
            self.assertEqual(generation["model"], "fake-author")
            self.assertTrue(generation["known"])
            # A repaired attempt carries the documented revision suffix on the same prompt label
            # (``REVISION_PROMPT_SUFFIX``); the provenance block records the label actually used.
            self.assertTrue(
                generation["prompt_version"].startswith(gen.LESSON_PROMPT_VERSION),
                generation["prompt_version"],
            )
            self.assertEqual(generation["pipeline_version"], gen.PIPELINE_VERSION)
            self.assertNotIn("answer", json.dumps(generation))


if __name__ == "__main__":
    unittest.main()
