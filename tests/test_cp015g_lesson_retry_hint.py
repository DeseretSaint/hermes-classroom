"""CP-015g: a retry must reach a third attempt when each refusal is a *different* mistake.

Measured live for an unseen topic ("prune a fig tree"), 2026-11-11, across two validation
records for the same lesson section:

* attempt 1 (20:27:48) was refused under ``rubric_consistency`` and ``source_support`` for a
  claim neither cited source states (long branches shade lower growth), with the fix hint
  "Drop the shade mechanism or add a source that states it." on ``lesson.segments[0].body``;
* attempt 2 (20:41:27) *did* apply that hint and dropped the claim, but was refused under
  ``answer_leakage`` and ``source_support`` because ``learner_explanation`` restated the
  reference answer in different words ("heavy reset after cold danger; light tidying...").

So the hint reached the retry; the defect is that ``LESSON_ATTEMPTS = 2`` leaves no room for a
second, different mistake, and the prompt never said the explanation must not restate the key in
any wording. These tests prove the third attempt exists, that the retry carries the refusal that
applies to it, and that a prompt-compliant explanation does not read as an answer leak.
"""

from __future__ import annotations

import json

from tests.test_generation import (
    FakeLLM,
    GenerationTestBase,
    NOW,
    lesson_from_request,
    response,
    validation_from_fixture,
)

from coursebook import generation as gen

#: The unsupported mechanism the measured first draft carried.
UNSUPPORTED_CLAIM = (
    "Long branches shade the lower growth, so the tree keeps only the highest buds."
)
ITEM_PATH = "lesson.segments[0].body"
FIX_HINT = "Drop the shade mechanism or add a source that states it."
#: The paraphrase the measured second draft put in ``learner_explanation``. It is not the
#: reference answer verbatim, so the deterministic scan misses it; the independent validator
#: reads it as shipped key.
ANSWER_ECHO = "When you answer, the greeting is the one to say."
LEAK_PATH = "lesson.learner_explanation"


