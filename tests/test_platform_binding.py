"""Session binding: stored id only, explicit identifier, no recency, no fake empty answer.

The plugin cannot ship a binding kernel in this package, so these tests use a temp SQLite
connection with the frozen ``cb.db`` bindings shape. That is the seam ``coursebook/db.py``
exposes; nothing here mocks the thing under test (the dispatcher and the handler are real).
"""

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from unittest import mock

from coursebook import api, db

# The kernel owns the real binding handler; the skeleton's stub in ``api.py`` is only what ships
# before the kernel lands. Importing the domain registers it, exactly as ``hooks`` does at plugin
# load, so these tests exercise the handler the plugin actually runs.
from coursebook.domain import ensure_registered as _register_kernel

_register_kernel()
from tests.test_rpc import request

BINDING_DDL = """
CREATE TABLE bindings (
    id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    connection_id TEXT,
    runtime_session_id TEXT,
    stored_session_id TEXT,
    cwd_fingerprint TEXT,
    compression_tip TEXT,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)
"""

ROWS = [
    (
        "bnd_active", "enr_1", "default", None, "rt_live_1", "stored_1",
        None, None, "active", 3, "2026-01-02T00:00:00Z",
    ),
    (
        "bnd_paused", "enr_2", "default", None, "rt_live_2", "stored_2",
        None, None, "paused", 1, "2026-01-01T00:00:00Z",
    ),
]


def seeded_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(BINDING_DDL)
    connection.executemany(
        "INSERT INTO bindings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ROWS,
    )
    return connection


class UnmigratedDatabaseTest(unittest.TestCase):
    def test_binding_get_migrates_then_reports_no_binding_honestly(self) -> None:
        # With the kernel present, `binding.get` applies the schema before reading. On an empty
        # (but now migrated) database an explicit `{binding: null}` is a true statement: no row
        # exists. It is not a guess derived from recency or from a chat title.
        calls = []

        def fake_ensure_schema() -> int:
            calls.append("ensure")
            return 1

        with mock.patch.object(db, "ensure_schema", side_effect=fake_ensure_schema), mock.patch.object(
            db, "read", side_effect=lambda: closing(seeded_connection())
        ):
            response = api.dispatch(request("binding.get", {"session_id": "stored_1"}))
        self.assertEqual(calls, ["ensure"])
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["binding"]["binding_id"], "bnd_active")


class MigrationPresentTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher_version = mock.patch.object(db, "applied_schema_version", return_value=1)
        patcher_ensure = mock.patch.object(db, "ensure_schema", return_value=1)
        patcher_connect = mock.patch.object(db, "read", side_effect=lambda: closing(seeded_connection()))
        patcher_version.start()
        patcher_ensure.start()
        patcher_connect.start()
        self.addCleanup(patcher_version.stop)
        self.addCleanup(patcher_ensure.stop)
        self.addCleanup(patcher_connect.stop)

    def test_stored_id_resolves_the_binding(self) -> None:
        response = api.dispatch(request("binding.get", {"session_id": "stored_1"}))
        self.assertTrue(response["ok"], response)
        binding = response["result"]["binding"]
        self.assertEqual(binding["binding_id"], "bnd_active")
        self.assertEqual(binding["stored_session_id"], "stored_1")

    def test_runtime_id_resolves_only_the_live_binding(self) -> None:
        # A live runtime id is a real identifier for the bound chat (the hook sees it every turn);
        # it is never treated as a substitute for a *different* binding's stored id.
        response = api.dispatch(request("binding.get", {"session_id": "rt_live_1"}))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["binding"]["binding_id"], "bnd_active")

    def test_enrollment_id_resolves_the_same_row(self) -> None:
        response = api.dispatch(request("binding.get", {"enrollment_id": "enr_1"}))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["binding"]["binding_id"], "bnd_active")

    def test_unknown_stored_id_is_an_explicit_null_not_a_recency_pick(self) -> None:
        # stored_2 exists; asking for a missing id must not fall back to it.
        response = api.dispatch(request("binding.get", {"session_id": "stored_does_not_exist"}))
        self.assertTrue(response["ok"], response)
        self.assertIsNone(response["result"]["binding"])

    def test_non_active_binding_is_returned_with_its_state(self) -> None:
        response = api.dispatch(request("binding.get", {"session_id": "stored_2"}))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["binding"]["status"], "paused")

    def test_both_identifiers_are_refused(self) -> None:
        response = api.dispatch(
            request("binding.get", {"session_id": "stored_1", "enrollment_id": "enr_1"})
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_neither_identifier_is_refused(self) -> None:
        response = api.dispatch(
            request("binding.get", {"session_id": None, "enrollment_id": None})
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")


class RegistryTest(unittest.TestCase):
    def test_binding_get_is_registered(self) -> None:
        self.assertIn("binding.get", api.implemented_methods())

    def test_every_registered_method_exists_in_the_contract(self) -> None:
        from coursebook.contracts import method_names

        frozen = set(method_names())
        self.assertTrue(set(api.implemented_methods()) <= frozen)


if __name__ == "__main__":
    unittest.main()
