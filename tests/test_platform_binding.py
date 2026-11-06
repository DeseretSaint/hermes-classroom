"""Session binding: stored id only, explicit identifier, no recency, no fake empty answer.

The plugin cannot ship a binding kernel in this package, so these tests use a temp SQLite
connection with the frozen ``cb.db`` bindings shape. That is the seam ``coursebook/db.py``
exposes; nothing here mocks the thing under test (the dispatcher and the handler are real).
"""

from __future__ import annotations

import sqlite3
import unittest
from unittest import mock

from coursebook import api, db
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


class _ApiBindingHandlerIsolated(unittest.TestCase):
    """Pin ``binding.get`` to the platform handler while this module runs.

    ``coursebook.api.METHOD_HANDLERS`` is process-wide. Once the kernel package has been
    imported by another test module, ``coursebook.domain`` owns ``binding.get`` and reads the
    real database, which these tests deliberately replace with an in-memory copy of the frozen
    shape. Without this pin the suite result depends on module load order (CB-002 merge).
    """

    def setUp(self) -> None:
        self._saved_handlers = dict(api.METHOD_HANDLERS)
        api.METHOD_HANDLERS["binding.get"] = api._binding_get
        self.addCleanup(self._restore_handlers)

    def _restore_handlers(self) -> None:
        api.METHOD_HANDLERS.clear()
        api.METHOD_HANDLERS.update(self._saved_handlers)


class UnmigratedDatabaseTest(_ApiBindingHandlerIsolated):
    def test_binding_get_refuses_rather_than_claiming_no_binding(self) -> None:
        # No migrations -> no binding row can exist. `{binding: null}` would assert
        # "this chat is not bound", which this build cannot know.
        with mock.patch.object(db, "applied_schema_version", return_value=None):
            response = api.dispatch(request("binding.get", {"session_id": "stored_1"}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")
        self.assertFalse(response["error"]["retryable"])


class MigrationPresentTest(_ApiBindingHandlerIsolated):
    def setUp(self) -> None:
        super().setUp()
        patcher_version = mock.patch.object(db, "applied_schema_version", return_value=1)
        patcher_connect = mock.patch.object(db, "connect", side_effect=seeded_connection)
        patcher_version.start()
        patcher_connect.start()
        self.addCleanup(patcher_version.stop)
        self.addCleanup(patcher_connect.stop)

    def test_stored_id_resolves_the_binding(self) -> None:
        response = api.dispatch(request("binding.get", {"session_id": "stored_1"}))
        self.assertTrue(response["ok"], response)
        binding = response["result"]["binding"]
        self.assertEqual(binding["id"], "bnd_active")
        self.assertEqual(binding["stored_session_id"], "stored_1")
        self.assertEqual(binding["matched_column"], "stored_session_id")

    def test_runtime_id_is_not_a_substitute_for_a_stored_id(self) -> None:
        # rt_live_1 exists in runtime_session_id, but resume is stored-id-only by contract.
        response = api.dispatch(request("binding.get", {"session_id": "rt_live_1"}))
        self.assertTrue(response["ok"], response)
        self.assertIsNone(response["result"]["binding"])

    def test_enrollment_id_resolves_the_same_row(self) -> None:
        response = api.dispatch(request("binding.get", {"enrollment_id": "enr_1"}))
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["binding"]["id"], "bnd_active")
        self.assertEqual(response["result"]["binding"]["matched_column"], "enrollment_id")

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
