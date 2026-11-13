"""CP-015c follow-up: the lesson prompt states the answer-leak surfaces it is judged by.

Reproduction: on the approved Japanese Cafe plan (``pln_5dde08c973f94cc0a444caa77a09d53c``) the
lesson stage re-authored all three owner sections once and every one parked ``needs_review``.
Sections 1 and 2 were refused on the answer-leak family — section 1 by the deterministic gate
(``learner-facing narrative contains the check reference answer or a keyed answer``) and section 2
by the independent validator (``lesson.learner_explanation`` ... leaking the quiz answer). The
author taught the target in the model segment, which is the one presentation surface, and then
restated it verbatim in the explanation and the worked example — the natural way to explain a
phrase the learner is about to be checked on — because ``lesson-prompt.v10`` never stated which
surfaces are scanned.

The review page's validator added a second, distinct surface: ``lesson.check.reference_answer`` —
the learner-facing check appeared to ship the reference answer and accepted answers with
justifications. That is a check-payload leak, not a page-narrative leak.

These cases pin the fix at both ends:

* ``lesson-prompt.v11`` (carried into ``v12``) states the scanned surfaces, the one presentation
  surface, the legal shape and one passing example;
* a page that teaches the target in the model segment and refers to it elsewhere validates;
* the same page restating the key in the explanation (or a short) is still refused, deterministically,
  before any validator pass;
* a check whose stimulus prompt ships the reference answer is refused as
  ``lesson.check.reference_answer``;
* the lesson validation payload separates the stored key from the learner-facing artifact, and
  ``validation-prompt.v9`` says so.
"""

from __future__ import annotations

import json
import unittest

from coursebook import generation as gen

from tests.test_generation import (
    FakeLLM,
    GenerationTestBase,
    NOW,
    check_for_objective,
    lesson_fixture,
    response,
    source_ids_from,
    validation_from_fixture,
)

KEY = "こんにちは"


def taught_then_checked_lesson() -> dict:
    """A page that teaches the target once (the model segment) and refers to it elsewhere.

    The explanation names the phrase by where it was shown, never by restating it; the check keeps
    its authored key in the stored answer field. This is the shape the prompt now describes.
    """
    lesson = lesson_fixture("lesson_ja")
    lesson["segments"][0]["kind"] = "model"
    lesson["segments"][0]["body"] = (
        "こんにちは (konnichiwa) means \"hello\" and is the standard daytime greeting when you "
        "enter a shop or meet someone."
    )
    lesson["segments"][1]["kind"] = "explain"
    lesson["segments"][1]["body"] = (
        "The greeting the model segment showed is the daytime one; use it when you enter, not "
        "when you leave."
    )
    lesson["segments"][1]["short"] = "Use the daytime greeting when you enter."
    lesson["learner_explanation"] = (
        "Answer the greeting question with the phrase the model segment showed. The other "
        "options are for other times of day."
    )
    lesson["learner_explanation_short"] = "Use the phrase the model segment showed."
    return lesson


