"""CB-022 proof: the frozen cb.rpc v3 shapes against the real learning-loop backend.

`tests/test_contracts.py` proves the contract set is coherent; it cannot prove the contract matches
`coursebook/review.py` and `coursebook/evidence.py`, because those land on Cinder's branch. This
module closes that gap: it drives the real commands against a real SQLite database built by the real
migrations and validates the real backend outputs against the frozen v3 response schemas.

Run it in a worktree that contains the CB-008 backend:

    python3 -m unittest scripts.proof_contract_v3 -v

Without that kernel the module skips with an explicit reason instead of pretending to pass. It is a
proof, not a gate: `tests/test_contracts.py` is the gate that must pass everywhere.
"""

from __future__ import annotations

# This module is branch-dependent by design: it imports the CB-008 learning-loop backend that lands
# on Cinder's branch, so static analysis on a branch without it reports unresolved imports.
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false, reportGeneralTypeIssues=false

import unittest
from datetime import datetime, timedelta, timezone

from coursebook import contracts

try:  # The learning-loop backend and its fixtures live on Cinder's branch.
    from coursebook import db, evidence, review
    from tests.kernel_support import KernelCase, numeric_spec

    _KERNEL_AVAILABLE = True
    _KERNEL_WHY = ""
except ImportError as exc:  # pragma: no cover - depends on the branch being checked out
    _KERNEL_AVAILABLE = False
    _KERNEL_WHY = (
        "needs the CB-008 kernel (coursebook/review.py, coursebook/evidence.py, "
        f"tests/kernel_support.py): {exc}"
    )

    class KernelCase(unittest.TestCase):  # type: ignore[no-redef]
        """Placeholder so the module imports (and skips honestly) where the kernel is absent."""


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


