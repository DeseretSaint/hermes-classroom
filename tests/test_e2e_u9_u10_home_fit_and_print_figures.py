"""E2E U9/U10 — the wide Home fits its own art, and paper never captions a missing figure.

Two defects, one shipped module (`desktop/plugin.js`):

* **U9** — the room is authored at 1344x768 and chosen from 1200 px of route width up, so at 1250
  the fixed frame plus `overflow: hidden` cut the fox (left 1110 + 208) by more than half. The stage
  now scales into the box it is measured in, and a fifth course is reachable from the room's own
  `See all`.
* **U10** — the print sheet emitted one `.caption` per media child and the sheet carries no `<img>`,
  so paper said "A cutaway of the brake caliper" under nothing. Each media child now prints its own
  omission line, the sheet never falls back to the structural `label`, and a block whose only
  content is a figure still prints.

Everything asserted here is read back from a render of the built module, not from a copy of the
source, and the geometry constants are taken from the component's own `CB_HOME_SCENE` frame.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, block, document

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

FRAME_WIDTH = 1344
FRAME_HEIGHT = 768
ROUTE_1250 = 1250
FOX_LEFT = 1110
FOX_SIZE = 208
FIGURE_OMITTED = "Figure not printed - see the lesson screen."

HARNESS = r"""
// The SDK stub's viewport atom reads `__CB_TEST_WIDTH__` at import time, so one process is one
// route width; the suite runs a separate process per width.
globalThis.__CB_TEST_WIDTH__ = String((process.env.CB_TEST_WIDTH || '1250'))
const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')

const facts = { scene: mod.CB_HOME_SCENE }

