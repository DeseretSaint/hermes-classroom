"""H-173: the course-quality rubric, the bounded review packet, and the links that make it used.

The rubric is a quality lens beside the validator, not a second validator and not a mastery
score. These tests hold the file to the eight dimensions the card names, hold the packet to facts
plus blank verdicts, and hold a completed record to a named reviewer, evidence and a follow-up for
every dimension below 3. They also guard the two refusals: no mastery/engagement aggregate and no
change to generation, validation or RPC behavior.

Run: ``python3 -m unittest tests.test_course_quality_rubric``
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FIXTURES = ROOT / "tests" / "fixtures" / "generation"
RUBRIC = DOCS / "COURSE-QUALITY-RUBRIC.md"
REVIEW_SUMMARY = DOCS / "H173-COURSE-QUALITY-REVIEW.md"
REVIEW_RECORDS = (
    DOCS / "reviews" / "H173-S1-single-brake.md",
    DOCS / "reviews" / "H173-S2-short-japanese-cafe.md",
    DOCS / "reviews" / "H173-S3-parent-kitchen.md",
)
PACKET = ROOT / "scripts" / "course_quality_review.py"

EXPECTED_DIMENSIONS = (
    ("D1", "capability_objective_fit"),
    ("D2", "sequencing_prerequisite_truth"),
    ("D3", "evidence_target_fit"),
    ("D4", "example_explanation_quality"),
    ("D5", "cognitive_load_session_arc"),
    ("D6", "source_grounding_citation_honesty"),
    ("D7", "media_necessity"),
    ("D8", "learner_agency_recoverability"),
)


def load_packet_module():
    spec = importlib.util.spec_from_file_location("course_quality_review", PACKET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def packet_text(validation_name: str = "validation_pass") -> str:
    module = load_packet_module()
    return module.render_packet(
        plan_path=FIXTURES / "plan_one_off.json",
        plan=fixture("plan_one_off"),
        lesson_path=FIXTURES / "lesson_one_off.json",
        lesson=fixture("lesson_one_off"),
        validation_path=FIXTURES / f"{validation_name}.json",
        validation=fixture(validation_name),
        sample_id="TEST-S1",
        scope="single",
        reviewer="Test Reviewer",
    )


def valid_scores(follow_up: str = "t_c7fff5b4") -> dict:
    return {
        dimension_id: {
            "score": 3,
            "evidence": (
                f"{dimension_id}: reviewed plan_one_off.json and lesson_one_off.json; "
                "the field named here carries the evidence for this dimension."
            ),
            "follow_up": "none",
        }
        for dimension_id, _ in EXPECTED_DIMENSIONS
    }


class RubricFileTest(unittest.TestCase):
    def test_rubric_exists_and_names_all_eight_dimensions(self) -> None:
        self.assertTrue(RUBRIC.is_file(), "docs/COURSE-QUALITY-RUBRIC.md is missing")
        text = RUBRIC.read_text(encoding="utf-8")
        for dimension_id, dimension_name in EXPECTED_DIMENSIONS:
            self.assertIn(dimension_id, text, f"rubric does not name {dimension_id}")
            self.assertIn(dimension_name, text, f"rubric does not name {dimension_name}")
        for anchor in ("| 1 |", "| 2 |", "| 3 |", "| 4 |"):
            self.assertIn(anchor, text, f"rubric has no 1-4 scale anchor {anchor}")

    def test_rubric_forbids_score_as_mastery_and_engagement(self) -> None:
        text = RUBRIC.read_text(encoding="utf-8")
        self.assertIn("These are refused as evidence", text)
        for refused in (
            "mastery score",
            "mastery percentage",
            "engagement metrics",
            "time-to-complete promises",
            "learning-styles diagnosis",
            "leaderboards",
            "quality badges",
            "average or total quality scores",
        ):
            self.assertIn(refused, text, f"rubric does not refuse {refused!r}")
        # The refusals are not hedged into a maybe: the section is binding.
        self.assertIn("not merely deprioritised", text)
        self.assertIn("A score of 4 is never required for release", text)
        self.assertIn("Three rules for scoring", text)

    def test_rubric_is_distinct_from_the_ui_quality_bar(self) -> None:
        text = RUBRIC.read_text(encoding="utf-8")
        self.assertIn("docs/EXPERIENCE-QUALITY-BAR.md", text)
        self.assertIn("That file judges the surface", " ".join(text.split()))
        self.assertIn("This file judges the course", text)
        self.assertIn("does not replace the validator's structural pass", text)

    def test_quality_bar_and_experience_review_link_the_rubric(self) -> None:
        bar = (DOCS / "EXPERIENCE-QUALITY-BAR.md").read_text(encoding="utf-8")
        review = (DOCS / "EXPERIENCE-REVIEW.md").read_text(encoding="utf-8")
        self.assertIn("docs/COURSE-QUALITY-RUBRIC.md", bar)
        self.assertIn("docs/COURSE-QUALITY-RUBRIC.md", review)
        self.assertIn("docs/H173-COURSE-QUALITY-REVIEW.md", bar)
        self.assertIn("docs/H173-COURSE-QUALITY-REVIEW.md", review)
        self.assertIn("separate lens", bar)
        self.assertIn("separate bar", review)


class PacketTest(unittest.TestCase):
    def test_packet_writes_facts_blank_scores_and_the_validator_verdict(self) -> None:
        text = packet_text("validation_pass")
        self.assertIn("Validator verdict: pass", text)
        for dimension_id, dimension_name in EXPECTED_DIMENSIONS:
            self.assertIn(f"### {dimension_id} {dimension_name}", text)
            self.assertEqual(text.count(f"### {dimension_id} "), 1)
        self.assertEqual(text.count("Score: "), 8, "packet must leave eight blank score fields")
        self.assertIn("This record is not a mastery score", text)
        self.assertNotIn("mastery_score", text)
        self.assertNotIn("percent_mastered", text)
        self.assertNotIn("overall score", text.lower())
        # Facts, not reference-answer text: the packet must not leak the key into the record.
        self.assertNotIn("Both pads replaced, wheel seated", text)
        self.assertIn("Reference answer present: yes (not reproduced here)", text)

    def test_packet_echoes_a_reject_without_turning_it_into_a_pass(self) -> None:
        text = packet_text("validation_reject_hazard")
        self.assertIn("Validator verdict: reject", text)
        self.assertIn("hazard_age_appropriateness: fail", text)
        self.assertIn("child operate a kettle unattended", text)
        self.assertNotIn("Validator verdict: pass", text)

    def test_packet_refuses_a_malformed_input(self) -> None:
        module = load_packet_module()
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "plan.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(module.PacketError) as raised:
                module.load_json(bad, "plan")
            self.assertIn("not valid JSON", str(raised.exception))

    def test_packet_script_is_stdlib_only_and_cannot_change_rpc(self) -> None:
        source = PACKET.read_text(encoding="utf-8")
        self.assertNotIn("import coursebook", source)
        self.assertNotIn("from coursebook", source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("http", source)
        self.assertNotIn("cb.rpc", source)
        self.assertIn("MAX_INPUT_BYTES", source)
        self.assertIn("MAX_RECORD_BYTES", source)


class RecordCheckTest(unittest.TestCase):
    def test_blank_dimensions_are_not_a_review(self) -> None:
        module = load_packet_module()
        errors = module.check_record(packet_text())
        self.assertTrue(errors)
        joined = "\n".join(errors)
        for dimension_id, _ in EXPECTED_DIMENSIONS:
            self.assertIn(f"{dimension_id}: Score is blank", joined)

    def test_fill_requires_evidence_for_every_dimension(self) -> None:
        module = load_packet_module()
        scores = valid_scores()
        scores["D3"]["evidence"] = "too short"
        with self.assertRaises(module.PacketError) as raised:
            module.fill_packet(packet_text(), scores)
        self.assertIn("D3.evidence", str(raised.exception))

    def test_fill_requires_a_follow_up_card_below_three(self) -> None:
        module = load_packet_module()
        scores = valid_scores()
        scores["D6"]["score"] = 2
        scores["D6"]["follow_up"] = "none"
        with self.assertRaises(module.PacketError) as raised:
            module.fill_packet(packet_text(), scores)
        self.assertIn("below 3 needs a follow-up", str(raised.exception))

    def test_fill_rejects_an_unknown_dimension(self) -> None:
        module = load_packet_module()
        scores = valid_scores()
        scores["D9"] = {"score": 3, "evidence": "x" * 80, "follow_up": "none"}
        with self.assertRaises(module.PacketError) as raised:
            module.fill_packet(packet_text(), scores)
        self.assertIn("unknown dimensions D9", str(raised.exception))

    def test_filled_record_passes_and_a_validator_verdict_is_echoed(self) -> None:
        module = load_packet_module()
        filled = module.fill_packet(packet_text("validation_reject_check"), valid_scores())
        self.assertEqual(module.check_record(filled), [])
        self.assertIn("Validator verdict: reject", filled)
        self.assertIn("Recorded verdict: reject", filled)

    def test_checker_rejects_mastery_and_aggregate_language(self) -> None:
        module = load_packet_module()
        filled = module.fill_packet(packet_text(), valid_scores())
        tampered = filled.replace(
            "the field named here carries the evidence for this dimension.",
            "Overall score 87 percent mastery. Leaderboard position 2.",
        )
        errors = module.check_record(tampered)
        joined = "\n".join(errors)
        self.assertIn("overall score", joined)
        self.assertIn("leaderboard", joined)


class CommittedRecordTest(unittest.TestCase):
    def test_every_committed_review_record_passes_the_checker(self) -> None:
        module = load_packet_module()
        for path in REVIEW_RECORDS:
            self.assertTrue(path.is_file(), f"{path} is missing")
            text = path.read_text(encoding="utf-8")
            self.assertEqual(module.check_record(text), [], f"{path} is not a valid record")
            self.assertIn("Quill (rubric author, author-run dry run)", text)
            self.assertIn("H-172", text, "the record must state the fixture limitation")

    def test_each_below_three_dimension_names_a_follow_up_card(self) -> None:
        pattern = re.compile(
            r"^### (D[1-8]) [a-z_]+.*?^Score: ([1-4])$.*?^Follow-up: (\S+)$",
            re.MULTILINE | re.DOTALL,
        )
        for path in REVIEW_RECORDS:
            text = path.read_text(encoding="utf-8")
            matches = pattern.findall(text)
            self.assertEqual(len(matches), 8, f"{path} does not carry eight scored dimensions")
            for dimension_id, score, follow_up in matches:
                if int(score) < 3:
                    self.assertRegex(
                        follow_up,
                        r"^(t_[0-9a-f]{6,}|H-\d+[A-Za-z]?)$",
                        f"{path} {dimension_id} is below 3 without a card",
                    )
                else:
                    self.assertEqual(
                        follow_up,
                        "none",
                        f"{path} {dimension_id} is at least 3 but names a follow-up",
                    )

    def test_summary_names_the_three_samples_and_the_validator_truth(self) -> None:
        self.assertTrue(REVIEW_SUMMARY.is_file(), "docs/H173-COURSE-QUALITY-REVIEW.md is missing")
        text = REVIEW_SUMMARY.read_text(encoding="utf-8")
        for sample in ("S1", "S2", "S3"):
            self.assertIn(f"| {sample} |", text)
        self.assertIn("validator", text.lower())
        self.assertIn("H-172", text)
        self.assertIn("author-run dry run", text)
        self.assertIn("not a mastery", text.lower())
        self.assertNotIn("average score", text.lower())
        self.assertNotIn("leaderboard", text.lower())


if __name__ == "__main__":
    unittest.main()
