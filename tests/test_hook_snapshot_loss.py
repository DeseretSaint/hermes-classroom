"""A lost teaching snapshot is recorded, not swallowed (H-114 F3).

`hooks.post_llm_call` is the only writer of a teaching segment, the durable record the Textbook and
Guided views render. Before `cb.db` v10 it wrapped that write in `except Exception: return None`, so
a failed write removed a turn from the lesson page with no marker anywhere — the chat still showed
the answer, the lesson did not. These tests drive the real hook, the real dispatcher and a real
migrated database:

* the normal path still writes exactly one segment and records no failure;
* a write that raises does **not** fail the turn (the observer is never the gate) but leaves a
  durable `hook_errors` row;
* that loss is readable by the Desktop through `binding.get` (`snapshot_failures`);
* one transient failure recovers on the immediate retry and leaves no loss row;
* even when the failure record itself cannot be written, the hook still returns None and says so
  in the log instead of raising into the host turn.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, hooks, turn

from tests.test_hook_usage_telemetry import _STORED, TelemetryCase

_NONCE = "nonce-h124-snapshot"
_LESSON_TEXT = "「ありがとう」は thank you です。もう一度言ってみましょう。"


class SnapshotLossCase(TelemetryCase):
    """A bound lesson chat with one pending, post-turn observation."""

    def bind_pending(self) -> dict:
        lesson = self.bind_lesson()
        revision = self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        )
        hooks._TURNS[_STORED] = {
            "nonce": _NONCE,
            "revision": revision,
            "verdict": None,
            "attempt_id": None,
        }
        return lesson

    def teaching_segments(self) -> list[dict]:
        return self.rows(
            "SELECT id, kind, text FROM lesson_segments WHERE kind = 'teaching' ORDER BY ordinal"
        )

    def hook_errors(self) -> list[dict]:
        return self.rows("SELECT * FROM hook_errors ORDER BY created_at")


class NormalPath(SnapshotLossCase):
    def test_a_normal_turn_still_writes_exactly_one_teaching_segment(self) -> None:
        """Regression: the recorded-loss path may not change the healthy path's shape."""
        self.bind_pending()

        self.assertIsNone(
            hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)
        )

        segments = self.teaching_segments()
        self.assertEqual(len(segments), 1, "a normal teaching turn must write exactly one segment")
        self.assertEqual(segments[0]["text"], _LESSON_TEXT)
        self.assertEqual(self.hook_errors(), [], "a healthy write recorded a failure")

    def test_the_healthy_path_reports_zero_losses_to_the_pane(self) -> None:
        lesson = self.bind_pending()
        hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)

        binding = self.ok("binding.get", {"session_id": _STORED})["result"]["binding"]
        self.assertEqual(binding["lesson_run_id"], lesson["run_id"])
        self.assertEqual(binding["snapshot_failures"]["recorded"], 0)
        self.assertIsNone(binding["snapshot_failures"]["last_at"])


