"""H-103: the reasons a plan was rejected reach plan review on the job checkpoint.

`run_plan_job` already stores `rejection_reasons`, the validation provenance and the approval
provenance in `gen_plan_documents`. Plan review reads a job, not that table, so the executor has to
carry those recorded fields on the checkpoint. This test calls the real plan stage with a canned
`run_plan_job` result: it proves the passthrough is complete and that a clean run adds no invented
reason.

What this does NOT prove: that a live provider rejects a real topic. That is the plan probe's job.
"""

from __future__ import annotations

import unittest
from unittest import mock

from coursebook import executor, job_service


class _FakeConnection:
    def close(self) -> None:
        pass


class PlanCheckpointRejectionTest(unittest.TestCase):
    def _checkpoint(self, result: dict) -> dict:
        lease = job_service.Lease("job_plan_1", "att_1", "test", "2099-01-01T00:00:00+00:00")
        stage = executor._Resolvers(llm=object(), search=None, now=None)._plan_stage({"goal": "Order coffee"})
        with mock.patch.object(executor.db, "connect", return_value=_FakeConnection()), mock.patch.object(
            executor.job_service, "cancel_requested", return_value=False
        ), mock.patch.object(executor.generation, "run_plan_job", return_value=result):
            outcome = stage(lease)
        return outcome.checkpoint

    def test_recorded_rejection_reasons_and_provenance_travel_on_the_checkpoint(self) -> None:
        result = {
            "plan_id": "plan_1",
            "plan_hash": "hash_1",
            "plan_version": 1,
            "status": "needs_review",
            "objectives": 3,
            "validation_verdict": "reject",
            "rejection_reasons": [
                "objective 2: claims 'sourced' support without a ledger source"
            ],
            "validation": {
                "outcome": "rejected",
                "independence": "same_model",
                "research_status": "available",
            },
            "approval_provenance": {"outcome": "rejected", "needs_review": True},
        }
        checkpoint = self._checkpoint(result)
        self.assertEqual(
            checkpoint["rejection_reasons"],
            ["objective 2: claims 'sourced' support without a ledger source"],
        )
        self.assertEqual(checkpoint["validation_verdict"], "reject")
        self.assertEqual(checkpoint["validation"]["outcome"], "rejected")
        self.assertEqual(checkpoint["approval_provenance"]["needs_review"], True)
        # The state the review branches on is still the generation state, unchanged.
        self.assertEqual(checkpoint["generation_state"], "needs_review")

    def test_a_clean_result_does_not_invent_a_reason(self) -> None:
        result = {
            "plan_id": "plan_2",
            "plan_hash": "hash_2",
            "plan_version": 1,
            "status": "draft",
            "objectives": 4,
            "validation_verdict": "pass",
            "validation": {"outcome": "independently_validated"},
        }
        checkpoint = self._checkpoint(result)
        self.assertEqual(checkpoint["rejection_reasons"], [])
        self.assertEqual(checkpoint["validation_verdict"], "pass")
        self.assertEqual(checkpoint["generation_state"], "draft")


if __name__ == "__main__":
    unittest.main()
