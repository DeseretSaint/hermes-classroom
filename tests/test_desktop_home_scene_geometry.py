"""CP-053 — the wide Home scene's measured geometry, and its narrow fallback.

The binding reference frame is `docs/concept-parity/refs/home-concept-owner.png` (1344x768). The
scene's numbers were measured off it, live in `CB_HOME_SCENE`, and are mirrored by the standalone
proof `design/home-scene.html`. These tests do three things:

  * render the shipped module at and above the 1200 px scene breakpoint and assert the scene mounts
    with the authored geometry (card size, shelf and ledge position, fox/clock/tag placement);
  * assert the proof page and the shipped constants still carry the same numbers, so a parity
    measurement taken on the proof cannot describe a scene the plugin does not ship;
  * assert the narrow Home is untouched — below 1200 px the compact shelf renders and the scene
    never appears.

What this does not prove: pixel parity with the reference. That is a capture measurement
(`scripts/compare-ref.sh` / the card's pass log), not a unit test.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
PROOF = ROOT / "design" / "home-scene.html"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
const { CoursebookHome, CB_HOME_SCENE } = await import('./plugin.js')

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
  next_step: { kind: 'resume_lesson', label: 'Resume this lesson' },
  evidence_summary: { independent: 1, review_due: 0, total_objectives: 4, current_objective_id: 'obj' },
  warning: null,
  updated_at: '2026-11-01T18:00:00.000000+00:00',
  revision: 1,
  sections_total: row.sections_total,
  sections_done: row.sections_done
}))

const html = renderToStaticMarkup(
  React.createElement(CoursebookHome, {
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
    onRetry: () => {}
  })
)
process.stdout.write(JSON.stringify({ html, scene: CB_HOME_SCENE }))
"""


def style_with(html: str, declaration: str) -> dict:
    """The first inline style attribute carrying `declaration`, parsed into css properties."""
    for blob in re.findall(r'style="([^"]*)"', html):
        if declaration in blob:
            return parse_style(blob)
    raise AssertionError(f"no inline style carrying {declaration}")


def style_for_attr(html: str, attribute: str) -> dict:
    """The inline style of the first element carrying `attribute` (as written in the markup)."""
    match = re.search(re.escape(attribute) + r'[^>]*?style="([^"]*)"', html)
    if not match:
        raise AssertionError(f"no element carrying {attribute}")
    return parse_style(match.group(1))