if (payload.mode === 'home') {
  const rows = (payload.rows || []).map((row, index) => ({
    enrollment_id: `enr_${index}`,
    course_id: `crs_${index}`,
    title: row.title,
    subtitle: null,
    recipe: 'committed',
    level_label: null,
    locale: null,
    learner_label: null,
    enrollment_status: 'active',
    course_status: 'active',
    provenance: { source: 'authored', pack_id: null, pack_version: null },
    next_step: { kind: 'resume_lesson', label: 'Resume lesson' },
    evidence_summary: { independent: 0, review_due: 0, total_objectives: 4, current_objective_id: 'obj' },
    warning: null,
    updated_at: row.updated_at || '2026-11-01T18:00:00.000000+00:00',
    revision: 0,
    sections_total: row.sections_total,
    sections_done: row.sections_done
  }))
  facts.html = renderToStaticMarkup(
    React.createElement(mod.CoursebookHome, {
      library: {
        status: 'ready',
        data: { items: rows, next_cursor: null, total: rows.length, empty_reason: null, applied_filter: 'all' },
        error: null,
        stale: false
      },
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
}

if (payload.mode === 'print') {
  facts.printFigureOnly = mod.cbLessonPrintHtml(payload.figureOnly, {})
  facts.printLabelOnly = mod.cbLessonPrintHtml(payload.labelOnly, {})
}

process.stdout.write(JSON.stringify(facts), () => process.exit(0))
"""


def figure_block(media: list) -> dict:
    """One block whose only content is the figure: no headline, no prose."""
    return block("blk_figure0001", "explain", "", short=None, deep="", media=media)


def figure_document(media: list) -> dict:
    return document(guided=True, blocks=[figure_block(media)], check_id=None)


FIVE_ROWS = [
    {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
    {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 2},
    {"title": "Astronomy", "sections_total": 6, "sections_done": 1},
    {"title": "Sourdough", "sections_total": 3, "sections_done": 0},
    {"title": "Brake Service", "sections_total": 5, "sections_done": 0},
]

FOUR_ROWS = FIVE_ROWS[:4]

FIGURE_ONLY = figure_document([
    {
        "kind": "visual",
        "role": "illustration",
        "artifact_id": "art_0123456789abcdef",
        "purpose": "A cutaway of the brake caliper.",
        "text_equivalent": "A cutaway of the brake caliper.",
        "label": "Figure",
    }
])

LABEL_ONLY = figure_document([
    {
        "kind": "visual",
        "role": "illustration",
        "artifact_id": "art_fedcba9876543210",
        "label": "A cutaway of the brake caliper",
    }
])


class WideHomeAndPrintFiguresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render the runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-e2e-u9-u10-")
        cls.root = Path(cls.tmp.name)
        if stage_desktop_node_modules(cls.root) is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        write_sdk_stub(cls.root, SDK_STUB)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        cls.at_1250 = cls.render_case({"mode": "home", "rows": FIVE_ROWS}, width=ROUTE_1250)
        cls.at_wide = cls.render_case({"mode": "home", "rows": FOUR_ROWS}, width=FRAME_WIDTH)
        cls.print = cls.render_case({"mode": "print", "figureOnly": FIGURE_ONLY, "labelOnly": LABEL_ONLY})

    @classmethod
    def render_case(cls, payload: dict, width: int = FRAME_WIDTH) -> dict:
        case = cls.root / f"case-{payload['mode']}-{width}.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=240,
            env={**os.environ, "CB_TEST_WIDTH": str(width)},
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-4000:])
        return json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── U9: the room fits the route it is drawn in ───────────────────────────────────────────

    def fit(self, html: str):
        """(scale attribute, scale in the scene's CSS variable, fit-box height) of one render."""
        wrapper = re.search(r'<div data-cb-home-scene-fit[^>]*>', html)
        self.assertIsNotNone(wrapper, "the wide Home does not render a fit box")
        tag = wrapper.group(0)
        attr = re.search(r'data-cb-home-scene-scale="([^"]+)"', tag)
        height = re.search(r"height:(-?[\d.]+)px", tag)
        scene = re.search(r'<div[^>]*data-cb-home-scene=""[^>]*>', html)
        self.assertIsNotNone(scene, "the wide Home does not render the room")
        variable = re.search(r"--cb-home-scene-scale:([^;\"]+)", scene.group(0))
        return (
            float(attr.group(1)) if attr else None,
            float(variable.group(1)) if variable else None,
            float(height.group(1)) if height else None,
        )

    def test_the_room_is_drawn_at_1250_with_its_own_scale(self) -> None:
        html = self.at_1250["html"]
        self.assertIn('data-cb-home-scene=""', html)
        attr, variable, height = self.fit(html)
        self.assertIsNotNone(attr, "the fit box carries no measured scale")
        self.assertIsNotNone(variable, "the scene carries no scale property")
        self.assertIsNotNone(height, "the fit box carries no height")
        self.assertAlmostEqual(attr, ROUTE_1250 / FRAME_WIDTH, places=4)
        self.assertLess(attr, 1.0, "a room narrower than the frame must scale, not crop")
        self.assertAlmostEqual(variable, attr, places=4, msg="the stylesheet does not receive the scale")
        self.assertEqual(height, round(FRAME_HEIGHT * attr), "the fit box height is not the scaled frame")

    def test_the_fox_holds_its_right_edge_inside_the_1250_room(self) -> None:
        _, scale, _ = self.fit(self.at_1250["html"])
        frame = self.at_1250["scene"]
        self.assertEqual(frame["canvas"]["width"], FRAME_WIDTH, "the authored frame moved")
        right_edge = (frame["fox"]["left"] + frame["fox"]["size"]) * scale
        self.assertEqual(frame["fox"]["left"], FOX_LEFT)
        self.assertEqual(frame["fox"]["size"], FOX_SIZE)
        self.assertLessEqual(
            right_edge,
            ROUTE_1250,
            f"the fox's right edge sits at {right_edge:.1f}px in a {ROUTE_1250}px room",
        )
        # The whole authored frame fits, not just the fox: a scale that fits the fox and clips the
        # ledge would still be a crop.
        self.assertLessEqual(FRAME_WIDTH * scale, ROUTE_1250 + 0.5)

    def test_the_scene_is_not_scaled_above_its_authored_frame(self) -> None:
        _, scale, height = self.fit(self.at_wide["html"])
        self.assertEqual(scale, 1.0, "a wide route upscales a plate authored at 1344")
        self.assertEqual(height, FRAME_HEIGHT)

    def test_a_fifth_course_is_reachable_from_the_room(self) -> None:
        html = self.at_1250["html"]
        button = re.search(r"<button[^>]*data-cb-home-scene-see-all[^>]*>(.*?)</button>", html, re.S)
        self.assertIsNotNone(button, "the room has no See all for a fifth course")
        self.assertIn("See all", button.group(1))
        # Four cards, not five: the door is the fifth course's way in, not a cropped fifth card.
        self.assertEqual(html.count("data-cb-home-scene-card="), 4)

    def test_the_new_course_tag_does_not_stand_in_for_see_all(self) -> None:
        # VQ-011's kraft tag is a course, not an overflow control; only a real control counts.
        html = self.at_1250["html"]
        self.assertIn("data-cb-home-scene-tag=", html)
        self.assertIn("data-cb-home-scene-see-all=", html)

    def test_four_courses_show_no_see_all(self) -> None:
        html = self.at_wide["html"]
        self.assertNotIn("data-cb-home-scene-see-all", html, "a dead See all with nothing behind it")

    # ── U10: paper never captions a missing figure ──────────────────────────────────────────

    def test_a_figure_only_sheet_prints_text_and_never_an_image(self) -> None:
        html = self.print["printFigureOnly"]
        self.assertNotIn("<img", html, "the print sheet started printing an image")
        self.assertIn(FIGURE_OMITTED, html, "the sheet captioned a figure it does not print")
        self.assertIn("A cutaway of the brake caliper.", html, "the text equivalent was dropped")

    def test_the_omission_line_comes_before_its_description(self) -> None:
        html = self.print["printFigureOnly"]
        note = html.find(FIGURE_OMITTED)
        caption = html.find("A cutaway of the brake caliper.")
        self.assertGreaterEqual(note, 0)
        self.assertGreater(caption, note, "a description without the omission line reads as a caption")

    def test_a_label_never_stands_in_for_a_missing_figure(self) -> None:
        html = self.print["printLabelOnly"]
        self.assertIn(FIGURE_OMITTED, html)
        self.assertNotIn("A cutaway of the brake caliper", html, "the structural label reached the paper")

    def test_a_block_with_only_a_figure_is_not_dropped(self) -> None:
        html = self.print["printLabelOnly"]
        # The defect's other half: with no prose the block was skipped entirely, so paper said
        # nothing at all about the figure the lesson carries.
        self.assertIn("data-cb-print-media-omitted", html)
        self.assertEqual(html.count("data-cb-print-media-omitted"), 1)


if __name__ == "__main__":
    unittest.main()
