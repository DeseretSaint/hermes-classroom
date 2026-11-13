"""The three deterministic assessment rules the validator was paying for (E2E A2/A3/A4).

The adversarial end-to-end review of 2026-11-12 measured three defects in which an expensive
model pass decided something code could have decided:

* **A2** — a rubric criterion nothing in a verification checklist can earn was refused by the
  validator on all three attempts (~39 k output tokens, no servable lesson);
* **A3** — the answer-leak scan was exact containment, so "simmer gently" in a page did not
  register against a key of "gentle simmer";
* **A4** — nothing refused a wall: the floor was 120 characters, the ceiling did not exist.

These cases pin the rules on the real authoring path. The end-to-end cases run the real migrated
database through the real generation pipeline with a scripted provider, so "before the validator
is called" is observed as provider-call order, not asserted from prose.
"""

from __future__ import annotations

import copy
import unittest

from coursebook import generation as gen
from coursebook import rubrics, wording

from tests.test_check_items_authoring import ChecklistAuthoringCase, one_off_lesson
from tests.test_generation import fixture

#: The rubric band no brake-pad checklist item covers. Its obligation words (lower / heat /
#: withhold / egg / boil) appear nowhere in the three item labels, which is exactly the measured
#: A1 failure: the validator said "learners cannot earn that band from the check as posed".
UNCOVERED_BAND = {
    "criterion": "safety stop",
    "weight": 0.25,
    "description": "Lowers the heat or withholds the egg at a rolling boil",
}

#: The repaired criterion: it names the checklist's own fastener, so an item covers it.
COVERED_BAND = {
    "criterion": "safety stop",
    "weight": 0.25,
    "description": "Stops if the fastener will not turn by hand",
}


def with_third_criterion(lesson: dict, criterion: dict) -> dict:
    document = copy.deepcopy(lesson)
    document["check"]["rubric"][2] = dict(criterion)
    return document


def quiz_lesson() -> dict:
    """A free-response (quiz) lesson: no item labels, so A2 never judges it."""
    return {
        "check": {
            "kind": "quiz",
            "evidence_target": "comprehension",
            "rubric": [
                {"criterion": "accurate claim", "weight": 1.0,
                 "description": "States a claim that matches the lesson."},
                {"criterion": "mechanism", "weight": 1.0,
                 "description": "Explains how the process works."},
                {"criterion": "example", "weight": 1.0,
                 "description": "Gives an example from the lesson."},
            ],
            "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
        },
        "media": [],
    }


def teaching_lesson() -> dict:
    """A lesson that clears the H-195 floor, for the A4 ceiling cases."""
    return {
        "section_title": "A section",
        "segments": [
            {"kind": "model", "heading": "Name the two parts", "body": "A" * 200,
             "short": "Name the two parts."},
            {"kind": "guided", "heading": "Try it with one example", "body": "B" * 260,
             "short": "Try it with one example."},
        ],
        "worked_example": {
            "prompt": "Do it once",
            "steps": ["First step", "Second step"],
            "answer": "the answer",
            "short": "Do it once.",
        },
        "learner_explanation": "You will do the thing twice.",
    }


def leak_page(*, presenting_kind: str = "model", explain_body: str | None = None) -> dict:
    """A page whose model segment may present "gentle simmer"; one other segment is the surface."""
    return {
        "section_title": "Poaching an egg",
        "segments": [
            {
                "kind": presenting_kind,
                "heading": "Hold the water at a gentle simmer",
                "body": "Bring the water to a gentle simmer, not a rolling boil.",
                "short": "A gentle simmer, not a rolling boil.",
            },
            {
                "kind": "explain",
                "heading": "Watch the white set",
                "body": explain_body if explain_body is not None else "The white sets from the outside in.",
                "short": "The white sets from the outside in.",
            },
        ],
        "worked_example": {
            "prompt": "The water is ready. What is the next move?",
            "steps": ["Crack the egg into a cup", "Slide it into the water"],
            "answer": "Slide the egg into the water.",
            "short": "Crack, then slide.",
        },
        "learner_explanation": "Keep the water calm and watch the white.",
        "media": [],
    }


def leak_lesson() -> dict:
    return {
        "check": {
            "kind": "quiz",
            "reference_answer": "gentle simmer",
            "accepted_answers": [],
            "accepted_alternatives": [],
            "rubric": [],
        }
    }


