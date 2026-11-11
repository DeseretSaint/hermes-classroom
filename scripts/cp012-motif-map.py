#!/usr/bin/env python3
"""CP-012 motif map: draw every declared motif zone on the shipped masters.

Writes two audit artifacts, both measured from the files on disk:

  audit/cp012-covers/motif-map.png          three masters with the motif zones outlined
  audit/cp012-covers/motif-retention.json   per motif: bbox, painted pixels, 4:5 retention

The map is a review artifact: it is how a reviewer checks that a motif zone is
on the object it names, rather than trusting a table. Nothing here is product UI
and nothing here is drawn by a model.

Usage: python3 scripts/cp012-motif-map.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
COVERS = ROOT / "assets" / "art" / "covers"
AUDIT = ROOT / "audit" / "cp012-covers"
OUT_PNG = AUDIT / "motif-map.png"
OUT_JSON = AUDIT / "motif-retention.json"

PAPER = (247, 241, 228)
INK = (26, 23, 19)
SOFT = (92, 83, 71)
RULE = (215, 203, 180)
ZONE = (156, 46, 28)      # review annotation, never shipped
CROP_EDGE = (47, 96, 71)
CROP = (280, 920)
FONT = "/usr/share/fonts/liberation/LiberationSans-%s.ttf"

SLUGS = {
    "japanese-affection-context-l0": "japanese",
    "parent-measurement-practice": "parent",
    "technical-pack-literacy": "technical",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT % ("Bold" if bold else "Regular"), size)


def ink_mask(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB")).astype(np.int16)
    return np.abs(a - np.array(PAPER)).max(axis=2) > 60


def main() -> int:
    covers = json.loads((AUDIT / "swap-check.json").read_text())["covers"]
    cell_w, cell_h, head = 620, 500, 96
    width = cell_w * 3 + 48
    im = Image.new("RGB", (width, head + cell_h + 40), PAPER)
    d = ImageDraw.Draw(im)
    d.text((24, 22), "A3 cover motif map — declared zones on the shipped masters",
           font=font(26, True), fill=INK)
    d.text((24, 58), "Outlined region = the motif's declared bbox. Vertical green line = the "
                     "mechanical 4:5 crop edge. Review artifact, not product UI.",
           font=font(15), fill=SOFT)

    report = {"card": "CP-012", "crop_window": list(CROP), "min_ink": 150,
              "min_retained": 0.60, "covers": []}

    for i, cover in enumerate(covers):
        slug = SLUGS[cover["pack"]]
        master_path = COVERS / f"{slug}-master-1200x800.png"
        mask = ink_mask(master_path)
        scale = 600 / 1200
        art = Image.open(master_path).convert("RGB").resize(
            (600, 400), Image.Resampling.LANCZOS)
        x0c, y0c = 24 + i * cell_w, head
        im.paste(art, (x0c, y0c))

        for cx in CROP:
            x = x0c + round(cx * scale)
            d.line([(x, y0c), (x, y0c + 400)], fill=CROP_EDGE, width=2)

        row = {"pack": cover["pack"], "accent": cover["accent"], "motifs": []}
        for motif in cover["motifs"]:
            bx0, by0, bx1, by1 = motif["bbox"]
            painted = int(mask[by0:by1, bx0:bx1].sum())
            ix0, ix1 = max(bx0, CROP[0]), min(bx1, CROP[1])
            kept = int(mask[by0:by1, ix0:ix1].sum()) if ix1 > ix0 else 0
            retained = kept / painted if painted else 0.0
            row["motifs"].append({"mark": motif["mark"], "bbox": motif["bbox"],
                                  "painted_px": painted, "retained": round(retained, 4)})
            rect = [x0c + round(bx0 * scale), y0c + round(by0 * scale),
                    x0c + round(bx1 * scale), y0c + round(by1 * scale)]
            d.rectangle(rect, outline=ZONE, width=2)
            d.text((rect[0] + 2, max(y0c + 2, rect[1] - 15)),
                   f"{motif['mark']} {retained:.0%}", font=font(13, True), fill=ZONE)

        d.text((x0c, y0c + 410), cover["title"], font=font(15, True), fill=INK)
        d.text((x0c, y0c + 432), f"{cover['pack']} · grammar {cover['grammar']} · "
                                 f"accent {cover['accent']}", font=font(13), fill=SOFT)
        d.text((x0c, y0c + 452), "motifs: " + ", ".join(m["mark"] for m in cover["motifs"]),
               font=font(13), fill=SOFT)
        report["covers"].append(row)

    d.line([(24, im.height - 26), (width - 24, im.height - 26)], fill=RULE, width=1)
    d.text((24, im.height - 20),
           "Retention is measured from the shipped master bytes inside each declared bbox; "
           "scripts/cp012-cover-accept.py fails under 60 %.",
           font=font(13), fill=SOFT)

    im.save(OUT_PNG, optimize=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {OUT_PNG.relative_to(ROOT)} ({im.width}x{im.height}) and {OUT_JSON.name}")
    for cover in report["covers"]:
        print(f"  {cover['pack']:34s} " + "  ".join(
            f"{m['mark']}={m['retained']:.0%}({m['painted_px']}px)" for m in cover["motifs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
