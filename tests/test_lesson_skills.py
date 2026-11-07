"""Which bundled learner skill a lesson turn loads — and proof that nothing else loads one.

H-65: the plugin registers ``coursebook:lesson-tutoring`` and ``coursebook:learner-coach``, but a
registered plugin skill is not in the agent's automatic index. The rule that actually loads one is
``coursebook.lesson_skills`` (called from the ``pre_llm_call`` hook and from the pane's read-only
``GET /sessions/skill``). These tests pin the three cases and the two properties that make the rule
safe: an unrelated chat is never touched, and a block is never rewritten into a teaching turn.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from coursebook import bindings, db, hooks, lesson_skills

from .kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent


class DecideRuleTest(unittest.TestCase):
    """The rule table itself: no I/O, so it can be read against the spec line by line."""

    def test_a_live_binding_loads_the_db_backed_tutor(self) -> None:
        for status in ("active", "paused"):
            skill, reason = lesson_skills.decide(status, known_chat=True)
            self.assertEqual(skill, "coursebook:lesson-tutoring", status)
            self.assertEqual(reason, "lesson_binding")

    def test_a_coursebook_chat_without_a_live_binding_loads_the_coach(self) -> None:
        for status in ("detached", "branched", "orphaned"):
            skill, reason = lesson_skills.decide(status, known_chat=True)
            self.assertEqual(skill, "coursebook:learner-coach", status)
            self.assertEqual(reason, "coursebook_chat_without_live_binding")

    def test_a_chat_the_store_never_recorded_gets_no_skill(self) -> None:
        skill, reason = lesson_skills.decide(None, known_chat=False)
        self.assertIsNone(skill)
        self.assertEqual(reason, "unrelated_session")


class SkillForSessionTest(KernelCase):
    """The store read: one binding row, one status, one answer. Never recency."""

    def _begin(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.begin",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"], "mode": "fresh"},
            idempotency_key=f"begin-{os.urandom(6).hex()}",
        )["result"]

    def _bound_chat(self, status: str = "active") -> tuple[str, dict]:
        lesson = self.prepare_lesson()
        run = self._begin(lesson)
        stored = "20261107_120000_abc123"
        bindings.bind_session(
            stored_session_id=stored,
            enrollment_id=lesson["enrollment_id"],
            objective_id=lesson["objective_id"],
            lesson_run_id=run["lesson_run_id"],
        )
        if status != "active":
            self.execute("UPDATE bindings SET status = ? WHERE stored_session_id = ?", (status, stored))
        return stored, lesson

    def test_a_bound_session_answers_the_tutor(self) -> None:
        stored, _ = self._bound_chat()
        answer = lesson_skills.skill_for_session(stored)
        self.assertEqual(answer["skill"], lesson_skills.TUTOR_SKILL)
        self.assertEqual(answer["binding_status"], "active")

    def test_a_paused_lesson_still_answers_the_tutor(self) -> None:
        stored, _ = self._bound_chat(status="paused")
        self.assertEqual(lesson_skills.skill_for_session(stored)["skill"], lesson_skills.TUTOR_SKILL)

    def test_a_detached_lesson_chat_answers_the_coach(self) -> None:
        stored, _ = self._bound_chat(status="detached")
        answer = lesson_skills.skill_for_session(stored)
        self.assertEqual(answer["skill"], lesson_skills.COACH_SKILL)
        self.assertEqual(answer["reason"], lesson_skills.REASON_NO_LIVE_BINDING)

    def test_an_unrelated_session_is_untouched_even_with_rows_in_the_store(self) -> None:
        self._bound_chat()
        answer = lesson_skills.skill_for_session("20261107_000000_not_a_lesson")
        self.assertIsNone(answer["skill"])
        self.assertEqual(answer["reason"], lesson_skills.REASON_UNRELATED)

    def test_an_empty_session_id_answers_nothing(self) -> None:
        self.assertIsNone(lesson_skills.skill_for_session("")["skill"])
        self.assertIsNone(lesson_skills.skill_for_session(None)["skill"])

    def test_the_newest_live_row_wins_over_an_older_detached_one(self) -> None:
        stored, lesson = self._bound_chat(status="detached")
        # The same chat re-attached to a new run: an older detached row plus a live one. Ordering
        # is what makes this a tutor chat rather than a coach chat.
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, stored_session_id, lesson_run_id,"
            " objective_id, status, revision, updated_at)"
            " SELECT 'bind_live_again', enrollment_id, profile, stored_session_id, lesson_run_id,"
            " objective_id, 'active', 1, ? FROM bindings WHERE stored_session_id = ? LIMIT 1",
            ("2026-11-07T12:30:00+00:00", stored),
        )
        self.assertEqual(lesson_skills.skill_for_session(stored)["skill"], lesson_skills.TUTOR_SKILL)


class AttachTest(unittest.TestCase):
    """``attach`` must never turn a block into a teaching turn, and never drop a gate's words."""

    def test_no_skill_leaves_the_hook_untouched(self) -> None:
        block = {"action": "block", "message": "stopped"}
        self.assertIs(lesson_skills.attach(block, None), block)
        self.assertIsNone(lesson_skills.attach(None, None))

    def test_a_skill_rides_on_an_empty_hook(self) -> None:
        out = lesson_skills.attach(None, lesson_skills.TUTOR_SKILL, "lesson_binding")
        self.assertIn("coursebook:lesson-tutoring", out["context"])
        self.assertIn('skill_view(name="coursebook:lesson-tutoring")', out["context"])

    def test_a_gate_context_keeps_its_own_words_after_the_instruction(self) -> None:
        hook = {"context": "Grade: not_yet. Ask one fresh check."}
        out = lesson_skills.attach(hook, lesson_skills.TUTOR_SKILL, "lesson_binding")
        self.assertTrue(out["context"].startswith("[Coursebook]"))
        self.assertTrue(out["context"].endswith("Ask one fresh check."))

    def test_a_block_is_not_annotated(self) -> None:
        block = {"action": "block", "message": "stopped"}
        self.assertEqual(lesson_skills.attach(block, lesson_skills.COACH_SKILL), block)

    def test_the_instruction_forbids_the_reference_answer_and_names_one_check(self) -> None:
        for skill in (lesson_skills.TUTOR_SKILL, lesson_skills.COACH_SKILL):
            text = lesson_skills.instruction(skill)
            self.assertIn("Never print the reference answer", text)
            self.assertIn("exactly one check", text)

    def test_the_generic_coach_is_not_japanese_specific(self) -> None:
        text = lesson_skills.instruction(lesson_skills.COACH_SKILL)
        for token in ("Japanese", "romaji", "furigana", "kana"):
            self.assertNotIn(token, text)