class LessonRetryHintTest(GenerationTestBase):
    def lesson_script(self, validate, generate=None) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate or lesson_from_request(),
                "coursebook.lesson.validate": validate,
            }
        )

    def run_lessons(self, plan_result: dict, llm: FakeLLM) -> dict:
        return gen.run_lesson_job(
            self.connection,
            {"job_id": "job-lesson-retry", "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )

    def _validator(self):
        """Judge the draft's content: the refused claim first, then the key echo.

        Content-sensitive, not call-count-sensitive: each refusal follows the defect the draft
        actually carries, exactly as the two live validation records did.
        """
        accept = validation_from_fixture("validation_pass")

        def validate(request: gen.LLMRequest) -> gen.LLMResponse:
            payload = json.loads(request.input_text)
            lesson = payload.get("lesson") or {}
            explanation = str(lesson.get("learner_explanation") or "")
            carries_claim = any(
                UNSUPPORTED_CLAIM in str(segment.get("body") or "")
                for segment in lesson.get("segments") or []
            )
            passed = json.loads(accept(request).text)
            if not carries_claim and ANSWER_ECHO not in explanation:
                return response(passed, model="fake-validator")
            passed["verdict"] = "reject"
            if carries_claim:
                failed, path, reason, hint = (
                    "source_support",
                    ITEM_PATH,
                    "Neither cited page states that long branches shade lower growth.",
                    FIX_HINT,
                )
            else:
                failed, path, reason, hint = (
                    "answer_leakage",
                    LEAK_PATH,
                    "The learner explanation restates the reference answer in different words.",
                    "Describe how to reach the answer; do not state or paraphrase the key.",
                )
            passed["criteria"] = [
                (
                    {**entry, "verdict": "fail", "reason": reason}
                    if entry.get("id") == failed
                    else entry
                )
                for entry in passed["criteria"]
            ]
            passed["rejections"] = [
                {"item": path, "criterion": failed, "reason": reason, "fix_hint": hint}
            ]
            return response(passed, model="fake-validator")

        return validate

    def _generator(self, *, measured_sequence: bool):
        """The first section repeats the measured sequence; every other section is clean.

        Draft 1 carries the unsupported claim. Draft 2 drops it but restates the key in the
        explanation. Draft 3 is prompt-compliant. With two attempts this parks after draft 2.
        """
        base = lesson_from_request()
        attempts: dict[str, int] = {}
        first: dict[str, str | None] = {"id": None}

        def generate(request: gen.LLMRequest) -> gen.LLMResponse:
            payload = json.loads(request.input_text)
            section_id = str((payload.get("section") or {}).get("section_id") or "")
            attempts[section_id] = attempts.get(section_id, 0) + 1
            if first["id"] is None:
                first["id"] = section_id
            built = base(request)
            if not measured_sequence or section_id != first["id"]:
                return built
            draft = json.loads(built.text)
            segments = [dict(segment) for segment in draft["segments"]]
            if attempts[section_id] == 1:
                segments[0]["body"] = f"{segments[0]['body']} {UNSUPPORTED_CLAIM}"
            elif attempts[section_id] == 2:
                draft["learner_explanation"] = (
                    f"{draft['learner_explanation']} {ANSWER_ECHO}"
                )
            draft["segments"] = segments
            return response(draft, model="fake-author")

        return generate

    def test_a_different_second_mistake_still_earns_a_third_attempt(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(
            self._validator(),
            generate=self._generator(measured_sequence=True),
        )
        result = self.run_lessons(plan_result, llm)

        first = result["lessons"][0]
        self.assertEqual(first["state"], "validated")
        self.assertTrue(first["check_enabled"])
        self.assertEqual(result["needs_review"], [])
        first_section = first["section_id"]
        generations = [
            request
            for request in llm.requests
            if request.purpose == "coursebook.lesson.generate"
            and json.loads(request.input_text)["section"]["section_id"] == first_section
        ]
        self.assertEqual(len(generations), 3)
        # Attempt 2 carried the first refusal (the claim hint); attempt 3 carried the *second*
        # refusal of attempt 2, which named a different criterion and a different item.
        second_revision = json.loads(generations[1].input_text).get("revision_instructions") or ""
        third_revision = json.loads(generations[2].input_text).get("revision_instructions") or ""
        self.assertIn(ITEM_PATH, second_revision)
        self.assertIn(FIX_HINT, second_revision)
        self.assertIn(LEAK_PATH, third_revision)
        self.assertIn("answer_leakage", third_revision)
        self.assertNotIn(FIX_HINT, third_revision)

    def test_a_generator_that_repeats_the_same_mistake_twice_still_parks(self) -> None:
        plan_result = self.approved_plan()
        # Freeze every section on the refused claim: three identical refusals spend the ceiling.
        stuck = self._generator(measured_sequence=True)

        def repeat_claim(request: gen.LLMRequest) -> gen.LLMResponse:
            built = stuck(request)
            payload = json.loads(built.text)
            segments = [dict(segment) for segment in payload["segments"]]
            if UNSUPPORTED_CLAIM not in segments[0]["body"]:
                segments[0]["body"] = f"{segments[0]['body']} {UNSUPPORTED_CLAIM}"
            payload["segments"] = segments
            return response(payload, model="fake-author")

        llm = self.lesson_script(self._validator(), generate=repeat_claim)
        result = self.run_lessons(plan_result, llm)

        parked = result["lessons"][0]
        self.assertEqual(parked["state"], "needs_review")
        self.assertFalse(parked["check_enabled"])
        self.assertIn(parked["section_id"], result["needs_review"])
        check = self.rows("SELECT * FROM checks WHERE id = ?", (parked["check_id"],))[0]
        self.assertEqual(check["audit_state"], "failed")
        self.assertEqual(check["state"], "closed")
        with self.assertRaises(gen.LessonNotAvailable):
            gen.learner_page(self.connection, parked["lesson_id"])

    def test_the_prompt_names_the_explanation_as_a_coaching_surface(self) -> None:
        instructions = gen._lesson_instructions(
            recipe="casual", locale=None, scaffold_note=""
        )
        self.assertIn("learner_explanation is a coaching surface", instructions)
        self.assertIn("paraphrase", instructions)

    def test_a_prompt_compliant_explanation_does_not_trip_answer_leakage(self) -> None:
        # The fixture's explanation coaches ("set them aside; the remaining phrase is...") and its
        # reference answer is a specific phrase: the deterministic scan must clear it, and the
        # content-aware independent pass above must pass it, which the run proves end to end.
        plan_result = self.approved_plan()
        llm = self.lesson_script(self._validator())
        result = self.run_lessons(plan_result, llm)
        self.assertTrue(all(item["state"] == "validated" for item in result["lessons"]))
        self.assertEqual(result["needs_review"], [])
