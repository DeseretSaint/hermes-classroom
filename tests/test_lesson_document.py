"""M1-P4: the v8 LessonDocument projection.

One validated document, many views. These tests pin the four things the card asks for:

* the projection is deterministic and contract-valid (roundtrip);
* a page authored before v8 migrates to a clear ``textbook_only`` state, not a broken toggle;
* exactly one check attaches to exactly one block and no answer material enters the document;
* source ids survive the projection, and duplicate or empty blocks are rejected rather than
  rendered.

The tests are deliberately storage-free: the projection is a pure function of the rows the
backend already returns, which is what makes "old rows are not rewritten" true.
"""

from __future__ import annotations

import copy
import json
import unittest

from coursebook import contracts, generation, lesson_document


CHECK_ID = "chk_lesson01"
SOURCE_ALPHA = "src_alpha01"
SOURCE_BETA = "src_beta001"
ART_AUDIO = "art_audio001"


def page_fixture() -> dict:
    return {
        "section_title": "Greeting someone",
        "lesson_intent": "Say a daytime greeting.",
        "segments": [
            {
                "kind": "model",
                "heading": "Hear it",
                "body": "The daytime greeting is spoken with a falling pitch.",
            },
            {
                "kind": "explain",
                "heading": "Why it changes",
                "body": "Japanese greetings follow the time of day, not the rank of the listener.",
            },
            {
                "kind": "guided",
                "heading": "Try it",
                "body": "Greet a classmate before noon and listen for the reply.",
            },
        ],
        "worked_example": {
            "prompt": "Greet a coworker at nine in the morning.",
            "steps": ["Choose the daytime greeting.", "Say it with a slight bow."],
            "answer": "The authored example answer.",
        },
        "learner_explanation": "Greeting choice follows the clock, and the reply mirrors the greeting.",
        "check": {"kind": "quiz"},
        "sources": [
            {
                "source_id": SOURCE_ALPHA,
                "title": "Greeting register",
                "publisher": "Example",
                "url": "https://example.invalid/greetings",
                "published_at": "2026-01-01T00:00:00+00:00",
                "fetched_at": "2026-01-02T00:00:00+00:00",
                "support_status": "supported",
            },
            {
                "source_id": SOURCE_BETA,
                "title": "Time of day",
                "publisher": "Example",
                "url": None,
                "published_at": None,
                "fetched_at": "2026-01-03T00:00:00+00:00",
                "support_status": "unassessed",
            },
        ],
        "media": [
            {
                "kind": "audio",
                "role": "narration",
                "purpose": "Model the phrase",
                "text_equivalent": "Audio of the daytime greeting.",
                "artifact_id": ART_AUDIO,
                "mime": "audio/mpeg",
                "label": "Phrase model",
                "degraded": False,
                "reason": None,
            }
        ],
    }


def segment_row(segment_id: str, ordinal: int, kind: str, text: str | None, *,
                artifact_id: str | None = None, source_id: str | None = None) -> dict:
    return {
        "segment_id": segment_id,
        "lesson_run_id": "run_lesson01",
        "ordinal": ordinal,
        "kind": kind,
        "text": text,
        "artifact_id": artifact_id,
        "source_id": source_id,
        "created_at": "2026-01-04T00:00:00+00:00",
    }


