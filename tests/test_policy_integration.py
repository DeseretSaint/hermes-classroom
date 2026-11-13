"""M1-P3: the capability policy and rubric angles reach the prompt and the validator.

The policy module (P1) and the rubric registry (P2) are proven on their own. This file proves the
integration: the lesson the model is asked to write receives the chosen permissions and angles,
forbidden media is never offered, and generated media that contradicts the policy is rejected
deterministically before a validator ever sees it.

Six matrix lessons are covered end to end: head-gasket procedure, Japanese greeting, algebra
derivation, history source analysis, wiring brief and parent reading lesson
(``docs/VISUAL_MEDIA_PLAN.md`` §4).
"""

from __future__ import annotations

import unittest
from unittest import mock

from coursebook import generation as gen
from coursebook import policy, rubrics


# ── Helpers ─────────────────────────────────────────────────────────────────


def section(intent: str, ordinal: int = 1) -> dict:
    return {
        "section_id": f"sec_{ordinal}",
        "ordinal": ordinal,
        "title": "Section",
        "lesson_intent": intent,
        "objective_refs": [ordinal],
        "source_ids": [],
    }


def objective(target: str, ordinal: int = 1) -> dict:
    return {
        "id": f"obj_{ordinal}",
        "ordinal": ordinal,
        "title": "Objective",
        "evidence_target": target,
        "evidence_criteria": ["Produces something observable"],
    }


def rubric_for(profile: str) -> list[dict]:
    entry = rubrics.get_profile(profile)
    return [
        {"criterion": criterion.label, "weight": 1.0, "description": criterion.observation}
        for criterion in entry.criteria
    ]


def lesson_body(
    *,
    profile: str,
    target: str,
    check_kind: str = "quiz",
    stimulus_format: str = "text",
    scaffolds: dict | None = None,
    parent: bool = False,
) -> dict:
    stimulus: dict = {"prompt": "Do the thing", "format": stimulus_format, "choices": []}
    if stimulus_format == "verification":
        # A verification checklist enumerates its steps; generation refuses one without items.
        stimulus["items"] = [
            {"id": "item_1", "label": "First step confirmed"},
            {"id": "item_2", "label": "Second step confirmed"},
        ]
    return {
        "section_title": "A durable section",
        "segments": [
            {
                "kind": "model",
                "heading": "Model",
                "body": "A model segment for this section.",
                "short": "Model segment for this section.",
            },
            {
                "kind": "guided",
                "heading": "Guided",
                "body": "A guided segment for this section.",
                "short": "Guided segment for this section.",
            },
        ],
        "worked_example": {
            "prompt": "An example prompt",
            "steps": ["First step of the example", "Second step of the example"],
            "answer": "An example answer",
            "short": "Two steps, then the example answer.",
        },
        "learner_explanation": "A learner explanation that does not announce the check answer.",
        "learner_explanation_short": "A learner explanation without the check answer.",
        "check": {
            "kind": check_kind,
            "stimulus": stimulus,
            "learner_instructions": "Respond honestly and in your own words.",
            "evidence_target": target,
            "accepted_answers": ["the expected response"],
            "accepted_alternatives": [],
            "rubric": rubric_for(profile),
            "reference_answer": "the expected response",
            "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
            "scaffolds": scaffolds
            or {"romaji": False, "furigana": False, "english_meaning": False},
        },
        "sources": [],
        "media": [],
        "parent_notes": "Parent note." if parent else None,
        "supervision_notes": ["Adult nearby"] if parent else [],
    }


def visual(role: str, **extra) -> dict:
    item = {
        "kind": "visual",
        "role": role,
        "purpose": "Carry the teaching construct",
        "spec": "A declarative media spec",
        "text_equivalent": "A complete text equivalent for the item.",
    }
    item.update(extra)
    return item


