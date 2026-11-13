"""H-194: fine-tune a generated course without regenerating it.

Real SQLite database, real migrations, real `coursebook.api.dispatch`. The course under test is
authored by the real offline generation pipeline (the deterministic fake provider already used by
`test_learner_plan_flow`), not hand-inserted: generate a short course -> approve the plan ->
author its lessons -> approve the content, then fine-tune one section and the order.

Cases:
* reorder persists ordinals, leaves every generated lesson body and learner attempt untouched,
  and records a reviewable plan revision;
* a reorder that crosses a unit prerequisite backwards is refused with a typed reason and the old
  order is kept;
* `lesson.revise` writes a new immutable lesson revision and marks only that section stale;
* editing after an attempt requires the explicit evidence-consequence confirmation;
* the export gate fails closed until the exact edited bytes are approved again;
* `plan.undo` restores the previous order as one stored revision;
* `lesson.regenerate` queues one section's work with a one-section preflight, not a plan replan.
"""

from __future__ import annotations

import hashlib
import json
import unittest

from coursebook import db, domain, generation

from tests.blueprint_support import (
    unit_sections_document,
    validation_pass,
    validation_responder,
    response as blueprint_response,
)
from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    lesson_from_request,
    plan_job,
    validation_from_fixture,
)
from tests.test_learner_plan_flow import learner_course_payload, learner_plan, learner_plan_brief


