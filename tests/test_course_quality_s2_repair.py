"""H-173b: the repaired S2 fixture is pipeline-legal and its re-score holds.

The repair makes the short Japanese café sample score at least 3 on the seven dimensions its
H-173 review found below 3, without touching the validator's recorded rejection, any RPC, schema,
UI or grading behavior. These tests prove the three claims a reader cannot check by eye:

1. the repaired plan and lesson pass the real generation gates (plan rules, lesson rules) and the
   answer-leak gate, so the fixture is a lesson generation could actually store;
2. the check measures the evidence target the objective declares (discrimination, not a
   production label on a selection item);
3. the new review record passes the bounded packet checker and scores D1-D7 at 3 or 4, while the
   recorded validator rejection stays a rejection.

Run: ``python3 -m unittest tests.test_course_quality_s2_repair``
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

from coursebook import generation as gen
from coursebook import lesson_document, research

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "generation"
REVIEW = ROOT / "docs" / "reviews" / "H173b-S2-short-japanese-cafe-repaired.md"
PACKET = ROOT / "scripts" / "course_quality_review.py"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_packet_module():
    spec = importlib.util.spec_from_file_location("course_quality_review", PACKET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_record() -> research.SourceRecord:
    """The ledger entry the plan's SRC_ALPHA stands for, so the plan rules can run."""
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


class RepairedFixtureGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = fixture("plan_ja")
        self.lesson = fixture("lesson_ja")

    def test_repaired_plan_passes_the_generation_rules(self) -> None:
        gen.validate_artifact(gen.PLAN_SCHEMA, self.plan, what="plan")
        gen.enforce_plan_rules(
            self.plan,
            recipe="committed",
            dials={"level": "L0"},
            locale="ja-JP",
            ledger=[source_record()],
            scope="short",
        )

    def test_schedule_covers_every_authored_section(self) -> None:
        estimate = self.plan["time_estimate"]
        capacity = estimate["sessions_per_week"] * estimate["weeks"]
        self.assertGreaterEqual(capacity, len(self.plan["sections"]))

    def test_repaired_lesson_passes_the_generation_rules_and_leak_gate(self) -> None:
        gen.validate_artifact(gen.LESSON_SCHEMA, self.lesson, what="lesson")
        section = self.plan["sections"][0]
        objective = self.plan["objectives"][0]
        gen.enforce_lesson_rules(
            self.lesson,
            section=section,
            objective=objective,
            recipe="committed",
            locale="ja-JP",
            dials={"level": "L0"},
            ledger=[source_record()],
        )
        page = gen._build_learner_page(self.lesson, section, [source_record()], locale="ja-JP")
        document = lesson_document.document_from_page(page, check_id="chk_s2_fixture")
        gen.assert_no_answer_leak({**page, "document": document}, self.lesson)

    def test_check_target_and_plan_target_are_the_same_discrimination_family(self) -> None:
        objective = self.plan["objectives"][0]
        entry = self.plan["check_plan"][0]
        check = self.lesson["check"]
        self.assertEqual(objective["evidence_target"], "discrimination")
        self.assertEqual(entry["evidence_target"], objective["evidence_target"])
        self.assertEqual(check["evidence_target"], objective["evidence_target"])
        self.assertEqual(check["stimulus"]["format"], "selection")
        # The keyed phrase is a permitted stimulus choice, never an announced narrative answer.
        self.assertIn(check["reference_answer"], check["stimulus"]["choices"])


class RepairedReviewRecordTest(unittest.TestCase):
    def test_record_passes_the_packet_checker(self) -> None:
        module = load_packet_module()
        errors = module.check_record(REVIEW.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])

    def test_the_seven_repaired_dimensions_score_at_least_three(self) -> None:
        text = REVIEW.read_text(encoding="utf-8")
        scores = {
            match.group(1): int(match.group(2))
            for match in re.finditer(r"^### (D[1-8]) [a-z_]+\n(?:Question:.*\n)Score: ([1-4])$",
                                     text, re.MULTILINE)
        }
        self.assertEqual(sorted(scores), [f"D{i}" for i in range(1, 9)])
        for dimension in ("D1", "D2", "D3", "D4", "D5", "D6", "D7"):
            with self.subTest(dimension=dimension):
                self.assertGreaterEqual(scores[dimension], 3)

    def test_the_recorded_validator_rejection_is_unchanged(self) -> None:
        record = fixture("validation_reject_check")
        self.assertEqual(record["verdict"], "reject")
        failed = {
            item["id"]: item["verdict"]
            for item in record["criteria"]
            if item["verdict"] != "pass"
        }
        self.assertEqual(
            failed,
            {"answer_uniqueness": "fail", "alternative_coverage": "fail"},
        )
        self.assertEqual([item["criterion"] for item in record["rejections"]], ["answer_uniqueness"])
        # The repaired record must not turn that rejection into a pass.
        self.assertIn("Validator verdict: reject", REVIEW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
