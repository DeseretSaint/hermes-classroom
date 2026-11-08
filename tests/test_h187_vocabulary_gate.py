"""H-187 — the vocabulary-sequence rule is a language-course rule.

Measured live on the merged tree: a non-language ``committed`` plan (a cooking course, no locale)
was refused twice by ``frequency.plan_vocabulary_reasons`` because the author model had set
``target_items`` on its objectives. A non-language brief is never asked for that field — the plan
prompt carries no vocabulary block at all — so the plan had no legal way to satisfy the rule and
the job ended ``needs_review`` / ``rejected`` without ever reaching the validator.

The gate is on the *declared locale*: a language course keeps the rule exactly as strict, and a
non-language plan's inert ``target_items`` cannot fail it.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from tests.blueprint_support import blueprint_plan


def plan_with_target_items() -> dict:
    plan = blueprint_plan(scope="single")
    for objective in plan["objectives"]:
        objective["target_items"] = ["anchor choice"]
    return plan


class VocabularyRuleLocaleGateTest(unittest.TestCase):
    def test_a_non_language_plan_is_not_refused_for_inert_target_items(self) -> None:
        plan = plan_with_target_items()
        # No locale: the brief declares no language, so there is no inventory to check against.
        gen.enforce_plan_rules(plan, recipe="casual", dials={}, locale=None, ledger=[], scope="single")

    def test_a_language_plan_without_an_inventory_is_still_refused(self) -> None:
        plan = plan_with_target_items()
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan, recipe="casual", dials={}, locale="es-ES", ledger=[], scope="single"
            )
        reasons = "\n".join(caught.exception.reasons)
        self.assertIn("no frequency inventory is available", reasons)
        self.assertIn("declares target item", reasons)


if __name__ == "__main__":
    unittest.main()
