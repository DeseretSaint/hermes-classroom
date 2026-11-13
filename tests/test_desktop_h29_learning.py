"""H-29: the lesson index, the check result and progress speak to a learner.

The plugin is one uncompiled ESM file, so these tests render the shipped components with
``react-dom/server`` and the stub ``@hermes/plugin-sdk`` that ``tests/test_desktop_lesson_views.py``
already owns. They assert what a person reads and the structure a keyboard user navigates:

* the index answers "where am I / what is next" before metadata, groups by unit only when the plan
  really has more than one unit, makes the row itself the action (one chevron, no repeated button),
  and carries every state as icon + word;
* the result voice says "First try, no hints", "We could not grade this answer" and a concrete
  takeaway followed by one next action, never a mastery claim;
* progress is a count the backend records ("3 of 4 sections have independent evidence"), not a
  percentage, streak or invented unit.

What this does NOT prove: that a live Desktop window paints these strings. The M4 visual audit and
the captured frames are the separate painted evidence; this is the structural half.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

#: The shared stub's Button drops unknown props. This suite needs the row's `data-*` markers and
#: `aria-current` to survive the render, so the one stub authority is extended in place.
STUB = SDK_STUB.replace(
    """export const Button = (props) =>
  el('button', {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }, textOf(props))""",
    """export const Button = (props) =>
  el('button', {
    type: 'button',
    ...props,
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }, textOf(props))""",
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  AttemptVerdict,
  EvidenceClassText,
  OverviewView,
  TextbookView,
  learnerEvidenceTarget,
  objectiveProgress,
  progressStatement
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const noop = () => {}

let html = null
if (payload.kind === 'textbook') {
  html = renderToStaticMarkup(
    React.createElement(TextbookView, {
      row: payload.row,
      page: null,
      pageState: { status: 'idle', error: null, reload: noop },
      review: null,
      notebooks: null,
      outline: payload.outline,
      implemented: new Set(['course.outline']),
      openSectionId: null,
      onOpenSection: noop,
      onCloseSection: noop,
      onChanged: noop,
      targetBlockId: null
    })
  )
} else if (payload.kind === 'overview') {
  html = renderToStaticMarkup(
    React.createElement(OverviewView, {
      row: payload.row,
      page: payload.page,
      review: { items: [], total_overdue: 0 },
      quizzes: { attempts: [] },
      outline: payload.outline,
      implemented: new Set(),
      onOpenSection: noop,
      onResume: noop
    })
  )
} else if (payload.kind === 'verdict') {
  html = renderToStaticMarkup(
    React.createElement(AttemptVerdict, {
      result: payload.result,
      criteria: payload.criteria || [],
      checklist: payload.checklist || [],
      onResumeChecklist: noop,
      onNewExample: noop,
      onExplain: noop
    })
  )
} else if (payload.kind === 'evidence-class') {
  html = renderToStaticMarkup(React.createElement(EvidenceClassText, { value: payload.value }))
}

process.stdout.write(
  JSON.stringify({
    html,
    helpers: {
      progress: progressStatement(payload.independent, payload.total),
      target: learnerEvidenceTarget('discrimination'),
      unknownTarget: learnerEvidenceTarget('self_assessment'),
      counts: objectiveProgress(payload.objectives || [], 0)
    }
  })
)
"""


def objective(objective_id, ordinal, title, state, target, independent, *, last_opened_at=None):
    return {
        "objective_id": objective_id,
        "ordinal": ordinal,
        "title": title,
        "evidence_target": target,
        "state": state,
        "check_state": "closed" if independent else "open",
        "attempt_count": 1 if independent else 0,
        "independent": independent,
        "last_opened_at": last_opened_at,
    }


OBJECTIVES = [
    objective("obj_orient", 1, "Find the valve", "independent_evidence", "procedure", True),
    objective("obj_apart", 2, "Tell the two tubes apart", "review_due", "discrimination", False),
    objective("obj_fit", 3, "Fit the tube without pinching", "not_started", "procedure", False),
    objective("obj_bead", 4, "Seat the bead", "independent_evidence", "procedure", True),
    objective("obj_pressure", 5, "Inflate to the sidewall pressure", "independent_evidence", "recall", True),
    objective("obj_ride", 6, "Check the wheel before riding", "not_started", "transfer", False),
]

