"""The procedure layout is a header over the same lesson document (VISUAL_MEDIA_PLAN §8).

A procedure does not add a second copy of the teaching text, a second check, or an answer. It
adds typed header facts, an ordered list of block references, deterministic schematic rows and a
cited source with a permission status. These tests pin the validator, the content hash and the
deterministic SVG, and they are the fixture the Desktop render tests reuse.
"""

from __future__ import annotations

import hashlib
import json
import unittest

from coursebook import artifacts, lesson_document


SOURCE_ID = "src_gasket_manual"
SCHEMATIC_SOURCE_ID = "src_gasket_manual"
CHECK_ID = "chk_gasket_torque01"


def block(block_id: str, role: str, headline: str, deep: str, short: str | None = None, **extra):
    return {
        "id": block_id,
        "role": role,
        "headline": headline,
        "short": short or deep,
        "deep": deep,
        "check_id": extra.pop("check_id", None),
        "media": extra.pop("media", []),
        "source_ids": extra.pop("source_ids", []),
    }


def schematic_media() -> dict:
    return {
        "kind": "visual",
        "role": "schematic",
        "artifact_id": "art_torque_seq_001",
        "purpose": "Torque sequence for the cylinder head bolts",
        "text_equivalent": "Bolt 1 20 Nm, bolt 2 20 Nm, bolt 3 40 Nm, bolt 4 40 Nm",
        "label": "Deterministic schematic rendered from structured facts.",
        "degraded": False,
        "reason": None,
    }


def head_gasket_blocks() -> list[dict]:
    return [
        block(
            "blk_gasket_orient1",
            "orient",
            "Before you lift the head",
            "Drain the coolant into a sealed container and photograph the vacuum and coolant "
            "routing before any connector is removed. The engine must be stone cold.",
            short="Drain coolant; engine cold; photograph the routing.",
            source_ids=[SOURCE_ID],
        ),
        block(
            "blk_gasket_explain1",
            "explain",
            "Loosen in reverse sequence",
            "Release the head bolts from the outside in, a quarter turn at a time, in the reverse "
            "of the tightening sequence printed on the manual page.",
            short="Loosen outside-in, a quarter turn at a time, reverse sequence.",
        ),
        block(
            "blk_gasket_step0001",
            "practice",
            "Clean the deck and fit the gasket",
            "Scrape the block deck with a plastic scraper, wipe with a lint-free cloth, and set "
            "the new gasket dry with its tab toward the front of the engine.",
            short="Clean the deck; fit the gasket dry, tab to the front.",
            check_id=CHECK_ID,
            media=[schematic_media()],
            source_ids=[SOURCE_ID],
        ),
        block(
            "blk_gasket_step0002",
            "practice",
            "Torque the head bolts",
            "Oil the bolt threads, seat each bolt finger-tight, then torque in the numbered "
            "sequence in three passes to the specification on the manual page.",
            short="Oil threads; three passes in the numbered sequence.",
            media=[schematic_media()],
        ),
        block(
            "blk_gasket_recap001",
            "recap",
            "Verify before the first start",
            "Re-check the sequence, confirm every connector is seated, refill coolant, and run "
            "the engine to temperature while watching for leaks.",
            short="Re-check sequence, connectors, coolant; run to temperature.",
        ),
    ]


