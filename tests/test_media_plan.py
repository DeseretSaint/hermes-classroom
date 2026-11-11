"""H-05: the plan declares each lesson's media need, and the policy is still the authority.

The lesson policy used to guess media from incidental ``lesson_intent`` prose. These tests drive a
**generated** plan through the real plan job with a fake model, then prove three things agree:

1. the plan prompt asks for a typed ``media_need`` on every section;
2. the stored plan carries exactly that declaration; and
3. the capability policy, the lesson prompt and the lesson validator all read the declaration —
   a required need must be produced, a forbidden role is rejected, and a section that declares no
   need can never produce decorative media.

Six matrix lessons: head-gasket procedure, Japanese spoken phrase, algebra derivation, history
source image, one-off wiring and parent observation (``docs/VISUAL_MEDIA_PLAN.md`` §4).
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime, timezone

from coursebook import generation as gen
from coursebook import policy

from tests.test_generation import (
    FakeLLM,
    response,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    gen.ensure_schema(connection)
    return connection


def fake_plan_validation():
    return validation_from_fixture()



# ── The six generated plans ─────────────────────────────────────────────────

def need(construct: str, image=("none", "none"), audio=("none", "none")) -> dict:
    return {
        "construct": construct,
        "image": {"level": image[0], "role": image[1]},
        "audio": {"level": audio[0], "role": audio[1]},
    }


NONE_NEED = need("")

MATRIX = {
    "head_gasket_procedure": {
        "recipe": "committed",
        "target": "procedure",
        "domain": "technical_procedure",
        "locale": None,
        "level": None,
        "intent": "Follow the torque sequence and tighten each bolt to the labelled specification.",
        "media_need": need("torque sequence and labelled bolt specifications", image=("required", "schematic")),
        "expect_image": ("required", "schematic"),
        "expect_audio": ("none", None),
        "profile": "procedural",
        "permitted": {
            "kind": "visual",
            "role": "schematic",
            "purpose": "Carry the torque sequence",
            "spec": "Deterministic torque table",
            "text_equivalent": "Bolt 1 to 20 Nm in the numbered order.",
            "facts": {"rows": [{"label": "Bolt 1", "value": "20 Nm"}]},
        },
    },
    "japanese_spoken_phrase": {
        "recipe": "committed",
        "target": "production",
        "domain": "language",
        "locale": "ja-JP",
        "level": "L0",
        "intent": "Model the polite greeting, then have the learner say it aloud.",
        "media_need": need(
            "say the polite greeting aloud",
            audio=("required", "pronunciation_reference"),
        ),
        "expect_image": ("none", None),
        "expect_audio": ("required", "pronunciation_reference"),
        "profile": "language_production",
        "permitted": {
            "kind": "audio",
            "role": "narration",
            "purpose": "Hear the phrase",
            "spec": "A clear rendering of the greeting",
            "text_equivalent": "こんにちは",
            "transcript": "こんにちは",
            "language": "ja-JP",
            "voice": "default",
        },
    },
    "algebra_derivation": {
        "recipe": "committed",
        "target": "comprehension",
        "domain": "mathematics",
        "locale": None,
        "level": None,
        "intent": "Derive the quadratic formula by completing the square, line by line.",
        "media_need": NONE_NEED,
        "expect_image": ("none", None),
        "expect_audio": ("none", None),
        "profile": "concept_explanation",
        "permitted": None,
    },
    "history_source_image": {
        "recipe": "committed",
        "target": "transfer",
        "domain": "history",
        "locale": None,
        "level": None,
        "intent": "Analyse a wartime recruitment poster: claim, evidence, provenance and bias.",
        "media_need": need(
            "wartime recruitment poster photograph",
            image=("required", "sourced_reference"),
        ),
        "expect_image": ("required", "sourced_reference"),
        "expect_audio": ("none", None),
        "profile": "source_analysis",
        "permitted": {
            "kind": "visual",
            "role": "sourced_technical",
            "purpose": "The poster the analysis is performed on",
            "spec": "The cited public-domain poster",
            "text_equivalent": "A recruitment poster reading 'Your country needs you'.",
            "source_ids": ["src_poster"],
            "permission": "public_domain",
        },
    },
    "one_off_wiring": {
        "recipe": "one_off",
        "target": "procedure",
        "domain": "technical_procedure",
        "locale": None,
        "level": None,
        "intent": "Wire the replacement harness connector in the order the wiring diagram shows.",
        "media_need": need(
            "wiring diagram and connector pin order",
            image=("required", "schematic"),
        ),
        "expect_image": ("required", "schematic"),
        "expect_audio": ("none", None),
        "profile": "procedural",
        "permitted": {
            "kind": "visual",
            "role": "schematic",
            "purpose": "Carry the pin order",
            "spec": "Deterministic pin table",
            "text_equivalent": "Pin 1 is the red wire; pin 2 is black.",
            "facts": {"rows": [{"label": "Pin 1", "value": "Red"}]},
        },
    },
    "parent_observation": {
        "recipe": "parent",
        "target": "comprehension",
        "domain": "history",
        "locale": None,
        "level": None,
        "intent": "Parent reads a picture book page and asks the child what happened next.",
        "media_need": need(
            "picture book page photograph",
            image=("optional", "sourced_reference"),
        ),
        "expect_image": ("optional", "sourced_reference"),
        "expect_audio": ("none", None),
        "profile": "observation",
        # Optional: the observation is the evidence, so the lesson may omit it.
        "permitted": None,
    },
}


def check_kind(row: dict) -> str:
    return {"one_off": "verification", "parent": "observation"}.get(row["recipe"], "quiz")


def plan_document(row: dict) -> dict:
    """A complete, schema-valid plan whose first section carries the scenario declaration."""
    kind = check_kind(row)
    targets = [row["target"], "comprehension", "comprehension", "comprehension"]
    sections = []
    for ordinal in range(1, 5):
        sections.append(
            {
                "ordinal": ordinal,
                "title": f"Section {ordinal}",
                "lesson_intent": row["intent"]
                if ordinal == 1
                else f"Explain supporting idea {ordinal} and work one example.",
                "media_need": dict(row["media_need"]) if ordinal == 1 else dict(NONE_NEED),
                "objective_refs": [ordinal],
                "context_needs": ["romaji"] if row["locale"] else ["worked example"],
                "source_ids": [],
            }
        )
    document = {
        "title": "A generated course",
        "learner_outcome": "Produce the declared evidence for every objective in this course.",
        # H-195: the schema requires the plan's arc and starting assumptions; this builder is a
        # hand-built plan, so it states them rather than leaving the rule to reject it.
        "through_line": (
            "Each section adds one observable move and every later section uses the previous "
            "one, so the declared evidence is produced by the end of the course."
        ),
        "prerequisite_assumptions": [
            "The learner can read the language the course is delivered in.",
            "No prior knowledge of the subject is assumed.",
        ],
        "delivery": "parent_led" if row["recipe"] == "parent" else "self_study",
        "time_estimate": {
            "sessions_per_week": 3,
            "minutes_per_session": 25,
            "weeks": 4,
            "basis": "model",
            "confidence": "low",
            "rationale": "Derived from the declared weekly minutes; it is scheduling, not attainment.",
            "benchmark": None,
            "attainment_hours": None,
        },
        "objectives": [
            {
                "ordinal": ordinal,
                "title": f"Objective {ordinal}",
                "evidence_target": targets[ordinal - 1],
                "evidence_criteria": ["Produces an observable response to the task"],
                "support": "unverified",
            }
            for ordinal in range(1, 5)
        ],
        "sections": sections,
        "check_plan": [
            {
                "objective_ref": ordinal,
                "kind": kind,
                "evidence_target": targets[ordinal - 1],
                "count": 1,
                "independent_evidence": True,
            }
            for ordinal in range(1, 5)
        ],
        "context_needs": ["romaji"] if row["locale"] else ["worked example", "quiet space"],
        "source_ids": [],
        "exclusions": ["No claim beyond the declared evidence target."],
        "spaced_review": row["recipe"] == "committed",
        "evidence_note": "Checks are self-checks; they are not independent evidence."
        if row["recipe"] == "casual"
        else None,
    }
    if row["recipe"] == "parent":
        document["parent"] = {
            "age_band": "6-8",
            "reading_level": "early reader",
            "supervision_notes": ["An adult stays with the child throughout."],
            "hazards": ["No hazards apply in this lesson."],
            "setting_materials": ["The picture book"],
        }
    return document


def plan_job(row: dict, *, job_id: str = "job-h05") -> dict:
    brief = {"goal": "Learn the declared thing", "recipe": row["recipe"], "dials": {}, "locale": row["locale"]}
    if row["level"]:
        brief["level"] = row["level"]
    if row["domain"]:
        brief["subject_domain"] = row["domain"]
    return {"job_id": job_id, "kind": "plan", "attempt_id": "attempt-1", "brief": brief}


def run_generated_plan(row: dict):
    """Run the real plan job with a fake model and return (connection, result, stored section)."""
    document = plan_document(row)
    llm = FakeLLM(
        {
            "coursebook.plan.generate": lambda request: response(document),
            "coursebook.plan.validate": fake_plan_validation(),
        }
    )
    connection = memory_connection()
    result = gen.run_plan_job(connection, plan_job(row), llm, search=None, now=NOW)
    section_row = dict(
        connection.execute(
            "SELECT * FROM gen_plan_sections WHERE plan_id = ? AND ordinal = 1",
            (result["plan_id"],),
        ).fetchone()
    )
    return connection, result, section_row


def stored_section(section_row: dict) -> dict:
    return gen._section_dict(section_row)


def objective_for(row: dict) -> dict:
    return {
        "id": "obj_1",
        "ordinal": 1,
        "title": "Objective 1",
        "evidence_target": row["target"],
        "evidence_criteria": ["Produces an observable response to the task"],
    }


def policy_dials(row: dict) -> dict:
    return gen._policy_dials({}, level=row["level"], subject_domain=row["domain"])


def capability_for(row: dict, section: dict) -> policy.LessonCapabilityPlan:
    return gen.lesson_capability_plan(
        recipe=row["recipe"],
        section=section,
        objective=objective_for(row),
        locale=row["locale"],
        dials=policy_dials(row),
    )


def rubric_for(profile: str) -> list[dict]:
    from coursebook import rubrics

    entry = rubrics.get_profile(profile)
    return [
        {"criterion": criterion.label, "weight": 1.0, "description": criterion.observation}
        for criterion in entry.criteria
    ]


def lesson_for(row: dict, section: dict, *, media: list[dict] | None = None) -> dict:
    kind = check_kind(row)
    stimulus: dict = {"prompt": "Do the thing", "format": "text", "choices": []}
    if kind == "verification":
        stimulus = {
            "prompt": "Confirm each step",
            "format": "verification",
            "choices": [],
            "items": [
                {"id": "item_1", "label": "First step confirmed"},
                {"id": "item_2", "label": "Second step confirmed"},
            ],
        }
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
            "kind": kind,
            "stimulus": stimulus,
            "learner_instructions": "Respond honestly and in your own words.",
            "evidence_target": row["target"],
            "accepted_answers": ["the expected response"],
            "accepted_alternatives": [],
            "rubric": rubric_for(row["profile"]),
            "reference_answer": "the expected response",
            "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
            "scaffolds": {"romaji": True, "furigana": True, "english_meaning": True}
            if row["locale"]
            else {"romaji": False, "furigana": False, "english_meaning": False},
        },
        "sources": [],
        "media": list(media or []),
        "parent_notes": "Parent note." if row["recipe"] == "parent" else None,
        "supervision_notes": ["Adult nearby"] if row["recipe"] == "parent" else [],
    }


def enforce(row: dict, section: dict, lesson: dict) -> None:
    gen.enforce_lesson_rules(
        lesson,
        section=section,
        objective=objective_for(row),
        recipe=row["recipe"],
        locale=row["locale"],
        dials=policy_dials(row),
    )


# ── Prompt / plan / policy agree ────────────────────────────────────────────


class GeneratedPlanDeclarationTest(unittest.TestCase):
    def test_every_matrix_plan_declares_its_need_and_the_policy_adopts_it(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                connection, result, raw = run_generated_plan(row)
                try:
                    self.assertIsNotNone(result["plan_id"])
                    declared = json.loads(raw["media_need_json"])
                    self.assertEqual(declared, row["media_need"])

                    section = stored_section(raw)
                    self.assertEqual(section["media_need"], row["media_need"])
                    capability = capability_for(row, section)
                    self.assertTrue(capability.declared)
                    self.assertEqual(capability.construct, row["media_need"]["construct"])
                    self.assertEqual(
                        (capability.image, capability.image_role), row["expect_image"]
                    )
                    self.assertEqual(
                        (capability.audio, capability.audio_role), row["expect_audio"]
                    )
                finally:
                    connection.close()

    def test_plan_prompt_asks_for_the_declaration_and_names_the_default(self) -> None:
        instructions = gen._plan_instructions(
            recipe="committed", dials={}, locale=None, research_status="ok"
        )
        self.assertIn("Media policy", instructions)
        self.assertIn("media is not the default", instructions)
        self.assertIn("'media_need'", instructions)
        self.assertIn('"role": "none"', instructions)
        self.assertIn("sourced_reference", instructions)
        self.assertIn("never declare decorative media", instructions.lower())
        # CP-015's ledger-first authoring rule advances the label (v12 -> v14); the media
        # declaration rule this test guards is unchanged.
        self.assertEqual(gen.PLAN_PROMPT_VERSION, "plan-prompt.v17")

    def test_lesson_prompt_receives_the_declared_permissions_not_a_wish_list(self) -> None:
        for name, row in MATRIX.items():
            with self.subTest(lesson=name):
                connection, _result, raw = run_generated_plan(row)
                try:
                    section = stored_section(raw)
                    request = gen.build_lesson_request(
                        plan={"title": "Course", "learner_outcome": "Outcome", "delivery": "self_study"},
                        section=section,
                        objective=objective_for(row),
                        recipe=row["recipe"],
                        dials=policy_dials(row),
                        locale=row["locale"],
                        sources=[],
                    )
                    payload = gen._load_json(request.input_text, {})
                    recorded = payload["capability_policy"]
                    self.assertTrue(recorded["declared"])
                    self.assertEqual(recorded["construct"], row["media_need"]["construct"])
                    self.assertEqual(recorded["image"], row["expect_image"][0])
                    self.assertEqual(recorded["audio"], row["expect_audio"][0])

                    if row["expect_image"][0] == "none":
                        self.assertIn("Emit no visual media item", request.instructions)
                    else:
                        spec_role = policy.IMAGE_SPEC_ROLE[row["expect_image"][1]]
                        self.assertIn(f"visual item with role '{spec_role}'", request.instructions)
                        expected = (
                            "at least one" if row["expect_image"][0] == "required" else "at most one optional"
                        )
                        self.assertIn(expected, request.instructions)
                    if row["expect_audio"][0] == "none":
                        self.assertIn("Emit no audio media item", request.instructions)
                    else:
                        self.assertIn("audio item with role 'narration'", request.instructions)
                        self.assertIn("at least one", request.instructions)
                finally:
                    connection.close()

    def test_a_declared_none_wins_over_prose_that_names_a_construct(self) -> None:
        # The old failure mode: the intent prose names a torque sequence and the policy guessed a
        # schematic. The plan's declaration is authoritative now.
        row = dict(MATRIX["head_gasket_procedure"])
        row["media_need"] = dict(NONE_NEED)
        row["expect_image"] = ("none", None)
        row["expect_audio"] = ("none", None)
        row["permitted"] = None
        connection, _result, raw = run_generated_plan(row)
        try:
            capability = capability_for(row, stored_section(raw))
        finally:
            connection.close()
        self.assertTrue(capability.declared)
        self.assertEqual(capability.image, "none")
        self.assertIn("declares no visual need", " ".join(capability.reasons))


# ── The validator honors the declaration ────────────────────────────────────


class DeclaredMediaValidationTest(unittest.TestCase):
    def assert_rejected(self, row: dict, media: list[dict], needle: str) -> None:
        connection, _result, raw = run_generated_plan(row)
        try:
            section = stored_section(raw)
            lesson = lesson_for(row, section, media=media)
            with self.assertRaises(gen._RuleViolation) as caught:
                enforce(row, section, lesson)
        finally:
            connection.close()
        self.assertTrue(
            any(needle in reason for reason in caught.exception.reasons), caught.exception.reasons
        )

    def test_every_permitted_media_is_accepted_where_it_is_required(self) -> None:
        for name, row in MATRIX.items():
            if row["permitted"] is None:
                continue
            with self.subTest(lesson=name):
                connection, _result, raw = run_generated_plan(row)
                try:
                    section = stored_section(raw)
                    enforce(row, section, lesson_for(row, section, media=[dict(row["permitted"])]))
                finally:
                    connection.close()

    def test_a_required_need_must_be_produced(self) -> None:
        for name, row in MATRIX.items():
            if row["expect_image"][0] != "required" and row["expect_audio"][0] != "required":
                continue
            with self.subTest(lesson=name):
                self.assert_rejected(row, [], "the lesson did not produce one")

    def test_a_forbidden_role_is_rejected(self) -> None:
        # History declares a cited source image; a schematic is a different role.
        row = MATRIX["history_source_image"]
        self.assert_rejected(
            row,
            [
                {
                    "kind": "visual",
                    "role": "schematic",
                    "purpose": "Decoration",
                    "spec": "A schematic",
                    "text_equivalent": "A schematic of the poster.",
                    "facts": {"rows": [{"label": "A", "value": "B"}]},
                }
            ],
            "is not permitted",
        )

    def test_a_no_need_plan_cannot_produce_decorative_media(self) -> None:
        row = MATRIX["algebra_derivation"]
        self.assert_rejected(
            row,
            [
                {
                    "kind": "visual",
                    "role": "illustration",
                    "purpose": "Decorate the derivation",
                    "spec": "A picture of a quadratic",
                    "text_equivalent": "A picture of a parabola.",
                }
            ],
            "image to 'none'",
        )

    def test_a_parents_optional_reference_is_not_the_evidence(self) -> None:
        row = MATRIX["parent_observation"]
        # No media is fine: the observation is the evidence.
        connection, _result, raw = run_generated_plan(row)
        try:
            section = stored_section(raw)
            enforce(row, section, lesson_for(row, section))
        finally:
            connection.close()

    def test_required_media_is_deterministic(self) -> None:
        row = MATRIX["head_gasket_procedure"]
        connection, _result, raw = run_generated_plan(row)
        try:
            section = stored_section(raw)
            seen = []
            for _ in range(2):
                with self.assertRaises(gen._RuleViolation) as caught:
                    enforce(row, section, lesson_for(row, section))
                seen.append(caught.exception.reasons)
        finally:
            connection.close()
        self.assertEqual(seen[0], seen[1])


# ── The plan is rejected before authoring when the role is impossible ──────


class PlanDeclarationRuleTest(unittest.TestCase):
    def assert_plan_rejected(self, row: dict, document: dict, needle: str) -> None:
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                document,
                recipe=row["recipe"],
                dials=policy_dials(row),
                locale=row["locale"],
                ledger=[],
            )
        self.assertTrue(
            any(needle in reason for reason in caught.exception.reasons), caught.exception.reasons
        )

    def test_an_illustration_on_a_symbolic_lesson_is_refused_at_plan_time(self) -> None:
        row = dict(MATRIX["algebra_derivation"])
        document = plan_document(row)
        document["sections"][0]["media_need"] = need(
            "example picture", image=("optional", "illustration")
        )
        self.assert_plan_rejected(row, document, "illustration role is not permitted")

    def test_audio_outside_a_language_lesson_is_refused_at_plan_time(self) -> None:
        row = dict(MATRIX["algebra_derivation"])
        document = plan_document(row)
        document["sections"][0]["media_need"] = need(
            "say the derivation aloud", audio=("optional", "pronunciation_reference")
        )
        self.assert_plan_rejected(row, document, "generated audio is not permitted")

    def test_a_required_illustration_is_refused_at_plan_time(self) -> None:
        row = dict(MATRIX["head_gasket_procedure"])
        document = plan_document(row)
        document["sections"][0]["media_need"] = need(
            "context picture", image=("required", "illustration")
        )
        self.assert_plan_rejected(row, document, "can never be a required visual need")

    def test_a_missing_declaration_is_refused(self) -> None:
        row = MATRIX["algebra_derivation"]
        document = plan_document(row)
        document["sections"][0].pop("media_need")
        self.assert_plan_rejected(row, document, "must declare media_need")

    def test_a_construct_without_media_is_refused(self) -> None:
        row = MATRIX["algebra_derivation"]
        document = plan_document(row)
        document["sections"][0]["media_need"] = need("finished work", image=("none", "none"))
        self.assert_plan_rejected(row, document, "declares no media")

    def test_an_impossible_declaration_never_reaches_lesson_authoring(self) -> None:
        # The plan job retries, then stores a draft whose rejection reasons name the bad role.
        row = dict(MATRIX["algebra_derivation"])
        document = plan_document(row)
        document["sections"][0]["media_need"] = need(
            "example picture", image=("optional", "illustration")
        )
        llm = FakeLLM({"coursebook.plan.generate": lambda request: response(document)})
        connection = memory_connection()
        try:
            result = gen.run_plan_job(connection, plan_job(row), llm, search=None, now=NOW)
        finally:
            connection.close()
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(
            any("illustration role is not permitted" in reason for reason in result["rejection_reasons"]),
            result["rejection_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
