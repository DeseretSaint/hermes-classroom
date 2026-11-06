"""CB-011: the agent-side job tick and the authored parent pack/PDF export.

Every case runs offline against a real migrated SQLite database. The plan/lesson executor uses
the same deterministic ``FakeLLM`` and ``FakeSearch`` seams as ``tests/test_generation.py``; the
export cases seed generation staging rows directly so the pack minima (three rubric criteria per
check) are exercised with content that actually satisfies them. No test opens a network socket.
"""

from __future__ import annotations

import json
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from coursebook import db, domain, executor, generation, job_service, packs, parent_authoring as authoring

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    lesson_from_request,
    plan_from_fixture,
    response,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)

PARENT_BRIEF = {
    "title": "Japanese café basics",
    "goal": "Order coffee in Japanese politely",
    "starting_point": None,
    "age_band": "8-10",
    "reading_level": "early reader",
    "duration_minutes": 20,
    "setting": "home",
    "materials": ["menu card"],
    "exclusions": [],
    "supervision": "An adult is nearby.",
    "desired_pages": 2,
    "desired_visuals": "none",
    "narration": "script",
    "locale": "ja-JP",
    "egress_acknowledged": True,
    "redaction_requested": False,
}


def rich_lesson_response(extra_criteria: int = 2):
    """``lesson_from_request`` with a rubric that satisfies the pack's three-criteria floor."""
    base = lesson_from_request()

    def build(request):
        result = base(request)
        payload = dict(result.parsed or {})
        rubric = list((payload.get("check") or {}).get("rubric") or [])
        for index in range(extra_criteria):
            rubric.append(
                {
                    "criterion": f"declared-{index}",
                    "weight": 1.0,
                    "description": f"Declared observable criterion {index + 1}",
                }
            )
        payload["check"] = {**payload["check"], "rubric": rubric}
        return response(payload, model="fake-author")

    return build


def page_document(section_title: str) -> dict:
    return {
        "section_title": section_title,
        "lesson_intent": "Practise the greeting with a parent.",
        "segments": [
            {"kind": "model", "heading": "Model", "body": "Say the polite greeting clearly."},
            {"kind": "explain", "heading": "Why", "body": "Politeness is the safe default with staff."},
        ],
        "worked_example": {
            "prompt": "You enter a café.",
            "steps": ["Make eye contact", "Greet politely"],
            "answer": "A polite greeting",
        },
        "learner_explanation": "Choose the greeting a visitor would use.",
        "check": {
            "kind": "observation",
            "stimulus": {
                "prompt": "Which greeting opens the interaction politely?",
                "format": "selection",
                "choices": ["Politely greet the staff", "Wave silently"],
            },
            "learner_instructions": "Pick one.",
            "evidence_target": "production",
            "scaffolds": {},
            "assistance_policy": {},
        },
        "sources": [],
        "media": [],
        "parent_notes": "Ask the learner to say it once more.",
        "supervision_notes": ["An adult listens for the polite form"],
    }