class FineTuneCase(KernelCase):
    """One approved, fully authored short course, built through the real commands."""

    def authored_course(self) -> dict:
        created = self.ok("course.create", learner_course_payload(), idempotency_key="h194-create")
        course_id = created["result"]["course_id"]
        enrollment_id = self.ok(
            "enrollment.create",
            {"course_id": course_id, "learner_label": "Fine tune"},
            idempotency_key="h194-enroll",
        )["result"]["enrollment_id"]
        brief = learner_plan_brief(course_id, enrollment_id)
        job_id = self.ok(
            "jobs.create", {"kind": "plan", "brief": brief}, idempotency_key="h194-plan"
        )["result"]["job_id"]

        plan = learner_plan()
        job = plan_job(job_id=job_id)
        job["brief"] = dict(brief)
        connection = db.connect()
        try:
            generated = generation.run_plan_job(
                connection,
                job,
                FakeLLM(
                    {
                        "coursebook.plan.generate": blueprint_response(plan),
                        "coursebook.plan.validate": validation_responder(
                            blueprint_response,
                            validation_pass(),
                            model="fake-independent-validator",
                        ),
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
        finally:
            connection.close()
        plan_id = generated["plan_id"]
        book = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        self.ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": book["plan"]["plan_hash"]},
            expected_revision=0,
            idempotency_key="h194-plan-approve",
        )
        lessons_brief = {
            "stage": "lessons", "plan_id": plan_id, "enrollment_id": enrollment_id, "unit_ordinal": 1,
        }
        self.ok(
            "jobs.create", {"kind": "plan", "brief": lessons_brief}, idempotency_key="h194-lessons"
        )
        unit = plan["units"][0]
        objectives = [item for item in plan["objectives"] if int(item["unit_ref"]) == 1]
        connection = db.connect()
        try:
            generation.run_unit_sections_job(
                connection,
                {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
                FakeLLM(
                    {
                        "coursebook.unit_sections.generate": blueprint_response(
                            unit_sections_document(
                                unit=unit,
                                objectives=objectives,
                                reviews=max(0, int(unit["target_lessons"]) - len(objectives)),
                            )
                        ),
                        "coursebook.unit_sections.validate": blueprint_response(
                            validation_pass(), model="fake-independent-validator"
                        ),
                    }
                ),
                plan_id=plan_id,
                unit_ordinal=1,
                now=NOW,
            )
            generation.run_lesson_job(
                connection,
                {"job_id": None, "brief": lessons_brief},
                FakeLLM(
                    {
                        "coursebook.lesson.generate": lesson_from_request(),
                        "coursebook.lesson.validate": validation_from_fixture("validation_pass"),
                    }
                ),
                plan_id=plan_id,
                unit_ordinal=1,
                now=NOW,
                budget=generation.CostBudget(max_calls=32),
            )
        finally:
            connection.close()
        book = self.ok("parent.blueprint.read", {"course_id": course_id})["result"]
        approved = self.ok(
            "parent.final.approve",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "plan_hash": book["plan"]["plan_hash"],
                "content_hash": book["content_hash"],
            },
            expected_revision=1,
            idempotency_key="h194-final-approve",
        )
        revision = approved["result"]["revision"]
        sections = self.rows(
            "SELECT id, ordinal FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal",
            (plan_id,),
        )
        objective_ids = [
            str(row["id"])
            for row in self.rows("SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan_id,))
        ]
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "revision": revision,
            "sections": sections,
            "objective_ids": objective_ids,
            "book": book,
        }

    def plan_hash(self, plan_id: str) -> str:
        return domain.plan_hash(plan_id)


class ReorderTest(FineTuneCase):
    def test_reorder_persists_ordinals_and_leaves_lessons_and_attempts_alone(self) -> None:
        course = self.authored_course()
        lesson_pages = self.rows(
            "SELECT id, section_id, version, page_json FROM gen_lessons WHERE plan_id = ? ORDER BY section_id",
            (course["plan_id"],),
        )
        check_id = str(
            self.scalar(
                "SELECT g.check_id FROM gen_lesson_checks g JOIN gen_lessons l ON l.id = g.lesson_id"
                " WHERE l.plan_id = ? ORDER BY l.section_id LIMIT 1",
                (course["plan_id"],),
            )
        )
        # A committed learner attempt is the evidence a reorder must not rewrite.
        self.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce,"
            " answer_kind, answer_json, answer_hash, verdict, evidence_class, criteria_json,"
            " grading_provenance_json, state, created_at, committed_at)"
            " VALUES ('att_h194', ?, ?, 1, 'n1', 'text', '{}', 'h', 'pass', 'cold', '[]', '{}',"
            " 'committed', ?, ?)",
            (course["enrollment_id"], check_id, NOW.isoformat(), NOW.isoformat()),
        )
        requested = list(reversed(course["objective_ids"]))
        result = self.ok(
            "plan.edit",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "expected_plan_hash": self.plan_hash(course["plan_id"]),
                "reorder": requested,
            },
            expected_revision=course["revision"],
            idempotency_key="h194-reorder-1",
        )["result"]
        self.assertEqual(result["objective_ids"], requested)
        self.assertTrue(result["changes_need_review"])
        self.assertEqual(result["review"]["kind"], "reorder")
        self.assertIn("order", result["review"]["changed_fields"])
        stored = [
            str(row["id"])
            for row in self.rows("SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (course["plan_id"],))
        ]
        self.assertEqual(stored, requested)
        # No lesson body or revision moved, and the attempt still points at its own check.
        self.assertEqual(
            self.rows("SELECT id, section_id, version, page_json FROM gen_lessons WHERE plan_id = ? ORDER BY section_id", (course["plan_id"],)),
            lesson_pages,
        )
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM attempts")), 1)
        self.assertEqual(str(self.scalar("SELECT check_id FROM attempts WHERE id = 'att_h194'")), check_id)
        revision_rows = self.rows("SELECT * FROM plan_revisions WHERE plan_id = ?", (course["plan_id"],))
        self.assertEqual(len(revision_rows), 1)
        self.assertEqual(revision_rows[0]["state"], "needs_review")
        # The approval no longer covers the new bytes: export fails closed, not silently.
        status = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertFalse(status["export"]["ready"])
        self.assertEqual(status["export"]["blocked_reason"], "no_final_approval")
        self.assertEqual(len(status["plan_revisions"]), 1)
        exported = self.err(
            "parent.export",
            {"enrollment_id": course["enrollment_id"]},
            idempotency_key="h194-export-stale",
        )
        self.assertEqual(exported["code"], "POLICY_VIOLATION")
        self.assertEqual(exported["details"]["reason"], "no_final_approval")

    def test_reorder_that_crosses_a_unit_prerequisite_backwards_is_refused(self) -> None:
        course = self.authored_course()
        # Split the objectives across two units; that stored edge is what a reorder can break.
        # The plan already has unit 1 from the blueprint; add a second unit that requires it.
        unit_one = str(
            self.scalar("SELECT id FROM plan_units WHERE plan_id = ? AND ordinal = 1", (course["plan_id"],))
        )
        self.execute(
            "INSERT INTO plan_units (id, plan_id, ordinal, title, goal, prereq_unit_ordinals_json,"
            " target_lessons, created_at) VALUES ('u2', ?, 2, 'Two', 'go', '[1]', 1, ?)",
            (course["plan_id"], NOW.isoformat()),
        )
        ids = course["objective_ids"]
        self.execute("UPDATE objectives SET unit_id = ? WHERE id = ? AND plan_id = ?", (unit_one, ids[0], course["plan_id"]))
        for objective_id in ids[1:]:
            self.execute("UPDATE objectives SET unit_id = 'u2' WHERE id = ? AND plan_id = ?", (objective_id, course["plan_id"]))
        bad_order = [ids[1], ids[0], ids[2]]
        error = self.err(
            "plan.edit",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "expected_plan_hash": self.plan_hash(course["plan_id"]),
                "reorder": bad_order,
            },
            expected_revision=course["revision"],
            idempotency_key="h194-reorder-bad",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "prerequisite_order_conflict")
        kept = [
            str(row["id"])
            for row in self.rows("SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (course["plan_id"],))
        ]
        self.assertEqual(kept, ids)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM plan_revisions")), 0)

    def test_undo_restores_the_previous_order_as_a_revision(self) -> None:
        course = self.authored_course()
        original = list(course["objective_ids"])
        requested = list(reversed(original))
        self.ok(
            "plan.edit",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "expected_plan_hash": self.plan_hash(course["plan_id"]),
                "reorder": requested,
            },
            expected_revision=course["revision"],
            idempotency_key="h194-undo-reorder",
        )
        undone = self.ok(
            "plan.undo",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "expected_plan_hash": self.plan_hash(course["plan_id"]),
            },
            expected_revision=course["revision"] + 1,
            idempotency_key="h194-undo-1",
        )["result"]
        self.assertEqual(undone["objective_ids"], original)
        self.assertEqual(
            [str(row["id"]) for row in self.rows("SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (course["plan_id"],))],
            original,
        )
        states = {row["kind"]: row["state"] for row in self.rows("SELECT kind, state FROM plan_revisions WHERE plan_id = ?", (course["plan_id"],))}
        self.assertEqual(states["reorder"], "reverted")
        self.assertEqual(states["undo"], "needs_review")


class ReviseSectionTest(FineTuneCase):
    def test_revise_writes_one_new_revision_and_marks_only_that_section_stale(self) -> None:
        course = self.authored_course()
        section = course["sections"][0]
        before_states = {
            row["section_id"]: row["state"]
            for row in self.rows("SELECT section_id, state, version FROM gen_lessons WHERE plan_id = ?", (course["plan_id"],))
        }
        page = json.loads(
            self.scalar("SELECT page_json FROM gen_lessons WHERE section_id = ? ORDER BY version DESC LIMIT 1", (section["id"],))
        )
        # Read the current page hash from the authored surface, which is what the UI sends back.
        book = self.ok("parent.blueprint.read", {"course_id": course["course_id"]})["result"]
        revised_page = dict(page)
        revised_page["section_title"] = "A sharper first section"
        result = self.ok(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section["id"],
                "expected_page_hash": self.page_hash(section["id"]),
                "title": "A sharper first section",
                "page": {"section_title": "A sharper first section"},
            },
            expected_revision=course["revision"],
            idempotency_key="h194-revise-1",
        )["result"]
        self.assertEqual(result["lesson_state"], "needs_review")
        self.assertEqual(result["lesson_version"], 2)
        rows = self.rows(
            "SELECT id, version, state, page_json FROM gen_lessons WHERE section_id = ? ORDER BY version",
            (section["id"],),
        )
        self.assertEqual([row["version"] for row in rows], [1, 2])
        self.assertEqual(json.loads(rows[0]["page_json"]), page)
        self.assertEqual(rows[1]["state"], "needs_review")
        # Every other section keeps its exact state and version.
        for row in self.rows("SELECT section_id, state, version FROM gen_lessons WHERE plan_id = ? AND section_id != ?", (course["plan_id"], section["id"])):
            self.assertEqual(row["state"], before_states[row["section_id"]])
            self.assertEqual(row["version"], 1)
        # The blueprint shows the edited title and the review diff, and export is gated.
        review = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertEqual(len(review["lesson_revisions"]), 1)
        self.assertEqual(review["lesson_revisions"][0]["changed_fields"], ["title"])
        self.assertFalse(review["export"]["ready"])
        self.assertEqual(review["export"]["blocked_reason"], "no_final_approval")
        # Approving the exact edited bytes is still `parent.final.approve`; it is the only writer
        # that clears the review and marks the row parent-approved (never independently validated).
        book = self.ok("parent.blueprint.read", {"course_id": course["course_id"]})["result"]
        self.ok(
            "parent.final.approve",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "plan_hash": book["plan"]["plan_hash"],
                "content_hash": book["content_hash"],
            },
            expected_revision=course["revision"] + 1,
            idempotency_key="h194-revise-approve",
        )
        self.assertEqual(
            str(self.scalar("SELECT state FROM gen_lessons WHERE id = ?", (result["lesson_id"],))),
            "parent_approved",
        )
        status = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertTrue(status["export"]["ready"], status["export"])

    def test_editing_after_an_attempt_requires_the_evidence_confirmation(self) -> None:
        course = self.authored_course()
        section = course["sections"][0]
        check_id = str(
            self.scalar(
                "SELECT g.check_id FROM gen_lesson_checks g JOIN gen_lessons l ON l.id = g.lesson_id"
                " WHERE l.section_id = ? LIMIT 1",
                (section["id"],),
            )
        )
        self.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce,"
            " answer_kind, answer_json, answer_hash, verdict, evidence_class, criteria_json,"
            " grading_provenance_json, state, created_at, committed_at)"
            " VALUES ('att_confirm', ?, ?, 1, 'n2', 'text', '{}', 'h', 'pass', 'cold', '[]', '{}',"
            " 'committed', ?, ?)",
            (course["enrollment_id"], check_id, NOW.isoformat(), NOW.isoformat()),
        )
        page_hash = self.page_hash(section["id"])
        blocked = self.err(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section["id"],
                "expected_page_hash": page_hash,
                "title": "Edited after evidence",
            },
            expected_revision=course["revision"],
            idempotency_key="h194-revise-unconfirmed",
        )
        self.assertEqual(blocked["code"], "POLICY_VIOLATION")
        self.assertEqual(blocked["details"]["reason"], "evidence_consequence_confirmation_required")
        self.assertEqual(blocked["details"]["evidence_attempts"], 1)
        # Nothing was written by the refused edit.
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM lesson_revisions")), 0)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_lessons WHERE section_id = ?", (section["id"],))), 1)
        self.ok(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section["id"],
                "expected_page_hash": page_hash,
                "title": "Edited after evidence",
                "confirm_evidence_consequence": True,
            },
            expected_revision=course["revision"],
            idempotency_key="h194-revise-confirmed",
        )
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM attempts WHERE id = 'att_confirm'")), 1)
        row = self.rows("SELECT * FROM lesson_revisions")[0]
        self.assertEqual(row["evidence_attempts"], 1)
        self.assertEqual(row["confirmed_evidence_consequence"], 1)

    def page_hash(self, section_id: str) -> str:
        page = json.loads(
            self.scalar(
                "SELECT page_json FROM gen_lessons WHERE section_id = ? ORDER BY version DESC LIMIT 1",
                (section_id,),
            )
        )
        return "sha256:" + hashlib.sha256(
            json.dumps(page, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()


class RegenerateOneSectionTest(FineTuneCase):
    def test_regenerate_queues_one_section_with_a_one_section_preflight(self) -> None:
        course = self.authored_course()
        section = course["sections"][0]
        before_jobs = int(self.scalar("SELECT COUNT(*) FROM jobs"))
        before_lessons = int(self.scalar("SELECT COUNT(*) FROM gen_lessons WHERE plan_id = ?", (course["plan_id"],)))
        result = self.ok(
            "lesson.regenerate",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section["id"],
            },
            idempotency_key="h194-regenerate-1",
        )["result"]
        self.assertEqual(result["kind"], "plan")
        self.assertEqual(result["scope"]["section_count"], 1)
        self.assertEqual(result["scope"]["section_id"], section["id"])
        self.assertEqual(result["preflight"]["section_count"], 1)
        self.assertTrue(result["preflight"]["fits_minimum"], result["preflight"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs")), before_jobs + 1)
        job_brief = json.loads(self.scalar("SELECT brief_json FROM jobs WHERE id = ?", (result["job_id"],)))
        self.assertEqual(job_brief["section_id"], section["id"])
        self.assertTrue(job_brief["regenerate"])
        self.assertEqual(
            job_brief["stage"], "lessons",
            "a section regeneration is a lessons job, never a plan-wide replan",
        )
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM gen_lessons WHERE plan_id = ?", (course["plan_id"],))), before_lessons)

    def test_regenerate_is_idempotent_per_key_and_payload(self) -> None:
        course = self.authored_course()
        payload = {
            "enrollment_id": course["enrollment_id"],
            "plan_id": course["plan_id"],
            "section_id": course["sections"][0]["id"],
        }
        first = self.ok("lesson.regenerate", payload, idempotency_key="h194-regenerate-idem")["result"]
        second = self.ok("lesson.regenerate", payload, idempotency_key="h194-regenerate-idem")["result"]
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM jobs")), 3)  # plan + lessons + one


class BlueprintSectionIdentityTest(FineTuneCase):
    """H-194b: the blueprint read serves the section fence, so the desktop can fine-tune.

    ``lesson.revise`` fences on ``expected_page_hash`` and ``lesson.regenerate`` on ``section_id``.
    Before v20 neither value was readable for a section that had never been revised, so the first
    fine-tune of any section was unreachable from the desktop. These cases read the values off the
    wire and hand them straight back to the commands — no test helper recomputes a digest, because
    a helper recomputing one would re-hide exactly the defect this card closes.
    """

    FIELDS = {
        "section_id",
        "objective_id",
        "ordinal",
        "title",
        "lesson_state",
        "lesson_version",
        "page_hash",
    }

    def blueprint(self, course_id: str) -> dict:
        return self.ok("parent.blueprint.read", {"course_id": course_id})["result"]

    def test_one_row_per_composed_section_in_ordinal_order(self) -> None:
        course = self.authored_course()
        rows = self.rows(
            "SELECT id, ordinal FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal",
            (course["plan_id"],),
        )
        served = self.blueprint(course["course_id"])["sections"]
        self.assertEqual(len(served), len(rows))
        self.assertEqual([entry["section_id"] for entry in served], [str(row["id"]) for row in rows])
        self.assertEqual([entry["ordinal"] for entry in served], [int(row["ordinal"]) for row in rows])
        for entry in served:
            self.assertEqual(set(entry), self.FIELDS, "the row is closed: exactly the seven keys")
            self.assertIn(entry["objective_id"], course["objective_ids"])
            self.assertEqual(entry["lesson_state"], "validated")
            self.assertEqual(entry["lesson_version"], 1)
            self.assertRegex(str(entry["page_hash"]), r"^sha256:[0-9a-f]{64}$")
            self.assertTrue(str(entry["title"]))

    def test_the_served_digest_is_accepted_by_lesson_revise_unchanged(self) -> None:
        course = self.authored_course()
        target = self.blueprint(course["course_id"])["sections"][1]
        result = self.ok(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": target["section_id"],
                "expected_page_hash": target["page_hash"],
                "title": "Retitled from the served identity",
                "page": {"section_title": "Retitled from the served identity"},
            },
            expected_revision=course["revision"],
            idempotency_key="h194b-revise",
        )["result"]
        self.assertEqual(result["lesson_state"], "needs_review")
        self.assertEqual(result["lesson_version"], 2)
        # The read follows the revision: the next call fences on the new digest, not the old one.
        after = next(
            entry
            for entry in self.blueprint(course["course_id"])["sections"]
            if entry["section_id"] == target["section_id"]
        )
        self.assertEqual(after["lesson_version"], 2)
        self.assertEqual(after["lesson_state"], "needs_review")
        self.assertEqual(after["page_hash"], result["page_hash"])
        self.assertNotEqual(after["page_hash"], target["page_hash"])
        self.assertEqual(after["title"], "Retitled from the served identity")

    def test_regenerate_takes_the_served_section_id(self) -> None:
        course = self.authored_course()
        target = self.blueprint(course["course_id"])["sections"][2]
        result = self.ok(
            "lesson.regenerate",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": target["section_id"],
            },
            idempotency_key="h194b-regenerate",
        )["result"]
        self.assertEqual(result["scope"]["section_id"], target["section_id"])
        self.assertEqual(result["scope"]["objective_id"], target["objective_id"])
        self.assertEqual(result["scope"]["section_count"], 1)

    def test_an_unauthored_section_is_served_as_nulls_not_omitted(self) -> None:
        course = self.authored_course()
        target = self.blueprint(course["course_id"])["sections"][0]
        # Model "the plan has this section but no lesson row yet", the state in which
        # `lesson.revise` refuses the section and `lesson.regenerate` is the way to author it.
        with db.transaction() as connection:
            connection.execute(
                "DELETE FROM gen_lessons WHERE section_id = ?", (target["section_id"],)
            )
        unauthored = next(
            entry
            for entry in self.blueprint(course["course_id"])["sections"]
            if entry["section_id"] == target["section_id"]
        )
        self.assertEqual(unauthored["lesson_state"], None)
        self.assertEqual(unauthored["lesson_version"], None)
        self.assertEqual(unauthored["page_hash"], None)
        self.assertEqual(set(unauthored), self.FIELDS)

    def test_a_course_with_no_composed_sections_answers_an_empty_array(self) -> None:
        # The key is required, so a course whose plan currently composes no sections answers []
        # rather than omitting it. A re-plan that has not produced its sections yet is exactly
        # this state; `gen_plan_sections` is the table `authoring.sections()` walks.
        course = self.authored_course()
        with db.transaction() as connection:
            connection.execute(
                "DELETE FROM gen_plan_sections WHERE plan_id = ?", (course["plan_id"],)
            )
        book = self.blueprint(course["course_id"])
        self.assertIn("sections", book, "a required response key is never omitted")
        self.assertEqual(book["sections"], [])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM gen_plan_sections WHERE plan_id = ?", (course["plan_id"],))),
            0,
        )


