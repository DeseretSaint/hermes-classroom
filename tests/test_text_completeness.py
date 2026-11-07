"""H-46: the lesson validator must reject truncated authored text (audit D8).

``docs/GENERIC-ACCEPTANCE-AUDIT.md`` D8 recorded that a lesson section whose authored body was cut
off mid-sentence (a provider truncation) passed the lesson validator and was stored as if complete:
bicycle ``"…, not."`` and soldering ``"…board repair.."``. H-38/H-22 changed copy, not validation.

These tests pin the structural signal, not a length threshold:

* every deterministic truncation shape is rejected and names its check;
* a long-but-complete body passes (the over-rejection guard: length is not a completeness test);
* the gate is wired into both readers the card names — ``enforce_unit_section_rules`` (unit-sections
  stage) and ``_enforce_lesson_document`` (the ``lesson.page`` readiness gate, through
  ``lesson_document.validate_blocks``);
* a rejection takes the *existing* route: one regeneration with the reasons, then a
  ``needs_review`` lesson with no learner-facing check enabled — and, for a unit-sections batch,
  H-42's transactional rule (no row survives, the job fails with its reasons);
* a stored page written before this rule is not newly refused by the read projection.
"""

from __future__ import annotations

import copy
import json
import unittest

from coursebook import generation as gen
from coursebook import lesson_document
from coursebook import text_completeness

from tests.blueprint_support import (
    blueprint_plan,
    response,
    unit_sections_document,
    validation_pass,
)
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import (
    FakeLLM,
    GenerationTestBase,
    NOW,
    lesson_fixture,
    validation_from_fixture,
)

CHECK = "text_completeness"


def _checks(problems: list[str]) -> set[str]:
    """The check names reported, so a test asserts the rule that spoke, not a message copy."""
    names = set()
    for problem in problems:
        for name in (
            "unclosed_code_fence",
            "empty_heading_body",
            "empty_list_item",
            "truncated_checklist",
            "repeated_terminal_punctuation",
            "dangling_terminal_word",
            "mid_sentence_end",
        ):
            if name in problem:
                names.add(name)
    return names


