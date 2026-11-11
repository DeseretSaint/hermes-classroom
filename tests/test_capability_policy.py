"""M1-P1: the lesson capability policy matrix.

The policy is the gate that stops media and rubric templates being generated before the harness
knows what kind of lesson this is. These tests are the contract:

* every matrix row asserts the positive and the negative case;
* a media decision must name the construct that justified it (or the constructs that were absent);
* a locale never implies audio, a recipe never implies a quiz, and an AI illustration is never
  required evidence;
* the module imports nothing that can reach a database or a network.

Run: ``python3 -m unittest tests.test_capability_policy``
"""

from __future__ import annotations

import ast
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from coursebook import generation, packs, policy
from coursebook import curriculum

POLICY_SOURCE = Path(policy.__file__)


def plan(**overrides: object) -> policy.LessonCapabilityPlan:
    base: dict[str, object] = {
        "recipe": "committed",
        "evidence_target": "comprehension",
        "lesson_intent": "Explain the idea and work one example.",
        "locale": None,
        "level": None,
        "subject_domain": None,
    }
    base.update(overrides)
    return policy.plan_lesson_capability(**base)  # type: ignore[arg-type]


#: The representative matrix from ``docs/VISUAL_MEDIA_PLAN.md`` §4. Every row is a pair: a case
#: where the construct is present and a case where it is absent, so the policy must make both the
#: positive and the negative decision for the reason, not for a preference.
MATRIX: tuple[dict[str, object], ...] = (
    {
        # Positive: the torque sequence is the evidence, so a deterministic schematic is required.
        "case": "head gasket procedure",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "procedure",
            "subject_domain": "technical_procedure",
            "lesson_intent": (
                "Replace the head gasket: follow the torque sequence, part orientation and the "
                "safety stop condition."
            ),
        },
        "expect": {
            "image": "required",
            "image_role": "schematic",
            "audio": "none",
            "audio_role": None,
            "check_angle": "procedure",
            "rubric_profile": "procedural",
        },
        "reason_terms": ("torque sequence",),
    },
    {
        # Negative: describing what a gasket does names no procedure construct, so no media.
        "case": "head gasket explanation without a sequence",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "comprehension",
            "subject_domain": "technical_procedure",
            "lesson_intent": "Describe what a head gasket does and why it fails in general terms.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "comprehension",
            "rubric_profile": "concept_explanation",
        },
        "reason_terms": ("no sequence",),
    },
    {
        # Positive: a spoken greeting is a production construct, so a reference recording is required.
        "case": "japanese greeting",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "production",
            "subject_domain": "language",
            "locale": "ja-JP",
            "level": "L0",
            "lesson_intent": (
                "Greet a coworker and introduce yourself with the right register, saying the "
                "phrase aloud."
            ),
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "required",
            "audio_role": "pronunciation_reference",
            "check_angle": "production",
            "rubric_profile": "language_production",
        },
        "reason_terms": ("spoken construct",),
    },
    {
        # Negative: writing a greeting card is production, but it is not an oral construct.
        "case": "japanese written greeting",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "production",
            "subject_domain": "language",
            "locale": "ja-JP",
            "level": "L0",
            "lesson_intent": "Write a short greeting card in Japanese with the right register.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "production",
            "rubric_profile": "language_production",
        },
        "reason_terms": ("reading or writing",),
    },
    {
        # Negative: reading kana is not pronunciation; a locale alone never buys narration.
        "case": "japanese reading-only lesson",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "comprehension",
            "subject_domain": "language",
            "locale": "ja-JP",
            "level": "L0",
            "lesson_intent": (
                "Read the hiragana row and recognise each kana in short words; no speaking."
            ),
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "comprehension",
            "rubric_profile": "concept_explanation",
        },
        "reason_terms": ("reading or writing",),
    },
    {
        # Positive counterweight: the same reading objective becomes oral when the intent says so.
        "case": "japanese read-aloud lesson",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "comprehension",
            "subject_domain": "language",
            "locale": "ja-JP",
            "level": "L0",
            "lesson_intent": "Read each hiragana kana aloud so the learner hears the rhythm.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "required",
            "audio_role": "pronunciation_reference",
            "check_angle": "comprehension",
            "rubric_profile": "language_production",
        },
        "reason_terms": ("spoken construct",),
    },
    {
        # Negative: a derivation is symbolic; an AI illustration of it is not evidence.
        "case": "algebra derivation",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "comprehension",
            "subject_domain": "mathematics",
            "lesson_intent": "Derive the quadratic formula by completing the square.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "comprehension",
            "rubric_profile": "concept_explanation",
        },
        "reason_terms": ("symbolic",),
    },
    {
        # Positive: a named graph deserves a deterministic schematic, never an illustration.
        "case": "algebra graph sketch",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "comprehension",
            "subject_domain": "mathematics",
            "lesson_intent": (
                "Sketch the graph of a quadratic and label the vertex and the axis of symmetry."
            ),
        },
        "expect": {
            "image": "optional",
            "image_role": "schematic",
            "audio": "none",
            "audio_role": None,
            "check_angle": "comprehension",
            "rubric_profile": "concept_explanation",
        },
        "reason_terms": ("graph",),
    },
    {
        # Positive: the source image is the evidence, so it is required and cited.
        "case": "history source analysis",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "transfer",
            "subject_domain": "history",
            "lesson_intent": (
                "Analyse the 1942 recruitment poster: state the claim, weigh the evidence, check "
                "its provenance and handle a contradiction."
            ),
        },
        "expect": {
            "image": "required",
            "image_role": "sourced_reference",
            "audio": "none",
            "audio_role": None,
            "check_angle": "transfer",
            "rubric_profile": "source_analysis",
        },
        "reason_terms": ("poster",),
    },
    {
        # Negative: a textual source analysis needs no image, but keeps the source rubric.
        "case": "history textual source analysis",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "transfer",
            "subject_domain": "history",
            "lesson_intent": (
                "Analyse the text of the 1942 conscription act: state the claim, weigh the "
                "evidence and check its provenance."
            ),
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "transfer",
            "rubric_profile": "source_analysis",
        },
        "reason_terms": ("no source image",),
    },
    {
        # Positive: a one-off wiring brief is verified by a checklist anchored on a schematic.
        "case": "wiring brief",
        "kwargs": {
            "recipe": "one_off",
            "evidence_target": "procedure",
            "subject_domain": "technical_procedure",
            "lesson_intent": (
                "Wire the workshop outlet circuit and verify the wiring order against the label."
            ),
        },
        "expect": {
            "image": "required",
            "image_role": "schematic",
            "audio": "none",
            "audio_role": None,
            "check_angle": "verification",
            "rubric_profile": "procedural",
        },
        "reason_terms": ("wire",),
    },
    {
        # Negative: a one-off brief with no visual construct gets no decorative media and no quiz.
        "case": "one-off refund brief",
        "kwargs": {
            "recipe": "one_off",
            "evidence_target": "comprehension",
            "subject_domain": None,
            "lesson_intent": "Write a one-page refund policy brief for the front desk.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "verification",
            "rubric_profile": "procedural",
        },
        "reason_terms": ("no visual construct",),
    },
    {
        # Negative: a parent reading lesson is observation; the parent is the reader, not a voice
        # the harness generates, and the picture book is not an AI illustration.
        "case": "parent reading lesson",
        "kwargs": {
            "recipe": "parent",
            "evidence_target": "comprehension",
            "subject_domain": "language",
            "locale": "en-US",
            "lesson_intent": (
                "Read the picture book aloud with your child and ask what happens next."
            ),
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "observation",
            "rubric_profile": "observation",
        },
        "reason_terms": ("parent",),
    },
    {
        # Positive: a parent lesson may need a cited field guide, but it stays optional reference.
        "case": "parent field-guide observation",
        "kwargs": {
            "recipe": "parent",
            "evidence_target": "comprehension",
            "subject_domain": None,
            "lesson_intent": (
                "Compare the leaves you collected against the field guide plate and record what "
                "you observe."
            ),
        },
        "expect": {
            "image": "optional",
            "image_role": "sourced_reference",
            "audio": "none",
            "audio_role": None,
            "check_angle": "observation",
            "rubric_profile": "observation",
        },
        "reason_terms": ("field guide",),
    },
    {
        # Negative: grammar is symbolic; a locale does not imply narration or a picture.
        "case": "japanese grammar discrimination",
        "kwargs": {
            "recipe": "committed",
            "evidence_target": "discrimination",
            "subject_domain": "grammar",
            "locale": "ja-JP",
            "level": "L2",
            "lesson_intent": "Distinguish the particles wa and ga in written sentences.",
        },
        "expect": {
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "check_angle": "discrimination",
            "rubric_profile": "recall_accuracy",
        },
        "reason_terms": ("symbolic",),
    },
)


