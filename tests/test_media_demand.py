"""Item 25/26/28: media demand comes from the lesson's **shape**, and text is drawn after.

The defect these cases pin: media permission was granted only when the learner's own words matched
a visual or oral regex. A head-gasket procedure whose goal never said "diagram" got no schematic,
and a Japanese section that quoted the exact phrase got no clip because its prose never said
"pronounce". The policy now reads facts it already has — the evidence target, the domain, the
objective, a named object, a named phrase — and the intent regex becomes a role selector and a
veto, never the only reason media exists.

No model, no provider, no database: every case is a call to the deterministic policy.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from coursebook import policy


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


def rear_brake_job() -> policy.LessonCapabilityPlan:
    """A real procedure whose prose names no visual construct at all."""
    return plan(
        evidence_target="procedure",
        subject_domain="technical_procedure",
        lesson_intent=(
            "Replace the rear brake pads: lift the caliper, press the piston back, fit the new "
            "pads and refit the wheel."
        ),
    )


class ImageDemandTest(unittest.TestCase):
    """Item 25: a procedure's step table needs its drawing even with no visual word in the goal."""

    def test_a_head_gasket_procedure_gets_a_required_schematic_with_no_visual_word(self) -> None:
        decision = rear_brake_job()
        self.assertEqual((decision.image, decision.image_role), ("required", "schematic"))
        reason = decision.reasons[1].lower()
        self.assertIn("step table", reason)
        self.assertIn("drawing", reason)
        self.assertIn("no visual construct", reason)
        self.assertEqual(policy.permitted_image_roles(decision), ("schematic",))
        self.assertEqual(policy.IMAGE_AUTHORITY["schematic"], "deterministic")

    def test_a_transfer_objective_in_a_technical_lesson_also_needs_the_schematic(self) -> None:
        decision = plan(
            evidence_target="transfer",
            subject_domain="technical_procedure",
            lesson_intent="Decide which of the two worn pads a customer should replace first.",
        )
        self.assertEqual((decision.image, decision.image_role), ("required", "schematic"))

    def test_a_procedure_objective_in_a_general_lesson_earns_an_optional_illustration(self) -> None:
        decision = plan(
            evidence_target="procedure",
            lesson_intent="Set up two-factor sign-in and confirm it works on a second device.",
        )
        self.assertEqual((decision.image, decision.image_role), ("optional", "illustration"))
        self.assertIn("reason to omit", " ".join(decision.reasons))
        # An illustration is context only; it can never be the visual the check grades.
        self.assertEqual(decision.image_authority, "none")

    def test_a_named_physical_object_earns_an_optional_illustration(self) -> None:
        decision = plan(lesson_intent="Explain how a car engine turns fuel into motion.")
        self.assertEqual((decision.image, decision.image_role), ("optional", "illustration"))
        self.assertIn("car", " ".join(decision.reasons))

    def test_a_symbolic_domain_keeps_refusing_the_illustration(self) -> None:
        for domain in ("mathematics", "grammar"):
            with self.subTest(domain=domain):
                decision = plan(
                    evidence_target="procedure",
                    subject_domain=domain,
                    lesson_intent="Work the derivation one line at a time.",
                )
                self.assertEqual((decision.image, decision.image_role), ("none", None))
                self.assertIn("symbolic", " ".join(decision.reasons))

    def test_the_intent_veto_wins_over_every_need(self) -> None:
        base = "Replace the rear brake pads: lift the caliper and fit the new pads"
        for refusal in (
            "no images",
            "without pictures",
            "no diagrams",
            "text only",
            "prose only",
            "text alone",
        ):
            with self.subTest(refusal=refusal):
                decision = plan(
                    evidence_target="procedure",
                    subject_domain="technical_procedure",
                    lesson_intent=f"{base}; {refusal}.",
                )
                self.assertEqual((decision.image, decision.image_role), ("none", None))
                self.assertEqual(decision.image, "none")

    def test_a_one_off_brief_and_a_parent_lesson_gain_nothing_from_shape(self) -> None:
        # A one-off brief is a verification checklist and a parent lesson is an observation; neither
        # is a lesson whose shape needs a figure, so the shape path must not widen them.
        one_off = plan(
            recipe="one_off",
            evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Replace the rear brake pads: lift the caliper and fit the new pads.",
        )
        self.assertEqual((one_off.image, one_off.image_role), ("none", None))
        parent = plan(
            recipe="parent",
            evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Watch your child fit the new pads and note what went well.",
        )
        self.assertEqual((parent.image, parent.image_role), ("none", None))

    def test_a_lesson_with_no_shape_signal_stays_text(self) -> None:
        decision = plan(lesson_intent="Explain the causes of the French Revolution.")
        self.assertEqual((decision.image, decision.image_role), ("none", None))
        self.assertEqual((decision.audio, decision.audio_role), ("none", None))

    def test_the_regex_still_selects_the_role_when_it_names_one(self) -> None:
        # The need path only fills a gap: a named construct keeps deciding the role, and the
        # illustration the intent names is still optional context.
        decision = plan(
            evidence_target="procedure",
            subject_domain="technical_procedure",
            lesson_intent="Replace the pads; a picture of the caliper in place helps.",
        )
        self.assertEqual((decision.image, decision.image_role), ("optional", "illustration"))


