"""CP-015c-ja: the one further lessons pass, pinned as a red result.

The pass re-authored the three parked owner sections through ``lesson.regenerate`` (the same route
a parent uses) and then ran one unit lessons job, which authored the review section under CP-015j.
Every owner page was parked ``needs_review`` again on a real rule, so the card stops: no pack, no
Workshop entry and no install proof may be claimed.

These tests read the committed evidence document, not the live backend, so they fail if the packet
or the evidence starts telling a greener story than the run produced.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = ROOT / "docs" / "concept-parity" / "demo" / "cp015c-lessons-pass.json"
PACKET = ROOT / "docs" / "concept-parity" / "demo" / "CP-015c-REVIEW.md"

#: Owner ruling 2026-11-10: nothing a learner reads may say demo, sample or fixture.
FIXTURE_WORDING = re.compile(r"demo|sample|fixture", re.IGNORECASE)


def evidence() -> dict:
    return json.loads(PASS.read_text(encoding="utf-8"))


def sections_after() -> list[dict]:
    return evidence()["review"]["sections_after"]


class LessonsPassEvidenceTest(unittest.TestCase):
    def test_every_section_was_attempted_and_still_parked(self) -> None:
        sections = sections_after()
        self.assertEqual([row["ordinal"] for row in sections], [1, 2, 3, 4])
        for row in sections:
            lesson = row.get("lesson") or {}
            self.assertEqual(lesson.get("state"), "needs_review", row["title"])
            reasons = json.loads(lesson.get("rejection_reasons_json") or "[]")
            self.assertTrue(reasons, f"section {row['ordinal']} parked with no reason")

    def test_the_owner_pages_were_re_authored_at_a_new_version(self) -> None:
        before = {(row["ordinal"], (row.get("lesson") or {}).get("version"))
                  for row in evidence()["sections_before"]}
        after = {(row["ordinal"], (row.get("lesson") or {}).get("version"))
                 for row in sections_after()}
        for ordinal in (1, 2, 3):
            self.assertIn((ordinal, 2), after, f"section {ordinal} was not re-authored")
            self.assertIn((ordinal, 1), before, f"section {ordinal} had no prior version")

    def test_the_review_section_authored_against_closed_owner_checks(self) -> None:
        review = next(row for row in sections_after() if row["section_role"] == "review")
        lesson = review["lesson"]
        self.assertEqual(lesson["state"], "needs_review")
        reasons = json.loads(lesson["rejection_reasons_json"])
        self.assertTrue(any("presents a closed owner check" in reason for reason in reasons),
                        reasons)
        # CP-015j names each owner lesson behind the closed check instead of failing the job.
        for ordinal in (1, 2, 3):
            owner = next(row for row in sections_after() if row["ordinal"] == ordinal)
            self.assertIn(owner["lesson"]["id"], reasons[0])

    def test_export_refuses_and_no_section_is_validated(self) -> None:
        export = evidence()["export_read"]
        self.assertFalse(export["ready"])
        self.assertEqual(export["blocked_reason"], "lessons_not_validated")
        self.assertEqual(export["sections"], {"total": 4, "validated": 0})
        self.assertIsNone(export["content_hash"])

    def test_no_section_title_carries_fixture_wording(self) -> None:
        for row in sections_after():
            self.assertIsNone(FIXTURE_WORDING.search(str(row["title"])), row["title"])

    def test_the_packet_reports_the_red_result_not_a_pass(self) -> None:
        text = PACKET.read_text(encoding="utf-8")
        self.assertIn("not authorable to export", text)
        self.assertIn("This is a red result", text)
        self.assertIn("lessons_not_validated", text)
        # The absence table must mark the unreached milestones absent, never passed.
        lines = [line.lower() for line in text.splitlines()]
        for claim in ("one approved world and one rendered lesson page",
                      "pack manifest valid; workshop entry",
                      "visual review; real plate"):
            matching = [line for line in lines if line.startswith(f"| {claim}")]
            self.assertTrue(matching, claim)
            self.assertIn("absent", matching[0], claim)
            self.assertNotIn("pass", matching[0], claim)


if __name__ == "__main__":
    unittest.main()