class CapabilityMatrixTest(unittest.TestCase):
    """One table, positive and negative side by side, asserted field by field."""

    def test_matrix_rows(self) -> None:
        for row in MATRIX:
            with self.subTest(case=row["case"]):
                result = plan(**row["kwargs"])  # type: ignore[arg-type]
                for field, expected in row["expect"].items():  # type: ignore[union-attr]
                    self.assertEqual(
                        getattr(result, field),
                        expected,
                        f"{row['case']}: {field} was {getattr(result, field)!r}",
                    )
                joined = " ".join(result.reasons).lower()
                for term in row["reason_terms"]:  # type: ignore[union-attr]
                    self.assertIn(
                        str(term).lower(),
                        joined,
                        f"{row['case']}: reason must name the construct {term!r}: {result.reasons}",
                    )

    def test_every_row_records_a_reason_for_each_decision(self) -> None:
        for row in MATRIX:
            with self.subTest(case=row["case"]):
                result = plan(**row["kwargs"])  # type: ignore[arg-type]
                self.assertEqual(len(result.reasons), 4)
                # angle, image, audio, rubric: none may be empty or a bare preference.
                self.assertTrue(all(len(reason) > 40 for reason in result.reasons))

    def test_every_recipe_is_decided(self) -> None:
        for recipe in policy.RECIPES:
            with self.subTest(recipe=recipe):
                result = plan(recipe=recipe, lesson_intent="Explain the idea and work one example.")
                self.assertEqual(result.recipe, recipe)
                if recipe == "one_off":
                    self.assertEqual(result.check_angle, "verification")
                elif recipe == "parent":
                    self.assertEqual(result.check_angle, "observation")
                else:
                    self.assertEqual(result.check_angle, "comprehension")


