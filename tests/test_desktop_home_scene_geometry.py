"""CP-053 — the wide Home scene: geometry from the binding reference, paint from the token layer.

The reference frame is `docs/concept-parity/refs/home-concept-owner.png` (1344x768). The scene's
numbers were measured off it and now live in the v3 stylesheet
(`desktop/src/76-v3-scope.js`, addressed by `data-cb-home-scene-*` hooks), while every colour,
shadow and type size comes from the token contract. These tests assert four things:

  * the scene mounts only at the route breakpoint, and the narrow Home is untouched;
  * the shipped stylesheet still carries the measured geometry;
  * the rendered scene markup carries hooks and no inline paint — colour, shadow and font size
    cannot leak back into the module, which is what `test_desktop_tokens*` and
    `test_desktop_type_scale` police;
  * a card's bar is `sections_done/sections_total` and nothing invents a rating.

Pixel parity with the reference is a capture measurement (`docs/concept-parity/cp053/PASSES.md`),
not a unit test.
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

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
const { CoursebookHome } = await import('./plugin.js')

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
  updated_at: '2026-11-01T18:00:00.000000+00:00',
  revision: 0,
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
process.stdout.write(JSON.stringify({ html }))
"""

FOUR = [
    {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
    {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 2},
    {"title": "Astronomy", "sections_total": 6, "sections_done": 1},
    {"title": "Sourdough", "sections_total": 3, "sections_done": 0},
]


def css_block(source: str, hook: str) -> str:
    """The declarations of the first rule whose selector carries `hook` (the base rule, not a child)."""
    match = re.search(
        r'\[data-cb-v3\] \[' + re.escape(hook) + r'\]\s*\{([^}]*)\}', source
    )
    if not match:
        raise AssertionError(f"stylesheet no longer declares [data-cb-v3] [{hook}]")
    return match.group(1)


def declaration(block: str, prop: str) -> str:
    match = re.search(r'(?:^|[\s;])' + re.escape(prop) + r':\s*([^;]+);', block)
    if not match:
        raise AssertionError(f"no {prop} in rule: {block[:120]}")
    return match.group(1).strip()


def markup_only(html: str) -> str:
    return re.sub(r'data:[^"\s)]+', 'data:', html)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HomeSceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp053-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(cls.source, encoding="utf-8")
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

    def render(self, width: int, rows=None) -> str:
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
        return json.loads(result.stdout)["html"]

    # --- the breakpoint and the narrow Home ------------------------------------------------

    def test_the_scene_is_used_only_at_the_wide_breakpoint(self) -> None:
        narrow = self.render(1199)
        self.assertNotIn("data-cb-home-scene", narrow)
        self.assertIn('data-cb-home-card=""', narrow)
        wide = self.render(1200)
        self.assertIn('data-cb-home-scene=""', wide)
        self.assertNotIn('data-cb-home-card=""', wide)

    def test_narrow_home_keeps_its_shelf_and_see_all(self) -> None:
        # After the CP-040 seam, the narrow Home is the v3 hub; the scene must never appear there.
        html = self.render(1049)
        self.assertNotIn("data-cb-home-scene", html)
        self.assertIn("data-cb-home-layout=", html)
        self.assertIn("data-cb-home-card", html)

    # --- the measured geometry lives in the stylesheet --------------------------------------

    def test_card_is_the_measured_collectible_size(self) -> None:
        card = css_block(self.source, "data-cb-home-scene-card")
        self.assertEqual(declaration(card, "width"), "176px")
        self.assertEqual(declaration(card, "height"), "175px")
        cover = css_block(self.source, "data-cb-home-scene-card] img,\n[data-cb-v3] [data-cb-home-scene-cover")
        self.assertEqual(declaration(cover, "height"), "106px")

    def test_cards_sit_on_the_measured_shelf_line(self) -> None:
        scene = css_block(self.source, "data-cb-home-scene")
        self.assertEqual(declaration(scene, "max-width"), "1344px")
        self.assertEqual(declaration(scene, "height"), "768px")
        cards = css_block(self.source, "data-cb-home-scene-cards")
        self.assertEqual(declaration(cards, "top"), "384px")
        self.assertEqual(declaration(cards, "left"), "273px")
        self.assertEqual(declaration(cards, "height"), "175px")
        self.assertEqual(declaration(cards, "gap"), "24px")

    def test_planks_and_objects_hold_the_reference_positions(self) -> None:
        one = css_block(self.source, "data-cb-home-scene-plank-one")
        self.assertEqual(declaration(one, "left"), "219px")
        self.assertEqual(declaration(one, "width"), "915px")
        self.assertEqual(declaration(one, "top"), "559px")
        two = css_block(self.source, "data-cb-home-scene-plank-two")
        self.assertEqual(declaration(two, "left"), "130px")
        self.assertEqual(declaration(two, "width"), "1150px")
        self.assertEqual(declaration(two, "top"), "684px")
        tag = css_block(self.source, "data-cb-home-scene-tag")
        self.assertEqual(declaration(tag, "left"), "880px")
        self.assertEqual(declaration(tag, "top"), "606px")
        self.assertEqual(declaration(tag, "width"), "164px")
        self.assertEqual(declaration(tag, "height"), "88px")
        clock = css_block(self.source, "data-cb-home-scene-clock")
        self.assertEqual(declaration(clock, "left"), "1042px")
        self.assertEqual(declaration(clock, "width"), "118px")
        fox = css_block(self.source, "data-cb-home-scene-fox")
        self.assertEqual(declaration(fox, "left"), "1088px")
        self.assertEqual(declaration(fox, "top"), "526px")
        hero = css_block(self.source, "data-cb-home-scene-hero")
        self.assertEqual(declaration(hero, "top"), "128px")

    def test_the_scene_paints_from_tokens_only(self) -> None:
        scene_rules = re.findall(r'\[data-cb-v3\] \[data-cb-home-scene[^{]*\{[^}]*\}', self.source)
        self.assertGreaterEqual(len(scene_rules), 12, "the scene stylesheet is missing")
        joined = "\n".join(scene_rules)
        self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', joined), "raw hex in the scene block")
        self.assertIsNone(re.search(r'rgba?\(', joined), "raw colour function in the scene block")
        for shadow in re.findall(r'box-shadow:\s*([^;]+);', joined):
            self.assertTrue(shadow.strip().startswith("var(--cb3-elev"),
                            f"shadow is not an elevation token: {shadow}")
        for size in re.findall(r'font-size:\s*([^;]+);', joined):
            self.assertTrue(size.strip().startswith("var(--cb3-text-"),
                            f"font size escapes the type scale: {size}")

    def test_the_rendered_scene_carries_hooks_and_no_inline_paint(self) -> None:
        html = self.render(1344)
        for hook in ("data-cb-home-scene-hero", "data-cb-home-scene-question",
                     "data-cb-home-scene-subline", "data-cb-home-scene-cta",
                     "data-cb-home-scene-cards", "data-cb-home-scene-card",
                     "data-cb-home-scene-title", "data-cb-home-scene-progress",
                     "data-cb-home-scene-meta", "data-cb-home-scene-plank-one",
                     "data-cb-home-scene-plank-two", "data-cb-home-scene-tag",
                     "data-cb-home-scene-fox"):
            self.assertIn(hook, html)
        scene = markup_only(html[html.index('data-cb-home-scene=""'):])
        for prop in ("color:", "background:", "box-shadow:", "font-size:", "transform: rotate"):
            self.assertNotIn(prop, scene, f"inline paint leaked into the scene: {prop}")

    # --- honesty --------------------------------------------------------------------------

    def test_a_card_bar_reads_sections_not_a_rating(self) -> None:
        html = self.render(1344, [
            {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
            {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 1},
        ])
        self.assertIn("5 of 8 sections", html)
        self.assertIn("1 of 4 sections", html)
        self.assertIn("width:63%", html.replace(" ", ""))
        self.assertIn("width:25%", html.replace(" ", ""))
        copy = markup_only(html)
        for invented in ("\u2605", "rating", "stars", "XP", "streak"):
            self.assertNotIn(invented, copy)

    def test_a_card_without_progress_says_so_and_invents_nothing(self) -> None:
        html = self.render(1344, [{"title": "Sourdough", "sections_total": 0, "sections_done": 0}])
        self.assertIn("Not started", html)
        self.assertIn("width:0%", html.replace(" ", ""))

    def test_the_four_visible_titles_are_the_reference_strings(self) -> None:
        html = self.render(1344)
        for title in ("Auto Repair Fundamentals", "Japanese Cafe Basics", "Astronomy", "Sourdough"):
            self.assertIn(title, html)
        self.assertIn("New course", html)
        self.assertNotIn("Repir", html)
        self.assertNotIn("Asttomamy", html)


if __name__ == "__main__":
    unittest.main()
