"""Tool telemetry is attributed to an enrollment, or it is not written (CB-014).

The gateway-hosted root-profile copy of the plugin used to record a ``usage_events`` row for
*every* tool call in *every* agent session, with ``enrollment_id`` NULL: 48 unattributed rows
appeared in the operator's own ``~/.hermes/plugin-data/coursebook/data.db`` while all content
tables stayed empty. ``usage_events.enrollment_id`` exists to attribute a row to an enrollment, so
an unattributed row is not a degraded row — it is noise in a store the session does not belong to.

These tests drive the real hooks, the real dispatcher and a real migrated SQLite database. What
they pin down:

* an unbound chat writes **zero** rows and never opens (or creates) a database;
* a bound lesson chat writes exactly one row, attributed to its enrollment;
* a chat detached after the gate decided stops being recorded immediately;
* under the single-home flag the row lands in the launch home and the escaped (root-profile)
  scope is not touched at all.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, hooks
from tests.kernel_support import KernelCase, numeric_spec

try:  # present when the agent is importable, which is how the gateway runs
    import hermes_constants  # noqa: F401

    HAVE_HOST = True
except Exception:  # pragma: no cover - a bare checkout without the agent on sys.path
    HAVE_HOST = False

_STORED = "stored-telemetry-1"


def _count(home: Path) -> int:
    """``usage_events`` rows in the database under ``home`` (0 when the file does not exist)."""
    path = home / "plugin-data" / "coursebook" / "data.db"
    if not path.is_file():
        return 0
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0])
    finally:
        connection.close()


class TelemetryCase(KernelCase):
    """A migrated database and a real bound lesson chat for one stored session id."""

    def setUp(self) -> None:
        super().setUp()
        hooks._TURNS.clear()
        hooks._GOVERNED.clear()
        self.addCleanup(hooks._TURNS.clear)
        self.addCleanup(hooks._GOVERNED.clear)

    def bind_lesson(self, spec: dict | None = None) -> dict:
        lesson = self.prepare_lesson(spec or numeric_spec("42.7"))
        run_id = "run_telemetry_1"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0,"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL)",
            (run_id, lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at,"
            " lesson_run_id, objective_id) VALUES ('bnd_telemetry', ?, 'cinder', 'conn-1', 'rt-1', ?,"
            " 'sha256:cwd-1', NULL, 'active', 0, '2026-01-01T00:00:00+00:00', ?, ?)",
            (lesson["enrollment_id"], _STORED, run_id, lesson["objective_id"]),
        )
        lesson["run_id"] = run_id
        return lesson

    def usage_rows(self) -> list[dict]:
        return self.rows("SELECT * FROM usage_events ORDER BY recorded_at")


class UnboundSessionsWriteNothing(unittest.TestCase):
    """The defect itself: a chat with no binding must not write telemetry anywhere."""

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="coursebook-telemetry-"))
        self._previous_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(self.home)
        hooks._TURNS.clear()
        hooks._GOVERNED.clear()
        self.addCleanup(hooks._TURNS.clear)
        self.addCleanup(hooks._GOVERNED.clear)

    def tearDown(self) -> None:
        if self._previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._previous_home
        shutil.rmtree(self.home, ignore_errors=True)

    def test_unbound_tool_call_writes_zero_rows_and_creates_no_database(self) -> None:
        """A gateway session that is not a lesson must not even open the plugin store."""
        for tool in ("terminal", "skill_view", "read_file"):
            hooks.post_tool_call(
                tool_name=tool,
                task_id="20261106_062333_4730b6",
                duration_ms=12,
                session_id="agent-session-with-no-binding",
            )
        self.assertFalse(
            (self.home / "plugin-data").exists(),
            "an unbound tool call created plugin storage",
        )
        self.assertEqual(_count(self.home), 0)

    def test_a_task_id_alone_never_attributes_a_usage_row(self) -> None:
        """``task_id`` is a correlation id, not an identity: it cannot stand in for a binding."""
        hooks.post_tool_call(tool_name="terminal", task_id="20261106_055011_00373f")
        self.assertEqual(_count(self.home), 0)

    def test_an_unmigrated_store_is_still_not_created_by_telemetry(self) -> None:
        """Even after the gate ran for other chats, an unbound call writes nothing."""
        hooks._GOVERNED["some-other-session"] = {"binding_id": "bnd_other"}
        hooks.post_tool_call(tool_name="terminal", session_id="agent-session-with-no-binding")
        self.assertFalse((self.home / "plugin-data").exists())


class BoundSessionsAttributeTelemetry(TelemetryCase):
    def test_a_bound_lesson_tool_call_writes_one_attributed_row(self) -> None:
        lesson = self.bind_lesson()
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        self.assertIn(_STORED, hooks._GOVERNED, "the gate did not mark the bound chat governed")

        hooks.post_tool_call(
            tool_name="terminal",
            task_id="20261106_062333_4730b6",
            duration_ms=37,
            session_id=_STORED,
        )

        rows = self.usage_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["enrollment_id"], lesson["enrollment_id"])
        self.assertEqual(row["provider"], "tool:terminal")
        self.assertEqual(row["operation_id"], "20261106_062333_4730b6")
        self.assertEqual(row["duration_ms"], 37)
        self.assertEqual(row["artifact_count"], 0)
        self.assertEqual(row["tokens_json"], "{}")

    def test_each_tool_call_is_its_own_row(self) -> None:
        self.bind_lesson()
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        for tool in ("terminal", "read_file"):
            hooks.post_tool_call(tool_name=tool, session_id=_STORED)
        self.assertEqual(len(self.usage_rows()), 2)

    def test_a_chat_detached_after_the_gate_stops_being_recorded(self) -> None:
        """The binding row is re-checked inside the fence; a stale decision cannot write."""
        self.bind_lesson()
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        self.execute("UPDATE bindings SET status = 'detached' WHERE stored_session_id = ?", (_STORED,))

        hooks.post_tool_call(tool_name="terminal", session_id=_STORED)

        self.assertEqual(self.usage_rows(), [])
        self.assertNotIn(_STORED, hooks._GOVERNED, "a detached chat stayed in the governed set")

    def test_a_cwd_change_on_the_next_turn_forgets_governance(self) -> None:
        self.bind_lesson()
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        self.assertIn(_STORED, hooks._GOVERNED)

        # The chat now runs somewhere else: the gate detaches governance before the turn.
        hooks.pre_llm_call(
            session_id=_STORED,
            user_message="hello",
            cwd_fingerprint="sha256:different-cwd",
        )
        self.assertNotIn(_STORED, hooks._GOVERNED)
        hooks.post_tool_call(tool_name="terminal", session_id=_STORED)
        self.assertEqual(self.usage_rows(), [])

    def test_post_tool_call_never_breaks_on_a_foreign_session(self) -> None:
        self.bind_lesson()
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        self.assertIsNone(hooks.post_tool_call(tool_name="terminal", session_id="someone-else"))
        self.assertEqual(self.usage_rows(), [])

    def test_governed_set_stays_bounded(self) -> None:
        """A long-lived gateway cannot grow the in-process set without limit."""
        for index in range(hooks._MAX_GOVERNED + 10):
            hooks._remember_governed(f"session-{index}", "bnd")
        self.assertLessEqual(len(hooks._GOVERNED), hooks._MAX_GOVERNED)


@unittest.skipUnless(HAVE_HOST, "hermes_constants is not importable in this interpreter")
class TelemetryFollowsTheSingleHome(TelemetryCase):
    """Under the single-home flag the row lands where the course data lives, nowhere else."""

    def setUp(self) -> None:
        super().setUp()
        self.root = Path(tempfile.mkdtemp(prefix="coursebook-telemetry-homes-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.launch = self.root / "launch-home"
        self.escaped = self.root / "default-home"
        self.launch.mkdir()
        self.escaped.mkdir()
        patches = [
            mock.patch("hermes_constants.get_process_hermes_home", lambda: self.launch),
            mock.patch("hermes_constants.get_hermes_home", lambda: self.escaped),
            mock.patch.dict(os.environ, {db.SINGLE_HOME_FLAG: "1"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_bound_telemetry_lands_in_the_launch_home_only(self) -> None:
        self.bind_lesson()  # written through the pinned connection into the launch home
        hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?")
        hooks.post_tool_call(tool_name="terminal", session_id=_STORED)

        self.assertEqual(_count(self.launch), 1)
        self.assertFalse(
            (self.escaped / "plugin-data").exists(),
            "telemetry landed in the escaped (root-profile) home",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
