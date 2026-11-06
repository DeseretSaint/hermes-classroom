"""Job state machine is contract data, not an ad-hoc enum in the worker code."""

from __future__ import annotations

import unittest

from coursebook import api, contracts, jobs


class JobStateTest(unittest.TestCase):
    def test_states_come_from_the_contract(self) -> None:
        self.assertEqual(set(jobs.states()), set(contracts.contract("cb.jobs")["states"]))
        self.assertIn("completed_late", jobs.states())
        self.assertIn("interrupted_requires_retry", jobs.states())

    def test_every_state_has_a_transition_entry(self) -> None:
        table = jobs.transitions()
        self.assertEqual(set(table), set(jobs.states()))
        for state in jobs.terminal_states():
            self.assertEqual(table[state], [], f"terminal state {state} must have no exits")

    def test_happy_path_is_allowed(self) -> None:
        for current, target in (
            ("queued", "running"),
            ("running", "completed"),
            ("running", "cancel_requested"),
            ("cancel_requested", "cancelling"),
            ("cancelling", "cancelled"),
            ("running", "interrupted_requires_retry"),
        ):
            with self.subTest(current=current, target=target):
                self.assertTrue(jobs.can_transition(current, target))

    def test_illegal_moves_are_refused(self) -> None:
        for current, target in (
            ("queued", "completed"),
            ("completed", "running"),
            ("cancelled", "running"),
            ("cancel_requested", "running"),
        ):
            with self.subTest(current=current, target=target):
                self.assertFalse(jobs.can_transition(current, target))

    def test_assert_transition_raises_contract_error(self) -> None:
        with self.assertRaises(api.RpcError) as raised:
            jobs.assert_transition("completed", "running")
        self.assertEqual(raised.exception.error["code"], "JOB_STATE_INVALID")

    def test_cancellation_is_only_offered_where_meaningful(self) -> None:
        self.assertTrue(jobs.cancellable("queued"))
        self.assertTrue(jobs.cancellable("running"))
        self.assertFalse(jobs.cancellable("cancelling"))
        self.assertFalse(jobs.cancellable("completed"))

    def test_job_schema_requires_a_persistent_attempt_id(self) -> None:
        job_schema = jobs.job_schema()
        self.assertIn("attempt_id", job_schema["required"])
        self.assertIn("checkpoint", job_schema["properties"])


class JobCommandTest(unittest.TestCase):
    """The command layer may only offer cancellation where the contract allows it."""

    def test_cancel_targets_are_contract_edges(self) -> None:
        targets = {"queued": "cancelled", "running": "cancel_requested", "interrupted_requires_retry": "cancelled"}
        for state, target in targets.items():
            with self.subTest(state=state):
                self.assertTrue(jobs.can_transition(state, target))
        self.assertTrue(jobs.cancellable("queued"))
        self.assertTrue(jobs.cancellable("running"))

    def test_non_cancellable_states_are_refused_not_guessed(self) -> None:
        for state in ("cancel_requested", "cancelling", "cancelled", "completed", "completed_late", "failed"):
            with self.subTest(state=state):
                self.assertFalse(jobs.cancellable(state))

    def test_domain_refuses_cancel_with_the_contract_code(self) -> None:
        from coursebook import api, domain

        error = api.build_error("JOB_NOT_CANCELLABLE", "job is cancelling and cannot be cancelled.")
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")
        self.assertFalse(error["retryable"])
        self.assertIn("jobs.cancel", domain.KERNEL_METHODS)


if __name__ == "__main__":
    unittest.main()
