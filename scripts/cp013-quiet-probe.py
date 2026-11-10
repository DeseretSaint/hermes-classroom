#!/usr/bin/env python3
"""CP-013 probe: measure a candidate quiet field inside a painted scene.

Reads a raw plate, crops the reserved band at a range of vertical offsets and
prints, per offset, the detail energy and luminance spread of the region a DOM
title would sit in. Used to pick the crop offset that actually is quiet, instead
of eyeballing one.

Usage: python3 scripts/cp013-quiet-probe.py <raw.png> [--aspect 4.4] [--left 0.40]
"""
import sys

from PIL import Image, ImageFilter, ImageStat


def main(argv):
    path = argv[1]
    aspect = 4.4
    left = 0.40
    if "--aspect" in argv:
        aspect = float(argv[argv.index("--aspect") + 1])
    if "--left" in argv:
        left = float(argv[argv.index("--left") + 1])

    img = Image.open(path).convert("RGB")
    w, h = img.size
    band = round(w / aspect)
    if band > h:
        raise SystemExit("plate is not tall enough for %.2f:1" % aspect)

    print("plate %s %dx%d, crop band %dpx tall, quiet field = left %d%%" % (path, w, h, band, round(left * 100)))
    print("%6s %9s %9s %9s %9s %9s" % ("y0", "detail", "lum_med", "p05", "p95", "dark_frac"))
    for y0 in range(0, h - band + 1, max(1, (h - band) // 12)):
        crop = img.crop((0, y0, w, y0 + band))
        field = crop.crop((0, 0, round(w * left), band))
        gray = field.convert("L")
        detail = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
        hist = gray.histogram()
        total = sum(hist)
        acc = 0
        p05 = p95 = med = 0
        for i, n in enumerate(hist):
            acc += n
            if not p05 and acc >= total * 0.05:
                p05 = i
            if not med and acc >= total * 0.50:
                med = i
            if not p95 and acc >= total * 0.95:
                p95 = i
        dark = sum(hist[:70]) / total
        print("%6d %9.2f %9d %9d %9d %9.3f" % (y0, detail, med, p05, p95, dark))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
