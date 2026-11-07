"""H-34: a verification checklist is confirmed by selecting its declared item ids.

Frozen decision: ``docs/CHECKLIST-CONFIRMATION.md`` §4/§7/§8. A submission takes the confirmation
lane iff the stored reference is ``rubric_only``, the stimulus is ``format: "verification"`` with a
non-empty ``{id, label}`` item list, the answer is ``kind: "selection"`` and the enrollment's
course recipe is not ``parent``. Every ticked item is a ``pass`` with
``evidence_class = "self_reported"``; a subset is ``partial``; an empty selection or an undeclared id
is ``VALIDATION_FAILED`` before any row is written.

These cases run the real command path (``check.open`` -> ``attempt.submit``) against a real
migrated database, through the one-off verification fixture. No provider is called.
"""

from __future__ import annotations

import json
import unittest

from coursebook import domain, grading

from tests.kernel_support import KernelCase
from tests.test_grading_lanes import GradingLaneCase


class ChecklistConfirmationCase(GradingLaneCase):
    """The H-20 lane fixture, plus selection submissions and refusal assertions."""

    def authored(self) -> dict:
        return self.author(
            plan_name="plan_one_off", recipe="one_off", lesson_name="lesson_one_off"
        )

    def declared_items(self, opened: dict) -> list[dict]:
        stimulus = json.loads(str(self.scalar(
            "SELECT stimulus_json FROM checks WHERE id = ?", (opened["check_id"],)
        )))
        return stimulus["items"]

    def revision_of(self, enrollment_id: str) -> int:
        return int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)))

    def attempt_rows(self, check_id: str) -> list[dict]:
        return self.rows("SELECT * FROM attempts WHERE check_id = ? ORDER BY rowid", (check_id,))

    def layer2_rows(self, enrollment_id: str) -> int:
        return int(self.scalar(
            "SELECT COUNT(*) FROM evidence WHERE enrollment_id = ? AND layer = 2",
            (enrollment_id,),
        ))

    def submit_selection(self, opened: dict, selection: list[str], *, key: str = "key-confirm") -> dict:
        return self.dispatch(
            "attempt.submit",
            {
                "enrollment_id": opened["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": f"nonce-{key}",
                "answer": {"kind": "selection", "selection": selection},
            },
            expected_revision=opened["revision"],
            idempotency_key=key,
        )

    def confirm(self, opened: dict, selection: list[str], *, key: str = "key-confirm") -> dict:
        response = self.submit_selection(opened, selection, key=key)
        self.assertTrue(response["ok"], response.get("error"))
        return response["result"]

    def inspect(self, opened: dict) -> dict:
        return self.ok(
            "evidence.inspect",
            {"enrollment_id": opened["enrollment_id"], "objective_id": opened["objective_id"]},
        )["result"]


class FullConfirmationTest(ChecklistConfirmationCase):
    """§8.1, §8.2 — every item ticked closes the check as self-reported."""

    def test_every_item_ticked_passes_as_self_reported(self) -> None:
        opened = self.open_generated(self.authored())
        items = self.declared_items(opened)
        ids = [item["id"] for item in items]
        result = self.confirm(opened, ids)

        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "self_reported")
        self.assertEqual(result["next_action"], "review_objective")
        self.assertEqual(result["revision"], opened["revision"] + 1)

        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "closed"
        )
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (opened["objective_id"],)),
            "introduced",
        )
        self.assertEqual(self.layer2_rows(opened["enrollment_id"]), 0)

        criteria = result["criteria"]
        self.assertEqual([entry["id"] for entry in criteria], ids)
        self.assertEqual([entry["observed"] for entry in criteria],
                         [item["label"] for item in items])
        self.assertTrue(all(entry["met"] is True for entry in criteria))

        # The stored reference is never upgraded to a closed kind (§5/§7).
        reference = self.stored_reference(opened["check_id"])
        self.assertEqual(reference["kind"], "rubric_only")
        self.assertNotIn(reference["kind"], ("exact", "numeric", "selection"))

    def test_answer_is_persisted_verbatim_and_inspectable(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        selection = [ids[2], ids[0], ids[1]]
        result = self.confirm(opened, selection)

        rows = self.attempt_rows(opened["check_id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["answer_kind"], "selection")
        self.assertEqual(json.loads(str(rows[0]["answer_json"])),
                         {"kind": "selection", "selection": selection})
        self.assertEqual(rows[0]["evidence_class"], "self_reported")
        self.assertEqual(rows[0]["verdict"], "pass")
        self.assertEqual(json.loads(str(rows[0]["grading_provenance_json"])), {
            "grader": "provider-free:confirmation",
            "reference_sha256": grading.reference_hash(self.stored_reference(opened["check_id"])),
            "declared_items": len(ids),
            "confirmed_items": len(ids),
        })

        bundle = self.inspect(opened)
        self.assertEqual(bundle["l1"]["attempts"][0]["evidence_class"], "self_reported")
        self.assertTrue(any(
            event["evidence_class"] == "self_reported" and event["kind"] == "attempt"
            for event in bundle["l1"]["events"]
        ))

    def test_duplicate_ids_collapse_to_one_confirmation(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        result = self.confirm(opened, [ids[0], ids[0], ids[1], ids[2]])
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(json.loads(str(self.attempt_rows(opened["check_id"])[0]["answer_json"])),
                         {"kind": "selection", "selection": [ids[0], ids[0], ids[1], ids[2]]})


class PartialConfirmationTest(ChecklistConfirmationCase):
    """§8.3 — a subset advances nothing but records which steps were confirmed."""

    def test_one_of_three_is_partial_and_keeps_the_check_open(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        result = self.confirm(opened, [ids[0]])

        self.assertEqual(result["verdict"], "partial")
        self.assertEqual(result["evidence_class"], "self_reported")
        self.assertEqual(result["next_action"], "retry_attempt")
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (opened["objective_id"],)),
            "needs_review",
        )
        self.assertEqual(self.layer2_rows(opened["enrollment_id"]), 0)
        self.assertEqual([entry["met"] for entry in result["criteria"]], [True, False, False])

    def test_two_of_three_is_still_partial(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        result = self.confirm(opened, [ids[0], ids[2]])
        self.assertEqual(result["verdict"], "partial")
        self.assertEqual([entry["met"] for entry in result["criteria"]], [True, False, True])


class RefusalTest(ChecklistConfirmationCase):
    """§8.4, §8.5 — refusals happen before the write transaction."""

    def assert_refused(self, opened: dict, selection: list[str], reason: str) -> None:
        before = self.revision_of(opened["enrollment_id"])
        error = self.err(
            "attempt.submit",
            {
                "enrollment_id": opened["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": f"nonce-refused-{reason}",
                "answer": {"kind": "selection", "selection": selection},
            },
            expected_revision=opened["revision"],
            idempotency_key=f"key-refused-{reason}",
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], reason)
        self.assertEqual(error["details"]["field"], "answer")
        self.assertEqual(self.attempt_rows(opened["check_id"]), [])
        self.assertEqual(self.revision_of(opened["enrollment_id"]), before)
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )

    def test_unknown_item_is_refused(self) -> None:
        opened = self.open_generated(self.authored())
        self.assert_refused(opened, ["item_9"], "unknown_check_item")

    def test_a_declared_and_an_unknown_id_is_refused(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        self.assert_refused(opened, [ids[0], "item_9"], "unknown_check_item")

    def test_empty_selection_is_refused(self) -> None:
        opened = self.open_generated(self.authored())
        self.assert_refused(opened, [], "checklist_no_items_confirmed")


class UnchangedPathsTest(ChecklistConfirmationCase):
    """§8.6, §8.8 — text answers and pack open responses are untouched."""

    def test_a_text_answer_on_a_checklist_stays_needs_retry(self) -> None:
        opened = self.open_generated(self.authored())
        result = self.submit_answer(opened, {"kind": "text", "text": "all done"})
        self.assertEqual(result["verdict"], "needs_retry")
        self.assertEqual(result["next_action"], "retry_grading")
        self.assertEqual(result["revision"], int(opened["revision"]))
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )

    def test_a_pack_production_selection_cannot_be_ticked_into_a_pass(self) -> None:
        """``rubric_only`` with no stimulus format/items is the open lane, never confirmation."""
        spec = {
            "audit_state": "passed",
            "stimulus": {"prompt": "Write a short procedure for seating the pad."},
            "reference": {"kind": "rubric_only"},
            "rubric": {
                "construct": "production",
                "pass_rule": "all",
                "criteria": [{"id": "c1", "description": "Procedure is workable"}],
            },
        }
        opened = self.prepare_lesson(spec)
        before = self.revision_of(opened["enrollment_id"])
        result = self.confirm(opened, ["item_1"], key="key-pack-open")
        self.assertEqual(result["verdict"], "needs_retry")
        self.assertEqual(result["next_action"], "retry_grading")
        self.assertEqual(result["revision"], before)
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )
        self.assertIn(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (opened["objective_id"],)),
            ("not_started", "introduced"),
        )
        self.assertEqual(self.layer2_rows(opened["enrollment_id"]), 0)


class HintThenConfirmationTest(ChecklistConfirmationCase):
    """§8.7 — a prior hint never erases the self-reported label or makes the objective independent."""

    def test_hint_then_full_confirmation_stays_self_reported(self) -> None:
        opened = self.open_generated(self.authored())
        ids = [item["id"] for item in self.declared_items(opened)]
        self.ok(
            "lesson.assist",
            {
                "enrollment_id": opened["enrollment_id"],
                "objective_id": opened["objective_id"],
                "kind": "hint_request",
            },
            expected_revision=opened["revision"],
            idempotency_key="key-hint-1",
        )
        opened["revision"] = self.revision_of(opened["enrollment_id"])
        result = self.confirm(opened, ids, key="key-after-hint")

        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "self_reported")
        self.assertEqual(result["next_action"], "review_objective")
        self.assertNotEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (opened["objective_id"],)),
            "independent_evidence",
        )
        self.assertEqual(self.layer2_rows(opened["enrollment_id"]), 0)
        bundle = self.inspect(opened)
        hints = [event for event in bundle["l1"]["events"] if event["kind"] == "hint_request"]
        self.assertEqual(len(hints), 1, bundle["l1"]["events"])
        self.assertEqual(hints[0]["evidence_class"], "hinted")


