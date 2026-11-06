"""The v2 amendment: library, textbook/lesson runtime, notebook edits, deletes, artifact handle.

These were added by CB-018 because the Desktop shell could not be built without them. Each case
asserts the contract shape and the honest refusal, not just a happy path.
"""

from __future__ import annotations

import unittest

from coursebook import api, db, domain
from coursebook.contracts import method_names
from tests.kernel_support import KernelCase


class LibraryTest(KernelCase):
    def test_empty_library_names_the_reason(self) -> None:
        result = self.ok("library.list", {})["result"]
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["empty_reason"], "no_courses")
        self.assertIsNone(result["next_cursor"])
        self.assertEqual(result["applied_filter"], "all")

    def test_a_new_enrollment_appears_with_a_next_step(self) -> None:
        course_id, plan_id = self.new_course(title="Conversational Japanese", recipe="committed")
        self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id, label="Ada")
        result = self.ok("library.list", {})["result"]
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["enrollment_id"], enrollment_id)
        self.assertEqual(item["title"], "Conversational Japanese")
        self.assertEqual(item["learner_label"], "Ada")
        self.assertEqual(item["provenance"]["source"], "authored")
        self.assertEqual(item["next_step"]["kind"], "review_plan")
        self.assertEqual(item["evidence_summary"]["total_objectives"], 1)
        self.assertEqual(item["revision"], 0)
        self.assertIsNone(item["empty_reason"] if "empty_reason" in item else None)

    def test_approved_plan_moves_the_next_step_to_the_first_section(self) -> None:
        lesson = self.prepare_lesson()
        item = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(item["next_step"]["kind"], "start_lesson")
        self.assertIn("Compute", item["next_step"]["label"])
        self.assertEqual(item["evidence_summary"]["current_objective_id"], lesson["objective_id"])

    def test_review_due_filter_follows_evidence_state(self) -> None:
        lesson = self.prepare_lesson()
        self.assertEqual(self.ok("library.list", {"filter": "review_due"})["result"]["total"], 0)
        self.submit(lesson, "5")  # not_yet -> needs_review
        result = self.ok("library.list", {"filter": "review_due"})["result"]
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["next_step"]["kind"], "resolve_review_due")
        self.assertEqual(result["items"][0]["evidence_summary"]["review_due"], 1)

    def test_archived_filter_separates_archived_enrollments(self) -> None:
        course_id, _ = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        self.ok("enrollment.update", {"enrollment_id": enrollment_id, "action": "archive"}, expected_revision=0)
        self.assertEqual(self.ok("library.list", {})["result"]["total"], 0)
        archived = self.ok("library.list", {"filter": "archived"})["result"]
        self.assertEqual(archived["total"], 1)
        self.assertEqual(archived["items"][0]["enrollment_status"], "archived")
        self.assertEqual(self.ok("library.list", {})["result"]["empty_reason"], "all_archived")

    def test_query_and_recipe_filters(self) -> None:
        japanese, _ = self.new_course(title="Japanese", recipe="committed")
        braising, _ = self.new_course(title="Braising", recipe="casual")
        self.new_enrollment(japanese)
        self.new_enrollment(braising)
        self.assertEqual(self.ok("library.list", {"query": "japan"})["result"]["total"], 1)
        self.assertEqual(self.ok("library.list", {"recipe": "casual"})["result"]["total"], 1)
        missing = self.ok("library.list", {"query": "zzz"})["result"]
        self.assertEqual(missing["total"], 0)
        self.assertEqual(missing["empty_reason"], "no_matches")

    def test_pagination_is_cursor_bounded(self) -> None:
        for index in range(3):
            course_id, _ = self.new_course(title=f"Course {index}")
            self.new_enrollment(course_id)
        first = self.ok("library.list", {"limit": 2})["result"]
        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(first["total"], 3)
        self.assertIsNotNone(first["next_cursor"])
        second = self.ok("library.list", {"limit": 2, "cursor": first["next_cursor"]})["result"]
        self.assertEqual(len(second["items"]), 1)
        self.assertIsNone(second["next_cursor"])

    def test_a_bad_cursor_is_a_validation_failure(self) -> None:
        error = self.err("library.list", {"cursor": "not-a-cursor"})
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["field"], "cursor")


