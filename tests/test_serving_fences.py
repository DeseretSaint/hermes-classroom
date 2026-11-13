"""E2E L2/L8: the revision fence a check moves, and the binding gate's scope.

Two serving fences from ``docs/UX-AUDIT-E2E.md`` that each refused a learner's honest action:

* **L2 — the check's own revision.** ``check.open`` bumps the enrollment when it creates the
  check and returns the new revision. A surface that fences the next ``attempt.submit`` on the
  page read it already held sends the old number and is refused ``STALE_REVISION`` for a move the
  backend made itself. This suite pins the command contract: the returned revision is the one the
  submit must carry, and the older one is refused.
* **L8 — binding scope.** A binding belongs to the objective its lesson run teaches. The gate used
  to read every binding in the enrollment, so a chat left detached on section 1 refused a submit on
  section 2, which had no chat to answer to at all. These cases pin the three outcomes: no binding
  for this objective allows, a detached one on this objective refuses, and an active one allows.

The desktop half of L2/L3 lives in ``tests/test_desktop_serving_fences.py``; this module is the
backend behaviour against a real migrated SQLite database.
"""

from __future__ import annotations

import unittest

from coursebook import bindings, db
from tests.kernel_support import KernelCase


class CheckRevisionFenceCase(KernelCase):
    def test_check_open_returns_the_revision_the_next_submit_must_carry(self) -> None:
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        approved = self.approve(enrollment_id, plan_id, 0)

        # The read that opened the section holds `approved`; the check's creation moves the
        # enrollment, and the command reports where it moved to.
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=approved,
        )["result"]
        self.assertEqual(opened["revision"], approved + 1)

        lesson = {
            "enrollment_id": enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }
        # The stale fence is the defect's shape, not a valid submit...
        stale = self.submit(lesson, "4", revision=approved)
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["error"]["code"], "STALE_REVISION")
        self.assertEqual(stale["error"]["current_revision"], approved + 1)
        # ...and the revision `check.open` returned is exactly what makes it commit.
        graded = self.ok(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": "nonce-l2-first",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=opened["revision"],
            idempotency_key="l2-first-submit",
        )["result"]
        self.assertEqual(graded["verdict"], "pass")
        self.assertEqual(graded["revision"], opened["revision"] + 1)

    def test_an_open_check_read_reports_the_enrollment_revision(self) -> None:
        """A re-open of a check that already exists is a read: it returns where the enrollment is.

        The surface may call `check.open` again after adopting the first answer's revision; the
        second call must not bump anything and must report the same fence.
        """
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        again = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=opened["revision"],
        )["result"]
        self.assertEqual(again["check_id"], opened["check_id"])
        self.assertEqual(again["revision"], opened["revision"])


class BindingScopeCase(KernelCase):
    """L8: a binding answers only for the objective it teaches."""

    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        # Both objectives are authored while the plan is still a draft; approval freezes it.
        self.objective_a = self.seed_objective(self.plan_id)
        self.objective_b = self.seed_objective(self.plan_id)
        self.enrollment_id = self.new_enrollment(self.course_id)
        self.revision = self.approve(self.enrollment_id, self.plan_id, 0)
        self.check_a = self.ok(
            "check.open",
            {"enrollment_id": self.enrollment_id, "objective_id": self.objective_a},
            expected_revision=self.revision,
        )["result"]
        self.revision = self.check_a["revision"]
        self.check_b = self.ok(
            "check.open",
            {"enrollment_id": self.enrollment_id, "objective_id": self.objective_b},
            expected_revision=self.revision,
        )["result"]
        self.revision = self.check_b["revision"]

    def _lesson(self, opened: dict) -> dict:
        return {
            "enrollment_id": self.enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": self.revision,
        }

    def _begin(self, objective_id: str) -> str:
        return self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.enrollment_id,
                "objective_id": objective_id,
                "mode": "fresh",
            },
            idempotency_key=f"begin-{objective_id}",
        )["result"]["lesson_run_id"]

    def _bind(self, objective_id: str, run_id: str, stored: str) -> dict:
        return bindings.bind_session(
            stored_session_id=stored,
            enrollment_id=self.enrollment_id,
            objective_id=objective_id,
            lesson_run_id=run_id,
            profile="cbqa",
        )["binding"]

    def _abandon(self, binding: dict) -> None:
        self.ok(
            "binding.abandon",
            {"binding_id": binding["id"]},
            expected_revision=int(binding["revision"]),
            idempotency_key=f"abandon-{binding['id']}",
        )

    def test_no_binding_for_this_objective_allows_the_submit(self) -> None:
        """A detached chat left on objective A must not refuse objective B's answer."""
        run_a = self._begin(self.objective_a)
        self._abandon(self._bind(self.objective_a, run_a, "sess_a"))
        rows = self.rows("SELECT status, objective_id FROM bindings")
        self.assertEqual([(row["status"], row["objective_id"]) for row in rows], [("orphaned", self.objective_a)])

        # No binding names objective B: the write has no chat to answer to, so it commits.
        graded = self.ok(
            "attempt.submit",
            {
                "enrollment_id": self.enrollment_id,
                "check_id": self.check_b["check_id"],
                "check_version": self.check_b["check_version"],
                "attempt_nonce": "nonce-l8-b",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=self.revision,
            idempotency_key="l8-submit-b",
        )["result"]
        self.assertEqual(graded["verdict"], "pass")

    def test_a_detached_binding_on_this_objective_refuses(self) -> None:
        """The refusal still fires where it is true: the objective's own chat was detached."""
        run_b = self._begin(self.objective_b)
        self._abandon(self._bind(self.objective_b, run_b, "sess_b"))
        error = self.err(
            "attempt.submit",
            {
                "enrollment_id": self.enrollment_id,
                "check_id": self.check_b["check_id"],
                "check_version": self.check_b["check_version"],
                "attempt_nonce": "nonce-l8-b-refused",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=self.revision,
            idempotency_key="l8-submit-b-refused",
        )
        self.assertEqual(error["code"], "BINDING_NOT_ACTIVE")
        self.assertEqual(error["details"]["objective_id"], self.objective_b)

    def test_an_active_binding_on_this_objective_allows_the_submit(self) -> None:
        run_b = self._begin(self.objective_b)
        self._bind(self.objective_b, run_b, "sess_b")
        graded = self.ok(
            "attempt.submit",
            {
                "enrollment_id": self.enrollment_id,
                "check_id": self.check_b["check_id"],
                "check_version": self.check_b["check_version"],
                "attempt_nonce": "nonce-l8-b-active",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=self.revision,
            idempotency_key="l8-submit-b-active",
        )["result"]
        self.assertEqual(graded["verdict"], "pass")

    def test_a_live_binding_on_another_objective_does_not_cover_this_one(self) -> None:
        """An active chat on A is not a chat for B: B still commits, A is untouched."""
        run_a = self._begin(self.objective_a)
        self._bind(self.objective_a, run_a, "sess_a")
        graded = self.ok(
            "attempt.submit",
            {
                "enrollment_id": self.enrollment_id,
                "check_id": self.check_b["check_id"],
                "check_version": self.check_b["check_version"],
                "attempt_nonce": "nonce-l8-b-cross",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=self.revision,
            idempotency_key="l8-submit-b-cross",
        )["result"]
        self.assertEqual(graded["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
