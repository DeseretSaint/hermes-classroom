"""CP-TEXT-GATE — every lettering run in the wide Home scene sits inside the object it is on.

`tests/test_desktop_home_scene_parity.py` proves the committed proof page is a fresh render of
`desktop/plugin.js`; it says nothing about where the glyphs land. A label can overhang the board it
is painted on and every existing check still passes, because no other test measures ink against the
scene's own authored geometry.

This gate measures it directly:

  * **Ink is the pixel difference**, not a segmentation of the artwork. The same page is
    screenshotted with the scene intact and again with one run's glyph paint killed
    (`color: transparent`, so the object's background and every box stay put); what changed is
    exactly what that run drew.
  * **Reference geometry is the object's own box.** Four probe points at the object's corners give
    its quad after its rotation, and a homography maps the screenshot into the object's local
    frame. The tag and the cards are rotated by the scene's CSS; measuring in their local frame is
    what catches spill their axis-aligned bounding box would hide.
  * **Metrics:** no ink outside the object (`spill_pixels == 0`); the run's *layout* rects also
    inside the object, and its text not wider than its client box (`scrollWidth`), so text clipped
    by `overflow: hidden` is still caught; for objects the
    scene centres its type on, `|left-right| <= 4%` of width and `|top-bottom| <= 7%` of height;
    and a floor (300 ink px, 8 px ink height) so a run that silently stopped painting cannot pass
    as an empty mask.

The fixture at `tests/fixtures/scene-text/overhanging.html` is a rotated board whose label is
deliberately wider and taller than the board. `test_the_overhanging_fixture_is_caught` asserts the
gate flags it; run the suite with `CB_SCENE_TEXT_TARGET=overhanging` to watch the *scene* assertions
fail on it (the fail-then-pass evidence in `docs/concept-parity/CP-TEXT-GATE.md`).

The gate does not edit the scene. A failure names the unit, the selector and the measured margins.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "scene-text"
MEASURE_JS = FIXTURES / "measure.mjs"
SCENE_UNITS = json.loads((FIXTURES / "scene.units.json").read_text(encoding="utf-8"))
OVERHANG_PAGE = FIXTURES / "overhanging.html"
OVERHANG_UNITS = json.loads((FIXTURES / "overhanging.units.json").read_text(encoding="utf-8"))
PROOF = ROOT / "design" / "home-scene.html"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The metric contract. `LEFT_RIGHT` is 4% of the object's width and `TOP_BOTTOM` 7% of its height:
# enough slack for a side bearing or a line box's descender, far below a label that has left its
# board. The floor keeps a blank mask from reading as a pass.
LEFT_RIGHT_TOLERANCE = 0.04
TOP_BOTTOM_TOLERANCE = 0.07
MIN_INK_PIXELS = 300
MIN_INK_HEIGHT_PX = 8.0
INK_THRESHOLD = 8  # per-channel delta that counts as glyph ink rather than image noise
EDGE_TOLERANCE = 0.5  # local px around the object edge (half-pixel antialias quantisation)
RECT_PAD = 2.0  # screen px of slack around a run's text rects

SCENE_UNIT_NAMES = [unit["name"] for unit in SCENE_UNITS]
SCENE_RUN_COUNT = sum(len(unit["runs"]) for unit in SCENE_UNITS)


def _chrome_available() -> bool:
    return shutil.which("node") is not None and shutil.which("chromium") is not None


def _analysis_available() -> bool:
    try:
        import numpy  # noqa: F401
        import PIL  # noqa: F401
    except Exception:  # pragma: no cover - optional test dependency
        return False
    return True


def _load_rgb(path: str):
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def _affine_from_quad(quad):
    """(M, W, H): local (u,v) -> screenshot (x,y) for the object's own frame."""
    import numpy as np

    p0, p1, p2, p3 = (np.array(point, float) for point in quad)
    width = float(np.hypot(*(p1 - p0)))
    height = float(np.hypot(*(p2 - p1)))
    local = np.array([[0, 0, 1], [width, 0, 1], [width, height, 1], [0, height, 1]], float)
    screen = np.array([p0, p1, p2, p3], float)
    transform, *_ = np.linalg.lstsq(local, screen, rcond=None)
    return transform.T, width, height


def _local_coords(transform, xs, ys):
    import numpy as np

    linear = np.array([[transform[0, 0], transform[0, 1]], [transform[1, 0], transform[1, 1]]], float)
    offset = np.array([transform[0, 2], transform[1, 2]], float)
    points = np.stack([xs, ys], axis=1) - offset
    return points @ np.linalg.inv(linear).T


