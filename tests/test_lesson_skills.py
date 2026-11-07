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
import sys
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