class AnswerLeakPromptRuleTest(unittest.TestCase):
    """The prompt states the rule the deterministic gate enforces (v11)."""

    def instructions(self) -> str:
        return gen._lesson_instructions(
            recipe="committed", locale="ja-JP", scaffold_note=""
        )

    def test_the_version_advanced_for_the_new_instruction_text(self) -> None:
        self.assertEqual(gen.LESSON_PROMPT_VERSION, "lesson-prompt.v16")

    def test_the_prompt_names_the_scanned_surfaces_and_the_one_presentation_surface(self) -> None:
        text = self.instructions()
        self.assertIn("Answer-leak rule", text)
        # The one exempt surface, in the gate's own terms.
        self.assertIn("kind 'model'", text)
        self.assertIn("presentation surface", text)
        self.assertIn("Narration-role media", text)
        # Every scanned surface the gate's _narrative_text reads.
        for surface in (
            "worked example",
            "learner_explanation",
            "learner_explanation_short",
            "parent_notes",
            "non-narration media",
            "recap",
        ):
            self.assertIn(surface, text)
        # Choices are deliberately not scanned, and the prompt says why.
        self.assertIn("choices are not scanned", text)

    def test_the_prompt_states_the_legal_shape_and_a_passing_example(self) -> None:
        text = self.instructions()
        self.assertIn("Legal shape for a taught-then-checked item", text)
        self.assertIn("form plus reading or gloss plus function", text)
        self.assertIn("never restate the reference answer verbatim", text)
        self.assertIn("Passing example", text)
        self.assertIn("二人です (futari desu)", text)
        self.assertIn("The answer is 二人です", text)  # the refused shape, named

    def test_the_prompt_states_the_check_payload_rule(self) -> None:
        text = self.instructions()
        self.assertIn("check.reference_answer", text)
        self.assertIn("learner_instructions", text)
        self.assertIn("lesson.check.reference_answer", text)

    def test_the_lesson_request_payload_states_the_leak_rule_too(self) -> None:
        from tests.blueprint_support import media_none

        request = gen.build_lesson_request(
            plan={"title": "Cafe Japanese", "learner_outcome": "Order politely", "delivery": "self"},
            section={"section_id": "s1", "ordinal": 1, "title": "Greeting", "lesson_intent": "Greet",
                     "source_ids": [], "media_need": media_none()},
            objective={"id": "o1", "ordinal": 1, "title": "Greet", "evidence_target": "comprehension",
                       "evidence_criteria": []},
            recipe="committed",
            dials={},
            locale="ja-JP",
            sources=(),
        )
        payload = json.loads(request.input_text)
        self.assertIn("answer_leak", payload["rules"])
        self.assertIn("model", payload["rules"]["answer_leak"])


class TaughtThenCheckedGateTest(unittest.TestCase):
    """The deterministic gate admits teaching and refuses announcing."""

    def test_a_taught_then_checked_page_passes_the_narrative_scan(self) -> None:
        lesson = taught_then_checked_lesson()
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        # The key is presented in the model segment and nowhere else on the narrative surfaces.
        gen.assert_no_answer_leak(page, lesson)  # no exception

    def test_the_same_key_in_the_explanation_is_refused(self) -> None:
        lesson = taught_then_checked_lesson()
        lesson["learner_explanation"] = f"The answer is {KEY}."
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_no_answer_leak(page, lesson)
        self.assertIn("reference answer", " ".join(caught.exception.reasons))

    def test_the_same_key_in_a_non_model_short_is_refused(self) -> None:
        lesson = taught_then_checked_lesson()
        lesson["segments"][1]["short"] = f"Pick {KEY}."
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        with self.assertRaises(gen._RuleViolation):
            gen.assert_no_answer_leak(page, lesson)