class WordingTest(unittest.TestCase):
    """The one tokenizer both word rules use, pinned at its boundaries."""

    def test_inflections_fold_to_one_key(self) -> None:
        self.assertEqual(wording.content_words("Simmered"), wording.content_words("simmer"))
        self.assertEqual(wording.content_words("steps"), wording.content_words("step"))

    def test_stopwords_do_not_count_as_content(self) -> None:
        self.assertEqual(wording.content_words("the water is at"), wording.content_words("water"))

    def test_a_reordered_pair_in_one_clause_is_a_paraphrase(self) -> None:
        self.assertTrue(wording.paraphrases("gentle simmer", ["Simmer gently until set."]))

    def test_a_pair_split_across_sentences_is_not(self) -> None:
        self.assertFalse(
            wording.paraphrases(
                "gentle simmer", ["Simmer the onions for ten minutes. Add a gentle spice."]
            )
        )

    def test_a_single_word_secret_is_left_to_containment(self) -> None:
        self.assertFalse(wording.paraphrases("simmer", ["Simmer gently."]))


class RubricCoverageTest(unittest.TestCase):
    """A2: a rubric criterion no checklist item can earn is refused before validation."""

    def test_a_covered_rubric_has_no_coverage_problem(self) -> None:
        lesson = fixture("lesson_one_off")
        check = lesson["check"]
        self.assertEqual(
            rubrics.rubric_item_coverage_problems(check["rubric"], check["stimulus"]["items"]),
            [],
        )

    def test_an_uncovered_band_names_the_criterion_and_the_repair(self) -> None:
        lesson = fixture("lesson_one_off")
        check = lesson["check"]
        problems = rubrics.rubric_item_coverage_problems(
            [dict(UNCOVERED_BAND)], check["stimulus"]["items"]
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("not earnable", problems[0])
        self.assertIn("check.stimulus.items", problems[0])

    def test_an_empty_item_list_is_not_this_rules_job(self) -> None:
        self.assertEqual(rubrics.rubric_item_coverage_problems([dict(UNCOVERED_BAND)], []), [])

    def test_enforce_lesson_rules_raises_before_any_page_is_validated(self) -> None:
        plan = fixture("plan_one_off")
        lesson = with_third_criterion(fixture("lesson_one_off"), UNCOVERED_BAND)
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_lesson_rules(
                lesson,
                section=plan["sections"][0],
                objective=plan["objectives"][0],
                recipe="committed",
                locale=None,
                dials={},
            )
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("not earnable from the check's items", reasons)

    def test_a_free_response_check_is_not_judged_for_item_coverage(self) -> None:
        # No items, so the rule cannot say anything; the rubric's own shape rules still apply.
        gen.enforce_lesson_rules(
            quiz_lesson(),
            section={"lesson_intent": "Explain why water evaporates."},
            objective={"evidence_target": "comprehension"},
            recipe="casual",
            locale=None,
            dials={},
        )


class RubricCoveragePipelineTest(ChecklistAuthoringCase):
    """A2 on the real authoring path: gate → repair, validator only after the repair."""

    def test_the_uncovered_band_is_refused_and_the_validator_is_never_called(self) -> None:
        lesson = with_third_criterion(one_off_lesson(), UNCOVERED_BAND)
        _plan, _enrollment, result, llm = self.author_one_off(lesson)

        self.assertTrue(result["lessons"])
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "needs_review")
            self.assertFalse(summary["check_enabled"])
            reasons = " ".join(summary["rejection_reasons"])
            self.assertIn("not earnable from the check's items", reasons)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)

    def test_the_repaired_draft_reaches_the_validator(self) -> None:
        calls = {"count": 0}

        def drafts(_request):
            calls["count"] += 1
            criterion = UNCOVERED_BAND if calls["count"] == 1 else COVERED_BAND
            return with_third_criterion(one_off_lesson(), criterion)

        _plan, _enrollment, result, llm = self.author_one_off(drafts)

        purposes = [request.purpose for request in llm.requests]
        generates = [i for i, purpose in enumerate(purposes) if purpose == "coursebook.lesson.generate"]
        validates = [i for i, purpose in enumerate(purposes) if purpose == "coursebook.lesson.validate"]
        self.assertGreaterEqual(len(generates), 2)
        self.assertTrue(validates, "the repaired draft was never validated")
        self.assertLess(generates[1], validates[0], "the validator ran before the repair")
        for summary in result["lessons"]:
            self.assertNotEqual(summary["state"], "needs_review")