class BoundStoreTest(KernelCase):
    """H-69: two Coursebook stores on one machine, only one bound to this chat.

    The fix is (a) from the card — hand the resolved store to the turn instead of letting the
    skill probe candidate homes. So the proof is: the answer names the absolute DB the binding
    row came from, that DB really holds the bound ``objective_id``, a second store on the same
    filesystem does not, and nothing in the instruction points at it. When no store holds the
    bound objective the turn is told to stand down rather than fall back.
    """

    def setUp(self) -> None:
        super().setUp()
        hooks._TURNS.clear()
        hooks._GOVERNED.clear()
        hooks._SKILLS.clear()

    def _begin(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.begin",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"], "mode": "fresh"},
            idempotency_key=f"begin-{os.urandom(6).hex()}",
        )["result"]

    def _bound_chat(self, objective_id: str | None = None) -> tuple[str, dict]:
        lesson = self.prepare_lesson()
        run = self._begin(lesson)
        stored = "20261106_095109_eac24e"
        bindings.bind_session(
            stored_session_id=stored,
            enrollment_id=lesson["enrollment_id"],
            objective_id=objective_id or lesson["objective_id"],
            lesson_run_id=run["lesson_run_id"],
        )
        return stored, lesson

    def _foreign_store(self) -> Path:
        """A second, unrelated Coursebook home: its own DB, its own objective, its own chat."""
        other = Path(tempfile.mkdtemp(prefix="coursebook-other-home-"))
        self.addCleanup(shutil.rmtree, other, True)
        path = other / "plugin-data" / "coursebook" / "data.db"
        path.parent.mkdir(parents=True)
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE objectives (id TEXT PRIMARY KEY, title TEXT)")
            connection.execute(
                "CREATE TABLE bindings (id TEXT PRIMARY KEY, stored_session_id TEXT,"
                " objective_id TEXT, status TEXT)"
            )
            connection.execute(
                "INSERT INTO objectives VALUES ('obj_flat_repair_s1', 'Roadside flat repair - Section 1')"
            )
            connection.execute(
                "INSERT INTO bindings VALUES ('bind_other', '20261106_090000_other',"
                " 'obj_flat_repair_s1', 'active')"
            )
            connection.commit()
        finally:
            connection.close()
        return path

    def test_the_turn_names_the_store_that_holds_the_bound_objective(self) -> None:
        stored, lesson = self._bound_chat()
        foreign = self._foreign_store()
        answer = lesson_skills.skill_for_session(stored)
        own = db.store_root() / "data.db"

        self.assertEqual(answer["skill"], lesson_skills.TUTOR_SKILL)
        self.assertEqual(answer["reason"], lesson_skills.REASON_LIVE_BINDING)
        self.assertEqual(Path(answer["store_path"]), own.resolve())
        self.assertNotEqual(Path(answer["store_path"]), foreign.resolve())
        self.assertEqual(answer["objective_id"], lesson["objective_id"])
        self.assertTrue(answer["objective_in_store"])

        with db.read() as connection:
            bound_exists = connection.execute(
                "SELECT 1 FROM objectives WHERE id = ?", (lesson["objective_id"],)
            ).fetchone()
        self.assertIsNotNone(bound_exists, "the named store is the one that holds the bound objective")
        foreign_db = sqlite3.connect(foreign)
        try:
            foreign_has_bound = foreign_db.execute(
                "SELECT 1 FROM objectives WHERE id = ?", (lesson["objective_id"],)
            ).fetchone()
        finally:
            foreign_db.close()
        self.assertIsNone(foreign_has_bound, "the other store does not hold the bound objective")

        text = lesson_skills.instruction(
            str(answer["skill"]), str(answer["reason"]), store_path=answer["store_path"],
            objective_id=answer["objective_id"],
        )
        self.assertIn(str(own.resolve()), text)
        self.assertIn(lesson["objective_id"], text)
        self.assertNotIn(str(foreign.resolve()), text, "a turn must never be pointed at another home")
        self.assertIn("Never print the reference answer", text)

    def test_a_live_binding_with_no_objective_in_the_store_stands_down(self) -> None:
        # A live binding that carries no objective is exactly the "no stored content" state:
        # there is no second store to fall back to, and the turn must say so.
        stored, _lesson = self._bound_chat()
        self.execute("UPDATE bindings SET objective_id = NULL WHERE stored_session_id = ?", (stored,))
        foreign = self._foreign_store()

        answer = lesson_skills.skill_for_session(stored)
        self.assertEqual(answer["reason"], lesson_skills.REASON_BOUND_OBJECTIVE_MISSING)
        self.assertEqual(answer["skill"], lesson_skills.TUTOR_SKILL)
        text = lesson_skills.instruction(
            str(answer["skill"]), str(answer["reason"]), store_path=answer["store_path"],
            objective_id=answer["objective_id"], binding_id=answer["binding_id"],
        )
        self.assertIn("no stored content", text)
        self.assertIn("Do not teach any section", text)
        self.assertIn("do not read any other Coursebook store", text)
        self.assertNotIn(str(foreign.resolve()), text)

    def test_an_objective_row_missing_from_the_store_stands_down(self) -> None:
        # A dangling binding (FKs off, as a foreign writer could leave it) is the same state:
        # the store is real, the objective is not in it, so nothing may be taught from elsewhere.
        stored, lesson = self._bound_chat()
        raw = sqlite3.connect(db.store_root() / "data.db")
        try:
            raw.execute("DELETE FROM objectives WHERE id = ?", (lesson["objective_id"],))
            raw.commit()
        finally:
            raw.close()
        answer = lesson_skills.skill_for_session(stored)
        self.assertEqual(answer["reason"], lesson_skills.REASON_BOUND_OBJECTIVE_MISSING)
        self.assertFalse(answer["objective_in_store"])
        self.assertEqual(answer["objective_id"], lesson["objective_id"])

    def test_the_bound_turn_carries_the_store_path_and_objective(self) -> None:
        stored, lesson = self._bound_chat()
        hook = hooks.pre_llm_call(session_id=stored, user_message="What am I practising here?")
        self.assertIsNotNone(hook)
        self.assertIn(str((db.store_root() / "data.db").resolve()), hook["context"])
        self.assertIn(lesson["objective_id"], hook["context"])
        self.assertIn("Do not probe, glob, or open any other Coursebook store", hook["context"])

    def test_the_coach_turn_is_not_pointed_at_a_store(self) -> None:
        stored, _lesson = self._bound_chat()
        self.execute("UPDATE bindings SET status = 'detached' WHERE stored_session_id = ?", (stored,))
        answer = lesson_skills.skill_for_session(stored)
        self.assertEqual(answer["skill"], lesson_skills.COACH_SKILL)
        self.assertIsNone(answer["store_path"], "a chat with no live run has no lesson store to read")