class LessonRuntimeTest(KernelCase):
    def test_begin_creates_then_resumes_by_run_not_recency(self) -> None:
        lesson = self.prepare_lesson()
        created = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                            "objective_id": lesson["objective_id"], "mode": "resume"},
                          idempotency_key="begin-key-0001")["result"]
        self.assertEqual(created["run_state"], "created")
        self.assertIsNone(created["binding"])
        self.assertEqual(created["resume"], {"available": False, "reason": "no_binding"})

        again = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                         "objective_id": lesson["objective_id"], "mode": "resume"},
                        idempotency_key="begin-key-0002")["result"]
        self.assertEqual(again["lesson_run_id"], created["lesson_run_id"])
        self.assertEqual(again["run_state"], "needs_fresh_run")

        self.execute(
            "INSERT INTO bindings (id, enrollment_id, lesson_run_id, objective_id, profile,"
            " runtime_session_id, stored_session_id, status, revision, updated_at)"
            " VALUES ('bnd_run_0001', ?, ?, ?, 'cinder', 'runtime-1', 'stored-1', 'active', 0,"
            " '2026-01-01T00:00:00+00:00')",
            (lesson["enrollment_id"], created["lesson_run_id"], lesson["objective_id"]),
        )
        resumed = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                           "objective_id": lesson["objective_id"], "mode": "resume"},
                          idempotency_key="begin-key-0003")["result"]
        self.assertEqual(resumed["run_state"], "resumed")
        self.assertEqual(resumed["binding"]["binding_id"], "bnd_run_0001")
        self.assertTrue(resumed["binding"]["reattachable"])
        self.assertTrue(resumed["resume"]["available"])

    def test_fresh_mode_abandons_the_previous_run(self) -> None:
        lesson = self.prepare_lesson()
        first = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                         "objective_id": lesson["objective_id"], "mode": "resume"},
                        idempotency_key="begin-key-0010")["result"]
        second = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                          "objective_id": lesson["objective_id"], "mode": "fresh"},
                         idempotency_key="begin-key-0011")["result"]
        self.assertNotEqual(first["lesson_run_id"], second["lesson_run_id"])
        self.assertEqual(self.scalar("SELECT state FROM lesson_runs WHERE id = ?", (first["lesson_run_id"],)),
                         "abandoned")
        self.assertEqual(self.scalar("SELECT state FROM lesson_runs WHERE id = ?", (second["lesson_run_id"],)),
                         "active")

    def test_begin_replays_its_idempotency_key(self) -> None:
        lesson = self.prepare_lesson()
        payload = {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"],
                   "mode": "resume"}
        first = self.ok("lesson.begin", payload, idempotency_key="begin-key-0020")["result"]
        second = self.ok("lesson.begin", payload, idempotency_key="begin-key-0020")["result"]
        self.assertEqual(first, second)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM lesson_runs"), 1)

    def test_lesson_page_is_a_durable_read(self) -> None:
        lesson = self.prepare_lesson()
        before = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        page = self.ok("lesson.page", {"enrollment_id": lesson["enrollment_id"],
                                        "objective_id": lesson["objective_id"]})["result"]
        self.assertIsNone(page["runtime"])
        self.assertEqual(page["segments"], [])
        self.assertEqual(page["section"]["title"], "Compute")
        self.assertEqual(page["checks"][0]["check_id"], lesson["check_id"])
        self.assertEqual(page["checks"][0]["attempt_count"], 0)
        self.assertEqual(self.scalar("SELECT revision FROM enrollments WHERE id = ?",
                                     (lesson["enrollment_id"],)), before, "reading changed evidence")

        run = self.ok("lesson.begin", {"enrollment_id": lesson["enrollment_id"],
                                       "objective_id": lesson["objective_id"], "mode": "resume"},
                      idempotency_key="begin-key-0030")["result"]
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES ('seg_0001_x', ?, 1, 'teaching', 'Braising is low and slow.', '2026-01-01T00:00:00+00:00')",
            (run["lesson_run_id"],),
        )
        page = self.ok("lesson.page", {"enrollment_id": lesson["enrollment_id"],
                                        "objective_id": lesson["objective_id"]})["result"]
        self.assertEqual(page["runtime"]["lesson_run_id"], run["lesson_run_id"])
        self.assertEqual(page["runtime"]["session_state"], "missing")
        self.assertEqual(page["segments"][0]["text"], "Braising is low and slow.")
        self.assertEqual(page["state"], "not_started")

    def test_page_refuses_another_courses_objective(self) -> None:
        first = self.prepare_lesson()
        second = self.prepare_lesson()
        error = self.err("lesson.page", {"enrollment_id": second["enrollment_id"],
                                          "objective_id": first["objective_id"]})
        self.assertEqual(error["code"], "VALIDATION_FAILED")


