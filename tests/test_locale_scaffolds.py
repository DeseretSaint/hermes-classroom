"""H-18: locale-aware scaffolds and the document direction/lang contract.

These tests pin the decision the Japanese-only scaffold triple could not express:

* a French A1 lesson declares no scaffold and is never asked for romaji;
* an Arabic lesson carries ``direction: rtl`` and its beginner scaffold is harakat diacritics;
* Japanese at L0/L1 still mandates romaji, furigana and an English gloss;
* every value is bounded (unknown kind, script, gloss, direction or field is refused);
* an old page/document without lang/direction still reads, and the projection invents neither.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from coursebook import contracts, generation as gen, lesson_document, localization

FIXTURES = Path(__file__).parent / "fixtures" / "generation"
BLOCK = {
    "id": "blk_loc00001",
    "role": "orient",
    "headline": "مرحبا",
    "short": "تحية قصيرة.",
    "deep": "تحية عربية قصيرة عند الدخول إلى متجر.",
    "check_id": None,
    "media": [],
    "source_ids": [],
}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class ScaffoldVocabularyTest(unittest.TestCase):
    def test_legacy_triple_is_read_as_the_open_vocabulary(self) -> None:
        legacy = {"romaji": True, "furigana": True, "english_meaning": True}
        self.assertEqual(
            localization.normalize_scaffolds(legacy),
            [{"kind": "romaji"}, {"kind": "furigana"}, {"kind": "gloss"}],
        )
        self.assertEqual(
            localization.declared_scaffold_kinds({"romaji": False, "furigana": True, "english_meaning": False}),
            {"furigana"},
        )
        self.assertEqual(localization.normalize_scaffolds({}), [])
        self.assertEqual(localization.normalize_scaffolds(None), [])

    def test_unknown_values_are_refused(self) -> None:
        for bad in (
            {"romaji": True, "pinyin": True},
            {"romaji": "yes"},
            [{"kind": "romaji_squared"}],
            [{"kind": "gloss", "colour": "red"}],
            [{"kind": "gloss", "script": "klingon"}],
            [{"kind": "gloss", "direction": "up"}],
            [{"kind": "romaji"}, {"kind": "romaji"}],
        ):
            with self.subTest(bad=bad), self.assertRaises(localization.ScaffoldError):
                localization.normalize_scaffolds(bad)

    def test_locale_and_level_key_the_mandate(self) -> None:
        self.assertEqual(
            localization.scaffold_requirements("ja-JP", {"level": "L0"}),
            {"romaji": True, "furigana": True, "gloss": True},
        )
        self.assertEqual(
            localization.scaffold_requirements("ja", {"level": "L1"}),
            {"romaji": True, "furigana": True, "gloss": True},
        )
        # A Japanese lesson above beginner needs nothing unless the brief asks for romaji.
        self.assertEqual(localization.scaffold_requirements("ja", {"level": "B2"}), {})
        self.assertEqual(
            localization.scaffold_requirements("ja", {"level": "B2", "romaji": True}),
            {"romaji": True},
        )
        self.assertEqual(localization.scaffold_requirements("fr-FR", {"level": "A1"}), {})
        self.assertEqual(localization.scaffold_requirements("ar-SA", {"level": "A1"}), {"diacritics": True})
        self.assertEqual(localization.scaffold_requirements(None, {"level": "L0"}), {})

    def test_direction_is_a_property_of_the_script(self) -> None:
        self.assertEqual(localization.direction_for_locale("ar-SA"), "rtl")
        self.assertEqual(localization.direction_for_locale("he-IL"), "rtl")
        self.assertEqual(localization.direction_for_locale("fa-IR"), "rtl")
        self.assertEqual(localization.direction_for_locale("ja-JP"), "ltr")
        self.assertEqual(localization.direction_for_locale("fr-FR"), "ltr")
        self.assertIsNone(localization.direction_for_locale(None))
        self.assertIsNone(localization.direction_for_locale(""))


class LessonSchemaTest(unittest.TestCase):
    def test_french_needs_no_japanese_scaffold(self) -> None:
        lesson = fixture("lesson_fr")
        gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")
        self.assertEqual(lesson["check"]["scaffolds"], [])

    def test_legacy_japanese_fixture_still_validates(self) -> None:
        gen.validate_artifact(gen.LESSON_SCHEMA, fixture("lesson_ja"), what="lesson")

    def test_open_form_validates_and_values_are_bounded(self) -> None:
        lesson = fixture("lesson_fr")
        lesson["check"]["scaffolds"] = [
            {"kind": "romaji", "script": "kana", "direction": "ltr"},
            {"kind": "gloss", "gloss": "en"},
        ]
        gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")
        for bad in ([{"kind": "nope"}], [{"kind": "gloss", "gloss": "toolong" * 10}]):
            candidate = json.loads(json.dumps(lesson))
            candidate["check"]["scaffolds"] = bad
            with self.assertRaises(gen.GenerationRejected):
                gen.validate_artifact(gen.LESSON_SCHEMA, candidate, what="lesson")

    def test_the_field_is_optional_but_a_required_scaffold_is_still_enforced(self) -> None:
        lesson = fixture("lesson_fr")
        lesson["check"].pop("scaffolds", None)
        gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")

        japanese = fixture("lesson_ja")
        japanese["check"].pop("scaffolds", None)
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_lesson_rules(
                japanese,
                section={},
                objective=None,
                recipe="committed",
                locale="ja-JP",
                dials={"level": "L0"},
            )
        self.assertTrue(any("romaji" in reason for reason in caught.exception.reasons))


class DocumentDirectionTest(unittest.TestCase):
    def test_arabic_document_carries_rtl_and_lang(self) -> None:
        document = lesson_document.document_from_blocks([BLOCK], section_title="تحية", locale="ar-SA")
        self.assertEqual((document["lang"], document["direction"]), ("ar-SA", "rtl"))
        lesson_document.validate_document(document)
        contracts.validate_definition("cb.rpc", "lesson_document", document)

    def test_old_document_without_direction_still_reads(self) -> None:
        document = lesson_document.document_from_page(fixture("lesson_ja"))
        self.assertNotIn("lang", document)
        self.assertNotIn("direction", document)
        lesson_document.validate_document(document)
        contracts.validate_definition("cb.rpc", "lesson_document", document)

    def test_a_page_with_a_locale_projects_the_same_fields(self) -> None:
        page = fixture("lesson_ja")
        page["lang"] = "ja-JP"
        page["direction"] = "ltr"
        document = lesson_document.document_from_page(page)
        self.assertEqual((document["lang"], document["direction"]), ("ja-JP", "ltr"))
        lesson_document.validate_document(document)

    def test_invalid_direction_and_lang_are_rejected(self) -> None:
        document = lesson_document.document_from_blocks([BLOCK], section_title="x", locale="ar-SA")
        broken = json.loads(json.dumps(document))
        broken["direction"] = "up"
        with self.assertRaises(lesson_document.LessonDocumentError):
            lesson_document.validate_document(broken)
        broken = json.loads(json.dumps(document))
        broken["lang"] = "not a tag!"
        with self.assertRaises(lesson_document.LessonDocumentError):
            lesson_document.validate_document(broken)

    def test_learner_page_projection_records_the_course_locale(self) -> None:
        lesson = fixture("lesson_fr")
        section = {"lesson_intent": "Greet politely."}
        page = gen._build_learner_page(lesson, section, [], locale="fr-FR")
        self.assertEqual((page["lang"], page["direction"]), ("fr-FR", "ltr"))
        self.assertEqual(page["check"]["scaffolds"], [])
        document = lesson_document.document_from_page(page)
        self.assertEqual((document["lang"], document["direction"]), ("fr-FR", "ltr"))
        self.assertNotIn("lang", gen._build_learner_page(lesson, section, [], locale=None))


class LegacyDocumentHashTest(unittest.TestCase):
    """A page authored before H-18 must render and hash exactly as it did before H-18.

    The pinned values were produced by the **master** checkout (263c19d, before this change) with
    ``lesson_document.document_from_page(lesson_ja)`` — the same call ``domain.lesson_page`` makes
    for a stored ``gen_lessons.page_json`` — so this is cross-version evidence rather than a number
    the new code reports about itself.
    """

    PINNED_HASH = "sha256:fe03579c76401d11e57e6285bd62b471a0b4e216b7f258653d10c4e7c1a785c5"
    PINNED_ID = "doc_fe03579c76401d11e57e"

    def test_legacy_document_hash_unchanged_by_locale(self) -> None:
        document = lesson_document.document_from_page(fixture("lesson_ja"))
        self.assertEqual(document["content_hash"], self.PINNED_HASH)
        self.assertEqual(document["document_id"], self.PINNED_ID)
        self.assertNotIn("lang", document)
        self.assertNotIn("direction", document)
        lesson_document.validate_document(document)
        contracts.validate_definition("cb.rpc", "lesson_document", document)

    def test_the_read_path_does_not_hand_the_course_locale_to_a_legacy_page(self) -> None:
        # domain.lesson_page projects a stored page with document_from_page(page, check_id=...)
        # and deliberately passes no locale: a page that never recorded one must not be given an
        # invented direction, which would move its content hash and document id.
        source = (
            Path(__file__).resolve().parents[1] / "coursebook" / "domain.py"
        ).read_text(encoding="utf-8")
        self.assertIn("document = lesson_document.document_from_page(authored, check_id=check_id)", source)
        self.assertNotIn('authored, check_id=check_id, locale=', source)


class ReviewTargetScaffoldTest(unittest.TestCase):
    """A review lesson reuses an owner check, so it must read the new scaffold list too.

    Before H-18 the review target copied ``stimulus.scaffolds`` with ``dict(...)``. An H-18 lesson
    stores a list, and ``dict(list)`` raises, which would have made every review section over a
    newly authored lesson fail. This pins the normalisation on a real SQLite database.
    """

    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        gen.ensure_schema(connection)
        now = "2026-11-07T00:00:00Z"
        connection.execute(
            "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at)"
            " VALUES ('pln_review0001', 'crs_review0001', 1, 'approved', 'h', '{}', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
            " evidence_criteria_json, state, version, created_at)"
            " VALUES ('obj_review0001', 'pln_review0001', 1, 'Greet', 'recall', '[]', 'independent', 1, ?)",
            (now,),
        )
        return connection

    def _seed_check(self, connection, scaffolds) -> None:
        connection.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at)"
            " VALUES ('chk_review0001', 'obj_review0001', 1, 'recall', ?, '{}', '{}', 'ja-JP',"
            " 'passed', 'open', '2026-11-07T00:00:00Z')",
            (json.dumps({"prompt": "Say hello", "scaffolds": scaffolds}),),
        )
        connection.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " created_at, updated_at) VALUES ('lsn_review0001', 'pln_review0001', 'sec1', 'h', 1,"
            " 'validated', ?, '2026-11-07T00:00:00Z', '2026-11-07T00:00:00Z')",
            (json.dumps({"check": {"kind": "quiz"}}),),
        )
        connection.execute(
            "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref)"
            " VALUES ('lsn_review0001', 'chk_review0001', 1)"
        )

    def test_open_list_scaffolds_survive_the_review_projection(self) -> None:
        connection = self._connection()
        self.addCleanup(connection.close)
        self._seed_check(connection, [{"kind": "romaji"}, {"kind": "gloss", "gloss": "en"}])
        target = gen._resolve_review_target(connection, "pln_review0001", {"objective_refs": [1]})
        self.assertEqual(target["check"]["scaffolds"], [{"kind": "romaji"}, {"kind": "gloss", "gloss": "en"}])
        self.assertEqual(target["check"]["kind"], "quiz")
        self.assertEqual(
            localization.declared_scaffold_kinds(target["check"]["scaffolds"]),
            {"romaji", "gloss"},
        )

    def test_legacy_triple_scaffolds_still_project(self) -> None:
        connection = self._connection()
        self.addCleanup(connection.close)
        self._seed_check(connection, {"romaji": True, "furigana": True, "english_meaning": True})
        target = gen._resolve_review_target(connection, "pln_review0001", {"objective_refs": [1]})
        self.assertEqual(
            target["check"]["scaffolds"],
            [{"kind": "romaji"}, {"kind": "furigana"}, {"kind": "gloss"}],
        )