class HookWiringTest(KernelCase):
    """The real hook: a bound lesson turn carries the skill; an ordinary chat returns nothing."""

    def setUp(self) -> None:
        super().setUp()
        hooks._TURNS.clear()
        hooks._GOVERNED.clear()
        hooks._SKILLS.clear()

    def test_a_bound_lesson_turn_carries_the_tutor_instruction(self) -> None:
        lesson = self.prepare_lesson()
        run = self._begin(lesson)
        stored = "20261107_121500_def456"
        bindings.bind_session(
            stored_session_id=stored,
            enrollment_id=lesson["enrollment_id"],
            objective_id=lesson["objective_id"],
            lesson_run_id=run["lesson_run_id"],
        )
        hook = hooks.pre_llm_call(
            session_id=stored, user_message="What am I practising here?", is_first_turn=True
        )
        self.assertIsNotNone(hook, "a bound lesson turn must be told which skill to load")
        self.assertIn("coursebook:lesson-tutoring", hook["context"])

    def test_an_ordinary_chat_in_the_same_profile_gets_no_instruction(self) -> None:
        lesson = self.prepare_lesson()
        run = self._begin(lesson)
        bindings.bind_session(
            stored_session_id="20261107_121600_aaa111",
            enrollment_id=lesson["enrollment_id"],
            objective_id=lesson["objective_id"],
            lesson_run_id=run["lesson_run_id"],
        )
        hook = hooks.pre_llm_call(session_id="20261107_090000_unrelated", user_message="write me a poem")
        self.assertIsNone(hook)

    def test_the_decision_is_logged_once_for_a_reviewer(self) -> None:
        stored, _lesson = self._bound_chat()
        with self.assertLogs("coursebook", level="INFO") as logs:
            hooks.pre_llm_call(session_id=stored, user_message="hint please")
            hooks.pre_llm_call(session_id=stored, user_message="another hint")
        self.assertEqual(
            sum("coursebook lesson skill" in line for line in logs.output), 1,
            "the load is evidence: state it once, not on every turn",
        )

    def _begin(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.begin",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"], "mode": "fresh"},
            idempotency_key=f"begin-{os.urandom(6).hex()}",
        )["result"]

    def _bound_chat(self) -> tuple[str, dict]:
        lesson = self.prepare_lesson()
        run = self._begin(lesson)
        stored = "20261107_121700_bbb222"
        bindings.bind_session(
            stored_session_id=stored,
            enrollment_id=lesson["enrollment_id"],
            objective_id=lesson["objective_id"],
            lesson_run_id=run["lesson_run_id"],
        )
        return stored, lesson