OUTLINE = {
    "enrollment_id": "enr_0123456789abcdef",
    "plan": {
        "units": [
            {
                "ordinal": 1,
                "title": "Get the wheel off",
                "goal": "Open the quick release and free the wheel.",
                "prereq_unit_ordinals": [],
                "prerequisite_state": "no_edges",
                "unmet": [],
                "objectives": OBJECTIVES[:3],
            },
            {
                "ordinal": 2,
                "title": "Put it back together",
                "goal": "Seat, inflate and check.",
                "prereq_unit_ordinals": [1],
                "prerequisite_state": "unmet",
                "unmet": [],
                "objectives": OBJECTIVES[3:],
            },
        ]
    },
    "objectives": OBJECTIVES,
    "total": 6,
    "truncated": False,
}

ROW = {
    "enrollment_id": "enr_0123456789abcdef",
    "title": "Bike tube replacement",
    "recipe": "course",
    "enrollment_status": "active",
    "revision": 3,
    "evidence_summary": {
        "total_objectives": 6,
        "independent": 3,
        "review_due": 1,
        "current_objective_id": "obj_fit",
        "current_section_id": "obj_fit",
    },
    "next_step": {"kind": "start_lesson", "label": "Start: Fit the tube without pinching"},
    "provenance": {"source": "authored"},
}


class LearningSurfaceRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h29-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    def textbook(self) -> str:
        return self.render({"kind": "textbook", "row": ROW, "outline": OUTLINE, "independent": 3, "total": 4})["html"]

    # -- Lesson index -----------------------------------------------------------------------
    def test_progress_statement_is_the_count_the_backend_records(self) -> None:
        html = self.textbook()
        self.assertIn("3 of 6 sections have independent evidence", html)
        progress_block = html.split("data-cb-progress-statement", 1)[1].split("</div>", 1)[0]
        self.assertNotIn("%", progress_block)
        self.assertNotIn("streak", html.lower())
        self.assertNotIn("mastered", html.lower())

    def test_the_exact_ux_example_is_reproducible(self) -> None:
        out = self.render(
            {"kind": "textbook", "row": ROW, "outline": OUTLINE, "independent": 3, "total": 4, "objectives": OBJECTIVES}
        )
        self.assertEqual(out["helpers"]["progress"], "3 of 4 sections have independent evidence")
        self.assertEqual(out["helpers"]["counts"]["independent"], 3)
        self.assertEqual(out["helpers"]["counts"]["total"], 6)

    def test_next_marker_is_on_the_section_the_backend_points_to(self) -> None:
        html = self.textbook()
        self.assertIn("data-cb-next-statement", html)
        self.assertIn("Next ·", html)
        self.assertIn("Fit the tube without pinching", html)
        self.assertEqual(html.count('aria-current="step"'), 1)
        # The current row is marked `next`, not `not_started`, and carries its own state word.
        self.assertIn('data-cb-section-state="next"', html)

    def test_the_row_itself_is_the_action(self) -> None:
        html = self.textbook()
        self.assertEqual(html.count("data-cb-section-row="), 6)
        self.assertNotIn("Open section", html)
        # Each row is one button; the only other buttons would be a repeated action, which is gone.
        self.assertEqual(html.count("<button"), 6)

    def test_units_group_only_when_the_plan_has_more_than_one(self) -> None:
        html = self.textbook()
        self.assertEqual(html.count("data-cb-unit="), 2)
        self.assertIn("Get the wheel off", html)
        self.assertIn("Put it back together", html)
        self.assertEqual(html.count("data-cb-unit-progress="), 2)
        self.assertIn("1 of 3 sections have independent evidence", html)
        self.assertIn("2 of 3 sections have independent evidence", html)

    def test_a_single_implicit_unit_is_not_invented_as_a_heading(self) -> None:
        outline = dict(OUTLINE)
        outline["plan"] = {
            "units": [
                {
                    "ordinal": 1,
                    "title": "Bike tube replacement",
                    "goal": "",
                    "prereq_unit_ordinals": [],
                    "prerequisite_state": "no_edges",
                    "unmet": [],
                    "objectives": OBJECTIVES,
                }
            ]
        }
        out = self.render({"kind": "textbook", "row": ROW, "outline": outline, "independent": 3, "total": 4})
        html = out["html"]
        self.assertNotIn("data-cb-unit=", html)
        self.assertNotIn("Unit 1", html)
        self.assertEqual(html.count("data-cb-section-row="), 6)

    def test_every_state_has_an_icon_and_a_word(self) -> None:
        html = self.textbook()
        self.assertIn('data-cb-section-state="complete"', html)
        self.assertIn('data-cb-section-state="review"', html)
        self.assertIn('data-cb-section-state="not_started"', html)
        self.assertIn("Independent evidence", html)
        self.assertIn("Review due", html)
        self.assertIn("Not started", html)
        # The state word travels with the icon inside the row, not only in the details legend.
        row = html.split('data-cb-section-row="obj_apart"', 1)[1].split("data-cb-section-row=", 1)[0]
        self.assertIn("Review due", row)

    def test_discrimination_moves_out_of_the_default_learner_text(self) -> None:
        html = self.textbook()
        visible, details = html.split("data-cb-index-details", 1)
        self.assertNotIn("discrimination", visible)
        self.assertIn("Tell the difference", visible)
        self.assertIn("discrimination", details)
        self.assertIn("Check types in this course", details)

    def test_repeated_timestamps_are_gone(self) -> None:
        # No row carries a timestamp unless it is the next section; none of these rows do.
        self.assertNotIn("last opened", self.textbook())

    # -- Overview ---------------------------------------------------------------------------
    def overview(self) -> str:
        payload = {
            "kind": "overview",
            "row": ROW,
            "outline": OUTLINE,
            "page": {
                "section": {
                    "objective_id": "obj_fit",
                    "title": "Fit the tube without pinching",
                    "state": "not_started",
                    "evidence_target": "discrimination",
                }
            },
        }
        return self.render(payload)["html"]

    def test_overview_answers_where_and_next_before_metadata(self) -> None:
        html = self.overview()
        progress = html.index("data-cb-progress-statement")
        next_statement = html.index("data-cb-next-statement")
        details = html.index("data-cb-overview-details")
        self.assertLess(progress, next_statement)
        self.assertLess(next_statement, details)
        self.assertIn("3 of 6 sections have independent evidence", html)
        self.assertIn("Next ·", html)
        self.assertNotIn("THIS COURSE", html)
        self.assertIn("Course details", html)
        self.assertNotIn("discrimination", html.split("data-cb-overview-details", 1)[0])

    # -- Result voice -----------------------------------------------------------------------
    def verdict(self, result: dict, criteria: list[dict], checklist: list[dict] | None = None) -> str:
        out = self.render(
            {
                "kind": "verdict",
                "result": result,
                "criteria": criteria,
                "checklist": checklist or [],
            }
        )
        return out["html"]

    def test_a_pass_shows_a_takeaway_and_one_next_action_without_mastery(self) -> None:
        html = self.verdict(
            {"verdict": "pass", "evidence_class": "cold", "next_action": "complete_objective"},
            [{"id": "c1", "observed": "You seated the bead without pinching the tube", "met": True}],
        )
        self.assertIn("Passed", html)
        self.assertIn("What you showed: You seated the bead without pinching the tube.", html)
        self.assertIn("Next: open the section after this one", html)
        self.assertIn("not mastery of the whole course", html)
        self.assertNotIn("This objective is complete", html)
        self.assertNotIn("mastered", html.lower())
        self.assertNotIn("confetti", html.lower())

    def test_first_try_copy_explains_why_independent_evidence_matters(self) -> None:
        out = self.render({"kind": "evidence-class", "value": "cold"})
        html = out["html"]
        self.assertIn("First try, no hints", html)
        self.assertIn("Independent evidence is worth more", html)
        self.assertNotIn("Cold", html)

    def test_a_grade_failure_names_the_system_not_the_learner(self) -> None:
        html = self.verdict({"verdict": "needs_retry", "evidence_class": "cold", "next_action": "retry_grading"}, [])
        self.assertIn("We could not grade this answer", html)
        self.assertNotIn("Grading failed", html)
        # The saved / not graded distinction is not softened away.
        self.assertIn("The answer is saved. Retry grading does not consume a new attempt.", html)

    def test_a_not_yet_verdict_is_not_dressed_as_encouragement(self) -> None:
        html = self.verdict({"verdict": "not_yet", "evidence_class": "cold", "next_action": "continue"}, [])
        self.assertIn("Not yet", html)
        self.assertNotIn("What you showed", html)

    # -- Source-level guarantees ------------------------------------------------------------
    def test_no_raw_evidence_vocabulary_in_default_learner_copy(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertNotIn("Cold attempt", source)
        self.assertNotIn("Grading failed", source)
        self.assertNotIn("label: 'Discrimination'", source)
        self.assertIn("cold: 'First try, no hints'", source)
        self.assertIn("needs_retry: 'We could not grade this answer'", source)
        self.assertIn("Your answer is saved, not graded.", source)

    def test_a_pass_never_prints_the_old_completion_sentence(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertNotIn("This objective is complete", source)
        self.assertNotIn("Cold attempt", source)

    def test_unknown_construct_never_prints_a_raw_enum(self) -> None:
        out = self.render({"kind": "textbook", "row": ROW, "outline": OUTLINE, "independent": 3, "total": 4})
        self.assertEqual(out["helpers"]["target"], "Tell the difference")
        self.assertEqual(out["helpers"]["unknownTarget"], "Self Assessment")


if __name__ == "__main__":
    unittest.main()