def parse_style(blob: str) -> dict:
    out = {}
    for part in blob.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def markup_only(html: str) -> str:
    """The markup with every inlined asset dropped, so assertions read the copy, not base64."""
    return re.sub(r'data:[^"\s)]+', 'data:', html)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HomeSceneGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp053-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, width: int, rows=None) -> dict:
        payload = {"width": width, "rows": rows if rows is not None else FOUR}
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_scene_is_used_only_at_the_wide_breakpoint(self) -> None:
        narrow = self.render(1199)
        self.assertNotIn("data-cb-home-scene", narrow["html"])
        self.assertIn('data-cb-home-card=""', narrow["html"])
        wide = self.render(1200)
        self.assertIn('data-cb-home-scene=""', wide["html"])
        self.assertNotIn('data-cb-home-card=""', wide["html"])

    def test_narrow_home_keeps_its_shelf_and_see_all(self) -> None:
        narrow = self.render(1049)
        html = narrow["html"]
        self.assertEqual(html.count('data-cb-home-card=""'), 4)
        self.assertIn("See all", html)
        self.assertNotIn("data-cb-home-scene", html)

    def test_card_is_the_measured_collectible_size(self) -> None:
        data = self.render(1344)
        html = data["html"]
        self.assertEqual(html.count("data-cb-home-scene-card"), 4)
        style = style_for_attr(html, 'data-cb-home-scene-card=""')
        self.assertEqual(style["width"], "176px")
        self.assertEqual(style["height"], "175px")
        self.assertEqual(style["border-radius"], "7px")
        cover = style_for_attr(html, 'data-cb-home-scene-cover')
        self.assertEqual(cover["height"], "106px")

    def test_cards_sit_on_the_measured_shelf_line(self) -> None:
        data = self.render(1344)
        cards = style_for_attr(data["html"], 'data-cb-home-scene=""')
        self.assertEqual(cards["height"], "768px")
        self.assertIn("1344px", cards["max-width"])
        row = style_for_attr(data["html"], 'role="list" aria-label="Your courses"')
        self.assertEqual(row["top"], "384px")
        self.assertEqual(row["left"], "273px")
        self.assertEqual(row["height"], "175px")
        self.assertEqual(row["gap"], "24px")

    def test_planks_and_objects_hold_the_reference_positions(self) -> None:
        data = self.render(1344)
        html = data["html"]
        shelf = style_with(html, 'top:559px')
        self.assertEqual(shelf["left"], "219px")
        self.assertEqual(shelf["width"], "915px")
        ledge = style_with(html, 'top:684px')
        self.assertEqual(ledge["left"], "130px")
        self.assertEqual(ledge["width"], "1150px")
        tag = style_with(html, 'top:606px')
        self.assertEqual(tag["left"], "880px")
        self.assertEqual(tag["width"], "164px")
        self.assertEqual(tag["height"], "88px")
        clock = style_with(html, 'left:1042px')
        self.assertEqual(clock["width"], "118px")
        fox = style_with(html, 'left:1088px')
        self.assertEqual(fox["top"], "526px")

    def test_a_card_bar_reads_sections_not_a_rating(self) -> None:
        rows = [
            {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
            {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 1},
        ]
        html = self.render(1344, rows)["html"]
        self.assertIn('data-cb-home-scene-meta=""', html)
        self.assertIn("5 of 8 sections", html)
        self.assertIn("1 of 4 sections", html)
        self.assertIn("width:63%", html.replace(" ", ""))
        self.assertIn("width:25%", html.replace(" ", ""))
        copy = markup_only(html)
        for invented in ("\u2605", "rating", "stars", "XP", "streak"):
            self.assertNotIn(invented, copy)

    def test_a_card_without_progress_says_so_and_invents_nothing(self) -> None:
        rows = [{"title": "Sourdough", "sections_total": 0, "sections_done": 0}]
        html = self.render(1344, rows)["html"]
        self.assertIn("Not started", html)
        self.assertIn("width:0%", html.replace(" ", ""))

    def test_the_four_visible_titles_are_the_reference_strings(self) -> None:
        html = self.render(1344)["html"]
        for title in ("Auto Repair Fundamentals", "Japanese Cafe Basics", "Astronomy", "Sourdough"):
            self.assertIn(title, html)
        self.assertIn("New course", html)
        # The two reference typos stay corrected.
        self.assertNotIn("Repir", html)
        self.assertNotIn("Asttomamy", html)

    def test_the_proof_page_and_the_shipped_constants_agree(self) -> None:
        proof = PROOF.read_text(encoding="utf-8")
        scene = self.render(1344)["scene"]
        pairs = [
            (r"\.shelf\.cards \{[^}]*top: (\d+)px", scene["cards"]["top"]),
            (r"\.shelf\.cards \{[^}]*height: (\d+)px", scene["cards"]["height"]),
            (r"\.shelf \{ position: absolute; left: (\d+)px", scene["cards"]["left"]),
            (r"\.card \{ width: (\d+)px", scene["cards"]["width"]),
            (r"\.card \{ width: \d+px; height: (\d+)px", scene["cards"]["height"]),
            (r"\.card \.cover \{ height: (\d+)px", scene["cards"]["cover"]),
            (r"\.plank\.one \{ left: (\d+)px", scene["shelf"]["left"]),
            (r"\.plank\.one \{ left: \d+px; width: (\d+)px", scene["shelf"]["width"]),
            (r"\.plank\.one \{ left: \d+px; width: \d+px; top: (\d+)px", scene["shelf"]["top"]),
            (r"\.plank\.two \{ left: (\d+)px", scene["ledge"]["left"]),
            (r"\.plank\.two \{ left: \d+px; width: (\d+)px", scene["ledge"]["width"]),
            (r"\.plank\.two \{ left: \d+px; width: \d+px; top: (\d+)px", scene["ledge"]["top"]),
            (r"\.tag \{ position: absolute; left: (\d+)px", scene["tag"]["left"]),
            (r"\.tag \{ position: absolute; left: \d+px; top: (\d+)px", scene["tag"]["top"]),
            (r"\.clock \{ position: absolute; left: (\d+)px", scene["clock"]["left"]),
            (r"\.clock \{ position: absolute; left: \d+px; top: (\d+)px", scene["clock"]["top"]),
            (r"\.fox \{ position: absolute; left: (\d+)px", scene["fox"]["left"]),
            (r"\.fox \{ position: absolute; left: \d+px; top: (\d+)px", scene["fox"]["top"]),
            (r"\.hero \{ position: absolute; top: (\d+)px", scene["hero"]["top"]),
            (r"\.hero h1 \{[^}]*font-size: (\d+)px", scene["hero"]["title"]),
            (r"\.hero p \{[^}]*font-size: (\d+)px", scene["hero"]["subline"]),
        ]
        for pattern, expected in pairs:
            match = re.search(pattern, proof)
            self.assertIsNotNone(match, f"proof no longer declares {pattern}")
            self.assertEqual(int(match.group(1)), expected, f"proof and plugin disagree on {pattern}")


FOUR = [
    {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
    {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 2},
    {"title": "Astronomy", "sections_total": 6, "sections_done": 1},
    {"title": "Sourdough", "sections_total": 3, "sections_done": 0},
]


if __name__ == "__main__":
    unittest.main()