def head_gasket_procedure() -> dict:
    return {
        "tools": ["Torque wrench 5–25 Nm", "Plastic scraper", "Lint-free cloth", "Drain pan"],
        "parts": ["Head gasket", "Head bolts (10)", "Coolant (5 L)"],
        "hazards": [
            "Coolant is toxic and stays hot for hours after the engine stops.",
            "A dropped bolt or washer can fall into an oil gallery.",
        ],
        "stop_condition": (
            "Stop and do not proceed if any bolt will not reach the specified torque, if a "
            "thread is damaged, or if the deck shows a crack or deep score."
        ),
        "steps": [
            {"block_id": "blk_gasket_orient1", "check": None},
            {"block_id": "blk_gasket_explain1", "check": None},
            {"block_id": "blk_gasket_step0001", "check": "Gasket tab faces the front of the engine."},
            {"block_id": "blk_gasket_step0002", "check": "Wrench clicks at the specified torque on every bolt."},
            {"block_id": "blk_gasket_recap001", "check": None},
        ],
        "schematic": {
            "title": "Head bolt torque sequence",
            "text_equivalent": (
                "Four-row torque table: bolts 1 and 2 at 20 Nm, bolts 3 and 4 at 40 Nm, in the "
                "order the manual prints."
            ),
            "artifact_id": "art_torque_seq_001",
            "source_id": SCHEMATIC_SOURCE_ID,
            "rows": [
                {"label": "Bolt 1", "value": "20 Nm", "row": 1},
                {"label": "Bolt 2", "value": "20 Nm", "row": 2},
                {"label": "Bolt 3", "value": "40 Nm", "row": 3},
                {"label": "Bolt 4", "value": "40 Nm", "row": 4},
            ],
        },
        "source": {"source_id": SOURCE_ID, "permission": "licensed"},
    }


def head_gasket_document() -> dict:
    return lesson_document.document_from_blocks(
        head_gasket_blocks(),
        section_title="Replace the head gasket",
        objective_id="obj_gasket00000001",
        check_id=CHECK_ID,
        source_ids=[SOURCE_ID],
        procedure=head_gasket_procedure(),
    )


