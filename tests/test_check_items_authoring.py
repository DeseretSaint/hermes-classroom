"""The authoring half of the structured check checklist (`stimulus.items[]`).

t_4fbf0bcf closed the read seam and the renderer: a stored checklist is projected by ``check.get``
and printed once. No writer produced one, so an authored check could never carry it. These cases
close that half and prove it end to end:

* ``generation.LESSON_SCHEMA`` admits ``items[]`` with exactly the contracted shape, and refuses a
  malformed one (bad id, extra key, more than 24 entries);
* a generated verification lesson round-trips: model output → ``gen_lessons.page_json`` →
  ``checks.stimulus_json`` → ``check.get``, with the same ids, labels and order;
* a near-duplicate label is refused **at generation** by the deterministic rule (the validator is
  never called), and a verification checklist with no items is refused the same way;
* the Parent Studio learner-page projection prints each label exactly once and invents nothing.

Every case runs offline against a real migrated database through the real generation pipeline; no
provider is called.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from coursebook import db, domain
from coursebook import generation, parent_authoring as authoring

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    fixture,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def one_off_lesson(items=None, *, drop_items: bool = False) -> dict:
    """The one-off verification lesson fixture, optionally with a mutated checklist."""
    document = fixture("lesson_one_off")
    if drop_items:
        document["check"]["stimulus"].pop("items", None)
    elif items is not None:
        document["check"]["stimulus"]["items"] = items
    return document


class ChecklistAuthoringCase(KernelCase):
    """A real kernel database plus the real generation pipeline on the same connection."""

    def setUp(self) -> None:
        super().setUp()
        self.connection = db.connect()
        generation.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        super().tearDown()

    # ── pipeline helpers ────────────────────────────────────────────────────
    def author_one_off(self, lesson: dict) -> tuple[dict, str, dict, FakeLLM]:
        """Plan + approve + author lessons for the one-off (verification checklist) recipe."""
        llm = FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture("plan_one_off"),
                "coursebook.plan.validate": validation_from_fixture(),
                # A dict is returned on every call: a broken lesson stays broken, so the retry
                # path is exercised with the same bad artifact instead of a lucky second draft.
                "coursebook.lesson.generate": lesson,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        plan = generation.run_plan_job(
            self.connection,
            plan_job(recipe="one_off", dials={}, locale=None),
            llm,
            FakeSearch(),
            now=NOW,
        )
        enrollment_id = self.ok("enrollment.create", {"course_id": plan["course_id"]})["result"][
            "enrollment_id"
        ]
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
        return plan, enrollment_id, result, llm

    def stored_stimulus(self, check_id: str) -> dict:
        return json.loads(
            str(self.scalar("SELECT stimulus_json FROM checks WHERE id = ?", (check_id,)))
        )


class ChecklistSchemaTest(ChecklistAuthoringCase):
    """The generation schema admits the contracted shape and nothing wider."""

    def test_the_schema_accepts_the_contracted_checklist(self) -> None:
        lesson = one_off_lesson()
        errors = list(Draft202012Validator(generation.LESSON_SCHEMA).iter_errors(lesson))
        self.assertEqual(errors, [], [error.message for error in errors])
        items = lesson["check"]["stimulus"]["items"]
        self.assertEqual([item["id"] for item in items], ["item_1", "item_2", "item_3"])

    def test_the_schema_refuses_a_malformed_checklist(self) -> None:
        validator = Draft202012Validator(generation.LESSON_SCHEMA)
        cases = {
            "id with a space": [{"id": "item 1", "label": "Check the heat"}],
            "extra key": [{"id": "item_1", "label": "Check the heat", "done": True}],
            "empty label": [{"id": "item_1", "label": ""}],
            "too many items": [
                {"id": f"item_{index}", "label": f"Step {index}"} for index in range(1, 26)
            ],
        }
        for name, items in cases.items():
            with self.subTest(name):
                lesson = one_off_lesson(items)
                self.assertTrue(
                    list(validator.iter_errors(lesson)),
                    f"the schema accepted a checklist with {name}",
                )


class GeneratedChecklistRoundTripTest(ChecklistAuthoringCase):
    """generation → stored stimulus_json → check.get, with the same items in the same order."""

    def test_a_generated_verification_check_round_trips_to_check_get(self) -> None:
        expected = fixture("lesson_one_off")["check"]["stimulus"]["items"]
        _plan, enrollment_id, result, _llm = self.author_one_off(one_off_lesson())

        self.assertTrue(result["lessons"], "the one-off plan produced no lessons")
        self.assertEqual(result["needs_review"], [])
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "validated")
            stored = self.stored_stimulus(summary["check_id"])
            self.assertEqual(stored["format"], "verification")
            self.assertEqual(stored["items"], expected)

            served = self.ok(
                "check.get",
                {"enrollment_id": enrollment_id, "check_id": summary["check_id"]},
            )["result"]["stimulus"]
            self.assertEqual(served["items"], expected)
            self.assertEqual(served["format"], "verification")
            self.assertEqual(served["prompt"], stored["prompt"])
            self.assertEqual(len(served["items"]), 3)

            page = json.loads(
                str(
                    self.scalar(
                        "SELECT page_json FROM gen_lessons WHERE id = ?", (summary["lesson_id"],)
                    )
                )
            )
            self.assertEqual(page["check"]["stimulus"]["items"], expected)

    def test_the_lesson_prompt_asks_for_checklist_items(self) -> None:
        _plan, _enrollment, _result, llm = self.author_one_off(one_off_lesson())
        requests = [
            request
            for request in llm.requests
            if request.purpose == "coursebook.lesson.generate"
        ]
        self.assertTrue(requests)
        for request in requests:
            self.assertIn("check.stimulus.items", request.instructions)
            self.assertEqual(request.prompt_version, generation.LESSON_PROMPT_VERSION)


class ChecklistRefusedAtGenerationTest(ChecklistAuthoringCase):
    """The refusals happen while authoring, not only when the pane reads the check."""

    def test_a_near_duplicate_label_is_refused_at_generation(self) -> None:
        items = [
            {"id": "item_1", "label": "Check the heat"},
            {"id": "item_2", "label": "check  the heat."},
        ]
        _plan, _enrollment, result, llm = self.author_one_off(one_off_lesson(items))

        self.assertTrue(result["lessons"])
        self.assertEqual(result["needs_review"], [summary["section_id"] for summary in result["lessons"]])
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "needs_review")
            self.assertFalse(summary["check_enabled"])
            reasons = " ".join(summary["rejection_reasons"])
            self.assertIn("reads the same as an earlier item", reasons)
            # Refused deterministically: the independent validator never saw the broken draft.
            self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)
            self.assertEqual(
                self.scalar("SELECT state FROM checks WHERE id = ?", (summary["check_id"],)),
                "closed",
            )

    def test_a_verification_check_without_items_is_refused_at_generation(self) -> None:
        _plan, _enrollment, result, llm = self.author_one_off(one_off_lesson(drop_items=True))

        self.assertTrue(result["lessons"])
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "needs_review")
            reasons = " ".join(summary["rejection_reasons"])
            self.assertIn("must enumerate its steps in check.stimulus.items", reasons)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 0)

    def test_a_repeated_item_id_is_refused_at_generation(self) -> None:
        items = [
            {"id": "item_1", "label": "Check the heat"},
            {"id": "item_1", "label": "Check sharp objects"},
        ]
        _plan, _enrollment, result, _llm = self.author_one_off(one_off_lesson(items))
        for summary in result["lessons"]:
            self.assertEqual(summary["state"], "needs_review")
            self.assertIn("repeats 'item_1'", " ".join(summary["rejection_reasons"]))


class ParentProjectionTest(ChecklistAuthoringCase):
    """The parent-reviewed learner page prints the authored checklist once."""

    def test_each_item_label_is_printed_exactly_once_in_the_authored_order(self) -> None:
        labels = ["Pad model matched to the manual", "Worn pad removed", "Caliper undamaged"]
        page = {
            "section_title": "Replace a brake pad",
            "segments": [],
            "check": {
                "stimulus": {
                    "prompt": "Tick each step only after you have done it with the manual open.",
                    "format": "verification",
                    # A legacy choice restates an item label: it must not print a second time.
                    "choices": ["Caliper undamaged"],
                    "items": [
                        {"id": "item_1", "label": labels[0]},
                        {"id": "item_2", "label": labels[1]},
                        {"id": "item_3", "label": labels[2]},
                    ],
                },
                "learner_instructions": "Tick what is true.",
            },
        }
        text = authoring._learner_page_text(page)

        for label in labels:
            self.assertEqual(text.count(label), 1, label)
        positions = [text.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions), "the checklist lost its authored order")
        self.assertIn("1. " + labels[0], text)
        self.assertIn("3. " + labels[2], text)

    def test_a_check_without_items_prints_no_invented_labels(self) -> None:
        page = {
            "section_title": "Replace a brake pad",
            "segments": [],
            "check": {
                "stimulus": {
                    "prompt": "Tick each step only after you have done it with the manual open.",
                    "format": "verification",
                    "choices": ["Only authored choice"],
                },
                "learner_instructions": "Tick what is true.",
            },
        }
        text = authoring._learner_page_text(page)
        self.assertIn("Only authored choice", text)
        self.assertNotIn("\n1. ", text)

    def test_a_generated_page_reaches_the_projection_unchanged(self) -> None:
        expected = [item["label"] for item in fixture("lesson_one_off")["check"]["stimulus"]["items"]]
        _plan, _enrollment, result, _llm = self.author_one_off(one_off_lesson())
        summary = result["lessons"][0]
        page = json.loads(
            str(self.scalar("SELECT page_json FROM gen_lessons WHERE id = ?", (summary["lesson_id"],)))
        )
        text = authoring._learner_page_text(page)
        for label in expected:
            self.assertEqual(text.count(label), 1, label)


if __name__ == "__main__":
    unittest.main()
