"""H-173d media finding: each fixture's media decision must match what the lesson ships.

The three sample pairs are recorded fixtures, not live provider output. These tests pin the
media half of the repair only:

- S1 declared four required schematics but shipped one. The lesson now ships four
  ``visual/schematic`` items with structured facts, and every section's required visual is
  produced under the real lesson rules.
- S2 assigned a say-it-aloud act while every section declared ``audio=none`` with an empty
  construct. The spoken act and the audio need are gone; the lesson and plan now state that no
  recording ships and why.
- S3 depended on four picture cards whose content was never specified. The plan, the parent
  materials and the lesson now name the four objects, and the decision stays an honest ``none``
  because the cards are parent-supplied props.

Each new re-score record must pass the bounded packet checker and score D7 at 3 or 4. The
independent H-173d records and the earlier author records are not edited.

Run: ``python3 -m unittest tests.test_course_quality_media_fixtures``
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

from coursebook import generation as gen, research

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "generation"
PACKET = ROOT / "scripts" / "course_quality_review.py"
RECORDS = (
    "H173d-D7-S1-media-rescore.md",
    "H173d-D7-S2-media-rescore.md",
    "H173d-D7-S3-media-rescore.md",
)

CARD_OBJECTS = ("kettle", "toaster", "fridge", "ice tray")


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_packet_module():
    spec = importlib.util.spec_from_file_location("course_quality_review_media", PACKET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_record() -> research.SourceRecord:
    """The ledger entry plan_ja's SRC_ALPHA stands for, so the committed rules can run."""
    return research.SourceRecord(
        source_id="SRC_ALPHA",
        url="https://example.org/ja-cafe-greetings",
        title="Japanese café greetings and register",
        publisher="Example",
        source_type="reference",
        fetched_at="2026-11-08T00:00:00Z",
        published_at=None,
        content_hash="sha256:" + "0" * 64,
        support_status="supported",
    )


def assert_lesson_rules(test: unittest.TestCase, lesson: dict, plan: dict, *, recipe: str,
                        locale: str | None, ledger, sections) -> None:
    dials = {"level": "L0"} if locale else {}
    gen.validate_artifact(gen.LESSON_SCHEMA, lesson, what="lesson")
    for section in sections:
        objective = next(
            obj for obj in plan["objectives"] if obj["ordinal"] == section["objective_refs"][0]
        )
        test.assertIsNone(
            gen.enforce_lesson_rules(
                lesson,
                section=section,
                objective=objective,
                recipe=recipe,
                locale=locale,
                dials=dials,
                ledger=ledger,
            )
        )


class S1BrakeMediaTest(unittest.TestCase):
    """Four required schematics now have four artifacts that carry them."""

    def setUp(self) -> None:
        self.plan = fixture("plan_one_off")
        self.lesson = fixture("lesson_one_off")

    def test_every_section_still_requires_a_schematic(self) -> None:
        for section in self.plan["sections"]:
            with self.subTest(section=section["ordinal"]):
                need = section["media_need"]
                self.assertEqual(need["image"], {"level": "required", "role": "schematic"})
                self.assertTrue(need["construct"].strip())

    def test_lesson_ships_one_schematic_for_each_construct(self) -> None:
        media = self.lesson["media"]
        self.assertEqual(len(media), 4)
        for index, item in enumerate(media, start=1):
            with self.subTest(item=index):
                self.assertEqual(item["kind"], "visual")
                self.assertEqual(item["role"], "schematic")
                self.assertTrue(item["text_equivalent"].strip())
                self.assertTrue(item["facts"]["rows"], "a schematic must render from structured facts")

    def test_lesson_names_where_each_schematic_is_used(self) -> None:
        body = " ".join(segment["body"] for segment in self.lesson["segments"]).lower()
        self.assertIn("release-sequence diagram", body)
        self.assertIn("moving-parts diagram", body)
        explanation = self.lesson["learner_explanation"].lower()
        for phrase in ("caliper parts", "release sequence", "pad seating", "parts that move"):
            self.assertIn(phrase, explanation)

    def test_rules_pass_for_every_section(self) -> None:
        gen.enforce_plan_rules(
            self.plan, recipe="one_off", dials={}, locale=None, ledger=[], scope="single"
        )
        assert_lesson_rules(
            self, self.lesson, self.plan, recipe="one_off", locale=None, ledger=None,
            sections=self.plan["sections"],
        )