class HardRuleTest(unittest.TestCase):
    def test_media_is_none_by_default(self) -> None:
        result = plan(lesson_intent="Explain the causes of the French Revolution.")
        self.assertEqual((result.image, result.image_role), ("none", None))
        self.assertEqual((result.audio, result.audio_role), ("none", None))
        self.assertFalse(result.carries_media)
        self.assertEqual(result.required_media, ())

    def test_locale_alone_never_buys_audio(self) -> None:
        result = plan(
            evidence_target="comprehension",
            subject_domain="language",
            locale="ja-JP",
            level="L0",
            lesson_intent="Read the hiragana row and match each kana to its sound in writing.",
        )
        self.assertEqual(result.audio, "none")
        self.assertIn("no narration is added merely because locale", " ".join(result.reasons))

    def test_illustration_is_never_required(self) -> None:
        result = plan(
            recipe="committed",
            evidence_target="comprehension",
            subject_domain="language",
            locale="ja-JP",
            lesson_intent="Use a picture of a station to introduce the vocabulary for a trip.",
        )
        self.assertEqual((result.image, result.image_role), ("optional", "illustration"))
        with self.assertRaises(policy.CapabilityPolicyError):
            policy.LessonCapabilityPlan(
                recipe="committed",
                evidence_target="comprehension",
                check_angle="comprehension",
                rubric_profile="concept_explanation",
                image="required",
                image_role="illustration",
                audio="none",
                audio_role=None,
                reasons=("looks nicer",),
            )

    def test_one_off_never_gets_a_decorative_illustration(self) -> None:
        result = plan(
            recipe="one_off",
            evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Replace the cabin filter; use the illustration for context.",
        )
        self.assertEqual((result.image, result.image_role), ("none", None))
        self.assertEqual(result.check_angle, "verification")

    def test_parent_never_gets_generated_narration(self) -> None:
        result = plan(
            recipe="parent",
            evidence_target="production",
            subject_domain="language",
            locale="ja-JP",
            lesson_intent="Say each greeting aloud to your child and have them repeat it.",
        )
        self.assertEqual(result.audio, "none")
        self.assertEqual(result.check_angle, "observation")
        self.assertEqual(result.rubric_profile, "observation")

    def test_symbolic_domain_refuses_ai_illustration_even_when_named(self) -> None:
        result = plan(
            subject_domain="mathematics",
            lesson_intent="Use a picture of a pizza to make fractions concrete.",
        )
        self.assertEqual((result.image, result.image_role), ("none", None))

    def test_parent_reading_does_not_treat_the_book_as_generated_media(self) -> None:
        result = plan(
            recipe="parent",
            evidence_target="comprehension",
            subject_domain="language",
            locale="en-US",
            lesson_intent="Read the picture book aloud and ask your child to predict the ending.",
        )
        self.assertEqual((result.image, result.audio), ("none", "none"))

    def test_strong_technical_construct_works_without_an_advisory_domain(self) -> None:
        result = plan(
            recipe="one_off",
            evidence_target="procedure",
            subject_domain=None,
            lesson_intent="Tighten the bolts to the torque sequence printed on the label.",
        )
        self.assertEqual((result.image, result.image_role), ("required", "schematic"))

    def test_check_angle_follows_the_recipe_rule(self) -> None:
        self.assertEqual(plan(recipe="one_off", evidence_target="recall").check_angle, "verification")
        self.assertEqual(plan(recipe="parent", evidence_target="production").check_angle, "observation")
        self.assertEqual(plan(recipe="committed", evidence_target="procedure").check_angle, "procedure")

    def test_required_media_lists_the_roles_the_generator_must_produce(self) -> None:
        result = plan(
            evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Follow the torque sequence and check the clearance with a gauge.",
        )
        self.assertEqual(result.required_media, ("schematic",))


