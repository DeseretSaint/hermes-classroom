#!/usr/bin/env python3
"""CP-010 marking audit: measure the dark limb band the shipped fox actually carries.

Deterministic, no model call. The ink contour is the same warm brown as the dark
limb marking, so a colour threshold alone cannot separate them; eroding the mask
by half the contour weight removes the drawn line and leaves only solid dark
fill. What is left is the marking itself, measured in figure-height units on the
model sheet — the authority — so ART-BIBLE.md §3 can state a band that the art
implements instead of one the art never did.

    python3 scripts/cp010-marking-audit.py          # print
    python3 scripts/cp010-marking-audit.py --write  # write audit/cp010-fox/marking-audit.json

Reported to 0.1 %. A silhouette / paint-area measurement, not a line-following
measurement; the elbow joint is not detectable on a plate whose arm merges with
the torso, so no wrist-to-elbow ratio is claimed.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art" / "fox"
OUT = ROOT / "audit" / "cp010-fox" / "marking-audit.json"

INK = (0, 120, 255)
ERODE = 9  # px; the contour is 3-4 px at master size


def opaque_blocks(im: Image.Image):
    """Column ranges of the sheet that hold opaque pixels."""
    a = im.getchannel("A")
    w, h = a.size
    ap = a.load()
    cols = [any(ap[x, y] > 0 for y in range(h)) for x in range(w)]
    runs, start = [], None
    for x, filled in enumerate(cols):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, w - 1))
    return runs


def row_widths(ap, x0, x1, y0, y1):
    widths = []
    for y in range(y0, y1 + 1):
        xs = [x for x in range(x0, x1 + 1) if ap[x, y] > 0]
        widths.append(max(xs) - min(xs) + 1 if xs else 0)
    return widths


def figure_box(ap, x0, x1, h):
    ys = [y for y in range(h) if any(ap[x, y] > 0 for x in range(x0, x1 + 1))]
    y0, y1 = ys[0], ys[-1]
    xs = [x for x in range(x0, x1 + 1) if any(ap[x, y] > 0 for y in range(h))]
    return xs[0], y0, xs[-1], y1


def dark_fill(im: Image.Image, box):
    """Solid dark fill: threshold, then erode the ink line away."""
    x0, y0, x1, y1 = box
    w, h = im.size
    px = im.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b, a = px[x, y]
            if a > 200 and r < 110 and g < 85 and b < 75:
                mp[x, y] = 255
    return mask.filter(ImageFilter.MinFilter(ERODE))


def components(mask, box, x0, y0, min_px=40):
    x0b, y0b, x1b, y1b = box
    mp = mask.load()
    w, h = mask.size
    seen, comps = set(), []
    for y in range(y0b, y1b + 1):
        for x in range(x0b, x1b + 1):
            if mp[x, y] and (x, y) not in seen:
                q = collections.deque([(x, y)])
                seen.add((x, y))
                pts = []
                while q:
                    cx, cy = q.popleft()
                    pts.append((cx, cy))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and mp[nx, ny] and (nx, ny) not in seen:
                                seen.add((nx, ny))
                                q.append((nx, ny))
                if len(pts) >= min_px:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    comps.append({
                        "bbox": [min(xs), min(ys), max(xs), max(ys)],
                        "width_px": max(xs) - min(xs) + 1,
                        "height_px": max(ys) - min(ys) + 1,
                        "pixels": len(pts),
                    })
    comps.sort(key=lambda c: (c["bbox"][1], c["bbox"][0]))
    return comps


def band_of(comp, y0, bh):
    top, bottom = comp["bbox"][1], comp["bbox"][3]
    return {
        "height_px": comp["height_px"],
        "height_percent_figure": round(comp["height_px"] / bh * 100, 1),
        "top_percent_figure": round((top - y0) / bh * 100, 1),
        "bottom_percent_figure": round((bottom - y0) / bh * 100, 1),
    }


def head_fraction(ap, box):
    """Neck-pinch head height, the method shape-audit.py uses. None if meaningless."""
    x0, y0, x1, y1 = box
    bh = y1 - y0 + 1
    widths = row_widths(ap, x0, x1, y0, y1)
    peak = max(range(len(widths)), key=lambda i: widths[i])
    window = widths[peak:int(len(widths) * 0.70)]
    if len(window) < 5:
        return None, peak, bh
    neck = peak + min(range(len(window)), key=lambda i: window[i])
    return round(neck / bh * 100, 1), peak, bh


def main(argv):
    sheet = Image.open(ART / "fox-model-sheet.png").convert("RGBA")
    ap = sheet.getchannel("A").load()
    blocks = opaque_blocks(sheet)
    x0, x1 = blocks[0]

    view = figure_box(ap, x0, x1, sheet.height)
    vx0, vy0, vx1, vy1 = view
    bh = vy1 - vy0 + 1
    bw = vx1 - vx0 + 1

    mask = dark_fill(sheet, view)
    comps = components(mask, view, vx0, vy0)
    arms = [c for c in comps if 0.55 < (c["bbox"][1] - vy0) / bh < 0.85]
    legs = [c for c in comps if (c["bbox"][1] - vy0) / bh >= 0.85]

    wave = Image.open(ART / "fox-wave.png").convert("RGBA")
    wap = wave.getchannel("A").load()
    wbox = figure_box(wap, 0, wave.width - 1, wave.height)
    wave_head, wave_peak, wave_bh = head_fraction(wap, wbox)

    sheet_head, sheet_peak, _ = head_fraction(ap, view)

    print(f"model sheet front view: {bw}x{bh} px at ({vx0},{vy0})")
    print(f"  widest row {sheet_peak} ({(sheet_peak / bh) * 100:.1f} % of figure)")
    print(f"  neck-pinch head estimate: {sheet_head} %"
          if sheet_head is not None else "  neck-pinch head estimate: not meaningful "
          "(the widest row is at or below 70 % of the figure)")
    print(f"wave neck-pinch head estimate: {wave_head} % of {wave_bh} px")
    for label, group in (("arm", arms), ("leg/foot", legs)):
        for c in group:
            b = band_of(c, vy0, bh)
            print(f"  {label} band x{c['bbox'][0]}..{c['bbox'][2]} "
                  f"h={b['height_px']} px = {b['height_percent_figure']} % of figure, "
                  f"top {b['top_percent_figure']} %, bottom {b['bottom_percent_figure']} %")

    if "--write" in argv:
        OUT.write_text(json.dumps({
            "method": "opaque-alpha figure box + solid-dark fill. The ink contour shares the "
                      "marking's warm brown, so the dark mask is eroded by 9 px (half the 3-4 px "
                      "master contour at this size) before components are measured; what remains "
                      "is paint area, not line. Band height and edges are reported as percentages "
                      "of the front view's figure height. Bounding boxes are [x0, y0, x1, y1], "
                      "not the [x0, y0, width, height] form shape-audit.json uses.",
            "why": "ART-BIBLE.md §3 previously required dark socks to the elbow. No plate carries "
                   "that; the longest dark band on the authority is the one measured here.",
            "sheet": {
                "file": "assets/art/fox/fox-model-sheet.png",
                "front_view": {"bbox": list(view), "width_px": bw, "height_px": bh,
                               "column_blocks": [list(b) for b in blocks]},
                "neck_pinch_head_percent": sheet_head,
                "neck_pinch_note": "the front view's widest row is its feet, so the neck-pinch "
                                   "estimate is not meaningful on the sheet",
                "arm_bands": [band_of(c, vy0, bh) | {"bbox": c["bbox"]} for c in arms],
                "foot_bands": [band_of(c, vy0, bh) | {"bbox": c["bbox"]} for c in legs],
            },
            "wave": {
                "file": "assets/art/fox/fox-wave.png",
                "bbox": list(wbox),
                "neck_pinch_head_percent": wave_head,
            },
            "not_claimed": "No wrist, elbow or ankle joint is detected. The arm merges with the "
                           "torso on every plate in this set, so no wrist-to-elbow ratio is "
                           "claimed from a silhouette.",
        }, indent=2) + "\n")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
