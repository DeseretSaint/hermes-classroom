"""An all-practice course is not "0 of 0 sections done".

`generation.SELF_REPORT_ONLY_TARGETS` (production, procedure) means the library's
``sections_done``/``sections_total`` count evidence-bearing objectives only. A course whose
objectives are all practice therefore reports ``0 / 0`` while the learner has committed four
checks and the backend's own terminal step is ``next_step.kind = "complete"``. Two surfaces read
badly on that row, and both are fixed here without touching the backend count or inventing a
second progress authority:

  * ``homeCardFacts`` printed ``0 of 0 sections done`` on the shelf card. It now prints
    ``{n} checks recorded`` from the CP-005 field ``checks_recorded`` — the committed attempts the
    learner actually worked — and only when ``sections_total`` is 0. A course with sections keeps
    the section line verbatim.
  * ``CourseHomeV3`` computed ``total > 0 && done >= total``, so an all-practice route never
    closed. Completion now also honours ``next_step.kind === "complete"``, which is the backend's
    decision; every unlocked node reads done, and the close names the recorded checks instead of
    claiming "Every section has evidence."

The tests render the shipped ``desktop/plugin.js`` through React (the same harness shape the CP-022
and CP-024 suites use) and call the exported pure helpers directly. Nothing here asserts pixels;
a layout pass is a separate gate.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
// Pinned before the module import: the SDK stub reads the viewport atom at evaluation time.
globalThis.__CB_TEST_WIDTH__ = '1049'
const mod = await import('./plugin.js')
const h = React.createElement
const out = { facts: {}, home: '', course: {}, nodes: {}, normalCourse: '' }

// ── the shelf line, called directly ──────────────────────────────────────────────────────────
for (const [name, row] of Object.entries(payload.facts)) {
  out.facts[name] = mod.homeCardFacts(row)
}

// ── the shelf as it paints ──────────────────────────────────────────────────────────────────
const lib = (rows) => ({
  items: rows,
  next_cursor: null,
  total: rows.length,
  empty_reason: rows.length ? null : 'no_courses',
  applied_filter: 'all'
})
out.home = renderToStaticMarkup(
  h('div', null,
    h(mod.CoursebookHome, {
      library: { status: 'ready', data: lib(payload.homeRows), error: null, stale: false },
      modes: {},
      modesSupported: true,
      online: true,
      canCreate: true,
      onStartCreate: () => {},
      onBrowseLibrary: () => {},
      onOpenCourse: () => {},
      onShowAll: () => {},
      onOpenStudio: () => {},
      onRetry: () => {}
    })
  )
)

// ── the course home, rendered with the all-practice row ────────────────────────────────────
const renderCourse = (fixture) =>
  renderToStaticMarkup(
    h(mod.CourseHomeV3, {
      row: fixture.row,
      objectives: fixture.objectives,
      page: fixture.page,
      plate: fixture.plate,
      anchors: fixture.anchors,
      others: fixture.others,
      sectionsDone: fixture.row.sections_done,
      sectionsTotal: fixture.row.sections_total,
      parentLabel: 'Home',
      width: 1049,
      busy: false,
      worldState: null,
      readState: 'ready',
      onBack: () => {},
      onContinue: () => {},
      onOpenPlan: () => {},
      onOpenSection: () => {},
      onOpenReview: () => {}
    })
  )
out.course = renderCourse(payload.practice)
out.normalCourse = renderCourse(payload.normal)

// ── node states, pure ──────────────────────────────────────────────────────────────────────
out.nodes.complete = mod.cb3CourseNodes({
  objectives: payload.practice.objectives,
  row: payload.practice.row,
  page: payload.practice.page,
  complete: true
})
out.nodes.incomplete = mod.cb3CourseNodes({
  objectives: payload.practice.objectives,
  row: payload.practice.row,
  page: payload.practice.page
})
out.evidenceLine = [mod.cb3CourseEvidenceLine(0, 0), mod.cb3CourseEvidenceLine(2, 5)]
process.stdout.write(JSON.stringify(out))
"""


