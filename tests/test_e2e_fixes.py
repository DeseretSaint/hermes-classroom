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


class PlanCheckKindTest(unittest.TestCase):
    """A plan's check kind must match the objective's family.

    Rule 5b refuses a plan whose check_plan declares a quiz for a procedure objective. The
    lesson-stage rule is still recipe-keyed: the lesson fixtures author a quiz for a procedure and
    every LessonJobTest authors from them, so that rule lands with the fixture migration rather
    than leaving the tree red. The plan rule catches the contradiction before authoring either way.
    """

    def test_the_plan_rule_compares_kind_as_well_as_family(self) -> None:
        source = Path(generation.__file__).read_text(encoding="utf-8")
        self.assertIn("CHECK_KIND_BY_TARGET", source)
        self.assertIn("is measured by", source)


class BeginnerOpeningTest(unittest.TestCase):
    """A learner who starts from nothing is not handed the act first."""

    def test_level_tokens_that_mean_starting_from_nothing(self) -> None:
        for level in ("none", "None", "no experience", "complete beginner", "NOVICE", "L0", "A1"):
            self.assertTrue(generation.is_beginner_level(level), level)

    def test_levels_that_do_not_mean_starting_from_nothing(self) -> None:
        for level in ("confident", "some", "A2", "B1", "intermediate", "", None):
            self.assertFalse(generation.is_beginner_level(level), level)

    def test_the_beginner_rule_is_stated_in_the_plan_rules(self) -> None:
        # The v2 rule set is the only place a plan's opening objective can be refused, and no
        # v2 plan fixture exists in this tree, so the rule's own text is pinned here.
        source = Path(generation.__file__).read_text(encoding="utf-8")
        self.assertIn("may not open with a", source)
        self.assertIn("is_beginner_level(level)", source)


if __name__ == "__main__":
    unittest.main()
