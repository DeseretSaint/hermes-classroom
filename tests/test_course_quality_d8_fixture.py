"""H-173d: the D8 copy fix on the S1 and S3 lesson fixtures.

The independent H-173d re-score (``docs/reviews/H173d-S1-independent.md`` and
``-S3-independent.md``) scored D8 = 2 on both fixtures because
``check.assistance_policy.hint`` said ``available`` while no hint text existed, and no
lesson copy stated what a learner or parent does after a failed attempt.

These tests prove the fix lives in the lesson copy, not only in a review record, and that
both edited lessons still satisfy the generation schema and rules. They do not run the
validator, do not call a provider, and do not change a score.

Run: ``python3 -m unittest tests.test_course_quality_d8_fixture``
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from coursebook import generation

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "generation"

#: The review records that scored D8 = 2 quote these bytes; a later edit must update the
#: superseded-bytes notes in ``docs/reviews/H173a-*`` and ``docs/reviews/H173c-*``.
FIXED_D8_RECORDS = (
    "H173a-S1-single-brake-rescored.md",
    "H173c-S3-parent-kitchen-rescore.md",
)


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def schema_errors(document: dict) -> list[str]:
    return [
        f"{list(error.path)}: {error.message}"
        for error in Draft202012Validator(generation.LESSON_SCHEMA).iter_errors(document)
    ]


class S1RecoveryCopyTest(unittest.TestCase):
    """The self-study checklist states a hint and a next move after a failed attempt."""

    def setUp(self) -> None:
        self.plan = load("plan_one_off")
        self.lesson = load("lesson_one_off")
        self.copy = self.lesson["check"]["learner_instructions"]

    def test_lesson_still_validates_and_passes_the_one_off_rules(self) -> None:
        self.assertEqual(schema_errors(self.lesson), [])
        generation.enforce_lesson_rules(
            self.lesson,
            section=self.plan["sections"][0],
            objective=self.plan["objectives"][0],
            recipe="one_off",
            locale=None,
            dials={},
            ledger=None,
        )

    def test_hint_text_exists_because_the_policy_claims_a_hint(self) -> None:
        self.assertEqual(self.lesson["check"]["assistance_policy"]["hint"], "available")
        self.assertIn("Hint:", self.copy)
        # The hint is specific to this procedure, not a generic "try again".
        self.assertIn("fastener will not turn by hand", self.copy)
        self.assertIn("re-read segment", self.copy)

    def test_a_failed_attempt_has_a_stated_next_move(self) -> None:
        self.assertIn("If you cannot tick an item", self.copy)
        self.assertIn("leave it unticked", self.copy)
        self.assertIn("re-read the segment that covers it", self.copy)
        self.assertIn("submit again", self.copy)
        self.assertIn("a retry records the same self-report, not a pass", self.copy)

    def test_the_hazard_stop_is_still_stated(self) -> None:
        body = " ".join(segment["body"] for segment in self.lesson["segments"]).lower()
        self.assertIn("stop if the caliper moves or the fastener will not turn by hand", body)


class S3RecoveryCopyTest(unittest.TestCase):
    """The parent-led observation states a hint and the same retry move on both surfaces."""

    def setUp(self) -> None:
        self.plan = load("plan_parent")
        self.lesson = load("lesson_parent_safe")
        self.copy = self.lesson["check"]["learner_instructions"]
        self.notes = self.lesson["parent_notes"] or ""
        self.text = json.dumps(self.lesson).lower()

    def test_lesson_still_validates_and_passes_the_parent_rules(self) -> None:
        self.assertEqual(schema_errors(self.lesson), [])
        generation.enforce_lesson_rules(
            self.lesson,
            section=self.plan["sections"][0],
            objective=self.plan["objectives"][0],
            recipe="parent",
            locale=None,
            dials={},
            ledger=None,
        )

    def test_hint_text_exists_because_the_policy_claims_a_hint(self) -> None:
        self.assertEqual(self.lesson["check"]["assistance_policy"]["hint"], "available")
        self.assertIn("Hint:", self.copy)
        self.assertIn("point at the card and say its name", self.copy)

    def test_a_failed_attempt_has_a_stated_next_move_on_both_surfaces(self) -> None:
        for surface in (self.copy, self.notes):
            self.assertIn("If the child sorts a card wrong or cannot name one", surface)
            self.assertIn("put the cards back, name each card together", surface)
            self.assertIn("try the sort again", surface)
            self.assertIn("write down the retry", surface)

    def test_the_hazard_gate_is_not_weakened(self) -> None:
        self.assertIn("within arm's reach", self.notes)
        self.assertIn("unplugged and out of reach", self.notes)
        self.assertIn("stop, move it further away and go back to the cards", self.notes)
        self.assertNotIn("fill the kettle", self.text)
        self.assertNotIn("switch it on", self.text)
        self.assertIn("never fills or switches on the kettle", self.text)


class SupersededBytesNoteTest(unittest.TestCase):
    """The author-run records that quote the old bytes say so, without rewriting a score."""

    def test_earlier_records_mark_the_fixture_bytes_superseded(self) -> None:
        for name in FIXED_D8_RECORDS:
            text = (ROOT / "docs" / "reviews" / name).read_text(encoding="utf-8")
            self.assertIn("Superseded bytes", text, name)


if __name__ == "__main__":
    unittest.main()