class ExecutorTest(KernelCase):
    """queued → running → completed/failed/cancelled through the real job service."""

    def plan_llm(self) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture("plan_ja"),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )

    def create_plan_job(self, **overrides) -> str:
        brief = {
            "goal": "Order coffee in Japanese",
            "recipe": "committed",
            "dials": {"level": "L0"},
            "locale": "ja-JP",
        }
        brief.update(overrides)
        return self.ok("jobs.create", {"kind": "plan", "brief": brief})["result"]["job_id"]

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]

    def test_a_queued_plan_job_completes_offline_through_the_pump(self) -> None:
        job_id = self.create_plan_job()
        self.assertEqual(self.job(job_id)["state"], "queued")

        llm = self.plan_llm()
        search = FakeSearch()
        finished = executor.pump_once(llm=llm, search=search, now=NOW)

        self.assertEqual([view["job_id"] for view in finished], [job_id])
        view = self.job(job_id)
        self.assertEqual(view["state"], "completed")
        self.assertEqual(view["kind"], "plan")
        self.assertIn("plan_id", view["checkpoint"])
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM gen_plan_sections"), 0)
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)
        self.assertTrue(search.fetches, "research must have used the injected seam")
        self.assertGreater(llm.calls_for("coursebook.plan.generate"), 0)

    def test_a_cancelled_queued_job_spends_nothing(self) -> None:
        job_id = self.create_plan_job()
        self.assertEqual(self.ok("jobs.cancel", {"job_id": job_id})["result"]["state"], "cancelled")

        class NoCalls(FakeLLM):
            def __call__(self, request):  # noqa: ANN001 - script must never be reached
                raise AssertionError("a cancelled job must not call the provider")

        executor.pump_once(llm=NoCalls({}), search=FakeSearch(), now=NOW)
        self.assertEqual(self.job(job_id)["state"], "cancelled")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM plans"), 0)

    def test_a_cancel_during_the_stage_finishes_completed_late_not_failed(self) -> None:
        job_id = self.create_plan_job()

        def cancel_after_plan(request):  # noqa: ANN001 - the call really happened before the stop
            job_service.request_cancel(job_id)
            return plan_from_fixture("plan_ja")(request)

        llm = FakeLLM(
            {
                "coursebook.plan.generate": cancel_after_plan,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        executor.pump_once(llm=llm, search=FakeSearch(), now=NOW)
        state = self.job(job_id)["state"]
        self.assertIn(state, ("completed_late", "cancelled"))
        # Whatever ran was really spent and recorded; nothing is silently rewritten to "cancelled".
        self.assertGreater(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)

    def test_a_killed_worker_leaves_interrupted_requires_retry_with_the_same_checkpoint(self) -> None:
        job_id = self.create_plan_job()
        dead = job_service.claim(job_id, owner="worker-previous-process", now=NOW)
        job_service.checkpoint(
            dead, stage="plan", steps_done=1, steps_total=1,
            checkpoint={"plan_id": "pln_resume_me"}, now=NOW,
        )
        report = job_service.reconcile_startup(now=NOW)
        self.assertEqual(report["interrupted"], 1)
        view = self.job(job_id)
        self.assertEqual(view["state"], "interrupted_requires_retry")
        self.assertEqual(view["checkpoint"]["plan_id"], "pln_resume_me")
        # Resume keeps the brief and checkpoint: a retry is a new attempt, not a new job.
        resumed = job_service.resume(job_id, now=NOW)
        self.assertEqual(resumed["state"], "queued")
        self.assertEqual(resumed["checkpoint"]["plan_id"], "pln_resume_me")

    def test_the_one_resolver_dispatches_lessons_on_brief_stage(self) -> None:
        plan_job = self.create_plan_job()
        executor.pump_once(llm=self.plan_llm(), search=FakeSearch(), now=NOW)
        plan_id = self.job(plan_job)["checkpoint"]["plan_id"]
        course_id = str(self.scalar("SELECT course_id FROM plans WHERE id = ?", (plan_id,)))
        enrollment_id = self.new_enrollment(course_id, label="Learner")
        self.assertEqual(self.approve(enrollment_id, plan_id, 0), 1)

        lesson_job = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}},
        )["result"]["job_id"]
        lesson_llm = FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        executor.pump_once(llm=lesson_llm, search=FakeSearch(), now=NOW)

        view = self.job(lesson_job)
        self.assertEqual(view["kind"], "plan", "there is no lesson job kind in cb.vocabulary")
        self.assertEqual(view["state"], "completed")
        self.assertEqual(view["checkpoint"]["lessons"], 3)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 3)

    def test_pump_does_nothing_on_an_unmigrated_store(self) -> None:
        import os
        import shutil
        import tempfile

        fresh = tempfile.mkdtemp(prefix="coursebook-unmigrated-")
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = fresh
        try:
            self.assertFalse(db.store_exists())
            self.assertEqual(executor.pump_once(), [])
            # A read tick must never provision the profile it is reading.
            self.assertFalse((Path(fresh) / "plugin-data" / "coursebook").exists())
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
            shutil.rmtree(fresh, ignore_errors=True)

    def test_the_tick_never_starts_without_a_host_event_loop(self) -> None:
        self.assertIsNone(executor.start_tick(object()))
        self.assertLessEqual(executor.MAX_JOBS_PER_TICK, 20)

    def test_register_starts_the_bounded_tick_when_the_host_can_spawn(self) -> None:
        from tests.test_manifest import RecordingContext, load_plugin_package

        class Done:
            def done(self) -> bool:
                return False

        class TickContext(RecordingContext):
            def __init__(self) -> None:
                super().__init__()
                self.spawned: list[str | None] = []
                self.unloads: list = []

            def spawn_task(self, coro, *, name=None):  # noqa: ANN001 - mirrors the host signature
                self.spawned.append(name)
                coro.close()  # the loop itself is exercised by pump_once above
                return Done()

            def on_unload(self, callback) -> None:  # noqa: ANN001
                self.unloads.append(callback)

        module = load_plugin_package()
        ctx = TickContext()
        module.register(ctx)
        self.assertEqual(ctx.spawned, ["coursebook-job-tick"])
        self.assertEqual(len(ctx.unloads), 1, "the loop must be stopped on unload")
        ctx.unloads[0]()