@unittest.skipUnless(_KERNEL_AVAILABLE, _KERNEL_WHY)
class V3BackendProof(KernelCase):
    def lesson(self) -> dict:
        return self.prepare_lesson(numeric_spec("42.7"))

    def backdate(self, objective_id: str, days: float = 10) -> None:
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 2",
            (_iso(days), objective_id),
        )

    def pass_once(self, lesson: dict, answer: str = "42.7") -> dict:
        revision = int(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=revision,
        )["result"]
        response = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            answer,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def test_contract_set_still_audits_clean_on_the_backend_branch(self) -> None:
        self.assertEqual(contracts.audit_contracts(), [])
        # This proof is version-agnostic: it holds the four v3 methods to their frozen shapes
        # whatever the current wire version is (v4 added pack reads on top of them).
        self.assertGreaterEqual(contracts.WIRE_CONTRACT_VERSION, 3)
        self.assertEqual(contracts.contract_version("cb.rpc"), contracts.WIRE_CONTRACT_VERSION)
        self.assertEqual(contracts.contract_version("cb.db"), 2)

    def test_review_queue_output_is_contract_legal_as_returned(self) -> None:
        lesson = self.lesson()
        self.pass_once(lesson)
        self.backdate(lesson["objective_id"])
        with db.read() as connection:
            result = review.queue(connection, lesson["enrollment_id"])
        contracts.validate_response_payload("review.queue", result)
        self.assertEqual(result["total_due"], 1)
        self.assertEqual(result["total_overdue"], 1)
        self.assertEqual(result["items"][0]["objective_id"], lesson["objective_id"])

        # The cap bounds rows, never the counts.
        with db.read() as connection:
            capped = review.queue(connection, lesson["enrollment_id"], cap=1)
        contracts.validate_response_payload("review.queue", capped)
        contracts.validate_request_payload(
            "review.queue",
            {"enrollment_id": lesson["enrollment_id"], "cap": 5, "include_upcoming": False},
        )

    def test_review_action_mapping_validates_for_every_action(self) -> None:
        lesson = self.lesson()
        self.pass_once(lesson)
        self.backdate(lesson["objective_id"])
        enrollment_id = lesson["enrollment_id"]
        objective_id = lesson["objective_id"]

        def mapped(connection, action: str) -> dict:
            outcome = review.apply_action(
                connection, enrollment_id=enrollment_id, objective_id=objective_id, action=action
            )
            state = connection.execute(
                "SELECT state FROM objectives WHERE id = ?", (objective_id,)
            ).fetchone()["state"]
            return {**outcome, "state": state}

        with db.transaction() as connection:
            snoozed = mapped(connection, "snooze")
        with db.read() as connection:
            queue = review.queue(connection, enrollment_id)
        due_at = next(
            (item["due_at"] for item in queue["items"] if item["objective_id"] == objective_id), None
        )
        contracts.validate_response_payload("review.action", {**snoozed, "due_at": due_at})
        self.assertIsNotNone(due_at)

        with db.transaction() as connection:
            stretched = mapped(connection, "stretch")
            dropped = mapped(connection, "drop")
        contracts.validate_response_payload("review.action", {**stretched, "due_at": None})
        contracts.validate_response_payload("review.action", {**dropped, "due_at": None})
        self.assertEqual(dropped["state"], "independent_evidence")

        with db.transaction() as connection:
            resumed = mapped(connection, "resume")
        contracts.validate_response_payload("review.action", {**resumed, "due_at": None})
        self.assertEqual(resumed["state"], "review_due")

        # The envelope carries the revision; the payload must not carry a second copy.
        self.assertNotIn("revision", snoozed)

    def test_evidence_bundle_maps_to_inspect_with_one_documented_delta(self) -> None:
        lesson = self.lesson()
        self.pass_once(lesson)
        enrollment_id = lesson["enrollment_id"]
        with db.read() as connection:
            bundle = evidence.bundle(connection, enrollment_id)

        # The raw bundle is already four-layer shaped; only the dispute view lacks the paging
        # fields the contract requires, which is exactly what the handler adds.
        self.assertEqual(set(bundle), {"l1", "l2", "l3", "disputes"})
        self.assertEqual(set(bundle["disputes"]), {"enrollment_id", "disputes", "count"})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_response_payload("evidence.inspect", bundle)

        count = bundle["disputes"]["count"]
        mapped = {
            **bundle,
            "disputes": {**bundle["disputes"], "count": count, "truncated": count > 50},
        }
        contracts.validate_response_payload("evidence.inspect", mapped)
        self.assertFalse(mapped["l3"]["is_persona"])
        self.assertTrue(mapped["l2"]["objectives"][0]["independent"])
        self.assertEqual(len(mapped["l1"]["attempts"]), 1)
        self.assertEqual(mapped["l1"]["attempts"][0]["evidence_class"], "cold")

        with db.read() as connection:
            focused = evidence.bundle(connection, enrollment_id, objective_id=lesson["objective_id"])
        contracts.validate_response_payload(
            "evidence.inspect",
            {**focused, "disputes": {**focused["disputes"], "truncated": False}},
        )

    def test_evidence_disputes_view_validates_after_a_real_dispute(self) -> None:
        lesson = self.lesson()
        submitted = self.pass_once(lesson, answer="41.9")
        attempt_id = submitted["attempt_id"]
        self.ok("attempt.dispute", {"attempt_id": attempt_id, "note": "Rounding differs from the rubric."})
        enrollment_id = lesson["enrollment_id"]
        with db.read() as connection:
            raw = evidence.disputes(connection, enrollment_id)
        self.assertEqual(raw["count"], 1)
        self.assertEqual(
            set(raw["disputes"][0]),
            {
                "dispute_id", "attempt_id", "check_id", "verdict", "evidence_class", "state",
                "note", "created_at",
            },
        )
        contracts.validate_response_payload(
            "evidence.disputes", {**raw, "truncated": raw["count"] > 50}
        )
        self.assertEqual(raw["disputes"][0]["attempt_id"], attempt_id)
        self.assertEqual(raw["disputes"][0]["state"], "open")

        with db.read() as connection:
            filtered = evidence.disputes(connection, enrollment_id, attempt_id=attempt_id)
        contracts.validate_response_payload(
            "evidence.disputes", {**filtered, "truncated": filtered["count"] > 50}
        )
        with db.read() as connection:
            empty = evidence.disputes(connection, enrollment_id, attempt_id="att_00000000")
        contracts.validate_response_payload(
            "evidence.disputes", {**empty, "truncated": empty["count"] > 50}
        )
        self.assertEqual(empty["count"], 0)


if __name__ == "__main__":
    unittest.main()
