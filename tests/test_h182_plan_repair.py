"""H-182/D1–D3: a refused draft is repairable, a retry is a real attempt, and approval fails closed.

Three defects from the cold walk, each pinned here against the real pipeline and the real command
surface (no hand-written row pretends to be a validation record):

* **D2** — the plan reuse cache answered a *new* job with the draft it had just refused, so
  ``Try again`` finished in seconds with the identical plan hash while the screen claimed a fresh
  research pass. A new attempt for the same brief now runs research again and writes a new plan
  version; the result names what it declined (``reuse_declined``).
* **D3** — the review surface inferred approvability from whichever job line it polled, which
  rendered an ``Approve plan`` control for a refused draft while a retry ran. ``course.outline`` and
  ``parent.blueprint.read`` now project one durable ``validation`` object computed by the same gate
  ``plan.approve`` fences on, and a missing record on a generated draft is not approvable.
* **D1** — the refused draft is repairable. ``parent.plan.edit`` records the parent's explicit
  manual decision, after which approval is offered *as manual* and never as validated, so the loop
  can reach a lesson even when the research pass could not source the first draft.
"""

from __future__ import annotations

import json
import unittest

from coursebook import contracts, db, domain, generation

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)


class RejectedPlanIsNotReplayedTest(KernelCase):
    def run_plan(self, course_id: str, job_id: str, *, reject: bool) -> dict:
        job = plan_job(job_id=job_id)
        job["brief"]["course_id"] = course_id
        script = {
            "coursebook.plan.generate": plan_from_fixture("plan_ja"),
            "coursebook.plan.validate": validation_from_fixture(
                "validation_reject_hazard" if reject else "validation_pass"
            ),
        }
        connection = db.connect()
        try:
            return generation.run_plan_job(connection, job, FakeLLM(script), FakeSearch(), now=NOW)
        finally:
            connection.close()

    def test_a_new_attempt_does_not_get_the_refused_draft_back(self) -> None:
        course_id, _placeholder = self.new_course()
        refused = self.run_plan(course_id, "job-refused-1", reject=True)
        self.assertEqual(refused["validation_verdict"], "reject")
        self.assertFalse(refused["reused"])

        retried = self.run_plan(course_id, "job-retry-2", reject=False)

        # A new job is a new attempt: a fresh plan version and a fresh hash, not the old bytes.
        self.assertFalse(retried["reused"])
        self.assertEqual(retried["reuse_declined"]["reason"], "rejected_draft_not_replayed")
        self.assertEqual(retried["reuse_declined"]["previous_plan_id"], refused["plan_id"])
        self.assertEqual(retried["reuse_declined"]["previous_validation_verdict"], "reject")
        self.assertNotEqual(retried["plan_id"], refused["plan_id"])
        self.assertNotEqual(retried["plan_hash"], refused["plan_hash"])
        self.assertEqual(retried["validation_verdict"], "pass")

    def test_the_job_that_wrote_a_draft_still_reuses_it(self) -> None:
        """A reconnect of the *same* job stays free; only a different attempt re-runs."""
        course_id, _placeholder = self.new_course()
        first = self.run_plan(course_id, "job-same-1", reject=True)

        again = self.run_plan(course_id, "job-same-1", reject=False)

        self.assertTrue(again["reused"])
        self.assertEqual(again["plan_id"], first["plan_id"])
        self.assertEqual(again["plan_hash"], first["plan_hash"])
        self.assertEqual(again["validation_verdict"], "reject")

    def test_a_passing_draft_is_still_reused(self) -> None:
        course_id, _placeholder = self.new_course()
        first = self.run_plan(course_id, "job-pass-1", reject=False)

        again = self.run_plan(course_id, "job-pass-2", reject=False)

        self.assertTrue(again["reused"])
        self.assertEqual(again["plan_id"], first["plan_id"])


