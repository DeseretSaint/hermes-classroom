#!/usr/bin/env python3
"""CP-013 scene and object prep: deterministic, no model call.

Scenes
  A scene raw is a 16:9 (1024x576) painted plate. The banner is cropped to its
  4.4:1 band at a vertical offset chosen by `scripts/cp013-quiet-probe.py` — the
  offset with the calmest reserved field and no dark mass under where the title
  sits — never by eye. The cafe and the map ship the full 16:9 frame; the lesson
  frame crops that master mechanically at render time (SPEC-V3 §3.3: a plate is
  cropped, never stretched).

Objects
  A5 objects are cutouts. The same chroma key, trim, square pad and colour
  temper as A1 (`scripts/cp010-fox-prep.py`, fuzz 30) is applied, then the plate
  is exported at 256 px RGBA — the size `PLAN.md` §5 A5 pins. No matte is baked
  in; alpha stays binary after the key.

Usage:
  python3 scripts/cp013-scene-prep.py scenes
  python3 scripts/cp013-scene-prep.py objects
  python3 scripts/cp013-scene-prep.py all
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "audit" / "cp013-scenes" / "raw"
SCENES = ROOT / "assets" / "art" / "scenes"
OBJECTS = ROOT / "assets" / "art" / "objects"

#: plate id -> (raw file, target aspect, crop offset as a fraction of the slack)
SCENE_PLAN = {
    "discover-banner": ("scene-banner-raw-r3.png", 4.4, 196),
    "lesson-cafe": ("scene-cafe-raw.png", 16 / 9, 0),
    "course-map": ("scene-map-raw.png", 16 / 9, 0),
}

#: object id -> raw file, when the shipped plate is not the first round
RAW_OVERRIDE = {"passport-tray": "object-passport-tray-raw-r2.png"}

#: the six blanks the card names, plus the shelf plank the kit has always carried
OBJECT_PLAN = (
    "stamp-rim",
    "medallion-rim",
    "passport-tray",
    "ticket",
    "clock",
    "tag",
    "shelf-plank",
)


def magick(*args):
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("magick failed: %s\n%s" % (" ".join(args), r.stderr))
    return r.stdout.strip()


def build_scene(plate, raw_name, aspect, y0):
    raw = RAW / raw_name
    if not raw.is_file():
        raise SystemExit("missing raw plate: %s" % raw)
    width, height = (int(v) for v in magick(str(raw), "-format", "%w %h", "info:").split())
    band = round(width / aspect)
    if band > height:
        raise SystemExit("%s is %dx%d: too short for %.3f:1" % (raw_name, width, height, aspect))
    y0 = max(0, min(y0, height - band))
    SCENES.mkdir(parents=True, exist_ok=True)
    out = SCENES / ("%s.png" % plate)
    # Print-safety lift: the medium forbids a black or near-black value, so the raw's pure-black
    # deepest shadow is mapped into a warm umber band (+level) before the plate ships. The lift is
    # 4 % of the range: enough to remove true black, not enough to flatten the scene.
    magick(str(raw), "-crop", "%dx%d+0+%d" % (width, band, y0), "+repage",
           "-alpha", "off", "+level", "4%,100%", str(out))
    print("%-16s %s -> %s (%dx%d, crop y0=%d)" % (plate, raw_name, out.relative_to(ROOT), width, band, y0))
    return out


def build_object(name):
    raw_name = RAW_OVERRIDE.get(name)
    if raw_name is None:
        raw_name = "object-%s-raw.png" % name
    raw = RAW / raw_name
    if not raw.is_file():
        raise SystemExit("missing raw object: %s" % raw)
    corner = magick(str(raw), "-format", "%[pixel:p{2,2}]", "info:")
    chroma = corner.replace("srgb(", "rgb(")
    keyed = str(Path(tempfile.mkdtemp(prefix="cp013-key-")) / "keyed.png")
    magick(str(raw), "-alpha", "on", "-fuzz", "30%", "-transparent", chroma,
           "-trim", "+repage", "-bordercolor", "none", "-border", "16", keyed)
    side = max(int(v) for v in magick(keyed, "-format", "%w %h", "info:").split())
    OBJECTS.mkdir(parents=True, exist_ok=True)
    out = OBJECTS / ("%s.png" % name)
    magick(keyed, "-background", "none", "-gravity", "center", "-extent", "%dx%d" % (side, side),
           "-modulate", "92,72,100", "-resize", "256x256", "-unsharp", "0x0.6+0.5+0.02", str(out))
    left = float(magick(str(out), "-fuzz", "6%", "-fill", "black", "-opaque", chroma,
                        "-fill", "white", "+opaque", "black", "-format", "%[fx:mean]", "info:"))
    print("%-16s chroma %s -> %s (256x256, %d residual chroma px)"
          % (name, corner, out.relative_to(ROOT), round((1.0 - left) * 256 * 256)))
    return out


def main(argv):
    what = argv[1] if len(argv) > 1 else "all"
    if what in ("scenes", "all"):
        for plate, (raw_name, aspect, y0) in SCENE_PLAN.items():
            build_scene(plate, raw_name, aspect, y0)
    if what in ("objects", "all"):
        for name in OBJECT_PLAN:
            build_object(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