class CheckPayloadLeakGateTest(unittest.TestCase):
    """The learner-facing check must not ship the key with the question (CP-015c follow-up)."""

    def test_a_check_prompt_that_restates_the_key_is_refused_under_a_named_reason(self) -> None:
        lesson = taught_then_checked_lesson()
        lesson["check"]["stimulus"]["prompt"] = f"Choose the greeting: {KEY}."
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_check_payload_does_not_announce_answer(lesson)
        self.assertTrue(caught.exception.reasons[0].startswith("lesson.check.reference_answer:"))

    def test_learner_instructions_that_restate_the_key_are_refused(self) -> None:
        lesson = taught_then_checked_lesson()
        lesson["check"]["learner_instructions"] = f"Write {KEY} in the box."
        with self.assertRaises(gen._RuleViolation):
            gen.assert_check_payload_does_not_announce_answer(lesson)

    def test_choices_may_carry_the_correct_choice_without_leaking_it(self) -> None:
        lesson = taught_then_checked_lesson()
        # A selection check necessarily lists the correct choice; only the question is scanned.
        self.assertIn(KEY, [str(item) for item in lesson["check"]["stimulus"]["choices"]])
        gen.assert_check_payload_does_not_announce_answer(lesson)  # no exception

    def test_a_short_choice_token_is_not_treated_as_a_restated_answer(self) -> None:
        lesson = taught_then_checked_lesson()
        lesson["check"]["reference_answer"] = "2"
        lesson["check"]["accepted_answers"] = ["2"]
        lesson["check"]["stimulus"]["prompt"] = "Choose one of the 2 lines that opens the greeting."
        gen.assert_check_payload_does_not_announce_answer(lesson)  # no exception

    def test_the_learner_page_projection_still_drops_the_stored_key(self) -> None:
        lesson = taught_then_checked_lesson()
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        serialized = json.dumps(page, ensure_ascii=False)
        for forbidden in ("reference_answer", "accepted_answers", "accepted_alternatives", "rubric"):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("check", page)
        self.assertIn("learner_instructions", page["check"])