class ParentRecipeIsExcludedTest(KernelCase):
    """§8.10 — a parent course records observations, never a child-operated checklist."""

    def test_a_parent_enrollment_does_not_take_the_confirmation_lane(self) -> None:
        course_id, plan_id = self.new_course(recipe="parent")
        spec = {
            "audit_state": "passed",
            "stimulus": {
                "prompt": "Tick each step you watched your child do.",
                "format": "verification",
                "items": [
                    {"id": "item_1", "label": "Sorted the shapes"},
                    {"id": "item_2", "label": "Named each shape"},
                ],
            },
            "reference": {"kind": "rubric_only"},
            "rubric": {
                "construct": "procedure",
                "pass_rule": "all",
                "criteria": [{"id": "c1", "description": "Observed"}],
            },
        }
        objective_id = self.seed_objective(plan_id, spec)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        opened["enrollment_id"] = enrollment_id
        opened["objective_id"] = objective_id

        response = self.dispatch(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": "nonce-parent-selection",
                "answer": {"kind": "selection", "selection": ["item_1", "item_2"]},
            },
            expected_revision=opened["revision"],
            idempotency_key="key-parent-selection",
        )
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        # No confirmation pass: the open lane is unconfigured, so grading fails closed.
        self.assertEqual(result["verdict"], "needs_retry")
        self.assertNotEqual(result["verdict"], "pass")
        self.assertEqual(
            self.scalar("SELECT state FROM checks WHERE id = ?", (opened["check_id"],)), "open"
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM evidence WHERE enrollment_id = ? AND layer = 2",
                        (enrollment_id,)),
            0,
        )

        # The observation path remains the parent's write path: layer 1 only, no attempt row.
        attempts_before = self.scalar(
            "SELECT COUNT(*) FROM attempts WHERE enrollment_id = ?", (enrollment_id,)
        )
        evidence_id = domain.record_observation(
            enrollment_id, objective_id, evidence_class="parent_reported",
            note="Watched both steps.",
        )
        self.assertTrue(evidence_id.startswith("evd_"))
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM attempts WHERE enrollment_id = ?", (enrollment_id,)),
            attempts_before,
        )
        row = self.rows("SELECT * FROM evidence WHERE id = ?", (evidence_id,))[0]
        self.assertEqual(row["layer"], 1)
        self.assertEqual(row["evidence_class"], "parent_reported")


if __name__ == "__main__":
    unittest.main()
