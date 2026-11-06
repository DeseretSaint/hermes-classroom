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
from datetime import datetime, timedelta, timezone
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


def parent_lesson_response(rubric_criteria: int = 3):
    """A parent-observation lesson in the shape the lesson-prompt.v2 instructions ask for.

    Three distinct observable criteria, an observation check, parent notes and supervision notes.
    ``accepted_answers`` deliberately repeats the reference answer: the shipped lesson fixtures do
    exactly that, and the export must drop it from ``accepted_alternatives``.
    """

    def build(request):
        payload = json.loads(request.input_text)
        section = payload.get("section") or {}
        objective = payload.get("objective") or {}
        lesson = {
            "section_title": section.get("title") or "Kitchen science",
            "segments": [
                {
                    "kind": "model",
                    "heading": "Name one of each",
                    "body": "Point at the kettle: it holds hot water. Point at the fridge: it is cold inside.",
                },
                {
                    "kind": "guided",
                    "heading": "Sort the cards",
                    "body": "Put each card under the warm or cold heading and say the word out loud.",
                },
            ],
            "worked_example": {
                "prompt": "Which card belongs under warm?",
                "steps": ["Look at the picture", "Say the object name", "Choose warm"],
                "answer": "The pot card",
            },
            "learner_explanation": "You will name warm and cold things, then sort the picture cards together.",
            "check": {
                "kind": "observation",
                "stimulus": {
                    "prompt": "Which card belongs under warm?",
                    "format": "selection",
                    "choices": ["kettle card", "fridge card"],
                },
                "learner_instructions": "Watch the child choose one card.",
                "evidence_target": objective.get("evidence_target") or "recall",
                "accepted_answers": ["kettle card"],
                "rubric": [
                    {
                        "criterion": f"observable-{index + 1}",
                        "weight": 1.0,
                        "description": f"Observable criterion {index + 1}: the child performs the described step.",
                    }
                    for index in range(rubric_criteria)
                ],
                "reference_answer": "kettle card",
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "hinted"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            },
            "parent_notes": "Point at each object before asking.",
            "supervision_notes": ["An adult stays within arm's reach for the whole activity"],
            "sources": [],
            "media": [],
        }
        return response(lesson, model="fake-parent-author")

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
        # A real crash stops renewing, so the lease is what has to lapse before recovery may
        # touch the row. (Reclaiming on owner mismatch is the bug that killed live jobs.)
        report = job_service.reconcile_startup(
            now=NOW + timedelta(seconds=job_service.LEASE_SECONDS + 1)
        )
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
        self.assertEqual(view["checkpoint"]["lessons"], 4)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 4)

    def test_a_lesson_provider_timeout_is_a_host_failure_the_parent_can_retry(self) -> None:
        """CB-011-D1: the live failure. jobs.get must name the provider, not the grader."""
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
        author = lesson_from_request()
        generations = {"count": 0}

        def stall_on_the_second_section(request):  # noqa: ANN001 - the host seam raised
            generations["count"] += 1
            if generations["count"] == 2:
                raise TimeoutError("provider stalled past its deadline")
            return author(request)

        executor.pump_once(
            llm=FakeLLM(
                {
                    "coursebook.lesson.generate": stall_on_the_second_section,
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            ),
            search=FakeSearch(),
            now=NOW,
        )

        # jobs.get validates the stored error against cb.errors through api.dispatch.
        view = self.job(lesson_job)
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"]["code"], "HOST_UNAVAILABLE")
        self.assertEqual(view["error"]["category"], "capability")
        self.assertTrue(view["error"]["retryable"])
        self.assertIn("sections are saved", view["error"]["message"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 1)

        retry_job = self.ok(
            "jobs.create",
            {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}},
        )["result"]["job_id"]
        retry_llm = FakeLLM(
            {
                "coursebook.lesson.generate": author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        executor.pump_once(llm=retry_llm, search=FakeSearch(), now=NOW)
        retried = self.job(retry_job)
        self.assertEqual(retried["state"], "completed")
        self.assertEqual(retried["checkpoint"]["lessons"], 4)
        # Only the three missing sections were authored: the saved one was reused, not re-charged.
        self.assertEqual(retry_llm.calls_for("coursebook.lesson.generate"), 3)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 4)

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

        # The Hermes loader calls register() synchronously, so the spawn_task branch only exists
        # when a loop is already running. Before this test ran under a loop it asserted behaviour
        # no real host provides (which is exactly the bug that left jobs queued forever).
        import asyncio

        async def register_inside_a_running_loop() -> None:
            module.register(ctx)

        asyncio.run(register_inside_a_running_loop())
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
                                # The shipped lesson author copies accepted answers into the
                                # reference answer slot; the export must not echo it back.
                                "accepted_answers": ["Politely greet the staff"],
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

    def test_exported_rubrics_are_assessment_criteria_only(self) -> None:
        """The rubric is the check's criteria plus the plan's evidence criteria, nothing else."""
        with db.read() as connection:
            course = connection.execute("SELECT * FROM courses WHERE id = ?", (self.course_id,)).fetchone()
            plan = connection.execute("SELECT * FROM plans WHERE id = ?", (self.plan_id,)).fetchone()
            composed = authoring.sections(connection, course, plan)
        section = next(item for item in composed if item.get("check") is not None)
        rubric = authoring._check_rubric(section["check"], section["objective"])
        self.assertEqual(
            rubric,
            [
                "Greets politely",
                "Uses the polite register",
                "Speaks clearly",
                "Declared criterion A",
                "Declared criterion B",
            ],
        )
        self.assertFalse(
            any("adult listens" in item.casefold() for item in rubric),
            "a supervision note is a safety instruction, not a grading criterion",
        )

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

    def test_a_short_rubric_still_refuses_export_with_the_named_problems(self) -> None:
        """A lesson stored before the floor existed is refused, not bypassed or padded."""
        with db.transaction() as connection:
            connection.execute(
                "UPDATE checks SET rubric_json = ?",
                (json.dumps({"criteria": [{"criterion": "a", "description": "Greets politely"}]}),),
            )
            connection.execute(
                "UPDATE objectives SET evidence_criteria_json = ?",
                (json.dumps(["Declared criterion A"]),),
            )
        self.approve_final()
        error = self.err("parent.export", {"enrollment_id": self.enrollment_id}, idempotency_key="key-export-short")
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "export_not_exportable")
        self.assertIn("rubric criteria; minimum is 3", error["message"])
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


class ParentPipelineExportTest(KernelCase):
    """``plan_parent`` through the real executor pipeline, approved and exported with no seeding."""

    def pump(self, llm: FakeLLM) -> None:
        executor.pump_once(llm=llm, search=FakeSearch(), now=NOW)

    def test_a_real_generated_parent_course_exports_and_meets_the_pack_minima(self) -> None:
        created = self.ok(
            "parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-e2e"
        )["result"]
        course_id = created["course_id"]
        enrollment_id = created["enrollment_id"]

        # 1. The plan job really ran: one section per objective, four of each.
        self.pump(
            FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_parent"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            )
        )
        plan_ref = self.ok("parent.brief.get", {"course_id": course_id})["result"]["plan_job"]
        plan_job = self.ok("jobs.get", {"job_id": plan_ref["job_id"]})["result"]["job"]
        self.assertEqual(plan_job["state"], "completed")
        plan_id = plan_job["checkpoint"]["plan_id"]
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_plan_sections"), 4)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 0)  # nothing seeded

        # 2. The lesson job really ran: four validated lessons, none parked.
        revision = self.approve(enrollment_id, plan_id, 0)
        lesson_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id}}
        )["result"]["job_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.lesson.generate": parent_lesson_response(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
        )
        lesson_job = self.ok("jobs.get", {"job_id": lesson_job_id})["result"]["job"]
        self.assertEqual(lesson_job["state"], "completed")
        self.assertEqual(
            [row["state"] for row in self.rows("SELECT state FROM gen_lessons ORDER BY created_at")],
            ["validated"] * 4,
        )

        # 3. Approve exactly the served content, then export it.
        blueprint = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        self.assertEqual(len(blueprint["tabs"]["narration"]), 4)
        approval = self.ok(
            "parent.final.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": blueprint["plan"]["plan_hash"],
                "content_hash": blueprint["content_hash"],
            },
            expected_revision=revision,
            idempotency_key="key-final-e2e",
        )["result"]
        self.assertEqual(approval["state"], "active")

        result = self.ok(
            "parent.export", {"enrollment_id": enrollment_id}, idempotency_key="key-export-e2e"
        )["result"]
        self.assertEqual(result["content_hash"], approval["content_hash"])
        roles = {item["role"] for item in result["files"]}
        self.assertEqual(roles, {"parent_guide", "learner_page", "answer_guide"})
        self.assertTrue(all(item["mime"] == "text/markdown" for item in result["files"]))

        # The narration script is served as a tab (clipped to the request limit) and written in full
        # inside the exported parent guide.
        served_script = blueprint["tabs"]["narration"][0]["text"].strip()
        self.assertTrue(served_script)
        with db.read() as connection:
            pack_row = connection.execute(
                "SELECT path FROM artifacts WHERE id = ?",
                (next(item["artifact_id"] for item in result["artifacts"] if item["kind"] == "pack"),),
            ).fetchone()
        archive = Path(str(pack_row["path"]))
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            manifest_name = [name for name in names if name.endswith("/pack.json")].pop()
            document = json.loads(bundle.read(manifest_name))
            guide_name = next(name for name in names if "/parent-guide/" in name)
            guide_text = bundle.read(guide_name).decode("utf-8")
        self.assertIn("## Narration script", guide_text)
        self.assertIn(served_script.splitlines()[0], guide_text)

        # Every check is teachable and carries assessment criteria only.
        authored = {
            f"Observable criterion {index}: the child performs the described step."
            for index in (1, 2, 3)
        }
        supervision = "An adult stays within arm's reach for the whole activity"
        for objective in document["objectives"]:
            self.assertEqual(len(objective["sections"]), 1)
            self.assertEqual(len(objective["checks"]), 1)
            check = objective["checks"][0]
            self.assertGreaterEqual(len(check["rubric"]), packs.MIN_RUBRIC_CRITERIA)
            self.assertTrue(
                set(check["rubric"]) <= authored | set(objective["evidence_criteria"]),
                "a rubric entry must come from the check or the plan's evidence criteria",
            )
            self.assertFalse(
                any(supervision.casefold() in item.casefold() for item in check["rubric"]),
                "supervision notes are not grading criteria",
            )
            self.assertNotIn(check["reference_answer"], check.get("accepted_alternatives") or [])


    def test_a_replanned_plan_carries_its_outline_through_edit_to_lessons_and_export(self) -> None:
        """The dead end from CB-015 row 9: replan → edit → approve → lessons → approve → export.

        ``plan.replan`` cannot author prose, so it must carry the approved outline onto the new
        version. Without the carry ``run_lesson_job`` fails ``has no authored document`` and the
        course can never reach export again (``parent.export`` stays ``no_generated_content``).
        """
        created = self.ok(
            "parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-replan"
        )["result"]
        course_id = created["course_id"]
        enrollment_id = created["enrollment_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_parent"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            )
        )
        plan_ref = self.ok("parent.brief.get", {"course_id": course_id})["result"]["plan_job"]
        first_job = self.ok("jobs.get", {"job_id": plan_ref["job_id"]})["result"]["job"]
        self.assertEqual(first_job["state"], "completed")
        first_plan_id = first_job["checkpoint"]["plan_id"]
        revision = self.approve(enrollment_id, first_plan_id, 0)

        # 1. A content-preserving replan: keep every objective, retitle one.
        objectives = self.rows(
            "SELECT id, ordinal FROM objectives WHERE plan_id = ? ORDER BY ordinal", (first_plan_id,)
        )
        changes = [
            (
                {"objective_id": row["id"], "change": "retitle", "title": "Renamed opening"}
                if row["ordinal"] == 1
                else {"objective_id": row["id"], "change": "keep"}
            )
            for row in objectives
        ]
        replanned = self.ok(
            "plan.replan",
            {"enrollment_id": enrollment_id, "objective_changes": changes},
            expected_revision=revision,
            idempotency_key="key-replan-1",
        )["result"]
        self.assertEqual(replanned["plan_version"], 2)
        revision = replanned["revision"]
        new_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft' ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        # The carry is real: the new version has a document and one section per objective.
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM gen_plan_documents WHERE plan_id = ?", (new_plan_id,)), 1
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM gen_plan_sections WHERE plan_id = ?", (new_plan_id,)), 4
        )
        self.assertNotEqual(new_plan_id, str(first_plan_id))

        # 2. Edit the new draft through the Parent Studio command, then approve it.
        new_objective = self.rows(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal LIMIT 1", (new_plan_id,)
        )[0]["id"]
        edited = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": new_plan_id,
                "expected_plan_hash": domain.plan_hash(new_plan_id),
                "objective_edits": [{"objective_id": new_objective, "title": "Edited after replan"}],
            },
            expected_revision=revision,
            idempotency_key="key-replan-edit-1",
        )["result"]
        revision = self.approve(enrollment_id, new_plan_id, edited["revision"])

        # 3. Lessons for the replanned version: one per section, no provider re-authoring of a plan.
        lesson_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": new_plan_id}}
        )["result"]["job_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.lesson.generate": parent_lesson_response(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
        )
        lesson_job = self.ok("jobs.get", {"job_id": lesson_job_id})["result"]["job"]
        self.assertEqual(lesson_job["state"], "completed", lesson_job.get("error"))
        self.assertEqual(lesson_job["checkpoint"]["lessons"], 4)
        self.assertEqual(
            [row["state"] for row in self.rows("SELECT state FROM gen_lessons ORDER BY created_at")],
            ["validated"] * 4,
        )
        # The lessons read the edited objective title, not the pre-replan document snapshot.
        self.assertEqual(
            self.scalar(
                "SELECT title FROM objectives WHERE plan_id = ? ORDER BY ordinal LIMIT 1",
                (new_plan_id,),
            ),
            "Edited after replan",
        )

        # 4. Re-approve the lesson set and export.
        blueprint = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        self.assertEqual(blueprint["plan"]["plan_id"], new_plan_id)
        self.assertEqual(len(blueprint["tabs"]["learner_pages"]), 4)
        approval = self.ok(
            "parent.final.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": new_plan_id,
                "plan_hash": blueprint["plan"]["plan_hash"],
                "content_hash": blueprint["content_hash"],
            },
            expected_revision=revision,
            idempotency_key="key-final-replan",
        )["result"]
        self.assertEqual(approval["state"], "active")
        exported = self.ok(
            "parent.export", {"enrollment_id": enrollment_id}, idempotency_key="key-export-replan"
        )["result"]
        self.assertEqual(exported["content_hash"], approval["content_hash"])
        self.assertEqual(
            {item["role"] for item in exported["files"]},
            {"parent_guide", "learner_page", "answer_guide"},
        )

    def test_a_structural_add_is_not_silently_carried(self) -> None:
        """An objective the old outline never covered must be re-authored, never half-exported."""
        created = self.ok(
            "parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-add"
        )["result"]
        course_id = created["course_id"]
        enrollment_id = created["enrollment_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_parent"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            )
        )
        plan_ref = self.ok("parent.brief.get", {"course_id": course_id})["result"]["plan_job"]
        first_job = self.ok("jobs.get", {"job_id": plan_ref["job_id"]})["result"]["job"]
        first_plan_id = first_job["checkpoint"]["plan_id"]
        revision = self.approve(enrollment_id, first_plan_id, 0)
        objectives = self.rows(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (first_plan_id,)
        )
        changes = [{"objective_id": row["id"], "change": "keep"} for row in objectives]
        changes.append({"objective_id": objectives[0]["id"], "change": "add", "title": "Brand new"})
        replanned = self.ok(
            "plan.replan",
            {"enrollment_id": enrollment_id, "objective_changes": changes},
            expected_revision=revision,
            idempotency_key="key-replan-add",
        )["result"]
        new_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft' ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM gen_plan_documents WHERE plan_id = ?", (new_plan_id,)), 0,
            "an added objective has no authored section; nothing faithful can be carried",
        )
        self.approve(enrollment_id, new_plan_id, replanned["revision"])
        lesson_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": new_plan_id}}
        )["result"]["job_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.lesson.generate": parent_lesson_response(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
        )
        lesson_job = self.ok("jobs.get", {"job_id": lesson_job_id})["result"]["job"]
        self.assertEqual(lesson_job["state"], "failed")
        self.assertIn("authored document", lesson_job["error"]["message"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_lessons"), 0)


    def test_a_removal_renumbers_the_carried_sections(self) -> None:
        """Dropping one objective keeps the outline for the survivors, renumbered one per section."""
        created = self.ok(
            "parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-remove"
        )["result"]
        course_id = created["course_id"]
        enrollment_id = created["enrollment_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_parent"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            )
        )
        plan_ref = self.ok("parent.brief.get", {"course_id": course_id})["result"]["plan_job"]
        first_job = self.ok("jobs.get", {"job_id": plan_ref["job_id"]})["result"]["job"]
        first_plan_id = first_job["checkpoint"]["plan_id"]
        revision = self.approve(enrollment_id, first_plan_id, 0)
        objectives = self.rows(
            "SELECT id, ordinal FROM objectives WHERE plan_id = ? ORDER BY ordinal", (first_plan_id,)
        )
        changes = [
            (
                {"objective_id": row["id"], "change": "remove"}
                if row["ordinal"] == len(objectives)
                else {"objective_id": row["id"], "change": "keep"}
            )
            for row in objectives
        ]
        replanned = self.ok(
            "plan.replan",
            {"enrollment_id": enrollment_id, "objective_changes": changes},
            expected_revision=revision,
            idempotency_key="key-replan-remove",
        )["result"]
        new_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft' ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        sections = self.rows(
            "SELECT ordinal, objective_refs_json FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal",
            (new_plan_id,),
        )
        self.assertEqual([row["ordinal"] for row in sections], [1, 2, 3])
        self.assertEqual([json.loads(row["objective_refs_json"]) for row in sections], [[1], [2], [3]])
        self.approve(enrollment_id, new_plan_id, replanned["revision"])
        lesson_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": new_plan_id}}
        )["result"]["job_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.lesson.generate": parent_lesson_response(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
        )
        lesson_job = self.ok("jobs.get", {"job_id": lesson_job_id})["result"]["job"]
        self.assertEqual(lesson_job["state"], "completed", lesson_job.get("error"))
        self.assertEqual(lesson_job["checkpoint"]["lessons"], 3)


    def test_a_version_that_never_authored_its_own_document_carries_from_the_last_authored_one(self) -> None:
        """The live rig's shape: v3 was replanned before the fix, so only v1 has a document.

        A later replan of v3 must walk back to v1's outline, not refuse because the source version
        has no document of its own.
        """
        created = self.ok(
            "parent.brief.create", {"brief": PARENT_BRIEF}, idempotency_key="key-brief-chain"
        )["result"]
        course_id = created["course_id"]
        enrollment_id = created["enrollment_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.plan.generate": plan_from_fixture("plan_parent"),
                    "coursebook.plan.validate": validation_from_fixture(),
                }
            )
        )
        plan_ref = self.ok("parent.brief.get", {"course_id": course_id})["result"]["plan_job"]
        plan_job = self.ok("jobs.get", {"job_id": plan_ref["job_id"]})["result"]["job"]
        first_plan_id = plan_job["checkpoint"]["plan_id"]
        revision = self.approve(enrollment_id, first_plan_id, 0)
        objectives = self.rows(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (first_plan_id,)
        )
        changes = [{"objective_id": row["id"], "change": "keep"} for row in objectives]
        first_replan = self.ok(
            "plan.replan",
            {"enrollment_id": enrollment_id, "objective_changes": changes},
            expected_revision=revision,
            idempotency_key="key-chain-1",
        )["result"]
        middle_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft' ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        # Simulate a version created before this fix: approved, but with no authored outline.
        with db.transaction() as connection:
            connection.execute("DELETE FROM gen_plan_sections WHERE plan_id = ?", (middle_plan_id,))
            connection.execute("DELETE FROM gen_plan_documents WHERE plan_id = ?", (middle_plan_id,))
        middle_revision = self.approve(enrollment_id, middle_plan_id, first_replan["revision"])
        middle_objectives = self.rows(
            "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (middle_plan_id,)
        )
        second_replan = self.ok(
            "plan.replan",
            {"enrollment_id": enrollment_id,
             "objective_changes": [{"objective_id": row["id"], "change": "keep"} for row in middle_objectives]},
            expected_revision=middle_revision,
            idempotency_key="key-chain-2",
        )["result"]
        last_plan_id = str(
            self.scalar(
                "SELECT id FROM plans WHERE course_id = ? AND state = 'draft' ORDER BY version DESC LIMIT 1",
                (course_id,),
            )
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM gen_plan_documents WHERE plan_id = ?", (last_plan_id,)), 1,
            "the carry must fall back to the last version that actually has a document",
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM gen_plan_sections WHERE plan_id = ?", (last_plan_id,)), 4
        )
        self.approve(enrollment_id, last_plan_id, second_replan["revision"])
        lesson_job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": last_plan_id}}
        )["result"]["job_id"]
        self.pump(
            FakeLLM(
                {
                    "coursebook.lesson.generate": parent_lesson_response(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
        )
        lesson_job = self.ok("jobs.get", {"job_id": lesson_job_id})["result"]["job"]
        self.assertEqual(lesson_job["state"], "completed", lesson_job.get("error"))
        self.assertEqual(lesson_job["checkpoint"]["lessons"], 4)


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
