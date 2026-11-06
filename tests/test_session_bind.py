"""The session-binding write seam (`POST /sessions/bind` → `coursebook.bindings.bind_session`).

The point of these tests is the *absence* they close: before this seam nothing in the backend ever
inserted a ``bindings`` row, so the governed loop (pre-turn gate, pane, chat reconciliation) was
unreachable from a real Desktop even though every unit below it passed with rows inserted by hand.

Each case runs against a real migrated SQLite database under a throwaway ``HERMES_HOME``.
"""

from __future__ import annotations

import unittest

from coursebook import api, bindings, db
from tests.kernel_support import KernelCase


class BindSessionCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "mode": "fresh",
            },
            idempotency_key=f"begin-{self.lesson['objective_id']}",
        )["result"]
        self.run_id = run["lesson_run_id"]

    def bind(self, **overrides):
        payload = {
            "stored_session_id": "sess_durable_1",
            "enrollment_id": self.lesson["enrollment_id"],
            "objective_id": self.lesson["objective_id"],
            "lesson_run_id": self.run_id,
            "profile": "cbqa",
        }
        payload.update(overrides)
        return bindings.bind_session(**payload)

    def binding_rows(self) -> list[dict]:
        return self.rows("SELECT * FROM bindings ORDER BY rowid")

    # ── the happy path ──────────────────────────────────────────────────

    def test_binds_the_stored_id_to_the_exact_run(self) -> None:
        outcome = self.bind()
        self.assertTrue(outcome["created"])
        binding = outcome["binding"]
        self.assertEqual(binding["stored_session_id"], "sess_durable_1")
        self.assertEqual(binding["enrollment_id"], self.lesson["enrollment_id"])
        self.assertEqual(binding["lesson_run_id"], self.run_id)
        self.assertEqual(binding["objective_id"], self.lesson["objective_id"])
        self.assertEqual(binding["status"], "active")
        self.assertEqual(binding["profile"], "cbqa")
        self.assertEqual(binding["matched_column"], "stored_session_id")

        # The read half (binding.get) now answers by stored id — the seam wrote the row the
        # contract reads, not a private parallel record.
        found = self.ok("binding.get", {"session_id": "sess_durable_1"})["result"]["binding"]
        self.assertIsNotNone(found)
        self.assertEqual(found["binding_id"], binding["id"])
        self.assertEqual(found["matched_column"], "stored_session_id")

    def test_repeating_the_same_bind_is_idempotent(self) -> None:
        first = self.bind()
        second = self.bind()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["binding"]["id"], second["binding"]["id"])
        self.assertEqual(len(self.binding_rows()), 1)

    def test_defaults_the_profile_instead_of_storing_an_empty_one(self) -> None:
        outcome = self.bind(profile="")
        self.assertEqual(outcome["binding"]["profile"], "default")

    # ── refusals: never a second authoritative chat ─────────────────────

    def test_a_chat_already_bound_to_another_lesson_is_refused(self) -> None:
        self.bind()
        other = self.prepare_lesson_second()
        with self.assertRaises(api.RpcError) as caught:
            self.bind(
                enrollment_id=other["enrollment_id"],
                objective_id=other["objective_id"],
                lesson_run_id=other["run_id"],
            )
        error = caught.exception.error
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "session_already_bound")
        # The refusal wrote nothing: still one row, still the first lesson.
        rows = self.binding_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["enrollment_id"], self.lesson["enrollment_id"])

    def test_a_second_active_chat_for_one_enrollment_is_refused(self) -> None:
        self.bind()
        second_run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "mode": "fresh",
            },
            idempotency_key="begin-second-run",
        )["result"]["lesson_run_id"]
        with self.assertRaises(api.RpcError) as caught:
            self.bind(stored_session_id="sess_durable_2", lesson_run_id=second_run)
        error = caught.exception.error
        self.assertEqual(error["details"]["reason"], "enrollment_already_bound")
        self.assertEqual(error["details"]["binding_id"], self.binding_rows()[0]["id"])
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM bindings WHERE stored_session_id = 'sess_durable_2'"), 0
        )

    def test_an_abandoned_run_cannot_be_bound(self) -> None:
        self.execute("UPDATE lesson_runs SET state = 'abandoned' WHERE id = ?", (self.run_id,))
        with self.assertRaises(api.RpcError) as caught:
            self.bind()
        self.assertEqual(caught.exception.error["details"]["reason"], "lesson_run_not_active")
        self.assertEqual(self.binding_rows(), [])

    def test_a_run_from_another_enrollment_is_refused(self) -> None:
        other = self.prepare_lesson_second()
        with self.assertRaises(api.RpcError) as caught:
            self.bind(lesson_run_id=other["run_id"])
        self.assertEqual(caught.exception.error["details"]["reason"], "lesson_run_mismatch")
        self.assertEqual(self.binding_rows(), [])

    def test_a_different_objective_for_the_same_run_is_refused(self) -> None:
        other = self.prepare_lesson_second()
        with self.assertRaises(api.RpcError) as caught:
            self.bind(objective_id=other["objective_id"])
        self.assertEqual(caught.exception.error["details"]["reason"], "lesson_run_mismatch")
        self.assertEqual(self.binding_rows(), [])

    def test_unknown_ids_are_not_found_and_write_nothing(self) -> None:
        with self.assertRaises(api.RpcError) as caught:
            self.bind(enrollment_id="enr_missing")
        self.assertEqual(caught.exception.error["code"], "NOT_FOUND")
        with self.assertRaises(api.RpcError) as caught:
            self.bind(lesson_run_id="run_missing")
        self.assertEqual(caught.exception.error["code"], "NOT_FOUND")
        self.assertEqual(self.binding_rows(), [])

    def test_a_missing_stored_id_is_refused_rather_than_invented(self) -> None:
        for value in ("", "   ", None):
            with self.assertRaises(api.RpcError) as caught:
                self.bind(stored_session_id=value)
            self.assertEqual(caught.exception.error["details"]["field"], "stored_session_id")
        self.assertEqual(self.binding_rows(), [])

    # ── what the binding then enables ───────────────────────────────────

    def test_the_bound_chat_reaches_the_pre_turn_gate(self) -> None:
        """The gate resolves the same row the seam wrote — by stored id, not by recency."""
        from coursebook import turn

        outcome = self.bind()
        binding = turn._binding_for_session(api.dispatch, "sess_durable_1")
        self.assertIsNotNone(binding)
        self.assertEqual(binding["id"], outcome["binding"]["id"])
        # A runtime id is never a stand-in for the durable one.
        self.assertIsNone(turn._binding_for_session(api.dispatch, "rt_runtime_only"))

    def test_abandoning_the_binding_keeps_the_evidence_and_releases_the_enrollment(self) -> None:
        first = self.bind()
        abandoned = self.ok(
            "binding.abandon",
            {"binding_id": first["binding"]["id"], "reason": "test"},
            expected_revision=0,
        )["result"]
        self.assertEqual(abandoned["status"], "orphaned")
        second = self.bind(stored_session_id="sess_durable_2")
        self.assertTrue(second["created"])

    # ── moving between sections of one course ───────────────────────────

    def add_section(self) -> dict:
        """A second objective in the same plan, with its own active run."""
        import json

        objective_id = "obj_test_transfer"
        self.execute(
            "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
            " evidence_criteria_json, state, version, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                objective_id,
                self.lesson["plan_id"],
                2,
                "Transfer",
                "transfer",
                json.dumps([{"id": "c1", "description": "explains the change"}]),
                "not_started",
                1,
                db.utcnow(),
            ),
        )
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": objective_id,
                "mode": "fresh",
            },
            idempotency_key=f"begin-{objective_id}",
        )["result"]
        return {"objective_id": objective_id, "run_id": run["lesson_run_id"]}

    def test_a_new_sections_chat_supersedes_the_previous_sections_chat(self) -> None:
        """One section keeps one authoritative chat; the old one detaches, it is not deleted."""
        first = self.bind()
        other = self.add_section()
        second = self.bind(
            stored_session_id="sess_durable_2",
            objective_id=other["objective_id"],
            lesson_run_id=other["run_id"],
        )
        self.assertTrue(second["created"])
        rows = self.binding_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], first["binding"]["id"])
        self.assertEqual(rows[0]["status"], "detached")
        self.assertEqual(rows[1]["status"], "active")
        self.assertEqual(rows[1]["objective_id"], other["objective_id"])
        self.assertEqual(rows[1]["lesson_run_id"], other["run_id"])

    def test_the_same_chat_moves_with_the_learner_to_the_next_section(self) -> None:
        """Reattach: the focused chat follows the learner instead of needing a second row."""
        first = self.bind()
        other = self.add_section()
        moved = self.bind(
            objective_id=other["objective_id"], lesson_run_id=other["run_id"]
        )
        self.assertFalse(moved["created"])
        self.assertEqual(moved["binding"]["id"], first["binding"]["id"])
        self.assertEqual(moved["binding"]["objective_id"], other["objective_id"])
        self.assertEqual(moved["binding"]["lesson_run_id"], other["run_id"])
        self.assertEqual(moved["binding"]["status"], "active")
        self.assertEqual(len(self.binding_rows()), 1)

    def prepare_lesson_second(self) -> dict:
        lesson = self.prepare_lesson()
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "mode": "fresh",
            },
            idempotency_key=f"begin-{lesson['objective_id']}",
        )["result"]
        return {
            **lesson,
            "run_id": run["lesson_run_id"],
        }


class SeamPacketShape(unittest.TestCase):
    """The HTTP adapter answers the shape the Desktop half reads."""

    def test_route_is_registered_beside_the_other_host_seams(self) -> None:
        import importlib.util
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "coursebook_plugin_api_bind_test", root / "dashboard" / "plugin_api.py"
        )
        if spec is None or spec.loader is None:
            self.fail("cannot load dashboard/plugin_api.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paths = {route.path for route in module.router.routes}
        self.assertIn("/sessions/bind", paths)
        self.assertIn("/packs/grant", paths)


if __name__ == "__main__":
    unittest.main()
