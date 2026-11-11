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


class VocabularyRuleDomainGateTest(unittest.TestCase):
    """CP-015: the live create flow always sends a locale, so the locale test was always true.

    Measured on the demo backend: a ``Sourdough`` course (``subject_domain: cooking``,
    ``locale: en-US``) authored by the real provider was refused twice with "no frequency
    inventory is available" because the plan author had set ``target_items`` — a field a cooking
    plan is never asked for. The course then sat at ``needs_review`` / ``rejected`` and could not
    be approved. The rule must resolve "is this a language course?" from the declared domain.
    """

    def test_a_cooking_course_with_a_locale_is_not_refused(self) -> None:
        plan = plan_with_target_items()
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale="en-US", ledger=[], scope="single",
            subject_domain="cooking",
        )

    def test_a_repair_course_with_a_locale_is_not_refused(self) -> None:
        plan = plan_with_target_items()
        # `repair` normalises to `technical_procedure`; the alias table is the authority.
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale="en-US", ledger=[], scope="single",
            subject_domain="repair",
        )

    def test_a_declared_language_course_is_still_refused(self) -> None:
        plan = plan_with_target_items()
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan, recipe="casual", dials={}, locale="ja-JP", ledger=[], scope="single",
                subject_domain="language",
            )
        self.assertIn("no frequency inventory is available", "\n".join(caught.exception.reasons))

    def test_an_undeclared_domain_keeps_the_pre_v10_locale_rule(self) -> None:
        # No declared domain: the locale is the only declaration there is, so the historical
        # behaviour (a locale meant a language course) is kept rather than silently widened.
        plan = plan_with_target_items()
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan, recipe="casual", dials={}, locale="es-ES", ledger=[], scope="single"
            )
        self.assertIn("no frequency inventory is available", "\n".join(caught.exception.reasons))

    def test_a_declared_domain_outranks_a_matching_locale(self) -> None:
        # A Japanese-language cooking course is `cooking`: the domain wins over the locale.
        plan = plan_with_target_items()
        gen.enforce_plan_rules(
            plan, recipe="casual", dials={}, locale="ja-JP", ledger=[], scope="single",
            subject_domain="cooking",
        )


if __name__ == "__main__":
    unittest.main()