class CompletenessRulesTest(unittest.TestCase):
    """One deterministic truncation per structural shape, plus the over-rejection guard."""

    def problems(self, text: str, *, prose: bool = True) -> list[str]:
        return text_completeness.completeness_problems(text, where="body", prose=prose)

    def test_an_unclosed_code_fence_is_rejected(self) -> None:
        problems = self.problems("Seat the bead, then check it:\n```text\nbead seated\n")
        self.assertIn(CHECK, problems[0])
        self.assertEqual(_checks(problems), {"unclosed_code_fence"})

    def test_a_heading_with_an_empty_body_is_rejected(self) -> None:
        problems = self.problems("## Before you ride\n\n## After you ride\nThe brake holds.")
        self.assertEqual(_checks(problems), {"empty_heading_body"})
        self.assertIn("Before you ride", problems[0])

    def test_a_trailing_heading_with_no_body_is_rejected(self) -> None:
        problems = self.problems("Deflate the tyre fully.\n\n## Seat the tube")
        self.assertEqual(_checks(problems), {"empty_heading_body"})

    def test_an_empty_checklist_item_is_rejected(self) -> None:
        problems = self.problems("Tick each step:\n- [ ] Deflate\n- [ ] \n- [ ] Inflate slowly.")
        self.assertEqual(_checks(problems), {"empty_list_item"})

    def test_a_checklist_that_stops_mid_item_is_rejected(self) -> None:
        for tail in ("- release the brake and", "- seat the tube by hand,"):
            with self.subTest(tail=tail):
                problems = self.problems(f"Steps:\n- deflate the tyre\n{tail}")
                self.assertEqual(_checks(problems), {"truncated_checklist"})

    def test_a_body_that_ends_on_repeated_punctuation_is_rejected(self) -> None:
        # D8's soldering shape: the clip kept a mark and lost the rest of the sentence.
        problems = self.problems("Check the bead by hand before any board repair..")
        self.assertEqual(_checks(problems), {"repeated_terminal_punctuation"})

    def test_a_body_that_ends_on_a_dangling_word_is_rejected(self) -> None:
        # D8's bicycle shape: the terminal period survived, the complement did not.
        problems = self.problems("Seat the tube by hand and close the quick-release, not.")
        self.assertEqual(_checks(problems), {"dangling_terminal_word"})

    def test_a_body_that_loses_its_terminal_punctuation_is_rejected(self) -> None:
        problems = self.problems("Inflate the tube in small steps and check the bead")
        self.assertEqual(_checks(problems), {"mid_sentence_end"})

    def test_a_long_but_complete_body_passes(self) -> None:
        """The over-rejection guard: no length threshold stands in for completeness."""
        paragraph = (
            "Seat the new tube by hand, working around the rim in one direction so the bead never "
            "gets pinched under the tyre lever. Inflate in small steps and check the bead line on "
            "both sides after each step, because a tube that is trapped only shows itself once the "
            "pressure is high enough to push it out. "
        )
        body = "\n\n".join(paragraph * 3 for _ in range(6))
        self.assertGreater(len(body), 3000)
        self.assertEqual(self.problems(body), [])

    def test_a_deliberate_continuation_marker_passes(self) -> None:
        for marker in ("…", "...", " —", " (continued)"):
            with self.subTest(marker=marker):
                self.assertEqual(
                    self.problems(f"We come back to the bead in the next unit{marker}"), []
                )

    def test_structural_terminators_pass(self) -> None:
        cases = {
            "table": "Measure:\n\n| step | value |\n| --- | --- |\n| bead | 40 psi |",
            "fence": "Run the check:\n```text\nbead seated\n```",
            "label": "Answer: seat the tube by hand",
            "quoted": 'The manual says "seat the bead by hand."',
            "bulleted-complete": "Steps:\n- deflate the tyre\n- seat the tube",
            "japanese": "お願いしますは依頼のときに使います。",
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.problems(body), [])

    def test_a_title_is_judged_for_structure_only(self) -> None:
        # A title is a label; it owes no terminal punctuation, but a fence in it is still a cut.
        self.assertEqual(self.problems("Grade 3 — Fractions", prose=False), [])
        self.assertEqual(
            _checks(self.problems("Unit 4:\n```text\nmore", prose=False)), {"unclosed_code_fence"}
        )