class PlanValidationProjectionTest(KernelCase):
    def run_plan(self, course_id: str, job_id: str, *, reject: bool) -> dict:
        job = plan_job(job_id=job_id)
        job["brief"]["course_id"] = course_id
        script = {
            "coursebook.plan.generate": plan_from_fixture("plan_ja"),
            "coursebook.plan.validate": validation_from_fixture(
                "validation_reject_hazard" if reject else "validation_pass"
            ),
        }
        connection = db.connect()
        try:
            return generation.run_plan_job(connection, job, FakeLLM(script), FakeSearch(), now=NOW)
        finally:
            connection.close()

    def outline_validation(self, enrollment_id: str) -> dict:
        outline = self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]
        self.assertIsNotNone(outline["plan"])
        return outline["plan"]["validation"]

    def blueprint_validation(self, course_id: str) -> dict:
        book = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        self.assertIsNotNone(book["plan"])
        return book["plan"]["validation"]

    def test_a_refused_draft_projects_not_approvable_with_its_reasons(self) -> None:
        course_id, _placeholder = self.new_course()
        refused = self.run_plan(course_id, "job-refused", reject=True)
        enrollment_id = self.new_enrollment(course_id)

        validation = self.outline_validation(enrollment_id)

        self.assertFalse(validation["approvable"])
        self.assertEqual(validation["verdict"], "reject")
        self.assertEqual(validation["outcome"], "rejected")
        self.assertGreater(len(validation["reasons"]), 0)
        self.assertIsNone(validation["source"])
        # The blueprint read answers with the same gate.
        self.assertEqual(self.blueprint_validation(course_id)["approvable"], False)
        # And the command refuses, so the screen and the backend cannot disagree.
        self.err(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": refused["plan_id"],
                "plan_hash": domain.plan_hash(refused["plan_id"]),
            },
            expected_revision=0,
        )

    def test_a_passing_draft_projects_approvable_and_approves(self) -> None:
        course_id, _placeholder = self.new_course()
        passed = self.run_plan(course_id, "job-pass", reject=False)
        enrollment_id = self.new_enrollment(course_id)

        validation = self.outline_validation(enrollment_id)

        self.assertTrue(validation["approvable"])
        self.assertEqual(validation["verdict"], "pass")
        self.assertIn(validation["source"], ("generated_validated", "model_assessed_pass"))
        self.assertEqual(self.blueprint_validation(course_id)["approvable"], True)

        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": passed["plan_id"],
                "plan_hash": domain.plan_hash(passed["plan_id"]),
            },
            expected_revision=0,
            idempotency_key="approve-passed-plan",
        )["result"]
        self.assertGreater(approved["revision"], 0)

    def test_an_edit_is_the_repair_and_approves_as_manual(self) -> None:
        """D1: the refused draft can be owned by its parent and approved on the authored outline."""
        course_id, _placeholder = self.new_course()
        refused = self.run_plan(course_id, "job-refused", reject=True)
        enrollment_id = self.new_enrollment(course_id)
        plan_id = refused["plan_id"]
        objective_id = self.scalar(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal LIMIT 1", (plan_id,)
        )

        edited = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "objective_edits": [
                    {"objective_id": objective_id, "title": "Explain attention to a colleague"}
                ],
            },
            expected_revision=0,
            idempotency_key="edit-refused-plan",
        )["result"]

        validation = self.outline_validation(enrollment_id)
        self.assertTrue(validation["approvable"])
        self.assertTrue(validation["manual_authoring"])
        self.assertEqual(validation["source"], "manual")
        self.assertEqual(validation["verdict"], "not_validated")

        approved = self.ok(
            "plan.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": edited["plan_hash"],
            },
            expected_revision=edited["revision"],
            idempotency_key="approve-edited-plan",
        )["result"]
        self.assertGreater(approved["revision"], edited["revision"])
        self.assertEqual(
            str(self.scalar("SELECT state FROM plans WHERE id = ?", (plan_id,))), "approved"
        )

    def test_a_version_with_no_record_is_not_approvable(self) -> None:
        course_id, _placeholder = self.new_course()
        passed = self.run_plan(course_id, "job-pass", reject=False)
        enrollment_id = self.new_enrollment(course_id)
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT id, result_json FROM gen_plan_documents WHERE plan_id = ?",
                (passed["plan_id"],),
            ).fetchone()
            result = json.loads(row["result_json"])
            result.pop("plan_content_hash", None)
            connection.execute(
                "UPDATE gen_plan_documents SET result_json = ? WHERE id = ?",
                (json.dumps(result), row["id"]),
            )

        validation = self.outline_validation(enrollment_id)
        self.assertFalse(validation["approvable"])
        self.assertEqual(validation["reason"], "plan_not_validated")


