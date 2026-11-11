"""XP measures demonstrated learning, not activity.

The owner's rule: XP must be real. A bare-minimum action must not pay what a checkpoint pays, a
hinted answer must not pay what an independent one pays, and presence, reading or a daily check-in
must pay nothing at all. These tests pin the formula and the two properties that make the number
checkable later: it is derived from the graded row, and it can be recomputed from the response.
"""

from __future__ import annotations

import unittest

from coursebook import engagement


class XpFormulaTest(unittest.TestCase):
    """The pure formula: base by evidence target, times verdict, times independence."""

    def test_a_checkpoint_pays_more_than_a_recall_question_at_the_same_quality(self) -> None:
        recall = engagement.xp_for_evidence("recall", "pass", "cold")
        transfer = engagement.xp_for_evidence("transfer", "pass", "cold")
        self.assertGreater(transfer, recall)
        # The gap has to be a real difference, not one point: a checkpoint is worth several
        # recall questions, because that is what it asks of the learner.
        self.assertGreaterEqual(transfer, recall * 3)

    def test_every_evidence_target_pays_more_than_the_one_below_it(self) -> None:
        ladder = ["recall", "comprehension", "discrimination", "production", "procedure", "transfer"]
        points = [engagement.xp_for_evidence(target, "pass", "cold") for target in ladder]
        self.assertEqual(points, sorted(points))
        self.assertEqual(len(set(points)), len(points), "two targets must not pay the same")

    def test_a_hinted_pass_pays_half_and_a_shown_answer_pays_a_fifth(self) -> None:
        cold = engagement.xp_for_evidence("comprehension", "pass", "cold")
        hinted = engagement.xp_for_evidence("comprehension", "pass", "hinted")
        shown = engagement.xp_for_evidence("comprehension", "pass", "answer_shown")
        self.assertEqual(hinted, round(cold * 0.5))
        self.assertEqual(shown, round(cold * 0.2))
        self.assertLess(shown, hinted)

    def test_partial_credit_pays_less_and_a_failed_verdict_pays_nothing(self) -> None:
        full = engagement.xp_for_evidence("procedure", "pass", "cold")
        partial = engagement.xp_for_evidence("procedure", "partial", "cold")
        self.assertLess(partial, full)
        for verdict in ("not_yet", "needs_retry", "clarification", ""):
            self.assertEqual(engagement.xp_for_evidence("procedure", verdict, "cold"), 0, verdict)

    def test_an_unknown_target_or_class_pays_nothing_rather_than_a_default(self) -> None:
        self.assertEqual(engagement.xp_for_evidence("vibes", "pass", "cold"), 0)
        self.assertEqual(engagement.xp_for_evidence("recall", "pass", "guessed"), 0)

    def test_the_same_facts_always_pay_the_same(self) -> None:
        first = engagement.xp_for_evidence("production", "pass", "cold")
        for _ in range(5):
            self.assertEqual(engagement.xp_for_evidence("production", "pass", "cold"), first)

    def test_a_pass_from_any_route_pays_at_least_one(self) -> None:
        # Rounding must never turn a genuine pass into a zero: zero is reserved for "no evidence".
        self.assertGreaterEqual(engagement.xp_for_evidence("recall", "pass", "answer_shown"), 1)


class XpBasisTest(unittest.TestCase):
    """The sentence the learner reads is built from the same facts as the number."""

    def test_the_basis_names_the_target_and_how_independent_the_answer_was(self) -> None:
        text = engagement.xp_basis("procedure", "pass", "cold")
        self.assertIn("procedure", text)
        self.assertIn("without help", text)
        self.assertIn(str(engagement.xp_for_evidence("procedure", "pass", "cold")), text)

    def test_a_hinted_basis_says_so_and_a_failure_says_there_is_no_xp(self) -> None:
        self.assertIn("with a hint", engagement.xp_basis("recall", "pass", "hinted"))
        self.assertIn("partial credit", engagement.xp_basis("recall", "partial", "cold"))
        self.assertEqual(
            engagement.xp_basis("recall", "not_yet", "cold"), "no XP: the check did not pass"
        )


class ActivityPaysNothingTest(unittest.TestCase):
    """Presence is not learning, and the module says which real actions are refused."""

    def test_reading_a_page_and_returning_are_named_as_not_evidence(self) -> None:
        self.assertIn("lesson_step", engagement.NOT_EVIDENCE_REASON)
        self.assertIn("returned", engagement.NOT_EVIDENCE_REASON)

    def test_no_base_weight_exists_for_a_kind_that_is_only_presence(self) -> None:
        # The old flat table paid 5 for a page open. There is no such table now.
        self.assertFalse(hasattr(engagement, "XP_POINTS"))
        self.assertNotIn("lesson_step", engagement.XP_BASE_BY_TARGET)

    def test_review_pays_the_top_base_because_spaced_retrieval_is_the_best_evidence(self) -> None:
        self.assertEqual(engagement.REVIEW_XP, max(engagement.XP_BASE_BY_TARGET.values()))


if __name__ == "__main__":
    unittest.main()
