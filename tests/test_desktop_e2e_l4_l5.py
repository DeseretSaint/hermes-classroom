"""E2E L4/L5 on the shipped Desktop module.

The module is one ESM file with no build step, so these tests import the *shipped* ``plugin.js``
and assert on its pure projections and the markup the readiness panel renders. They prove that:

* a finished course reads as ``complete`` on the desk, not as ``review_plan``;
* a ``needs_review`` objective is not counted as a spaced review due;
* a parked authored page gets its own state word, the validator's named reasons and one Repair
  control, and a section that is genuinely ``review_due`` never shows that control.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

PARKED_REASONS = [
    "The page taught the answer its check asks for.",
    "The explanation restates the reference value instead of teaching the procedure.",
]

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  buildDeskModel,
  mainlineObjective,
  objectiveProgress,
  sectionSemanticFor,
  lessonReadiness,
  LessonReadinessPanel,
  cbNextStopSentence
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const row = payload.row || {}
const objectives = (payload.outline && payload.outline.objectives) || []
const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: null })
const readiness = lessonReadiness({
  outline: payload.outline,
  page: payload.page,
  jobs: payload.jobs || null,
  pageStatus: payload.pageStatus || 'ready',
  planStatus: 'ready'
})
const panel = payload.renderPanel
  ? renderToStaticMarkup(
      React.createElement(LessonReadinessPanel, {
        readiness,
        onOpenPlan: () => {},
        onRepeatCheck: () => {},
        onRetryLessonsJob: () => {},
        onRepairLesson: () => {},
        busy: false
      })
    )
  : null
process.stdout.write(
  JSON.stringify({
    desk: {
      primaryKind: desk.primaryKind,
      primaryLabel: desk.primaryLabel,
      dueCount: desk.dueCount,
      nextLabel: desk.nextLabel,
      current: desk.current ? desk.current.objective_id : null
    },
    mainline: (() => {
      const entry = mainlineObjective(row, objectives)
      return entry ? entry.objective_id : null
    })(),
    progress: objectiveProgress(objectives),
    semantics: objectives.map((entry) => sectionSemanticFor(entry, false)),
    sentence: cbNextStopSentence(payload.nextKind || (row.next_step || {}).kind || null),
    readiness: {
      state: readiness.state,
      headline: readiness.headline,
      reasons: readiness.reasons,
      action: readiness.action,
      sectionId: readiness.sectionId
    },
    panel
  })
)
"""


def objective(objective_id: str, state: str, ordinal: int = 1, **extra) -> dict:
    entry = {
        "objective_id": objective_id,
        "ordinal": ordinal,
        "title": f"Section {ordinal}",
        "evidence_target": "procedure",
        "state": state,
        "check_state": "open",
        "attempt_count": 0,
        "independent": state in ("independent_evidence", "delayed_evidence"),
        "last_opened_at": None,
    }
    entry.update(extra)
    return entry


def outline(objectives: list[dict]) -> dict:
    return {
        "enrollment_id": "enr_1",
        "plan": {"plan_id": "pln_1", "version": 1, "state": "approved", "plan_hash": None, "units": []},
        "objectives": objectives,
        "total": len(objectives),
        "truncated": False,
    }


def library(row: dict) -> dict:
    return {
        "items": [
            {
                "enrollment_id": "enr_1",
                "course_id": "crs_1",
                "title": "Compute a value",
                "recipe": "committed",
                "enrollment_status": "active",
                "course_status": "active",
                "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
                "next_step": row.get("next_step") or {"kind": "start_lesson", "label": "Start"},
                "evidence_summary": {
                    "independent": 0,
                    "review_due": 0,
                    "total_objectives": 1,
                    "current_objective_id": None,
                },
                "updated_at": "2026-11-12T00:00:00+00:00",
                "revision": 0,
                "sections_done": 0,
                "sections_total": 1,
                "checks_recorded": 0,
                "is_new": False,
                "subject_label": None,
                "cover_artifact_id": None,
                "last_studied_at": None,
            }
        ],
        "next_cursor": None,
        "total": 1,
        "empty_reason": None,
        "applied_filter": "all",
    }


def page_with_section(**section) -> dict:
    base = {
        "objective_id": "obj_1",
        "title": "Section 1",
        "ordinal": 1,
        "state": "not_started",
        "evidence_target": "procedure",
        "last_opened_at": None,
    }
    base.update(section)
    return {
        "enrollment_id": "enr_1",
        "course": {"course_id": "crs_1", "title": "Compute a value"},
        "section": base,
        "runtime": None,
        "segments": [],
        "document": None,
        "sources": [],
        "artifacts": [],
        "checks": [],
        "notebook_entries": [],
        "attempts": [],
        "state": base["state"],
        "provenance": None,
        "revision": 0,
    }


