"""A cited source that contradicts the lesson cannot be a pass.

``validation_verdict`` used to count only the declared verdict, the rubric criteria and the
rejections. A claim the validator itself marked ``contradictory`` was recorded in the ledger and
then ignored, so a lesson whose footnote disagreed with a cited source could still carry
``outcome: independently_validated``. The claim is now a rejection in its own right.
"""
from __future__ import annotations

import unittest

from coursebook import generation, research


class ContradictedClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = [
            research.SourceRecord(
                source_id="src-1",
                url="https://example.org/pruning",
                title="Pruning figs",
                publisher="Example",
                source_type="web_page",
                fetched_at="2026-11-11T00:00:00Z",
                published_at=None,
                content_hash="sha256:" + "a" * 64,
                support_status="unverified",
                excerpt="Pruning in late winter removes the fruiting wood from last season.",
                excerpt_state="recorded",
            )
        ]
        self.report = {
            "verdict": "pass",
            "criteria": [{"id": "source_support", "verdict": "pass", "reason": "cited"}],
            "claim_verdicts": [
                {
                    "item": "Prune after the fruit has set.",
                    "support": "contradictory",
                    "reason": "the source says pruning removes the fruiting wood, so fruit would not follow",
                    "source_id": "src-1",
                    "evidence_quote": "removes the fruiting wood from last season",
                }
            ],
        }

    def test_a_contradicted_claim_rejects_the_artifact(self) -> None:
        verdict = generation.validation_verdict(
            self.report,
            research_status="ok",
            ledger=self.ledger,
            independence=generation.INDEPENDENCE_INDEPENDENT,
            criteria=("source_support",),
        )
        self.assertEqual(verdict["verdict"], "reject")
        self.assertEqual(verdict["outcome"], generation.OUTCOME_REJECTED)
        self.assertTrue(
            any("claim_contradicted" in reason for reason in verdict["rejections"]),
            verdict["rejections"],
        )
        # The claim verdict itself is preserved: the author is told what disagreed, not just "no".
        self.assertEqual(verdict["claim_verdicts"][0]["support"], "contradictory")

    def test_a_supported_claim_still_passes(self) -> None:
        report = dict(self.report)
        report["claim_verdicts"] = [{**self.report["claim_verdicts"][0], "support": "supported"}]
        verdict = generation.validation_verdict(
            report,
            research_status="ok",
            ledger=self.ledger,
            independence=generation.INDEPENDENCE_INDEPENDENT,
            criteria=("source_support",),
        )
        self.assertEqual(verdict["verdict"], "pass")
        self.assertEqual(verdict["rejections"], [])


if __name__ == "__main__":
    unittest.main()