class ParaphraseLeakTest(unittest.TestCase):
    """A3: containment keeps its exact cases; the token-set scan catches the reordered restatement."""

    def test_simmer_gently_in_an_explain_segment_against_gentle_simmer_is_refused(self) -> None:
        page = leak_page(explain_body="Simmer gently until the white is just set.")
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_no_answer_leak(page, leak_lesson())
        self.assertIn("paraphrases", str(caught.exception))

    def test_a_model_segment_may_present_the_form_it_checks(self) -> None:
        page = leak_page(presenting_kind="model")
        gen.assert_no_answer_leak(page, leak_lesson())  # no violation

    def test_the_same_restatement_in_a_non_model_segment_is_refused(self) -> None:
        page = leak_page()
        page["segments"][1]["body"] = "Then let it simmer gently for three minutes."
        with self.assertRaises(gen._RuleViolation):
            gen.assert_no_answer_leak(page, leak_lesson())

    def test_a_distant_pair_in_one_sentence_is_not_a_leak(self) -> None:
        page = leak_page(
            explain_body="Simmer the onions for ten minutes, then add a gentle spice blend."
        )
        gen.assert_no_answer_leak(page, leak_lesson())

    def test_selection_choices_stay_exempt(self) -> None:
        lesson = leak_lesson()
        lesson["check"].update(
            {"kind": "quiz", "stimulus": {"prompt": "Which step comes next?",
                                          "format": "selection",
                                          "choices": ["simmer gently", "boil hard"]}}
        )
        gen.assert_no_answer_leak(leak_page(), lesson)
        gen.assert_check_payload_does_not_announce_answer(lesson)

    def test_the_check_prompt_is_scanned_for_a_paraphrase_too(self) -> None:
        lesson = leak_lesson()
        lesson["check"]["stimulus"] = {
            "prompt": "Should the water simmer gently or boil hard?",
            "format": "selection",
            "choices": ["simmer gently", "boil hard"],
        }
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_check_payload_does_not_announce_answer(lesson)
        self.assertIn("paraphrases", str(caught.exception))

    def test_a_media_spec_may_not_paraphrase_the_key(self) -> None:
        page = leak_page()
        page["media"] = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "Shows the water",
                "spec": "A cutaway of a pot where the water simmers gently.",
                "text_equivalent": "A pot of water on a stove.",
            }
        ]
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.assert_no_answer_leak(page, leak_lesson())
        self.assertIn("media spec paraphrases", str(caught.exception))


class SegmentCeilingTest(unittest.TestCase):
    """A4: a wall under one heading is refused, with the split named in the repair."""

    def test_the_ceiling_is_below_the_schema_body_bound(self) -> None:
        body_bound = gen.LESSON_SCHEMA["properties"]["segments"]["items"]["properties"]["body"]["maxLength"]
        self.assertEqual(gen.MAX_SINGLE_SEGMENT_CHARS, 1200)
        self.assertLess(gen.MAX_SINGLE_SEGMENT_CHARS, body_bound)

    def test_a_2500_character_segment_is_refused_with_a_split_hint(self) -> None:
        lesson = teaching_lesson()
        lesson["segments"][1]["body"] = "B" * 2500
        problems = gen.teaching_quality_problems(lesson)
        ceiling = [problem for problem in problems if "ceiling" in problem]
        self.assertEqual(len(ceiling), 1, problems)
        self.assertIn("split it into two segments", ceiling[0])
        self.assertIn("2500 characters", ceiling[0])

    def test_a_body_at_the_ceiling_is_not_refused(self) -> None:
        lesson = teaching_lesson()
        lesson["segments"][1]["body"] = "B" * gen.MAX_SINGLE_SEGMENT_CHARS
        problems = gen.teaching_quality_problems(lesson)
        self.assertFalse([problem for problem in problems if "ceiling" in problem], problems)

    def test_the_authored_lesson_fixtures_clear_the_ceiling(self) -> None:
        for name in ("lesson_ja", "lesson_fr", "lesson_one_off", "lesson_parent_safe"):
            with self.subTest(fixture=name):
                problems = gen.teaching_quality_problems(fixture(name))
                self.assertFalse([problem for problem in problems if "ceiling" in problem], problems)


if __name__ == "__main__":
    unittest.main()
