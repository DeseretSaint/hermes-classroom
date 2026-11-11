"""H-20: every stored check declares its grading lane, and generated checks are gradable.

Measured defect (`docs/ASSESSMENT-BREADTH.md` §2.2, §11 B-1): ``generation._check_payloads``
wrote ``reference_answer``/``accepted_answers``/``accepted_alternatives`` with **no kind**, so the
grading router fell through to the open lane, which this build never configures. Every generated
lesson therefore persisted ``needs_retry`` and nothing advanced.

These cases prove the frozen lane mapping in ``docs/GRADING-LANES.md`` against a real migrated
database and the real command path (``check.open`` -> ``attempt.submit``):

* a generated quiz (text and selection formats) stores ``kind: exact`` over every declared correct
  form, and a right answer passes as ``cold`` while a wrong answer is ``not_yet`` with no advance;
* a generated verification checklist declares ``rubric_only`` explicitly and stays ungraded — the
  recorded decision, not an accidental fallthrough;
* no generated or pack-imported reference can lack a kind: ``check.open`` refuses one, and the
  grader treats a missing kind as a grader failure rather than an open response;
* the frozen chat directive (`docs/ASSESSMENT-BREADTH.md` §7.4) is in both prompt constants.

No provider is called.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from coursebook import db, domain, grading, pack_flow, turn, validators
from coursebook import generation

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    check_for_objective,
    fixture,
    plan_from_fixture,
    plan_job,
    response,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def authored_lesson(name: str = "lesson_ja", mutate=None):
    """Build the same lesson for every section, with an optional authoring mutation."""

    def build(request: generation.LLMRequest) -> generation.LLMResponse:
        payload = json.loads(request.input_text)
        section = payload.get("section") or {}
        objective = payload.get("objective") or {}
        lesson = fixture(name)
        lesson["section_title"] = section.get("title") or lesson["section_title"]
        check_for_objective(lesson, objective)
        if mutate is not None:
            mutate(lesson)
        return response(lesson, model="fake-author")

    return build


def as_text_check(lesson: dict) -> None:
    lesson["check"]["stimulus"] = {
        "prompt": "Write the greeting you would use with shop staff.",
        "format": "text",
        "choices": [],
    }


class GradingLaneCase(KernelCase):
    """A real profile database plus the real generation pipeline on the same connection."""

    def setUp(self) -> None:
        super().setUp()
        self.connection = db.connect()
        generation.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        super().tearDown()

    # ── pipeline helpers ────────────────────────────────────────────────────
    def author(self, *, plan_name: str = "plan_ja", recipe: str = "committed",
               lesson_name: str = "lesson_ja", mutate=None) -> dict:
        llm = FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture(plan_name),
                "coursebook.plan.validate": validation_from_fixture(),
                "coursebook.lesson.generate": authored_lesson(lesson_name, mutate),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        plan = generation.run_plan_job(
            self.connection,
            plan_job(recipe=recipe, dials={}, locale=None),  # type: ignore[arg-type]
            llm,
            FakeSearch(),
            now=NOW,
        )
        enrollment_id = self.ok("enrollment.create", {"course_id": plan["course_id"]})[
            "result"
        ]["enrollment_id"]
        self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan["plan_id"],
                "plan_hash": domain.plan_hash(plan["plan_id"]),
            },
            expected_revision=0,
        )
        result = generation.run_lesson_job(
            self.connection,
            {"job_id": "job-lesson-1", "kind": "plan", "brief": {"plan_id": plan["plan_id"]}},
            llm,
            now=NOW,
            budget=generation.CostBudget(max_calls=64),
        )
        self.assertEqual(result["needs_review"], [], result["needs_review"])
        return {"plan": plan, "enrollment_id": enrollment_id, "lessons": result["lessons"]}

    def open_generated(self, authored: dict, index: int = 0) -> dict:
        summary = authored["lessons"][index]
        objective_id = self.scalar(
            "SELECT objective_id FROM checks WHERE id = ?", (summary["check_id"],)
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": authored["enrollment_id"], "objective_id": objective_id},
            expected_revision=self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (authored["enrollment_id"],)
            ),
        )["result"]
        opened["enrollment_id"] = authored["enrollment_id"]
        opened["objective_id"] = objective_id
        return opened

    def stored_reference(self, check_id: str) -> dict:
        return json.loads(str(self.scalar(
            "SELECT reference_json FROM checks WHERE id = ?", (check_id,)
        )))

    def submit_answer(self, opened: dict, answer: dict, *, key: str = "key-lane-1") -> dict:
        response_envelope = self.dispatch(
            "attempt.submit",
            {
                "enrollment_id": opened["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": f"nonce-{key}",
                "answer": answer,
            },
            expected_revision=opened["revision"],
            idempotency_key=key,
        )
        self.assertTrue(response_envelope["ok"], response_envelope.get("error"))
        return response_envelope["result"]


class GeneratedCheckIsClosedTest(GradingLaneCase):
    """A generated quiz is closed-form, and its lane is stored, not inferred."""

    def test_text_quiz_right_answer_passes_cold_and_completes(self) -> None:
        authored = self.author(mutate=as_text_check)
        opened = self.open_generated(authored)
        reference = self.stored_reference(opened["check_id"])
        self.assertEqual(reference["kind"], "exact")
        self.assertIn("こんにちは", reference["answers"])
        self.assertIn("konnichiwa", reference["answers"])

        result = self.submit_answer(opened, {"kind": "text", "text": "こんにちは"})
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["next_action"], "complete_objective")
        self.assertEqual(result["evidence_class"], "cold")

    def test_text_quiz_wrong_answer_is_not_yet_and_advances_nothing(self) -> None:
        authored = self.author(mutate=as_text_check)
        opened = self.open_generated(authored)
        result = self.submit_answer(opened, {"kind": "text", "text": "さようなら"})
        self.assertEqual(result["verdict"], "not_yet")
        self.assertEqual(result["next_action"], "retry_attempt")
        # No advance: the check stays open and the objective never reaches independent evidence.
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )
        self.assertNotEqual(
            self.scalar(
                "SELECT state FROM objectives WHERE id = ?", (opened["objective_id"],)
            ),
            "independent_evidence",
        )

    def test_selection_quiz_grades_the_typed_choice(self) -> None:
        """The pane shows choices as text and submits what was typed; exact grades that."""
        authored = self.author()
        opened = self.open_generated(authored)
        reference = self.stored_reference(opened["check_id"])
        self.assertEqual(reference["kind"], "exact")
        result = self.submit_answer(opened, {"kind": "text", "text": "こんにちは"})
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["next_action"], "complete_objective")
        self.assertEqual(result["evidence_class"], "cold")

    def test_every_generated_check_declares_a_known_lane(self) -> None:
        authored = self.author()
        rows = self.rows("SELECT id, reference_json FROM checks")
        self.assertTrue(rows)
        for row in rows:
            reference = json.loads(str(row["reference_json"]))
            with self.subTest(check=row["id"]):
                self.assertIn(reference.get("kind"), validators.REFERENCE_KINDS)

    def test_an_accepted_alternative_also_passes(self) -> None:
        authored = self.author(mutate=as_text_check)
        opened = self.open_generated(authored)
        result = self.submit_answer(opened, {"kind": "text", "text": "konnichiwa"})
        self.assertEqual(result["verdict"], "pass")


class VerificationCheckIsSelfReportedTest(GradingLaneCase):
    """Frozen decision: a checklist is self-reported, not compared to a typed string."""

    def test_verification_reference_declares_rubric_only(self) -> None:
        authored = self.author(
            plan_name="plan_one_off", recipe="one_off", lesson_name="lesson_one_off"
        )
        opened = self.open_generated(authored)
        reference = self.stored_reference(opened["check_id"])
        self.assertEqual(reference["kind"], "rubric_only")
        stimulus = json.loads(str(self.scalar(
            "SELECT stimulus_json FROM checks WHERE id = ?", (opened["check_id"],)
        )))
        self.assertEqual(stimulus["format"], "verification")

    def test_a_self_report_answer_is_not_graded_and_advances_nothing(self) -> None:
        authored = self.author(
            plan_name="plan_one_off", recipe="one_off", lesson_name="lesson_one_off"
        )
        opened = self.open_generated(authored)
        result = self.submit_answer(opened, {"kind": "text", "text": "done"})
        self.assertEqual(result["verdict"], "needs_retry")
        self.assertEqual(result["next_action"], "retry_grading")
        self.assertEqual(result["revision"], int(opened["revision"]))


class MissingKindIsImpossibleTest(GradingLaneCase):
    """A reference without a kind is a writer bug, refused before a learner sees it."""

    def test_check_open_refuses_a_spec_without_a_lane(self) -> None:
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(
            plan_id,
            {
                "audit_state": "passed",
                "stimulus": {"prompt": "Compute the answer."},
                "reference": {"value": "4", "tolerance": {"abs": "0"}},
                "rubric": {
                    "construct": "procedure",
                    "pass_rule": "all",
                    "criteria": [{"id": "c1", "description": "Correct value"}],
                },
            },
        )
        enrollment_id = self.new_enrollment(course_id)
        self.approve(enrollment_id, plan_id, 0)
        error = self.err(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=1,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "check_not_gradable")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM checks"), 0)

    def test_grading_a_reference_without_a_kind_is_a_grader_failure(self) -> None:
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(
                reference={"answers": ["4"]},
                rubric=None,
                stimulus=None,
                answer={"kind": "text", "text": "4"},
                attempt_id="att-lane",
            )

    def test_seal_reference_requires_a_declared_lane(self) -> None:
        with self.assertRaises(validators.ReferenceSpecError):
            validators.seal_reference({"answers": ["4"]})
        sealed = validators.seal_reference({"kind": "exact", "answers": ["4"]})
        self.assertEqual(sealed["kind"], "exact")

    def test_generated_writer_seals_every_reference(self) -> None:
        """The generated write path always emits a sealed reference, even for a minimal check."""
        payload = generation._reference_payload(
            {"reference_answer": "4", "accepted_answers": ["4"]}
        )
        self.assertEqual(payload["kind"], "exact")
        self.assertEqual(payload["answers"], ["4"])


class PackImportLaneTest(unittest.TestCase):
    """Pack import declares its lane too: closed when closed, recorded open otherwise."""

    def pack_check(self, target: str) -> dict:
        return {
            "stimulus": "What is 2 + 2?",
            "reference_answer": "4",
            "accepted_alternatives": ["four"],
            "rubric": ["Correct sum"],
            "evidence_target": target,
        }

    def test_closed_target_gets_an_exact_reference(self) -> None:
        spec = pack_flow.check_spec_from_pack_check(self.pack_check("recall"), recipe="committed")
        assert spec is not None
        self.assertEqual(spec["reference"]["kind"], "exact")
        self.assertEqual(spec["reference"]["answers"], ["4", "four"])

    def test_production_and_transfer_declare_the_open_lane_explicitly(self) -> None:
        for target in ("production", "transfer"):
            with self.subTest(target=target):
                spec = pack_flow.check_spec_from_pack_check(
                    self.pack_check(target), recipe="committed"
                )
                assert spec is not None
                self.assertEqual(spec["reference"], {"kind": "rubric_only"})


class FrozenChatDirectiveTest(unittest.TestCase):
    """`docs/ASSESSMENT-BREADTH.md` §7.4, in both prompt constants."""

    def test_lesson_author_instructions_carry_the_rule(self) -> None:
        text = generation._lesson_instructions(recipe="committed", locale=None, scaffold_note="")
        self.assertIn("Never claim that Coursebook ran code, heard a recording", text)
        self.assertIn("verdicts come only from the check surface", text)

    def test_continuation_prompt_carries_the_rule(self) -> None:
        text = turn.continuation_prompt(
            verdict="pass", next_action="complete_objective", evidence_class="cold"
        )
        self.assertIn("Never claim that Coursebook ran code, heard a recording", text)
        self.assertIn("verdicts come only from the check surface", text)


if __name__ == "__main__":
    unittest.main()
