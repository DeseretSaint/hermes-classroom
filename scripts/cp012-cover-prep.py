#!/usr/bin/env python3
"""CP-012 cover prep: one paper, one temper, one crop, three deliverable files.

Deterministic, no model call. Usage:

  python3 scripts/cp012-cover-prep.py <raw.png> <out-dir> <slug> [--master-only]

What it does, in order, and why each step is here:

1. **Paper match.** The provider returns a different off-white on every call
   (#f8f7f0, #fbf6e6, #f8f7ea across the three A3 raws). The kit rule is one
   paper, so the measured corner colour is scaled channel-by-channel onto the
   contract's `card-stock` paper `#f7f1e4`. Gains are clamped to [0.90, 1.10];
   a file that needs more than that is a different paper and is regenerated,
   not stretched.
2. **One temper.** A single global `-modulate 97,86,100` pulls the raw's
   saturation into the muted gouache family the A1 fox set was tempered into
   (`docs/concept-parity/ART-BIBLE.md` §2, "Measured pigments"). One value for
   every cover, so no cover can drift in saturation alone.
3. **One crop.** The 16:9 raw is centre-cropped to 864x576 (3:2), then resized
   to the 1200x800 master with Lanczos at 1.389x — inside the 1.5x ceiling the
   art direction sets. The 4:5 file is a 640x800 centre crop of the shipped
   master with no resampling, so it cannot be a second drawing.

Output files in <out-dir>:

  <slug>-master-1200x800.png   the master, 3:2
  <slug>-crop-3x2-1200x800.png byte-identical 3:2 export of the master
  <slug>-crop-4x5-640x800.png  mechanical centre crop, 4:5
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

MASTER_W, MASTER_H = 1200, 800
CROP_W, CROP_H = 640, 800
RAW_CROP_W = 864
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


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    raw, out_dir, slug = argv[1], Path(argv[2]), argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)

    w, h = (int(v) for v in magick(raw, "-format", "%w %h", "info:").split())
    if (w, h) != (1024, 576):
        raise SystemExit(f"{raw}: expected a 1024x576 16:9 raw, measured {w}x{h}")

    tmp = Path(tempfile.mkdtemp(prefix="cp012-cover-")) / "tempered.png"
    # Temper first, paper-match second: the match must land the corner on the
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

    master = out_dir / f"{slug}-master-{MASTER_W}x{MASTER_H}.png"
    magick(str(matched), "-gravity", "center", "-crop", f"{RAW_CROP_W}x{h}+0+0", "+repage",
           "-resize", f"{MASTER_W}x{MASTER_H}!", "-strip", "-define", "png:color-type=2",
           str(master))

    crop32 = out_dir / f"{slug}-crop-3x2-{MASTER_W}x{MASTER_H}.png"
    magick(str(master), "-strip", str(crop32))

    crop45 = out_dir / f"{slug}-crop-4x5-{CROP_W}x{CROP_H}.png"
    magick(str(master), "-gravity", "center", "-crop", f"{CROP_W}x{CROP_H}+0+0", "+repage",
           "-strip", str(crop45))

    print(f"paper after: {corner_rgb(str(master))}")
    for p in (master, crop32, crop45):
        print(f"{p.name}: {magick(str(p), '-format', '%wx%h %[channels] %b', 'info:')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