def _painted_rect_mask(shape, rects):
    import numpy as np

    mask = np.zeros(shape, bool)
    for left, top, width, height in rects:
        x0 = max(0, int(left // 1) - int(RECT_PAD))
        y0 = max(0, int(top // 1) - int(RECT_PAD))
        x1 = min(shape[1], int(-(-(left + width) // 1)) + int(RECT_PAD))
        y1 = min(shape[0], int(-(-(top + height) // 1)) + int(RECT_PAD))
        mask[y0:y1, x0:x1] = True
    return mask


def _bbox_metrics(transform, width, height, xs, ys) -> dict:
    import numpy as np

    local = _local_coords(transform, xs + 0.5, ys + 0.5)
    u, v = local[:, 0], local[:, 1]
    outside = (
        (u < -EDGE_TOLERANCE) | (u > width + EDGE_TOLERANCE)
        | (v < -EDGE_TOLERANCE) | (v > height + EDGE_TOLERANCE)
    )
    return {
        "left": float(u.min()),
        "right": float(width - u.max()),
        "top": float(v.min()),
        "bottom": float(height - v.max()),
        "spill_pixels": int(outside.sum()),
        "spill_fraction": float(outside.sum() / max(1, len(u))),
        "ink_bbox_px": [float(u.max() - u.min()), float(v.max() - v.min())],
    }


def _layout_metrics(transform, width, height, rects) -> dict:
    import numpy as np

    corners = []
    for left, top, rect_width, rect_height in rects:
        for x, y in ((left, top), (left + rect_width, top), (left, top + rect_height),
                     (left + rect_width, top + rect_height)):
            corners.append((x, y))
    points = np.array(corners, float)
    local = _local_coords(transform, points[:, 0], points[:, 1])
    u, v = local[:, 0], local[:, 1]
    outside = (
        (u < -EDGE_TOLERANCE) | (u > width + EDGE_TOLERANCE)
        | (v < -EDGE_TOLERANCE) | (v > height + EDGE_TOLERANCE)
    )
    return {"outside": bool(outside.any()), "outside_corners": int(outside.sum())}


def analyse(result: dict) -> list[dict]:
    """Turn a browser capture into one metric row per measured object."""
    import numpy as np

    base = _load_rgb(result["base"])
    diffs = {
        shot["index"]: np.abs(base - _load_rgb(shot["file"])).max(axis=2)
        for shot in result["shots"]
    }
    rows = []
    for unit in result["info"]["units"]:
        if unit.get("missing"):
            rows.append({"unit": unit["name"], "missing": True})
            continue
        transform, width, height = _affine_from_quad(unit["object"]["quad"])
        run_rows = []
        union = np.zeros(base.shape[:2], bool)
        for run in unit["runs"]:
            diff = diffs.get(run["index"])
            if diff is None:
                continue
            painted = _painted_rect_mask(base.shape[:2], run["rects"])
            mask = (diff > INK_THRESHOLD) & painted
            union |= mask
            row = {
                "selector": run["selector"],
                "text": run["text"],
                "textAlign": run["textAlign"],
                "ink_pixels": int(mask.sum()),
                "layout": _layout_metrics(transform, width, height, run["rects"]),
                "overflow": run.get("overflow", []),
            }
            if mask.sum():
                ys, xs = np.nonzero(mask)
                row.update(_bbox_metrics(transform, width, height, xs, ys))
            run_rows.append(row)

        row = {
            "unit": unit["name"],
            "centre": bool(unit.get("centre")),
            "width": width,
            "height": height,
            "overflow": [unit["object"]["overflowX"], unit["object"]["overflowY"]],
            "runs": run_rows,
            "ink_pixels": int(union.sum()),
        }
        ys, xs = np.nonzero(union)
        if union.sum():
            row.update(_bbox_metrics(transform, width, height, xs, ys))
            row["centre_dx"] = abs(row["left"] - row["right"]) / width
            row["centre_dy"] = abs(row["top"] - row["bottom"]) / height
        rows.append(row)
    return rows


def violations(rows: list[dict]) -> list[str]:
    """Every way a measured run breaks the gate, as human-readable sentences."""
    problems = []
    for row in rows:
        name = row["unit"]
        if row.get("missing"):
            problems.append(f"{name}: the object did not paint at all")
            continue
        if row["ink_pixels"] < MIN_INK_PIXELS:
            problems.append(
                f"{name}: only {row['ink_pixels']} ink px (floor {MIN_INK_PIXELS}); the run may not have painted"
            )
            continue
        for run in row["runs"]:
            if run["layout"]["outside"]:
                problems.append(
                    f"{name}: the layout box of {run['selector']} ({run['text']!r}) leaves the object "
                    f"({run['layout']['outside_corners']} corners outside)"
                )
            if run["overflow"]:
                detail = ", ".join(
                    f"{entry['tag']} +{entry['dx']:.0f}px wider than its client area"
                    for entry in run["overflow"]
                )
                problems.append(
                    f"{name}: {run['selector']} ({run['text']!r}) overflows its box ({detail})"
                )
        if row["ink_bbox_px"][1] < MIN_INK_HEIGHT_PX:
            problems.append(
                f"{name}: ink is only {row['ink_bbox_px'][1]:.1f} px tall (floor {MIN_INK_HEIGHT_PX} px); "
                "the run may not have painted"
            )
        if row["spill_pixels"]:
            problems.append(
                f"{name}: {row['spill_pixels']} ink px ({row['spill_fraction'] * 100:.2f}% of the run) "
                f"fall outside the object ({row['width']:.1f}x{row['height']:.1f}); "
                f"margins l={row['left']:.2f} r={row['right']:.2f} t={row['top']:.2f} b={row['bottom']:.2f}"
            )
        if row["centre"]:
            if row["centre_dx"] > LEFT_RIGHT_TOLERANCE:
                problems.append(
                    f"{name}: horizontally off-centre by {row['centre_dx'] * 100:.2f}% of width "
                    f"(limit {LEFT_RIGHT_TOLERANCE * 100:.0f}%); margins l={row['left']:.2f} r={row['right']:.2f}"
                )
            if row["centre_dy"] > TOP_BOTTOM_TOLERANCE:
                problems.append(
                    f"{name}: vertically off-centre by {row['centre_dy'] * 100:.2f}% of height "
                    f"(limit {TOP_BOTTOM_TOLERANCE * 100:.0f}%); margins t={row['top']:.2f} b={row['bottom']:.2f}"
                )
    return problems


def format_rows(rows: list[dict]) -> str:
    """The evidence table: every measured run with every metric."""
    lines = []
    for row in rows:
        if row.get("missing"):
            lines.append(f"{row['unit']}: MISSING")
            continue
        lines.append(
            f"{row['unit']:<18} object {row['width']:.1f}x{row['height']:.1f} "
            f"overflow={','.join(row['overflow'])} centre={row['centre']} ink={row['ink_pixels']} "
            f"l={row['left']:.2f} r={row['right']:.2f} t={row['top']:.2f} b={row['bottom']:.2f} "
            f"dx={row['centre_dx'] * 100:.2f}% dy={row['centre_dy'] * 100:.2f}% "
            f"spill={row['spill_pixels']} ({row['spill_fraction'] * 100:.2f}%) "
            f"ink_bbox={row['ink_bbox_px'][0]:.1f}x{row['ink_bbox_px'][1]:.1f}"
        )
        for run in row["runs"]:
            spill = ""
            if "spill_pixels" in run:
                spill = f" spill={run['spill_pixels']} ({run['spill_fraction'] * 100:.2f}%)"
            clipped = f" scroll_overflow={run['overflow']}" if run.get("overflow") else ""
            lines.append(
                f"    {run['selector']:<42} align={run['textAlign']:<7} ink={run['ink_pixels']:5d}"
                f"{spill} layout_outside={run['layout']['outside']}{clipped} {run['text']!r}"
            )
    return "\n".join(lines)


def capture(page: Path, units: list[dict], workdir: Path) -> dict:
    """Drive Chromium and return the raw capture (base + one image per run)."""
    result = subprocess.run(
        ["node", str(MEASURE_JS), str(page), json.dumps(units), str(workdir)],
        cwd=workdir, capture_output=True, text=True, timeout=420,
    )
    if result.returncode != 0:
        raise AssertionError(f"the browser driver failed:\n{result.stderr[-4000:]}")
    return json.loads(result.stdout)


def measure(page: Path, units: list[dict]) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="cp-text-gate-") as tmp:
        return analyse(capture(page, units, Path(tmp)))


def render_scene(workdir: Path, extra_css: str = "") -> Path:
    """Render the shipped Home scene into `workdir` (optionally with one injected regression)."""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("gen_home_proof", ROOT / "scripts" / "gen-home-proof.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load scripts/gen-home-proof.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    page = workdir / "home-scene.html"
    generator.render(page)
    if extra_css:
        text = page.read_text(encoding="utf-8")
        page.write_text(text.replace("</head>", f"<style>{extra_css}</style>\n</head>", 1), encoding="utf-8")
    return page


@unittest.skipIf(not _chrome_available(), "node + chromium are required to photograph the scene")
@unittest.skipIf(not _analysis_available(), "numpy and Pillow are required to read the screenshots")
class SceneTextContainmentTest(unittest.TestCase):
    def test_the_shipped_scene_lettering_stays_inside_its_object(self) -> None:
        target = os.environ.get("CB_SCENE_TEXT_TARGET", "scene").strip().lower()
        if target == "overhanging":
            rows = measure(OVERHANG_PAGE, OVERHANG_UNITS)
            label = "the overhanging fixture"
        else:
            with tempfile.TemporaryDirectory(prefix="cp-text-gate-scene-") as tmp:
                page = render_scene(Path(tmp))
                module_sha = hashlib.sha256(PLUGIN_JS.read_bytes()).hexdigest()
                self.assertIn(
                    f"desktop/plugin.js (sha256 {module_sha})",
                    page.read_text(encoding="utf-8"),
                    "the rendered proof does not name the current desktop/plugin.js; "
                    "the measurement would not be tied to the shipped module",
                )
                self.assertEqual(
                    page.read_bytes(),
                    PROOF.read_bytes(),
                    "design/home-scene.html no longer matches a render of desktop/plugin.js; "
                    "the containment gate would measure a stale page. Regenerate with "
                    "`python3 scripts/gen-home-proof.py`.",
                )
                rows = measure(page, SCENE_UNITS)
            label = "the shipped Home scene"

        self.assertEqual(
            [row["unit"] for row in rows],
            SCENE_UNIT_NAMES if target != "overhanging" else [unit["name"] for unit in OVERHANG_UNITS],
            f"{label} did not paint every measured object",
        )
        missing = [row["unit"] for row in rows if row.get("missing")]
        self.assertEqual(missing, [], f"{label} did not paint these objects: {missing}")
        if target != "overhanging":
            self.assertEqual(
                sum(len(row["runs"]) for row in rows),
                SCENE_RUN_COUNT,
                f"{label} did not paint every measured run",
            )
        problems = violations(rows)
        print(f"\nCP-TEXT-GATE — {label} ({SCENE_RUN_COUNT if target != 'overhanging' else 2} runs)\n" + format_rows(rows))
        self.assertEqual(
            problems, [],
            f"{label} has lettering outside its object:\n" + "\n".join(problems)
            + "\n\nmeasured:\n" + format_rows(rows),
        )

    def test_the_overhanging_fixture_is_caught(self) -> None:
        rows = measure(OVERHANG_PAGE, OVERHANG_UNITS)
        print("\nCP-TEXT-GATE — overhanging fixture (2 runs)\n" + format_rows(rows))
        by_unit = {row["unit"]: row for row in rows}
        self.assertIn("board-pass", by_unit, "the fixture control did not paint")
        self.assertIn("board-fail", by_unit, "the fixture defect did not paint")
        self.assertEqual(
            violations([by_unit["board-pass"]]), [],
            "the fixture's control board is inside its box and must pass:\n" + format_rows([by_unit["board-pass"]]),
        )
        caught = violations([by_unit["board-fail"]])
        self.assertTrue(caught, "the overhanging fixture passed the gate; the gate has no teeth")
        text = "\n".join(caught)
        self.assertIn("fall outside the object", text, f"the gate did not report spill:\n{text}")
        self.assertIn("layout box", text, f"the gate did not report the overflowing layout box:\n{text}")
        self.assertGreater(
            by_unit["board-fail"]["spill_fraction"], 0.05,
            "the fixture is not actually overhanging: " + format_rows([by_unit["board-fail"]]),
        )

    def test_a_text_regression_in_the_shipped_scene_is_caught(self) -> None:
        cases = (
            (
                "tag-label-too-large",
                "html body [data-cb-v3] [data-cb-home-scene-tag]{font-size:60px;line-height:1.1;white-space:nowrap}",
                "tag-lettering",
                "fall outside the object",
            ),
            (
                "card-title-overflows-its-clip",
                "html body [data-cb-v3] [data-cb-home-scene-title]{font-size:32px;line-height:1.1;white-space:nowrap}",
                "card-1-lettering",
                "overflows its box",
            ),
        )
        for name, css, unit, needle in cases:
            with self.subTest(perturbation=name):
                with tempfile.TemporaryDirectory(prefix=f"cp-text-gate-{name}-") as tmp:
                    rows = measure(render_scene(Path(tmp), css), SCENE_UNITS)
                caught = [problem for problem in violations(rows) if problem.startswith(f"{unit}:")]
                self.assertTrue(
                    caught,
                    f"the regression {name!r} was not caught; the gate cannot see a real scene defect:\n"
                    + format_rows(rows),
                )
                self.assertIn(
                    needle, "\n".join(caught),
                    f"the regression {name!r} was not caught for the expected reason:\n" + "\n".join(caught),
                )


if __name__ == "__main__":
    unittest.main()