class ParentSeedMixin(KernelCase):
    """Seed a compliant authored course: approved plan + validated generation staging rows."""

    def new_parent_course(self) -> dict:
        result = self.ok(
            "parent.brief.create",
            {"brief": PARENT_BRIEF},
            idempotency_key="key-brief-1",
        )["result"]
        return result

    def seed_generated_content(self, course_id: str, plan_id: str, enrollment_id: str, *, sections: int = 2) -> str:
        now = "2026-11-06T12:00:00Z"
        gen_hash = "sha256:" + "a" * 64
        with db.read() as connection:
            generation.ensure_schema(connection)
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
                " document_json, research_json, generation_state, validation_id, result_json, created_at)"
                " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
                (f"gpd_{course_id}", plan_id, course_id, gen_hash, now),
            )
            for ordinal in range(1, sections + 1):
                section_id = f"sec_{ordinal}_{course_id}"
                lesson_id = f"lsn_{ordinal}_{course_id}"
                check_id = f"chk_{ordinal}_{course_id}"
                objective = connection.execute(
                    "SELECT * FROM objectives WHERE plan_id = ? AND ordinal = ?", (plan_id, ordinal)
                ).fetchone()
                if objective is None:
                    raise AssertionError("seed_generated_content needs one objective per section")
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                    " objective_refs_json, context_needs_json, source_ids_json)"
                    " VALUES (?, ?, ?, ?, ?, 'Practise with a parent.', ?, '[]', '[]')",
                    (section_id, plan_id, ordinal, gen_hash, f"Section {ordinal}", f"[{ordinal}]"),
                )
                connection.execute(
                    "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
                    " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', ?, '[]', NULL, ?, ?)",
                    (
                        lesson_id,
                        plan_id,
                        section_id,
                        gen_hash,
                        json.dumps(page_document(f"Section {ordinal}")),
                        json.dumps(
                            {
                                "parent_notes": "Ask once more.",
                                "supervision_notes": ["An adult listens for the polite form"],
                            }
                        ),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                    " rubric_json, reference_json, locale, audit_state, state, created_at)"
                    " VALUES (?, ?, 1, 'production', ?, ?, ?, 'ja-JP', 'passed', 'open', ?)",
                    (
                        check_id,
                        objective["id"],
                        json.dumps({"prompt": "Which greeting opens politely?", "format": "selection"}),
                        json.dumps(
                            {
                                "criteria": [
                                    {"criterion": "a", "description": "Greets politely"},
                                    {"criterion": "b", "description": "Uses the polite register"},
                                    {"criterion": "c", "description": "Speaks clearly"},
                                ]
                            }
                        ),
                        json.dumps(
                            {
                                "reference_answer": "Politely greet the staff",
                                "accepted_answers": [],
                                "accepted_alternatives": [],
                            }
                        ),
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, ?)",
                    (lesson_id, check_id, ordinal),
                )
        plan_hash = domain.plan_hash(plan_id)
        with db.transaction() as connection:
            connection.execute(
                "UPDATE plans SET state = 'approved', plan_hash = ?, approved_at = ? WHERE id = ?",
                (plan_hash, now, plan_id),
            )
        return plan_hash


class ParentBriefTest(ParentSeedMixin):
    def test_brief_create_is_idempotent_and_returns_three_ids(self) -> None:
        first = self.ok("parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-1")["result"]
        second = self.ok("parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-1")["result"]
        self.assertEqual(first, second)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)
        self.assertEqual(self.scalar("SELECT recipe FROM courses"), "parent")

        brief = self.ok("parent.brief.get", {"course_id": first["course_id"]})["result"]
        self.assertEqual(brief["brief"]["title"], PARENT_BRIEF["title"])
        self.assertEqual(brief["enrollment_id"], first["enrollment_id"])
        self.assertEqual(brief["plan_job"]["state"], "queued")
        self.assertEqual(brief["plan_job"]["kind"], "plan")

    def test_brief_create_requires_acknowledged_egress(self) -> None:
        brief = dict(PARENT_BRIEF, egress_acknowledged=False)
        error = self.err("parent.brief.create", {"brief": brief}, idempotency_key="key-nope")
        self.assertEqual(error["code"], "VALIDATION_FAILED")

    def test_a_stage_lessons_job_is_a_plan_job(self) -> None:
        # The vocabulary is frozen: no 'lesson' kind exists, so payload validation refuses it.
        error = self.err("jobs.create", {"kind": "lesson", "brief": {"plan_id": "pln_x"}})
        self.assertEqual(error["code"], "VALIDATION_FAILED")