def practice_row(**overrides) -> dict:
    """The one-off procedure course: four practice objectives, nothing that can reach evidence."""
    row = {
        "enrollment_id": "enr_practice",
        "course_id": "crs_practice",
        "title": "Replace a bicycle brake pad",
        "subject_label": "Bicycle repair",
        "recipe": "committed",
        "sections_done": 0,
        "sections_total": 0,
        "checks_recorded": 4,
        "is_new": False,
        "next_step": {"kind": "complete", "label": "You have finished this course"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 0,
            "current_objective_id": None,
        },
        "updated_at": "2026-11-14T00:00:00Z",
        "revision": 3,
    }
    row.update(overrides)
    return row


def braise_row() -> dict:
    """The ordinary course beside it: sections exist, so the section line must stay."""
    return {
        "enrollment_id": "enr_braise",
        "course_id": "crs_braise",
        "title": "Learn to braise",
        "subject_label": "Kitchen",
        "recipe": "committed",
        "sections_done": 2,
        "sections_total": 5,
        "checks_recorded": 3,
        "is_new": False,
        "next_step": {"kind": "resume_lesson", "label": "Continue Braise short ribs"},
        "evidence_summary": {
            "independent": 2,
            "review_due": 0,
            "total_objectives": 5,
            "current_objective_id": "obj_3",
        },
        "updated_at": "2026-11-14T00:00:00Z",
        "revision": 1,
    }


def practice_objectives() -> list[dict]:
    return [
        {
            "objective_id": f"obj_p{i}",
            "title": title,
            "ordinal": i,
            # A practice-only objective stays `introduced`: the checklist is a self-report and can
            # never reach independent evidence. It is still worked, so the route may not read next.
            "state": "introduced",
            "independent": False,
            "evidence_target": "procedure",
        }
        for i, title in enumerate(
            [
                "Remove the wheel",
                "Take out the old pad",
                "Fit the new pad",
                "Test the brake",
            ],
            start=1,
        )
    ]


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


class PracticeOnlyProgressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-practice-only-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

        practice_objectives_ = practice_objectives()
        payload = {
            "facts": {
                "practice": practice_row(),
                "one": practice_row(checks_recorded=1),
                "braise": braise_row(),
                "untouched": practice_row(checks_recorded=0),
                # An older read with no section pair at all: the evidence summary pair is the only
                # section fact, and it must still win over the checks line.
                "legacy": practice_row(
                    checks_recorded=1,
                    sections_done=None,
                    sections_total=None,
                    evidence_summary={
                        "independent": 3,
                        "review_due": 0,
                        "total_objectives": 7,
                        "current_objective_id": "obj_p2",
                    },
                ),
            },
            "homeRows": [practice_row(), braise_row()],
            "practice": {
                "row": practice_row(),
                "objectives": practice_objectives_,
                "page": {"section": {"objective_id": "obj_p4", "title": "Test the brake", "ordinal": 4}},
                "plate": {"artifactId": None, "src": None, "credit": None, "anchors": []},
                "anchors": [
                    {"objective_id": f"obj_p{i}", "x": 0.15 + 0.2 * (i - 1), "y": 0.5}
                    for i in range(1, 5)
                ],
                "others": [],
            },
            "normal": {
                "row": braise_row(),
                "objectives": [
                    {"objective_id": "obj_1", "title": "Sear", "ordinal": 1, "state": "completed", "independent": True},
                    {"objective_id": "obj_2", "title": "Braise", "ordinal": 2, "state": "completed", "independent": True},
                    {"objective_id": "obj_3", "title": "Reduce", "ordinal": 3, "state": "introduced"},
                    {"objective_id": "obj_4", "title": "Serve", "ordinal": 4, "state": "not_started"},
                    {"objective_id": "obj_5", "title": "Store", "ordinal": 5, "state": "not_started"},
                ],
                "page": {"section": {"objective_id": "obj_3", "title": "Reduce", "ordinal": 3}},
                "plate": {"artifactId": None, "src": None, "credit": None, "anchors": []},
                "anchors": [
                    {"objective_id": f"obj_{i}", "x": 0.1 + 0.2 * (i - 1), "y": 0.5}
                    for i in range(1, 6)
                ],
                "others": [],
            },
        }
        (root / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
        result = __import__("subprocess").run(
            ["node", "harness.mjs", "payload.json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(f"harness failed: {result.stderr}")
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    # ── 1. the shelf line ─────────────────────────────────────────────────────────────────────

    def test_an_all_practice_course_prints_its_recorded_checks(self) -> None:
        self.assertEqual(self.report["facts"]["practice"]["meta"], "4 checks recorded")
        self.assertEqual(self.report["facts"]["one"]["meta"], "1 check recorded")

    def test_a_course_with_sections_keeps_its_section_line(self) -> None:
        self.assertEqual(self.report["facts"]["braise"]["meta"], "2 of 5 sections done")

    def test_no_zero_of_zero_line_is_ever_composed(self) -> None:
        for name, facts in self.report["facts"].items():
            meta = facts["meta"]
            if meta is None:
                continue
            self.assertNotIn("0 of 0", meta, f"{name} invented an empty denominator: {meta}")

    def test_a_course_with_nothing_worked_prints_no_progress_claim(self) -> None:
        # 0 sections and 0 recorded checks is a genuinely new course: the card omits the line
        # rather than printing "0 of 0 sections done" or "0 checks recorded".
        self.assertIsNone(self.report["facts"]["untouched"]["meta"])

    def test_an_older_read_keeps_the_evidence_summary_pair(self) -> None:
        # No CP-005 section pair at all: the summary pair is the only section fact and wins over
        # the checks line, so a legacy read is not relabelled as practice.
        self.assertEqual(self.report["facts"]["legacy"]["meta"], "3 of 7 sections done")

    def test_the_shelf_paints_the_checks_line(self) -> None:
        text = strip_tags(self.report["home"])
        self.assertIn("4 checks recorded", text)
        self.assertNotIn("0 of 0 sections done", text)
        # the ordinary row beside it is untouched
        self.assertIn("2 of 5 sections done", text)

    # ── 2. the course home closes on the backend's terminal step ──────────────────────────────

    def test_an_all_practice_course_renders_the_complete_beat(self) -> None:
        html = self.report["course"]
        text = strip_tags(html)
        self.assertIn('data-cb-continue="complete"', html)
        self.assertIn("Course complete", text)
        self.assertIn("4 checks recorded", text)
        # The close may not claim evidence it does not have.
        self.assertNotIn("Every section has evidence.", text)

    def test_no_empty_evidence_row_is_rendered(self) -> None:
        html = self.report["course"]
        self.assertNotIn("data-cb-course-evidence", html)
        self.assertEqual(self.report["evidenceLine"][0], None)
        self.assertEqual(self.report["evidenceLine"][1], "2 of 5 sections have evidence")

    def test_completion_is_the_backend_step_not_a_fabricated_total(self) -> None:
        html = self.report["course"]
        # the one action is the backend's own label for the terminal step
        self.assertIn("You have finished this course", strip_tags(html))
        states = [node["state"] for node in self.report["nodes"]["complete"]]
        self.assertEqual(states, ["done", "done", "done", "done"])
        self.assertNotIn("You are here", strip_tags(html))
        self.assertNotIn('aria-current="step"', html)
        self.assertEqual(html.count('data-cb-course-node-state="done"'), 4)

    def test_an_unfinished_practice_course_still_shows_a_current_step(self) -> None:
        # Negative control: without the backend's `complete`, nothing may read done.
        states = [node["state"] for node in self.report["nodes"]["incomplete"]]
        self.assertIn("current", states)
        self.assertNotIn("done", states)

    def test_a_course_with_sections_is_unchanged(self) -> None:
        html = self.report["normalCourse"]
        text = strip_tags(html)
        self.assertIn('data-cb-continue="resume_lesson"', html)
        self.assertIn("2 of 5 sections have evidence", text)
        self.assertNotIn("checks recorded", text)
        self.assertEqual(html.count('data-cb-course-node-state="done"'), 2)
        self.assertEqual(html.count('data-cb-course-node-state="current"'), 1)

    # ── 3. the honesty rules still hold ───────────────────────────────────────────────────────

    def test_no_percentage_and_no_second_progress_authority(self) -> None:
        for html in (self.report["home"], self.report["course"], self.report["normalCourse"]):
            text = strip_tags(html).lower()
            self.assertNotIn("%", text)
            for banned in ("mastery", "streak", "rating"):
                self.assertNotRegex(text, rf"\b{banned}\b", f"the surface invented {banned!r}")
            self.assertNotRegex(text, r"\bxp\b|\b\d+\s*xp\b", "the surface invented XP")


if __name__ == "__main__":
    unittest.main()
