"""The plugin ships its learner skills without depending on a user skill directory."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BundledSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location(
            "coursebook_plugin_entry",
            ROOT / "__init__.py",
            submodule_search_locations=[str(ROOT)],
        )
        assert spec and spec.loader
        cls.plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.plugin
        spec.loader.exec_module(cls.plugin)

    def test_the_entry_point_registers_each_bundled_skill_under_its_own_name(self) -> None:
        class Ctx:
            def __init__(self) -> None:
                self.skills = []

            def register_skill(self, name, path) -> None:  # noqa: ANN001 - SDK shape
                self.skills.append((name, path))

        ctx = Ctx()
        self.plugin._register_bundled_skills(ctx)
        names = {name for name, _ in ctx.skills}
        self.assertEqual(names, {"learner-coach", "lesson-tutoring"})
        for name, path in ctx.skills:
            self.assertEqual(path.name, "SKILL.md")
            self.assertIn(name, path.parent.name)

    def test_a_host_without_the_skill_api_still_registers(self) -> None:
        self.plugin._register_bundled_skills(object())

    def test_the_bundled_skills_are_subject_neutral(self) -> None:
        text = (ROOT / "skills" / "learner-coach" / "SKILL.md").read_text(encoding="utf-8")
        for token in ("technical", "language", "quantitative", "parent-led"):
            self.assertIn(token, text.lower())
        self.assertNotIn("Japanese affection", text)

    def _skill_text(self, name: str) -> str:
        return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_the_tutor_skill_documents_the_no_check_reply_path(self) -> None:
        # H-113: a section may have zero checks by design; "read the check" would send the tutor
        # looking for a graded item that does not exist, and inventing one is worse.
        text = self._skill_text("lesson-tutoring")
        for token in (
            "assessment='none'",
            "no `checks` row",
            "evidence_criteria_json",
            "bound_objective_not_in_store",
            "one short",
            "answer format",
        ):
            self.assertIn(token, text)
        self.assertIn("Never invent", text)
        self.assertIn("never report the plugin as broken", text)

    def test_the_tutor_skill_names_the_injected_store_and_no_other_home(self) -> None:
        text = self._skill_text("lesson-tutoring")
        self.assertIn("absolute", text)
        self.assertIn("data.db", text)
        self.assertIn("objective_id", text)
        self.assertIn("sibling", text)

    def test_the_coach_skill_names_the_injected_store_and_the_no_check_path(self) -> None:
        text = self._skill_text("learner-coach")
        self.assertIn("data.db", text)
        self.assertIn("objective_id", text)
        self.assertIn("bound_objective_not_in_store", text)
        self.assertIn("no check", text.lower())
        self.assertIn("evidence_criteria_json", text)
        self.assertIn("one short line", text)

    def test_neither_bundled_skill_assumes_one_subject(self) -> None:
        # The tutor serves every course, so no bundled procedure may hard-code a language.
        for name in ("lesson-tutoring", "learner-coach"):
            text = self._skill_text(name).lower()
            for token in ("japanese", "romaji", "furigana", "kana"):
                self.assertNotIn(token, text, f"{name} is not subject-neutral")


if __name__ == "__main__":
    unittest.main()
