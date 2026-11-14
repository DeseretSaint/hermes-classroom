"""The slot-type contract: declared slot, cap rule, warp, shrink-not-clip.

Type placed by eye onto a painted object was rejected three times. This test pins the replacement:
a label is a rectangle in the OBJECT'S own plane, and every placement dimension is derived by
rule — inset 6 % of the short side (min 4 px), cap at most 42 % of the inner short side and never
under 11 px, ink centred on its own advance width, baseline at the cap box's bottom, the four ink
corners warped through the plane's basis, and overflow shrunk uniformly.

The declaration is allowed to be wrong by 8 px: no rule reads its `x`/`y`, so the ink cannot move
with it. That tolerance was measured (0.00 % spill at +-0, +-4 and +-8 px), not assumed; the test
re-measures it on a plane rotated -3 deg (the Home tag's own seat) so an axis-aligned accident
cannot pass.

The floor case is the honest refusal: at 11 px cap a line that still does not fit returns
`status: "refused"` with `ink: null`. The component paints nothing visible; it never clips and
never ellipsizes a learner's label.

Run: ``python3 -m unittest tests.test_desktop_slot_type -v``
"""

from __future__ import annotations

import json
import math
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
const mod = await import('./plugin.js')
const cases = payload.cases.map((spec) => {
  const layout = mod.cbSlotTypeLayout(spec)
  const html = renderToStaticMarkup(React.createElement(mod.CbSlotType, spec))
  return { name: spec.name, layout, html }
})
process.stdout.write(JSON.stringify({ cases }))
"""


def axis_plane(left: float, top: float, width: float, height: float) -> dict:
    return {
        "origin": {"x": left, "y": top},
        "ex": {"x": 1.0, "y": 0.0},
        "ey": {"x": 0.0, "y": 1.0},
        "width": width,
        "height": height,
    }


def rotated_plane(cx: float, cy: float, width: float, height: float, degrees: float) -> dict:
    """A plane centred on (cx, cy), its own axes turned by ``degrees`` (screen coords)."""
    radians = math.radians(degrees)
    ex = {"x": math.cos(radians), "y": math.sin(radians)}
    ey = {"x": -math.sin(radians), "y": math.cos(radians)}
    origin = {
        "x": cx - ex["x"] * width / 2 - ey["x"] * height / 2,
        "y": cy - ex["y"] * width / 2 - ey["y"] * height / 2,
    }
    return {"origin": origin, "ex": ex, "ey": ey, "width": width, "height": height}


def point_in_convex_quad(point: dict, quad: list[dict], tolerance: float = 1e-9) -> bool:
    """True when ``point`` is inside (or on) the convex quadrilateral ``quad``."""
    signed = []
    for index in range(4):
        ax, ay = quad[index]["x"], quad[index]["y"]
        bx, by = quad[(index + 1) % 4]["x"], quad[(index + 1) % 4]["y"]
        signed.append((bx - ax) * (point["y"] - ay) - (by - ay) * (point["x"] - ax))
    return all(value >= -tolerance for value in signed) or all(value <= tolerance for value in signed)


def bounds(points: list[dict]) -> tuple[float, float, float, float]:
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


class SlotTypeRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-slot-type-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
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

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def measure(self, cases: list[dict]) -> list[dict]:
        payload = self.root / "case.json"
        payload.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(payload)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)["cases"]

    # --- the measured tolerance ---------------------------------------------------------------

    def test_the_declaration_may_be_wrong_by_eight_px_and_the_ink_stays_inside_and_centred(self) -> None:
        # The Home tag's seat: a 148 px square kraft plate turned -3 deg, as the scene paints it.
        plane = rotated_plane(888 + 74, 559 + 74, 148, 148, -3.0)
        declaration = {"x": 914, "y": 624, "width": 96, "height": 52, "cap": 20}
        offsets = [(0, 0), (4, 0), (-4, 0), (0, 4), (0, -4), (8, 8), (-8, -8), (-8, 8), (8, -8)]
        cases = [
            {
                "name": f"offset_{dx}_{dy}",
                "plane": plane,
                "declared": {**declaration, "x": declaration["x"] + dx, "y": declaration["y"] + dy},
                "label": "New course",
            }
            for dx, dy in offsets
        ]
        measured = self.measure(cases)
        object_width, object_height = 148.0, 148.0
        ink_signatures = []
        for case in measured:
            with self.subTest(declaration=case["name"]):
                layout = case["layout"]
                self.assertEqual(layout["status"], "fits")
                self.assertEqual(layout["inset"], 9)
                quad = layout["plane"]["corners"]
                ink_quad = layout["ink"]["corners"]
                for point in ink_quad:
                    self.assertTrue(point_in_convex_quad(point, quad), f"ink corner {point} spills")
                ink_l, ink_t, ink_r, ink_b = bounds(ink_quad)
                obj_l, obj_t, obj_r, obj_b = bounds(quad)
                left_gap = ink_l - obj_l
                right_gap = obj_r - ink_r
                top_gap = ink_t - obj_t
                bottom_gap = obj_b - ink_b
                self.assertLessEqual(abs(left_gap - right_gap) / object_width, 0.04,
                                     f"horizontal off-centre: L={left_gap:.3f} R={right_gap:.3f}")
                self.assertLessEqual(abs(top_gap - bottom_gap) / object_height, 0.07,
                                     f"vertical off-centre: T={top_gap:.3f} B={bottom_gap:.3f}")
                self.assertEqual(layout["overflowPx"], 0.0, "the ink spills its own inner width")
                ink_signatures.append(tuple((round(p["x"], 9), round(p["y"], 9)) for p in ink_quad))
        # No declared position moves the ink: every offset produced the identical quad.
        self.assertEqual(len(set(ink_signatures)), 1, "a wrong declaration moved the type")

    def test_the_rule_uses_the_plane_not_the_declaration(self) -> None:
        plane = axis_plane(100, 40, 200, 80)
        base = {"plane": plane, "label": "Field Notes", "declared": {"x": 130, "y": 60, "width": 120, "height": 40, "cap": 18}}
        moved = {**base, "declared": {**base["declared"], "x": 130 + 8, "y": 60 - 8}}
        first, second = self.measure([{**base, "name": "base"}, {**moved, "name": "moved"}])
        self.assertEqual(first["layout"]["ink"]["corners"], second["layout"]["ink"]["corners"])
        self.assertEqual(first["layout"]["capBefore"], second["layout"]["capBefore"])

    # --- uniform shrink -----------------------------------------------------------------------

    def test_a_long_label_shrinks_uniformly_and_still_fits(self) -> None:
        # The Home tag's kraft face, axis-aligned: 148 px square -> 130 px inner width.
        plane = axis_plane(888, 559, 148, 148)
        cases = [
            {
                "name": "fits",
                "plane": plane,
                "declared": {"x": 914, "y": 624, "width": 96, "height": 52, "cap": 20},
                "label": "New course",
            },
            {
                "name": "overlong",
                "plane": plane,
                "declared": {"x": 914, "y": 624, "width": 96, "height": 52, "cap": 20},
                "label": "Advanced Cardmaking",
            },
        ]
        fits, shrunk = self.measure(cases)
        before = fits["layout"]["capBefore"]
        after = shrunk["layout"]["cap"]
        natural_before = shrunk["layout"]["chars"] * before * 0.62
        self.assertEqual(fits["layout"]["status"], "fits")
        self.assertEqual(shrunk["layout"]["status"], "fits")
        self.assertLess(after, before, "an overlong label must shrink")
        self.assertGreaterEqual(after, 11.0, "shrink crossed the 11 px floor")
        # Uniform: cap and advance scale by exactly the same factor, so the face never condenses.
        cap_ratio = shrunk["layout"]["cap"] / fits["layout"]["capBefore"]
        advance_ratio = shrunk["layout"]["advance"] / natural_before
        self.assertAlmostEqual(cap_ratio, advance_ratio, places=9)
        self.assertAlmostEqual(
            shrunk["layout"]["advance"],
            shrunk["layout"]["chars"] * after * 0.62,
            places=9,
        )
        self.assertLessEqual(shrunk["layout"]["advance"], shrunk["layout"]["innerWidth"] + 1e-9)
        print(
            "\n[slot-type] overlong 'Advanced Cardmaking' on the 148x148 tag plane: "
            f"cap {before:.3f} px -> {after:.3f} px, advance {natural_before:.3f} px -> "
            f"{shrunk['layout']['advance']:.3f} px (inner width {shrunk['layout']['innerWidth']:.3f} px), "
            f"scale {cap_ratio:.4f}, status {shrunk['layout']['status']}"
        )

    # --- the floor refuses --------------------------------------------------------------------

    def test_the_floor_refuses_to_shrink_below_eleven_px_cap_and_never_clips(self) -> None:
        plane = axis_plane(100, 40, 200, 80)
        case = {
            "name": "floor",
            "plane": plane,
            "declared": {"x": 120, "y": 50, "width": 160, "height": 40, "cap": 20},
            "label": "An Extremely Long Course Name That Cannot Fit",
        }
        measured = self.measure([case])[0]
        layout = measured["layout"]
        self.assertEqual(layout["status"], "refused")
        self.assertAlmostEqual(layout["cap"], 11.0, places=9)
        self.assertEqual(layout["capBefore"], 20.0)
        self.assertIsNone(layout["ink"], "a refused slot must not hand back an ink box")
        self.assertGreater(layout["overflowPx"], 0.0)
        self.assertIn('data-cb-slot-type="refused"', measured["html"])
        self.assertIn("hidden", measured["html"])
        print(
            "\n[slot-type] floor: cap before 20.000 px, requested scale "
            f"{layout['scale']:.4f} would be {20 * layout['scale']:.3f} px; floor holds "
            f"{layout['cap']:.3f} px, overflow {layout['overflowPx']:.3f} px -> refused (no ink)"
        )

    def test_the_floor_never_appears_on_a_rendered_fits_slot(self) -> None:
        plane = axis_plane(0, 0, 90, 90)
        case = {
            "name": "tiny",
            "plane": plane,
            "declared": {"x": 0, "y": 0, "width": 90, "height": 90, "cap": 4},
            "label": "Tiny",
        }
        layout = self.measure([case])[0]["layout"]
        self.assertGreaterEqual(layout["capBefore"], 11.0)
        self.assertGreaterEqual(layout["cap"], 11.0)

    # --- the component paints the rule --------------------------------------------------------

    def test_the_component_paints_the_solved_line_through_the_plane_basis(self) -> None:
        plane = rotated_plane(962, 633, 148, 148, -3.0)
        case = {
            "name": "component",
            "plane": plane,
            "declared": {"x": 914, "y": 624, "width": 96, "height": 52, "cap": 20},
            "label": "New course",
        }
        measured = self.measure([case])[0]
        layout = measured["layout"]
        html = measured["html"]
        self.assertIn('data-cb-slot-type="fits"', html)
        self.assertIn(f'data-cb-slot-cap="{round(layout["cap"], 2)}"', html)
        self.assertIn(f'data-cb-slot-baseline="{round(layout["baseline"], 2)}"', html)
        self.assertIn("matrix(", html)
        self.assertIn("white-space:nowrap", html.replace(" ", ""))
        # The matrix's linear half is the plane's own basis: -3 deg, not 0 deg.
        ex, ey = plane["ex"], plane["ey"]
        matrix = layout["transform"][len("matrix("):-1].split(",")
        self.assertAlmostEqual(float(matrix[0]), ex["x"], places=6)
        self.assertAlmostEqual(float(matrix[1]), ex["y"], places=6)
        self.assertAlmostEqual(float(matrix[2]), ey["x"], places=6)
        self.assertAlmostEqual(float(matrix[3]), ey["y"], places=6)
        self.assertNotAlmostEqual(float(matrix[1]), 0.0, places=3)

    def test_an_empty_plane_has_no_slot(self) -> None:
        case = {
            "name": "no-plane",
            "plane": axis_plane(0, 0, 0, 0),
            "declared": {"x": 0, "y": 0, "width": 0, "height": 0, "cap": 20},
            "label": "No object",
        }
        layout = self.measure([case])[0]["layout"]
        self.assertEqual(layout["status"], "refused")
        self.assertIsNone(layout["ink"])


if __name__ == "__main__":
    unittest.main()