class S2JapaneseAudioTest(unittest.TestCase):
    """No spoken act is assigned and no audio need is left undecided."""

    def setUp(self) -> None:
        self.plan = fixture("plan_ja")
        self.lesson = fixture("lesson_ja")

    def test_no_say_it_aloud_instruction_remains(self) -> None:
        text = " ".join(segment["body"] for segment in self.lesson["segments"]).lower()
        self.assertNotIn("aloud", text)
        self.assertIn("no recording ships with this sample", text)

    def test_every_section_declares_no_audio_with_an_empty_construct(self) -> None:
        for section in self.plan["sections"]:
            with self.subTest(section=section["ordinal"]):
                need = section["media_need"]
                self.assertEqual(need["audio"], {"level": "none", "role": "none"})
                self.assertEqual(need["construct"], "")
        self.assertEqual(self.lesson["media"], [])

    def test_plan_states_why_no_recording_ships(self) -> None:
        exclusions = " ".join(self.plan["exclusions"]).lower()
        self.assertIn("no model recording is shipped", exclusions)
        self.assertIn("typed selections", exclusions)

    def test_rules_pass_for_the_supplied_lesson(self) -> None:
        gen.enforce_plan_rules(
            self.plan, recipe="committed", dials={"level": "L0"}, locale="ja-JP",
            ledger=[source_record()], scope="short",
        )
        assert_lesson_rules(
            self, self.lesson, self.plan, recipe="committed", locale="ja-JP",
            ledger=[source_record()], sections=self.plan["sections"][:1],
        )


class S3ParentCardsTest(unittest.TestCase):
    """The four picture cards are named, and the absence of lesson media is stated."""

    def setUp(self) -> None:
        self.plan = fixture("plan_parent")
        self.lesson = fixture("lesson_parent_safe")

    def test_plan_names_what_each_card_depicts(self) -> None:
        section_two = self.plan["sections"][1]
        joined = " ".join(
            self.plan["context_needs"]
            + section_two["context_needs"]
            + [section_two["lesson_intent"]]
            + self.plan["parent"]["setting_materials"]
        ).lower()
        for obj in CARD_OBJECTS:
            self.assertIn(obj, joined)
        self.assertIn("parent-supplied props", joined)

    def test_lesson_names_the_same_four_objects_before_the_sort(self) -> None:
        guided = [segment for segment in self.lesson["segments"] if segment["kind"] == "guided"]
        self.assertEqual(len(guided), 1)
        body = guided[0]["body"].lower()
        for obj in CARD_OBJECTS:
            self.assertIn(obj, body)

    def test_media_stays_honestly_none(self) -> None:
        for section in self.plan["sections"]:
            with self.subTest(section=section["ordinal"]):
                need = section["media_need"]
                self.assertEqual(need["image"], {"level": "none", "role": "none"})
                self.assertEqual(need["audio"], {"level": "none", "role": "none"})
                self.assertEqual(need["construct"], "")
        self.assertEqual(self.lesson["media"], [])

    def test_rules_pass_for_the_supplied_lesson(self) -> None:
        gen.enforce_plan_rules(self.plan, recipe="parent", dials={}, locale=None, ledger=[])
        assert_lesson_rules(
            self, self.lesson, self.plan, recipe="parent", locale=None, ledger=None,
            sections=self.plan["sections"][:1],
        )


class MediaRescoreRecordTest(unittest.TestCase):
    """Each new record is a valid review and scores the repaired D7 at 3 or 4."""

    def test_records_pass_the_packet_checker(self) -> None:
        module = load_packet_module()
        for name in RECORDS:
            with self.subTest(record=name):
                path = ROOT / "docs" / "reviews" / name
                self.assertTrue(path.is_file())
                self.assertEqual(module.check_record(path.read_text(encoding="utf-8")), [])

    def test_d7_is_rescored_at_three_or_four(self) -> None:
        for name in RECORDS:
            with self.subTest(record=name):
                text = (ROOT / "docs" / "reviews" / name).read_text(encoding="utf-8")
                match = re.search(
                    r"^### D7 media_necessity\n(?:Question:.*\n)Score: ([1-4])$",
                    text,
                    re.MULTILINE,
                )
                self.assertIsNotNone(match)
                assert match is not None
                self.assertGreaterEqual(int(match.group(1)), 3)

    def test_records_say_they_are_author_run_fixture_rescores(self) -> None:
        for name in RECORDS:
            with self.subTest(record=name):
                text = (ROOT / "docs" / "reviews" / name).read_text(encoding="utf-8")
                self.assertIn("author-run re-score", text)
                self.assertIn("H-172", text)
                self.assertIn("not a live provider run", text)


if __name__ == "__main__":
    unittest.main()
