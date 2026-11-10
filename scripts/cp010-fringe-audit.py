#!/usr/bin/env python3
"""CP-010 fringe audit: count magenta-contaminated edge pixels in a keyed cutout."""
import sys
from PIL import Image


def main(path):
    im = Image.open(path).convert("RGBA")
    px = im.load()
    w, h = im.size
    mag = semi = opaque = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if a < 255:
                semi += 1
            opaque += 1
            # magenta signature: red and blue high, green suppressed
            if r > 140 and b > 100 and g < 90 and (r - g) > 70 and (b - g) > 50:
                mag += 1
    print(f"{path}: {w}x{h}")
    print(f"  opaque pixels        : {opaque}")
    print(f"  semi-transparent px  : {semi} ({semi / max(opaque, 1):.3%})")
    print(f"  magenta-contaminated : {mag} ({mag / max(opaque, 1):.3%})")
    return 0 if mag / max(opaque, 1) < 0.001 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
