"""Item 28b — the figure's own drawn labels, from the wire to the served page.

The picture is generated textless (``media.lesson_illustration_prompt``): a model that paints text
garbles it into a false fact. So the words a learner reads over a figure are *page text* the UI
draws, and they have to travel on the wire. ``cb.rpc`` v27 adds one optional
``$defs/lesson_document_media.labels`` array for exactly that.

These tests pin the four things that make it real rather than declared:

* the projection carries a valid label list and refuses one that breaks the contract's bounds
  (>8 labels, text over 40 characters, a fraction outside 0–1);
* a media child with **no** labels keeps its exact pre-v27 shape — no manufactured empty array —
  and stays valid against the frozen v26 document;
* **reach:** a stored page whose media child carries two labels passes
  ``validate_response_payload`` for ``lesson.page`` and the route returns them intact, with the
  document's own media child carrying them too;
* a label that restates the check's reference answer or an accepted answer is refused by the one
  answer-leak scan (``assert_no_answer_leak`` over ``narrative_text``), not by a second rule.
"""

from __future__ import annotations

import json
import unittest

from jsonschema import Draft202012Validator

from coursebook import contracts, db, domain, generation, lesson_document
from tests.kernel_support import KernelCase, numeric_spec

LABELS = [
    {"text": "Jaws", "x": 0.28, "y": 0.74, "anchor": "start"},
    {"text": "Workpiece", "x": 0.62, "y": 0.41, "anchor": "center"},
]


def validate_against_v26(document: dict) -> None:
    """Validate a document against the *frozen* v26 wire, not the live one."""
    v26 = contracts.contract_as("cb.rpc", 26)
    validator = Draft202012Validator(
        {**v26, "$ref": "#/$defs/lesson_document"}, registry=contracts.registry()
    )
    errors = list(validator.iter_errors(document))
    if errors:
        raise contracts.ContractError(errors[0].message, contract_id="cb.rpc", path="")


def page_with_labels(labels: list[dict] | None) -> dict:
    """A stored ``gen_lessons.page_json`` shape carrying one illustration child."""
    media = {
        "kind": "visual",
        "role": "illustration",
        "purpose": "Show the caliper jaws closing on the workpiece",
        "text_equivalent": "A caliper with its jaws closing on a marked workpiece.",
        "artifact_id": "art_00000000000000000000000000000001",
        "mime": "image/png",
        "label": "Illustration",
        "degraded": False,
        "reason": None,
    }
    if labels is not None:
        media["labels"] = labels
    return {
        "section_title": "Close the jaws",
        "lesson_intent": "Measure the workpiece with the caliper.",
        "segments": [
            {
                "kind": "model",
                "heading": "Watch the jaws close",
                "body": "Slide the jaws until they touch the workpiece, then read the scale.",
                "short": "Slide the jaws to the workpiece, then read the scale.",
            },
            {
                "kind": "explain",
                "heading": "Why the jaws must touch",
                "body": "A gap between jaw and workpiece shows a longer measurement than the part.",
                "short": "A gap shows a longer measurement than the part.",
            },
            {
                "kind": "guided",
                "heading": "Take one measurement",
                "body": "Close the jaws on the marked face and write the reading down.",
                "short": "Close the jaws on the marked face and write the reading.",
            },
        ],
        "worked_example": {
            "prompt": "Measure the marked face.",
            "steps": ["Open the jaws", "Close them on the face", "Read the scale"],
            "answer": "The reading on the scale",
            "short": "Open, close on the face, read the scale.",
        },
        "learner_explanation": "The jaws sit flat against the face you measure; the scale reads the gap between them.",
        "learner_explanation_short": "The jaws sit flat on the face; the scale reads the gap.",
        "sources": [],
        "media": [media],
    }


class LabelProjectionTest(unittest.TestCase):
    def test_a_valid_label_list_rides_the_media_child(self) -> None:
        document = lesson_document.document_from_page(page_with_labels(LABELS), check_id=None)
        media = [item for block in document["blocks"] for item in block["media"]]
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["labels"], LABELS)
        contracts.validate_definition("cb.rpc", "lesson_document", document)
        contracts.validate_definition("cb.rpc", "lesson_document_media", media[0])

    def test_the_bounds_are_the_contract_bounds(self) -> None:
        too_many = [{"text": f"Part {index}", "x": 0.1, "y": 0.1, "anchor": "start"} for index in range(9)]
        with self.assertRaises(lesson_document.LessonDocumentError) as raised:
            lesson_document.document_from_page(page_with_labels(too_many), check_id=None)
        self.assertIn("labels", str(raised.exception))

        for broken in (
            [{"text": "x" * 41, "x": 0.5, "y": 0.5, "anchor": "end"}],
            [{"text": "Jaws", "x": 1.4, "y": 0.5, "anchor": "start"}],
            [{"text": "Jaws", "x": 0.5, "y": -0.2, "anchor": "start"}],
            [{"text": "Jaws", "x": 0.5, "y": 0.5, "anchor": "middle"}],
            [{"text": "Jaws", "x": 0.5, "y": 0.5, "anchor": "start", "colour": "red"}],
        ):
            with self.subTest(broken=broken):
                with self.assertRaises(lesson_document.LessonDocumentError):
                    lesson_document.document_from_page(page_with_labels(broken), check_id=None)

    def test_a_figure_without_labels_keeps_its_pre_v27_shape(self) -> None:
        document = lesson_document.document_from_page(page_with_labels(None), check_id=None)
        media = [item for block in document["blocks"] for item in block["media"]]
        self.assertEqual(len(media), 1)
        self.assertEqual(set(media[0]), set(lesson_document.MEDIA_FIELDS))
        self.assertNotIn("labels", media[0])
        # The same record is valid against the frozen v26 document: absence is unchanged.
        validate_against_v26(document)
        # And the labelled page is *not* valid there — the field is what v27 buys.
        labelled = lesson_document.document_from_page(page_with_labels(LABELS), check_id=None)
        with self.assertRaises(contracts.ContractError):
            validate_against_v26(labelled)

    def test_a_bool_is_not_a_coordinate(self) -> None:
        # `True` is an int in Python; it must not read as `1.0` and pin a label to the edge.
        with self.assertRaises(lesson_document.LessonDocumentError):
            lesson_document.document_from_page(
                page_with_labels([{"text": "Jaws", "x": True, "y": 0.5, "anchor": "start"}]),
                check_id=None,
            )


