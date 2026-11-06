"""Command behaviour: courses, plans, checks, notebook, jobs, usage, bindings.

Every case runs the real handler against the real migrated database. Refusal shapes are asserted
as hard as successes: a command that cannot do the work must say so with a contract code.
"""

from __future__ import annotations

import unittest

from coursebook import db, jobs as jobs_contract
from tests.kernel_support import KernelCase, criteria_with, numeric_spec


class CourseAndEnrollmentTest(KernelCase):
    def test_create_returns_minted_ids_and_get_round_trips(self) -> None:
        course_id, plan_id = self.new_course(title="  Braise  ")
        result = self.ok("course.get", {"course_id": course_id})["result"]
        self.assertEqual(result["course"]["title"], "  Braise  ")
        self.assertEqual(result["course"]["status"], "draft")
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["course"]["active_plan_id"], None)
        self.assertEqual([plan["plan_id"] for plan in result["course"]["plans"]], [plan_id])
        self.assertEqual(result["course"]["plans"][0]["state"], "draft")

    def test_ids_are_random_not_titles(self) -> None:
        first, _ = self.new_course(title="Same title")
        second, _ = self.new_course(title="Same title")
        self.assertNotEqual(first, second)
        self.assertNotIn("Same", first)

    def test_create_replays_the_same_idempotency_key(self) -> None:
        payload = {"title": "Braise", "recipe": "casual", "goal": "Braise"}
        first = self.ok("course.create", payload, idempotency_key="create-key-0001")["result"]
        second = self.ok("course.create", payload, idempotency_key="create-key-0001")["result"]
        self.assertEqual(first, second)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)

    def test_same_key_different_payload_is_a_conflict(self) -> None:
        self.ok("course.create", {"title": "A", "recipe": "casual", "goal": "g"}, idempotency_key="create-key-0002")
        error = self.err(
            "course.create", {"title": "B", "recipe": "casual", "goal": "g"}, idempotency_key="create-key-0002"
        )
        self.assertEqual(error["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(error["category"], "conflict")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)

    def test_enrollment_on_unknown_course_is_not_found(self) -> None:
        error = self.err("enrollment.create", {"course_id": "crs_missing_0001"})
        self.assertEqual(error["code"], "NOT_FOUND")

    def test_course_get_unknown_is_not_found(self) -> None:
        self.assertEqual(self.err("course.get", {"course_id": "crs_missing_0002"})["code"], "NOT_FOUND")


class PlanApprovalTest(KernelCase):
    def test_approval_binds_to_the_exact_plan_hash(self) -> None:
        course_id, plan_id = self.new_course()
        self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        error = self.err(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": "sha256:" + "0" * 64},
            expected_revision=0,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["field"], "plan_hash")
        self.assertRegex(error["details"]["current_plan_hash"], r"^sha256:[a-f0-9]{64}$")

    def test_approval_requires_expected_revision(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        error = self.err(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": __import__("coursebook.domain", fromlist=["x"]).plan_hash(plan_id)},
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["field"], "expected_revision")

    def test_approval_bumps_revision_and_writes_one_transition(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        revision = self.ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
            expected_revision=0,
        )["result"]["revision"]
        self.assertEqual(revision, 1)
        self.assertEqual(self.scalar("SELECT state FROM plans WHERE id = ?", (plan_id,)), "approved")
        transitions = self.rows("SELECT * FROM transitions WHERE enrollment_id = ?", (enrollment_id,))
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["to_revision"], 1)

    def test_criteria_are_part_of_the_approved_hash(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        plan_hash = domain.plan_hash(plan_id)
        # The plan's evidence criteria are inside the hash: editing them invalidates the approval.
        self.execute(
            "UPDATE objectives SET evidence_criteria_json = '[{\"id\":\"c1\",\"description\":\"weaker\"}]'"
            " WHERE id = ?",
            (objective_id,),
        )
        error = self.err(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": plan_hash},
            expected_revision=0,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["field"], "plan_hash")
        self.assertNotEqual(error["details"]["current_plan_hash"], plan_hash)

    def test_stale_approval_is_refused_with_current_revision(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        plan_hash = domain.plan_hash(plan_id)
        self.ok("plan.approve", {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": plan_hash},
                expected_revision=0)
        error = self.err("plan.approve",
                         {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": plan_hash},
                         expected_revision=0)
        self.assertEqual(error["code"], "STALE_REVISION")
        self.assertEqual(error["details"]["current_revision"], 1)

    def test_replan_supersedes_the_approved_plan_and_pauses_checks(self) -> None:
        lesson = self.prepare_lesson()
        revision = lesson["revision"]
        replanned = self.ok(
            "plan.replan",
            {"enrollment_id": lesson["enrollment_id"],
             "objective_changes": [{"objective_id": lesson["objective_id"], "change": "keep"}]},
            expected_revision=revision,
        )["result"]
        self.assertEqual(replanned["plan_version"], 2)
        self.assertEqual(replanned["revision"], revision + 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM plans WHERE course_id = ? AND state = 'approved'",
                                     (lesson["course_id"],)), 0)
        error = self.err("check.open",
                         {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
                         expected_revision=replanned["revision"])
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "plan_not_approved")

    def test_replan_retitle_remove_and_add(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        first = self.seed_objective(plan_id)
        second = domain.record_objective(plan_id, title="Second", evidence_target="recall", criteria=[])
        enrollment_id = self.new_enrollment(course_id)
        self.ok("plan.approve",
                {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
                expected_revision=0)
        self.ok("plan.replan",
                {"enrollment_id": enrollment_id, "objective_changes": [
                    {"objective_id": first, "change": "retitle", "title": "Renamed"},
                    {"objective_id": second, "change": "remove"},
                ]},
                expected_revision=1)
        plans = self.rows("SELECT * FROM plans WHERE course_id = ? ORDER BY version", (course_id,))
        objectives = self.rows("SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plans[1]["id"],))
        self.assertEqual([row["title"] for row in objectives], ["Renamed"])

    def test_replan_unknown_objective_is_not_found(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        self.ok("plan.approve",
                {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
                expected_revision=0)
        error = self.err("plan.replan",
                         {"enrollment_id": enrollment_id,
                          "objective_changes": [{"objective_id": "obj_missing_0001", "change": "keep"}]},
                         expected_revision=1)
        self.assertEqual(error["code"], "NOT_FOUND")


class CheckOpenTest(KernelCase):
    def test_open_is_repeatable_without_stacking_checks(self) -> None:
        lesson = self.prepare_lesson()
        again = self.ok("check.open",
                        {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
                        expected_revision=lesson["revision"])["result"]
        self.assertEqual(again["check_id"], lesson["check_id"])
        self.assertEqual(again["check_version"], lesson["check_version"])
        self.assertEqual(again["revision"], lesson["revision"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM checks"), 1)

    def test_unaudited_check_cannot_be_opened(self) -> None:
        spec = numeric_spec(audit_state="pending")
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id, spec)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        error = self.err("check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                         expected_revision=revision)
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "check_not_audited")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM checks"), 0)

    def test_objective_without_spec_is_not_checkable(self) -> None:
        from coursebook import domain

        course_id, plan_id = self.new_course()
        objective_id = domain.record_objective(plan_id, title="No spec", evidence_target="recall", criteria=[])
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        error = self.err("check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                         expected_revision=revision)
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "objective_not_checkable")

    def test_challenge_out_never_replays_a_seen_stimulus(self) -> None:
        variant = {"stimulus": {"prompt": "Compute 7-3."},
                   "reference": {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}},
                   "audit_state": "passed"}
        spec = numeric_spec(variants=[variant])
        lesson = self.prepare_lesson(spec)
        challenge = self.ok(
            "progression.challenge_out",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=lesson["revision"],
        )["result"]
        self.assertEqual(challenge["check_version"], 2)
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)), "superseded")
        # No unused variant remains: a second challenge would be a replay, so it is refused.
        error = self.err("progression.challenge_out",
                         {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
                         expected_revision=challenge["revision"])
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "no_varied_challenge_available")

    def test_challenge_out_refuses_an_objective_without_variants(self) -> None:
        lesson = self.prepare_lesson()
        error = self.err("progression.challenge_out",
                         {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
                         expected_revision=lesson["revision"])
        self.assertEqual(error["details"]["reason"], "no_varied_challenge_available")


class NotebookTest(KernelCase):
    def test_save_list_and_delete(self) -> None:
        lesson = self.prepare_lesson()
        saved = self.ok("notebook.save", {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": lesson["objective_id"],
            "kind": "personal_note",
            "note": "Ribs need a dry rub.",
            "tags": ["braise", "meat"],
        })["result"]
        listed = self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"]})["result"]["entries"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["entry_id"], saved["entry_id"])
        self.assertEqual(listed[0]["tags"], ["braise", "meat"])
        self.assertEqual(listed[0]["note"], "Ribs need a dry rub.")

        tagged = self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"], "tag": "braise"})["result"]
        self.assertEqual(len(tagged["entries"]), 1)
        self.assertEqual(self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"], "tag": "fish"})["result"]["entries"], [])

        found = self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"], "query": "dry rub"})["result"]
        self.assertEqual(len(found["entries"]), 1)

        deleted = self.ok("notebook.delete", {"entry_id": saved["entry_id"]})["result"]
        self.assertTrue(deleted["deleted"])
        self.assertEqual(self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"]})["result"]["entries"], [])
        self.assertEqual(self.err("notebook.delete", {"entry_id": saved["entry_id"]})["code"], "NOT_FOUND")

    def test_entries_do_not_leak_between_enrollments(self) -> None:
        first = self.prepare_lesson()
        second = self.prepare_lesson()
        self.ok("notebook.save", {"enrollment_id": first["enrollment_id"], "objective_id": first["objective_id"],
                                  "kind": "personal_note", "note": "private to first"})
        self.assertEqual(self.ok("notebook.list", {"enrollment_id": second["enrollment_id"]})["result"]["entries"], [])
        self.assertEqual(len(self.ok("notebook.list", {"enrollment_id": first["enrollment_id"]})["result"]["entries"]), 1)

    def test_objective_from_another_course_is_refused(self) -> None:
        first = self.prepare_lesson()
        second = self.prepare_lesson()
        error = self.err("notebook.save", {
            "enrollment_id": second["enrollment_id"],
            "objective_id": first["objective_id"],
            "kind": "personal_note",
            "note": "cross-course",
        })
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "objective_not_in_enrollment_course")

    def test_list_is_bounded_to_500_rows(self) -> None:
        lesson = self.prepare_lesson()
        with db.transaction() as connection:
            for index in range(600):
                connection.execute(
                    "INSERT INTO notebook_entries (id, enrollment_id, objective_id, kind, note, tags_json,"
                    " created_at, updated_at) VALUES (?, ?, ?, 'personal_note', ?, '[]', ?, ?)",
                    (f"nbt_{index:06d}_bulk", lesson["enrollment_id"], lesson["objective_id"],
                     f"note {index}", f"2026-01-01T00:00:{index % 60:02d}.000000+00:00",
                     "2026-01-01T00:00:00.000000+00:00"),
                )
        entries = self.ok("notebook.list", {"enrollment_id": lesson["enrollment_id"]})["result"]["entries"]
        self.assertEqual(len(entries), 500)


class JobsTest(KernelCase):
    def test_create_get_and_cancel_a_queued_job(self) -> None:
        created = self.ok("jobs.create", {"kind": "research", "brief": {"topic": "braising"}})["result"]
        self.assertEqual(created["state"], "queued")
        job = self.ok("jobs.get", {"job_id": created["job_id"]})["result"]["job"]
        self.assertEqual(job["kind"], "research")
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["brief"], {"topic": "braising"})
        self.assertTrue(job["attempt_id"])
        self.assertIsNone(job["error"])

        cancelled = self.ok("jobs.cancel", {"job_id": created["job_id"]})["result"]
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(self.ok("jobs.get", {"job_id": created["job_id"]})["result"]["job"]["state"], "cancelled")
        self.assertEqual(self.err("jobs.cancel", {"job_id": created["job_id"]})["code"], "JOB_NOT_CANCELLABLE")

    def test_running_job_is_cancel_requested_not_cancelled(self) -> None:
        created = self.ok("jobs.create", {"kind": "media", "brief": {}})["result"]
        self.execute("UPDATE jobs SET state = 'running' WHERE id = ?", (created["job_id"],))
        self.assertEqual(self.ok("jobs.cancel", {"job_id": created["job_id"]})["result"]["state"],
                         "cancel_requested")
        self.assertEqual(self.err("jobs.cancel", {"job_id": created["job_id"]})["code"], "JOB_NOT_CANCELLABLE")

    def test_unknown_job_is_not_found(self) -> None:
        self.assertEqual(self.err("jobs.get", {"job_id": "job_missing_0001"})["code"], "NOT_FOUND")
        self.assertEqual(self.err("jobs.cancel", {"job_id": "job_missing_0001"})["code"], "NOT_FOUND")

    def test_job_state_is_the_contract_state_machine(self) -> None:
        created = self.ok("jobs.create", {"kind": "export", "brief": {}})["result"]
        self.assertIn(created["state"], jobs_contract.states())


class UsageTest(KernelCase):
    def test_empty_usage_is_zero_calls_and_unknown_tokens(self) -> None:
        result = self.ok("usage.summary", {})["result"]
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["tokens"], {"input": None, "output": None, "cache_read": None, "cache_write": None})
        self.assertEqual(result["unknown_fields"], ["cache_read", "cache_write", "input", "output"])
        self.assertEqual(result["artifacts"], 0)

    def test_recorded_tokens_sum_and_missing_fields_stay_unknown(self) -> None:
        lesson = self.prepare_lesson()
        with db.transaction() as connection:
            for index, tokens in enumerate(['{"input": 10, "output": 5}', '{"input": 7}']):
                connection.execute(
                    "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model, tokens_json,"
                    " duration_ms, artifact_count, recorded_at) VALUES (?, ?, ?, 'nous', 'm', ?, 100, 1, ?)",
                    (f"use_{index:04d}_x", f"op-{index}", lesson["enrollment_id"], tokens, "2026-01-01T00:00:00+00:00"),
                )
        result = self.ok("usage.summary", {"enrollment_id": lesson["enrollment_id"]})["result"]
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["tokens"]["input"], 17)
        self.assertEqual(result["tokens"]["output"], 5)
        self.assertEqual(result["unknown_fields"], ["cache_read", "cache_write", "output"])
        self.assertEqual(result["artifacts"], 2)


class BindingTest(KernelCase):
    def test_no_binding_returns_null(self) -> None:
        lesson = self.prepare_lesson()
        self.assertEqual(self.ok("binding.get", {"enrollment_id": lesson["enrollment_id"]})["result"]["binding"], None)

    def test_binding_resolves_by_stored_id_only_never_recency(self) -> None:
        lesson = self.prepare_lesson()
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at)"
            " VALUES ('bnd_0001_x', ?, 'cinder', 'conn-1', 'runtime-abc', 'stored-xyz', 'cwd-hash', NULL,"
            " 'active', 0, '2026-01-01T00:00:00+00:00')",
            (lesson["enrollment_id"],),
        )
        # A runtime id is a live-gateway id, not an identity: it must not resolve a binding (R1).
        self.assertEqual(self.ok("binding.get", {"session_id": "runtime-abc"})["result"]["binding"], None)
        by_stored = self.ok("binding.get", {"session_id": "stored-xyz"})["result"]["binding"]
        self.assertEqual(by_stored["runtime_session_id"], "runtime-abc")
        self.assertEqual(by_stored["matched_column"], "stored_session_id")
        # A legacy/course-level binding (no lesson_run_id) reports no section rather than a guess.
        self.assertIsNone(by_stored["objective_id"])
        self.assertIsNone(by_stored["lesson_run_id"])
        self.assertEqual(self.ok("binding.get", {"session_id": "unknown-session"})["result"]["binding"], None)
        # Exactly one identifier is accepted; two is a caller bug, not a preference order.
        error = self.err("binding.get", {"session_id": "stored-xyz", "enrollment_id": lesson["enrollment_id"]})
        self.assertEqual(error["code"], "VALIDATION_FAILED")

    def test_binding_reports_the_section_it_is_bound_to(self) -> None:
        """The pane scopes by `binding.objective_id`; `evidence_summary` is the enrollment's current."""
        lesson = self.prepare_lesson()
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "mode": "fresh",
            },
            idempotency_key="begin-scope-key-0001",
        )["result"]
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, lesson_run_id, objective_id, cwd_fingerprint, compression_tip,"
            " status, revision, updated_at)"
            " VALUES ('bnd_scope_x', ?, 'cinder', NULL, 'runtime-scope', 'stored-scope', ?, ?,"
            " NULL, NULL, 'active', 0, '2026-01-01T00:00:00+00:00')",
            (lesson["enrollment_id"], run["lesson_run_id"], lesson["objective_id"]),
        )
        binding = self.ok("binding.get", {"session_id": "stored-scope"})["result"]["binding"]
        self.assertEqual(binding["objective_id"], lesson["objective_id"])
        self.assertEqual(binding["lesson_run_id"], run["lesson_run_id"])
        # Additive fields must not disturb the status the pane renders for this chat.
        self.assertEqual(binding["status"], "active")
        by_enrollment = self.ok("binding.get", {"enrollment_id": lesson["enrollment_id"]})["result"]["binding"]
        self.assertEqual(by_enrollment["objective_id"], lesson["objective_id"])
        self.assertEqual(by_enrollment["lesson_run_id"], run["lesson_run_id"])


if __name__ == "__main__":
    unittest.main()