class E2ECompletionAndRepairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to import a runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-e2e-l4l5-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        if stage_desktop_node_modules(cls.root) is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        write_sdk_stub(cls.root, SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            self.fail(f"harness failed: {result.stderr}\n{result.stdout}")
        return json.loads(result.stdout)

    def test_a_finished_course_reads_as_complete_on_the_desk(self) -> None:
        objectives = [objective("obj_1", "independent_evidence")]
        row = {
            "next_step": {"kind": "complete", "label": "You have finished this course"},
            "evidence_summary": {
                "independent": 1, "review_due": 0, "total_objectives": 1, "current_objective_id": None,
            },
        }
        out = self.run_harness({"library": library(row), "outline": outline(objectives), "row": row})
        self.assertEqual(out["desk"]["primaryKind"], "complete")
        self.assertEqual(out["desk"]["primaryLabel"], "Course complete")
        self.assertIn("Every section has evidence", out["sentence"])

    def test_a_needs_review_objective_is_not_a_due_count(self) -> None:
        objectives = [objective("obj_1", "needs_review", lesson_state="needs_review",
                                lesson_rejection_reasons=PARKED_REASONS)]
        row = {
            "next_step": {
                "kind": "repair_lesson",
                "label": "Repair the lesson for Section 1",
                "objective_id": "obj_1",
                "section_id": "sec_1",
                "reasons": PARKED_REASONS,
            },
            "evidence_summary": {
                "independent": 0, "review_due": 0, "total_objectives": 1, "current_objective_id": "obj_1",
            },
        }
        out = self.run_harness({"library": library(row), "outline": outline(objectives), "row": row})
        self.assertEqual(out["desk"]["dueCount"], 0)
        self.assertEqual(out["progress"]["due"], 0)
        # The desk opens the parked section, named by the backend, not by recency.
        self.assertEqual(out["desk"]["current"], "obj_1")
        self.assertEqual(out["mainline"], "obj_1")

    def test_a_review_due_row_is_still_the_review_row(self) -> None:
        objectives = [
            objective("obj_1", "needs_review", lesson_state="needs_review"),
            objective("obj_2", "review_due", ordinal=2),
        ]
        row = {
            "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
            "evidence_summary": {
                "independent": 0, "review_due": 1, "total_objectives": 2, "current_objective_id": "obj_1",
            },
        }
        out = self.run_harness({"library": library(row), "outline": outline(objectives), "row": row})
        self.assertEqual(out["desk"]["dueCount"], 1)
        self.assertEqual(out["mainline"], "obj_2")

    def test_the_state_words_are_distinct(self) -> None:
        objectives = [
            objective("obj_1", "review_due"),
            objective("obj_2", "needs_review", ordinal=2),
            objective("obj_3", "not_started", ordinal=3, lesson_state="needs_review"),
        ]
        row = {"next_step": {"kind": "start_lesson", "label": "Start"}}
        out = self.run_harness({"library": library(row), "outline": outline(objectives), "row": row})
        review_due, needs_review, parked = out["semantics"]
        self.assertEqual(review_due["key"], "review")
        self.assertEqual(review_due["label"], "Review due")
        self.assertEqual(needs_review["key"], "unwritten")
        self.assertEqual(needs_review["label"], "Could not be written")
        self.assertEqual(parked["key"], "unwritten")
        self.assertEqual(parked["label"], "Could not be written")

    def test_a_parked_page_shows_named_reasons_and_one_repair_control(self) -> None:
        page = page_with_section(
            section_id="sec_1",
            lesson_state="needs_review",
            rejection_reasons=PARKED_REASONS,
        )
        out = self.run_harness(
            {
                "library": library({"next_step": {"kind": "repair_lesson", "label": "Repair"}}),
                "outline": outline([objective("obj_1", "not_started", lesson_state="needs_review")]),
                "page": page,
                "renderPanel": True,
            }
        )
        self.assertEqual(out["readiness"]["state"], "unwritten")
        self.assertEqual(out["readiness"]["reasons"], PARKED_REASONS)
        self.assertEqual(out["readiness"]["action"]["kind"], "repair")
        self.assertEqual(out["readiness"]["sectionId"], "sec_1")
        panel = out["panel"]
        self.assertIn('data-cb-readiness-action="repair"', panel)
        self.assertIn('data-cb-lesson-repair-reasons="2"', panel)
        for reason in PARKED_REASONS:
            self.assertIn(reason, panel)

    def test_a_genuine_spaced_review_never_offers_the_repair_control(self) -> None:
        page = page_with_section(state="review_due")
        out = self.run_harness(
            {
                "library": library({"next_step": {"kind": "resolve_review_due", "label": "Review"}}),
                "outline": outline([objective("obj_1", "review_due")]),
                "page": page,
                "renderPanel": True,
            }
        )
        self.assertNotEqual(out["readiness"]["state"], "unwritten")
        self.assertNotEqual((out["readiness"]["action"] or {}).get("kind"), "repair")
        self.assertNotIn('data-cb-readiness-action="repair"', out["panel"] or "")


if __name__ == "__main__":
    unittest.main()
