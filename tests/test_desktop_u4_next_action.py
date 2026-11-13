"""U4 (finding 27) — the course page names the real next action, not a fresh run.

``desktop/src/90-course.js`` used to hold a binary label that sent ``resolve_review_due`` and
``review_plan`` both to "Start a fresh run" and then called ``onResume(objective_id)``. This pins
the replacement: one map entry per next-step kind, holding both the words and the verb, so a due
review says "Start the review" and resolves the review, and only a lesson kind may reach a lesson
run. A kind the surface cannot serve is disabled instead of being dressed as something else.

The plugin is one ESM file, so the harness mounts the shipped ``OverviewView`` in jsdom with the
stub ``@hermes/plugin-sdk`` and drives it with real clicks; the recorded calls are the proof of
which handler ran, not the DOM's word for it.

What this does NOT prove: that a live Desktop window paints these states. The card's rendered
evidence is the painted half; this is the behavioural and source half.
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
COURSE_SRC = ROOT / "desktop" / "src" / "90-course.js"
HOME_SRC = ROOT / "desktop" / "src" / "30-home.js"

HARNESS = r"""
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { OverviewView } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

const root = createRoot(document.getElementById('root'))
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const text = (node) => (node ? String(node.textContent || '').trim() : null)

const output = {}
const ui = []
for (const entry of payload.cases || []) {
  ui.length = 0
  // Every surface passes the same shape. `entry.handlers` may omit one on purpose: the point is
  // what the surface does when it has no honest action for that verb.
  const handlers = entry.handlers || {}
  const props = {
    row: entry.row,
    page: entry.page || null,
    review: { items: [], total_overdue: 0 },
    quizzes: { attempts: [] },
    outline: { objectives: entry.objectives || [] },
    implemented: new Set(entry.implemented || ['review.action']),
    onOpenSection: (id) => ui.push('section:' + String(id)),
    onOpenPlan: () => ui.push('plan')
  }
  if (handlers.resume !== false) props.onResume = (id) => ui.push('resume:' + String(id))
  if (handlers.review !== false) props.onReview = (id) => ui.push('review:' + String(id))
  root.render(React.createElement(OverviewView, props))
  await sleep(80)
  const button = document.querySelector('[data-cb-overview-primary]')
  const record = {
    label: text(button),
    kind: button ? button.getAttribute('data-cb-overview-primary') : null,
    disabled: button ? Boolean(button.disabled) : null,
    action: []
  }
  if (button && !button.disabled) {
    button.click()
    await sleep(60)
  }
  record.action = ui.slice()
  output[entry.name] = record
}