class ProjectionRoundtripTest(unittest.TestCase):
    def test_the_same_page_projects_to_the_same_document(self) -> None:
        first = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        second = lesson_document.document_from_page(copy.deepcopy(page_fixture()), check_id=CHECK_ID)
        self.assertEqual(first, second)
        self.assertEqual(
            lesson_document.canonical(first), lesson_document.canonical(second)
        )
        self.assertEqual(first["document_id"], second["document_id"])
        self.assertRegex(first["content_hash"], r"^sha256:[a-f0-9]{64}$")
        self.assertTrue(first["document_id"].startswith("doc_"))

    def test_the_projection_is_contract_valid(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        lesson_document.validate_document(document)
        contracts.validate_definition("cb.rpc", "lesson_document", document)
        for block in document["blocks"]:
            contracts.validate_definition("cb.rpc", "lesson_block", block)
            for item in block["media"]:
                contracts.validate_definition("cb.rpc", "lesson_document_media", item)

    def test_a_different_check_is_a_different_document(self) -> None:
        first = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        second = lesson_document.document_from_page(page_fixture(), check_id="chk_lesson02")
        self.assertNotEqual(first["content_hash"], second["content_hash"])
        self.assertNotEqual(first["document_id"], second["document_id"])

    def test_projection_does_not_mutate_the_stored_page(self) -> None:
        page = page_fixture()
        before = json.dumps(page, sort_keys=True, ensure_ascii=False)
        lesson_document.document_from_page(page, check_id=CHECK_ID)
        self.assertEqual(before, json.dumps(page, sort_keys=True, ensure_ascii=False))


class OldPageMigrationTest(unittest.TestCase):
    def test_a_v7_page_is_textbook_only_with_a_note_not_a_broken_toggle(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        self.assertEqual(document["state"], "textbook_only")
        self.assertTrue(document["views"]["textbook"])
        self.assertFalse(document["views"]["guided"])
        self.assertFalse(document["views"]["field_quest"])
        self.assertFalse(document["views"]["field_notes"])
        self.assertIn("Textbook view only", document["view_note"])
        # Every projected block has no invented short text: short is authored, never sliced.
        self.assertTrue(all(block["short"] is None for block in document["blocks"]))

    def test_projected_blocks_keep_the_authored_segment_roles_and_order(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        self.assertEqual(
            [block["role"] for block in document["blocks"]],
            ["example", "explain", "practice", "example", "recap"],
        )
        self.assertEqual(document["blocks"][0]["headline"], "Hear it")
        self.assertEqual(document["blocks"][1]["headline"], "Why it changes")
        self.assertIn("Choose the daytime greeting.", document["blocks"][3]["deep"])

    def test_an_empty_section_gets_an_empty_document(self) -> None:
        document = lesson_document.document_from_page(
            {"section_title": "Empty", "segments": [], "sources": [], "media": []}, check_id=None
        )
        self.assertEqual(document["state"], "empty")
        self.assertEqual(document["blocks"], [])
        self.assertFalse(any(document["views"].values()))
        self.assertIn("no teaching content", document["view_note"])

    def test_authored_blocks_reach_the_complete_state(self) -> None:
        page = page_fixture()
        page["blocks"] = [
            {
                "id": "blk_authored01",
                "role": "orient",
                "headline": "Greeting someone",
                "short": "Greetings follow the clock.",
                "deep": "Greetings follow the clock, and the reply mirrors the greeting you chose.",
                "check_id": None,
                "media": [],
                "source_ids": [SOURCE_ALPHA],
            },
            {
                "id": "blk_authored02",
                "role": "practice",
                "headline": "Try it",
                "short": "Greet a classmate before noon.",
                "deep": "Greet a classmate before noon, then write down the reply you heard.",
                "check_id": None,
                "media": [],
                "source_ids": [],
            },
        ]
        document = lesson_document.document_from_page(page, check_id=CHECK_ID)
        lesson_document.validate_document(document)
        self.assertEqual(document["state"], "complete")
        self.assertTrue(document["views"]["guided"])
        self.assertTrue(document["views"]["field_quest"])
        self.assertIsNone(document["view_note"])
        self.assertEqual([block["id"] for block in document["blocks"]],
                         ["blk_authored01", "blk_authored02"])


class CheckAttachmentTest(unittest.TestCase):
    def test_one_check_attaches_to_exactly_one_block(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        carriers = [block for block in document["blocks"] if block["check_id"]]
        self.assertEqual(len(carriers), 1)
        self.assertEqual(carriers[0]["role"], "practice")
        self.assertEqual(document["check_id"], CHECK_ID)

    def test_a_page_without_a_practice_block_attaches_to_the_terminal_block(self) -> None:
        page = page_fixture()
        page["segments"] = [segment for segment in page["segments"] if segment["kind"] != "guided"]
        page["worked_example"] = {}
        document = lesson_document.document_from_page(page, check_id=CHECK_ID)
        carriers = [block for block in document["blocks"] if block["check_id"]]
        self.assertEqual(len(carriers), 1)
        self.assertEqual(carriers[0]["id"], document["blocks"][-1]["id"])

    def test_no_check_means_no_block_claims_one(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=None)
        self.assertIsNone(document["check_id"])
        self.assertTrue(all(block["check_id"] is None for block in document["blocks"]))

    def test_two_blocks_claiming_one_check_are_rejected(self) -> None:
        blocks = [
            {
                "id": "blk_dupecheck1",
                "role": "practice",
                "headline": "First",
                "short": None,
                "deep": "A first practice block.",
                "check_id": CHECK_ID,
                "media": [],
                "source_ids": [],
            },
            {
                "id": "blk_dupecheck2",
                "role": "practice",
                "headline": "Second",
                "short": None,
                "deep": "A second practice block.",
                "check_id": CHECK_ID,
                "media": [],
                "source_ids": [],
            },
        ]
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.document_from_blocks(
                blocks, section_title="Two checks", check_id=CHECK_ID
            )
        self.assertIn("one check attaches to exactly one block", str(caught.exception))


class SourcePreservationTest(unittest.TestCase):
    def test_page_source_ids_are_preserved_in_order(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        self.assertEqual(document["source_ids"], [SOURCE_ALPHA, SOURCE_BETA])

    def test_segment_source_ids_travel_with_their_block(self) -> None:
        rows = [
            segment_row("seg_teach001", 1, "teaching", "First teaching paragraph.", source_id=SOURCE_ALPHA),
            segment_row("seg_teach002", 2, "teaching", "Second teaching paragraph.", source_id=SOURCE_BETA),
            segment_row("seg_check001", 3, "check_prompt", "Greet the listener.", source_id=SOURCE_ALPHA),
        ]
        document = lesson_document.document_from_segments(
            rows, section_title="Greeting someone", objective_id="obj_section01", check_id=CHECK_ID
        )
        lesson_document.validate_document(document)
        self.assertEqual(document["blocks"][0]["source_ids"], [SOURCE_ALPHA])
        self.assertEqual(document["blocks"][1]["source_ids"], [SOURCE_BETA])
        self.assertEqual(document["blocks"][2]["source_ids"], [SOURCE_ALPHA])
        self.assertEqual(set(document["source_ids"]), {SOURCE_ALPHA, SOURCE_BETA})
        self.assertEqual([block["role"] for block in document["blocks"]], ["orient", "recap", "practice"])

    def test_media_is_a_child_of_a_block_and_keeps_its_honesty_fields(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        media = [item for block in document["blocks"] for item in block["media"]]
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["kind"], "audio")
        self.assertEqual(media[0]["role"], "narration")
        self.assertEqual(media[0]["artifact_id"], ART_AUDIO)
        self.assertEqual(media[0]["text_equivalent"], "Audio of the daytime greeting.")
        self.assertFalse(media[0]["degraded"])

    def test_an_unknown_artifact_is_preserved_as_text_not_a_guessed_kind(self) -> None:
        rows = [
            segment_row("seg_teach001", 1, "teaching", "A teaching paragraph."),
            segment_row("seg_media001", 2, "media", "An unlabelled audio equivalent.", artifact_id="art_missing01"),
        ]
        document = lesson_document.document_from_segments(rows, section_title="Legacy media")
        lesson_document.validate_document(document)
        media = [item for block in document["blocks"] for item in block["media"]]
        self.assertEqual(media, [])
        self.assertTrue(any("An unlabelled audio equivalent." in block["deep"] for block in document["blocks"]))


class RejectionTest(unittest.TestCase):
    def _block(self, **overrides) -> dict:
        block = {
            "id": "blk_reject001",
            "role": "explain",
            "headline": "A block",
            "short": "Short text.",
            "deep": "Deep text that supports the short text.",
            "check_id": None,
            "media": [],
            "source_ids": [],
        }
        block.update(overrides)
        return block

    def test_duplicate_block_ids_are_rejected(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks([self._block(), self._block()])
        self.assertIn("duplicate block id", str(caught.exception))

    def test_an_empty_block_is_rejected(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks([self._block(deep="   ")])
        self.assertIn("deep is empty", str(caught.exception))
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks([self._block(headline="")])
        self.assertIn("headline is empty", str(caught.exception))

    def test_an_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks([self._block(role="chapter")])
        self.assertIn("is not one of", str(caught.exception))

    def test_an_unknown_block_field_is_rejected(self) -> None:
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.document_from_blocks(
                [dict(self._block(), view="textbook")], section_title="Unknown field"
            )
        self.assertIn("unknown field", str(caught.exception))

    def test_media_must_be_a_child_with_a_text_equivalent(self) -> None:
        media = [{"kind": "visual", "role": "illustration", "artifact_id": None,
                  "purpose": "", "text_equivalent": "", "label": None,
                  "degraded": False, "reason": None}]
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_blocks([self._block(media=media)])
        self.assertIn("purpose is empty", str(caught.exception))
        self.assertIn("text_equivalent is empty", str(caught.exception))

    def test_a_tampered_content_hash_is_rejected(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        document["blocks"][0]["deep"] = "A different claim entirely."
        with self.assertRaises(lesson_document.LessonDocumentError) as caught:
            lesson_document.validate_document(document)
        self.assertIn("content_hash does not match", str(caught.exception))

    def test_answer_material_keys_are_detected(self) -> None:
        self.assertEqual(lesson_document.answer_material({"blocks": [{"reference_answer": "x"}]}),
                         ["reference_answer"])
        self.assertEqual(lesson_document.answer_material({"blocks": [{"deep": "text"}]}), [])


class NoAnswerLeakTest(unittest.TestCase):
    def test_a_secret_in_a_block_is_detected(self) -> None:
        document = lesson_document.document_from_blocks(
            [
                {
                    "id": "blk_leak00001",
                    "role": "explain",
                    "headline": "Careful",
                    "short": "The key is 42.",
                    "deep": "The key you should type is 42.",
                    "check_id": None,
                    "media": [],
                    "source_ids": [],
                }
            ],
            section_title="Leaky",
            check_id=CHECK_ID,
        )
        self.assertTrue(lesson_document.leaks_answer(document, ["42"]))
        clean = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        self.assertEqual(lesson_document.leaks_answer(clean, ["42"]), [])

    def test_the_generation_leak_gate_reads_the_document(self) -> None:
        document = lesson_document.document_from_page(page_fixture(), check_id=CHECK_ID)
        secret = "the authored example answer"
        document["blocks"][0]["deep"] = f"The answer is {secret}."
        page = {"segments": [], "document": document}
        lesson = {
            "check": {"reference_answer": secret, "accepted_answers": [], "rubric": []},
        }
        with self.assertRaises(generation._RuleViolation) as caught:
            generation.assert_no_answer_leak(page, lesson)
        self.assertIn("reference answer", str(caught.exception))


class ContractSurfaceTest(unittest.TestCase):
    def test_the_wire_contract_is_v10_and_keeps_v9_on_disk(self) -> None:
        self.assertEqual(contracts.contract_version("cb.rpc"), 10)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 10)
        self.assertTrue((contracts.CONTRACT_DIR / "rpc.v9.json").is_file())

    def test_lesson_page_requires_the_document_and_keeps_the_old_fields(self) -> None:
        schema = contracts.method_schema("lesson.page")
        response = schema["response"]
        self.assertIn("document", response["properties"])
        self.assertIn("document", response["required"])
        for field in ("segments", "sources", "artifacts", "checks", "notebook_entries", "attempts"):
            self.assertIn(field, response["required"])
        document = contracts.contract("cb.rpc")["$defs"]["lesson_document"]
        self.assertIn("blocks", document["required"])
        self.assertIn("textbook_only", document["properties"]["state"]["enum"])

    def test_the_document_contract_has_no_answer_or_transcript_field(self) -> None:
        document = contracts.contract("cb.rpc")["$defs"]["lesson_document"]
        # `procedure` is the typed §8 header (tools/parts/hazards/stop condition/steps/source);
        # it is not answer material. Every other field is the v8 block document.
        self.assertEqual(
            set(document["properties"]),
            {
                "schema_version", "document_id", "content_hash", "section_title", "objective_id",
                "state", "view_note", "views", "blocks", "check_id", "source_ids", "procedure",
            },
        )
        self.assertNotIn("transcript", json.dumps(document))
        procedure = json.dumps(document["properties"]["procedure"])
        for forbidden in ("reference_answer", "accepted_answers", "rubric"):
            self.assertNotIn(forbidden, procedure)


if __name__ == "__main__":
    unittest.main()
