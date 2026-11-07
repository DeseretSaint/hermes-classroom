"""The frozen assessment-breadth copy must reach the Desktop half verbatim.

`docs/ASSESSMENT-BREADTH.md` §7 freezes these strings: one static disclosure for every plan and
every check, because the harness grades written answers, choices and checklists only. The copy is
keyed to the lane, never to a guessed construct, so a topic classifier over the learner's goal must
not appear here either. This module asserts the literals rather than rendering the plugin: the disk
loader refuses JSX and extra modules, so `desktop/plugin.js` is the single source of the strings.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "desktop" / "plugin.js"

PLAN_BREADTH_DISCLOSURE = (
    "What Coursebook can check — Written answers, choices, and checklists. This build cannot "
    'collect or grade a program, a recording, a photo, or a built object. Checks marked "practice '
    'only" never advance a section.'
)
CHECK_SURFACE_DISCLOSURE = (
    "Your answer is text, a choice, or a checklist. Nothing you type is executed."
)
OPEN_LANE_NOT_GRADED_COPY = (
    "Saved, not graded. This build has no grading model for open answers, so no verdict was "
    "produced. Your answer is saved, no progress was changed, and Retry grading does not consume "
    "an attempt."
)
SELF_REPORTED_COPY = "Reported by you — not independently verified."
PARENT_REPORTED_COPY = "Reported by the parent — not graded by Coursebook."


class DesktopBreadthCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN.read_text(encoding="utf-8")

    def assert_in_source(self, text: str) -> None:
        self.assertIn(text, self.source, f"frozen copy missing from desktop/plugin.js: {text!r}")

    def test_plan_preview_disclosure_is_verbatim(self) -> None:
        self.assert_in_source(PLAN_BREADTH_DISCLOSURE)

    def test_check_surface_disclosure_is_verbatim(self) -> None:
        self.assert_in_source(CHECK_SURFACE_DISCLOSURE)

    def test_open_lane_saved_not_graded_copy_is_verbatim(self) -> None:
        self.assert_in_source(OPEN_LANE_NOT_GRADED_COPY)

    def test_observation_evidence_labels_are_verbatim(self) -> None:
        self.assertIn(
            f"self_reported: '{SELF_REPORTED_COPY}',",
            self.source,
            "self_reported label missing from EVIDENCE_CLASS_COPY",
        )
        self.assertIn(
            f"parent_reported: '{PARENT_REPORTED_COPY}'",
            self.source,
            "parent_reported label missing from EVIDENCE_CLASS_COPY",
        )

    def test_plan_disclosure_precedes_outcomes(self) -> None:
        # §7.1: shown above the objective list, before the plan is approved and editable.
        disclosure = self.source.index("'data-cb-breadth': 'plan'")
        objectives = self.source.index("children: `OUTLINE AND ACTIVITIES (${objectives.length})`")
        self.assertLess(disclosure, objectives, "plan disclosure must sit above the objective list")

    def test_plan_disclosure_also_sits_above_pack_outcomes(self) -> None:
        # The frozen doc anchors §7.1 at `OUTCOMES (n)`; on this tree that section is the pack
        # manifest preview, so the same static line is rendered there as well.
        disclosure = self.source.index("'data-cb-breadth': 'pack-plan'")
        outcomes = self.source.index("children: `OUTCOMES (${objectives.length})`")
        self.assertLess(disclosure, outcomes, "pack preview disclosure must sit above OUTCOMES")

    def test_one_disclosure_per_surface(self) -> None:
        self.assertEqual(self.source.count("'data-cb-breadth': 'plan'"), 1)
        self.assertEqual(self.source.count("'data-cb-breadth': 'pack-plan'"), 1)
        self.assertEqual(self.source.count("'data-cb-breadth': 'check'"), 1)
        self.assertEqual(self.source.count("'data-cb-breadth': 'open-lane'"), 1)

    def test_open_lane_copy_is_keyed_to_recorded_provenance(self) -> None:
        # The unconfigured lane is read from the attempt's own grading provenance, not guessed from
        # the learner's goal text or the check's topic.
        self.assertIn("OPEN_LANE_UNCONFIGURED_PATTERN", self.source)
        self.assertIn("openLaneWasUnconfigured", self.source)
        self.assertIn("quiz.history", self.source)

    def test_retry_actions_are_unchanged(self) -> None:
        self.assertIn("children: 'Retry grading'", self.source)
        self.assertIn("children: 'Edit answer'", self.source)
        self.assertIn("children: 'Move on…'", self.source)


if __name__ == "__main__":
    unittest.main()
