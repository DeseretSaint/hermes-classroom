"""CP-015g/D1-F2 followup: the lesson stage resolves the domain the plan resolved.

The plan-stage half (``tests/test_cp015g_domain_default.py``) made ``curriculum.resolve_domain`` the
one resolver for the brief, the research queries, the plan prompt, the validator and the plan run
record. The lesson stage still had the pre-v10 rule in ``policy._normalise_domain``: a declared
locale with no declared domain meant ``language``. A CP-015g telescope course (``subject_domain:
null``) was therefore gated as a language lesson — a section could declare narration audio, an
illustration was read as a "language visual aid", and the rubric profile could be
``language_production``.

These tests pin the lesson half:

* a locale alone no longer selects a domain in the policy;
* a telescope course's lesson cannot declare narration audio or a language illustration, and is
  not scored as language production;
* an inferred language course (named target language + locale) keeps its audio and pronunciation
  rules, and a declared language course keeps ``domain_source=declared``;
* a declared ``technical_procedure`` course is unchanged;
* the lesson run record names the same resolved domain and source the plan record did.
"""

from __future__ import annotations

import json
import unittest

from coursebook import generation as gen
from coursebook import policy

from tests.test_generation import (
    FakeLLM,
    GenerationTestBase,
    NOW,
    lesson_from_request,
    plan_job,
    validation_from_fixture,
)

TELESCOPE = (
    "Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night"
)
SPANISH = "Learn Spanish to order food in Mexico City"


def _provenance(goal: str, *, subject_domain: str | None, locale: str | None) -> dict:
    """The plan-stage decision a lesson stage would reuse from the plan document."""
    return gen._stage_domain_provenance(
        {}, goal=goal, subject_domain=subject_domain, locale=locale
    )


def _none_media() -> dict:
    return {
        "construct": "",
        "image": {"level": "none", "role": "none"},
        "audio": {"level": "none", "role": "none"},
    }


def _declared_media(construct: str, *, image: tuple[str, str], audio: tuple[str, str]) -> dict:
    return {
        "construct": construct,
        "image": {"level": image[0], "role": image[1]},
        "audio": {"level": audio[0], "role": audio[1]},
    }


def _lesson_plan(
    *,
    goal: str,
    subject_domain: str | None,
    locale: str | None,
    section: dict,
    evidence_target: str = "comprehension",
    recipe: str = "casual",
) -> policy.LessonCapabilityPlan:
    return gen.lesson_capability_plan(
        recipe=recipe,
        section=section,
        objective={"ordinal": 1, "evidence_target": evidence_target},
        locale=locale,
        dials={},
        plan={"subject_domain": subject_domain},
        domain_provenance=_provenance(goal, subject_domain=subject_domain, locale=locale),
    )


class PolicyOmitedDomainTest(unittest.TestCase):
    def test_an_omitted_domain_is_general_even_with_a_locale(self) -> None:
        # The pre-v10 rule returned `language` here. A locale is the delivery language, not the
        # subject: only a declared (or goal-resolved) domain can make the course a language course.
        self.assertEqual(policy.normalise_subject_domain(None, "ja-JP"), "general")
        self.assertEqual(policy.normalise_subject_domain("   ", "es-MX"), "general")
        result = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="comprehension",
            lesson_intent="Explain why the moons change position from night to night.",
            locale="en-US",
        )
        self.assertEqual(result.subject_domain, "general")
        self.assertEqual(result.audio, "none")
        self.assertNotIn(result.rubric_profile, ("language_production",))

    def test_a_declared_domain_still_wins(self) -> None:
        result = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="comprehension",
            lesson_intent="Explain the idea.",
            locale="es-MX",
            subject_domain="technical_procedure",
            domain_source="declared",
        )
        self.assertEqual(result.subject_domain, "technical_procedure")
        self.assertEqual(result.domain_source, "declared")
        self.assertEqual(result.audio, "none")


class TelescopeLessonTest(unittest.TestCase):
    """A CP-015g telescope course must not be gated as a language lesson."""

    def test_the_lesson_resolves_the_plan_domain_and_source(self) -> None:
        capability = _lesson_plan(
            goal=TELESCOPE,
            subject_domain=None,
            locale="en-US",
            section={"lesson_intent": "Explain how to align the finder scope.", "media_need": _none_media()},
        )
        self.assertEqual(capability.subject_domain, "technical_procedure")
        self.assertEqual(capability.domain_source, "inferred")
        self.assertEqual(capability.audio, "none")
        self.assertNotEqual(capability.rubric_profile, "language_production")

    def test_a_listening_intent_cannot_declare_narration_audio(self) -> None:
        section = {
            "lesson_intent": "Listen to a short passage about Jupiter's moons.",
            "media_need": _declared_media(
                "a short listening passage about Jupiter's moons",
                image=("none", "none"),
                audio=("required", "narration"),
            ),
        }
        with self.assertRaises(policy.CapabilityPolicyError) as caught:
            _lesson_plan(goal=TELESCOPE, subject_domain=None, locale="en-US", section=section)
        self.assertIn("not a language lesson", str(caught.exception))

    def test_a_language_visual_aid_cannot_be_declared(self) -> None:
        section = {
            "lesson_intent": "Explain how to align the finder scope.",
            "media_need": _declared_media(
                "a language visual aid with the words for each part of the telescope",
                image=("optional", "illustration"),
                audio=("none", "none"),
            ),
        }
        with self.assertRaises(policy.CapabilityPolicyError) as caught:
            _lesson_plan(goal=TELESCOPE, subject_domain=None, locale="en-US", section=section)
        self.assertIn("language artefact", str(caught.exception))

    def test_generic_context_artwork_is_still_optional(self) -> None:
        # The guard is narrow: a telescope lesson may still carry an optional picture of the night
        # sky. What it may not carry is a language artefact or generated narration.
        section = {
            "lesson_intent": "Explain how to align the finder scope.",
            "media_need": _declared_media(
                "a picture of the night sky around Jupiter",
                image=("optional", "illustration"),
                audio=("none", "none"),
            ),
        }
        capability = _lesson_plan(
            goal=TELESCOPE, subject_domain=None, locale="en-US", section=section
        )
        self.assertEqual((capability.image, capability.image_role), ("optional", "illustration"))


