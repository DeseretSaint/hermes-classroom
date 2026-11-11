"""GM-010 — Game mode's play layer: XP, cosmetic level, `Game progress` and the field journal.

Two kinds of proof:

* the shipped module is rendered through React (``renderToStaticMarkup``, the same jsdom-free
  harness the GM-006/GM-008 cards use) and the composed DOM is asserted: the chip and bar come from
  ``engagement.read`` verbatim, the play layer disappears when the learner turns feedback off, the
  bar is labelled as play progress and never as mastery, and the collectible cards are stamped only
  by recorded evidence;
* the module source is scanned for the two things a render cannot show: the play layer is mounted
  only behind a Game-course gate, and the renderer never computes XP or calls ``engagement.award``.

What this does not prove: pixels against the approved concept frames, or the live packet. The
isolated rig and ``docs/visual-review/gm-010/`` carry those.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The shared stub has no ToggleRow and drops inline style. This card renders the settings sheet and
# reads the header's own geometry, so both are added here instead of changing the shared stub that
# several unrelated suites pin.
TOGGLE_ANCHOR = "export const SandboxedFrame = () => null"
TOGGLE_NEW = """export const ToggleRow = (props) =>
  el('div', { 'data-cb-settings-toggle-row': props.checked ? 'on' : 'off' }, [
    el('span', { key: 'label' }, props.label),
    el('span', { key: 'description' }, props.description || null),
    el('input', {
      key: 'switch',
      type: 'checkbox',
      checked: Boolean(props.checked),
      disabled: Boolean(props.disabled),
      'aria-label': props.label,
      onChange: () => props.onChange && props.onChange(!props.checked)
    })
  ])
export const SandboxedFrame = () => null"""

GM010_SDK_STUB = SDK_STUB.replace(
    "  if (props.title) attrs.title = props.title",
    "  if (props.title) attrs.title = props.title\n  if (props.style) attrs.style = props.style",
).replace(TOGGLE_ANCHOR, TOGGLE_NEW)
assert "ToggleRow" in GM010_SDK_STUB and "attrs.style = props.style" in GM010_SDK_STUB

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import {
  GameHeader,
  GameJournal,
  HomeSettingsSheet,
  CB_GAME_PROGRESS_NOTE,
  CB_HOME_PREF_DEFAULTS,
  cbGameCourse,
  cbGameFeedbackVisible,
  cbGameSectionCards
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const quiet = () => {}
const out = (node) => process.stdout.write(renderToStaticMarkup(node))

if (payload.kind === 'header') {
  out(React.createElement(GameHeader, {
    engagement: payload.engagement,
    status: payload.status || 'ready',
    error: payload.error || null,
    prefs: payload.prefs || {},
    onRetry: quiet
  }))
} else if (payload.kind === 'journal') {
  out(React.createElement(GameJournal, { objectives: payload.objectives || [] }))
} else if (payload.kind === 'settings') {
  out(React.createElement(HomeSettingsSheet, {
    open: true,
    prefs: { ...CB_HOME_PREF_DEFAULTS, ...(payload.prefs || {}) },
    classroom: null,
    onUpdate: quiet,
    onReset: quiet,
    onClose: quiet
  }))
} else if (payload.kind === 'guard') {
  out(React.createElement('div', {
    'data-course': String(cbGameCourse(payload.row, payload.mode)),
    'data-visible': String(cbGameFeedbackVisible(payload.prefs, payload.engagement)),
    'data-note': CB_GAME_PROGRESS_NOTE,
    'data-cards': JSON.stringify(cbGameSectionCards(payload.objectives || []))
  }))
}
"""


def engagement(**overrides) -> dict:
    """One `engagement.read` answer, shaped exactly like the v24 contract requires."""
    payload = {
        "xp_total": 245,
        "level": {
            "level": 3,
            "title": "Pathfinder",
            "xp_into_level": 45,
            "xp_for_next_level": 100,
            "is_cosmetic": True,
        },
        "progress": {
            "label": "Game progress",
            "is_play_progress": True,
            "assigned_steps": 8,
            "completed_steps": 5,
            "feedback_visible": True,
        },
        "recent_events": [
            {
                "action_kind": "check_submitted",
                "action_id": "att_0123456789abcdef",
                "points": 20,
                "level_after": 3,
                "created_at": "2026-11-09T10:00:00Z",
            }
        ],
    }
    payload.update(overrides)
    return payload


def objective(objective_id: str, ordinal: int, state: str, independent: bool) -> dict:
    return {
        "objective_id": objective_id,
        "title": f"Section {ordinal} title",
        "ordinal": ordinal,
        "state": state,
        "independent": independent,
    }


