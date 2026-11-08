"""H-86: first-run wayfinding and one next action, guarded structurally.

These are source and static-render assertions. They prove what the shipped module contains and
what a server render of the start plate reads; they do **not** prove a live Desktop window paints
it (the live evidence lives in ``docs/UX-WAYFINDING-V2.md``).
"""

from __future__ import annotations

import re
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"


class StartPlateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_plate_opens_on_the_question_with_no_eyebrow(self) -> None:
        start = self.source.index("function FirstRun({")
        end = self.source.index("function onImportPlaceholder()")
        body = self.source[start:end]
        self.assertNotIn("DeskLabel", body)
        self.assertIn("'data-cb-first-run-title'", body)
        self.assertIn("children: FIRST_RUN_COPY.title", body)
        self.assertEqual(body.count("variant: 'default'"), 1, body)

    def test_plate_is_a_flat_field_not_a_thick_bar(self) -> None:
        start = self.source.index("function FirstRun({")
        end = self.source.index("function onImportPlaceholder()")
        body = self.source[start:end]
        self.assertNotIn("3px", body)
        self.assertIn("borderTop: '1px solid var(--cb-lamp)'", body)

    def test_no_onboarding_by_overlay(self) -> None:
        for banned in ("role: 'dialog'", "coachMark", "coach_mark", "ThemePicker", "welcomeTour"):
            self.assertNotIn(banned, self.source)


class WayfindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_destination_nav_states_the_current_section(self) -> None:
        start = self.source.index("function CbDestinationNav(")
        end = self.source.index("function CoursebookPane()")
        body = self.source[start:end]
        self.assertIn("DESTINATIONS.map", body)
        self.assertIn("'aria-current': current ? 'page' : undefined", body)
        # A non-colour cue: weight plus a lamp underline, not a fill alone.
        self.assertIn("fontWeight: current ? 600 : 400", body)
        self.assertIn("borderBottom: current ? '2px solid var(--cb-lamp)'", body)
        self.assertIn("jsx(CbDestinationNav, { value: destination, onChange: changeDestination })", self.source)
        self.assertNotIn("options: DESTINATIONS,\n                sizing: 'content'", self.source)

    def test_new_course_is_secondary_and_yields_to_a_course(self) -> None:
        self.assertIn(
            "destination === 'courses' && canCreate && !coursesEmpty && !openCourse",
            self.source,
        )
        line = [
            value
            for value in self.source.splitlines()
            if "children: 'New course'" in value
        ]
        self.assertEqual(len(line), 1, line)
        nearby = self.source[self.source.index("children: 'New course'") - 220 : self.source.index("children: 'New course'")]
        self.assertIn("variant: 'secondary'", nearby)
        self.assertNotIn("variant: 'default', children: 'New course'", self.source)

    def test_host_entry_opens_the_route_and_carries_the_seal(self) -> None:
        self.assertIn("data: { path: ROUTE_PATH, label: ROUTE_TITLE, codicon: 'book' }", self.source)
        header = self.source[self.source.index("'data-cb-route': ROUTE_PATH") :]
        header = header[: header.index("PageBody")]
        self.assertIn("SurveyMark", header)
        self.assertIn("children: ROUTE_TITLE", header)
        # The header no longer explains the UI in a second line.
        self.assertNotIn("Pick up where you left off", self.source)


class LessonStartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def _section_actions(self) -> str:
        start = self.source.index("'data-cb-section-actions'")
        return self.source[start : start + 1400]

    def test_section_has_exactly_one_start_button(self) -> None:
        block = self._section_actions()
        self.assertEqual(block.count("sdk.Button"), 1, block)
        self.assertNotIn("Start a fresh run instead", self.source)

    def test_no_chat_sentence_and_action_agree_with_the_desk(self) -> None:
        self.assertIn(
            "This section has no lesson chat yet. Start one and send the first message to begin.",
            self.source,
        )
        self.assertIn("children: busy ? 'Opening the lesson' : bindingActive ? 'Continue in the lesson chat' : 'Start a fresh run'", self.source)
        self.assertIn("start_lesson: 'Start a fresh run'", self.source)
        # The detached notice is not hidden behind a runtime read succeeding.
        self.assertIn("        !bindingActive\n          ? jsx('div', {", self.source)

    def test_learner_copy_has_no_internal_vocabulary(self) -> None:
        # Source comments and diagnostics keep the machine words on purpose; the copy a learner can
        # read is the four blocks below plus the section sentence.
        blocks = []
        for marker, stop in (
            ("const FIRST_RUN_COPY = {", "\n}\n"),
            ("const CREATE_RESULT_COPY = {", "\n}\n"),
            ("const CREATE_STEP_SPINE = Object.freeze([", "\n])\n"),
        ):
            start = self.source.index(marker)
            blocks.append(self.source[start : self.source.index(stop, start) + len(stop)])
        blocks.append("This section has no lesson chat yet. Start one and send the first message to begin.")
        copy_text = "\n".join(blocks).lower()
        banned = (
            "durable chat",
            "chat binding",
            "session id",
            "evidence target",
            "projection",
            "not_started",
            "in_progress",
            "needs_review",
            "model_assessed",
            "learn more",
            "get started",
            "click here",
        )
        for word in banned:
            self.assertNotIn(word, copy_text, word)
        for raw_enum in ("one_off", "self_check", "companion"):
            self.assertNotIn(raw_enum, copy_text, raw_enum)


class CreateFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_each_step_names_what_happens_next(self) -> None:
        start = self.source.index("const CREATE_STEP_SPINE")
        block = self.source[start : start + 400]
        self.assertEqual(block.count("next:"), 3, block)
        self.assertIn("Create the course, then review the draft plan.", block)

    def test_review_step_does_not_imply_lessons_exist(self) -> None:
        self.assertIn("no lesson is written until you do", self.source)
        self.assertIn("Approve the plan to start the first lesson", self.source)

    def test_course_name_is_marked_required(self) -> None:
        self.assertIn("children: 'Name this course (required)'", self.source)


if __name__ == "__main__":
    unittest.main()