class NotebookUpdateTest(KernelCase):
    def test_edit_is_fenced_on_the_entry_revision(self) -> None:
        lesson = self.prepare_lesson()
        entry = self.ok("notebook.save", {"enrollment_id": lesson["enrollment_id"],
                                          "objective_id": lesson["objective_id"],
                                          "kind": "personal_note", "note": "first",
                                          "tags": ["a"]})["result"]
        updated = self.ok("notebook.update", {"entry_id": entry["entry_id"], "note": "second",
                                              "tags": ["b", "c"]}, expected_revision=0)["result"]
        self.assertEqual(updated["revision"], 1)
        stored = self.rows("SELECT * FROM notebook_entries WHERE id = ?", (entry["entry_id"],))[0]
        self.assertEqual(stored["note"], "second")
        self.assertEqual(stored["revision"], 1)
        stale = self.err("notebook.update", {"entry_id": entry["entry_id"], "note": "third"},
                         expected_revision=0)
        self.assertEqual(stale["code"], "STALE_REVISION")
        self.assertEqual(stale["details"]["current_revision"], 1)

    def test_provenance_fields_cannot_be_edited(self) -> None:
        lesson = self.prepare_lesson()
        entry = self.ok("notebook.save", {"enrollment_id": lesson["enrollment_id"],
                                          "objective_id": lesson["objective_id"],
                                          "kind": "personal_note", "note": "x"})["result"]
        error = self.err("notebook.update", {"entry_id": entry["entry_id"], "source_ref": "rewritten",
                                             "note": "y"}, expected_revision=0)
        self.assertEqual(error["code"], "VALIDATION_FAILED")

    def test_unknown_entry_is_not_found(self) -> None:
        error = self.err("notebook.update", {"entry_id": "nbt_missing_0001", "note": "x"}, expected_revision=0)
        self.assertEqual(error["code"], "NOT_FOUND")


class JobsListTest(KernelCase):
    def test_counts_and_filters(self) -> None:
        first = self.ok("jobs.create", {"kind": "research", "brief": {}})["result"]["job_id"]
        second = self.ok("jobs.create", {"kind": "media", "brief": {}})["result"]["job_id"]
        self.execute("UPDATE jobs SET state = 'running' WHERE id = ?", (second,))
        result = self.ok("jobs.list", {})["result"]
        self.assertEqual(result["counts"], {"queued": 1, "running": 1, "failed": 0, "interrupted": 0})
        self.assertEqual(len(result["jobs"]), 2)
        filtered = self.ok("jobs.list", {"state": ["queued"]})["result"]
        self.assertEqual([job["job_id"] for job in filtered["jobs"]], [first])
        self.assertEqual(filtered["counts"]["running"], 1, "counts describe the filter, not the page")
        kinds = self.ok("jobs.list", {"kind": ["media"]})["result"]
        self.assertEqual(len(kinds["jobs"]), 1)

    def test_interrupted_jobs_are_visible_for_recovery(self) -> None:
        job = self.ok("jobs.create", {"kind": "export", "brief": {}})["result"]["job_id"]
        self.execute("UPDATE jobs SET state = 'interrupted_requires_retry' WHERE id = ?", (job,))
        result = self.ok("jobs.list", {"state": ["interrupted_requires_retry"]})["result"]
        self.assertEqual(result["counts"]["interrupted"], 1)
        self.assertEqual(result["jobs"][0]["state"], "interrupted_requires_retry")

    def test_list_is_bounded(self) -> None:
        error = self.err("jobs.list", {"limit": 101})
        self.assertEqual(error["code"], "VALIDATION_FAILED")

    def test_enrollment_filter_uses_the_job_brief(self) -> None:
        lesson = self.prepare_lesson()
        mine = self.ok("jobs.create", {"kind": "plan", "brief": {"enrollment_id": lesson["enrollment_id"]}})["result"]
        self.ok("jobs.create", {"kind": "plan", "brief": {"enrollment_id": "enr_someone_else"}})
        result = self.ok("jobs.list", {"enrollment_id": lesson["enrollment_id"]})["result"]
        self.assertEqual([job["job_id"] for job in result["jobs"]], [mine["job_id"]])