class MediaSpecAnswerLeakTest(unittest.TestCase):
    """MEDIA-3: the media spec is a generation prompt, not a place to park the answer.

    ``media[].spec`` never reaches the learner page, so the narrative scan cannot see it; but the
    artifact is generated *from* that text, so an answer named there is baked into the picture or
    clip the learner receives.
    """

    @staticmethod
    def media(spec: str, *, role: str = "illustration") -> dict:
        return {
            "kind": "visual",
            "role": role,
            "purpose": "Show the counter where the greeting is used.",
            "spec": spec,
            "text_equivalent": "A café counter with staff looking up as a learner enters.",
        }

    def test_a_media_spec_that_restates_the_key_is_refused(self) -> None:
        lesson = lesson_fixture("lesson_ja")
        lesson["media"] = [self.media(f"Draw the greeting {KEY} lettered above the shop door.")]
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_no_answer_leak(page, lesson)
        self.assertTrue(
            any("media spec" in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_a_media_spec_that_describes_without_the_key_passes(self) -> None:
        lesson = lesson_fixture("lesson_ja")
        lesson["media"] = [
            self.media("A learner entering a café, staff looking up; no lettering on the image.")
        ]
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        gen.assert_no_answer_leak(page, lesson)  # no exception

    def test_narration_may_read_the_presenting_segment_it_is_a_voice_for(self) -> None:
        # The narration is the audio of the model segment: presenting the target is its job.
        lesson = taught_then_checked_lesson()
        lesson["media"] = [self.media(f"Read the model segment aloud, including {KEY}.", role="narration")]
        page = gen._build_learner_page(lesson, {"lesson_intent": "Greet"}, ())
        gen.assert_no_answer_leak(page, lesson)  # no exception


class LessonValidationPayloadSplitTest(unittest.TestCase):
    """The key is authoring material and travels in its own block, stated by validation-prompt.v9."""

    def build(self):
        lesson = taught_then_checked_lesson()
        section = {"section_id": "s1", "ordinal": 1, "title": "Greeting",
                   "lesson_intent": "Greet", "source_ids": []}
        objective = {"id": "o1", "ordinal": 1, "title": "Greet",
                     "evidence_target": "comprehension", "evidence_criteria": []}
        page = gen._build_learner_page(lesson, section, ())
        request = gen.build_lesson_validation_request(
            lesson=lesson, page=page, section=section, objective=objective,
            recipe="committed", dials={}, locale="ja-JP", sources=(),
        )
        return lesson, request, json.loads(request.input_text)

    def test_the_version_advanced_for_the_new_instruction_text(self) -> None:
        # v9 is this card's answer-key locator; v10 is CP-015g/D1-F1's typed performance block
        # in the plan-validation payload (this pass's text is unchanged, the label is shared).
        self.assertEqual(gen.VALIDATION_PROMPT_VERSION, "validation-prompt.v13")

    def test_the_key_leaves_the_learner_facing_check_and_is_marked_authoring_material(self) -> None:
        lesson, _request, payload = self.build()
        self.assertNotIn("reference_answer", payload["lesson"]["check"])
        self.assertNotIn("accepted_answers", payload["lesson"]["check"])
        self.assertNotIn("rubric", payload["lesson"]["check"])
        self.assertFalse(payload["answer_key"]["learner_facing"])
        self.assertEqual(payload["answer_key"]["reference_answer"], lesson["check"]["reference_answer"])
        self.assertEqual(payload["answer_key"]["accepted_answers"], lesson["check"]["accepted_answers"])
        self.assertEqual(payload["answer_key"]["rubric"], lesson["check"]["rubric"])

    def test_the_instructions_state_where_the_key_lives_and_where_it_is_judged(self) -> None:
        _lesson, request, _payload = self.build()
        text = request.instructions
        self.assertIn("'answer_key'", text)
        self.assertIn("never serialized into the learner page", text)
        self.assertIn("Judge 'answer_leakage' on the learner-facing surfaces only", text)
        self.assertIn("lesson.check.reference_answer", text)
        self.assertIn("'model'", text)


class AuthoringPathParksTheRealShapesTest(GenerationTestBase):
    """Through the real lesson job: teaching validates, announcing and shipping the key park."""

    def lesson_script(self, validate, generate):
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate,
                "coursebook.lesson.validate": validate,
            }
        )

    def run_lessons(self, plan_result, llm):
        return gen.run_lesson_job(
            self.connection,
            {"job_id": "job-cp015c-leak", "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=32),
        )

    def _leaky(self, mutate):
        def build(request: gen.LLMRequest):
            payload = json.loads(request.input_text)
            lesson = taught_then_checked_lesson()
            ids = source_ids_from(request)
            if ids:
                lesson = json.loads(
                    json.dumps(lesson, ensure_ascii=False).replace("SRC_ALPHA", ids[0])
                )
                lesson["sources"] = list(ids)
            lesson["section_title"] = (payload.get("section") or {}).get("title") or lesson["section_title"]
            check_for_objective(lesson, payload.get("objective") or {})
            mutate(lesson)
            return response(lesson, model="fake-author")

        return build

    def test_a_taught_then_checked_page_reaches_validation_and_passes(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(validation_from_fixture(), generate=self._leaky(lambda lesson: None))
        result = self.run_lessons(plan_result, llm)
        # No deterministic refusal fired, so the independent pass actually ran for each owner.
        self.assertGreaterEqual(llm.calls_for("coursebook.lesson.validate"), 1)
        self.assertTrue(any(item["state"] == "validated" for item in result["lessons"]))

    def test_an_explanation_that_restates_the_key_parks_before_validation(self) -> None:
        plan_result = self.approved_plan()

        def restate(lesson: dict) -> None:
            lesson["learner_explanation"] = f"The answer is {KEY}."

        llm = self.lesson_script(
            validation_from_fixture(), generate=self._leaky(restate)
        )
        result = self.run_lessons(plan_result, llm)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
        reasons = " ".join(result["lessons"][0]["rejection_reasons"])
        self.assertIn("reference answer", reasons)

    def test_a_check_prompt_that_ships_the_key_parks_with_the_named_reason(self) -> None:
        plan_result = self.approved_plan()

        def ship_key(lesson: dict) -> None:
            lesson["check"]["stimulus"]["prompt"] = f"Choose the greeting: {KEY}."

        llm = self.lesson_script(
            validation_from_fixture(), generate=self._leaky(ship_key)
        )
        result = self.run_lessons(plan_result, llm)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
        reasons = " ".join(result["lessons"][0]["rejection_reasons"])
        self.assertIn("lesson.check.reference_answer", reasons)


if __name__ == "__main__":
    unittest.main()
