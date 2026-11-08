"""``coursebook_due``: the agent-side read of what is waiting, against a real database.

The tool must be a *view*: same profile-scoped store as the Desktop, same next step as
``library.list``, same derived review count as ``review.queue``, and no write of any kind. These
tests use the real migrations and the real commands (``tests/kernel_support.py``) so a passing
test proves the SQL and the derivation, not a stub.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import hermes_yaml as yaml

from coursebook import db, tools
from tests.kernel_support import KernelCase, numeric_spec

ROOT = Path(__file__).resolve().parent.parent


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class DueToolCase(KernelCase):
    def due(self, **args) -> dict:
        return json.loads(tools.due_handler(args or None))

    def prepare(self, *, titles: tuple[str, ...] = ("Compute",)) -> dict:
        course_id, plan_id = self.new_course(title="Learn to braise")
        objective_ids = [self.seed_objective(plan_id, numeric_spec("42.7")) for _ in titles]
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_ids": objective_ids,
            "enrollment_id": enrollment_id,
            "revision": revision,
        }

    def pass_objective(self, lesson: dict, objective_id: str, answer: str = "42.7") -> dict:
        revision = int(
            str(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)))
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        response = self.submit(
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            answer,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def backdate(self, objective_id: str, days: float = 10) -> None:
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 2",
            (_iso(days), objective_id),
        )


class OneDueCourseTest(DueToolCase):
    def test_an_overdue_review_is_the_next_step_and_carries_the_backend_count(self) -> None:
        lesson = self.prepare()
        self.pass_objective(lesson, lesson["objective_ids"][0])
        self.backdate(lesson["objective_ids"][0], days=10)
        payload = self.due()
        self.assertTrue(payload["available"])
        self.assertEqual(len(payload["due"]), 1)
        row = payload["due"][0]
        self.assertEqual(row["course_id"], lesson["course_id"])
        self.assertEqual(row["title"], "Learn to braise")
        self.assertEqual(row["next_step"]["kind"], "resolve_review_due")
        self.assertEqual(row["next_step"]["label"], "Review 1 objective(s)")
        self.assertEqual(row["due_count"], 1)
        self.assertEqual(row["section"], "Compute")
        self.assertIsInstance(row["check"], str)
        self.assertNotEqual(row["check"], "")
        # `next` is exactly the first due row, not a second derivation.
        self.assertEqual(payload["next"], row)

    def test_a_started_but_unpassed_course_reports_the_start_step_and_no_review_count(self) -> None:
        lesson = self.prepare()
        payload = self.due()
        self.assertTrue(payload["available"])
        row = payload["due"][0]
        self.assertEqual(row["next_step"]["kind"], "start_lesson")
        self.assertEqual(row["section"], "Compute")
        self.assertEqual(row["check"], "none")  # no checks row has been opened yet
        self.assertNotIn("due_count", row)  # never a fabricated zero

    def test_course_id_narrows_to_one_classroom(self) -> None:
        first = self.prepare()
        second_course, second_plan = self.new_course(title="Second classroom")
        self.seed_objective(second_plan, numeric_spec("7"))
        self.new_enrollment(second_course)
        payload = self.due(course_id=first["course_id"])
        self.assertTrue(payload["available"])
        self.assertEqual([row["course_id"] for row in payload["due"]], [first["course_id"]])


class EmptyStoreTest(DueToolCase):
    def test_a_provisioned_store_with_no_courses_is_genuinely_empty(self) -> None:
        payload = self.due()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["due"], [])
        self.assertIsNone(payload["next"])
        self.assertIn("checked_at", payload)


class UnavailableBackendTest(DueToolCase):
    def test_no_database_is_typed_not_an_empty_due_list(self) -> None:
        (db.store_root() / "data.db").unlink()
        payload = self.due()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "no_database")
        self.assertEqual(payload["due"], [])

    def test_an_unreadable_database_is_typed_not_an_empty_due_list(self) -> None:
        (db.store_root() / "data.db").write_bytes(b"this is not a sqlite database")
        payload = self.due()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "database_unavailable")
        self.assertEqual(payload["due"], [])

    def test_an_unmigrated_database_is_typed(self) -> None:
        # A real empty SQLite file with no migration table: the store exists but cannot answer.
        import sqlite3

        path = db.store_root() / "data.db"
        path.unlink()
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE unrelated (id TEXT)")
        connection.commit()
        connection.close()
        payload = self.due()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "schema_not_migrated")


class UnknownCourseTest(DueToolCase):
    def test_an_unknown_course_id_is_the_contract_error_shape(self) -> None:
        self.prepare()
        payload = self.due(course_id="course_does_not_exist")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "unknown_course")
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertEqual(payload["error"]["details"]["id"], "course_does_not_exist")
        for key in ("category", "message", "retryable"):
            self.assertIn(key, payload["error"])
        self.assertEqual(payload["due"], [])


class ReadOnlyTest(DueToolCase):
    def test_the_due_read_writes_nothing_and_does_not_run_the_scheduler_tick(self) -> None:
        lesson = self.prepare()
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        before_state = self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,))
        before_revision = self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )
        before_evidence = self.scalar("SELECT COUNT(*) FROM evidence")
        before_transitions = self.scalar("SELECT COUNT(*) FROM transitions")
        payload = self.due()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["due"][0]["due_count"], 1)
        # The queue is derived from evidence dates; the reading did not mark `review_due`.
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
                         before_state)
        self.assertEqual(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)),
            before_revision,
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), before_evidence)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), before_transitions)


class RegistrationTest(unittest.TestCase):
    def test_provides_tools_matches_register(self) -> None:
        from tests.test_manifest import RecordingContext, load_plugin_package

        module = load_plugin_package()
        ctx = RecordingContext()
        module.register(ctx)
        manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(ctx.tools), set(manifest.get("provides_tools") or []))
        self.assertIn(tools.DUE_TOOL_NAME, ctx.tools)
        self.assertIn(tools.STATUS_TOOL_NAME, ctx.tools)
        # The registered schema names the same tool it is registered under.
        self.assertEqual(module.tools.due_schema()["name"], tools.DUE_TOOL_NAME)

    def test_description_says_profile_scoped_local_read_only(self) -> None:
        description = tools.DUE_TOOL_DESCRIPTION.lower()
        for phrase in ("profile-scoped", "read-only", "local"):
            self.assertIn(phrase, description)


if __name__ == "__main__":
    unittest.main()
