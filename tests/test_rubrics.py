"""Registry and validator tests for rubric angles (``docs/VISUAL_MEDIA_PLAN.md`` §4, M1-P2).

The registry must select a scoring guide by construct, and the validator must reject the four
failure modes it can prove mechanically: an off-profile construct, a generic mental-state
criterion, a restated criterion, and a rubric outside the 3-6 bound. Every positive case is
proved with the profile's own observable aspects; every negative case names the rule it breaks.
"""

from __future__ import annotations

import copy
import unittest

from coursebook import generation as gen
from coursebook import packs, policy, rubrics


def concrete(profile: str) -> list[str]:
    """The registry's own aspects as scored sentences; used for the positive cases."""
    return [criterion.observation for criterion in rubrics.get_profile(profile).criteria]


class RegistryTest(unittest.TestCase):
    def test_registry_is_consistent_with_the_policy_vocabulary(self) -> None:
        self.assertEqual(rubrics.registry_problems(), [])
        self.assertEqual(tuple(rubrics.RUBRICS), tuple(policy.RUBRIC_PROFILES))

    def test_every_profile_has_three_to_six_distinct_observable_criteria(self) -> None:
        for name, profile in rubrics.RUBRICS.items():
            with self.subTest(profile=name):
                self.assertGreaterEqual(len(profile.criteria), 3)
                self.assertLessEqual(len(profile.criteria), 6)
                labels = [criterion.label for criterion in profile.criteria]
                self.assertEqual(len(labels), len(set(labels)))
                self.assertNotIn("understands", " ".join(labels).lower())
                self.assertTrue(all(criterion.observation.strip() for criterion in profile.criteria))

    def test_profile_labels_are_the_plan_wording_not_a_second_copy(self) -> None:
        for name, profile in rubrics.RUBRICS.items():
            with self.subTest(profile=name):
                self.assertEqual(profile.labels, policy.RUBRIC_PROFILE_CRITERIA[name])

    def test_every_profile_declares_valid_evidence_targets(self) -> None:
        for name, profile in rubrics.RUBRICS.items():
            with self.subTest(profile=name):
                self.assertTrue(profile.evidence_targets)
                self.assertLessEqual(profile.evidence_targets, set(policy.EVIDENCE_TARGETS))

    def test_every_target_has_a_default_profile_that_serves_it(self) -> None:
        for target in policy.EVIDENCE_TARGETS:
            with self.subTest(target=target):
                name = rubrics.default_profile_for(target)
                self.assertIn(name, rubrics.RUBRICS)
                self.assertTrue(rubrics.serves(name, target))

    def test_registry_projection_is_json_safe_and_names_no_answer(self) -> None:
        for profile in rubrics.RUBRICS.values():
            projection = profile.to_dict()
            self.assertEqual(projection["profile"], profile.name)
            self.assertEqual(len(profile.criteria), len(projection["criteria"]))
            body = str(projection).lower()
            for forbidden in ("reference_answer", "accepted_answer", "mastery"):
                self.assertNotIn(forbidden, body)


class PositiveValidationTest(unittest.TestCase):
    def test_each_profile_accepts_its_own_criteria_for_a_target_it_serves(self) -> None:
        for name, profile in rubrics.RUBRICS.items():
            target = sorted(profile.evidence_targets)[0]
            with self.subTest(profile=name, target=target):
                self.assertEqual(rubrics.validate_rubric(name, concrete(name), target), [])

    def test_generated_rubric_records_are_accepted(self) -> None:
        criteria = [
            {"criterion": "claim", "weight": 1.0, "description": "States the claim the model makes."},
            {"criterion": "mechanism", "weight": 1.0, "description": "Explains how the process works."},
            {"criterion": "example", "weight": 1.0, "description": "Gives an example from the lesson."},
        ]
        self.assertEqual(
            rubrics.validate_rubric("concept_explanation", criteria, "comprehension"), []
        )

    def test_template_returns_the_registry_aspects(self) -> None:
        template = rubrics.rubric_template("procedural")
        self.assertEqual([item["criterion"] for item in template], list(rubrics.RUBRICS["procedural"].labels))
        self.assertTrue(all(item["observation"] for item in template))