def audio(**extra) -> dict:
    item = {
        "kind": "audio",
        "role": "narration",
        "purpose": "Hear the phrase",
        "spec": "A clear rendering of the phrase",
        "text_equivalent": "こんにちは",
        "transcript": "こんにちは",
        "language": "ja-JP",
        "voice": "default",
    }
    item.update(extra)
    return item


#: The six matrix lessons from `docs/VISUAL_MEDIA_PLAN.md` §4. Each row states the exact facts
#: the policy is allowed to decide from, and the media the prompt may and may not offer.
MATRIX = {
    "head_gasket_procedure": {
        "recipe": "committed",
        "target": "procedure",
        "intent": "Follow the torque sequence and tighten each bolt to the labelled specification.",
        "locale": None,
        "dials": {"subject_domain": "technical_procedure"},
        "profile": "procedural",
        "angle": "procedure",
        "image": "required",
        "image_role": "schematic",
        "audio": "none",
        "permitted": visual("schematic", facts={"rows": [{"label": "Bolt 1", "value": "20 Nm"}]}),
        "forbidden": audio(),
    },
    "japanese_greeting": {
        "recipe": "committed",
        "target": "production",
        "intent": "Model one polite greeting, then have the learner say it aloud.",
        "locale": "ja-JP",
        "dials": {"level": "L0"},
        "profile": "language_production",
        "angle": "production",
        "image": "none",
        "image_role": None,
        "audio": "required",
        "audio_role": "pronunciation_reference",
        "permitted": audio(),
        "forbidden": visual("illustration"),
    },
    "algebra_derivation": {
        "recipe": "committed",
        "target": "comprehension",
        "intent": "Derive the quadratic formula from completing the square, line by line.",
        "locale": None,
        "dials": {"subject_domain": "mathematics"},
        "profile": "concept_explanation",
        "angle": "comprehension",
        "image": "none",
        "image_role": None,
        "audio": "none",
        "audio_role": None,
        "permitted": None,
        "forbidden": visual("illustration"),
    },
    "history_source_analysis": {
        "recipe": "committed",
        "target": "transfer",
        "intent": "Analyse a wartime recruitment poster: claim, evidence, provenance and bias.",
        "locale": None,
        "dials": {"subject_domain": "history"},
        "profile": "source_analysis",
        "angle": "transfer",
        "image": "required",
        "image_role": "sourced_reference",
        "audio": "none",
        "audio_role": None,
        "permitted": visual(
            "sourced_technical",
            source_ids=["src_poster"],
            permission="public_domain",
        ),
        "forbidden": audio(),
    },
    "wiring_brief": {
        "recipe": "one_off",
        "target": "procedure",
        "intent": "Wire the replacement harness connector in the order the wiring diagram shows.",
        "locale": None,
        "dials": {"subject_domain": "technical_procedure"},
        "profile": "procedural",
        "angle": "verification",
        "image": "required",
        "image_role": "schematic",
        "audio": "none",
        "audio_role": None,
        "permitted": visual("schematic", facts={"rows": [{"label": "Pin 1", "value": "Red"}]}),
        "forbidden": visual("illustration"),
    },
    "parent_reading_lesson": {
        "recipe": "parent",
        "target": "comprehension",
        "intent": "Parent reads a picture book page and asks the child what happened next.",
        "locale": None,
        "dials": {},
        "profile": "observation",
        "angle": "observation",
        "image": "none",
        "image_role": None,
        "audio": "none",
        "audio_role": None,
        "permitted": None,
        "forbidden": visual("illustration"),
    },
}


def plan_for(row: dict) -> policy.LessonCapabilityPlan:
    return gen.lesson_capability_plan(
        recipe=row["recipe"],
        section=section(row["intent"]),
        objective=objective(row["target"]),
        locale=row["locale"],
        dials=dict(row["dials"]),
    )


def request_for(row: dict) -> gen.LLMRequest:
    return gen.build_lesson_request(
        plan={"title": "Course", "learner_outcome": "Outcome", "delivery": "self_study"},
        section=section(row["intent"]),
        objective=objective(row["target"]),
        recipe=row["recipe"],
        dials=dict(row["dials"]),
        locale=row["locale"],
        sources=[],
    )


