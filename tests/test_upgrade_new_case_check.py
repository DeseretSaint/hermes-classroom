"""Upgrade 12: the check must pose a case the page has not already solved.

The model segment is the one learner surface allowed to print the target, and the check then
keyed that literal string with no rule that its prompt pose a *case the page had not already
solved*. The author taught "your host asks X — answer Y" in the model segment and then keyed the
check on the same host question, so the learner reproduced a sentence read minutes earlier and a
recall-family check measured look-up plus short-term copying.

Neither existing gate saw it: ``assert_no_answer_leak`` protects the key on the narrative surfaces
(the prompt is not one), and ``assert_check_payload_does_not_announce_answer`` refuses the key in
the prompt — which never appeared, because the reused half of the sentence is the *question*.

These cases pin the fix at both ends:

* ``lesson-prompt.v19`` states the new-case rule next to the answer-leak rule and names the reason
  the gate refuses under;
* a check whose prompt re-poses the model segment's sentence is refused deterministically, before
  any validator pass, as ``lesson.check.model_sentence_reuse``;
* the same check with a prompt that varies the interlocutor and setting passes;
* an accepted answer that reproduces the model sentence is refused too;
* the rule is wired into the real lesson job, so the refusal parks the lesson rather than retrying
  against a validator that was never given the draft.
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

#: The model sentence the check must not re-pose. Its answer — 二人です / futari desu — is the
#: taught form; the *frame* is the host's question, and that is what the check may not reuse.
MODEL_BODY = (
    "Your host asks 何人ですか (nannin desu ka) — how many people — and you answer "
    "二人です (futari desu) — two people."
)
REUSED_PROMPT = (
    "Your host asks 何人ですか (nannin desu ka). How many people? What do you answer?"
)
NEW_CASE_PROMPT = (
    "Your sister's friend is coming to dinner tonight and asks how many are coming. "
    "How do you answer?"
)


def party_size_lesson(prompt: str) -> dict:
    """The taught-then-checked shape with the given prompt.

    The model segment presents the form, its reading and its function; the check asks for the form.
    Only the prompt's *case* changes between the passing and the refused drafts.
    """
    lesson = lesson_fixture("lesson_ja")
    lesson["segments"][0]["kind"] = "model"
    lesson["segments"][0]["body"] = MODEL_BODY
    lesson["check"]["reference_answer"] = "二人です"
    lesson["check"]["accepted_answers"] = ["二人です"]
    lesson["check"]["accepted_alternatives"] = [["futari desu"]]
    lesson["check"]["stimulus"]["prompt"] = prompt
    lesson["check"]["stimulus"]["choices"] = ["二人です", "お願いします", "さようなら"]
    lesson["check"]["learner_instructions"] = (
        "Type the phrase the model segment showed, as it is written there."
    )
    return lesson


def learner_page(lesson: dict) -> dict:
    return gen._build_learner_page(lesson, {"lesson_intent": "Say how many people"}, ())


class NewCasePromptRuleTest(unittest.TestCase):
    """The prompt states the rule the deterministic gate enforces (v19)."""

    def instructions(self) -> str:
        return gen._lesson_instructions(recipe="committed", locale="ja-JP", scaffold_note="")

    def test_the_version_advanced_for_the_new_instruction_text(self) -> None:
        self.assertEqual(gen.LESSON_PROMPT_VERSION, "lesson-prompt.v19")

    def test_the_prompt_states_the_new_case_rule_and_its_named_reason(self) -> None:
        text = self.instructions()
        self.assertIn("New-case rule", text)
        self.assertIn("lesson.check.model_sentence_reuse", text)
        self.assertIn("different interlocutor, setting or object", text)
        self.assertIn("may not reuse the model segment's sentence beyond the target form", text)

    def test_the_prompt_states_the_fairness_bound_the_adversarial_note_names(self) -> None:
        text = self.instructions()
        # A hard new-case gate is only fair when the frame is already taught.
        self.assertIn("only vocabulary and grammar this lesson already taught", text)

    def test_the_rule_sits_beside_the_answer_leak_rule_it_complements(self) -> None:
        text = self.instructions()
        self.assertIn("Answer-leak rule", text)
        leak = text.index("Answer-leak rule")
        new_case = text.index("New-case rule")
        stored_key = text.index("The stored answer key is not a learner surface")
        # New-case is next to the leak rule, before the stored-key paragraph: one contract, two
        # halves — what the page may show and what the check may ask.
        self.assertLess(leak, new_case)
        self.assertLess(new_case, stored_key)

    def test_the_lesson_request_payload_carries_the_new_case_rule(self) -> None:
        from tests.blueprint_support import media_none

        request = gen.build_lesson_request(
            plan={"title": "Cafe Japanese", "learner_outcome": "Order politely", "delivery": "self"},
            section={"section_id": "s1", "ordinal": 1, "title": "Greeting",
                     "lesson_intent": "Greet", "source_ids": [], "media_need": media_none()},
            objective={"id": "o1", "ordinal": 1, "title": "Greet",
                       "evidence_target": "comprehension", "evidence_criteria": []},
            recipe="committed",
            dials={},
            locale="ja-JP",
            sources=(),
        )
        payload = json.loads(request.input_text)
        self.assertIn("new_case", payload["rules"])
        self.assertIn("model segment's sentence", payload["rules"]["new_case"])


class NewCaseGateTest(unittest.TestCase):
    """The deterministic gate refuses the solved case and admits a varied one."""

    def test_a_check_that_reuses_the_model_sentence_is_refused(self) -> None:
        lesson = party_size_lesson(REUSED_PROMPT)
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_check_states_a_new_case(learner_page(lesson), lesson)
        reason = caught.exception.reasons[0]
        self.assertTrue(reason.startswith("lesson.check.model_sentence_reuse:"), reason)
        self.assertIn("check prompt", reason)

    def test_a_prompt_that_varies_the_case_still_passes(self) -> None:
        lesson = party_size_lesson(NEW_CASE_PROMPT)
        gen.assert_check_states_a_new_case(learner_page(lesson), lesson)  # no exception

    def test_the_older_gates_admitted_the_reused_case_before_this_rule(self) -> None:
        """The measured gap: the key is absent from the prompt, so neither existing gate fired.

        The narrative scan never reads the prompt, and the check-payload scan only refuses the key
        itself — which the reused half of the sentence does not contain. That is why the defect was
        unrefused at HEAD and why the refusal must name the sentence, not the key.
        """
        lesson = party_size_lesson(REUSED_PROMPT)
        page = learner_page(lesson)
        gen.assert_no_answer_leak(page, lesson)  # no exception
        gen.assert_check_payload_does_not_announce_answer(lesson)  # no exception
        self.assertNotIn("二人です", lesson["check"]["stimulus"]["prompt"])

    def test_an_accepted_answer_that_reproduces_the_model_sentence_is_refused(self) -> None:
        lesson = party_size_lesson(NEW_CASE_PROMPT)
        lesson["check"]["accepted_answers"] = ["二人です", MODEL_BODY]
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_check_states_a_new_case(learner_page(lesson), lesson)
        self.assertIn("accepted answer", caught.exception.reasons[0])

    def test_learner_instructions_that_reproduce_the_model_sentence_are_refused(self) -> None:
        lesson = party_size_lesson(NEW_CASE_PROMPT)
        lesson["check"]["learner_instructions"] = (
            "Read it once more: " + MODEL_BODY
        )
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_check_states_a_new_case(learner_page(lesson), lesson)
        self.assertIn("learner instructions", caught.exception.reasons[0])

    def test_repeating_the_target_form_itself_is_not_reuse(self) -> None:
        """The form is what the check is *for*: only the frame beyond it is refused."""
        lesson = party_size_lesson("How many people are coming? Answer 二人です.")
        gen.assert_check_states_a_new_case(learner_page(lesson), lesson)  # no exception

    def test_a_lesson_with_no_model_segment_is_out_of_scope(self) -> None:
        lesson = party_size_lesson(REUSED_PROMPT)
        lesson["segments"][0]["kind"] = "explain"
        gen.assert_check_states_a_new_case(learner_page(lesson), lesson)  # no exception

    def test_a_short_frame_shares_topic_words_without_being_the_sentence(self) -> None:
        # The model's frame is a four-word run at most once it leaves the target out; a new case
        # that keeps the function ("how many people") is still a new case.
        lesson = party_size_lesson("How many people are coming to your party?")
        gen.assert_check_states_a_new_case(learner_page(lesson), lesson)  # no exception


class AuthoringPathParksTheReusedCaseTest(GenerationTestBase):
    """Through the real lesson job: the reused case parks before the validator is asked."""

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
            {"job_id": "job-up12-new-case", "kind": "plan",
             "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=32),
        )

    def _authoring(self, prompt: str):
        def build(request: gen.LLMRequest):
            payload = json.loads(request.input_text)
            lesson = party_size_lesson(prompt)
            ids = source_ids_from(request)
            if ids:
                lesson = json.loads(
                    json.dumps(lesson, ensure_ascii=False).replace("SRC_ALPHA", ids[0])
                )
                lesson["sources"] = list(ids)
            lesson["section_title"] = (
                (payload.get("section") or {}).get("title") or lesson["section_title"]
            )
            check_for_objective(lesson, payload.get("objective") or {})
            # The migration rewrites a quiz into the check shape the objective's evidence target
            # permits, so the draft under test is re-stated afterwards: same target form, and the
            # case is the one the model segment already solved.
            lesson["check"]["stimulus"]["prompt"] = prompt
            lesson["check"]["reference_answer"] = "二人です"
            lesson["check"]["accepted_answers"] = ["二人です"]
            lesson["check"]["accepted_alternatives"] = [["futari desu"]]
            return response(lesson, model="fake-author")

        return build

    def test_the_reused_case_parks_with_the_named_reason(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(
            validation_from_fixture(), generate=self._authoring(REUSED_PROMPT)
        )
        result = self.run_lessons(plan_result, llm)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
        reasons = " ".join(result["lessons"][0]["rejection_reasons"])
        self.assertIn("lesson.check.model_sentence_reuse", reasons)

    def test_a_varied_case_still_reaches_the_validator(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(
            validation_from_fixture(), generate=self._authoring(NEW_CASE_PROMPT)
        )
        result = self.run_lessons(plan_result, llm)
        self.assertGreaterEqual(llm.calls_for("coursebook.lesson.validate"), 1)
        self.assertTrue(any(item["state"] == "validated" for item in result["lessons"]))


if __name__ == "__main__":
    unittest.main()
