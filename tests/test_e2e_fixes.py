"""E2E fixes: a one-off brief follows its scope, and a check kind follows the evidence target.

These tests pin the two rules that made a hands-on course un-authorable:

1. "One task" paired with a short or full course was refused on every attempt, because the
   create screen sends the recipe and the size independently. The pair is now rewritten to the
   size's default recipe instead of being stored as a contradiction.
2. Every recipe except ``one_off`` and ``parent`` required ``check.kind == "quiz"``, while the
   plan prompt requires a procedure objective to be evidenced by a performance checklist. A
   head-gasket lesson could therefore only be authored as a quiz *about* the procedure.

Run: ``python3 -m unittest tests.test_e2e_fixes``
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from coursebook import generation

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "generation"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class CoerceRecipeScopeTest(unittest.TestCase):
    """A one-off brief is the single-lesson shape, so a larger size wins."""

    def test_a_one_off_paired_with_a_short_course_becomes_casual(self) -> None:
        self.assertEqual(generation.coerce_recipe_scope("one_off", "short"), ("casual", "short"))

    def test_a_one_off_paired_with_a_full_course_becomes_committed(self) -> None:
        self.assertEqual(
            generation.coerce_recipe_scope("one_off", "full"), ("committed", "full")
        )

    def test_a_one_off_paired_with_single_is_untouched(self) -> None:
        self.assertEqual(generation.coerce_recipe_scope("one_off", "single"), ("one_off", "single"))

    def test_an_ordinary_recipe_is_untouched(self) -> None:
        self.assertEqual(generation.coerce_recipe_scope("casual", "short"), ("casual", "short"))
        self.assertEqual(generation.coerce_recipe_scope("committed", None), ("committed", None))


class ProcedureCheckKindTest(unittest.TestCase):
    """A procedure is evidenced by a verification checklist under every recipe."""

    def setUp(self) -> None:
        self.plan = load("plan_one_off")
        self.lesson = load("lesson_one_off")
        self.section = self.plan["sections"][0]
        self.objective = self.plan["objectives"][0]
        self.assertEqual(self.objective["evidence_target"], "procedure")

    def rules(self, lesson: dict, recipe: str) -> None:
        generation.enforce_lesson_rules(
            lesson,
            section=self.section,
            objective=self.objective,
            recipe=recipe,
            locale=None,
            dials={},
            ledger=None,
        )

    def test_a_procedure_verification_check_passes_under_casual(self) -> None:
        self.assertEqual(self.lesson["check"]["kind"], "verification")
        # Was refused with "this recipe needs a graded check" before the fix.
        self.rules(self.lesson, "casual")

    def test_a_procedure_verification_check_passes_under_committed(self) -> None:
        self.rules(self.lesson, "committed")

    def test_a_quiz_about_a_procedure_is_refused(self) -> None:
        lesson = copy.deepcopy(self.lesson)
        lesson["check"]["kind"] = "quiz"
        with self.assertRaises(generation._RuleViolation) as caught:
            self.rules(lesson, "casual")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("procedure", reasons)
        self.assertIn("verification", reasons)


if __name__ == "__main__":
    unittest.main()
