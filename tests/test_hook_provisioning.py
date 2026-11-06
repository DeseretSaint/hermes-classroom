"""Provisioning seam: lifecycle hooks never create storage; ``health.get`` does (CB-014-R1).

The measured defect this pins down, in a fresh ``HERMES_HOME`` on the build before the fix:

1. ``import coursebook.hooks`` created ``<home>/plugin-data/coursebook/`` — the module-level
   startup reconciliation asked ``db.applied_schema_version()`` for the version, which resolved the
   path through ``plugin_data_dir()``, which ``mkdir``s on every call.
2. ``turn.reconcile_binding()`` opened a transaction, which *created* an empty ``data.db`` with no
   tables, and then failed on ``no such table: bindings``.
3. ``pre_llm_call`` failed closed on that error, so a freshly installed profile blocked **every**
   chat turn, forever, on a store it had just made.
4. ``health.get`` did not migrate, so removing the accidental hook provisioner without naming a
   real one would leave the pane permanently ``Degraded`` with no route to ``course.create``.

The rules these tests hold (frozen in card ``t_f76d6e1a``):

* R1 — a chat turn is not Coursebook use: no lifecycle path creates the directory, the file or a
  migration.
* R2 — absent is not unreadable: an absent store means "not governed" (``None``); a store that
  exists and cannot be read still fails closed (``{"action": "block", ...}``).
* R3 — reads are non-creating; ``health.get`` is the provisioning seam (R4).

Everything runs against real SQLite, real host imports and real hook functions. ``T2`` runs the
import in a child interpreter because the import side effect can only be observed once per process.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from coursebook import api, db, hooks
from tests.kernel_support import KernelCase, numeric_spec, request

ROOT = Path(__file__).resolve().parent.parent
_STORED = "stored-provisioning-1"


def _plugin_data(home: Path) -> Path:
    return home / "plugin-data"


def _db_file(home: Path) -> Path:
    return _plugin_data(home) / "coursebook" / "data.db"


class FreshHomeCase(unittest.TestCase):
    """A throwaway ``HERMES_HOME`` with **nothing provisioned and nothing migrated**."""

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="coursebook-fresh-"))
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

    def assert_nothing_provisioned(self, context: str = "") -> None:
        self.assertFalse(
            _plugin_data(self.home).exists(),
            f"plugin storage was created {context}".strip(),
        )
        self.assertFalse(_db_file(self.home).exists(), f"the database file was created {context}".strip())


class AbsentStoreIsNotGoverned(FreshHomeCase):
    """T1, T2, T3, T7 — nothing a lifecycle path touches may provision the store."""

    def test_t1_unbound_pre_llm_call_returns_none_and_creates_nothing(self) -> None:
        result = hooks.pre_llm_call(
            session_id="stored-session-never-bound",
            user_message="hello, are you there?",
            is_first_turn=True,
        )
        self.assertIsNone(result, "an absent store must be ungoverned, not failed closed")
        self.assert_nothing_provisioned("by an unbound pre_llm_call")

    def test_t2_importing_hooks_creates_no_plugin_data(self) -> None:
        env = dict(os.environ)
        env["HERMES_HOME"] = str(self.home)
        completed = subprocess.run(
            [sys.executable, "-c", "import coursebook.hooks"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assert_nothing_provisioned("by importing coursebook.hooks in a fresh home")

    def test_t3_applied_schema_version_creates_neither_directory_nor_file(self) -> None:
        self.assertIsNone(db.applied_schema_version())
        self.assertFalse(db.store_exists())
        # The health snapshot is a pure read too: only the handler provisions (R4).
        self.assertEqual(db.health(), {"ready": False, "schema_version": None})
        self.assert_nothing_provisioned("by applied_schema_version()/health()")

    def test_t3b_a_missing_file_in_an_existing_directory_opens_no_connection(self) -> None:
        """The directory may exist for other reasons; a read must still not mint an empty db."""
        (_plugin_data(self.home) / "coursebook").mkdir(parents=True)
        self.assertIsNone(db.applied_schema_version())
        self.assertFalse(_db_file(self.home).exists(), "a read created an empty database file")

    def test_t7_post_callbacks_create_nothing(self) -> None:
        hooks.post_llm_call(
            session_id="stored-session-never-bound",
            user_message="hello",
            assistant_response="hi there",
        )
        hooks.post_tool_call(
            tool_name="terminal",
            task_id="20261106_000000_aaaaaa",
            duration_ms=11,
            session_id="stored-session-never-bound",
        )
        self.assert_nothing_provisioned("by post_llm_call/post_tool_call")


class HealthGetProvisions(FreshHomeCase):
    """T4 — the pane's first contact is the first use, and it provisions (R4)."""

    def test_t4_health_get_provisions_the_store(self) -> None:
        response = api.dispatch(request("health.get"))
        self.assertTrue(response["ok"], response.get("error"))
        block = response["result"]["db"]
        self.assertTrue(block["ready"], block)
        self.assertEqual(block["schema_version"], db.target_schema_version())
        self.assertTrue(_db_file(self.home).is_file(), "health.get did not create the database")
        self.assertEqual(db.applied_schema_version(), db.target_schema_version())

    def test_health_get_is_idempotent_and_still_honest(self) -> None:
        first = api.dispatch(request("health.get"))["result"]["db"]
        second = api.dispatch(request("health.get"))["result"]["db"]
        self.assertEqual(first, second)
        self.assertTrue(second["ready"])


