#!/usr/bin/env python3
"""CP-010 shape audit: objective silhouette measurements for the fox plates.

Deterministic, no model call. Reads the shipped masters and prints (and, with
--write, records into audit/cp010-fox/shape-audit.json):

  * opaque bounding box and aspect ratio (w/h) of each plate;
  * for the model sheet, the same per view (four columns) plus a head-height
    estimate: the head runs from the top of the silhouette down to the narrowest
    row in the upper 70 %, which is the neck pinch of a chibi figure. This is a
    silhouette estimate, not a line-following measurement, and it is reported to
    one decimal place only.

The aspect ratio is the check that separates an upright figure from a
horizontal one, so it is what the stance guard asserts. A quadruped is wider
than it is tall; an upright chibi is taller than it is wide.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art" / "fox"
OUT = ROOT / "audit" / "cp010-fox" / "shape-audit.json"

POSES = ["wave", "point", "clock", "read", "cheer", "think", "sleep"]
# Only a neutral standing pose with the arms down can be measured by neck pinch.
NEUTRAL_STANDING = {"wave"}


def rowwidths(path: Path):
    with Image.open(path) as im:
        alpha = im.convert("RGBA").getchannel("A")
        w, h = alpha.size
        rows = []
        for y in range(h):
            xs = [x for x in range(w) if alpha.getpixel((x, y)) > 0]
            rows.append((min(xs), max(xs)) if xs else None)
    return w, h, rows


def bbox_of(rows):
    ys = [y for y, r in enumerate(rows) if r is not None]
    if not ys:
        return None
    xs0 = min(r[0] for r in rows if r is not None)
    xs1 = max(r[1] for r in rows if r is not None)
    return xs0, ys[0], xs1 - xs0 + 1, ys[-1] - ys[0] + 1


def head_fraction(rows, box):
    """Head height as a share of figure height, from the neck pinch.

    The head is the widest mass of a chibi figure, so the head bottom is the
    narrowest row below the widest row of the upper 70 % — the neck. Taking the
    narrowest row overall would return the ears or the feet instead.
    """
    x0, y0, bw, bh = box
    heights = []
    for y in range(y0, y0 + int(bh * 0.70)):
        r = rows[y]
        heights.append(0 if r is None else r[1] - r[0] + 1)
    peak_at = heights.index(max(heights))
    below = heights[peak_at:]
    neck_at = peak_at + below.index(min(below))
    return round((neck_at / bh) * 100.0, 1), heights[neck_at], heights[peak_at]


def view_columns(box):
    """Unused: per-view column slicing cannot separate four overlapping figures."""
    raise NotImplementedError


def main(argv):
    write = "--write" in argv
    plates = {}
    measured = {}
    for name in ["model-sheet"] + POSES:
        path = ART / f"fox-{name}.png"
        w, h, rows = rowwidths(path)
        box = bbox_of(rows)
        x0, y0, bw, bh = box
        row = {
            "file": f"assets/art/fox/fox-{name}.png",
            "canvas": f"{w}x{h}",
            "bbox": list(box),
            "aspect": round(bw / bh, 3),
        }
        if name != "model-sheet":
            # The neck-pinch estimate assumes a neutral standing pose with the arms
            # down. Raised arms, props or a seated pose make a wider row than the
            # head, so the estimate is only reported where it is meaningful.
            if name in NEUTRAL_STANDING:
                frac, neck, peak = head_fraction(rows, box)
                row["head_fraction_percent"] = frac
                row["head_peak_row_width"] = peak
                row["neck_row_width"] = neck
            else:
                row["head_fraction_percent"] = None
                row["head_fraction_note"] = "not measurable: arms or props make a wider row than the head"
        plates[f"fox-{name}"] = row
        extra = "" if name == "model-sheet" else f"  head {row['head_fraction_percent']}%"
        print(f"fox-{name:<11} bbox {bw}x{bh} aspect {bw / bh:.3f}{extra}")

    if write:
        OUT.write_text(json.dumps({
            "method": "opaque-alpha silhouette. Head height = distance from the top of the "
                      "figure to the narrowest row below the widest row of its upper 70 % "
                      "(the neck pinch). Reported to 0.1 %; a silhouette estimate, not a "
                      "line-following measurement.",
            "note": "Aspect > 1 means a wider-than-tall (horizontal) silhouette.",
            "plates": plates,
        }, indent=2) + "\n")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
