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
        self.assertEqual(body.count("variant: 'primary'"), 1, body)

    def test_plate_is_a_flat_field_not_a_thick_bar(self) -> None:
        start = self.source.index("function FirstRun({")
        end = self.source.index("function onImportPlaceholder()")
        body = self.source[start:end]
        self.assertNotIn("3px", body)
        self.assertIn("borderTop: '1px solid var(--cb-lamp)'", body)

    def test_no_onboarding_by_overlay(self) -> None:
        start = self.source.index("function FirstRun({")
        end = self.source.index("function onImportPlaceholder()")
        plate = self.source[start:end]
        # H-147 owns one user-invoked settings sheet: role="dialog", mounted only while `open`
        # (HomeSettingsSheet returns null when closed), with its own focus trap and Escape close.
        # That is a settings surface, not onboarding, so the overlay ban is scoped to the start
        # plate while the onboarding artifacts stay banned module-wide.
        self.assertNotIn("role: 'dialog'", plate)
        for banned in ("coachMark", "coach_mark", "ThemePicker", "welcomeTour"):
            self.assertNotIn(banned, self.source)
        self.assertIn("if (!open) return null", self.source)


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
        # GM-002: the course home is a step inside Home, so the nav also gets the way back to the
        # library when Home is already current.
        # The nav is keyed because its siblings are a children array; the key is presentational,
        # so the assertion pins the props and accepts the optional third argument.
        self.assertRegex(
            self.source,
            r"jsx\(CbDestinationNav, \{ value: destination, onChange: changeDestination, onHome: closeCourseHome \}(?:, '[^']+')?\)",
        )
        self.assertNotIn("options: DESTINATIONS,\n                sizing: 'content'", self.source)

    def test_new_course_is_the_catalog_primary_and_yields_to_a_course(self) -> None:
        # H-160: UX_SPEC §4 names Courses' page-header primary as **New course**. H-151 measured
        # the catalog at `primaryCount: 0` because this call site was still `secondary`; the yield
        # rule below is unchanged, so an open course (or the welcome) still owns the only primary.
        self.assertIn(
            "destination === 'courses' && canCreate && !coursesEmpty && !openCourse",
            self.source,
        )
        # H-176 added a *secondary* "New course" control on the "Your other classrooms" shelf, so
        # counting every literal would now fail while the invariant it protects still holds: the
        # page header carries exactly one primary, and the shelf control is not it.
        primary = [value for value in self.source.splitlines() if "children: 'New course'" in value and "variant: 'primary'" in value]
        self.assertEqual(len(primary), 1, primary)
        shelf = [
            value
            for value in self.source.splitlines()
            if "children: 'New course'" in value and "variant: 'primary'" not in value and "data-cb-home-scene-tag" not in value
        ]
        self.assertEqual(len(shelf), 1, shelf)
        # CP-053: the wide scene's paper tag is a second "New course" surface, but it is a hooked
        # scene object, not a catalog control — the shelf still carries exactly one. Its label is
        # the deck's own `home.tag.firstuse` row, so the pin is the constant, not a string literal.
        self.assertIn("'data-cb-home-scene-tag': '', children: CB_HOME_V3_COPY.tagNew", self.source)
        self.assertIn("  tagNew: 'New course',", self.source)
        self.assertIn("'data-cb-shelf-new-course'", self.source)
        self.assertIn("variant: 'primary', children: 'New course'", self.source)
        self.assertNotIn("variant: 'default', children: 'New course'", self.source)

    def test_host_entry_opens_the_route_and_carries_the_wordmark(self) -> None:
        self.assertIn("data: { path: ROUTE_PATH, label: ROUTE_TITLE, codicon: 'book' }", self.source)
        header = self.source[self.source.index("'data-cb-route': ROUTE_PATH") :]
        header = header[: header.index("PageBody")]
        # H-145: the chrome carries the product name as type, never the seal.
        self.assertIn("CoursebookWordmark", header)
        self.assertNotIn("SurveyMark", header)
        # H-92: the route header's heading is the destination's page title, so the first heading a
        # reader sees is the page they are on; the sidebar still registers ROUTE_TITLE above.
        self.assertIn("children: pageTitle", header)
        self.assertNotIn("children: ROUTE_TITLE", header)
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
        self.assertEqual(block.count("jsx(CbAction"), 1, block)
        self.assertNotIn("Start a fresh run instead", self.source)

    def test_no_chat_sentence_and_action_agree_with_the_desk(self) -> None:
        self.assertIn(
            "This section has no lesson chat yet. Start one and send the first message to begin.",
            self.source,
        )
        self.assertIn("children: busy ? 'Opening the lesson' : bindingActive ? 'Continue in the lesson chat' : 'Start a fresh run'", self.source)
        self.assertIn("start_lesson: 'Start a fresh run'", self.source)
        # The detached notice is not hidden behind a runtime read succeeding. H-174 also gates it on
        # a readable approved page, so a section whose page the lessons job has not written yet is
        # explained by the readiness panel instead of by a chat sentence.
        self.assertIn("        !bindingActive && pageReadable\n          ? jsx('div', {", self.source)

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

    def test_course_name_is_optional_and_suggested(self) -> None:
        self.assertIn("children: 'Name (optional)'", self.source)
        self.assertIn('data-cb-title-disclosure', self.source)
        self.assertNotIn("Name this course (required)", self.source)


if __name__ == "__main__":
    unittest.main()
