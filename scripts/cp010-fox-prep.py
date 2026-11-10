#!/usr/bin/env python3
"""CP-010 fox cutout prep: key the flat chroma ground, trim, pad, export sizes.

Deterministic, no model call. Usage:
  python3 scripts/cp010-fox-prep.py <raw.png> <out-master.png> [--fuzz 12]

The chroma colour is sampled from the file's own corner (the provider does not
return the literal #ff00ff we asked for), then every pixel within --fuzz of that
colour is made transparent. The matte is not blurred: a blurred matte is a halo,
not an edge.
"""
import subprocess
import sys


def magick(*args):
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"magick failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    raw, out = argv[1], argv[2]
    fuzz = argv[argv.index("--fuzz") + 1] if "--fuzz" in argv else "12"

    corner = magick(raw, "-format", "%[pixel:p{2,2}]", "info:")
    chroma = corner.replace("srgb(", "rgb(")  # magick accepts rgb(r,g,b)
    print(f"sampled corner chroma: {corner}")

    magick(raw, "-alpha", "on", "-fuzz", f"{fuzz}%",
           "-transparent", chroma, "-trim", "+repage",
           "-bordercolor", "none", "-border", "16", "/tmp/cp010-keyed.png")

    w, h = (int(v) for v in magick("/tmp/cp010-keyed.png", "-format", "%w %h", "info:").split())
    side = max(w, h)
    # Colour temper: the provider returns a more saturated rust than the art
    # bible's pigment. One deterministic global temper brings every plate to the
    # same muted gouache family, so a pose cannot drift in saturation alone.
    magick("/tmp/cp010-keyed.png", "-background", "none", "-gravity", "center",
           "-extent", f"{side}x{side}", "-modulate", "92,72,100", out)

    # Remaining chroma-ish pixels, counted on a black/white mask.
    mean = float(magick(out, "-fuzz", "6%", "-fill", "black", "-opaque", chroma,
                        "-fill", "white", "+opaque", "black",
                        "-format", "%[fx:mean]", "info:"))
    total = side * side
    left = round((1.0 - mean) * total)
    print(f"pixels still within 6% of chroma: {left} of {total}")
    print(f"master: {out} ({side}x{side})")

    for size in (512, 256, 128, 64):
        target = out.rsplit(".", 1)[0] + f"-{size}.png"
        magick(out, "-resize", f"x{size}", "-unsharp", "0x0.6+0.5+0.02", target)
        print(f"  {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
