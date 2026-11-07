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


if __name__ == "__main__":
    unittest.main()
