"""UP-42: a second plan attempt deletes the first plan's stored document.

The document table was ``UNIQUE(course_id, request_fingerprint)`` — the *brief* — while every read
goes by ``plan_id``, and the writer used ``INSERT OR REPLACE``. A retried plan job for the same
brief authors a new plan *version* under a new plan id with the same fingerprint, so the replace
silently deleted the row the earlier version owned. That version was still the course's plan and,
with no document left, it read as *manually authored* and approvable: the learner could approve a
plan that could never teach, because every lesson action raised ``plan … has no authored
document``. There was no recovery path.

The fix keys the document on the plan (``UNIQUE(plan_id)``) and moves the reuse lookup to a
non-unique ``(course_id, request_fingerprint, created_at)`` index read newest-first, so:

* each plan version keeps the document it was authored with, and ``plan_document`` can never be
  pointed at a row another version overwrote;
* the reuse cache still answers exactly one row per fingerprint (the newest), so a reconnect of
  the *same* job stays free — proven here with the same job id, not only the version read.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from coursebook import db, generation

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    NOW,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

#: The retry happens later than the first attempt; the reuse lookup reads newest-first, so the two
#: attempts must not share a timestamp.
AFTER = NOW + timedelta(hours=1)


class PlanDocumentVersionsTest(KernelCase):
    def author(self, course_id: str, job_id: str, now, *, reject: bool) -> dict:
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
            return generation.run_plan_job(
                connection, job, FakeLLM(script), FakeSearch(), now=now
            )
        finally:
            connection.close()

    def document_plan_ids(self) -> list[str]:
        return [
            str(row["plan_id"])
            for row in self.rows(
                "SELECT plan_id FROM gen_plan_documents ORDER BY created_at, rowid"
            )
        ]

    def document(self, plan_id: str) -> dict:
        with db.read() as connection:
            return generation.plan_document(connection, plan_id)

    def test_second_attempt_keeps_the_first_document(self) -> None:
        course_id, _placeholder = self.new_course()

        # v1 is a refused draft: the parent's first attempt. Its document is the authored artifact
        # the review surface reads.
        v1 = self.author(course_id, "job-version-1", NOW, reject=True)
        self.assertEqual(v1["validation_verdict"], "reject")
        v1_document = self.document(v1["plan_id"])

        # A retry for the same brief is a new attempt (H-182/D2): reuse is declined and a new plan
        # version is authored under a new plan id with the *same* request fingerprint. At HEAD this
        # write replaced v1's document row.
        v2 = self.author(course_id, "job-version-2", AFTER, reject=True)
        self.assertFalse(v2["reused"])
        self.assertNotEqual(v2["plan_id"], v1["plan_id"])
        self.assertEqual(v2["reuse_declined"]["previous_plan_id"], v1["plan_id"])

        # The approved v1's document is intact and is still its own. At HEAD the read raised
        # ``plan … has no authored document`` before reaching this line.
        self.assertEqual(self.document(v1["plan_id"]), v1_document)

        # Both versions keep their own document: two rows, one fingerprint.
        self.assertEqual(self.document_plan_ids(), [v1["plan_id"], v2["plan_id"]])
        self.assertEqual(
            len(
                {
                    str(row["request_fingerprint"])
                    for row in self.rows("SELECT request_fingerprint FROM gen_plan_documents")
                }
            ),
            1,
        )

        # The parent keeps v1 and owns it (the same durable decision every authoring command
        # records), then approves it through the real gate.
        connection = db.connect()
        try:
            generation.invalidate_plan_validation(
                connection, v1["plan_id"], reason="plan_edited", manual_authoring=True, now=AFTER
            )
        finally:
            connection.close()
        enrollment_id = self.new_enrollment(course_id)
        self.approve(enrollment_id, v1["plan_id"], 0)

        # …and a lessons job for the approved v1 reaches a page. At HEAD this raised
        # ``plan has no authored document`` — the course's dead end.
        lessons = generation.run_lesson_job(
            db.connect(),
            {"job_id": "job-lessons-v1", "kind": "plan", "brief": {"plan_id": v1["plan_id"]}},
            FakeLLM(
                {
                    "coursebook.lesson.generate": lesson_from_request(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            ),
            now=AFTER,
            budget=generation.CostBudget(max_calls=32),
        )
        self.assertTrue(lessons["lessons"])
        self.assertTrue(
            any(item["state"] == "validated" for item in lessons["lessons"]),
            f"no validated page for the approved v1: {lessons['lessons']}",
        )

        # The reuse cache still finds exactly one row per fingerprint — the newest attempt. A
        # reconnect of the second job is free, answers v2, and writes no third row.
        replay = self.author(course_id, "job-version-2", AFTER, reject=True)
        self.assertTrue(replay["reused"])
        self.assertEqual(replay["plan_id"], v2["plan_id"])
        self.assertEqual(self.document_plan_ids(), [v1["plan_id"], v2["plan_id"]])


class LegacyDocumentTableRebuildTest(GenerationTestBase):
    """A database created before this change is rebuilt in place, never dropped."""

    def test_a_brief_keyed_table_gains_one_document_per_plan(self) -> None:
        legacy = sqlite3.connect(":memory:", isolation_level=None)
        legacy.row_factory = sqlite3.Row
        self.addCleanup(legacy.close)
        legacy.execute(
            "CREATE TABLE gen_plan_documents ("
            " id TEXT PRIMARY KEY,"
            " plan_id TEXT NOT NULL,"
            " course_id TEXT NOT NULL,"
            " request_fingerprint TEXT NOT NULL,"
            " plan_hash TEXT NOT NULL,"
            " document_json TEXT NOT NULL,"
            " research_json TEXT NOT NULL,"
            " generation_state TEXT NOT NULL,"
            " validation_id TEXT,"
            " result_json TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " UNIQUE(course_id, request_fingerprint))"
        )
        legacy.execute(
            "INSERT INTO gen_plan_documents VALUES "
            "('doc-legacy', 'pln-a', 'course-a', 'fingerprint-a', 'hash-a', '{}', '{}',"
            " 'needs_review', NULL, '{}', '2026-11-06T12:00:00Z')"
        )

        generation.ensure_schema(legacy)

        # The recorded document survives the rebuild (a plan document is an artifact, not a cache
        # entry), and the table is idempotent under a second ensure_schema.
        generation.ensure_schema(legacy)
        rows = [dict(row) for row in legacy.execute("SELECT * FROM gen_plan_documents")]
        self.assertEqual([row["id"] for row in rows], ["doc-legacy"])

        # The key is now the plan: a second version of the same brief keeps its own row, and a
        # second document for the same plan is refused.
        legacy.execute(
            "INSERT INTO gen_plan_documents VALUES "
            "('doc-newer', 'pln-b', 'course-a', 'fingerprint-a', 'hash-b', '{}', '{}',"
            " 'needs_review', NULL, '{}', '2026-11-06T13:00:00Z')"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            legacy.execute(
                "INSERT INTO gen_plan_documents VALUES "
                "('doc-dup', 'pln-a', 'course-a', 'fingerprint-a', 'hash-c', '{}', '{}',"
                " 'needs_review', NULL, '{}', '2026-11-06T14:00:00Z')"
            )

        # The reuse lookup keeps a non-unique index on the brief, created by the same upgrade.
        indexes = {
            str(row[1]): [str(column[2]) for column in legacy.execute(f"PRAGMA index_info({row[1]})")]
            for row in legacy.execute("PRAGMA index_list(gen_plan_documents)")
            if int(row[2]) == 0
        }
        self.assertIn(
            ["course_id", "request_fingerprint", "created_at"], list(indexes.values())
        )