class RubricProfileTest(unittest.TestCase):
    def test_every_profile_has_at_least_three_distinct_observable_criteria(self) -> None:
        for profile, criteria in policy.RUBRIC_PROFILE_CRITERIA.items():
            with self.subTest(profile=profile):
                self.assertIn(profile, policy.RUBRIC_PROFILES)
                self.assertGreaterEqual(len(criteria), policy.MIN_RUBRIC_CRITERIA)
                self.assertEqual(len(criteria), len(set(criteria)))
                self.assertNotIn("understands", " ".join(criteria).lower())

    def test_rubric_profile_is_selected_by_construct(self) -> None:
        cases = {
            "concept_explanation": plan(
                subject_domain="mathematics",
                lesson_intent="Explain why the quadratic formula works.",
            ),
            "procedural": plan(
                evidence_target="procedure",
                subject_domain="technical_procedure",
                lesson_intent="Follow the torque sequence and verify the clearance.",
            ),
            "language_production": plan(
                evidence_target="production",
                subject_domain="language",
                locale="ja-JP",
                lesson_intent="Say the greeting aloud with the right register.",
            ),
            "recall_accuracy": plan(
                evidence_target="recall",
                lesson_intent="Name the three branches of the US federal government.",
            ),
            "source_analysis": plan(
                evidence_target="transfer",
                subject_domain="history",
                lesson_intent="Analyse the poster's claim, evidence and provenance.",
            ),
            "observation": plan(recipe="parent", lesson_intent="Watch your child sort the shapes."),
        }
        for profile, result in cases.items():
            with self.subTest(profile=profile):
                self.assertEqual(result.rubric_profile, profile)


