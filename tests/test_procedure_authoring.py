"""H-06 — the M4 procedure lens is reachable from generation, not fixture-only.

P0-6 of ``docs/ADVERSARIAL-HARNESS-REVIEW.md``: the renderer, contract and document validator
existed, but no authoring path could produce the typed ``procedure`` header, so the technical lens
was unreachable from a model-generated course.

These tests drive the real lesson job with a fake (recorded) model and prove:

1. a technical procedure lesson authored by the pipeline is served with the header, its hazards,
   numbered step references to real blocks, schematic rows and the source card;
2. the header is refused on a lesson that is not a technical procedure;
3. an unsourced schematic row (no cited source, no recorded source text, or a value the source
   does not contain) is refused;
4. pages written before the header existed still project unchanged;
5. the prompt asks for the header only where it belongs, and the version is bumped.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from coursebook import generation as gen
from coursebook import lesson_document
from coursebook import policy
from coursebook import rubrics
from coursebook.research import SourceRecord

from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    response,
    validation_from_fixture,
)
from tests.test_lesson_document import page_fixture

NOW = datetime(2026, 11, 7, 16, 0, tzinfo=timezone.utc)

TORQUE_TEXT = (
    "Caliper mounting fastener: tighten to 40 Nm in a star pattern. "
    "Pad model BR-42 uses a 5 mm hex key. Never let the caliper hang by the hose. "
) * 6

PAD_SOURCE = FakeSearch(
    {
        "https://example.org/brake-manual": {
            "title": "Brake pad service manual",
            "publisher": "example.org",
            "published_at": "2025-02-01",
            "content": TORQUE_TEXT,
        }
    }
)


def pad_ledger(*, excerpt: str = TORQUE_TEXT) -> list[SourceRecord]:
    return [
        SourceRecord(
            source_id="src_padmanual1",
            url="https://example.org/brake-manual",
            title="Brake pad service manual",
            publisher="example.org",
            source_type="documentation",
            fetched_at="2026-11-07T00:00:00+00:00",
            published_at="2025-02-01",
            content_hash="sha256:deadbeef",
            excerpt=excerpt,
        )
    ]


def build_request(*, evidence_target: str = "procedure", recipe: str = "one_off",
                  intent: str = "Replace a brake pad.", ledger=None) -> gen.LLMRequest:
    return gen.build_lesson_request(
        plan={"title": "Course", "learner_outcome": "Outcome", "delivery": "self_study"},
        section={"title": "Section", "lesson_intent": intent, "ordinal": 1},
        objective={"id": "obj_1", "ordinal": 1, "evidence_target": evidence_target},
        recipe=recipe,
        dials={},
        locale=None,
        sources=pad_ledger() if ledger is None else ledger,
    )


def parsed_lesson(request: gen.LLMRequest) -> dict:
    parsed = procedure_lesson(request).parsed
    assert isinstance(parsed, dict), "the fake author produced no parsed lesson"
    return parsed


def _rubric(profile: str) -> list[dict]:
    entry = rubrics.get_profile(profile)
    return [
        {"criterion": criterion.label, "weight": 1.0, "description": criterion.observation}
        for criterion in entry.criteria
    ]


def procedure_lesson(request: gen.LLMRequest) -> gen.LLMResponse:
    """A schema-valid one-off procedure lesson, citing the ledger source the request carries."""
    payload = json.loads(request.input_text)
    section = payload.get("section") or {}
    source_ids = [
        item["source_id"] for item in payload.get("sources") or [] if item.get("source_id")
    ]
    source_id = source_ids[0]
    lesson = {
        "section_title": section.get("title") or "Replace a brake pad",
        "segments": [
            {
                "kind": "model",
                "heading": "Match the pad to the manual",
                "body": (
                    "Find the pad model in the manufacturer's manual before touching the brake. "
                    "The manual names the pad as BR-42 and the fastener's 5 mm hex key."
                ),
                "short": "Find the pad model in the manual before touching the brake.",
            },
            {
                "kind": "guided",
                "heading": "Remove the worn pad",
                "body": (
                    "Hold the caliper steady and loosen only the fastener the manual names, then "
                    "slide the worn pad out while the caliper is supported by hand."
                ),
                "short": "Loosen only the named fastener and slide the worn pad out.",
            },
        ],
        "worked_example": {
            "prompt": "The manual lists pad model BR-42 and the listed key.",
            "steps": [
                "Lay out the new pad and the listed key",
                "Confirm the pad model matches the manual",
                "Loosen the fastener and slide the worn pad out",
            ],
            "answer": "The worn pad is removed with the listed key.",
            "short": "Lay out the pad and key, then loosen the fastener and slide the pad out.",
        },
        "learner_explanation": (
            "Work through the checklist with the manual open. This is a verification list, not a "
            "quiz: you confirm each step honestly."
        ),
        "learner_explanation_short": "Work through the checklist with the manual open and answer honestly.",
        "check": {
            "kind": "verification",
            "stimulus": {
                "prompt": "Tick each step only after you have done it with the manual open.",
                "format": "verification",
                "choices": [],
                "items": [
                    {"id": "item_1", "label": "Pad model matched to the manual"},
                    {"id": "item_2", "label": "Worn pad removed with the listed tool"},
                    {"id": "item_3", "label": "Caliper undamaged"},
                ],
            },
            "learner_instructions": "Tick what is true. Completion is self-reported, never verified.",
            "evidence_target": "procedure",
            "accepted_answers": ["all three steps ticked honestly"],
            "accepted_alternatives": [],
            "rubric": _rubric("procedural"),
            "reference_answer": "every checklist item confirmed against the manual",
            "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
            "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
        },
        "sources": [source_id],
        "media": [],
        "parent_notes": None,
        "supervision_notes": [],
        "procedure": {
            "tools": ["5 mm hex key", "torque wrench"],
            "parts": ["Brake pad set BR-42"],
            "hazards": ["The caliper must never hang from the brake hose."],
            "stop_condition": "Stop if the caliper moves or the fastener will not turn by hand.",
            "steps": [
                {"segment": 1, "check": "Manual open at the pad model page"},
                {"segment": 2, "check": "Fastener turns with the listed key only"},
            ],
            "schematic": {
                "title": "Caliper mounting fastener",
                "text_equivalent": "The mounting fastener is tightened to 40 Nm in a star pattern.",
                "source_id": source_id,
                "rows": [
                    {"label": "Mounting fastener", "value": "40 Nm", "row": 1},
                    {"label": "Pad model", "value": "BR-42", "row": 2},
                ],
            },
            "source": {"source_id": source_id, "permission": "public_domain"},
        },
    }
    return response(lesson, model="fake-author")


def technical_capability() -> policy.LessonCapabilityPlan:
    return policy.plan_lesson_capability(
        recipe="one_off",
        evidence_target="procedure",
        lesson_intent="Follow the manual's sequence to replace a brake pad.",
        locale=None,
    )


def non_technical_capability() -> policy.LessonCapabilityPlan:
    return policy.plan_lesson_capability(
        recipe="committed",
        evidence_target="comprehension",
        lesson_intent="Describe what a head gasket does in general terms.",
        locale=None,
    )


def procedure_problems(lesson: dict, capability, *, declared_target: str, ledger=None) -> list[str]:
    return gen.lesson_procedure_problems(
        lesson,
        capability=capability,
        declared_target=declared_target,
        sources=ledger,
    )


class GeneratedProcedureLessonTest(GenerationTestBase):
    """The real lesson job authors and serves a procedure header."""

    def author(self) -> tuple[dict, dict]:
        plan = self.approved_plan(
            fixture_name="plan_one_off",
            recipe="one_off",
            locale=None,
            search=PAD_SOURCE,
        )
        llm = FakeLLM(
            {
                "coursebook.lesson.generate": procedure_lesson,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        result = gen.run_lesson_job(
            self.connection,
            {"job_id": "job-procedure-1", "kind": "plan", "brief": {"plan_id": plan["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )
        return plan, result

    def test_every_generated_section_is_validated_with_the_header(self) -> None:
        _plan, result = self.author()
        self.assertTrue(result["lessons"])
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "validated", summary)
            page = gen.learner_page(self.connection, summary["lesson_id"])
            document = page["document"]
            procedure = document["procedure"]
            self.assertEqual(procedure["tools"], ["5 mm hex key", "torque wrench"])
            self.assertEqual(procedure["parts"], ["Brake pad set BR-42"])
            self.assertIn("never hang", " ".join(procedure["hazards"]))
            self.assertIn("Stop if", procedure["stop_condition"])
            self.assertEqual(procedure["source"]["permission"], "public_domain")

            # Numbered steps are ordered references to real projected blocks, not a second copy.
            block_ids = [block["id"] for block in document["blocks"]]
            step_ids = [step["block_id"] for step in procedure["steps"]]
            self.assertEqual(len(step_ids), 2)
            for step_id in step_ids:
                self.assertIn(step_id, block_ids)
            self.assertEqual(
                [block["id"] for block in document["blocks"][:2]], step_ids
            )
            self.assertEqual(document["blocks"][0]["deep"], page["segments"][0]["body"])
            self.assertEqual(document["blocks"][1]["deep"], page["segments"][1]["body"])

            # The table is the only place a measurement lives, and it is source-visible.
            self.assertEqual(procedure["schematic"]["title"], "Caliper mounting fastener")
            self.assertEqual(
                [(row["label"], row["value"]) for row in procedure["schematic"]["rows"]],
                [("Mounting fastener", "40 Nm"), ("Pad model", "BR-42")],
            )
            self.assertIn(procedure["schematic"]["source_id"], document["source_ids"])
            self.assertIn(
                procedure["source"]["source_id"],
                [source["source_id"] for source in page["sources"]],
            )

    def test_the_stored_page_keeps_segment_ordinals_and_no_block_ids(self) -> None:
        _plan, result = self.author()
        row = self.connection.execute(
            "SELECT page_json FROM gen_lessons WHERE id = ?", (result["lessons"][0]["lesson_id"],)
        ).fetchone()
        page = json.loads(row["page_json"])
        self.assertIn("procedure", page)
        self.assertEqual([step["segment"] for step in page["procedure"]["steps"]], [1, 2])
        self.assertNotIn("block_id", json.dumps(page["procedure"]))

    def test_the_served_document_is_deterministic(self) -> None:
        _plan, result = self.author()
        lesson_id = result["lessons"][0]["lesson_id"]
        first = gen.learner_page(self.connection, lesson_id)["document"]
        second = gen.learner_page(self.connection, lesson_id)["document"]
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(first["document_id"], second["document_id"])
        # The projected document re-validates on its own.
        lesson_document.validate_document(first)


class ProcedureGateTest(unittest.TestCase):
    """Deterministic refusals: the header cannot appear where it does not belong."""

    def base_lesson(self) -> dict:
        request = build_request()
        return parsed_lesson(request)

    def test_a_non_procedure_lesson_carrying_a_procedure_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"] = dict(lesson["procedure"])
        reasons = procedure_problems(
            lesson, non_technical_capability(), declared_target="comprehension"
        )
        self.assertTrue(
            any("only valid for a technical procedure lesson" in reason for reason in reasons),
            reasons,
        )

    def test_the_same_header_is_accepted_on_a_procedure_lesson(self) -> None:
        lesson = self.base_lesson()
        self.assertEqual(
            procedure_problems(lesson, technical_capability(), declared_target="procedure"), []
        )

    def test_a_step_that_names_no_segment_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"]["steps"] = [{"segment": 3}]
        reasons = procedure_problems(lesson, technical_capability(), declared_target="procedure")
        self.assertTrue(any("refers to no lesson segment" in reason for reason in reasons), reasons)

    def test_a_step_cue_that_copies_the_segment_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"]["steps"][0]["check"] = lesson["segments"][0]["body"]
        reasons = procedure_problems(lesson, technical_capability(), declared_target="procedure")
        self.assertTrue(
            any("must not be copied into the header" in reason for reason in reasons), reasons
        )

    def test_a_missing_source_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"].pop("source")
        reasons = procedure_problems(lesson, technical_capability(), declared_target="procedure")
        self.assertTrue(any("procedure.source is missing" in reason for reason in reasons), reasons)

    def test_a_source_the_lesson_does_not_cite_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"]["source"]["source_id"] = "src_uncited01"
        reasons = procedure_problems(lesson, technical_capability(), declared_target="procedure")
        self.assertTrue(
            any("is not in lesson.sources" in reason for reason in reasons), reasons
        )

    def test_an_unknown_permission_is_rejected(self) -> None:
        lesson = self.base_lesson()
        lesson["procedure"]["source"]["permission"] = "unknown"
        reasons = procedure_problems(lesson, technical_capability(), declared_target="procedure")
        self.assertTrue(any("permission" in reason for reason in reasons), reasons)


class UnsourcedSchematicTest(unittest.TestCase):
    """An illustration is never the authority: every row needs the cited source behind it."""

    def lesson(self) -> dict:
        request = build_request()
        return parsed_lesson(request)

    def ledger(self, *, excerpt: str = TORQUE_TEXT) -> list:
        return pad_ledger(excerpt=excerpt)

    def test_a_schematic_source_outside_the_lesson_is_rejected(self) -> None:
        lesson = self.lesson()
        lesson["procedure"]["schematic"]["source_id"] = "src_other00001"
        reasons = procedure_problems(
            lesson, technical_capability(), declared_target="procedure", ledger=self.ledger()
        )
        self.assertTrue(
            any("is not in lesson.sources" in reason for reason in reasons), reasons
        )

    def test_a_row_value_the_source_does_not_contain_is_rejected(self) -> None:
        lesson = self.lesson()
        lesson["procedure"]["schematic"]["rows"][0]["value"] = "95 Nm"
        reasons = procedure_problems(
            lesson, technical_capability(), declared_target="procedure", ledger=self.ledger()
        )
        self.assertTrue(
            any("does not appear in the recorded text" in reason for reason in reasons), reasons
        )

    def test_a_source_with_no_recorded_text_cannot_back_a_row(self) -> None:
        lesson = self.lesson()
        reasons = procedure_problems(
            lesson, technical_capability(), declared_target="procedure", ledger=self.ledger(excerpt="")
        )
        self.assertTrue(
            any("has no recorded source text" in reason for reason in reasons), reasons
        )

    def test_the_same_rows_are_accepted_against_the_real_source_text(self) -> None:
        lesson = self.lesson()
        self.assertEqual(
            procedure_problems(
                lesson, technical_capability(), declared_target="procedure", ledger=self.ledger()
            ),
            [],
        )


class ProcedureSchemaTest(unittest.TestCase):
    """The authored shape is closed, bounded and optional."""

    def test_the_schema_accepts_the_authored_shape(self) -> None:
        lesson = parsed_lesson(build_request())
        errors = list(Draft202012Validator(gen.LESSON_SCHEMA).iter_errors(lesson))
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_the_schema_refuses_unknown_fields_and_free_prose_steps(self) -> None:
        original = parsed_lesson(build_request())
        validator = Draft202012Validator(gen.LESSON_SCHEMA)
        cases = {
            "extra header key": lambda lesson: lesson["procedure"].__setitem__("narrative", "x"),
            "free prose step": lambda lesson: lesson["procedure"]["steps"].append(
                {"text": "Loosen the fastener"}
            ),
            "unknown permission": lambda lesson: lesson["procedure"]["source"].__setitem__(
                "permission", "unknown"
            ),
            "schematic without rows": lambda lesson: lesson["procedure"]["schematic"].__setitem__(
                "rows", []
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                lesson = json.loads(json.dumps(original))
                mutate(lesson)
                self.assertTrue(
                    list(validator.iter_errors(lesson)),
                    f"the schema accepted {name}",
                )

    def test_a_lesson_without_a_procedure_still_validates(self) -> None:
        lesson = parsed_lesson(
            build_request(
                evidence_target="comprehension",
                recipe="committed",
                intent="Describe a gasket in general terms.",
            )
        )
        lesson.pop("procedure")
        self.assertEqual(list(Draft202012Validator(gen.LESSON_SCHEMA).iter_errors(lesson)), [])


class ProcedurePromptTest(unittest.TestCase):
    def test_the_prompt_asks_for_the_header_only_on_a_technical_procedure(self) -> None:
        technical = build_request()
        self.assertIn("'procedure' header", technical.instructions)
        self.assertIn("1-based index of the segment", technical.instructions)
        self.assertIn("never restate a step in prose", technical.instructions)
        self.assertIn("verbatim in the cited source's supplied text", technical.instructions)
        self.assertIn("procedure", json.loads(technical.input_text)["rules"])

        ordinary = build_request(
            evidence_target="comprehension",
            recipe="committed",
            intent="Derive the quadratic formula by completing the square.",
        )
        self.assertIn("Do not include a 'procedure' header", ordinary.instructions)
        self.assertNotIn("1-based index of the segment", ordinary.instructions)

    def test_the_lesson_prompt_version_is_bumped(self) -> None:
        self.assertEqual(gen.LESSON_PROMPT_VERSION, "lesson-prompt.v7")


class LegacyPageTest(unittest.TestCase):
    """A page written before the header existed projects exactly as it did."""

    def test_a_page_without_a_procedure_still_renders(self) -> None:
        page = page_fixture()
        document = lesson_document.document_from_page(page, check_id="chk_lesson01")
        self.assertNotIn("procedure", document)
        lesson_document.validate_document(document)
        again = lesson_document.document_from_page(page, check_id="chk_lesson01")
        self.assertEqual(document["content_hash"], again["content_hash"])

    def test_a_page_level_step_outside_the_projected_blocks_is_refused(self) -> None:
        page = page_fixture()
        page["procedure"] = {
            "tools": [],
            "parts": [],
            "hazards": ["No hazards apply."],
            "stop_condition": "Stop if anything is unclear.",
            "steps": [{"segment": 9}],
            "schematic": None,
            "source": {"source_id": "src_alpha01", "permission": "public_domain"},
        }
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.document_from_page(page, check_id="chk_lesson01")
        self.assertTrue(
            any("refers to no projected block" in problem for problem in caught.exception.problems),
            caught.exception.problems,
        )


if __name__ == "__main__":
    unittest.main()
