"""CP-015h: the unit-sections stage states the construct shape its media gate enforces.

Reproduction: a real Japanese L0 course authored unit 1 with three
``pronunciation_reference`` declarations whose construct was the target phrase itself
(``二人です（ふたりです）``). The deterministic media gate refused every section (a
``pronunciation_reference`` construct must match the spoken-act vocabulary), the refused batch was
never validated, and both attempts produced the same shape because the only rule the author was
given never stated what the construct had to name. The retry therefore could not converge.

These cases pin the fix at both ends:

* ``_unit_sections_instructions`` states the shape the gate enforces (prompt v2);
* the refusal itself names the required shape, so the one legal re-author is told what to write;
* a bare target phrase is refused and a spoken act with its line passes the real gate.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen, policy

from tests.blueprint_support import (
    NOW,
    blueprint_plan,
    media_none,
    response,
    unit_sections_document,
    validation_pass,
)
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import FakeLLM

T0 = NOW

BARE_PHRASE = "二人です（ふたりです）"
BARE_PHRASE_2 = "テーブル席でお願いします（テーブルせきで おねがいします）"
SPOKEN_ACT = "pronounce the line 二人です (futari desu) aloud"
LISTENING_ACT = "listen to a shopkeeper greeting a customer"


def media_need(construct: str, *, role: str = "pronunciation_reference") -> dict:
    return {
        "construct": construct,
        "image": {"level": "none", "role": "none"},
        "audio": {"level": "optional", "role": role},
    }


class DeclaredConstructShapeTest(unittest.TestCase):
    """The gate: a target phrase is not a construct; a spoken act with its line is."""

    def plan(self) -> dict:
        return blueprint_plan(scope="single", units=1, objectives_per_unit=1)

    def section(self, construct: str, *, role: str = "pronunciation_reference") -> dict:
        document = unit_sections_document(
            unit=self.plan()["units"][0], objectives=self.plan()["objectives"]
        )
        section = dict(document["sections"][0])
        section["lesson_intent"] = (
            "Say the request aloud in the shop, choosing the polite register."
        )
        section["media_need"] = media_need(construct, role=role)
        return section

    def enforce(self, section: dict) -> None:
        plan = self.plan()
        gen.enforce_unit_section_rules(
            [section],
            unit=plan["units"][0],
            objectives=plan["objectives"],
            plan=plan,
            recipe="casual",
            dials={"subject_domain": "language", "level": "L0"},
            locale="ja-JP",
            ledger=(),
        )

    def test_a_bare_target_phrase_is_refused_and_names_the_required_shape(self) -> None:
        with self.assertRaises(gen._RuleViolation) as caught:
            self.enforce(self.section(BARE_PHRASE))
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("names no spoken construct", reasons)
        # The feedback has to teach the shape, not only report the absence of one.
        self.assertIn("spoken act and its line", reasons)
        self.assertIn("pronounce the line", reasons)
        self.assertIn("only quotes the target phrase", reasons)

    def test_the_reported_course_shape_is_refused_at_the_policy_layer(self) -> None:
        # The same shape the live job produced, asserted at the function that refused it.
        for construct in (BARE_PHRASE, BARE_PHRASE_2):
            with self.subTest(construct=construct):
                with self.assertRaises(policy.CapabilityPolicyError) as caught:
                    policy.plan_lesson_capability(
                        recipe="casual",
                        evidence_target="comprehension",
                        lesson_intent="Say the request aloud in the shop.",
                        locale="ja-JP",
                        level="L0",
                        subject_domain="language",
                        media_need=media_need(construct),
                    )
                self.assertIn("spoken act and its line", str(caught.exception))

    def test_a_spoken_act_with_its_line_passes_the_media_gate(self) -> None:
        self.enforce(self.section(SPOKEN_ACT))  # no exception
        decision = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="comprehension",
            lesson_intent="Say the request aloud in the shop.",
            locale="ja-JP",
            level="L0",
            subject_domain="language",
            media_need=media_need(SPOKEN_ACT),
        )
        self.assertEqual(
            (decision.audio, decision.audio_role), ("optional", "pronunciation_reference")
        )

    def test_a_narration_construct_must_name_the_listening_construct(self) -> None:
        with self.assertRaises(gen._RuleViolation) as caught:
            self.enforce(self.section(BARE_PHRASE, role="narration"))
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("names no listening construct", reasons)
        self.assertIn("what the learner listens to", reasons)
        self.enforce(self.section(LISTENING_ACT, role="narration"))  # no exception


class UnitSectionsPromptTest(UnitStageCase):
    """The prompt the author receives states the shape, and the version says it changed."""

    def setUp(self) -> None:
        super().setUp()
        self.plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, self.plan_id = self.seed(self.plan)

    def request(self) -> gen.LLMRequest:
        unit = self.plan["units"][0]
        return gen.build_unit_sections_request(
            plan=self.plan,
            unit=unit,
            objectives=self.plan["objectives"],
            goal=self.plan["learner_outcome"],
            recipe="casual",
            locale="ja-JP",
            sources=(),
            research_status="unavailable",
        )

    def test_the_prompt_states_the_construct_shape_the_gate_enforces(self) -> None:
        instructions = self.request().instructions
        self.assertIn("pronounce the line 二人です (futari desu) aloud", instructions)
        self.assertIn("spoken act and the line it speaks", instructions)
        self.assertIn("only the target phrase", instructions)
        self.assertIn("listen to a shopkeeper greeting a customer", instructions)
        self.assertIn("fails the whole unit batch", instructions)

    def test_the_prompt_version_advanced(self) -> None:
        # v3 adds CP-015g/D3's citation rule to the same instruction text this card states its
        # construct shape on, so the label advances rather than reusing v2 (docs/GENERATION.md §1).
        self.assertEqual(gen.UNIT_SECTIONS_PROMPT_VERSION, "unit-sections-prompt.v3")
        # The request builder carries the constant (``build_unit_sections_request`` points at
        # ``UNIT_SECTIONS_PROMPT_VERSION``), so the emitted label is the same v3. This assertion
        # pinned v2 and was left stale by CP-015g/D3's bump; it is the tree that was red, not the
        # builder.
        self.assertEqual(self.request().prompt_version, "unit-sections-prompt.v3")


class UnitSectionsRetryConvergesTest(UnitStageCase):
    """The refused attempt's feedback names the shape, and the second attempt can satisfy it."""

    def setUp(self) -> None:
        super().setUp()
        self.plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, self.plan_id = self.seed(self.plan)
        self.make_it_a_language_course(self.plan_id)

    def make_it_a_language_course(self, plan_id: str) -> None:
        # The unit stage reads locale/level/domain from the stored plan document. The reported
        # course is a Japanese L0 language course; the fixture plan carries none, so the document
        # metadata is set the way a language brief would have set it.
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT document_json FROM gen_plan_documents WHERE plan_id = ?", (plan_id,)
            ).fetchone()
            document = json.loads(row["document_json"])
            document["locale"] = "ja-JP"
            document["level"] = "L0"
            document["subject_domain"] = "language"
            connection.execute(
                "UPDATE gen_plan_documents SET document_json = ? WHERE plan_id = ?",
                (json.dumps(document), plan_id),
            )

    def batch(self, construct: str) -> dict:
        unit = self.plan["units"][0]
        document = unit_sections_document(unit=unit, objectives=self.plan["objectives"])
        section = dict(document["sections"][0])
        section["lesson_intent"] = "Say the request aloud in the shop, using the polite register."
        section["media_need"] = media_need(construct)
        document["sections"] = [section]
        return document

    def run_job(self, llm: FakeLLM) -> dict:
        return gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=T0,
        )

    def test_the_retry_is_told_the_required_construct_shape_and_can_pass(self) -> None:
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": [
                    response(self.batch(BARE_PHRASE)),
                    response(self.batch(SPOKEN_ACT)),
                ],
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        result = self.run_job(llm)
        self.assertEqual(result["sections"], 1)
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        retry = llm.requests[-2].input_text
        self.assertIn("names no spoken construct", retry)
        self.assertIn("spoken act and its line", retry)
        self.assertIn("pronounce the line", retry)
        with db.read() as connection:
            construct = connection.execute(
                "SELECT media_need_json FROM gen_plan_sections WHERE plan_id = ?",
                (self.plan_id,),
            ).fetchone()["media_need_json"]
        self.assertEqual(json.loads(construct)["construct"], SPOKEN_ACT)

    def test_a_batch_refused_twice_names_the_shape_and_stores_nothing(self) -> None:
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(self.batch(BARE_PHRASE)),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        with self.assertRaises(gen.GenerationRejected) as caught:
            self.run_job(llm)
        self.assertIn("names no spoken construct", str(caught.exception))
        self.assertIn("spoken act and its line", str(caught.exception))
        self.assertEqual(llm.calls_for("coursebook.unit_sections.validate"), 0)
        with db.read() as connection:
            sections = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?",
                (self.plan_id,),
            ).fetchone()["n"]
        self.assertEqual(int(sections), 0)


if __name__ == "__main__":
    unittest.main()