class BindingAbandonTest(KernelCase):
    def test_abandon_orphans_the_binding_and_blocks_submits(self) -> None:
        lesson = self.prepare_lesson()
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, status, revision, updated_at)"
            " VALUES ('bnd_abandon_01', ?, 'cinder', 'active', 0, '2026-01-01T00:00:00+00:00')",
            (lesson["enrollment_id"],),
        )
        result = self.ok("binding.abandon", {"binding_id": "bnd_abandon_01", "reason": "new chat"},
                         expected_revision=0)["result"]
        self.assertEqual(result["status"], "orphaned")
        self.assertEqual(result["revision"], 1)
        error = self.err("attempt.submit",
                         {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
                          "check_version": lesson["check_version"], "attempt_nonce": "nonce-after-abandon",
                          "answer": {"kind": "text", "text": "4"}},
                         expected_revision=lesson["revision"], idempotency_key="after-abandon-key")
        self.assertEqual(error["code"], "BINDING_NOT_ACTIVE")
        stale = self.err("binding.abandon", {"binding_id": "bnd_abandon_01"}, expected_revision=0)
        self.assertEqual(stale["code"], "STALE_REVISION")

    def test_unknown_binding_is_not_found(self) -> None:
        self.assertEqual(self.err("binding.abandon", {"binding_id": "bnd_missing_0001"},
                                  expected_revision=0)["code"], "NOT_FOUND")