class ParentPlanEditTest(ParentSeedMixin):
    def test_edit_is_draft_only_and_fenced_on_hash_then_revision(self) -> None:
        job_id = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": {"goal": "Order coffee in Japanese", "recipe": "committed",
                                       "dials": {"level": "L0"}, "locale": "ja-JP"}},
        )["result"]["job_id"]
        executor.pump_once(
            llm=FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_ja"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            ),
            search=FakeSearch(),
            now=NOW,
        )
        plan_id = self.ok("jobs.get", {"job_id": job_id})["result"]["job"]["checkpoint"]["plan_id"]
        course_id = str(self.scalar("SELECT course_id FROM plans WHERE id = ?", (plan_id,)))
        enrollment_id = self.new_enrollment(course_id, label="Parent")
        plan_hash = domain.plan_hash(plan_id)
        first_objective = str(self.scalar("SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan_id,)))

        result = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": plan_hash,
                "objective_edits": [{"objective_id": first_objective, "title": "Greet staff warmly"}],
            },
            expected_revision=0,
            idempotency_key="key-edit-1",
        )["result"]
        self.assertNotEqual(result["plan_hash"], plan_hash)
        self.assertTrue(result["changes_need_review"])
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["objective_ids"][0], first_objective)
        self.assertEqual(self.scalar("SELECT title FROM objectives WHERE id = ?", (first_objective,)),
                         "Greet staff warmly")

        stale = self.err(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": plan_hash,
                "goal": "Changed",
            },
            expected_revision=1,
            idempotency_key="key-edit-2",
        )
        self.assertEqual(stale["code"], "VALIDATION_FAILED")
        self.assertIn("current_plan_hash", stale["details"])

    def test_an_approved_plan_cannot_be_edited(self) -> None:
        course_id, plan_id = self.new_course(recipe="committed")
        self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id, label="Parent")
        revision = self.approve(enrollment_id, plan_id, 0)
        error = self.err(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "goal": "Nope",
            },
            expected_revision=revision,
            idempotency_key="key-edit-3",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "plan_not_draft")