class AudioDemandTest(unittest.TestCase):
    """Item 26: a language lesson that names its line is not silent."""

    def test_a_language_lesson_with_a_quoted_phrase_gets_a_reference_clip(self) -> None:
        decision = plan(
            subject_domain="language",
            locale="en-US",
            level="L1",
            lesson_intent='Practise the line "good morning" until you can say it to a colleague.',
        )
        self.assertEqual((decision.audio, decision.audio_role), ("optional", "pronunciation_reference"))
        reason = decision.reasons[2]
        self.assertIn("good morning", reason)
        self.assertIn("locale", reason)

    def test_non_latin_script_alone_is_a_target_phrase(self) -> None:
        decision = plan(
            subject_domain="language",
            locale="ja-JP",
            level="L0",
            lesson_intent="Match ありがとう to the counter where it is said.",
        )
        self.assertEqual((decision.audio, decision.audio_role), ("optional", "pronunciation_reference"))

    def test_an_explicit_no_audio_stays_silent(self) -> None:
        decision = plan(
            subject_domain="language",
            locale="en-US",
            lesson_intent='Practise the line "good morning"; no audio.',
        )
        self.assertEqual((decision.audio, decision.audio_role), ("none", None))

    def test_audio_is_never_permitted_outside_the_language_domain(self) -> None:
        for domain in ("mathematics", "technical_procedure", "general"):
            with self.subTest(domain=domain):
                decision = plan(
                    subject_domain=domain,
                    lesson_intent='Say the line "e equals m c squared" aloud and explain it.',
                )
                self.assertEqual((decision.audio, decision.audio_role), ("none", None))

    def test_a_locale_without_a_phrase_still_buys_no_audio(self) -> None:
        decision = plan(
            subject_domain="language",
            locale="ja-JP",
            level="L0",
            lesson_intent="Read the hiragana row and match each kana to its sound in writing.",
        )
        self.assertEqual((decision.audio, decision.audio_role), ("none", None))

    def test_a_pronunciation_reference_and_a_narration_may_coexist(self) -> None:
        # The lesson schema has one audio item role, ``narration``; the policy's two roles are two
        # *items* of it. A lesson granted a pronunciation reference may carry the reference clip and
        # a natural reading of the same line together, and the gate must permit both.
        decision = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="production",
            lesson_intent="Say the line 二人です (futari desu) aloud at the counter.",
            locale="ja-JP",
            level="L0",
            subject_domain="language",
        )
        self.assertEqual((decision.audio, decision.audio_role), ("required", "pronunciation_reference"))
        self.assertEqual(policy.permitted_audio_roles(decision), ("narration",))

        reference = {
            "kind": "audio",
            "role": "narration",
            "purpose": "Hear the reference clip",
            "spec": "The line said slowly, twice, with a pause",
            "text_equivalent": "二人です",
            "transcript": "二人です",
            "language": "ja-JP",
            "voice": "default",
        }
        reading = dict(reference, purpose="Hear the same line at natural speed")
        self.assertEqual(policy.media_policy_problems(decision, [reference, reading]), [])
        self.assertEqual(policy.missing_required_media(decision, [reference]), [])
        # The pair is a permission, not a waiver: a lesson that produced neither still fails.
        self.assertEqual(len(policy.missing_required_media(decision, [])), 1)

    def test_the_lesson_prompt_says_the_pair_is_permitted(self) -> None:
        decision = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="production",
            lesson_intent="Say the line 二人です (futari desu) aloud at the counter.",
            locale="ja-JP",
            level="L0",
            subject_domain="language",
        )
        lines = gen._capability_prompt_lines(decision)
        self.assertTrue(
            any("may also carry one narration item" in line for line in lines), lines
        )


class AuthoringContractTest(unittest.TestCase):
    """Item 28: the authoring prompt says text is drawn afterwards, never inside the raster."""

    def request(self) -> gen.LLMRequest:
        return gen.build_lesson_request(
            plan={"title": "Course", "learner_outcome": "Outcome", "delivery": "self_study"},
            section={
                "section_id": "sec_1",
                "ordinal": 1,
                "title": "Replace the rear pads",
                "lesson_intent": "Replace the rear brake pads in order.",
                "objective_refs": [1],
                "source_ids": [],
            },
            objective={
                "id": "obj_1",
                "ordinal": 1,
                "title": "Objective",
                "evidence_target": "procedure",
                "evidence_criteria": ["Produces something observable"],
            },
            recipe="committed",
            dials={"subject_domain": "technical_procedure"},
            locale=None,
            sources=[],
        )

    def test_the_lesson_prompt_states_the_spec_contract(self) -> None:
        instructions = self.request().instructions
        self.assertIn("names subject, medium and composition only", instructions)
        self.assertIn("the picture carries the scene", instructions)
        self.assertIn("the media item's 'labels' array carries the words", instructions)
        self.assertIn("never ask it to paint text, labels, numbers or arrows", instructions)
        self.assertIn("The product UI draws those labels over the textless image", instructions)

    def test_the_system_prompt_states_text_is_never_asked_of_the_image_model(self) -> None:
        self.assertIn("never requested from the image model", gen.LESSON_SYSTEM_PROMPT)
        self.assertIn("A visual spec names subject, medium and composition only", gen.LESSON_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