class FailedWrite(SnapshotLossCase):
    def test_a_failed_write_does_not_fail_the_turn(self) -> None:
        """The hook is never the gate: a snapshot failure returns None and raises nothing."""
        self.bind_pending()

        with mock.patch.object(
            turn, "record_assistant_snapshot", side_effect=RuntimeError("disk I/O error")
        ):
            with self.assertLogs("coursebook", level="WARNING") as logs:
                self.assertIsNone(
                    hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)
                )

        self.assertEqual(self.teaching_segments(), [], "the failed write stored a segment anyway")
        self.assertTrue(
            any("snapshot" in line.lower() for line in logs.output),
            f"no structured warning named the lost snapshot: {logs.output}",
        )

    def test_the_loss_is_durable_and_attributed_to_the_run(self) -> None:
        lesson = self.bind_pending()

        with mock.patch.object(
            turn, "record_assistant_snapshot", side_effect=RuntimeError("disk I/O error")
        ):
            hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)

        errors = self.hook_errors()
        self.assertEqual(len(errors), 1, "the lost snapshot left no durable record")
        row = errors[0]
        self.assertEqual(row["kind"], "snapshot_write_failed")
        self.assertEqual(row["session_id"], _STORED)
        self.assertEqual(row["lesson_run_id"], lesson["run_id"])
        self.assertEqual(row["nonce"], _NONCE)
        self.assertEqual(row["attempts"], 2, "the hook did not retry exactly once before giving up")
        self.assertIn("disk I/O error", row["detail"])
        self.assertTrue(row["created_at"])

    def test_the_pane_read_detects_the_loss_after_the_fact(self) -> None:
        """Acceptance: a read the Desktop already makes must surface the lost snapshot."""
        lesson = self.bind_pending()

        with mock.patch.object(
            turn, "record_assistant_snapshot", side_effect=RuntimeError("disk I/O error")
        ):
            hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)

        binding = self.ok("binding.get", {"session_id": _STORED})["result"]["binding"]
        self.assertEqual(binding["lesson_run_id"], lesson["run_id"])
        self.assertEqual(binding["snapshot_failures"]["recorded"], 1)
        self.assertTrue(binding["snapshot_failures"]["last_at"])

    def test_a_failure_record_that_cannot_be_written_still_returns_none(self) -> None:
        """The log is the last resort; it must not become a second exception into the host."""
        self.bind_pending()

        with mock.patch.object(
            turn, "record_assistant_snapshot", side_effect=RuntimeError("disk I/O error")
        ), mock.patch.object(
            turn, "record_snapshot_failure", side_effect=RuntimeError("store is read-only")
        ):
            with self.assertLogs("coursebook", level="ERROR") as logs:
                self.assertIsNone(
                    hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)
                )

        self.assertEqual(self.hook_errors(), [])
        self.assertTrue(
            any("could not be written" in line for line in logs.output),
            f"the log did not state that the failure record itself was lost: {logs.output}",
        )


class RetryRecovery(SnapshotLossCase):
    def test_one_transient_failure_recovers_without_a_loss_row(self) -> None:
        """A retry that succeeds is not a loss: nothing is recorded and the segment exists."""
        self.bind_pending()
        real = turn.record_assistant_snapshot
        calls: list[int] = []

        def flaky(**kwargs):
            if not calls:
                calls.append(1)
                raise RuntimeError("database is locked")
            return real(**kwargs)

        with mock.patch.object(turn, "record_assistant_snapshot", side_effect=flaky):
            self.assertIsNone(
                hooks.post_llm_call(session_id=_STORED, assistant_response=_LESSON_TEXT)
            )

        self.assertEqual(len(self.teaching_segments()), 1, "the retry did not write the segment")
        self.assertEqual(self.hook_errors(), [], "a recovered write was reported as a loss")


class V9ToV10Upgrade(unittest.TestCase):
    """An installed profile was at v9; v10 must be an in-place upgrade, not a rebuild."""

    def test_an_existing_v9_database_upgrades_without_losing_rows(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="coursebook-upgrade-"))
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(home)
        self.addCleanup(shutil.rmtree, home, True)
        self.addCleanup(
            lambda: os.environ.__setitem__("HERMES_HOME", previous)
            if previous is not None
            else os.environ.pop("HERMES_HOME", None)
        )
        path = home / "plugin-data" / "coursebook" / "data.db"
        path.parent.mkdir(parents=True)
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER NOT NULL PRIMARY KEY,"
                " checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            for migration in db.migration_files():
                version = db.migration_version(migration)
                if version > 9:
                    continue
                for statement in db._statements(migration.read_text(encoding="utf-8")):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES (?, ?, ?)",
                    (version, db.file_checksum(migration), db.utcnow()),
                )
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, dials_json, status, revision,"
                " created_at, updated_at) VALUES ('crs_h124upgrade', 'Kept', 'committed', 'g',"
                " '{}', 'draft', 0, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(db.applied_schema_version(), 9)
        self.assertEqual(db.migrate(), 10)
        self.assertEqual(db.applied_schema_version(), 10)
        with db.read() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT title FROM courses WHERE id = 'crs_h124upgrade'"
                ).fetchone()["title"],
                "Kept",
            )
            self.assertIsNotNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'hook_errors'"
                ).fetchone()
            )


if __name__ == "__main__":
    unittest.main()
