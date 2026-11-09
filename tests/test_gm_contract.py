"""GM-001: the frozen Game Mode contract.

These tests pin the names the whole program is built against before any handler exists:
the presentation mode and its read fallback, the world grammar/role vocabulary, the
take-home, homework, engagement and tutor enums, the ``cb.rpc`` method manifest, and the
additive shape of migration 0013.

The migration test is a real round trip: a disposable database is built with migrations
0001..0012, seeded with a legacy course, an attempt and evidence, then migrated to v13 and
re-read. The point is that the upgrade is additive, not that the test DB looks new.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from coursebook import contracts, db, gm_contract as gm


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "coursebook"

#: Modules that read evidence, build packs or package a course for export. None of them may
#: learn about a Game Mode table: XP, tutor prose and take-home drafts are not learning evidence.
EXPORT_AND_EVIDENCE_MODULES = ("evidence.py", "pack_flow.py", "packs.py", "archive.py")


def _db_document(filename: str) -> dict:
    return json.loads((contracts.CONTRACT_DIR / filename).read_text(encoding="utf-8"))


class GmContractManifestTest(unittest.TestCase):
    """The method manifest is the collision boundary for six backend cards."""

    def test_gm_contract_method_manifest_carries_every_card_method(self) -> None:
        self.assertEqual(len(gm.CARD_GM_METHODS), 18)
        self.assertEqual(set(gm.CARD_GM_METHODS) - set(gm.GM_RPC_METHODS), set())
        self.assertEqual(set(gm.GM_RPC_METHODS), set(gm.GM_METHOD_NAMES))
        self.assertEqual(
            set(gm.GM_RPC_METHODS) - set(gm.CARD_GM_METHODS), set(gm.EXTRA_GM_METHODS)
        )

    def test_gm_contract_method_manifest_matches_the_card_text(self) -> None:
        # The exact names the card enumerates. A later card that renames one fails here first.
        expected = {
            "world.read",
            "world.style.preview",
            "world.generate",
            "world.approve",
            "takehome.sources",
            "takehome.preview",
            "takehome.create",
            "takehome.approve",
            "takehome.export",
            "takehome.read",
            "homework.create",
            "homework.read",
            "homework.complete",
            "homework.skip",
            "engagement.read",
            "engagement.award",
            "tutor.ask",
            "tutor.history",
        }
        self.assertEqual(set(gm.CARD_GM_METHODS), expected)
        for name in gm.GM_METHOD_NAMES:
            with self.subTest(method=name):
                self.assertRegex(name, r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$")

    def test_gm_contract_every_entry_is_closed_and_typed(self) -> None:
        for name, entry in gm.GM_RPC_METHODS.items():
            with self.subTest(method=name):
                self.assertEqual(
                    set(entry),
                    {"kind", "idempotent", "requires_expected_revision", "spends_provider",
                     "job", "request", "response", "errors", "note"},
                )
                self.assertIn(entry["kind"], {"read", "mutate"})
                self.assertIsInstance(entry["idempotent"], bool)
                self.assertIsInstance(entry["requires_expected_revision"], bool)
                self.assertIsInstance(entry["spends_provider"], bool)
                self.assertIn(entry["job"], {None, "media"})
                for side in ("request", "response"):
                    fields = entry[side]
                    self.assertIsInstance(fields, tuple)
                    self.assertTrue(fields, f"{name}.{side} is empty")
                    self.assertEqual(len(fields), len(set(fields)), f"{name}.{side} has a duplicate")
                for code in entry["errors"]:
                    self.assertIn(code, contracts.error_codes(), f"{name} names unknown code {code}")

    def test_gm_contract_mutations_are_fenced_and_replayable(self) -> None:
        for name, entry in gm.GM_RPC_METHODS.items():
            with self.subTest(method=name):
                if entry["kind"] != "mutate":
                    self.assertFalse(entry["requires_expected_revision"], name)
                    continue
                # Every mutation is a command with a stable error shape and an idempotency key.
                self.assertTrue(entry["idempotent"], f"{name} must be idempotent")
                self.assertIn("IDEMPOTENCY_CONFLICT", entry["errors"], name)
                if name != "engagement.award":
                    # XP is an append-only event fenced by (enrollment, action_kind, action_id);
                    # it cannot move an aggregate revision, so it carries no revision fence.
                    self.assertTrue(
                        entry["requires_expected_revision"],
                        f"{name} mutates a revisioned aggregate and must fence on it",
                    )

    def test_gm_contract_provider_spend_is_named_and_gated(self) -> None:
        spending = {name for name, entry in gm.GM_RPC_METHODS.items() if entry["spends_provider"]}
        self.assertEqual(spending, {"world.generate", "homework.create", "tutor.ask"})
        for name in spending:
            entry = gm.GM_RPC_METHODS[name]
            self.assertEqual(entry["kind"], "mutate")

    def test_gm_contract_every_card_dependency_is_frozen(self) -> None:
        """No DAG card may need a name the manifest lacks, and no frozen name is orphaned."""
        card_dependencies = {
            "GM-002": ("course.mode.set",),
            "GM-003": ("world.read", "world.style.preview", "world.generate", "world.approve"),
            "GM-004": ("world.read", "world.style.preview"),
            "GM-005": ("takehome.sources", "takehome.preview", "takehome.create",
                       "takehome.approve", "takehome.export", "takehome.read"),
            "GM-006": ("takehome.sources", "takehome.preview", "takehome.read"),
            "GM-007": ("homework.create", "homework.read", "homework.complete", "homework.skip"),
            "GM-008": ("homework.read", "homework.complete", "homework.skip"),
            "GM-009": ("engagement.read", "engagement.award"),
            "GM-010": ("engagement.read",),
            "GM-011": ("tutor.ask", "tutor.history"),
            "GM-012": ("tutor.ask", "tutor.history"),
        }
        needed = {method for methods in card_dependencies.values() for method in methods}
        self.assertEqual(needed - set(gm.GM_RPC_METHODS), set(),
                         "a card depends on a method the manifest does not freeze")
        self.assertEqual(set(gm.GM_RPC_METHODS) - needed, set(),
                         "a frozen method belongs to no card")

    def test_gm_contract_document_names_every_frozen_name(self) -> None:
        text = (REPO_ROOT / "docs" / "GM-CONTRACT.md").read_text(encoding="utf-8")
        for method in gm.GM_METHOD_NAMES:
            with self.subTest(method=method):
                self.assertIn(method, text, f"GM-CONTRACT.md does not document {method}")
        for table in gm.GM_TABLES + ("courses.presentation_mode",):
            with self.subTest(table=table):
                self.assertIn(table, text, f"GM-CONTRACT.md does not document {table}")
        for enum in (gm.PresentationMode, gm.WorldGrammar, gm.WorldRole, gm.TakeHomeAudience,
                     gm.TakeHomeKind, gm.HomeworkKind, gm.HomeworkState, gm.TutorMode):
            for member in enum:
                with self.subTest(enum=enum.__name__, value=member.value):
                    self.assertIn(member.value, text)

    def test_gm_contract_manifest_has_no_evidence_keys(self) -> None:
        for name, entry in gm.GM_RPC_METHODS.items():
            with self.subTest(method=name):
                keys = set(entry["request"]) | set(entry["response"])
                self.assertEqual(keys & set(gm.FORBIDDEN_METHOD_KEYS), set())

    def test_gm_contract_manifest_is_pure(self) -> None:
        source = (SOURCE_DIR / "gm_contract.py").read_text(encoding="utf-8")
        for needle in ("import requests", "urllib", "http.client", "plugins.", "plugin_db",
                       "plugin.js", "desktop/"):
            self.assertNotIn(needle, source, f"gm_contract.py must stay pure: found {needle!r}")


class GmEnumTest(unittest.TestCase):
    """Exact enum values. A value is a stored string; changing one needs a migration."""

    def test_gm_contract_enum_values_are_pinned(self) -> None:
        self.assertEqual([m.value for m in gm.PresentationMode], ["game", "textbook"])
        self.assertEqual(
            [m.value for m in gm.WorldGrammar],
            ["field_atlas", "workshop_manual", "observatory", "kitchen_table",
             "archive_desk", "studio_bench", "lab_bench", "instrument_board"],
        )
        self.assertEqual(
            [m.value for m in gm.WorldRole], ["hero", "cover", "section", "lesson_scene"]
        )
        self.assertEqual([m.value for m in gm.TakeHomeAudience], ["learner", "parent"])
        self.assertEqual(
            [m.value for m in gm.TakeHomeKind],
            ["print_pack", "activity_plan", "homework_sheet"],
        )
        self.assertEqual(
            [m.value for m in gm.TakeHomeState],
            ["draft", "previewed", "approved", "exported", "superseded"],
        )
        self.assertEqual(
            [m.value for m in gm.HomeworkKind],
            ["real_world_use", "observe", "label", "practice", "make", "teach_back"],
        )
        self.assertEqual(
            [m.value for m in gm.HomeworkState],
            ["proposed", "assigned", "self_reported_done", "parent_reported_done",
             "skipped", "expired"],
        )
        self.assertEqual([m.value for m in gm.TutorMode], ["ask", "practice"])
        self.assertEqual(
            [m.value for m in gm.WorldState],
            ["not_requested", "concepts_generating", "concepts_ready", "style_selected",
             "kit_generating", "kit_ready", "approved", "failed", "stale", "unavailable"],
        )

    def test_gm_contract_enums_serialize_as_bare_strings(self) -> None:
        for member in gm.PresentationMode:
            with self.subTest(member=member):
                self.assertIsInstance(member, str)
                self.assertEqual(json.dumps({"v": member}), json.dumps({"v": member.value}))
                self.assertEqual(hash(member), hash(member.value))

    def test_gm_contract_presentation_mode_falls_back_to_textbook(self) -> None:
        self.assertEqual(gm.read_presentation_mode(None), "textbook")
        self.assertEqual(gm.read_presentation_mode(""), "textbook")
        self.assertEqual(gm.read_presentation_mode("textbook"), "textbook")
        self.assertEqual(gm.read_presentation_mode("game"), "game")
        # A value the contract does not define is not leaked to a caller.
        self.assertEqual(gm.read_presentation_mode("field_quest"), "textbook")
        self.assertEqual(gm.read_presentation_mode(gm.PresentationMode.GAME), "game")

    def test_gm_contract_world_role_budget_is_the_plan_budget(self) -> None:
        self.assertEqual(
            gm.WORLD_ROLE_LIMITS, {"hero": 1, "cover": 1, "section": 6, "lesson_scene": 2}
        )
        self.assertEqual(set(gm.WORLD_ROLE_LIMITS), {m.value for m in gm.WorldRole})
        self.assertIn("text", gm.WORLD_PROMPT_FORBIDDEN)
        self.assertIn("ui chrome", gm.WORLD_PROMPT_FORBIDDEN)
        self.assertEqual(gm.DEFAULT_WORLD_GRAMMAR, gm.WorldGrammar.FIELD_ATLAS)
        self.assertEqual(gm.DEFAULT_PRESENTATION_MODE, gm.PresentationMode.TEXTBOOK)

    def test_gm_contract_homework_completion_is_never_a_pass(self) -> None:
        states = {m.value for m in gm.HomeworkState}
        self.assertEqual(set(gm.HOMEWORK_COMPLETION_STATES),
                         {"self_reported_done", "parent_reported_done"})
        self.assertTrue(set(gm.HOMEWORK_COMPLETION_STATES) <= states)
        self.assertFalse(
            states & {"pass", "passed", "mastered", "complete", "graded", "verified"}
        )
        self.assertLess(gm.HOMEWORK_MINUTES_MIN, gm.HOMEWORK_MINUTES_MAX)
        self.assertEqual((gm.HOMEWORK_MINUTES_MIN, gm.HOMEWORK_MINUTES_MAX), (3, 10))


class GmMigrationTest(unittest.TestCase):
    """The additive shape of cb.db v13 and migration 0013."""

    def test_gm_contract_v13_is_v12_plus_only_game_mode_storage(self) -> None:
        v12 = _db_document("db.v12.json")
        v13 = _db_document("db.v13.json")
        self.assertEqual(v13["schema_version"], 13)
        self.assertEqual(v13["x-contract-version"], 13)
        self.assertEqual(v13["$id"], "https://contracts.coursebook.hermes/db/v13")
        self.assertEqual(v13["x-supersedes"], "https://contracts.coursebook.hermes/db/v12")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v13.json")

        self.assertEqual(set(v13["tables"]) - set(v12["tables"]), set(gm.GM_TABLES))
        self.assertEqual(set(v12["tables"]) - set(v13["tables"]), set(), "v13 dropped a table")

        added_columns = {
            (table, column)
            for table, spec in v12["tables"].items()
            for column in set(v13["tables"][table]["columns"]) - set(spec["columns"])
        }
        self.assertEqual(added_columns, {("courses", "presentation_mode")})
        column = v13["tables"]["courses"]["columns"]["presentation_mode"]
        self.assertEqual(column["type"], "TEXT")
        self.assertTrue(column["nullable"], "an old course must stay valid with NULL")
        self.assertEqual(column["enum"], ["game", "textbook"])

    def test_gm_contract_v13_retypes_no_v12_column_or_key(self) -> None:
        v12 = _db_document("db.v12.json")
        v13 = _db_document("db.v13.json")
        for table, spec in v12["tables"].items():
            with self.subTest(table=table):
                for column, definition in spec["columns"].items():
                    self.assertEqual(
                        v13["tables"][table]["columns"][column], definition,
                        f"{table}.{column} changed in v13",
                    )
                self.assertEqual(v13["tables"][table].get("unique"), spec.get("unique"))
                self.assertEqual(v13["tables"][table].get("indexes"), spec.get("indexes"))

    def test_gm_contract_migration_plan_is_append_only(self) -> None:
        v12 = _db_document("db.v12.json")
        v13 = _db_document("db.v13.json")
        self.assertEqual(v13["migration_plan"][: len(v12["migration_plan"])],
                         v12["migration_plan"])
        entry = v13["migration_plan"][-1]
        self.assertEqual((entry["version"], entry["from"]), (13, 12))
        self.assertEqual(entry["migration"], gm.GM_MIGRATION)
        self.assertTrue(any("Additive only" in line for line in entry["impact"]))
        self.assertTrue(any("No backfill" in line for line in entry["impact"]))

    def test_gm_contract_sql_is_additive_and_rewrites_no_row(self) -> None:
        sql = (SOURCE_DIR / "migrations" / gm.GM_MIGRATION).read_text(encoding="utf-8")
        statements = [
            line.strip()
            for line in sql.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        body = "\n".join(statements).upper()
        for forbidden in ("DROP TABLE", "DROP INDEX", "DELETE FROM", "UPDATE ",
                          "INSERT INTO", "RENAME TO", "CREATE TRIGGER"):
            self.assertNotIn(forbidden, body, f"0013 must not contain {forbidden!r}")
        self.assertEqual(body.count("ALTER TABLE"), 1)
        self.assertIn("ALTER TABLE COURSES ADD COLUMN PRESENTATION_MODE", body)
        created = {name.lower() for name in re.findall(r"CREATE TABLE (\w+)", body)}
        self.assertEqual(created, set(gm.GM_TABLES))

    def test_gm_contract_gm_tables_carry_no_evidence_columns(self) -> None:
        v13 = _db_document("db.v13.json")
        for table in gm.GM_TABLES:
            with self.subTest(table=table):
                columns = set(v13["tables"][table]["columns"])
                self.assertEqual(columns & set(gm.GM_FORBIDDEN_COLUMNS), set())

    def test_gm_contract_evidence_and_export_reads_ignore_gm_tables(self) -> None:
        for filename in EXPORT_AND_EVIDENCE_MODULES:
            text = (SOURCE_DIR / filename).read_text(encoding="utf-8")
            for table in gm.GM_TABLES:
                with self.subTest(module=filename, table=table):
                    self.assertIsNone(
                        re.search(rf"\b{table}\b", text),
                        f"{filename} reads {table}; it must not",
                    )

    def test_gm_contract_unmigrated_course_reads_textbook(self) -> None:
        """A row written before 0013 has no mode; it reads Textbook and stays NULL."""
        home = tempfile.mkdtemp(prefix="coursebook-gm13-")
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = home
        try:
            self._build_v12_with_legacy_rows()
            with db.read() as connection:
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(courses)")}
                self.assertNotIn("presentation_mode", columns,
                                 "the legacy shape must be a real pre-0013 table")
            self.assertEqual(db.migrate(), 13)
            with db.read() as connection:
                row = connection.execute(
                    "SELECT presentation_mode FROM courses WHERE id = 'crs_legacygm01'"
                ).fetchone()
                self.assertIsNone(row["presentation_mode"])
                self.assertEqual(gm.read_presentation_mode(row["presentation_mode"]), "textbook")
                # The read fallback never writes the fallback back.
                again = connection.execute(
                    "SELECT presentation_mode FROM courses WHERE id = 'crs_legacygm01'"
                ).fetchone()
                self.assertIsNone(again["presentation_mode"])
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
            shutil.rmtree(home, ignore_errors=True)

    def test_gm_contract_migration_leaves_attempts_and_evidence_byte_identical(self) -> None:
        home = tempfile.mkdtemp(prefix="coursebook-gm13-")
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = home
        try:
            self._build_v12_with_legacy_rows()
            before_attempts = self._rows("SELECT * FROM attempts ORDER BY id")
            before_evidence = self._rows("SELECT * FROM evidence ORDER BY id")
            before_lessons = self._rows("SELECT * FROM checks ORDER BY id")
            self.assertEqual(len(before_attempts), 1)
            self.assertEqual(len(before_evidence), 1)

            self.assertEqual(db.migrate(), 13)

            self.assertEqual(self._rows("SELECT * FROM attempts ORDER BY id"), before_attempts)
            self.assertEqual(self._rows("SELECT * FROM evidence ORDER BY id"), before_evidence)
            self.assertEqual(self._rows("SELECT * FROM checks ORDER BY id"), before_lessons)

            applied = [row[0] for row in self._rows("SELECT version FROM schema_migrations ORDER BY version")]
            self.assertEqual(applied[-1], 13)
            self.assertIn(13, applied)
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
            shutil.rmtree(home, ignore_errors=True)

    # ── helpers ────────────────────────────────────────────────────────────
    def _build_v12_with_legacy_rows(self) -> None:
        connection = db.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"CREATE TABLE IF NOT EXISTS {db.migration_table()} ("
                "version INTEGER NOT NULL PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            for path in db.migration_files():
                if db.migration_version(path) > 12:
                    continue
                for statement in db._statements(path.read_text(encoding="utf-8")):
                    connection.execute(statement)
                connection.execute(
                    f"INSERT INTO {db.migration_table()} (version, checksum, applied_at) VALUES (?, ?, ?)",
                    (db.migration_version(path), db.file_checksum(path), db.utcnow()),
                )
            self._seed(connection)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @staticmethod
    def _seed(connection: sqlite3.Connection) -> None:
        now = "2026-11-09T00:00:00.000000+00:00"
        connection.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status, revision,"
            " created_at, updated_at) VALUES ('crs_legacygm01', 'Legacy', 'casual', 'Read it',"
            " 'en-US', '{}', 'active', 0, ?, ?)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO plans (id, course_id, version, state, schedule_json, created_at)"
            " VALUES ('pln_legacygm01', 'crs_legacygm01', 1, 'approved', '{}', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
            " evidence_criteria_json, state, version, created_at)"
            " VALUES ('obj_legacygm01', 'pln_legacygm01', 1, 'Legacy objective', 'recall',"
            " '[]', 'not_started', 1, ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO enrollments (id, course_id, learner_label, status, revision,"
            " created_at, updated_at)"
            " VALUES ('enr_legacygm01', 'crs_legacygm01', 'Learner', 'active', 0, ?, ?)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, audit_state, state, created_at)"
            " VALUES ('chk_legacygm01', 'obj_legacygm01', 1, 'recall', '{\"prompt\":\"q\"}',"
            " '{\"criteria\":[]}', '{}', 'passed', 'closed', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce,"
            " answer_kind, answer_json, answer_hash, verdict, evidence_class, criteria_json,"
            " grading_provenance_json, state, created_at, committed_at)"
            " VALUES ('att_legacygm01', 'enr_legacygm01', 'chk_legacygm01', 1, 'nonce-1',"
            " 'text', '{\"text\":\"a\"}', 'sha256:abc', 'pass', 'cold', '[]', '{}',"
            " 'committed', ?, ?)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
            " evidence_class, created_at)"
            " VALUES ('evd_legacygm01', 'enr_legacygm01', 'obj_legacygm01', 'att_legacygm01',"
            " 1, 'attempt_pass', 'cold', ?)",
            (now,),
        )

    @staticmethod
    def _rows(sql: str) -> list[tuple]:
        with db.read() as connection:
            return [tuple(row) for row in connection.execute(sql)]


if __name__ == "__main__":
    unittest.main()