class LessonDocumentGateTest(unittest.TestCase):
    """The document validator is the shared gate: authoring and ``lesson.page`` readiness."""

    def block(self, **overrides) -> dict:
        block = {
            "id": "blk_h46_00001",
            "role": "explain",
            "headline": "Seat the tube",
            "short": "Seat the tube by hand and check the bead.",
            "deep": "Seat the tube by hand, then inflate in small steps and check the bead line.",
            "check_id": None,
            "media": [],
            "source_ids": [],
        }
        block.update(overrides)
        return block

    def test_a_truncated_short_is_rejected_with_its_check_named(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks(
                [self.block(short="Seat the tube by hand and check the bead, not.")]
            )
        message = str(caught.exception)
        self.assertIn(CHECK, message)
        self.assertIn("dangling_terminal_word", message)
        self.assertIn("blocks[0].short", message)

    def test_a_truncated_deep_body_is_rejected(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks(
                [self.block(deep="Seat the tube by hand, then inflate in small steps and")]
            )
        self.assertIn("mid_sentence_end", str(caught.exception))

    def test_document_from_blocks_refuses_a_truncated_body(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError):
            lesson_document.document_from_blocks(
                [self.block(short="Seat the tube by hand and check the bead")],
                section_title="Inner tube",
            )

    def test_a_stored_page_is_not_newly_refused_by_the_read_projection(self) -> None:
        """A page written before this rule keeps projecting: no row is rewritten or newly broken."""
        page = lesson_fixture("lesson_ja")
        page["segments"][0]["short"] = "お願いしますは依頼のときに使います"  # no terminal mark
        document = lesson_document.document_from_page(page)
        self.assertEqual(document["state"], "complete")
        with self.assertRaises(lesson_document.LessonDocumentError):
            lesson_document.document_from_page(page, completeness=True)


class LessonPageReadinessTest(GenerationTestBase):
    """The lesson author's own gate: ``_enforce_lesson_document``."""

    def truncated_lesson(self, *, mode: str = "dangling") -> dict:
        lesson = lesson_fixture("lesson_ja")
        short = str(lesson["segments"][0]["short"])
        if mode == "dangling":
            lesson["segments"][0]["short"] = short.rstrip(".").rsplit(" ", 1)[0] + ", not."
        else:
            lesson["segments"][0]["short"] = short.rstrip(".")
        return lesson

    def test_the_readiness_gate_refuses_a_truncated_short(self) -> None:
        page = self.truncated_lesson()
        with self.assertRaises(gen._RuleViolation) as caught:
            gen._enforce_lesson_document(page)
        reasons = caught.exception.reasons
        self.assertTrue(any(CHECK in reason for reason in reasons), reasons)
        self.assertTrue(any("dangling_terminal_word" in reason for reason in reasons), reasons)

    def author(self, drafts: list[dict]):
        """A scripted author: each call returns the next drafted lesson, in order."""
        queue = [copy.deepcopy(item) for item in drafts]

        def build(request):
            document = queue.pop(0) if queue else copy.deepcopy(drafts[-1])
            payload = json.loads(request.input_text)
            document["section_title"] = (payload.get("section") or {}).get("title") or document[
                "section_title"
            ]
            return response(document, model="fake-author")

        return build

    def run_lessons(self, plan_result: dict, llm: FakeLLM) -> dict:
        return gen.run_lesson_job(
            self.connection,
            {"job_id": "job-h46", "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=64),
        )

    def test_one_regeneration_is_spent_and_the_complete_draft_is_stored(self) -> None:
        plan_result = self.approved_plan()
        complete = lesson_fixture("lesson_ja")
        calls = {"n": 0}

        def author(request):
            calls["n"] += 1
            document = copy.deepcopy(complete)
            payload = json.loads(request.input_text)
            document["section_title"] = (payload.get("section") or {}).get("title") or document[
                "section_title"
            ]
            # First draft for each section is truncated; the regeneration is complete.
            if calls["n"] % 2 == 1:
                short = str(document["segments"][0]["short"])
                document["segments"][0]["short"] = short.rstrip(".").rsplit(" ", 1)[0] + ", not."
            return response(document, model="fake-author")

        llm = FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        result = self.run_lessons(plan_result, llm)
        generated = [
            request for request in llm.requests if request.purpose == "coursebook.lesson.generate"
        ]
        self.assertEqual(len(generated), 8)  # 4 sections x (rejected draft + regeneration)
        # The regeneration carries the check's reasons in its revision instructions, so the retry
        # is targeted, not blind.
        revision = json.loads(generated[1].input_text).get("revision_instructions") or ""
        self.assertIn(CHECK, revision)
        self.assertIn("dangling_terminal_word", revision)
        # The retry cleared the truncation everywhere: no lesson left review *for completeness*,
        # and every lesson that passed spent exactly one independent validation call.
        self.assertFalse(
            any(
                CHECK in reason
                for item in result["lessons"]
                for reason in (item.get("rejection_reasons") or [])
            ),
            result["lessons"],
        )
        self.assertEqual(
            llm.calls_for("coursebook.lesson.validate"),
            len([item for item in result["lessons"] if item["state"] == "validated"]),
        )
        self.assertTrue(any(item["state"] == "validated" for item in result["lessons"]))

    def test_a_second_truncation_parks_the_lesson_needs_review_with_no_check_enabled(self) -> None:
        plan_result = self.approved_plan()
        complete = lesson_fixture("lesson_ja")
        truncated = copy.deepcopy(complete)
        short = str(truncated["segments"][0]["short"])
        truncated["segments"][0]["short"] = short.rstrip(".").rsplit(" ", 1)[0] + ", not."

        def author(request):
            document = copy.deepcopy(truncated)
            payload = json.loads(request.input_text)
            document["section_title"] = (payload.get("section") or {}).get("title") or document[
                "section_title"
            ]
            return response(document, model="fake-author")

        llm = FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        result = self.run_lessons(plan_result, llm)
        self.assertEqual(llm.calls_for("coursebook.lesson.generate"), 8)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
        self.assertEqual(len(result["lessons"]), 4)
        self.assertEqual(result["needs_review"], [item["section_id"] for item in result["lessons"]])
        for item in result["lessons"]:
            self.assertEqual(item["state"], "needs_review")
            self.assertFalse(item["check_enabled"])
            self.assertTrue(any(CHECK in reason for reason in item["rejection_reasons"]))
        with self.assertRaises(gen.LessonNotAvailable):
            gen.learner_page(self.connection, result["lessons"][0]["lesson_id"])
        for row in self.rows("SELECT state, audit_state FROM checks"):
            self.assertEqual((row["state"], row["audit_state"]), ("closed", "failed"))


class UnitSectionsCompletenessTest(UnitStageCase):
    """The unit-sections stage: a truncated ``lesson_intent`` is a truncated authored batch."""

    def section_document(self, plan: dict, *, truncate: bool) -> dict:
        unit = self.unit(plan, 1)
        objectives = self.objectives_for(plan, 1)
        reviews = max(0, int(unit["target_lessons"]) - len(objectives))
        document = unit_sections_document(unit=unit, objectives=objectives, reviews=reviews)
        if truncate:
            for section in document["sections"]:
                intent = str(section["lesson_intent"])
                section["lesson_intent"] = " ".join(intent.split()[:4])
        return document

    def test_enforce_unit_section_rules_rejects_a_truncated_intent(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        unit = self.unit(plan, 1)
        objectives = self.objectives_for(plan, 1)
        document = self.section_document(plan, truncate=True)
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_unit_section_rules(
                document["sections"],
                unit=unit,
                objectives=objectives,
                plan=plan,
                recipe="casual",
                dials={},
                locale=None,
                ledger=[],
            )
        reasons = caught.exception.reasons
        self.assertTrue(any(CHECK in reason for reason in reasons), reasons)
        self.assertTrue(any("lesson_intent" in reason for reason in reasons), reasons)

    def test_a_truncated_batch_is_regenerated_once_then_discarded(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, plan_id = self.seed(plan)
        truncated = self.section_document(plan, truncate=True)
        complete = self.section_document(plan, truncate=False)
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": [response(truncated), response(complete)],
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        result = gen.run_unit_sections_job(
            self.connection_of(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=NOW,
        )
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        generated = [
            request
            for request in llm.requests
            if request.purpose == "coursebook.unit_sections.generate"
        ]
        self.assertIn(CHECK, generated[1].instructions)
        self.assertEqual(result["sections"], 1)

    def test_two_truncated_batches_leave_no_section_row(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        _course_id, plan_id = self.seed(plan)
        truncated = self.section_document(plan, truncate=True)
        llm = FakeLLM(
            {"coursebook.unit_sections.generate": response(truncated)},
        )
        with self.assertRaises(gen.GenerationRejected) as caught:
            gen.run_unit_sections_job(
                self.connection_of(),
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                llm,
                plan_id=plan_id,
                unit_ordinal=1,
                now=NOW,
            )
        self.assertIn(CHECK, str(caught.exception))
        self.assertEqual(llm.calls_for("coursebook.unit_sections.generate"), 2)
        self.assertEqual(self.section_rows(plan_id), 0)

    # ── helpers ─────────────────────────────────────────────────────────────
    def connection_of(self):
        from coursebook import db

        return db.connect()

    def section_rows(self, plan_id: str) -> int:
        from coursebook import db

        with db.read() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?", (plan_id,)
            ).fetchone()
        return int(row["n"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