def lesson_for(row: dict) -> dict:
    # GEN-7: the check kind follows the evidence target. A procedure, production or transfer
    # objective is a verification checklist; a parent lesson is an observation; only the quiz
    # family is a quiz.
    if row["recipe"] == "parent":
        kind, stimulus_format = "observation", "text"
    elif "quiz" in (gen.CHECK_KIND_BY_TARGET.get(str(row["target"])) or ("quiz",)):
        kind, stimulus_format = "quiz", "text"
    else:
        kind, stimulus_format = "verification", "verification"
    return lesson_body(
        profile=row["profile"],
        target=row["target"],
        check_kind=kind,
        stimulus_format=stimulus_format,
        scaffolds={"romaji": True, "furigana": True, "english_meaning": True}
        if row["locale"]
        else None,
        parent=row["recipe"] == "parent",
    )


# ── The plan reaches the prompt ─────────────────────────────────────────────


class PromptPolicyTest(unittest.TestCase):
    def test_every_matrix_row_prompts_its_decision(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                plan = plan_for(row)
                self.assertEqual(plan.rubric_profile, row["profile"])
                self.assertEqual(plan.check_angle, row["angle"])
                self.assertEqual(plan.image, row["image"])
                self.assertEqual(plan.audio, row["audio"])

                instructions = request_for(row).instructions
                self.assertEqual(gen.LESSON_PROMPT_VERSION, "lesson-prompt.v18")
                self.assertIn("Capability policy", instructions)
                self.assertIn(f"check angle: {row['angle']}", instructions)
                statements = [
                    line for line in instructions.splitlines()
                    if "rubric profile" in line.lower()
                ]
                self.assertEqual(len(statements), 1, statements)
                self.assertIn(f"Rubric profile: {row['profile']}", statements[0])
                self.assertIn(row["target"], str(request_for(row).input_text))

    def test_forbidden_media_is_never_offered(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                instructions = request_for(row).instructions
                if row["image"] == "none":
                    self.assertIn("Emit no visual media item", instructions)
                    self.assertNotIn("visual item with role", instructions)
                else:
                    spec_role = policy.IMAGE_SPEC_ROLE[row["image_role"]]
                    self.assertIn(f"visual item with role '{spec_role}'", instructions)
                if row["audio"] == "none":
                    self.assertIn("Emit no audio media item", instructions)
                    self.assertNotIn("audio item with role", instructions)
                else:
                    self.assertIn("audio item with role 'narration'", instructions)

    def test_prompt_payload_carries_the_plan_not_prose(self) -> None:
        request = request_for(MATRIX["algebra_derivation"])
        payload = gen._load_json(request.input_text, {})
        recorded = payload["capability_policy"]
        self.assertEqual(recorded["rubric_profile"], "concept_explanation")
        self.assertEqual(recorded["image"], "none")
        self.assertEqual(recorded["audio"], "none")
        self.assertTrue(recorded["reasons"])

    def test_plan_prompt_states_the_recipe_angle_and_media_default(self) -> None:
        one_off = gen._plan_instructions(
            recipe="one_off", dials={}, locale=None, research_status="ok"
        )
        self.assertIn("angle 'verification'", one_off)
        parent = gen._plan_instructions(
            recipe="parent", dials={}, locale=None, research_status="ok"
        )
        self.assertIn("angle 'observation'", parent)
        committed = gen._plan_instructions(
            recipe="committed", dials={}, locale=None, research_status="ok"
        )
        self.assertIn("media is not the default", committed)
        self.assertNotIn("angle 'verification'", committed)

    def test_rubric_angle_is_named_with_its_criteria(self) -> None:
        prompts = {
            name: request_for(row).instructions for name, row in MATRIX.items()
        }
        self.assertIn("ordered steps, safety stop condition, verification", prompts["head_gasket_procedure"])
        self.assertIn("target phrase, pronunciation or fluency, meaning, register", prompts["japanese_greeting"])
        self.assertIn("accurate claim, mechanism, example, limits", prompts["algebra_derivation"])
        self.assertIn("claim, evidence, provenance, contradiction handling", prompts["history_source_analysis"])
        self.assertIn("observable behaviour, context, note, follow-up", prompts["parent_reading_lesson"])


# ── The validator rejects policy-inappropriate media ────────────────────────


class AudioRolePromptTest(unittest.TestCase):
    """A permitted audio set with more than one role names every role, as the image branch does.

    ``permitted_audio_roles`` is the permission authority; the prompt may only describe what it
    grants. Naming ``audio_roles[0]`` alone told a lesson permitted narration plus a pronunciation
    clip about one of them, which made the second permission dead code.
    """

    def capability(self):
        return gen.lesson_capability_plan(
            recipe="committed",
            section={
                "section_id": "sec_audio",
                "ordinal": 1,
                "title": "Greeting",
                "lesson_intent": "Listen to a shopkeeper greeting a customer, then say it aloud.",
                "media_need": {
                    "construct": "listen to and repeat the greeting aloud",
                    "image": {"level": "none", "role": "none"},
                    "audio": {"level": "required", "role": "narration"},
                },
                "objective_refs": [1],
                "source_ids": [],
            },
            objective=objective("comprehension"),
            locale="ja-JP",
            dials={},
        )

    def audio_lines(self, capability) -> list[str]:
        return [
            line for line in gen._capability_prompt_lines(capability)
            if line.startswith("- audio")
        ]

    def test_the_single_permitted_role_is_named_without_inventing_a_second(self) -> None:
        lines = self.audio_lines(self.capability())
        self.assertEqual(len(lines), 1)
        self.assertIn("audio item with role 'narration'", lines[0])
        self.assertNotIn("at most one optional item with role", lines[0])

    def test_every_permitted_audio_role_is_named(self) -> None:
        with mock.patch.object(
            policy, "permitted_audio_roles",
            return_value=("narration", "pronunciation_reference"),
        ):
            lines = self.audio_lines(self.capability())
        self.assertEqual(len(lines), 1)
        self.assertIn("at least one audio item with role 'narration'", lines[0])
        self.assertIn("at most one optional item with role 'pronunciation_reference'", lines[0])


class ValidatorMediaPolicyTest(unittest.TestCase):
    def assert_rejected(self, row: dict, item: dict, needle: str) -> None:
        lesson = lesson_for(row)
        lesson["media"] = [item]
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_lesson_rules(
                lesson,
                section=section(row["intent"]),
                objective=objective(row["target"]),
                recipe=row["recipe"],
                locale=row["locale"],
                dials=dict(row["dials"]),
            )
        self.assertTrue(
            any(needle in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_permitted_media_passes_every_matrix_row(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                lesson = lesson_for(row)
                if row["permitted"] is not None:
                    lesson["media"] = [dict(row["permitted"])]
                gen.enforce_lesson_rules(
                    lesson,
                    section=section(row["intent"]),
                    objective=objective(row["target"]),
                    recipe=row["recipe"],
                    locale=row["locale"],
                    dials=dict(row["dials"]),
                )

    def test_forbidden_media_is_rejected_for_every_matrix_row(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                kind = row["forbidden"]["kind"]
                if kind == "visual":
                    needle = (
                        "image to 'none'"
                        if row["image"] == "none"
                        else "is not permitted"
                    )
                else:
                    needle = (
                        "audio to 'none'"
                        if row["audio"] == "none"
                        else "is not permitted"
                    )
                self.assert_rejected(row, dict(row["forbidden"]), needle)

    def test_image_for_algebra_is_rejected(self) -> None:
        self.assert_rejected(
            MATRIX["algebra_derivation"],
            visual("illustration", spec="A picture of the derivation"),
            "image to 'none'",
        )

    def test_audio_for_a_reading_only_language_lesson_is_rejected(self) -> None:
        row = {
            "recipe": "committed",
            "target": "comprehension",
            "intent": "Read each kana silently and answer what the sign says.",
            "locale": "ja-JP",
            "dials": {"level": "L0"},
            "profile": "concept_explanation",
            "angle": "comprehension",
            "image": "none",
            "image_role": None,
            "audio": "none",
            "audio_role": None,
            "permitted": None,
            "forbidden": audio(),
        }
        self.assert_rejected(row, audio(), "audio to 'none'")

    def test_decorative_image_for_a_one_off_brief_is_rejected(self) -> None:
        row = dict(MATRIX["wiring_brief"])
        row["intent"] = "Check the refund policy steps and issue the refund only when they pass."
        row["image"] = "none"
        row["image_role"] = None
        row["permitted"] = None
        self.assert_rejected(row, visual("illustration"), "image to 'none'")

    def test_unsourced_technical_image_presented_as_authority_is_rejected(self) -> None:
        row = MATRIX["history_source_analysis"]
        unsourced = visual("sourced_technical")
        self.assert_rejected(row, unsourced, "sourced technical reference needs at least one cited source")

        authority = visual("illustration", technical=True)
        # A language lesson permits an optional illustration; the artifact policy still refuses a
        # technical claim on it. Use the parent field-guide row to reach the illustration path.
        language = dict(MATRIX["japanese_greeting"])
        language["intent"] = "Use a picture as visual context for the greeting."
        language["audio"] = "none"
        language["audio_role"] = None
        language["permitted"] = None
        self.assert_rejected(language, authority, "illustration may not claim technical authority")

    def test_wrong_visual_role_is_rejected(self) -> None:
        # A symbolic lesson that names a graph may carry a schematic — and only a schematic.
        row = dict(MATRIX["algebra_derivation"])
        row["intent"] = "Sketch the graph of the quadratic and read off its roots."
        row["image"] = "optional"
        row["image_role"] = "schematic"
        self.assert_rejected(row, visual("illustration"), "is not permitted")

    def test_rejection_is_deterministic(self) -> None:
        row = MATRIX["algebra_derivation"]
        lesson = lesson_for(row)
        lesson["media"] = [visual("illustration")]
        results = []
        for _ in range(2):
            with self.assertRaises(gen._RuleViolation) as caught:
                gen.enforce_lesson_rules(
                    lesson,
                    section=section(row["intent"]),
                    objective=objective(row["target"]),
                    recipe=row["recipe"],
                    locale=row["locale"],
                    dials=dict(row["dials"]),
                )
            results.append(caught.exception.reasons)
        self.assertEqual(results[0], results[1])

    def test_lesson_media_must_pass_both_gates(self) -> None:
        # The head-gasket row permits a schematic; a schematic with no structured facts is still
        # refused by the artifact media policy.
        row = MATRIX["head_gasket_procedure"]
        self.assert_rejected(
            row, visual("schematic"), "a schematic must be rendered from structured facts"
        )


# ── Internal lesson schema ──────────────────────────────────────────────────


class LessonSchemaPolicyTest(unittest.TestCase):
    def test_schema_accepts_the_policy_fields(self) -> None:
        lesson = lesson_for(MATRIX["wiring_brief"])
        lesson["policy"] = plan_for(MATRIX["wiring_brief"]).to_dict()
        gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")

    def test_schema_rejects_an_unknown_policy_field(self) -> None:
        lesson = lesson_for(MATRIX["wiring_brief"])
        recorded = plan_for(MATRIX["wiring_brief"]).to_dict()
        recorded["image"] = "required-now"
        lesson["policy"] = recorded
        with self.assertRaises(gen.GenerationRejected):
            gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")


if __name__ == "__main__":
    unittest.main()