class ExportedPageRevisionTest(FineTuneCase):
    """H-194e: a page-title revision stays exportable, and one gate answers for both surfaces.

    Measured on the real store: after ``lesson.revise`` stored a section's page-title revision and
    ``parent.final.approve`` returned active, the review surface answered ``ready`` while
    ``parent.export`` refused ``no_generated_content`` ("section ... has no check"). The cause was
    two-fold: the new ``gen_lessons`` row was written with no ``gen_lesson_checks`` binding, and
    ``parent_export_status`` never ran the check-level gate the export runs.
    """

    def latest_page(self, section_id: str) -> dict:
        return json.loads(
            str(
                self.scalar(
                    "SELECT page_json FROM gen_lessons WHERE section_id = ? ORDER BY version DESC LIMIT 1",
                    (section_id,),
                )
            )
        )

    def section_identity(self, course_id: str, section_id: str) -> dict:
        return next(
            entry
            for entry in self.ok("parent.blueprint.read", {"course_id": course_id})["result"]["sections"]
            if entry["section_id"] == section_id
        )

    def revise_title(self, course: dict, section_id: str, title: str, *, revision: int | None = None) -> dict:
        target = self.section_identity(course["course_id"], section_id)
        return self.ok(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section_id,
                "expected_page_hash": target["page_hash"],
                "title": title,
                "page": {"section_title": title},
            },
            expected_revision=course["revision"] if revision is None else revision,
            idempotency_key=(
                f"h194e-revise-{section_id}-"
                f"{hashlib.sha1(title.encode('utf-8')).hexdigest()[:12]}"
            ),
        )["result"]

    def approve_content(self, course: dict, revision: int) -> dict:
        book = self.ok("parent.blueprint.read", {"course_id": course["course_id"]})["result"]
        return self.ok(
            "parent.final.approve",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "plan_hash": book["plan"]["plan_hash"],
                "content_hash": book["content_hash"],
            },
            expected_revision=revision,
            idempotency_key=f"h194e-approve-{revision}",
        )["result"]

    def test_a_page_title_revision_keeps_its_check_and_exports_after_approval(self) -> None:
        course = self.authored_course()
        section_id = str(course["sections"][0]["id"])
        original_check = str(
            self.scalar(
                "SELECT g.check_id FROM gen_lesson_checks g JOIN gen_lessons l ON l.id = g.lesson_id"
                " WHERE l.section_id = ? ORDER BY l.version DESC LIMIT 1",
                (section_id,),
            )
        )
        revised = self.revise_title(course, section_id, "A corrected section title")
        # The check binding follows the revision; the check row itself is not duplicated.
        self.assertEqual(
            [
                (str(row["check_id"]), int(row["objective_ref"]))
                for row in self.rows(
                    "SELECT check_id, objective_ref FROM gen_lesson_checks WHERE lesson_id = ?",
                    (revised["lesson_id"],),
                )
            ],
            [(original_check, 1)],
        )
        # Pre-approval both surfaces name the same blocker.
        review = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertEqual(review["export"], {"ready": False, "blocked_reason": "no_final_approval"})
        refusal = self.err(
            "parent.export", {"enrollment_id": course["enrollment_id"]},
            idempotency_key="h194e-export-preapproval",
        )
        self.assertEqual(refusal["details"]["reason"], "no_final_approval")
        # Approving the exact new bytes clears both, and the export really writes the pack.
        approval = self.approve_content(course, course["revision"] + 1)
        self.assertEqual(approval["state"], "active")
        review = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertEqual(review["export"], {"ready": True, "blocked_reason": None})
        exported = self.ok(
            "parent.export", {"enrollment_id": course["enrollment_id"]},
            idempotency_key="h194e-export-after-approval",
        )["result"]
        self.assertEqual(exported["content_hash"], approval["content_hash"])
        roles = {item["role"] for item in exported["files"]}
        self.assertEqual(roles, {"parent_guide", "learner_page", "answer_guide"})
        self.assertEqual(
            str(self.scalar("SELECT state FROM gen_lessons WHERE id = ?", (revised["lesson_id"],))),
            "parent_approved",
        )

    def test_the_review_gate_and_parent_export_share_one_gate_order(self) -> None:
        course = self.authored_course()
        section_id = str(course["sections"][0]["id"])
        revised = self.revise_title(course, section_id, "A title before the check is lost")
        # A generated page whose section binds no check: the state the H-194 live pass produced
        # before the revise fix. Both surfaces must name it, and name it before the approval gap.
        self.execute("DELETE FROM gen_lesson_checks WHERE lesson_id = ?", (revised["lesson_id"],))
        review = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertEqual(
            review["export"], {"ready": False, "blocked_reason": "no_generated_content"}
        )
        refusal = self.err(
            "parent.export", {"enrollment_id": course["enrollment_id"]},
            idempotency_key="h194e-export-checkless",
        )
        self.assertEqual(refusal["code"], "POLICY_VIOLATION")
        self.assertEqual(refusal["details"]["reason"], "no_generated_content")
        self.assertTrue(
            any("has no check" in problem for problem in refusal["details"]["problems"]),
            refusal["details"],
        )
        # Approval cannot repair it, so it is not offered as the next step.
        self.approve_content(course, course["revision"] + 1)
        status = self.ok("parent.review.read", {"course_id": course["course_id"]})["result"]
        self.assertEqual(
            status["export"], {"ready": False, "blocked_reason": "no_generated_content"}
        )
        refused_again = self.err(
            "parent.export", {"enrollment_id": course["enrollment_id"]},
            idempotency_key="h194e-export-checkless-approved",
        )
        self.assertEqual(refused_again["details"]["reason"], "no_generated_content")

    def test_a_pre_fix_checkless_revision_heals_on_its_next_revision(self) -> None:
        # The live H-194d store carries revisions written before this fix: a v2 lesson with no
        # `gen_lesson_checks` row. Editing it again must restore the section's check, not copy an
        # empty binding set and leave the section permanently unexportable.
        course = self.authored_course()
        section_id = str(course["sections"][0]["id"])
        original_check = str(
            self.scalar(
                "SELECT check_id FROM gen_lesson_checks WHERE lesson_id = ("
                " SELECT id FROM gen_lessons WHERE section_id = ? ORDER BY version DESC LIMIT 1)",
                (section_id,),
            )
        )
        revised = self.revise_title(course, section_id, "A title written before the fix")
        self.execute("DELETE FROM gen_lesson_checks WHERE lesson_id = ?", (revised["lesson_id"],))
        healed = self.revise_title(
            course, section_id, "A title written after the fix", revision=course["revision"] + 1
        )
        self.assertEqual(
            [
                str(row["check_id"])
                for row in self.rows(
                    "SELECT check_id FROM gen_lesson_checks WHERE lesson_id = ?",
                    (healed["lesson_id"],),
                )
            ],
            [original_check],
        )

    def test_a_page_revision_cannot_silently_rewrite_the_check(self) -> None:
        course = self.authored_course()
        section_id = str(course["sections"][0]["id"])
        target = self.section_identity(course["course_id"], section_id)
        page = self.latest_page(section_id)
        page["check"]["stimulus"]["prompt"] = "A question the stored reference answer cannot grade"
        refusal = self.err(
            "lesson.revise",
            {
                "enrollment_id": course["enrollment_id"],
                "plan_id": course["plan_id"],
                "section_id": section_id,
                "expected_page_hash": target["page_hash"],
                "page": {"check": page["check"]},
            },
            expected_revision=course["revision"],
            idempotency_key="h194e-revise-check",
        )
        self.assertEqual(refusal["code"], "VALIDATION_FAILED")
        self.assertEqual(refusal["details"]["reason"], "check_not_page_editable")
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM gen_lessons WHERE section_id = ?", (section_id,))),
            1,
        )
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM lesson_revisions")), 0)


if __name__ == "__main__":
    unittest.main()
