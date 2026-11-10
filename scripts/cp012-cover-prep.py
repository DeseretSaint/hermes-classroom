#!/usr/bin/env python3
"""CP-012 cover prep: one paper, one temper, one placement, one crop.

Deterministic, no model call. Usage:

  python3 scripts/cp012-cover-prep.py <raw.png> <out-dir> <slug>

What it does, in order, and why each step is here:

1. **Paper match.** The provider returns a different off-white on every call.
   The kit rule is one paper, so the measured edge colour is scaled
   channel-by-channel onto the contract's `card-stock` paper `#f7f1e4`. Gains
   are clamped to [0.90, 1.10]; a file that needs more than that is a
   different paper and is regenerated, not stretched.
2. **One temper.** A single global `-modulate 97,78,100` pulls the raw's
   saturation into the muted gouache family the A1 fox set was tempered into
   (`docs/concept-parity/ART-BIBLE.md` §2). One value for every cover, so no
   cover can drift in saturation alone.
3. **One placement.** The raw is a square plate. The plate is scaled so its
   *painted ink bounding box* fits inside the 4:5 safe window (the 640x800
   centre crop, less a 16 px margin) and centred on the 1200x800 master's own
   paper field. This is what makes the *mechanical* 4:5 crop keep every
   subject: no painted mark can fall outside the crop window, so no motif is
   severed at the crop edge. Round 1 shipped the full 16:9 raw as the master
   and the 4:5 crop severed the Japanese lantern (18 % of its ink survived)
   and most of the parent oranges; the reviewer's test is now satisfied by
   construction and re-checked from the shipped bytes.
   Placement is not a second drawing: it is the same single plate, paper-
   matched, scaled once and set on the kit's paper.
4. **One crop.** The 4:5 file is a 640x800 centre crop of the shipped master
   with no resampling, so it cannot be a second drawing.

Output files in <out-dir>:

  <slug>-master-1200x800.png   the master, 3:2
  <slug>-crop-3x2-1200x800.png byte-identical 3:2 export of the master
  <slug>-crop-4x5-640x800.png  mechanical centre crop, 4:5
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

MASTER_W, MASTER_H = 1200, 800
CROP_W, CROP_H = 640, 800
CROP_X = (MASTER_W - CROP_W) // 2  # 280
SAFE_MARGIN = 16                   # px of paper kept inside the crop window
TEMPER = "97,78,100"
PAPER = (247, 241, 228)  # #f7f1e4, contract role `card-stock`


def magick(*args: str) -> str:
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"magick failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def corner_rgb(path: str) -> tuple[int, int, int]:
    """Mean colour of a 32x32 patch at the top-right of the plate (never a form)."""
    out = magick(path, "-gravity", "northeast", "-crop", "32x32+0+0", "+repage",
                 "-format", "%[fx:round(255*mean.r)] %[fx:round(255*mean.g)] %[fx:round(255*mean.b)]",
                 "info:")
    r, g, b = (int(v) for v in out.split())
    return r, g, b


def ink_bbox(path: str) -> tuple[int, int, int, int]:
    """Bounding box of non-paper pixels, trimmed against the paper fill colour."""
    out = magick(path, "-fuzz", "22%", "-format", "%@", "info:")
    m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", out)
    if not m:
        raise SystemExit(f"{path}: unexpected trim box {out!r}")
    w, h, x, y = (int(v) for v in m.groups())
    return x, y, x + w, y + h


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    raw, out_dir, slug = argv[1], Path(argv[2]), argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)

    w, h = (int(v) for v in magick(raw, "-format", "%w %h", "info:").split())
    if w != h or w < 768:
        raise SystemExit(f"{raw}: expected a square raw of at least 768 px, measured {w}x{h}")

    tmp = Path(tempfile.mkdtemp(prefix="cp012-cover-")) / "tempered.png"
    # Temper first, paper-match second: the match must land the paper on the
    # contract value, and a gain applied before the temper cannot promise that.
    magick(raw, "-modulate", TEMPER, str(tmp))
    measured = corner_rgb(str(tmp))
    gains = [PAPER[i] / measured[i] for i in range(3)]
    if any(not (0.90 <= g <= 1.10) for g in gains):
        raise SystemExit(
            f"{raw}: tempered paper {measured} needs gains {['%.3f' % g for g in gains]}, "
            "outside the 0.90-1.10 clamp — regenerate, do not stretch")
    print(f"tempered paper {measured} -> gains {['%.3f' % g for g in gains]}")
    matched = Path(tempfile.mkdtemp(prefix="cp012-cover-")) / "matched.png"
    magick(str(tmp),
           "-channel", "R", "-evaluate", "multiply", f"{gains[0]:.4f}", "+channel",
           "-channel", "G", "-evaluate", "multiply", f"{gains[1]:.4f}", "+channel",
           "-channel", "B", "-evaluate", "multiply", f"{gains[2]:.4f}", "+channel",
           str(matched))

    bx0, by0, bx1, by1 = ink_bbox(str(matched))
    bw, bh = bx1 - bx0, by1 - by0
    if bw <= 0 or bh <= 0:
        raise SystemExit(f"{raw}: no painted ink found; the plate is blank")
    safe_w = CROP_W - 2 * SAFE_MARGIN          # 608
    # Only the horizontal fit matters: the 4:5 crop keeps the full master
    # height, so vertical bleed is a plate edge, never a crop loss.
    scale = min(MASTER_H / w, safe_w / bw)
    plate_px = round(scale * w)
    plate = Path(tempfile.mkdtemp(prefix="cp012-cover-")) / "plate.png"
    magick(str(matched), "-filter", "Lanczos", "-resize", f"{plate_px}x{plate_px}",
           "-unsharp", "0x0.6+0.5+0.02", str(plate))
    print(f"ink bbox {bw}x{bh} of {w} raw -> scale {scale:.4f}, plate {plate_px}px")

    # Centre the ink bbox inside the crop window, then keep the plate itself
    # on the canvas (a plate wider than the canvas is cropped by the master).
    bx_c, by_c = (bx0 + bx1) / 2 * scale, (by0 + by1) / 2 * scale
    off_x = round(CROP_X + CROP_W / 2 - bx_c)
    off_y = round(MASTER_H / 2 - by_c)
    if plate_px <= MASTER_W:
        off_x = min(max(off_x, 0), MASTER_W - plate_px)
    if plate_px <= MASTER_H:
        off_y = min(max(off_y, 0), MASTER_H - plate_px)

    master = out_dir / f"{slug}-master-{MASTER_W}x{MASTER_H}.png"
    magick("-size", f"{MASTER_W}x{MASTER_H}", f"xc:#{PAPER[0]:02x}{PAPER[1]:02x}{PAPER[2]:02x}",
           str(plate), "-geometry", f"+{off_x}+{off_y}", "-composite",
           "-strip", "-define", "png:color-type=2", str(master))

    crop32 = out_dir / f"{slug}-crop-3x2-{MASTER_W}x{MASTER_H}.png"
    magick(str(master), "-strip", str(crop32))

    crop45 = out_dir / f"{slug}-crop-4x5-{CROP_W}x{CROP_H}.png"
    magick(str(master), "-crop", f"{CROP_W}x{CROP_H}+{CROP_X}+0",
           "+repage", "-strip", str(crop45))

    print(f"paper after: {corner_rgb(str(master))}")
    for p in (master, crop32, crop45):
        print(f"{p.name}: {magick(str(p), '-format', '%wx%h %[channels] %b', 'info:')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
