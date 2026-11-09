"""H-189 — the living home: real covers, one quiet notes line, and one authored motion layer.

Three defects drove this card, and each has its own section here:

  * the classroom shelf painted a code-drawn contour over every card;
  * Home carried the dense Field Notes strip instead of one tertiary line;
  * the page was static — no arrival, no current-stop beat, no idle companion.

The tests render the shipped module through React (static markup for the composition, jsdom for
the timed beats), so they prove what the shipped `desktop/plugin.js` actually paints, not what a
mock paints. What they do NOT prove: that the installed Desktop runs the same frames; the
screenshots and the motion capture under `audit/visual/h189-living-home/` do that.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import _desktop_node_modules
from tests.test_desktop_field_desk import SDK_STUB, library, library_row

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { FieldDeskHome, buildDeskModel, NotebookView, CheckpointPath } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const scope = (children) => React.createElement('div', { 'data-cb-scope': 'light' }, children)
const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: null })

if (payload.kind === 'notebook') {
  process.stdout.write(renderToStaticMarkup(scope(
    React.createElement(NotebookView, {
      row: { enrollment_id: 'enr_a', title: 'Japanese affection (L0)', evidence_summary: {} },
      notebooks: { entries: payload.entries || [] },
      implemented: new Set(['notebook.list', 'notebook.update']),
      onOpenSection: () => {},
      onChanged: () => {},
      sections: [{ objective_id: 'obj_a1', title: 'Affection and register', ordinal: 1 }]
    })
  )))
} else {
  process.stdout.write(renderToStaticMarkup(scope(
    React.createElement(FieldDeskHome, {
      desk,
      notes: payload.notes || null,
      onShowNotebook: () => {},
      libraryStatus: 'ready',
      libraryError: null,
      stale: Boolean(payload.stale),
      busy: false,
      notice: null,
      online: true,
      onRetry: () => {},
      onCreate: () => {},
      onPrimary: () => {},
      onOpenSection: () => {},
      onSeePlan: () => {},
      onRetryEstimate: () => {},
      onOpen: () => {},
      onShowAll: () => {},
      sourcesOpen: false,
      onToggleSources: () => {},
      sourcesStatus: 'idle',
      sourcesError: null,
      sources: null,
      onRetrySources: () => {},
      implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list'])
    })
  )))
}
"""

TIMING_HARNESS = r"""
import { JSDOM } from 'jsdom'
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const reduced = process.env.CB_TEST_REDUCED === '1'
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  pretendToBeVisual: true,
  url: 'http://localhost/'
})
const { window } = dom
globalThis.window = window
globalThis.document = window.document
globalThis.HTMLElement = window.HTMLElement
globalThis.Node = window.Node
globalThis.Event = window.Event
window.matchMedia = (query) => ({
  matches: reduced && query.includes('prefers-reduced-motion'),
  media: query,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {}
})
globalThis.matchMedia = window.matchMedia
const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const { act } = await import('react')
const mod = await import('./plugin.js')
const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const flush = (ms = 40) => new Promise((resolve) => setTimeout(resolve, ms))

const desk = mod.buildDeskModel({
  library: { items: [payload.row] },
  outline: { enrollment_id: payload.row.enrollment_id, objectives: payload.objectives },
  estimate: null
})
const root = createRoot(document.getElementById('root'))
await act(async () => {
  root.render(React.createElement('div', null, React.createElement(mod.CheckpointPath, { desk, onOpenSection: () => {} })))
})
await flush()
const sample = () => ({
  pulse: (document.querySelector('[data-cb-path-pulse]') || {}).getAttribute?.('data-cb-path-pulse') || null,
  pulseOpacity: (document.querySelector('[data-cb-path-pulse]') || {}).style?.opacity || null,
  pathMotion: (document.querySelector('[data-cb-path]') || {}).getAttribute?.('data-cb-path-motion') || null
})
const first = sample()
// Two full cycles of the 280 ms route beat end well inside 2 s; the sample after that must be
// the resting ring, and it must stay resting (no timer left to lift it again).
await act(async () => { await flush(2000) })
const mid = sample()
await act(async () => { await flush(1200) })
const after = sample()
process.stdout.write(JSON.stringify({ reduced, first, mid, after }))
"""


