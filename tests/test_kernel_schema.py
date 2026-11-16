"""The migrated database must equal the frozen inventory in ``cb.db``.

This is the contract-conformance test for the schema: every table, column, nullability, default,
foreign key, unique key and index is compared against ``contracts/db.v1.json``. A typo in the
migration, or a "helpful" extra table, fails here rather than at integration time.
"""

from __future__ import annotations

import sqlite3
import unittest
from unittest import mock

from coursebook import api, contracts, db
from coursebook.contracts import contract
from tests.kernel_support import KernelCase, request


class SchemaConformanceTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.contract = contract("cb.db")["tables"]

    def test_every_contract_table_exists_and_nothing_else_does(self) -> None:
        with db.read() as connection:
            actual = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        self.assertEqual(actual, set(self.contract), f"tables differ: extra={actual - set(self.contract)} "
                                                     f"missing={set(self.contract) - actual}")

    def test_columns_types_nullability_and_defaults_match(self) -> None:
        with db.read() as connection:
            for table, spec in self.contract.items():
                with self.subTest(table=table):
                    info = {row["name"]: row for row in connection.execute(f"PRAGMA table_info({table})")}
                    self.assertEqual(set(info), set(spec["columns"]))
                    for name, column in spec["columns"].items():
                        row = info[name]
                        self.assertEqual(row["type"].upper(), column["type"].upper(), f"{table}.{name} type")
                        self.assertEqual(
                            bool(row["notnull"]), not column.get("nullable", False),
                            f"{table}.{name} nullability",
                        )
                        self.assertEqual(bool(row["pk"]), bool(column.get("pk")), f"{table}.{name} pk")
                        expected_default = column.get("default")
                        if expected_default is None:
                            self.assertIsNone(row["dflt_value"], f"{table}.{name} default")
                        else:
                            self.assertIsNotNone(row["dflt_value"], f"{table}.{name} default missing")
                            self.assertEqual(row["dflt_value"].strip("'\""), str(expected_default),
                                             f"{table}.{name} default")

    def test_foreign_keys_match_the_contract(self) -> None:
        with db.read() as connection:
            for table, spec in self.contract.items():
                with self.subTest(table=table):
                    actual = {
                        (row["from"], row["table"])
                        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
                    }
                    expected = {
                        (name, column["ref"].split(".", 1)[0])
                        for name, column in spec["columns"].items()
                        if column.get("ref")
                    }
                    self.assertEqual(actual, expected)

    def test_unique_constraints_match_the_contract(self) -> None:
        with db.read() as connection:
            for table, spec in self.contract.items():
                with self.subTest(table=table):
                    unique = {
                        tuple(row["name"] for row in connection.execute(f"PRAGMA index_info({index['name']})"))
                        for index in connection.execute(f"PRAGMA index_list({table})")
                        if index["unique"] and index["origin"] == "u"
                    }
                    expected = {tuple(columns) for columns in spec.get("unique", [])}
                    self.assertEqual(unique, expected)

    def test_indexes_match_the_contract(self) -> None:
        with db.read() as connection:
            for table, spec in self.contract.items():
                with self.subTest(table=table):
                    indexed = {
                        tuple(row["name"] for row in connection.execute(f"PRAGMA index_info({index['name']})"))
                        for index in connection.execute(f"PRAGMA index_list({table})")
                        if index["origin"] == "c"
                    }
                    expected = {tuple(columns) for columns in spec.get("indexes", [])}
                    self.assertEqual(indexed, expected)

    def test_state_columns_reject_values_outside_the_contract(self) -> None:
        """A CHECK derived from the contract means a buggy handler cannot write a new state."""
        with db.read() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO courses (id, title, recipe, goal, dials_json, status, revision, created_at, updated_at)"
                    " VALUES ('crs_xxxxxxxx', 't', 'committed', 'g', '{}', 'mastered', 0, 'now', 'now')"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at)"
                    " VALUES ('obj_xxxxxxxx', 'missing', 1, 't', 'recall_2', '[]', 'not_started', 1, 'now')"
                )


