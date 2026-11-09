"""cb.db v7 / cb.rpc v11: the unit storage and the legacy plan-hash invariant.

One test here is the merge blocker: migration 0007 must leave ``parent_authoring.plan_hash``
byte-identical for a plan stored before it existed. Every other v7 test is a shape or a fence.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest

from coursebook import db, domain, packs
from coursebook.contracts import contract
from tests.kernel_support import KernelCase

#: The exact pre-0007 kernel hash of the fixture plan below, computed with the v6 code before
#: migration 0007 was written (master 498b1da, schema version 6). It is a literal on purpose:
#: a refactor that quietly adds ``units: []`` or ``unit: null`` to the payload fails here.
LEGACY_PLAN_HASH = "sha256:2ec4ad3356df241d30ca185336f85f72bbec46035adedafce9b39ddb2477293b"

COURSE_ROW = (
    "crs_legacy01", "Legacy braise", "committed", "Braise short ribs", "en-US",
    '{"pace": "steady", "depth": "working", "assessment": "self_check", "autonomy": "guided"}',
    "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
)
PLAN_ROW = (
    "pln_legacy01", "crs_legacy01", 1, "draft", None, "{}",
    "2026-01-01T00:00:00+00:00", None,
)
OBJECTIVE_ROWS = [
    ("obj_legacy01", "pln_legacy01", 1, "Sear the ribs", "procedure",
     '[{"id": "c1", "description": "Sear without steaming the meat"}]', "not_started", 1,
     "2026-01-01T00:00:00+00:00"),
    ("obj_legacy02", "pln_legacy01", 2, "Braise to tenderness", "procedure",
     '[{"id": "c1", "description": "Meat yields to a fork"}]', "not_started", 1,
     "2026-01-01T00:00:00+00:00"),
]


def _legacy_payload() -> dict:
    """The v6 hash payload, written out independently of the implementation under test."""
    return {
        "course_id": PLAN_ROW[1],
        "version": PLAN_ROW[2],
        "schedule": {},
        "objectives": [
            {
                "id": row[0],
                "ordinal": row[2],
                "title": row[3],
                "evidence_target": row[4],
                "evidence_criteria": json.loads(row[5]),
                "version": row[7],
            }
            for row in OBJECTIVE_ROWS
        ],
    }


class PlanUnitsSchemaTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status,"
                " revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                COURSE_ROW,
            )
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json,"
                " created_at, approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                PLAN_ROW,
            )
            for row in OBJECTIVE_ROWS:
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )

    # ── schema ──────────────────────────────────────────────────────────────

    def test_target_schema_version_is_pinned_to_v13(self) -> None:
        # H-53 took cb.db to v9 for the nullable `evidence.note` column the v14
        # `observation.record` writes; H-124 took it to v10 for the `hook_errors` diagnostics
        # table a lost teaching snapshot is recorded in; H-120a took it to v11 for the
        # conversation-practice tables migration 0011 adds; H-194 took it to v12 for the
        # fine-tune ledgers migration 0012 adds (`plan_revisions`, `lesson_revisions`); GM-001
        # took it to v13 for the Game Mode storage migration 0013 adds.
        # Migrations 0007 (plan_units) and 0008 (syllabus) are unchanged.
        self.assertEqual(db.DB_SCHEMA_VERSION, 13)
        self.assertEqual(db.target_schema_version(), 13)
        self.assertEqual(contract("cb.db")["schema_version"], 13)
        self.assertEqual(db.applied_schema_version(), 13)
        with db.read() as connection:
            recorded = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        self.assertEqual(recorded, 13)

    def test_unit_columns_match_the_contract_exactly(self) -> None:
        spec = contract("cb.db")["tables"]
        with db.read() as connection:
            units = {row["name"]: row for row in connection.execute("PRAGMA table_info(plan_units)")}
            objectives = {row["name"]: row for row in connection.execute("PRAGMA table_info(objectives)")}
            sections = {row["name"]: row for row in connection.execute("PRAGMA table_info(gen_plan_sections)")}
        self.assertEqual(set(units), set(spec["plan_units"]["columns"]))
        self.assertIn("unit_id", objectives)
        self.assertEqual(objectives["unit_id"]["type"], "TEXT")
        self.assertEqual(objectives["unit_id"]["notnull"], 0)
        self.assertEqual(sections["unit_id"]["type"], "TEXT")
        self.assertEqual(sections["unit_id"]["notnull"], 0)
        self.assertEqual(sections["section_role"]["type"], "TEXT")
        self.assertEqual(sections["section_role"]["notnull"], 1)
        self.assertEqual(sections["section_role"]["dflt_value"].strip("'\""), "owner")

    def test_legacy_objectives_keep_a_null_unit(self) -> None:
        with db.read() as connection:
            rows = connection.execute(
                "SELECT unit_id FROM objectives WHERE plan_id = ? ORDER BY ordinal", ("pln_legacy01",)
            ).fetchall()
        self.assertEqual([row["unit_id"] for row in rows], [None, None])

    def test_a_section_defaults_to_owner_with_no_unit(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent)"
                " VALUES ('sec_legacy01', 'pln_legacy01', 1, 'sha256:legacy', 'Sear', 'Sear the ribs')"
            )
        with db.read() as connection:
            row = connection.execute("SELECT unit_id, section_role FROM gen_plan_sections").fetchone()
        self.assertIsNone(row["unit_id"])
        self.assertEqual(row["section_role"], "owner")

    def test_plan_unit_ordinals_are_unique_per_plan_and_fenced_by_the_plan(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES ('unt_12345678', 'pln_legacy01', 1, 'Sear', 'Sear the ribs', '[]', 2,"
                " '2026-01-01T00:00:00+00:00')"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            with db.transaction() as connection:
                connection.execute(
                    "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                    " prereq_unit_ordinals_json, target_lessons, created_at)"
                    " VALUES ('unt_87654321', 'pln_legacy01', 1, 'Dup', 'Duplicate ordinal', '[]', 1,"
                    " '2026-01-01T00:00:00+00:00')"
                )
        # The plan_id foreign key is real: a unit cannot hang off a plan that does not exist.
        with self.assertRaises(sqlite3.IntegrityError):
            with db.transaction() as connection:
                connection.execute(
                    "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                    " prereq_unit_ordinals_json, target_lessons, created_at)"
                    " VALUES ('unt_orphan01', 'pln_missing1', 1, 'Orphan', 'No plan', '[]', 1,"
                    " '2026-01-01T00:00:00+00:00')"
                )


class LegacyPlanHashInvarianceTest(KernelCase):
    """R4: migration 0007 must not invalidate a single stored plan hash."""

    def setUp(self) -> None:
        super().setUp()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status,"
                " revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                COURSE_ROW,
            )
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json,"
                " created_at, approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                PLAN_ROW,
            )
            for row in OBJECTIVE_ROWS:
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )

    def test_legacy_plan_hash_is_byte_identical_after_0007(self) -> None:
        self.assertEqual(domain.plan_hash("pln_legacy01"), LEGACY_PLAN_HASH)
        with db.read() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM plan_units WHERE plan_id = ?", ("pln_legacy01",)
                ).fetchone()[0],
                0,
            )

    def test_the_legacy_payload_carries_no_units_and_no_unit_keys(self) -> None:
        payload = _legacy_payload()
        self.assertNotIn("units", payload)
        for entry in payload["objectives"]:
            self.assertNotIn("unit", entry)
        expected = "sha256:" + hashlib.sha256(
            packs.canonical_json_bytes(payload)
        ).hexdigest()
        self.assertEqual(domain.plan_hash("pln_legacy01"), expected)

    def test_a_unit_row_extends_the_hash_and_a_retitle_changes_it(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES ('unt_12345678', 'pln_legacy01', 1, 'Sear', 'Sear the ribs', '[]', 2,"
                " '2026-01-01T00:00:00+00:00')"
            )
        with_unit = domain.plan_hash("pln_legacy01")
        self.assertNotEqual(with_unit, LEGACY_PLAN_HASH)
        # The units array is exactly the stored facts, in ordinal order.
        payload = _legacy_payload()
        payload["units"] = [{
            "id": "unt_12345678",
            "ordinal": 1,
            "title": "Sear",
            "goal": "Sear the ribs",
            "prereq_unit_ordinals": [],
            "target_lessons": 2,
        }]
        expected = "sha256:" + hashlib.sha256(
            packs.canonical_json_bytes(payload)
        ).hexdigest()
        self.assertEqual(with_unit, expected)
        # A unit retitle changes what the learner approved, so it changes the hash.
        with db.transaction() as connection:
            connection.execute("UPDATE plan_units SET title = 'Sear hard' WHERE id = 'unt_12345678'")
        self.assertNotEqual(domain.plan_hash("pln_legacy01"), with_unit)

    def test_an_objective_unit_id_adds_only_that_objectives_unit_key(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES ('unt_12345678', 'pln_legacy01', 1, 'Sear', 'Sear the ribs', '[]', 2,"
                " '2026-01-01T00:00:00+00:00')"
            )
            connection.execute(
                "UPDATE objectives SET unit_id = 'unt_12345678' WHERE id = 'obj_legacy01'"
            )
        payload = _legacy_payload()
        payload["objectives"][0]["unit"] = "unt_12345678"
        payload["units"] = [{
            "id": "unt_12345678", "ordinal": 1, "title": "Sear", "goal": "Sear the ribs",
            "prereq_unit_ordinals": [], "target_lessons": 2,
        }]
        expected = "sha256:" + hashlib.sha256(
            packs.canonical_json_bytes(payload)
        ).hexdigest()
        self.assertEqual(domain.plan_hash("pln_legacy01"), expected)
        # The unscoped objective keeps no `unit` key.
        self.assertNotIn("unit", payload["objectives"][1])

    def test_a_prerequisite_change_changes_the_hash(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES ('unt_12345678', 'pln_legacy01', 1, 'Sear', 'Sear the ribs', '[]', 2,"
                " '2026-01-01T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES ('unt_87654321', 'pln_legacy01', 2, 'Braise', 'Braise slowly', '[1]', 2,"
                " '2026-01-01T00:00:00+00:00')"
            )
        before = domain.plan_hash("pln_legacy01")
        with db.transaction() as connection:
            connection.execute(
                "UPDATE plan_units SET prereq_unit_ordinals_json = '[]' WHERE id = 'unt_87654321'"
            )
        self.assertNotEqual(domain.plan_hash("pln_legacy01"), before)


if __name__ == "__main__":
    unittest.main()