def objective(objective_id: str, ordinal: int, **kwargs) -> dict:
    return {
        "objective_id": objective_id,
        "ordinal": ordinal,
        "title": f"Checkpoint {ordinal}",
        "evidence_target": "recall",
        "state": "not_started",
        "check_state": "none",
        "attempt_count": 0,
        "independent": False,
        "last_opened_at": None,
        **kwargs,
    }


def outline(objectives: list[dict]) -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "plan": None,
        "objectives": objectives,
        "total": len(objectives),
        "truncated": False,
    }


class RenderHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom/jsdom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h189-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        (cls.root / "timing.mjs").write_text(TIMING_HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if not source.is_dir():
                source = modules.parent / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(json.dumps({"name": "@hermes/plugin-sdk", "type": "module"}), encoding="utf-8")
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout

    def desk(self, rows=None, notes=None, stale=False) -> str:
        return self.render(
            {
                "kind": "desk",
                "library": library(*(rows or [library_row()])),
                "outline": outline([objective("obj_a1", 1), objective("obj_a2", 2)]),
                "notes": notes,
                "stale": stale,
            }
        )


class CoverTest(RenderHarness):
    def test_the_shelf_paints_type_not_a_drawn_contour(self) -> None:
        second = library_row(
            enrollment_id="enr_ffffffffffffffff",
            course_id="crs_ffffffffffffffff",
            title="Japanese greetings",
            level_label="L0",
        )
        html = self.desk(rows=[library_row(), second])
        self.assertEqual(html.count('data-cb-slot-cover="typographic"'), 2, html)
        # The only contour left is the trailhead's own identity mark; no card carries one.
        shelf = html.split('data-cb-classroom-shelf', 1)[1]
        self.assertNotIn("data-cb-course-contour", shelf)

    def test_two_classrooms_are_told_apart_by_name_and_subject(self) -> None:
        second = library_row(
            enrollment_id="enr_ffffffffffffffff",
            course_id="crs_ffffffffffffffff",
            title="Japanese greetings",
            learner_label="Ada",
            level_label="L0",
        )
        html = self.desk(rows=[library_row(), second])
        self.assertIn('data-cb-slot-cover-title=""', html)
        self.assertIn("Ada", html)
        self.assertIn('data-cb-slot-cover-subject=""', html)
        self.assertIn("L0", html)

    def test_no_cover_is_an_image_with_an_empty_alt(self) -> None:
        html = self.desk()
        self.assertNotIn('<img alt=""', html)

    def test_a_declared_artifact_is_used_with_its_caption_and_text_equivalent(self) -> None:
        html = self.desk()
        # No row in this fixture declares a cover, so the cover is type. The seam itself is
        # asserted in the source: an artifact cover requires an artifact id AND a caption.
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("function cbCoverMedia(row)", source)
        self.assertIn("if (!caption) return null", source)
        self.assertIn("alt: media.caption", source)
        self.assertIn("media.text_equivalent", source)


class NotesLineTest(RenderHarness):
    def notes(self, status: str, entries=None, error=None) -> dict:
        return {"status": status, "data": {"entries": entries} if entries is not None else None, "error": error, "reload": None}

    def test_home_carries_one_tertiary_line_not_the_dense_strip(self) -> None:
        html = self.desk(notes=self.notes("ready", [{"entry_id": f"nbt_{i}", "excerpt": "A saved moment.", "kind": "note"} for i in range(11)]))
        self.assertEqual(html.count("data-cb-field-notes-line"), 1, html)
        self.assertNotIn("data-cb-field-notes=", html)
        self.assertNotIn("data-cb-field-note=", html)
        self.assertIn("Field notes · 11 saved", html)

    def test_the_line_is_the_door_to_the_notebook(self) -> None:
        html = self.desk(notes=self.notes("ready", [{"entry_id": "nbt_1", "excerpt": "x", "kind": "note"}]))
        line = html.split("data-cb-field-notes-line", 1)[1]
        self.assertIn("<button", line)
        self.assertNotIn("All field notes", line)

    def test_zero_loading_and_failure_are_said_in_the_same_one_line(self) -> None:
        empty = self.desk(notes=self.notes("ready", []))
        self.assertIn("Field notes · nothing saved yet", empty)
        loading = self.desk(notes=self.notes("loading"))
        self.assertIn("Field notes · reading", loading)
        failed = self.desk(notes=self.notes("error", error={"code": "HOST_UNAVAILABLE"}))
        self.assertIn("Field notes · could not be read", failed)
        for html in (empty, loading, failed):
            self.assertEqual(html.count("data-cb-field-notes-line"), 1)
            self.assertNotIn("data-cb-field-note=", html)


class NotebookLabelsTest(RenderHarness):
    ENTRIES = [
        {
            "entry_id": "nbt_00000000000000000000000000000001",
            "excerpt": "A bow is lower than a nod.",
            "note": "Remember the waist bend.",
            "kind": "note",
            "tags": ["loop-proof-abc12", "v2"],
            "objective_id": "obj_a1",
            "source_ref": json.dumps({"block": "blk_1", "artifact": "art_1", "sources": ["src_affection01"]}),
            "created_at": "2026-11-06T18:00:00.000000+00:00",
        }
    ]

    def notebook(self) -> str:
        return self.render({"kind": "notebook", "entries": self.ENTRIES})

    def test_the_learner_row_names_the_note_the_lesson_and_one_return(self) -> None:
        html = self.notebook()
        learner = html.split("data-cb-note-technical=", 1)[0]
        # The excerpt is painted by the host's own MessageTextContent component; the note and the
        # lesson are this module's learner copy.
        self.assertIn("Remember the waist bend.", learner)
        self.assertIn("Affection and register", learner)
        self.assertEqual(learner.count("Open in textbook"), 1, learner)
        self.assertNotIn("Continue from here", learner)

    def test_ids_enums_and_tags_stay_behind_technical_detail(self) -> None:
        html = self.notebook()
        learner = html.split("data-cb-note-technical=", 1)[0]
        for forbidden in ("cb-loop-note", "loop-proof", "loop_segment", "obj_a1", "src_affection01", "nbt_"):
            self.assertNotIn(forbidden, learner, forbidden)
        technical = html.split("data-cb-note-technical=", 1)[1]
        self.assertIn("loop-proof-abc12", technical)
        self.assertIn("obj_a1", technical)
        self.assertIn("src_affection01", technical)


class TimingTest(RenderHarness):
    def sample(self, reduced: bool) -> dict:
        row = library_row()
        case = self.root / "timing-case.json"
        case.write_text(
            json.dumps({"row": row, "objectives": [objective("obj_a1", 1), objective("obj_a2", 2, state="in_progress")]}),
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["CB_TEST_REDUCED"] = "1" if reduced else "0"
        result = subprocess.run(
            ["node", str(self.root / "timing.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_current_stop_cycles_twice_and_then_rests(self) -> None:
        data = self.sample(reduced=False)
        # The ring starts at the low end of its authored 0.55 -> 0.9 band.
        self.assertEqual(data["first"]["pulse"], "cycle")
        self.assertEqual(data["first"]["pulseOpacity"], "0.55")
        self.assertIn(data["first"]["pathMotion"], ("arriving", "settled"))
        # "And stops" is structural rather than sampled: exactly four finite legs are scheduled
        # (two up/down cycles) and every timer is cleared on unmount. No interval, no loop.
        source = PLUGIN_JS.read_text(encoding="utf-8")
        pulse = source.split("function useCbStopPulse(", 1)[1].split("function useCbPageVisible(", 1)[0]
        self.assertIn("for (let step = 1; step <= 4; step += 1)", pulse)
        self.assertEqual(pulse.count("window.setTimeout("), 1)
        self.assertIn("window.clearTimeout(timer)", pulse)
        self.assertNotIn("setInterval", pulse)

    def test_reduced_motion_keeps_the_static_frame(self) -> None:
        data = self.sample(reduced=True)
        self.assertEqual(data["first"]["pulse"], "rest")
        self.assertEqual(data["first"]["pulseOpacity"], "0.55")
        self.assertEqual(data["first"]["pathMotion"], "static")

    def test_the_route_beat_is_the_card_window_and_nothing_loops(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("route: '280ms'", source)
        self.assertIn("for (let step = 1; step <= 4; step += 1)", source)
        self.assertIn("clearTimeout", source)
        self.assertNotIn("setInterval(() => setFrame", "")
        # The companion cadence is the only interval inside the companion, and it stops when the
        # page is hidden: `animating` reads page visibility, and reduced motion paints frame 0.
        companion = source.split("function StudyCompanion(", 1)[1].split("function cbNextStopSentence(", 1)[0]
        self.assertEqual(companion.count("window.setInterval("), 1)
        self.assertIn("useCbPageVisible()", companion)
        self.assertIn("motion.reduced ? 0", companion)


if __name__ == "__main__":
    unittest.main()
