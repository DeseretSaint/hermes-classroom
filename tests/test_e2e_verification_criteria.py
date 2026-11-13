"""A verification checklist is not judged on weighted-rubric earnability (E2E review A1).

Measured 2026-11-13, live one-off ("poach an egg"): the independent validator refused the lesson on
attempt 3 with ``answer_key.rubric[2]: The 'Safety stop' criterion (weight 0.25) ... the check's
seven items contain no such step``. The learner-facing seven-item checklist was fine. The
confirmation lane that grades this shape reads the items and ``rubric.pass_rule`` only; the weighted
criteria are never scored, so the validator was enforcing a property the grader does not implement —
and the course ended with ``servable_objectives: []``.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen


VERIFICATION_CHECK = {
    "kind": "verification",
    "stimulus": {"format": "verification", "items": [{"id": "item_1", "label": "Water simmered."}]},
    "rubric": {"pass_rule": "all", "criteria": [{"label": "Safety stop", "weight": 0.25}]},
}

QUIZ_CHECK = {
    "kind": "quiz",
    "stimulus": {"format": "selection", "choices": [{"id": "a", "label": "3-5 minutes"}]},
    "rubric": {"pass_rule": "all", "criteria": [{"label": "Correct window", "weight": 1.0}]},
}


class VerificationCriteriaTest(unittest.TestCase):
    def test_rubric_consistency_is_not_asked_of_a_verification_check(self) -> None:
        asked = gen.lesson_validation_criteria(recipe="one_off", check=VERIFICATION_CHECK)
        self.assertNotIn("rubric_consistency", asked)
        # The rest of the set is untouched: a checklist still owes alignment and leakage.
        self.assertIn("objective_alignment", asked)
        self.assertIn("answer_leakage", asked)

    def test_a_quiz_still_owes_rubric_consistency(self) -> None:
        asked = gen.lesson_validation_criteria(recipe="casual", check=QUIZ_CHECK)
        self.assertIn("rubric_consistency", asked)

    def test_an_absent_check_keeps_the_full_set(self) -> None:
        asked = gen.lesson_validation_criteria(recipe="casual", check=None)
        self.assertIn("rubric_consistency", asked)

    def test_the_waiver_records_why_and_names_the_item_obligation(self) -> None:
        waivers = gen.lesson_validation_waivers(recipe="one_off", check=VERIFICATION_CHECK)
        reason = waivers["rubric_consistency"]
        self.assertIn("confirmation lane", reason)
        self.assertIn("checklist item", reason)

    def test_an_adult_recipe_carries_both_waivers(self) -> None:
        waivers = gen.lesson_validation_waivers(recipe="one_off", check=VERIFICATION_CHECK)
        self.assertIn("hazard_age_appropriateness", waivers)
        self.assertIn("rubric_consistency", waivers)

    def test_a_child_facing_recipe_keeps_the_hazard_check(self) -> None:
        waivers = gen.lesson_validation_waivers(recipe="parent", check=VERIFICATION_CHECK)
        self.assertNotIn("hazard_age_appropriateness", waivers)
        self.assertIn("rubric_consistency", waivers)

    def test_the_lesson_validation_request_no_longer_asks_it(self) -> None:
        # The instruction text is what the validator answers against; a criterion absent from it
        # cannot come back as a refusal and cannot be counted missing.
        request = gen.build_lesson_validation_request(
            plan={},
            section={"objective_refs": [1]},
            objective=None,
            lesson={
                "segments": [{"kind": "model", "heading": "h", "body": "b" * 200}],
                "check": VERIFICATION_CHECK,
            },
            page={"segments": []},
            recipe="one_off",
            dials={},
            locale=None,
            sources=[],
        )
        asked = request.instructions.split("Check every one of these criteria and return one "
                                             "entry per criterion: ", 1)[1].split(".", 1)[0]
        self.assertNotIn("rubric_consistency", asked)
        self.assertIn("Not asked of this artifact", request.instructions)


if __name__ == "__main__":
    unittest.main()