class LabelReachTest(KernelCase):
    """A labelled figure has to survive the whole way to ``lesson.page``, not just the projector."""

    def seed_generated_lesson(self, lesson: dict, page: dict, *, media: list[dict]) -> None:
        plan_hash = domain.plan_hash(lesson["plan_id"])
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
                " plan_hash, document_json, research_json, generation_state, result_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, '{}', '{}', ?, '{}', '2026-11-12T00:00:00Z')",
                (
                    "gpd_labels_test",
                    lesson["plan_id"],
                    lesson["course_id"],
                    "fingerprint-labels",
                    plan_hash,
                    "validated",
                ),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, 1, ?, ?, ?, '[1]', '[]', '[]')",
                ("gps_labels_test", lesson["plan_id"], plan_hash, "Close the jaws", "Measure the workpiece"),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, 'validated', ?, ?, '[]', '2026-11-12T00:00:00Z',"
                " '2026-11-12T00:00:00Z')",
                (
                    "gln_labels_test",
                    lesson["plan_id"],
                    "gps_labels_test",
                    plan_hash,
                    json.dumps(page, ensure_ascii=False),
                    json.dumps(media, ensure_ascii=False),
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, 1)",
                ("gln_labels_test", lesson["check_id"]),
            )

    def serve(self, labels: list[dict] | None) -> dict:
        lesson = self.prepare_lesson(numeric_spec("4711"))
        page = page_with_labels(labels)
        media = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "Show the caliper jaws closing on the workpiece",
                "text_equivalent": "A caliper with its jaws closing on a marked workpiece.",
                "artifact_id": "art_00000000000000000000000000000001",
                "mime": "image/png",
                "label": "Illustration",
                "degraded": False,
                "reason": None,
                **({"labels": labels} if labels else {}),
            }
        ]
        self.seed_generated_lesson(lesson, page, media=media)
        response = self.dispatch(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )
        self.assertTrue(response["ok"], response.get("error"))
        return response["result"]

    def test_the_route_serves_the_labels_intact(self) -> None:
        result = self.serve(LABELS)
        # The handler's own result is inside the frozen contract, not merely close to it: this is
        # the call that used to answer INTERNAL_ERROR when a media child carried an unknown field.
        contracts.validate_response_payload("lesson.page", result)
        media = [item for block in result["document"]["blocks"] for item in block["media"]]
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["labels"], LABELS)

    def test_a_figure_without_labels_serves_the_v26_shape(self) -> None:
        result = self.serve(None)
        contracts.validate_response_payload("lesson.page", result)
        media = [item for block in result["document"]["blocks"] for item in block["media"]]
        self.assertEqual(len(media), 1)
        self.assertNotIn("labels", media[0])


class LabelAnswerLeakTest(unittest.TestCase):
    """The scan that already guards the narrative guards the label: one surface, not two rules."""

    ANSWER = "0.42"

    def _lesson(self) -> dict:
        return {
            "check": {
                "reference_answer": self.ANSWER,
                "accepted_answers": ["0.42 millimetres"],
                "rubric": [],
            }
        }

    def _page(self, labels: list[dict]) -> dict:
        page = page_with_labels(labels)
        page["document"] = lesson_document.document_from_page(page, check_id=None)
        return page

    def test_a_label_restating_the_reference_answer_is_refused(self) -> None:
        page = self._page([{"text": self.ANSWER, "x": 0.4, "y": 0.4, "anchor": "center"}])
        with self.assertRaises(generation._RuleViolation) as raised:
            generation.assert_no_answer_leak(page, self._lesson())
        self.assertIn("reference answer", str(raised.exception))

    def test_a_label_restating_an_accepted_answer_is_refused(self) -> None:
        page = self._page([{"text": "0.42 millimetres", "x": 0.4, "y": 0.4, "anchor": "start"}])
        with self.assertRaises(generation._RuleViolation):
            generation.assert_no_answer_leak(page, self._lesson())

    def test_an_ordinary_label_passes(self) -> None:
        generation.assert_no_answer_leak(self._page(LABELS), self._lesson())


if __name__ == "__main__":
    unittest.main()