process.stdout.write(JSON.stringify(output))
"""


class CoursePagePrimaryTest(unittest.TestCase):
    """U4: one map entry per kind decides the words *and* the handler."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to mount a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-u4-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
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
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.report = cls._drive(root, {"cases": cls.CASES})

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    @staticmethod
    def _drive(root: Path, payload: dict) -> dict:
        case = root / "payload.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        done = subprocess.run(
            ["node", str(root / "harness.mjs"), str(case)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert done.returncode == 0, f"harness failed:\n{done.stdout}\n{done.stderr}"
        return json.loads(done.stdout)

    CASES = [
        {
            "name": "due",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
            },
            "page": {"section": {"objective_id": "obj-due", "title": "Say what you want", "ordinal": 2}},
            "objectives": [
                {"objective_id": "obj-due", "title": "Say what you want", "state": "review_due", "ordinal": 2}
            ],
        },
        {
            "name": "due_without_review_handler",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
            },
            "page": {"section": {"objective_id": "obj-due", "title": "Say what you want", "ordinal": 2}},
            "objectives": [
                {"objective_id": "obj-due", "title": "Say what you want", "state": "review_due", "ordinal": 2}
            ],
            "handlers": {"review": False},
        },
        {
            "name": "plan",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "review_plan", "label": "Review and approve the plan"},
            },
            "page": None,
            "objectives": [],
        },
        {
            "name": "resume",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "resume_lesson", "label": "Continue Say what you want"},
            },
            "page": {"section": {"objective_id": "obj-live", "title": "Say what you want", "ordinal": 3}},
            "objectives": [
                {"objective_id": "obj-live", "title": "Say what you want", "state": "introduced", "ordinal": 3}
            ],
        },
        {
            "name": "fresh",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "start_lesson", "label": "Start Say what you want"},
            },
            "page": {"section": {"objective_id": "obj-live", "title": "Say what you want", "ordinal": 3}},
            "objectives": [
                {"objective_id": "obj-live", "title": "Say what you want", "state": "introduced", "ordinal": 3}
            ],
        },
        {
            "name": "unknown",
            "row": {
                "course_id": "crs-1",
                "title": "Japanese",
                "next_step": {"kind": "some_future_kind", "label": "Do the new thing"},
            },
            "page": {"section": {"objective_id": "obj-live", "title": "Say what you want", "ordinal": 3}},
            "objectives": [
                {"objective_id": "obj-live", "title": "Say what you want", "state": "introduced", "ordinal": 3}
            ],
        },
    ]

    def case(self, name: str) -> dict:
        return self.report[name]

    def test_a_due_review_says_start_the_review_and_resolves_the_review(self) -> None:
        due = self.case("due")
        self.assertEqual(due["label"], "Start the review")
        self.assertEqual(due["kind"], "resolve_review_due")
        self.assertFalse(due["disabled"], "a due review with a review handler is not actionable")
        self.assertEqual(due["action"], ["review:obj-due"])
        self.assertNotIn("resume:obj-due", due["action"], "a due review was sent to onResume")

    def test_a_due_review_never_falls_back_to_a_lesson_run(self) -> None:
        case = self.case("due_without_review_handler")
        self.assertEqual(case["label"], "Start the review")
        self.assertTrue(case["disabled"], "a due review with no review handler still offered a lesson run")
        self.assertEqual(case["action"], [], "the disabled review primary fired something")

    def test_an_unapproved_plan_opens_the_plan(self) -> None:
        plan = self.case("plan")
        self.assertEqual(plan["label"], "Review the plan")
        self.assertEqual(plan["kind"], "review_plan")
        self.assertFalse(plan["disabled"])
        self.assertEqual(plan["action"], ["plan"])
        self.assertNotIn("resume:None", plan["action"])

    def test_a_lesson_step_keeps_its_lesson_verb(self) -> None:
        resume = self.case("resume")
        self.assertEqual(resume["label"], "Resume the lesson")
        self.assertEqual(resume["action"], ["resume:obj-live"])
        fresh = self.case("fresh")
        self.assertEqual(fresh["label"], "Start a fresh run")
        self.assertEqual(fresh["action"], ["resume:obj-live"])

    def test_a_kind_this_page_cannot_serve_is_disabled(self) -> None:
        unknown = self.case("unknown")
        self.assertEqual(unknown["label"], "Open the lesson")
        self.assertTrue(unknown["disabled"], "an unserved next step still offered a working primary")
        self.assertEqual(unknown["action"], [])

    def test_one_press_never_runs_two_actions(self) -> None:
        for name, record in self.report.items():
            self.assertLessEqual(len(record["action"]), 1, f"{name} fired {record['action']}")
            if record["action"]:
                self.assertFalse(record["disabled"], f"{name} fired while disabled")


class OnePrimaryMapTest(unittest.TestCase):
    """The course page and Home must not own two different words for one next step."""

    def setUp(self) -> None:
        self.course = COURSE_SRC.read_text(encoding="utf-8")
        self.home = HOME_SRC.read_text(encoding="utf-8")

    def test_the_course_page_reads_the_home_label_map(self) -> None:
        self.assertIn("DESK_PRIMARY_LABEL = {", self.home)
        self.assertIn("const COURSE_PRIMARY = Object.freeze({", self.course)
        # Every kind Home can name has exactly one course-page entry, and its label is Home's word.
        home_keys = set()
        for line in self.home.split("DESK_PRIMARY_LABEL = {", 1)[1].split("}", 1)[0].splitlines():
            if ":" in line:
                home_keys.add(line.strip().split(":", 1)[0].strip())
        self.assertTrue(home_keys)
        for key in sorted(home_keys):
            entry = f"{key}: Object.freeze({{ label: DESK_PRIMARY_LABEL.{key}, verb:"
            self.assertIn(entry, self.course, f"{key} has no course-page entry or a copied label")

    def test_the_retired_binary_label_is_gone(self) -> None:
        self.assertNotIn(
            "children: next.kind === 'resume_lesson' ? 'Resume the lesson' : 'Start a fresh run'",
            self.course,
        )
        self.assertNotIn("const primaryKind = coursePrimaryAction", self.course)
        # The course page must not paint a lesson-start label for a kind it will not run as a lesson.
        self.assertNotIn("'Start the review'", self.course, "the words are copied from Home, not restated")

    def test_every_course_page_primary_resolves_through_the_one_map(self) -> None:
        # Three primaries on this surface: the overview button, the v3 Continue plate, the hero.
        self.assertEqual(self.course.count("coursePrimaryAction("), 4)  # 1 definition + 3 surfaces
        for anchor, label in (
            ("data-cb-overview-primary", "overview"),
            ("data-cb-hero-primary", "hero"),
            ("data-cb-continue-action", "continue plate"),
        ):
            self.assertIn(anchor, self.course, f"the {label} primary is missing")


if __name__ == "__main__":
    unittest.main()