class PlanObjectTest(unittest.TestCase):
    def test_plan_is_immutable(self) -> None:
        result = plan()
        with self.assertRaises(FrozenInstanceError):
            result.image = "required"  # type: ignore[misc]

    def test_plan_is_deterministic(self) -> None:
        kwargs = {
            "recipe": "committed",
            "evidence_target": "production",
            "subject_domain": "language",
            "locale": "ja-JP",
            "level": "L0",
            "lesson_intent": "Greet a coworker and say the phrase aloud.",
        }
        first = policy.plan_lesson_capability(**kwargs)
        second = policy.plan_lesson_capability(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_plan_projection_is_json_safe(self) -> None:
        projection = plan().to_dict()
        self.assertEqual(json.loads(json.dumps(projection)), projection)
        self.assertIsInstance(projection["reasons"], list)

    def test_unknown_recipe_and_target_are_rejected(self) -> None:
        with self.assertRaises(policy.CapabilityPolicyError):
            policy.plan_lesson_capability(
                recipe="workshop", evidence_target="recall", lesson_intent="Do the thing."
            )
        with self.assertRaises(policy.CapabilityPolicyError):
            policy.plan_lesson_capability(
                recipe="committed", evidence_target="mastery", lesson_intent="Do the thing."
            )

    def test_media_level_must_agree_with_its_role(self) -> None:
        with self.assertRaises(policy.CapabilityPolicyError):
            policy.LessonCapabilityPlan(
                recipe="committed",
                evidence_target="comprehension",
                check_angle="comprehension",
                rubric_profile="concept_explanation",
                image="none",
                image_role="schematic",
                audio="none",
                audio_role=None,
                reasons=("test",),
            )
        with self.assertRaises(policy.CapabilityPolicyError):
            policy.LessonCapabilityPlan(
                recipe="committed",
                evidence_target="comprehension",
                check_angle="comprehension",
                rubric_profile="concept_explanation",
                image="optional",
                image_role=None,
                audio="none",
                audio_role=None,
                reasons=("test",),
            )


class PurityTest(unittest.TestCase):
    """The policy decides; it does not read a database, call a provider or touch a filesystem."""

    def test_module_imports_only_pure_standard_library(self) -> None:
        tree = ast.parse(POLICY_SOURCE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "re", "dataclasses", "typing"})

    def test_no_network_or_database_names_appear(self) -> None:
        source = POLICY_SOURCE.read_text(encoding="utf-8")
        for forbidden in ("sqlite3", "urllib", "requests", "socket", "http.client", "psycopg"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_mirrored_enums_cannot_drift(self) -> None:
        self.assertEqual(policy.RECIPES, generation.RECIPES)
        self.assertEqual(policy.EVIDENCE_TARGETS, generation.EVIDENCE_TARGETS)
        self.assertEqual(policy.MIN_RUBRIC_CRITERIA, packs.MIN_RUBRIC_CRITERIA)
        self.assertEqual(policy.DOMAIN_SOURCES, curriculum.DOMAIN_SOURCES)


class ParentMediaPreferenceTest(unittest.TestCase):
    """H-07: the parent's typed media answers may narrow the capability decision, never widen it."""

    def test_the_parent_answer_withholds_a_medium_the_intent_would_have_earned(self) -> None:
        # Two intents that really earn a medium: a torque sequence earns a schematic, a spoken
        # greeting earns a pronunciation reference.
        visual = plan(recipe="committed", evidence_target="procedure",
                      subject_domain="technical_procedure",
                      lesson_intent="Replace the head gasket: follow the torque sequence and the stop condition.")
        self.assertEqual((visual.image, visual.image_role), ("required", "schematic"))
        withheld_visual = policy.plan_lesson_capability(
            recipe="committed", evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Replace the head gasket: follow the torque sequence and the stop condition.",
            media_preferences={"desired_visuals": "none"},
        )
        self.assertEqual((withheld_visual.image, withheld_visual.image_role), ("none", None))
        self.assertIn("parent brief asked for no visuals", " ".join(withheld_visual.reasons))

        spoken = plan(recipe="committed", evidence_target="production", subject_domain="language",
                      locale="ja-JP", level="L0",
                      lesson_intent="Greet a coworker and introduce yourself, saying the phrase aloud.")
        self.assertEqual((spoken.audio, spoken.audio_role), ("required", "pronunciation_reference"))
        withheld_audio = policy.plan_lesson_capability(
            recipe="committed", evidence_target="production", subject_domain="language",
            locale="ja-JP", level="L0",
            lesson_intent="Greet a coworker and introduce yourself, saying the phrase aloud.",
            media_preferences={"narration": "none"},
        )
        self.assertEqual((withheld_audio.audio, withheld_audio.audio_role), ("none", None))
        self.assertIn("parent brief asked for no narration", " ".join(withheld_audio.reasons))

    def test_a_parent_permission_never_forces_media(self) -> None:
        permitted = plan(recipe="parent", evidence_target="recall",
                         lesson_intent="The parent names one object and the child points to it.",
                         locale="ja-JP", subject_domain="language",
                         media_preferences={"desired_visuals": "illustrations", "narration": "script"})
        self.assertEqual((permitted.image, permitted.audio), ("none", "none"))
        self.assertEqual(permitted, plan(recipe="parent", evidence_target="recall",
                                         lesson_intent="The parent names one object and the child points to it.",
                                         locale="ja-JP", subject_domain="language"))


if __name__ == "__main__":
    unittest.main()
