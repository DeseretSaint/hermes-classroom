"""H-12: plan approval is fail-closed and its provenance is explicit.

Every case drives the real ``coursebook.api.dispatch`` path against a real migrated SQLite
database. Generated plans come from the real offline generation pipeline (``run_plan_job`` with
the deterministic fake provider from ``tests.test_generation``) — no hand-written generation row
pretends to be a validation pass.

The rule these cases pin:

* an empty plan never approves;
* a generated plan approves only when the latest generation record is the pass state *and* carries
  a durable snapshot of the exact kernel content hash being approved;
* a rejected, unvalidated, or edited plan refuses with a typed error and writes no transition,
  no revision bump and no approval timestamp;
* a manually authored non-empty plan approves and never claims a validation pass.
"""

from __future__ import annotations

import dataclasses
import json
import unittest

from coursebook import db, domain, generation

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)


class PlanApprovalIntegrityTest(KernelCase):
    # ── generation helpers (real pipeline, deterministic provider) ──────────
    def run_plan(self, course_id: str, *, reject: bool = False, rule_break: bool = False) -> dict:
        job = plan_job(job_id=f"job-plan-{course_id}")
        job["brief"]["course_id"] = course_id
        if rule_break:
            # A quiz plan for the one-off recipe breaks a deterministic rule twice: the validator is
            # never called, so the stored record has no validation at all.
            job["brief"]["recipe"] = "one_off"
            job["brief"]["dials"] = {}
            job["brief"]["locale"] = None
            script = {"coursebook.plan.generate": plan_from_fixture("plan_ja")}
        else:
            script = {
                "coursebook.plan.generate": plan_from_fixture("plan_ja"),
                "coursebook.plan.validate": validation_from_fixture(
                    "validation_reject_hazard" if reject else "validation_pass"
                ),
            }
        connection = db.connect()
        try:
            return generation.run_plan_job(
                connection, job, FakeLLM(script), FakeSearch(), now=NOW
            )
        finally:
            connection.close()

    def approve(self, enrollment_id: str, plan_id: str, revision: int, *, key: str | None = None):
        return self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": domain.plan_hash(plan_id),
            },
            expected_revision=revision,
            idempotency_key=key,
        )["result"]

    def refuse(self, enrollment_id: str, plan_id: str, revision: int) -> dict:
        return self.err(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": domain.plan_hash(plan_id),
            },
            expected_revision=revision,
        )

    def assert_refused_without_side_effects(
        self, error: dict, *, reason: str, plan_id: str, enrollment_id: str
    ) -> None:
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], reason)
        plan = self.rows("SELECT * FROM plans WHERE id = ?", (plan_id,))[0]
        self.assertEqual(plan["state"], "draft")
        self.assertIsNone(plan["approved_at"])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM transitions WHERE enrollment_id = ?", (enrollment_id,))),
            0,
        )
        self.assertEqual(
            int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,))), 0
        )

    # ── empty plan ──────────────────────────────────────────────────────────
    def test_empty_plan_is_refused_and_changes_nothing(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        version_before = int(self.scalar("SELECT version FROM plans WHERE id = ?", (plan_id,)))

        error = self.refuse(enrollment_id, plan_id, 0)

        self.assert_refused_without_side_effects(
            error, reason="plan_empty", plan_id=plan_id, enrollment_id=enrollment_id
        )
        self.assertEqual(
            int(self.scalar("SELECT version FROM plans WHERE id = ?", (plan_id,))), version_before
        )

    # ── generated plans ─────────────────────────────────────────────────────
    def test_rejected_generated_plan_is_refused(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id, reject=True)
        self.assertEqual(generated["status"], "needs_review")
        self.assertEqual(generated["validation_verdict"], "reject")
        enrollment_id = self.new_enrollment(course_id)

        error = self.refuse(enrollment_id, generated["plan_id"], 0)

        self.assert_refused_without_side_effects(
            error, reason="plan_not_validated", plan_id=generated["plan_id"],
            enrollment_id=enrollment_id,
        )

    def test_generated_plan_without_a_validation_record_is_refused(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id, rule_break=True)
        self.assertEqual(generated["status"], "needs_review")
        self.assertIsNone(generated["validation_id"])
        enrollment_id = self.new_enrollment(course_id)

        error = self.refuse(enrollment_id, generated["plan_id"], 0)

        self.assert_refused_without_side_effects(
            error, reason="plan_not_validated", plan_id=generated["plan_id"],
            enrollment_id=enrollment_id,
        )

    def test_legacy_generated_plan_without_a_content_binding_is_refused(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id)
        self.assertEqual(generated["validation_verdict"], "pass")
        enrollment_id = self.new_enrollment(course_id)

        # Simulate a pre-H-12 row: a pass with no durable binding to this content hash.
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT id, result_json FROM gen_plan_documents WHERE plan_id = ?",
                (generated["plan_id"],),
            ).fetchone()
            result = json.loads(row["result_json"])
            result.pop("plan_content_hash", None)
            connection.execute(
                "UPDATE gen_plan_documents SET result_json = ? WHERE id = ?",
                (json.dumps(result), row["id"]),
            )

        error = self.refuse(enrollment_id, generated["plan_id"], 0)

        self.assert_refused_without_side_effects(
            error, reason="plan_not_validated", plan_id=generated["plan_id"],
            enrollment_id=enrollment_id,
        )

    def test_validated_generated_plan_approves(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id)
        self.assertEqual(generated["status"], "draft")
        self.assertEqual(generated["validation_verdict"], "pass")
        self.assertTrue(generated["plan_content_hash"].startswith("sha256:"))
        enrollment_id = self.new_enrollment(course_id)

        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": generated["plan_id"],
                "plan_hash": domain.plan_hash(generated["plan_id"]),
            },
            expected_revision=0,
        )

        self.assertEqual(approved["result"]["revision"], 1)
        plan = self.rows("SELECT * FROM plans WHERE id = ?", (generated["plan_id"],))[0]
        self.assertEqual(plan["state"], "approved")
        self.assertIsNotNone(plan["approved_at"])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM transitions WHERE enrollment_id = ?", (enrollment_id,))),
            1,
        )

    def test_model_assessed_pass_is_approvable_by_a_human_with_its_warning(self) -> None:
        """H-15 union: `needs_review` is the human review, not a refusal to ever approve.

        A pass from the author's own model is a model assessment. It is never called independent
        validation, but plan approval is the parent's decision (PREBUILD_SPEC §5), so it may be
        approved with the warning attached rather than being blocked forever.
        """
        course_id, _first_plan = self.new_course()
        job = plan_job(job_id=f"job-plan-{course_id}")
        job["brief"]["course_id"] = course_id
        independent = validation_from_fixture("validation_pass")

        def same_model(request: generation.LLMRequest) -> generation.LLMResponse:
            return dataclasses.replace(independent(request), model="fake-model")

        script = {
            "coursebook.plan.generate": plan_from_fixture("plan_ja"),
            "coursebook.plan.validate": same_model,
        }
        connection = db.connect()
        try:
            generated = generation.run_plan_job(
                connection, job, FakeLLM(script), FakeSearch(), now=NOW
            )
        finally:
            connection.close()

        self.assertEqual(generated["status"], "needs_review")
        self.assertEqual(generated["validation"]["outcome"], "model_assessed")
        self.assertFalse(generated["validation"]["independent"])
        self.assertTrue(generated["approval_provenance"]["needs_review"])
        self.assertTrue(generated["approval_provenance"]["warning"])

        enrollment_id = self.new_enrollment(course_id)
        approved = self.approve(enrollment_id, generated["plan_id"], 0)

        self.assertEqual(approved["revision"], 1)
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (generated["plan_id"],)), "approved"
        )

    # ── manually authored plan ──────────────────────────────────────────────
    def test_manual_nonempty_plan_approves_without_claiming_validation(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        edited = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "add_objectives": [
                    {"title": "Braise short ribs", "evidence_target": "procedure", "criteria": []}
                ],
            },
            expected_revision=0,
            idempotency_key="key-manual-author-1",
        )["result"]
        self.assertFalse(
            self._table_exists("gen_plan_documents"),
            "a purely manual course has no generation record to claim a pass from",
        )

        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": edited["plan_hash"],
            },
            expected_revision=edited["revision"],
        )

        self.assertEqual(approved["result"]["revision"], edited["revision"] + 1)
        # The wire response is frozen and carries no validation claim; the database agrees.
        self.assertEqual(set(approved["result"]), {"plan_hash", "revision"})
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (plan_id,)), "approved"
        )
        self.assertFalse(self._table_exists("gen_plan_documents"))

    # ── invalidation ────────────────────────────────────────────────────────
    def test_edit_invalidates_the_generated_pass_and_old_hash_still_refuses(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id)
        plan_id = generated["plan_id"]
        enrollment_id = self.new_enrollment(course_id)
        old_hash = domain.plan_hash(plan_id)
        objective_id = self.scalar(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal LIMIT 1", (plan_id,)
        )

        edited = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": old_hash,
                "objective_edits": [{"objective_id": objective_id, "title": "Edited opening"}],
            },
            expected_revision=0,
            idempotency_key="key-edit-generated-1",
        )["result"]
        self.assertNotEqual(edited["plan_hash"], old_hash)

        # The pre-edit pass cannot approve the edited content, even with the new revision.
        stale = self.err(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": old_hash},
            expected_revision=edited["revision"],
        )
        self.assertEqual(stale["code"], "VALIDATION_FAILED")
        self.assertEqual(stale["details"]["field"], "plan_hash")
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM transitions WHERE enrollment_id = ?", (enrollment_id,))),
            0,
        )
        record = self.rows("SELECT * FROM gen_plan_documents WHERE plan_id = ?", (plan_id,))[0]
        stored = json.loads(record["result_json"])
        self.assertEqual(record["generation_state"], "needs_review")
        self.assertIsNone(record["validation_id"])
        self.assertEqual(stored["validation_verdict"], "not_validated")
        self.assertTrue(stored["manual_authoring"])
        self.assertNotIn("plan_content_hash", stored)

        # The edit is the explicit manual decision: the authored plan may now approve, as manual.
        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": edited["plan_hash"],
            },
            expected_revision=edited["revision"],
        )
        self.assertEqual(approved["result"]["revision"], edited["revision"] + 1)

    def test_replan_does_not_carry_validation_and_the_new_version_refuses(self) -> None:
        course_id, _first_plan = self.new_course()
        generated = self.run_plan(course_id)
        plan_id = generated["plan_id"]
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)["revision"]

        objectives = self.rows(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan_id,)
        )
        replanned = self.ok(
            "plan.replan",
            {
                "enrollment_id": enrollment_id,
                "objective_changes": [
                    {"objective_id": row["id"], "change": "keep"} for row in objectives
                ],
            },
            expected_revision=revision,
        )["result"]
        new_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft'"
                " ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        self.assertNotEqual(new_plan_id, plan_id)

        carried = self.rows(
            "SELECT * FROM gen_plan_documents WHERE plan_id = ?", (new_plan_id,)
        )[0]
        carried_result = json.loads(carried["result_json"])
        self.assertEqual(carried["generation_state"], "needs_review")
        self.assertIsNone(carried["validation_id"])
        self.assertEqual(carried_result["validation_verdict"], "not_validated")
        self.assertEqual(carried_result["invalidated_reason"], "plan_replanned")
        self.assertNotIn("plan_content_hash", carried_result)

        response = self.err(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": new_plan_id,
                "plan_hash": domain.plan_hash(new_plan_id),
            },
            expected_revision=replanned["revision"],
        )
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(response["details"]["reason"], "plan_not_validated")
        self.assertEqual(
            self.scalar("SELECT state FROM plans WHERE id = ?", (new_plan_id,)), "draft"
        )

    # ── preserved fences ────────────────────────────────────────────────────
    def test_stale_revision_still_refuses(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "add_objectives": [
                    {"title": "Braise short ribs", "evidence_target": "procedure", "criteria": []}
                ],
            },
            expected_revision=0,
            idempotency_key="key-manual-author-stale",
        )
        self.approve(enrollment_id, plan_id, 1)

        stale = self.err(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": domain.plan_hash(plan_id),
            },
            expected_revision=1,
        )
        self.assertEqual(stale["code"], "STALE_REVISION")
        self.assertEqual(stale["details"]["current_revision"], 2)

    def test_idempotent_replay_returns_the_original_approval(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        edited = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "add_objectives": [
                    {"title": "Braise short ribs", "evidence_target": "procedure", "criteria": []}
                ],
            },
            expected_revision=0,
            idempotency_key="key-manual-author-replay",
        )["result"]
        first = self.ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": edited["plan_hash"]},
            expected_revision=edited["revision"],
            idempotency_key="key-approve-replay-1",
        )["result"]
        second = self.ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": edited["plan_hash"]},
            expected_revision=edited["revision"],
            idempotency_key="key-approve-replay-1",
        )["result"]
        self.assertEqual(first, second)
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM transitions WHERE enrollment_id = ?", (enrollment_id,))),
            1,
        )

    # ── helpers ─────────────────────────────────────────────────────────────
    def _table_exists(self, name: str) -> bool:
        with db.read() as connection:
            return connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
            ).fetchone() is not None


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