class NegativeValidationTest(unittest.TestCase):
    def assertProblem(self, problems: list[str], fragment: str) -> None:
        self.assertTrue(problems, "expected the rubric to be rejected")
        self.assertTrue(
            any(fragment in problem for problem in problems),
            f"expected {fragment!r} in {problems!r}",
        )

    def test_off_profile_construct_is_rejected(self) -> None:
        # Retrieval criteria cannot score a production target.
        problems = rubrics.validate_rubric("recall_accuracy", concrete("recall_accuracy"), "production")
        self.assertProblem(problems, "does not score the objective's declared evidence target")

    def test_duplicated_criterion_is_rejected_after_normalisation(self) -> None:
        criteria = ["Answers 150 ml", "answers 150 ML.", "Refers to the three marks"]
        problems = rubrics.validate_rubric("recall_accuracy", criteria, "recall")
        self.assertProblem(problems, "restate the same criterion")

    def test_generic_criterion_is_rejected(self) -> None:
        criteria = ["Understands the water cycle", "Explains how evaporation works", "Gives an example"]
        problems = rubrics.validate_rubric("concept_explanation", criteria, "comprehension")
        self.assertProblem(problems, "mental-state claim")

    def test_a_criterion_that_only_asserts_understanding_is_rejected(self) -> None:
        criteria = ["Learner understands the water cycle", "Explains how evaporation works", "Gives an example"]
        problems = rubrics.validate_rubric("concept_explanation", criteria, "comprehension")
        self.assertProblem(problems, "mental-state claim")

    def test_below_the_minimum_is_rejected(self) -> None:
        problems = rubrics.validate_rubric("recall_accuracy", ["Answers 150 ml"], "recall")
        self.assertProblem(problems, "rubric criteria; minimum is 3")

    def test_above_the_ceiling_is_rejected(self) -> None:
        criteria = [f"Answers item {index} correctly" for index in range(1, 8)]
        problems = rubrics.validate_rubric("recall_accuracy", criteria, "recall")
        self.assertProblem(problems, "at most 6")

    def test_unknown_profile_and_target_are_rejected(self) -> None:
        self.assertProblem(rubrics.validate_rubric("vibes", concrete("recall_accuracy"), "recall"), "unknown rubric profile")
        self.assertProblem(rubrics.validate_rubric("recall_accuracy", concrete("recall_accuracy"), "mastery"), "unknown evidence target")

    def test_empty_criterion_is_rejected(self) -> None:
        problems = rubrics.validate_rubric("recall_accuracy", ["", "Answers 150 ml", "Counts the marks"], "recall")
        self.assertProblem(problems, "empty")

    def test_assert_valid_rubric_raises_with_every_problem(self) -> None:
        with self.assertRaises(rubrics.RubricRejected) as caught:
            rubrics.assert_valid_rubric("recall_accuracy", ["Understands it"], "production")
        message = str(caught.exception)
        self.assertIn("mental-state claim", message)
        self.assertIn("minimum is 3", message)


class ProfileResolutionTest(unittest.TestCase):
    def test_a_compatible_construct_is_kept(self) -> None:
        self.assertEqual(rubrics.resolve_profile("procedural", "procedure"), "procedural")
        self.assertEqual(rubrics.resolve_profile("observation", "recall"), "observation")

    def test_an_incompatible_construct_falls_back_to_the_target_default(self) -> None:
        self.assertEqual(rubrics.resolve_profile("procedural", "comprehension"), "concept_explanation")
        self.assertEqual(rubrics.resolve_profile(None, "production"), "language_production")

    def test_language_production_selects_the_language_angle(self) -> None:
        profile = rubrics.profile_for_lesson(
            recipe="committed",
            evidence_target="production",
            lesson_intent="Say the greeting aloud with the right register.",
            locale="ja-JP",
        )
        self.assertEqual(profile, "language_production")

    def test_parent_recipe_selects_observation(self) -> None:
        profile = rubrics.profile_for_lesson(
            recipe="parent",
            evidence_target="comprehension",
            lesson_intent="Watch your child measure the water.",
        )
        self.assertEqual(profile, "observation")

    def test_a_one_off_brief_never_gets_a_quiz_angle(self) -> None:
        # One-off briefs are verified, so the advisory procedural construct cannot score a
        # comprehension target and the declared target's default is used instead.
        profile = rubrics.profile_for_lesson(
            recipe="one_off",
            evidence_target="comprehension",
            lesson_intent="Write a one-page refund policy brief for the front desk.",
        )
        self.assertEqual(profile, "concept_explanation")


class PackIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        self.manifest = packs.load_manifest(
            root / "bundled" / "packs" / "parent-measurement-practice" / "pack.json"
        )

    def test_bundled_pack_rubrics_pass_the_registry_rules(self) -> None:
        packs.validate_minima(self.manifest)

    def test_a_generic_pack_criterion_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][0]["checks"][0]["rubric"][0] = "Understands measuring"
        with self.assertRaises(packs.PackRejected) as caught:
            packs.validate_minima(manifest)
        self.assertIn("mental-state claim", str(caught.exception))

    def test_a_duplicated_pack_criterion_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        rubric = manifest["objectives"][0]["checks"][0]["rubric"]
        rubric[1] = rubric[0]
        with self.assertRaises(packs.PackRejected) as caught:
            packs.validate_minima(manifest)
        self.assertIn("restate the same criterion", str(caught.exception))


class GenerationIntegrationTest(unittest.TestCase):
    def lesson(self, rubric: list[dict]) -> dict:
        return {
            "check": {
                "kind": "quiz",
                "evidence_target": "comprehension",
                "rubric": rubric,
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            },
            "media": [],
        }

    def record(self, description: str) -> dict:
        return {"criterion": "aspect", "weight": 1.0, "description": description}

    def test_a_valid_lesson_rubric_passes_the_rule_path(self) -> None:
        lesson = self.lesson(
            [
                self.record("States the claim the lesson makes about evaporation."),
                self.record("Explains how the process works."),
                self.record("Gives an example from the lesson."),
            ]
        )
        gen.enforce_lesson_rules(
            lesson,
            section={"lesson_intent": "Explain why water evaporates."},
            objective={"evidence_target": "comprehension"},
            recipe="casual",
            locale=None,
            dials={},
        )

    def test_a_generic_lesson_criterion_is_rejected(self) -> None:
        lesson = self.lesson(
            [
                self.record("Understands evaporation."),
                self.record("Explains how the process works."),
                self.record("Gives an example from the lesson."),
            ]
        )
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_lesson_rules(
                lesson,
                section={"lesson_intent": "Explain why water evaporates."},
                objective={"evidence_target": "comprehension"},
                recipe="casual",
                locale=None,
                dials={},
            )
        self.assertIn("mental-state claim", " ".join(caught.exception.reasons))

    def test_a_duplicated_lesson_criterion_is_rejected(self) -> None:
        lesson = self.lesson(
            [
                self.record("States the claim the lesson makes about evaporation."),
                self.record("states the claim the lesson makes about evaporation"),
                self.record("Gives an example from the lesson."),
            ]
        )
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_lesson_rules(
                lesson,
                section={"lesson_intent": "Explain why water evaporates."},
                objective={"evidence_target": "comprehension"},
                recipe="casual",
                locale=None,
                dials={},
            )
        self.assertIn("restate the same criterion", " ".join(caught.exception.reasons))

    def test_the_lesson_prompt_names_the_selected_profile(self) -> None:
        request = gen.build_lesson_request(
            plan={},
            section={"source_ids": []},
            objective=None,
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
            rubric_profile="recall_accuracy",
        )
        self.assertIn("Rubric profile: recall_accuracy", request.instructions)
        self.assertIn("correct answer", request.instructions)


if __name__ == "__main__":
    unittest.main()