class EnrollmentLifecycleTest(KernelCase):
    def test_pause_and_resume(self) -> None:
        course_id, _ = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        paused = self.ok("enrollment.update", {"enrollment_id": enrollment_id, "action": "pause"},
                         expected_revision=0)["result"]
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["revision"], 1)
        resumed = self.ok("enrollment.update", {"enrollment_id": enrollment_id, "action": "resume"},
                          expected_revision=1)["result"]
        self.assertEqual(resumed["status"], "active")
        self.assertEqual(resumed["revision"], 2)
        stale = self.err("enrollment.update", {"enrollment_id": enrollment_id, "action": "pause"},
                         expected_revision=0)
        self.assertEqual(stale["code"], "STALE_REVISION")

    def test_delete_previews_scope_and_refuses_a_stale_hash(self) -> None:
        lesson = self.prepare_lesson()
        self.submit(lesson, "4")
        self.ok("notebook.save", {"enrollment_id": lesson["enrollment_id"],
                                  "objective_id": lesson["objective_id"],
                                  "kind": "personal_note", "note": "keep?"})
        preview = self.ok("enrollment.delete", {"enrollment_id": lesson["enrollment_id"], "dry_run": True},
                          expected_revision=lesson["revision"] + 1, idempotency_key="preview-key-0001")["result"]
        self.assertFalse(preview["deleted"])
        self.assertEqual(preview["data_scope"]["counts"]["attempts"], 1)
        self.assertEqual(preview["data_scope"]["counts"]["notebook_entries"], 1)
        self.assertTrue(preview["data_scope"]["preserved"]["course"])
        self.assertRegex(preview["data_scope"]["scope_hash"], r"^sha256:[a-f0-9]{64}$")

        stale = self.err("enrollment.delete",
                         {"enrollment_id": lesson["enrollment_id"], "dry_run": False,
                          "data_scope_hash": "sha256:" + "0" * 64},
                         expected_revision=lesson["revision"] + 1, idempotency_key="delete-key-0002")
        self.assertEqual(stale["code"], "DELETE_SCOPE_STALE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 1)

        deleted = self.ok("enrollment.delete",
                          {"enrollment_id": lesson["enrollment_id"], "dry_run": False,
                           "data_scope_hash": preview["data_scope"]["scope_hash"]},
                          expected_revision=lesson["revision"] + 1, idempotency_key="delete-key-0003")["result"]
        self.assertTrue(deleted["deleted"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notebook_entries"), 0)
        # The course and its plan/objectives are preserved by the deletion policy.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM objectives"), 1)


class PackDeleteTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.execute(
            "INSERT INTO packs (id, pack_id, version, manifest_hash, license_json, source, installed_at)"
            " VALUES ('pk_0001_x', 'jp-l0', '1.0.0', 'sha256:" + "a" * 64 + "', '{}', 'community',"
            " '2026-01-01T00:00:00+00:00')"
        )

    def test_freeze_keeps_evidence_and_requires_the_preview_hash(self) -> None:
        course_id, plan_id = self.new_course()
        self.execute("UPDATE courses SET pack_id = 'pk_0001_x' WHERE id = ?", (course_id,))
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok("check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                         expected_revision=revision)["result"]
        lesson = {"enrollment_id": enrollment_id, "check_id": opened["check_id"],
                  "check_version": opened["check_version"], "revision": opened["revision"]}
        self.submit(lesson, "4")

        preview = self.ok("pack.delete", {"pack_id": "jp-l0", "dry_run": True}, expected_revision=0,
                          idempotency_key="pack-preview-01")["result"]
        self.assertEqual(preview["data_scope"]["counts"]["courses"], 1)
        self.assertEqual(preview["data_scope"]["counts"]["enrollments"], 1)
        self.assertFalse(preview["deleted"])

        stale = self.err("pack.delete", {"pack_id": "jp-l0", "dry_run": False,
                                         "data_scope_hash": "sha256:" + "0" * 64},
                         expected_revision=0, idempotency_key="pack-delete-bad")
        self.assertEqual(stale["code"], "DELETE_SCOPE_STALE")

        frozen = self.ok("pack.delete", {"pack_id": "jp-l0", "dry_run": False,
                                         "data_scope_hash": preview["data_scope"]["scope_hash"]},
                         expected_revision=0, idempotency_key="pack-delete-ok")["result"]
        self.assertTrue(frozen["deleted"])
        self.assertEqual(self.scalar("SELECT state FROM packs WHERE pack_id = 'jp-l0'"), "frozen")
        self.assertEqual(self.scalar("SELECT revision FROM packs WHERE pack_id = 'jp-l0'"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 1, "evidence was cascaded away")

        library = self.ok("library.list", {})["result"]["items"][0]
        self.assertEqual(library["warning"], "pack_frozen")
        self.assertEqual(library["provenance"]["pack_id"], "jp-l0")
        self.assertEqual(library["provenance"]["pack_version"], "1.0.0")

    def test_unknown_pack_is_not_found(self) -> None:
        self.assertEqual(self.err("pack.delete", {"pack_id": "nope", "dry_run": True},
                                  expected_revision=0, idempotency_key="missing-pack-key")["code"],
                         "NOT_FOUND")


class ArtifactGetTest(KernelCase):
    def test_returns_metadata_and_a_session_bound_handle_never_a_path(self) -> None:
        course_id, _ = self.new_course()
        self.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, ref_count, created_at)"
            " VALUES ('art_0001_x', ?, 'pdf', 'sha256:" + "b" * 64 + "', '/srv/coursebook/private/x.pdf',"
            " 2048, 'application/pdf', '{\"generator\": \"coursebook.pdf\", \"model\": null,"
            " \"prompt_hash\": null, \"source_ids\": []}', 0, '2026-01-01T00:00:00+00:00')",
            (course_id,),
        )
        result = self.ok("artifact.get", {"artifact_id": "art_0001_x"})["result"]
        self.assertEqual(result["kind"], "pdf")
        self.assertEqual(result["bytes"], 2048)
        self.assertEqual(result["mime"], "application/pdf")
        self.assertRegex(result["download"]["url"], r"^/api/plugins/coursebook/artifacts/[A-Za-z0-9_-]+$")
        self.assertTrue(result["download"]["requires_session"])
        self.assertNotIn("private", repr(result), "a filesystem path must never reach the caller")
        self.assertEqual(self.err("artifact.get", {"artifact_id": "art_missing_0001"})["code"], "NOT_FOUND")


class RegistryTest(unittest.TestCase):
    def test_every_v2_method_is_registered_unless_another_package_owns_it(self) -> None:
        # ``pack.*`` belongs to Lattice (CB-004) and may or may not be wired when this branch is
        # merged; everything the kernel owns must be present, and nothing may be invented.
        pack_methods = {"pack.preview", "pack.import", "pack.export"}
        expected = set(method_names()) - pack_methods
        implemented = set(api.implemented_methods())
        self.assertTrue(expected <= implemented, f"unregistered: {sorted(expected - implemented)}")
        self.assertTrue(implemented <= set(method_names()), "a handler exists for a non-contract method")

    def test_the_kernel_owns_the_v2_lesson_and_library_commands(self) -> None:
        for method in ("library.list", "lesson.page", "lesson.begin", "enrollment.update",
                       "enrollment.delete", "pack.delete", "artifact.get", "jobs.list",
                       "notebook.update", "binding.abandon"):
            with self.subTest(method=method):
                self.assertIn(method, domain.KERNEL_METHODS)


if __name__ == "__main__":
    unittest.main()
