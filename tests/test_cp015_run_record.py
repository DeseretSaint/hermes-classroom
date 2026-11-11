"""CP-015: the committed run record must be reproducible from the demo backend.

Review round 1 (sentinel) found the record was a hand-assembled mid-run snapshot: it listed
three ``plan_attempts`` for the five stored verdicts and invented a content verdict for a plan no
validation record backs, its job list began eight hours after its own ``started_at`` and stopped
before the final attempt closed, the outcome undercounted ``HOST_UNAVAILABLE`` rows (said three,
the backend has six), and it carried no per-course source or image count.

The record is therefore generated from backend rows by ``scripts/cp015_record.py``, never typed.
These tests pin the contract: every course entry carries the fields the card asks for, every job
and validation row of the window appears, the outcome's ``HOST_UNAVAILABLE`` count equals the
failed rows carrying that code, and the committed record equals a fresh read of the demo DB.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "concept-parity" / "demo" / "cp015-run.json"
EVIDENCE = ROOT / "docs" / "concept-parity" / "demo" / "cp015-live-evidence.json"
BUILDER = ROOT / "scripts" / "cp015_record.py"
DEMO_DB = Path.home() / ".hermes" / "coursebook-test-cp015" / "home" / "plugin-data" \
    / "coursebook" / "data.db"

#: What each course entry must carry: the card asks for plan status, delivered units and pages,
#: and the research/image counts. A record missing one of these is not the run record.
REQUIRED_COURSE_FIELDS = {
    "title", "course_id", "plan_approved", "units", "pages", "sources", "images",
    "job_ids", "plan_attempts",
}
REQUIRED_JOB_FIELDS = {"id", "kind", "state", "course_id", "created_at", "updated_at"}


def _load_builder():
    spec = importlib.util.spec_from_file_location("cp015_record", BUILDER)
    if spec is None or spec.loader is None:  # pragma: no cover - absent file is a test failure
        raise AssertionError(f"missing builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _course_slugs(builder) -> set[str]:
    return set(builder.course_slots().values())


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _evidence() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def _stub_snapshot() -> dict:
    """A small backend-shaped snapshot: two courses, five jobs, one stored verdict."""
    jobs = [
        {"id": f"job_{index:02d}", "kind": "plan", "state": state,
         "brief_json": json.dumps({"course_id": course}),
         "error_json": json.dumps(error),
         "created_at": f"2026-11-10T22:0{index}:00Z",
         "updated_at": f"2026-11-10T22:0{index}:30Z"}
        for index, (course, state, error) in enumerate(
            [
                ("crs_astro", "failed", {"code": "HOST_UNAVAILABLE",
                                         "details": {"purpose": "coursebook.plan.generate"}}),
                ("crs_astro", "failed", {"code": "HOST_UNAVAILABLE",
                                         "details": {"purpose": "coursebook.plan.validate"}}),
                ("crs_astro", "completed", {}),
                ("crs_bread", "failed", {"code": "VALIDATION_FAILED",
                                         "message": "request payload is 25636 bytes"}),
                ("crs_bread", "completed", {}),
            ],
            start=1,
        )
    ]
    return {
        "courses": [
            {"id": "crs_astro", "title": "Astronomy", "status": "draft",
             "created_at": "2026-11-10T21:59:00Z"},
            {"id": "crs_bread", "title": "Sourdough", "status": "draft",
             "created_at": "2026-11-10T21:59:30Z"},
        ],
        "jobs": jobs,
        "plans": [
            {"id": "plan_astro", "course_id": "crs_astro", "state": "draft",
             "created_at": "2026-11-10T22:03:30Z"},
            {"id": "plan_bread", "course_id": "crs_bread", "state": "draft",
             "created_at": "2026-11-10T22:05:30Z"},
        ],
        "validations": [
            {"id": "val_astro", "subject_id": "plan_astro", "verdict": "reject",
             "outcome": "rejected", "independence": "same_model",
             "created_at": "2026-11-10T22:03:30Z"},
            {"id": "val_bread", "subject_id": "plan_bread", "verdict": "reject",
             "outcome": "rejected", "independence": "same_model",
             "created_at": "2026-11-10T22:05:30Z"},
        ],
        "plan_documents": [],
        "plan_units": {"plan_astro": 2, "plan_bread": 1},
        "objectives": {"plan_astro": 3, "plan_bread": 2},
        "sources": {"crs_astro": 11},
        "world_assets": {},
        "worlds": {},
        "lesson_runs": {},
        "lessons": {},
        "usage_events": [],
    }


class RunRecordContractTest(unittest.TestCase):
    """The committed record must be the backend's rows, in the shape the card asks for."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = _load_builder()

    def test_every_course_entry_carries_the_required_fields(self) -> None:
        record = _record()
        slugs = _course_slugs(self.builder)
        self.assertEqual(set(record["courses"]), slugs)
        for slug, course in record["courses"].items():
            with self.subTest(slug=slug):
                missing = REQUIRED_COURSE_FIELDS - set(course)
                self.assertEqual(missing, set(), f"{slug} is missing {sorted(missing)}")
                self.assertIsInstance(course["plan_approved"], bool)
                for field in ("units", "pages", "sources", "images"):
                    self.assertIsInstance(course[field], int, f"{slug}.{field} is not an int")
                self.assertIsInstance(course["job_ids"], list)
                self.assertIsInstance(course["plan_attempts"], list)
                self.assertEqual(course["units"], 0 if not course["plan_approved"] else course["units"])

    def test_every_job_row_of_the_window_is_recorded(self) -> None:
        record = _record()
        jobs = record["jobs"]
        self.assertTrue(jobs)
        for job in jobs:
            with self.subTest(job=job.get("id")):
                missing = REQUIRED_JOB_FIELDS - set(job)
                self.assertEqual(missing, set(), f"{job.get('id')} is missing {sorted(missing)}")
        recorded = {job["id"] for job in jobs}
        per_course = {jid for course in record["courses"].values()
                      for jid in course["job_ids"]}
        self.assertEqual(per_course, recorded,
                         "a job row is attributed to no course, or a course names a missing job")
        self.assertEqual(record["counts"]["jobs"], len(recorded))

    def test_stub_backend_with_n_jobs_yields_all_n_ids(self) -> None:
        record = self.builder.build_record(
            _stub_snapshot(), base="http://stub", wire_version=25,
            authoring_model="stub-model", validator="same model")
        self.assertEqual(record["counts"]["jobs"], 5)
        self.assertEqual({job["id"] for job in record["jobs"]},
                         {"job_01", "job_02", "job_03", "job_04", "job_05"})
        per_course = {jid for course in record["courses"].values()
                      for jid in course["job_ids"]}
        self.assertEqual(per_course, {"job_01", "job_02", "job_03", "job_04", "job_05"})

    def test_host_unavailable_count_equals_the_failed_rows(self) -> None:
        record = self.builder.build_record(
            _stub_snapshot(), base="http://stub", wire_version=25,
            authoring_model="stub-model", validator="same model")
        carrying = [job for job in record["jobs"] if job["error_code"] == "HOST_UNAVAILABLE"]
        self.assertEqual(record["counts"]["host_unavailable"], len(carrying))
        self.assertEqual(record["counts"]["host_unavailable_by_purpose"],
                         {"coursebook.plan.generate": 1, "coursebook.plan.validate": 1})
        self.assertIn(f"{len(carrying)} jobs ended HOST_UNAVAILABLE", record["outcome"])

        committed = _record()
        rows = [job for job in committed["jobs"] if job["error_code"] == "HOST_UNAVAILABLE"]
        self.assertEqual(committed["counts"]["host_unavailable"], len(rows))
        self.assertIn(f"{len(rows)} jobs ended HOST_UNAVAILABLE", committed["outcome"])
        self.assertEqual(
            committed["counts"]["host_unavailable_by_purpose"],
            {"coursebook.plan.generate": 4, "coursebook.plan.validate": 2},
        )

    def test_every_stored_verdict_appears_and_none_is_invented(self) -> None:
        record = _record()
        stored = {item["plan_id"]: item for item in record["validations"]}
        attempts = {item["plan_id"]: item for item in record["plan_attempts"]}
        self.assertEqual(
            {item["id"] for item in record["validations"]},
            {item["validation_id"] for item in attempts.values() if item["validated"]},
            "a stored verdict has no attempt row, or a verdict was invented")
        for plan_id, attempt in stored.items():
            with self.subTest(plan=plan_id):
                self.assertTrue(attempts[plan_id]["validated"])
                self.assertEqual(attempts[plan_id]["validation_id"], attempt["id"])
                self.assertEqual(attempts[plan_id]["verdict"], attempt["verdict"])

    def test_a_plan_without_a_validation_record_is_marked_unvalidated(self) -> None:
        record = _record()
        unvalidated = [item for item in record["plan_attempts"] if not item["validated"]]
        self.assertTrue(unvalidated, "the record must carry the plans the validator never judged")
        for attempt in unvalidated:
            with self.subTest(plan=attempt["plan_id"]):
                self.assertIsNone(attempt["verdict"])
                self.assertIsNone(attempt["validation_id"])
                self.assertTrue(attempt["unvalidated_reason"])

    def test_window_covers_every_row_including_the_final_attempt(self) -> None:
        record = _record()
        started = self.builder.parse_ts(record["started_at"])
        finished = self.builder.parse_ts(record["finished_at"])
        stamps = []
        for job in record["jobs"]:
            stamps.append(self.builder.parse_ts(job["created_at"]))
            stamps.append(self.builder.parse_ts(job["updated_at"]))
        for item in record["validations"]:
            stamps.append(self.builder.parse_ts(item["created_at"]))
        self.assertGreaterEqual(started, min(stamps))
        self.assertLessEqual(started, min(stamps))
        self.assertEqual(finished, max(stamps))
        final = [job for job in record["jobs"]
                 if job["id"] == "job_2ffe300c67114e3f9e7fe114b542be40"]
        self.assertTrue(final, "the final sourdough attempt is absent from the record")
        self.assertIn("348f8cbb76cb5edb", {item["plan_id"] for item in record["plan_attempts"]})

    def test_live_evidence_is_the_same_row_set(self) -> None:
        record = _record()
        evidence = _evidence()
        self.assertEqual({job["id"] for job in evidence["jobs"]},
                         {job["id"] for job in record["jobs"]})
        self.assertEqual({item["id"] for item in evidence["validations"]},
                         {item["id"] for item in record["validations"]})

    @unittest.skipUnless(DEMO_DB.is_file(), "demo backend DB is not on this machine")
    def test_committed_record_reproduces_from_the_demo_db(self) -> None:
        fresh = self.builder.build_record(
            self.builder.collect(DEMO_DB),
            base="http://127.0.0.1:44501",
            wire_version=25,
            authoring_model=self.builder.authoring_model_label(),
            validator=self.builder.validator_label(),
        )
        committed = _record()
        self.assertEqual({job["id"] for job in fresh["jobs"]},
                         {job["id"] for job in committed["jobs"]})
        self.assertEqual(fresh["counts"], committed["counts"])
        self.assertEqual({slug: course["sources"] for slug, course in fresh["courses"].items()},
                         {slug: course["sources"] for slug, course in committed["courses"].items()})
        self.assertEqual({slug: course["images"] for slug, course in fresh["courses"].items()},
                         {slug: course["images"] for slug, course in committed["courses"].items()})
        self.assertEqual(fresh["started_at"], committed["started_at"])
        self.assertEqual(fresh["finished_at"], committed["finished_at"])

    def test_outcome_reports_zero_approved_courses_honestly(self) -> None:
        record = _record()
        approved = sum(1 for course in record["courses"].values() if course["plan_approved"])
        self.assertEqual(approved, 0)
        self.assertRegex(record["outcome"], rf"^{approved} of {len(record['courses'])} courses")


if __name__ == "__main__":
    unittest.main()