class LanguageLessonStillWorksTest(unittest.TestCase):
    def test_an_inferred_language_goal_keeps_pronunciation_audio(self) -> None:
        section = {
            "lesson_intent": "Say the phrase for ordering water and practise the pronunciation.",
            "media_need": _declared_media(
                "the spoken phrase for ordering water",
                image=("none", "none"),
                audio=("required", "pronunciation_reference"),
            ),
        }
        capability = _lesson_plan(
            goal=SPANISH, subject_domain=None, locale="es-MX", section=section,
            evidence_target="production",
        )
        self.assertEqual(capability.subject_domain, "language")
        self.assertEqual(capability.domain_source, "inferred")
        self.assertEqual(capability.audio, "required")
        self.assertEqual(capability.audio_role, "pronunciation_reference")
        self.assertIn(capability.rubric_profile, ("language_production", "pronunciation"))

    def test_a_declared_language_course_keeps_declared_provenance(self) -> None:
        capability = _lesson_plan(
            goal=SPANISH,
            subject_domain="language",
            locale="es-MX",
            section={"lesson_intent": "Identify the phrase used to ask for the bill.", "media_need": _none_media()},
        )
        self.assertEqual(capability.subject_domain, "language")
        self.assertEqual(capability.domain_source, "declared")


class DeclaredTechnicalProcedureUnchangedTest(unittest.TestCase):
    def test_a_declared_procedure_course_keeps_its_schematic(self) -> None:
        capability = gen.lesson_capability_plan(
            recipe="one_off",
            section={
                "lesson_intent": "Follow the torque sequence and check the clearance with a gauge.",
            },
            objective={"ordinal": 1, "evidence_target": "procedure"},
            locale="es-MX",
            dials={},
            plan={"subject_domain": "technical_procedure"},
        )
        self.assertEqual(capability.subject_domain, "technical_procedure")
        self.assertEqual(capability.domain_source, "declared")
        self.assertEqual((capability.image, capability.image_role), ("required", "schematic"))
        self.assertEqual(capability.audio, "none")


class LessonRunRecordTest(GenerationTestBase):
    """The lesson job's own record names the same domain and source as the plan record."""

    def _author_lessons(self, plan: dict) -> dict:
        llm = FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request("lesson_ja"),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        return gen.run_lesson_job(
            self.connection,
            {
                "job_id": "job-lesson-domain-1",
                "kind": "lesson",
                "brief": {"plan_id": plan["plan_id"]},
            },
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )

    def test_an_inferred_language_course_records_the_plan_provenance(self) -> None:
        plan = self.approved_plan()
        self.assertEqual(plan["domain_provenance"]["resolved_domain"], "language")
        self.assertEqual(plan["domain_provenance"]["source"], "inferred")

        result = self._author_lessons(plan)
        self.assertEqual(result["subject_domain"], "language")
        self.assertEqual(result["domain_source"], plan["domain_provenance"]["source"])
        self.assertEqual(
            result["domain_provenance"]["resolved_domain"],
            plan["domain_provenance"]["resolved_domain"],
        )
        self.assertTrue(result["lessons"])
        for summary in result["lessons"]:
            self.assertEqual(summary["subject_domain"], "language")
            self.assertEqual(summary["domain_source"], "inferred")

        # The stored media/policy record carries the same decision, not a locale default.
        for row in self.rows("SELECT policy_json FROM gen_lessons"):
            stored = json.loads(row["policy_json"])
            self.assertEqual(stored["subject_domain"], "language")
            self.assertEqual(stored["domain_source"], "inferred")

    def test_the_plan_document_records_the_provenance_the_lessons_reuse(self) -> None:
        plan = self.approved_plan()
        document = gen._load_plan_document(self.connection, plan["plan_id"])
        self.assertIsNotNone(document)
        stored = document["document"]["domain_provenance"]
        self.assertEqual(stored["resolved_domain"], plan["domain_provenance"]["resolved_domain"])
        self.assertEqual(stored["source"], plan["domain_provenance"]["source"])


if __name__ == "__main__":
    unittest.main()
