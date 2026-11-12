"""CP-053 — the wide Home scene: geometry from the binding reference, paint from the token layer.

The reference frame is `docs/concept-parity/refs/home.png` (R-HOME; 1344x768). The scene's numbers
were measured off it and now live in the v3 stylesheet (`desktop/src/76-v3-scope.js`, addressed by
`data-cb-home-scene-*` hooks), while every colour, shadow and type size comes from the token
contract. These tests assert four things:

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


def img_tags(html: str) -> list:
    """Every `<img …>` tag in the rendered markup, as raw text."""
    return [match.group(0) for match in re.finditer(r'<img\b[^>]*>', html)]


def attr(tag: str, name: str):
    """One attribute's value from a rendered tag, or None when the attribute is absent."""
    match = re.search(r'(?:^|\s)' + re.escape(name) + r'="([^"]*)"', tag)
    return match.group(1) if match else None


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
        self.assertEqual(declaration(one, "height"), "18px")
        two = css_block(self.source, "data-cb-home-scene-plank-two")
        self.assertEqual(declaration(two, "left"), "130px")
        self.assertEqual(declaration(two, "width"), "1150px")
        self.assertEqual(declaration(two, "top"), "684px")
        self.assertEqual(declaration(two, "height"), "30px")
        tag = css_block(self.source, "data-cb-home-scene-tag")
        self.assertEqual(declaration(tag, "left"), "888px")
        self.assertEqual(declaration(tag, "top"), "559px")
        self.assertEqual(declaration(tag, "width"), "148px")
        self.assertEqual(declaration(tag, "height"), "148px")
        clock = css_block(self.source, "data-cb-home-scene-clock")
        self.assertEqual(declaration(clock, "left"), "1042px")
        self.assertEqual(declaration(clock, "top"), "568px")
        self.assertEqual(declaration(clock, "width"), "118px")
        self.assertEqual(declaration(clock, "height"), "118px")
        fox = css_block(self.source, "data-cb-home-scene-fox")
        self.assertEqual(declaration(fox, "left"), "1110px")
        self.assertEqual(declaration(fox, "top"), "481px")
        hero = css_block(self.source, "data-cb-home-scene-hero")
        self.assertEqual(declaration(hero, "top"), "128px")

    def test_the_tag_plate_keeps_the_master_aspect(self) -> None:
        # VQ-011: the plate paints the square 256x256 tag object, so its box is square and its size
        # is the single keyword `contain`. A two-value, box-derived size (100% 100% or otherwise)
        # stretches the kraft body and its rope hole, which is a composition defect, and a plate
        # colour or box shadow would paint a square behind the object's transparent corners.
        tag = css_block(self.source, "data-cb-home-scene-tag")
        self.assertEqual(declaration(tag, "width"), declaration(tag, "height"),
                         "a non-square box cannot paint the square tag master at its own aspect")
        size = declaration(tag, "background-size")
        self.assertEqual(size, "contain", f"the tag plate size must preserve the file's aspect: {size!r}")
        self.assertEqual(len(size.split()), 1, f"a two-value background-size stretches the plate: {size!r}")
        self.assertNotIn("%", size)
        self.assertNotIn("background-color", tag,
                         "a plate colour paints the transparent corners as a square")
        self.assertNotIn("box-shadow", tag,
                         "a box shadow paints a square around the transparent corners")

    def test_the_fox_and_clock_stand_on_plank_two_and_do_not_overlap(self) -> None:
        # Scope override item 3: feet and clock base sit on the plank's top edge (+/- 2 px). The card's
        # own 526/588 boxes put feet 45 px and the base 20 px below 684, so the seating instruction
        # (the later authority) wins. Insets are the painted-art opaque bounds inside each box,
        # measured on the rendered proof (alpha bottom 203.1/208 fox, 115.7/118 clock; opaque right
        # 100.5/118 clock, opaque left 43.9/208 fox).
        plank_top = 684
        fox_top = int(declaration(css_block(self.source, "data-cb-home-scene-fox"), "top")[:-2])
        clock_top = int(declaration(css_block(self.source, "data-cb-home-scene-clock"), "top")[:-2])
        feet = fox_top + 203.1
        base = clock_top + 115.7
        self.assertLessEqual(abs(feet - plank_top), 2, f"fox feet at {feet}, plank edge {plank_top}")
        self.assertLessEqual(abs(base - plank_top), 2, f"clock base at {base}, plank edge {plank_top}")
        fox_left = int(declaration(css_block(self.source, "data-cb-home-scene-fox"), "left")[:-2])
        clock_left = int(declaration(css_block(self.source, "data-cb-home-scene-clock"), "left")[:-2])
        fox_opaque_left = fox_left + 43.9
        clock_opaque_right = clock_left + 100.5
        self.assertGreaterEqual(fox_opaque_left - clock_opaque_right, 11,
                                "the fox and clock opaque art still overlap")

    def test_the_hero_holds_its_contrast_on_the_plate(self) -> None:
        question = css_block(self.source, "data-cb-home-scene-question")
        self.assertEqual(declaration(question, "color"), "var(--cb3-ink)",
                         "the hero must not paint forest on the plate's dark sky")
        match = re.search(r'\[data-cb-v3\] \[data-cb-home-scene-panel\]::before\s*\{([^}]*)\}', self.source)
        self.assertIsNotNone(match, "the hero text has no token scrim")
        self.assertGreaterEqual(float(declaration(match.group(1), "opacity")), 0.6,
                                "the scrim is below the measured 4.5:1 floor")

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

    # --- covers are approved kit plates, never letter plates --------------------------------

    def kit_rows(self) -> dict:
        rows = {}
        for match in re.finditer(r'"(cb\.asset\.kit\.field_atlas\.[a-z0-9-]+)":\s*\{', self.source):
            window = self.source[match.end():match.end() + 700000]
            src = re.search(r'"src":\s*"(data:image/webp;base64,[^"]+)"', window)
            if src:
                rows[match.group(1)] = src.group(1)
        return rows

    def test_every_scene_cover_is_an_approved_kit_plate(self) -> None:
        rows = self.kit_rows()
        self.assertIn("cb.asset.kit.field_atlas.home-hero", rows, "the kit segment is not in the module")
        html = self.render(1344)
        covers = [tag for tag in img_tags(html) if attr(tag, "data-cb-home-scene-cover")]
        self.assertEqual(len(covers), 4, "every visible card carries a cover image")
        self.assertNotIn('data-cb-home-scene-cover="type"', html, "a letter plate stands in for a cover")
        self.assertNotIn('data-cb-cover-kind="letter"', html)
        approved = set(rows.values())
        for tag in covers:
            kind = attr(tag, "data-cb-home-scene-cover")
            self.assertIn(kind, ("kit", "art", "lesson"), kind)
            src = attr(tag, "src") or ""
            self.assertTrue(src.startswith("data:image/webp"), src[:48])
            self.assertIn(src, approved, "a scene cover is not an approved field_atlas@2 row")

    def test_each_card_reads_the_plate_for_its_own_course(self) -> None:
        # "Equals the kit row" (scope override item 1): a swapped or shared plate must fail, not just
        # an unapproved one. cb3KitCoverFor answers one family per course; a course with no family
        # falls back to the kit's own lesson room, never a letter plate.
        rows = self.kit_rows()
        html = self.render(1344, [
            {"title": "Technical Pack Basics", "sections_total": 4, "sections_done": 1},
            {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 2},
            {"title": "Parent Kitchen Practice", "sections_total": 4, "sections_done": 0},
            {"title": "Astronomy", "sections_total": 6, "sections_done": 1},
        ])
        # Cards paint in shelf order, which is not render order, so map cover -> title, not by index.
        found = {}
        for article in re.findall(r'<article[^>]*data-cb-home-scene-card.*?</article>', html, re.S):
            title = re.search(r'data-cb-home-scene-title[^>]*>([^<]+)<', article)
            cover = re.search(r'<img[^>]*data-cb-home-scene-cover[^>]*>', article)
            if title and cover:
                found[title.group(1)] = attr(cover.group(0), "src")
        self.assertEqual(set(found), {
            "Technical Pack Basics", "Japanese Cafe Basics", "Parent Kitchen Practice", "Astronomy",
        })
        self.assertEqual(found["Technical Pack Basics"], rows["cb.asset.kit.field_atlas.technical-cover-3x2"])
        self.assertEqual(found["Japanese Cafe Basics"], rows["cb.asset.kit.field_atlas.japanese-cover-3x2"])
        self.assertEqual(found["Parent Kitchen Practice"], rows["cb.asset.kit.field_atlas.parent-cover-3x2"])
        self.assertEqual(found["Astronomy"], rows["cb.asset.kit.field_atlas.field-atlas-lesson-room"])

    def test_the_japanese_course_reads_in_the_japanese_plate(self) -> None:
        rows = self.kit_rows()
        html = self.render(1344)
        plate = rows["cb.asset.kit.field_atlas.japanese-cover-3x2"]
        self.assertIn(plate, html, "the Japanese course did not resolve to its display plate")

    def test_two_courses_on_one_plate_get_different_crops(self) -> None:
        html = self.render(1344, [
            {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 1},
            {"title": "Japanese Kitchen Japanese", "sections_total": 4, "sections_done": 0},
        ])
        positions = [
            attr(tag, "style") for tag in img_tags(html)
            if attr(tag, "data-cb-home-scene-cover") == "kit"
        ]
        self.assertEqual(len(positions), 2)
        self.assertNotEqual(positions[0], positions[1], "two Japanese courses share one crop")

    def test_the_stage_backdrop_is_the_home_hero_plate(self) -> None:
        rows = self.kit_rows()
        html = self.render(1344)
        backdrops = [tag for tag in img_tags(html) if attr(tag, "data-cb-home-scene-backdrop") is not None]
        self.assertEqual(len(backdrops), 1, "the stage has no painted backdrop")
        self.assertEqual(attr(backdrops[0], "src"), rows["cb.asset.kit.field_atlas.home-hero"])
        self.assertIn("data-cb-home-scene-panel", html, "the hero text has no token scrim panel")

    def test_narrow_home_carries_the_same_covers_and_a_hero_band(self) -> None:
        rows = self.kit_rows()
        html = self.render(900)
        self.assertNotIn("data-cb-home-scene", html)
        band = [tag for tag in img_tags(html) if attr(tag, "data-cb-home-hero-band") is not None]
        self.assertEqual(len(band), 1, "the narrow Home has no 16:9 hero band")
        self.assertEqual(attr(band[0], "src"), rows["cb.asset.kit.field_atlas.home-hero"])
        plates = []
        for chunk in html.split("data-cb-home-cover-plate")[1:]:
            tag = re.search(r'<img\b[^>]*>', chunk)
            if tag:
                plates.append(attr(tag.group(0), "src"))
        self.assertTrue(plates, "the narrow shelf has no cover plate")
        for src in plates:
            self.assertIn(src, set(rows.values()), "a narrow cover is not an approved kit row")
        self.assertIn('data-cb-home-cover-kind="', html)
        self.assertNotIn('data-cb-home-cover-kind="letter"', html)

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