class ParentStageRetryTest(KernelCase):
    """A parent brief whose locale was never stated is re-queueable through the real payload gate.

    The studio form has no locale field (``parent_brief.locale`` is nullable), while
    ``plan_brief.locale`` is a non-nullable locale string. Storing an explicit ``null`` made the
    brief its own job returns fail ``jobs.create`` payload validation, so "Run this stage again"
    and "Run research again" could never queue a parent plan. The stored brief must omit an
    unstated locale, and the exact payload the renderer sends must validate.
    """

    def brief(self, *, locale=None) -> dict:
        return {
            "title": "Why volcanoes erupt",
            "goal": "Explain how pressure from melted rock builds until a volcano erupts.",
            "starting_point": None,
            "age_band": "8-10",
            "reading_level": "Year 4, short paragraphs",
            "duration_minutes": 25,
            "setting": "home",
            "materials": ["paper", "pencil"],
            "exclusions": ["no heating or burning"],
            "supervision": "An adult reads the safety notes aloud.",
            "desired_pages": 3,
            "desired_visuals": "diagrams",
            "narration": "script",
            "locale": locale,
            "egress_acknowledged": True,
            "redaction_requested": False,
        }

    def test_an_unstated_locale_survives_the_retry_payload_gate(self) -> None:
        created = self.ok(
            "parent.brief.create",
            {"brief": self.brief(locale=None)},
            idempotency_key="parent-brief-no-locale",
        )["result"]
        job_id = created["job_id"]

        job = self.ok("jobs.get", {"job_id": job_id})["result"]["job"]
        stored = job["brief"]
        self.assertNotIn("locale", stored, "an unstated locale must be stored as absence")

        # The renderer sends `job.brief` back verbatim; that exact payload must pass the contract.
        contracts.validate_request_payload("jobs.create", {"kind": "plan", "brief": stored})

        retried = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": stored},
            idempotency_key=f"cb-stage-again-{job_id}",
        )["result"]
        self.assertNotEqual(retried["job_id"], job_id)
        self.assertEqual(retried["state"], "queued")

    def test_a_brief_stored_before_the_fix_is_still_requeueable(self) -> None:
        """A row at rest may still carry ``locale: null``; the read projects absence, not null."""
        created = self.ok(
            "parent.brief.create",
            {"brief": self.brief(locale=None)},
            idempotency_key="parent-brief-legacy-locale",
        )["result"]
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT brief_json FROM jobs WHERE id = ?", (created["job_id"],)
            ).fetchone()
            legacy = json.loads(row["brief_json"])
            legacy["locale"] = None
            connection.execute(
                "UPDATE jobs SET brief_json = ? WHERE id = ?",
                (json.dumps(legacy), created["job_id"]),
            )

        stored = self.ok("jobs.get", {"job_id": created["job_id"]})["result"]["job"]["brief"]
        self.assertNotIn("locale", stored)
        contracts.validate_request_payload("jobs.create", {"kind": "plan", "brief": stored})

    def test_a_stated_locale_is_carried_into_the_retry_brief(self) -> None:
        created = self.ok(
            "parent.brief.create",
            {"brief": self.brief(locale="en-US")},
            idempotency_key="parent-brief-with-locale",
        )["result"]

        stored = self.ok("jobs.get", {"job_id": created["job_id"]})["result"]["job"]["brief"]
        self.assertEqual(stored["locale"], "en-US")
        contracts.validate_request_payload("jobs.create", {"kind": "plan", "brief": stored})


if __name__ == "__main__":
    unittest.main()