class UnreadableStoreFailsClosed(FreshHomeCase):
    """T5 — absent and broken get different answers (R2)."""

    def test_t5_a_store_with_no_bindings_table_still_blocks(self) -> None:
        store = _plugin_data(self.home) / "coursebook"
        store.mkdir(parents=True)
        sqlite3.connect(_db_file(self.home)).close()  # a real, readable, schema-less database
        self.assertTrue(_db_file(self.home).is_file())
        self.assertIsNone(db.applied_schema_version())

        result = hooks.pre_llm_call(
            session_id="stored-session-on-a-broken-store",
            user_message="hello",
            is_first_turn=True,
        )
        self.assertIsNotNone(result, "an unreadable store must fail closed, not pass silently")
        assert result is not None  # narrowing for the type checker
        self.assertEqual(result["action"], "block")
        self.assertIn("could not read", result["message"])

    def test_t5b_a_turn_on_a_broken_store_leaves_it_broken_rather_than_half_provisioned(self) -> None:
        store = _plugin_data(self.home) / "coursebook"
        store.mkdir(parents=True)
        sqlite3.connect(_db_file(self.home)).close()
        hooks.pre_llm_call(session_id="stored-broken", user_message="hello")
        connection = sqlite3.connect(f"file:{_db_file(self.home)}?mode=ro", uri=True)
        try:
            tables = [
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            ]
        finally:
            connection.close()
        self.assertEqual(tables, [], "a failing turn migrated the store as a side effect")


class BoundChatStillGatedAndAttributed(KernelCase):
    """T6 — the write gate and the gate itself are untouched by this fix."""

    def setUp(self) -> None:
        super().setUp()
        hooks._TURNS.clear()
        hooks._GOVERNED.clear()
        self.addCleanup(hooks._TURNS.clear)
        self.addCleanup(hooks._GOVERNED.clear)

    def bind_lesson(self) -> dict:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        run_id = "run_provisioning_1"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0,"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL)",
            (run_id, lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at,"
            " lesson_run_id, objective_id) VALUES ('bnd_provisioning', ?, 'cinder', 'conn-1', 'rt-1',"
            " ?, 'sha256:cwd-1', NULL, 'active', 0, '2026-01-01T00:00:00+00:00', ?, ?)",
            (lesson["enrollment_id"], _STORED, run_id, lesson["objective_id"]),
        )
        lesson["run_id"] = run_id
        return lesson

    def test_t6_bound_chat_is_still_governed_and_writes_exactly_one_row(self) -> None:
        lesson = self.bind_lesson()

        # The gate runs: a clarification passes through ungraded, but the chat is now governed.
        self.assertIsNone(hooks.pre_llm_call(session_id=_STORED, user_message="what does this task mean?"))
        self.assertIn(_STORED, hooks._GOVERNED, "the gate did not mark the bound chat governed")

        self.assertIsNone(
            hooks.post_tool_call(
                tool_name="terminal",
                task_id="20261106_062333_4730b6",
                duration_ms=37,
                session_id=_STORED,
            )
        )
        rows = self.rows("SELECT * FROM usage_events")
        self.assertEqual(len(rows), 1, f"expected exactly one attributed row, got {rows}")
        self.assertEqual(rows[0]["enrollment_id"], lesson["enrollment_id"])
        self.assertEqual(rows[0]["provider"], "tool:terminal")