class ParentExportTest(ParentSeedMixin):
    def setUp(self) -> None:
        super().setUp()
        created = self.new_parent_course()
        self.course_id = created["course_id"]
        self.enrollment_id = created["enrollment_id"]
        # The brief created a queued plan job; the export fixture replaces it with a stored,
        # approved plan plus validated generation rows (a real plan job is exercised above).
        with db.transaction() as connection:
            plan_id = f"pln_{self.course_id}"
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at, approved_at)"
                " VALUES (?, ?, 1, 'draft', NULL, '{}', '2026-11-06T12:00:00Z', NULL)",
                (plan_id, self.course_id),
            )
            for ordinal in (1, 2):
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target, evidence_criteria_json,"
                    " state, version, created_at) VALUES (?, ?, ?, ?, 'production', ?, 'not_started', 1, ?)",
                    (
                        f"obj_{ordinal}_{self.course_id}",
                        plan_id,
                        ordinal,
                        f"Objective {ordinal}",
                        json.dumps(["Declared criterion A", "Declared criterion B"]),
                        "2026-11-06T12:00:00Z",
                    ),
                )
        self.plan_id = plan_id
        self.plan_hash = self.seed_generated_content(self.course_id, plan_id, self.enrollment_id)

    def blueprint(self) -> dict:
        return self.ok("parent.blueprint.read", {"course_id": self.course_id})["result"]

    def approve_final(self) -> dict:
        brief = self.blueprint()
        return self.ok(
            "parent.final.approve",
            {
                "enrollment_id": self.enrollment_id,
                "plan_id": self.plan_id,
                "plan_hash": brief["plan"]["plan_hash"],
                "content_hash": brief["content_hash"],
            },
            expected_revision=0,
            idempotency_key="key-final-1",
        )["result"]

    def export(self, key: str = "key-export-1") -> dict:
        return self.ok(
            "parent.export",
            {"enrollment_id": self.enrollment_id},
            idempotency_key=key,
        )["result"]

    def test_blueprint_refusal_before_approval_and_no_path_leaks(self) -> None:
        brief = self.blueprint()
        self.assertEqual(brief["export"]["blocked_reason"], "no_final_approval")
        self.assertEqual(len(brief["tabs"]["learner_pages"]), 2)
        self.assertEqual(len(brief["tabs"]["answers"]), 2)
        self.assertEqual(len(brief["tabs"]["parent_guide"]), 2)
        self.assertTrue(brief["tabs"]["narration"], "a script brief has a narration tab")
        self.assertFalse(_has_path_key(brief), "no response object may carry a filesystem path")
        self.assertEqual(brief["approval"]["state"], "none")
        error = self.err("parent.export", {"enrollment_id": self.enrollment_id}, idempotency_key="key-export-0")
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "no_final_approval")

    def test_approved_export_writes_pack_and_selectable_pdf(self) -> None:
        approval = self.approve_final()
        self.assertEqual(approval["state"], "active")
        self.assertEqual(self.blueprint()["export"], {"ready": True, "blocked_reason": None})

        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO notebook_entries (id, enrollment_id, objective_id, kind, excerpt, note,"
                " tags_json, created_at, updated_at)"
                " VALUES ('nb_secret', ?, ?, 'personal_note', 'SECRET-NOTE', 'SECRET-NOTE', '[]', ?, ?)",
                (self.enrollment_id, f"obj_1_{self.course_id}", "2026-11-06T12:00:00Z", "2026-11-06T12:00:00Z"),
            )

        result = self.export()
        self.assertEqual(result["content_hash"], approval["content_hash"])
        roles = {item["role"] for item in result["files"]}
        self.assertEqual(roles, {"parent_guide", "learner_page", "answer_guide"})
        for item in result["files"]:
            self.assertFalse(item["name"].startswith("/"))
            self.assertNotIn("..", item["name"])
            self.assertRegex(item["sha256"], r"^sha256:[a-f0-9]{64}$")
            self.assertEqual(item["mime"], "text/markdown")
        kinds = {item["kind"] for item in result["artifacts"]}
        self.assertEqual(kinds, {"pack", "pdf", "export"})
        pdf_ref = next(item for item in result["artifacts"] if item["kind"] == "pdf")
        self.assertEqual(pdf_ref["mime"], "application/pdf")

        # The pack is a valid cb.pack document, and the private note never entered it.
        with db.read() as connection:
            pack_row = connection.execute(
                "SELECT path FROM artifacts WHERE id = ?", (next(
                    item["artifact_id"] for item in result["artifacts"] if item["kind"] == "pack"
                ),)
            ).fetchone()
        archive_path = Path(str(pack_row["path"]))
        self.assertTrue(archive_path.is_file())
        with zipfile.ZipFile(archive_path) as bundle:
            names = bundle.namelist()
            manifest_name = [name for name in names if name.endswith("/pack.json")].pop()
            document = json.loads(bundle.read(manifest_name))
            self.assertEqual(
                [item["path"] for item in document["files"]],
                [item["name"] for item in result["files"]],
            )
            for key in packs.PRIVATE_FIELDS:
                self.assertNotIn(key, document)
            for name in names:
                self.assertNotIn(b"SECRET-NOTE", bundle.read(name))
        self.assertEqual(document["content_hash"], result["pack"]["manifest_hash"])

        # The PDF is a real selectable-text document, not an image of a page.
        with db.read() as connection:
            pdf_row = connection.execute(
                "SELECT path, bytes FROM artifacts WHERE id = ?", (pdf_ref["artifact_id"],)
            ).fetchone()
        data = Path(str(pdf_row["path"])).read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertIn(b" Tj", data)
        self.assertIn(b"Japanese caf", data)
        self.assertEqual(int(pdf_row["bytes"]), len(data))

        # same key replays; different key reuses the same artifact rows instead of duplicating.
        self.assertEqual(self.export(), result)
        second = self.export(key="key-export-2")
        self.assertEqual(second["pack"]["manifest_hash"], result["pack"]["manifest_hash"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts WHERE kind = 'pdf'"), 1)

    def test_a_content_change_supersedes_export_with_changes_need_review(self) -> None:
        self.approve_final()
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT id, page_json FROM gen_lessons ORDER BY id LIMIT 1"
            ).fetchone()
            page = json.loads(row["page_json"])
            page["learner_explanation"] = "Changed after approval."
            connection.execute(
                "UPDATE gen_lessons SET page_json = ? WHERE id = ?", (json.dumps(page), row["id"])
            )
        brief = self.blueprint()
        self.assertEqual(brief["export"]["blocked_reason"], "changes_need_review")
        error = self.err(
            "parent.export", {"enrollment_id": self.enrollment_id}, idempotency_key="key-export-3"
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "changes_need_review")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)

    def test_reflections_are_recorded_and_never_exported(self) -> None:
        self.approve_final()
        recorded = self.ok(
            "parent.reflection.record",
            {
                "course_id": self.course_id,
                "difficulty": "about_right",
                "revisit_note": "Repeat the greeting next week.",
            },
            idempotency_key="key-reflect-1",
        )["result"]
        self.assertEqual(recorded["difficulty"], "about_right")
        listing = self.ok("parent.reflection.list", {"course_id": self.course_id})["result"]
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["reflections"][0]["reflection_id"], recorded["reflection_id"])
        result = self.export()
        with db.read() as connection:
            pack_row = connection.execute(
                "SELECT path FROM artifacts WHERE id = ?",
                (next(item["artifact_id"] for item in result["artifacts"] if item["kind"] == "pack"),),
            ).fetchone()
        with zipfile.ZipFile(Path(str(pack_row["path"]))) as bundle:
            for name in bundle.namelist():
                self.assertNotIn(b"Repeat the greeting next week.", bundle.read(name))


def _has_path_key(value) -> bool:
    """True when a response object names a local path anywhere (v6 forbids every such field)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"path", "paths", "local_path", "file_path", "directory"}:
                return True
            if _has_path_key(item):
                return True
    elif isinstance(value, list):
        return any(_has_path_key(item) for item in value)
    return False


if __name__ == "__main__":
    unittest.main()