class ProcedureDocumentTest(unittest.TestCase):
    def test_head_gasket_document_validates_and_binds_the_procedure_into_the_hash(self):
        document = head_gasket_document()
        self.assertEqual(document["state"], "complete")
        self.assertEqual(document["procedure"]["source"]["permission"], "licensed")
        self.assertEqual(len(document["procedure"]["steps"]), 5)
        lesson_document.validate_document(document)
        plain = lesson_document.document_from_blocks(
            head_gasket_blocks(),
            section_title="Replace the head gasket",
            objective_id="obj_gasket00000001",
            check_id=CHECK_ID,
            source_ids=[SOURCE_ID],
        )
        self.assertNotIn("procedure", plain)
        self.assertNotEqual(document["content_hash"], plain["content_hash"])
        self.assertEqual(
            document["content_hash"],
            "sha256:" + hashlib.sha256(
                lesson_document.canonical(
                    {
                        "schema_version": 1,
                        "section_title": document["section_title"],
                        "objective_id": document["objective_id"],
                        "check_id": document["check_id"],
                        "source_ids": document["source_ids"],
                        "blocks": document["blocks"],
                        "procedure": document["procedure"],
                    }
                ).encode("utf-8")
            ).hexdigest(),
        )

    def test_procedure_is_deterministic(self):
        first = head_gasket_document()
        second = head_gasket_document()
        self.assertEqual(first["document_id"], second["document_id"])
        self.assertEqual(first["content_hash"], second["content_hash"])

    def test_procedure_never_carries_a_second_check(self):
        document = head_gasket_document()
        claimed = [block["check_id"] for block in document["blocks"] if block["check_id"]]
        self.assertEqual(claimed, [CHECK_ID])
        self.assertEqual(document["check_id"], CHECK_ID)
        for step in document["procedure"]["steps"]:
            self.assertEqual(set(step), {"block_id", "check"})

    def test_step_must_reference_a_document_block(self):
        procedure = head_gasket_procedure()
        procedure["steps"][0]["block_id"] = "blk_doesnotexist01"
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("is not a document block", "; ".join(caught.exception.problems))

    def test_step_cannot_repeat_a_block(self):
        procedure = head_gasket_procedure()
        procedure["steps"][1]["block_id"] = procedure["steps"][0]["block_id"]
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("repeats block", "; ".join(caught.exception.problems))

    def test_hazards_must_be_named(self):
        procedure = head_gasket_procedure()
        procedure["hazards"] = []
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("must name the hazards", "; ".join(caught.exception.problems))

    def test_stop_condition_must_be_present(self):
        procedure = head_gasket_procedure()
        procedure["stop_condition"] = "  "
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("stop_condition is empty", "; ".join(caught.exception.problems))

    def test_source_must_be_cited_and_permission_known(self):
        procedure = head_gasket_procedure()
        procedure["source"] = {"source_id": "src_uncited00001", "permission": "licensed"}
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("is not a document source", "; ".join(caught.exception.problems))
        procedure = head_gasket_procedure()
        procedure["source"]["permission"] = "unknown"
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("permission", "; ".join(caught.exception.problems))

    def test_schematic_facts_are_checked_against_the_source_ledger(self):
        procedure = head_gasket_procedure()
        procedure["schematic"]["source_id"] = "src_elsewhere001"
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("is not a document source", "; ".join(caught.exception.problems))

    def test_schematic_needs_structured_rows(self):
        procedure = head_gasket_procedure()
        procedure["schematic"]["rows"] = []
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("non-empty array of structured facts", "; ".join(caught.exception.problems))

    def test_unknown_procedure_fields_are_refused(self):
        procedure = head_gasket_procedure()
        procedure["torque_from_ai"] = "20 Nm"
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            head_gasket_document_with(procedure)
        self.assertIn("unknown field", "; ".join(caught.exception.problems))

    def test_answer_material_in_procedure_is_visible_to_the_leak_check(self):
        document = head_gasket_document()
        text = lesson_document.narrative_text(document)
        self.assertIn(lesson_document._normalize("Bolt 3 40 Nm"), text.replace("  ", " "))
        self.assertEqual(lesson_document.leaks_answer(document, ["20 Nm"]), ["20 Nm"])

    def test_schematic_svg_is_deterministic_and_carries_the_structured_rows(self):
        rows = head_gasket_procedure()["schematic"]["rows"]
        first = artifacts.make_schematic_svg("Head bolt torque sequence", rows)
        second = artifacts.make_schematic_svg("Head bolt torque sequence", list(reversed(rows)))
        self.assertEqual(first, second)
        text = first.decode("utf-8")
        self.assertIn("Head bolt torque sequence", text)
        self.assertIn("Bolt 3", text)
        self.assertIn("40 Nm", text)
        self.assertIn("Deterministic schematic rendered from structured facts.", text)
        self.assertNotIn("Illustration", text)

    def test_projection_carries_an_authored_procedure_from_a_stored_page(self):
        document = head_gasket_document()
        page = {
            "section_title": document["section_title"],
            "objective_id": document["objective_id"],
            "document": {
                "objective_id": document["objective_id"],
                "blocks": head_gasket_blocks(),
                "procedure": head_gasket_procedure(),
                "source_ids": [SOURCE_ID],
            },
            "sources": [{"source_id": SOURCE_ID}],
        }
        projected = lesson_document.document_from_page(page, check_id=CHECK_ID)
        self.assertEqual(projected["procedure"], document["procedure"])
        self.assertEqual(projected["content_hash"], document["content_hash"])

    def test_projection_without_procedure_is_unchanged(self):
        page = {
            "section_title": "Affection and register",
            "objective_id": "obj_0123456789abcdef",
            "document": {"blocks": head_gasket_blocks_without_procedure()},
            "sources": [],
        }
        projected = lesson_document.document_from_page(page)
        self.assertNotIn("procedure", projected)


def head_gasket_blocks_without_procedure() -> list[dict]:
    return [
        block(
            "blk_plain_orient001",
            "orient",
            "Start",
            "Plain teaching text without a procedure header.",
            short="Plain teaching text.",
        )
    ]


def head_gasket_document_with(procedure: dict) -> dict:
    return lesson_document.document_from_blocks(
        head_gasket_blocks(),
        section_title="Replace the head gasket",
        objective_id="obj_gasket00000001",
        check_id=CHECK_ID,
        source_ids=[SOURCE_ID],
        procedure=procedure,
    )


if __name__ == "__main__":
    unittest.main()