class LoaderTest(unittest.TestCase):
    """Registration: both names reach the host, an old host survives, nothing collides with a user."""

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "coursebook_plugin_entry_lesson_skills",
            ROOT / "__init__.py",
            submodule_search_locations=[str(ROOT)],
        )
        assert spec and spec.loader
        cls.plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.plugin
        spec.loader.exec_module(cls.plugin)

    def _ctx(self):
        class Ctx:
            def __init__(self) -> None:
                self.skills: list[tuple[str, Path]] = []

            def register_skill(self, name, path) -> None:  # noqa: ANN001 - SDK shape
                self.skills.append((name, path))

        return Ctx()

    def test_both_bundled_skills_reach_the_loader_under_namespaced_names(self) -> None:
        ctx = self._ctx()
        self.plugin._register_bundled_skills(ctx)
        registered = {f"coursebook:{name}" for name, _ in ctx.skills}
        self.assertEqual(registered, {"coursebook:lesson-tutoring", "coursebook:learner-coach"})

    def test_the_host_derives_the_namespace_so_a_bare_name_is_what_we_register(self) -> None:
        ctx = self._ctx()
        self.plugin._register_bundled_skills(ctx)
        for name, _path in ctx.skills:
            self.assertNotIn(":", name, "the host rejects a colon; the plugin name is the namespace")

    def test_a_host_without_the_skill_api_still_registers(self) -> None:
        self.plugin._register_bundled_skills(object())

    def test_plugin_names_cannot_collide_with_a_user_skill_directory(self) -> None:
        # The host qualifies a plugin skill as ``<plugin>:<name>``, so a user's own
        # ``~/.hermes/skills/learner-coach`` stays a different, unqualified skill.
        home = Path(os.environ.get("HOME") or "/root")
        user_skill = home / ".hermes" / "skills" / "learner-coach" / "SKILL.md"
        ctx = self._ctx()
        self.plugin._register_bundled_skills(ctx)
        for _name, path in ctx.skills:
            self.assertNotEqual(path.resolve(), user_skill.resolve())
            self.assertIn("skills", path.parts)
            self.assertEqual(path.parent.name, "learner-coach" if "learner-coach" in str(path) else "lesson-tutoring")

    def test_the_registered_paths_are_real_skill_files(self) -> None:
        ctx = self._ctx()
        self.plugin._register_bundled_skills(ctx)
        for _name, path in ctx.skills:
            self.assertTrue(path.is_file())
            self.assertEqual(path.name, "SKILL.md")


if __name__ == "__main__":
    unittest.main()
