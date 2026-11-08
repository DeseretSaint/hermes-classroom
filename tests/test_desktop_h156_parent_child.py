"""H-156 — parent and child defaults.

The card's shape: a parent prepares a lesson for a child, and the learner home stays a learner
home. Parent-authored rows are a different destination, child-facing defaults carry no loss,
ranking, loot or XP pressure, the session length is a parent-set number, and Parent Studio says
"prepare a lesson for a child" rather than offering a child chat.

Nothing here invents a child profile: the settings are the existing per-profile device document
(H-147) plus one session length, and the parent surfaces are the shipped ones. The live frames in
`docs/h156-shots/` prove the painted result; these tests prove the rules and the copy.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from tests.test_desktop_h147_home_settings import Harness, row

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_TEXT = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")


def parent_row(**overrides) -> dict:
    """A parent-authored row: a lesson plan for a child, never a learner classroom."""
    base = row(
        enrollment_id="enr_parent0000000001",
        course_id="crs_parent0000000001",
        title="Fractions for a 9-year-old",
        recipe="parent",
        # Newer than the learner row on purpose: recency must not sneak it into the rail.
        updated_at="2026-11-07T09:00:00.000000+00:00",
        next_step={"kind": "review_plan", "label": "Parent pack awaiting review"},
        evidence_summary={
            "independent": 0,
            "review_due": 0,
            "total_objectives": 4,
            "current_objective_id": "obj_parent000000001",
        },
    )
    base.update(overrides)
    return base


MODEL_HARNESS = r"""
import fs from 'node:fs'
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')
const hub = mod.hubSlots(payload.rows)
process.stdout.write(
  JSON.stringify({
    slotIds: hub.slots.map((slot) => slot.course_id),
    allIds: hub.all.map((slot) => slot.course_id),
    total: hub.total,
    rowTotal: hub.rowTotal,
    selected: (mod.selectedHubSlot(hub, payload.selected || null) || {}).course_id || null,
    clean: mod.sanitizeCbHomePrefs(payload.raw)
  })
)
"""


class HubModelTest(Harness):
    """Parent rows never become learner classrooms — proved on the shipped projection."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        (cls.root / "model.mjs").write_text(MODEL_HARNESS, encoding="utf-8")

    def run_model(self, rows: list[dict], selected: str | None = None, raw=None) -> dict:
        case = self.root / "model-case.json"
        case.write_text(json.dumps({"rows": rows, "selected": selected, "raw": raw}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "model.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def test_parent_rows_are_absent_from_the_rail_even_when_they_are_newest(self):
        learner = row()
        out = self.run_model([parent_row(), learner])
        self.assertEqual(out["slotIds"], [learner["course_id"]])
        self.assertEqual(out["allIds"], [learner["course_id"]])
        self.assertEqual(out["total"], 1)
        # The row total still counts every row: the parent-only desk state needs it.
        self.assertEqual(out["rowTotal"], 2)

    def test_a_parent_row_can_never_be_the_selected_classroom(self):
        learner = row()
        out = self.run_model([parent_row(), learner], selected="crs_parent0000000001")
        self.assertEqual(out["selected"], learner["course_id"])

    def test_a_parent_only_profile_has_no_learner_slot(self):
        out = self.run_model([parent_row()])
        self.assertEqual(out["slotIds"], [])
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["rowTotal"], 1)
        self.assertIsNone(out["selected"])

    def test_session_length_is_a_choice_with_a_calm_default(self):
        out = self.run_model([row()])
        self.assertEqual(out["clean"]["sessionMinutes"], 15)
        dirty = self.run_model([row()], raw={"sessionMinutes": 999})
        self.assertEqual(dirty["clean"]["sessionMinutes"], 15)
        chosen = self.run_model([row()], raw={"sessionMinutes": 20})
        self.assertEqual(chosen["clean"]["sessionMinutes"], 20)


class LearnerHomeTest(Harness):
    def test_home_shows_the_learner_classroom_and_never_the_parent_plan(self):
        result = self.mount([], rows=[parent_row(), row()])
        first = result["steps"][0]
        self.assertEqual(first["destination"], "home")
        self.assertEqual(first["bodyText"].count("Small-engine maintenance") >= 1, True)
        self.assertNotIn("Fractions for a 9-year-old", first["bodyText"])

    def test_a_parent_only_profile_gets_the_parent_studio_state_not_a_continue_plate(self):
        result = self.mount([], rows=[parent_row()])
        first = result["steps"][0]
        self.assertIn("Parent Studio holds your lesson plans.", first["bodyText"])
        self.assertIn("Open Parent Studio", first["bodyText"])
        self.assertNotIn("Fractions for a 9-year-old", first["bodyText"])

    def test_home_names_the_child_safe_floor_and_the_session_before_opening_anything(self):
        result = self.mount([])
        first = result["steps"][0]
        self.assertEqual(first["childSafe"], "on")
        self.assertEqual(first["sessionMinutes"], "15")
        self.assertIn("Child-safe defaults", first["homeDefaultsText"])
        self.assertIn("Session · 15 min", first["homeDefaultsText"])

    def test_the_settings_sheet_lists_the_four_rules_and_the_session_choice(self):
        result = self.mount([{"kind": "open"}])
        opened = result["steps"][1]
        self.assertIn("child-safe", opened["sections"])
        self.assertEqual(
            [rule["id"] for rule in opened["childSafeRules"]],
            ["reminders", "leaderboard", "rewards", "xp"],
        )
        for rule in opened["childSafeRules"]:
            self.assertEqual(rule["state"], "never", rule)
            self.assertIn("Never", rule["text"])
        self.assertEqual(opened["controls"]["session-length"], "15")
        html = result["sheetHtml"]
        for label in ("Loss-framed reminders", "Public leaderboard", "Loot or random rewards", "XP and streaks"):
            self.assertIn(label, html)

    def test_session_length_applies_at_once_and_resets_to_fifteen(self):
        result = self.mount(
            [
                {"kind": "open"},
                {"kind": "option", "section": "session-length", "value": "20"},
                {"kind": "option", "section": "session-length", "value": "10"},
                {"kind": "reset", "section": "child-safe"},
            ],
            storage_name="session.json",
        )
        opened, after_twenty, after_ten, after_reset = result["steps"][1:5]
        self.assertEqual(opened["controls"]["session-length"], "15")
        self.assertEqual(after_twenty["controls"]["session-length"], "20")
        self.assertEqual(after_twenty["sessionMinutes"], "20")
        self.assertEqual(after_ten["controls"]["session-length"], "10")
        self.assertEqual(after_reset["controls"]["session-length"], "15")
        self.assertEqual(after_reset["sessionMinutes"], "15")
        self.assertEqual(result["stored"]["home-preferences.default"]["sessionMinutes"], 15)


class ParentStudioTest(Harness):
    def test_studio_says_prepare_a_lesson_for_a_child(self):
        result = self.mount([{"kind": "destination", "value": "studio"}], rows=[parent_row()])
        studio = result["steps"][1]
        self.assertEqual(studio["destination"], "studio")
        self.assertIn("Prepare a lesson for a child", studio["bodyText"])
        self.assertIn("Plans for your child", studio["bodyText"])
        self.assertNotIn("chat as the child", studio["bodyText"].lower())

    def test_studio_carries_the_child_safe_line_and_opens_the_same_sheet(self):
        result = self.mount(
            [{"kind": "destination", "value": "studio"}, {"kind": "open"}],
            rows=[parent_row()],
            storage_name="studio-sheet.json",
        )
        studio, opened = result["steps"][1], result["steps"][2]
        self.assertEqual(studio["childSafe"], "on")
        self.assertEqual(studio["sessionMinutes"], "15")
        self.assertIn("Child-safe defaults", studio["bodyText"])
        self.assertIn("Session · 15 min", studio["bodyText"])
        self.assertTrue(opened["sheetOpen"])
        self.assertIn("child-safe", opened["sections"])

    def test_studio_settings_return_focus_to_the_studio_trigger(self):
        result = self.mount(
            [{"kind": "destination", "value": "studio"}, {"kind": "open"}, {"kind": "escape"}],
            rows=[parent_row()],
            storage_name="studio-focus.json",
        )
        closed = result["steps"][3]
        self.assertFalse(closed["sheetOpen"])
        self.assertEqual(closed["focus"]["label"], "Open Coursebook settings")
        self.assertEqual(closed["focus"]["text"], "Settings")

    def test_the_parent_view_reports_evidence_not_points(self):
        result = self.mount(
            [
                {"kind": "destination", "value": "studio"},
                {"kind": "text-click", "text": "Open plan"},
            ],
            rows=[parent_row()],
            storage_name="studio-plan.json",
        )
        plan = result["steps"][2]
        self.assertIn("never points, levels or rankings", plan["parentEvidence"])
        self.assertIn("what your child did", plan["parentEvidence"])
        self.assertEqual(plan["destination"], "studio")


class ChildSafeCopyTest(unittest.TestCase):
    """The refused mechanics cannot be worded back into the child-facing surfaces."""

    BANNED = (
        "lose your streak",
        "streak dies",
        "days in a row",
        "top of the leaderboard",
        "climb the leaderboard",
        "earn xp",
        "spin to win",
        "loot box",
        "chat as the child",
        "comeback bonus",
    )

    def test_no_refused_mechanic_phrase_ships(self):
        lowered = PLUGIN_TEXT.lower()
        for phrase in self.BANNED:
            self.assertNotIn(phrase, lowered, phrase)

    def test_the_child_safe_rules_are_stated_as_never(self):
        for label in ("Loss-framed reminders", "Public leaderboard", "Loot or random rewards", "XP and streaks"):
            self.assertIn(label, PLUGIN_TEXT)
        self.assertEqual(PLUGIN_TEXT.count("state: 'Never'"), 4)

    def test_parent_studio_copy_names_preparing_not_chatting(self):
        self.assertIn("Prepare a lesson for a child", PLUGIN_TEXT)
        self.assertIn("no child chat, no child persona", PLUGIN_TEXT)
        self.assertIsNone(re.search(r"chat as (a|the) child", PLUGIN_TEXT, re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
