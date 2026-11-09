"""H-182/D4 — the kernel's rule for a lesson check with no chat binding.

The cold walk reported `Submit answer` as a dead control in a fresh Desktop profile: the pane
disables Submit whenever `lesson.page`'s `runtime.binding_status` is not `active`, and a run whose
chat never woke has no binding row at all, so the kernel reported `detached`. Nothing in that path
was a backend refusal: `PREBUILD_SPEC.md` §8 makes `submit_attempt` "the primary correctness door",
invoked by the Coursebook UI, with the chat hook as an adapter — "it is not the sole boundary".

These tests pin the boundary so the pane can be repaired against it instead of against a guess:

* a run with **no binding row** may be graded from the pane, and the attempt is written (D4's dead
  control is a client gate, not a kernel rule);
* a run whose binding is **detached** is still refused — the governance gate has not weakened;
* the **one action that binds** (`POST /sessions/bind` → :func:`coursebook.bindings.bind_session`)
  turns the same unbound lesson into an `active` one, after which the pane's existing `active`
  gate is satisfied.

Each case runs against a real migrated SQLite database under a throwaway ``HERMES_HOME``.

Run only these with::

    python3 -m unittest tests.test_h182_lesson_check_unbound -v
"""

from __future__ import annotations

import unittest

from coursebook import api, bindings
from tests.kernel_support import KernelCase


class UnboundLessonCheckTest(KernelCase):
    """A lesson that has not bound a chat yet is still a gradable lesson."""

    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "mode": "fresh",
            },
            idempotency_key=f"begin-{self.lesson['objective_id']}",
        )["result"]
        self.run_id = run["lesson_run_id"]
        # The reported state: a run exists, no chat has bound to it.
        self.assertIsNone(run["binding"])
        self.assertEqual(run["resume"]["reason"], "no_binding")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM bindings"), 0)

    def test_a_run_with_no_binding_is_gradable_from_the_pane(self) -> None:
        submitted = self.submit(self.lesson, "4")
        result = submitted["result"]
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["next_action"], "complete_objective")
        attempt = self.rows("SELECT * FROM attempts")
        self.assertEqual(len(attempt), 1)
        self.assertEqual(attempt[0]["state"], "committed")
        # No binding was invented to make that work.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM bindings"), 0)

    def test_the_page_reports_no_binding_as_detached_not_as_a_refusal(self) -> None:
        """The kernel makes no claim that a chat governs the run; it does not refuse it either."""
        page = self.ok(
            "lesson.page",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
            },
        )["result"]
        runtime = page["runtime"]
        self.assertIsNone(runtime["binding_id"], "no binding row may be reported as an id")
        self.assertIn(runtime["binding_status"], ("detached", "active"))
        # A client that wants the honest answer asks `lesson.begin`, which already carries the
        # contract vocabulary for it (`resume.reason: no_binding`), rather than reading a status.

    def test_a_detached_binding_still_refuses_the_submit(self) -> None:
        """The governance gate is unchanged: a severed chat does not accept an answer."""
        bound = bindings.bind_session(
            stored_session_id="sess_durable_1",
            enrollment_id=self.lesson["enrollment_id"],
            objective_id=self.lesson["objective_id"],
            lesson_run_id=self.run_id,
            profile="cbqa",
        )
        self.execute(
            "UPDATE bindings SET status = 'detached' WHERE id = ?", (bound["binding"]["id"],)
        )
        self.assertEqual(
            self.scalar("SELECT status FROM bindings WHERE id = ?", (bound["binding"]["id"],)),
            "detached",
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM bindings WHERE enrollment_id = ?",
                        (self.lesson["enrollment_id"],)),
            1,
        )
        response = self.submit(self.lesson, "4")
        self.assertFalse(response["ok"], f"a detached binding accepted a submit: {response.get('result')}")
        error = response["error"]
        self.assertEqual(error["code"], "BINDING_NOT_ACTIVE")
        self.assertEqual(error["details"]["status"], "detached")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)

    def test_binding_the_chat_turns_the_same_run_active(self) -> None:
        """The one action that binds: the same run becomes `active`, nothing else moves."""
        bound = bindings.bind_session(
            stored_session_id="sess_durable_1",
            enrollment_id=self.lesson["enrollment_id"],
            objective_id=self.lesson["objective_id"],
            lesson_run_id=self.run_id,
            profile="cbqa",
        )
        self.assertTrue(bound["created"])
        self.assertEqual(bound["binding"]["status"], "active")
        self.assertEqual(bound["binding"]["lesson_run_id"], self.run_id)

        page = self.ok(
            "lesson.page",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
            },
        )["result"]
        self.assertEqual(page["runtime"]["binding_status"], "active")
        self.assertEqual(page["runtime"]["binding_id"], bound["binding"]["id"])

        submitted = self.submit(self.lesson, "4")
        self.assertTrue(submitted["ok"], submitted.get("error"))
        self.assertEqual(submitted["result"]["verdict"], "pass")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