class MigrationRunnerTest(KernelCase):
    def test_schema_version_is_recorded_with_a_checksum(self) -> None:
        applied = self.rows("SELECT version, checksum, applied_at FROM schema_migrations ORDER BY version")
        self.assertEqual([row["version"] for row in applied],
                         [db.migration_version(path) for path in db.migration_files()])
        self.assertEqual(max(row["version"] for row in applied), db.target_schema_version())
        for row in applied:
            self.assertRegex(row["checksum"], r"^sha256:[a-f0-9]{64}$")
            self.assertTrue(row["applied_at"])

    def test_migrate_is_idempotent(self) -> None:
        before = self.scalar("SELECT MAX(version) FROM schema_migrations")
        self.assertEqual(db.migrate(), db.target_schema_version())
        after = self.scalar("SELECT MAX(version) FROM schema_migrations")
        self.assertEqual(before, after)

    def test_health_reports_ready_after_migration(self) -> None:
        self.assertEqual(
            db.health(),
            {
                "ready": True,
                "schema_version": db.target_schema_version(),
                "state": "ready",
                "target_schema_version": db.target_schema_version(),
            },
        )

    def test_a_fresh_profile_is_honestly_not_ready(self) -> None:
        import os
        import tempfile

        fresh = tempfile.mkdtemp(prefix="coursebook-fresh-")
        previous = os.environ["HERMES_HOME"]
        os.environ["HERMES_HOME"] = fresh
        try:
            self.assertEqual(
                db.health(),
                {
                    "ready": False,
                    "schema_version": None,
                    "state": "unmigrated",
                    "target_schema_version": db.target_schema_version(),
                },
            )
            # No store has no migration error: "unmigrated" is not "failed".
            self.assertNotIn("error", db.health())
            self.assertIsNone(db.applied_schema_version())
            # A command migrates on first use instead of failing on a fresh install.
            response = self.ok("course.create", {"title": "Fresh", "recipe": "casual", "goal": "Start"})
            self.assertTrue(response["result"]["course_id"])
            self.assertEqual(db.health()["ready"], True)
        finally:
            os.environ["HERMES_HOME"] = previous

    def test_pragmas_are_wal_and_foreign_keys(self) -> None:
        with db.read() as connection:
            self.assertEqual(str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(), "wal")
            self.assertEqual(int(connection.execute("PRAGMA foreign_keys").fetchone()[0]), 1)
            self.assertEqual(int(connection.execute("PRAGMA busy_timeout").fetchone()[0]), db.BUSY_TIMEOUT_MS)

    def test_checksum_drift_is_refused(self) -> None:
        with db.transaction() as connection:
            connection.execute("UPDATE schema_migrations SET checksum = 'sha256:" + "0" * 64 + "'")
        with self.assertRaises(db.SchemaDrift):
            db.migrate()


class HealthMigrationFailureTest(KernelCase):
    """H-114 F11/F22 — a migration that *failed* is not a profile that was never migrated.

    ``health.get`` provisions on first contact, so its migration can fail for a real reason (disk
    I/O, a locked or corrupt store). Before ``cb.rpc`` v29 that failure was swallowed and the
    response was indistinguishable from a fresh profile: ``db.ready: false`` with the old version
    on disk, which the pane rendered as "this profile has no course tables". v29 carries
    ``db.state``, ``db.target_schema_version`` and a bounded ``db.error``, and the GET still
    answers ``ok``.
    """

    def test_a_failed_migration_carries_a_bounded_error_and_the_get_still_answers(self) -> None:
        with mock.patch.object(
            db, "ensure_schema", side_effect=sqlite3.OperationalError("disk I/O error")
        ):
            with self.assertLogs("coursebook", level="WARNING") as logs:
                response = api.dispatch(request("health.get"))
        # The GET is not a transport failure: it answered, and dispatch validated the result
        # against the current response schema (an out-of-contract block would be INTERNAL_ERROR).
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["contract_version"], contracts.WIRE_CONTRACT_VERSION)
        block = response["result"]["db"]
        self.assertFalse(block["ready"])
        self.assertEqual(block["state"], "failed")
        self.assertEqual(block["schema_version"], db.applied_schema_version())
        self.assertEqual(block["target_schema_version"], db.target_schema_version())
        self.assertEqual(block["error"]["type"], "OperationalError")
        self.assertIn("disk I/O error", block["error"]["message"])
        self.assertEqual(block["error"]["target_schema_version"], db.target_schema_version())
        # The failure is never silent: the handler logged it at WARNING.
        self.assertTrue(
            any("migration failed" in line for line in logs.output), logs.output
        )

    def test_a_healthy_store_carries_no_error_field(self) -> None:
        response = api.dispatch(request("health.get"))
        self.assertTrue(response["ok"], response)
        block = response["result"]["db"]
        self.assertTrue(block["ready"])
        self.assertEqual(block["state"], "ready")
        self.assertNotIn("error", block)

    def test_a_failed_startup_reconciliation_is_exposed_on_health_and_logged(self) -> None:
        from coursebook import hooks

        report = {"error": "OperationalError", "message": "orphaned artifact staging unreadable"}
        with mock.patch.object(hooks, "STARTUP_RECONCILIATION", report):
            response = api.dispatch(request("health.get"))
        self.assertTrue(response["ok"], response)
        block = response["result"]["reconciliation"]
        self.assertEqual(block["state"], "failed")
        self.assertEqual(block["error"], "OperationalError")
        self.assertEqual(block["message"], "orphaned artifact staging unreadable")
        # ...and the pane's block agrees with what the module logs at load time.
        with self.assertLogs("coursebook", level="WARNING") as logs:
            hooks._warn_startup_reconciliation(report)
        self.assertTrue(any("startup reconciliation failed" in line for line in logs.output))

    def test_a_healthy_load_reports_reconciliation_ok(self) -> None:
        from coursebook import hooks

        with mock.patch.object(hooks, "STARTUP_RECONCILIATION", {"attempts": 0, "jobs": 0, "artifacts": {}}):
            response = api.dispatch(request("health.get"))
        self.assertEqual(
            response["result"]["reconciliation"], {"state": "ok", "error": None, "message": None}
        )


if __name__ == "__main__":
    unittest.main()