OBJECTIVES = [
    objective("obj_0000000000000001", 1, "independent_evidence", True),
    objective("obj_0000000000000002", 2, "independent_evidence", True),
    objective("obj_0000000000000003", 3, "introduced", False),
    objective("obj_0000000000000004", 4, "not_started", False),
]


class _Rig:
    def __init__(self) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-gm010-")
        self.root = Path(self.tmp.name)
        (self.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "static.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = self.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(GM010_SDK_STUB, encoding="utf-8")

    def render(self, payload: dict) -> str:
        import subprocess

        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "static.mjs"), str(case)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(f"render failed: {result.stderr or result.stdout}")
        return result.stdout


class GameEngagementUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rig = _Rig()
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def header(self, **payload) -> str:
        return self.rig.render({"kind": "header", **payload})

    def test_game_header_only_in_game(self) -> None:
        guard = self.rig.render(
            {
                "kind": "guard",
                "row": {"course_id": "crs_gm010", "presentation_mode": "game", "recipe": "adult"},
                "mode": "game",
                "engagement": engagement(),
                "prefs": {},
                "objectives": OBJECTIVES,
            }
        )
        self.assertIn('data-course="true"', guard)
        self.assertIn('data-visible="true"', guard)
        for payload in (
            {"row": {"recipe": "adult"}, "mode": "textbook"},
            {"row": {"recipe": "adult"}, "mode": None},
            # A row that claims Game in a field a library row does not carry, with no mode read,
            # must still paint nothing: the mode read is the only mode.
            {"row": {"presentation_mode": "game", "recipe": "adult"}, "mode": None},
            {"row": {"recipe": "parent"}, "mode": "game"},
            {"row": {}, "mode": "game"},
        ):
            with self.subTest(payload=payload):
                text = self.rig.render(
                    {"kind": "guard", "engagement": engagement(), "prefs": {}, **payload}
                )
                self.assertIn('data-course="false"', text)

        html = self.header(engagement=engagement())
        self.assertIn('data-cb-game="ready"', html)
        self.assertIn("Game progress", html)
        # The play layer is READ in three places and MOUNTED in two. Three surfaces call
        # `engagement.read`: the course home (FieldDeskHome), the v3 classroom's Game rail
        # (ClassroomV3Surface, CP-023) and the course detail (CourseDetail). Only two of them
        # render GameHeader: the course home and CourseDetail's Game overview. The classroom rail
        # reads the engagement row for its own challenge/XP block and never mounts this header,
        # and CourseDetail's mount is gated on `view === 'overview'`, so no textbook surface can
        # reach it.
        mounts = re.findall(r"jsxs?\(\s*GameHeader,", self.source)
        self.assertEqual(
            len(mounts), 2, "GameHeader must be mounted in two places and read in three"
        )
        self.assertEqual(self.source.count("useRpcQuery(\n    'engagement.read'"), 3)
        self.assertIn("mode === 'game' && Boolean(courseId) && Boolean(enrollmentId)", self.source)
        self.assertNotIn("engagement.award", self.source)
        # The FieldDeskHome mount is unconditional inside `gameCourse`, and the CourseDetail mount
        # adds the view gate: overview only.
        self.assertIn("const gameCourse = cbGameCourse(desk.row, courseMode)", self.source)
        self.assertIn("courseGame && view === 'overview'", self.source)

    def test_game_xp_not_in_textbook(self) -> None:
        def body(name: str) -> str:
            start = self.source.index(f"function {name}(")
            rest = self.source[start + 10 :]
            nxt = re.search(r"\nfunction ", rest)
            return rest[: nxt.start()] if nxt else rest

        for name in ("TextbookView", "SectionPage", "NotebookView", "QuizzesView"):
            with self.subTest(view=name):
                text = body(name)
                for forbidden in ("GameHeader", "GameJournal", "engagement.read", " XP", "Game progress"):
                    self.assertNotIn(forbidden, text, f"{name} must stay free of game chrome")

        # And the component itself paints nothing for a course that is not in Game mode.
        guard = self.rig.render(
            {
                "kind": "guard",
                "row": {"presentation_mode": "textbook"},
                "engagement": engagement(),
                "prefs": {},
            }
        )
        self.assertIn('data-course="false"', guard)

    def test_game_feedback_toggle(self) -> None:
        shown = self.header(engagement=engagement())
        self.assertIn('data-cb-game="ready"', shown)
        self.assertIn("245 XP", shown)

        # 1. the learner's own switch on this device
        hidden = self.header(engagement=engagement(), prefs={"gameFeedback": False})
        self.assertEqual(hidden.strip(), "")

        # 2. the backend's profile setting, reported by the read itself
        backend_off = engagement()
        backend_off["progress"] = {**backend_off["progress"], "feedback_visible": False}
        self.assertEqual(self.header(engagement=backend_off).strip(), "")

        # 3. the setting exists, reads on, and reads off — a real toggle, not a label
        on = self.rig.render({"kind": "settings", "prefs": {"gameFeedback": True}})
        self.assertIn("Game feedback", on)
        self.assertIn("Show Game feedback", on)
        self.assertIn('data-cb-settings-toggle="game-feedback"', on)
        self.assertIn('data-cb-settings-toggle-row="on"', on)
        off = self.rig.render({"kind": "settings", "prefs": {"gameFeedback": False}})
        self.assertIn('data-cb-settings-toggle-row="off"', off)

        # The SDK switch is a black box that paints only its on/off colour, and the host reset
        # clears the UA ring. The wrapper therefore owns the keyboard ring: assert the row tracks
        # focus, paints the identity ring from that state, and is unpainted at rest.
        self.assertIn("'data-cb-settings-focus'", self.source)
        self.assertIn("outline: gameFeedbackFocused ? CB_FOCUS_RING : 'none'", self.source)
        self.assertIn("setGameFeedbackFocused(focusRingVisible(event.target))", self.source)
        self.assertIn("outline:none", on.replace(" ", ""))
        self.assertNotIn("outline:2px", on.replace(" ", ""))

    def test_game_progress_not_mastery_label(self) -> None:
        html = self.header(engagement=engagement())
        self.assertIn("Game progress", html)
        self.assertIn("Play progress, not evidence.", html)
        self.assertIn("cosmetic", html)
        self.assertIn("5 of 8 steps", html)
        self.assertIn('aria-valuenow="5"', html)
        self.assertIn('aria-valuemax="8"', html)
        lowered = html.lower()
        for forbidden in ("mastery", "mastered", "proficien", "verified skill", "skill level", "grade", "score"):
            self.assertNotIn(forbidden, lowered, f"the play layer must not claim {forbidden!r}")

        # A re-plan can leave more completed steps than assigned ones; the bar must not print a
        # ratio above its own maximum or imply a score.
        odd = engagement()
        odd["progress"] = {**odd["progress"], "assigned_steps": 3, "completed_steps": 7}
        over = self.header(engagement=odd)
        self.assertIn('aria-valuenow="3"', over)
        self.assertIn("3 of 3 steps", over)

        # Zero assigned steps paints no bar and says so; it never draws an empty fake frame.
        empty = engagement()
        empty["progress"] = {**empty["progress"], "assigned_steps": 0, "completed_steps": 0}
        zero = self.header(engagement=empty)
        self.assertIn("No steps assigned yet", zero)
        self.assertNotIn("progressbar", zero)

    def test_no_fake_stars_or_ratings(self) -> None:
        header = self.header(engagement=engagement())
        journal = self.rig.render({"kind": "journal", "objectives": OBJECTIVES})
        both = header + journal
        for forbidden in ("★", "☆", "star rating", "5 stars", "rating", "review count", "reviews", "out of 5"):
            self.assertNotIn(forbidden, both, f"no invented {forbidden!r} may reach the page")

        # The cards are exactly the outline's sections, and exactly the sections with recorded
        # independent evidence are stamped.
        self.assertEqual(journal.count("data-cb-game-card="), len(OBJECTIVES))
        self.assertEqual(journal.count('data-cb-game-card="earned"'), 2)
        self.assertIn('data-cb-game-journal="2"', journal)
        self.assertIn("2 of 4 sections stamped by recorded evidence.", journal)
        self.assertEqual(journal.count(">Stamped<"), 2)
        # An unearned card names its real state instead of a number or a star.
        self.assertIn("Started", journal)
        self.assertIn("Not started", journal)

        guard = self.rig.render(
            {
                "kind": "guard",
                "row": {"presentation_mode": "game"},
                "engagement": engagement(),
                "prefs": {},
                "objectives": OBJECTIVES,
            }
        )
        match = re.search(r'data-cards="(.*?)"', guard)
        self.assertIsNotNone(match)
        cards = json.loads(match.group(1).replace("&quot;", '"'))  # type: ignore[union-attr]
        self.assertEqual(len(cards), len(OBJECTIVES))
        self.assertEqual(sum(1 for card in cards if card["earned"]), 2)


if __name__ == "__main__":
    unittest.main()
