#!/usr/bin/env python3
"""CP-010 numeric art audit: pigment presence, contour colour, pure-black count.

Usage: python3 scripts/cp010-art-audit.py  (run from the repo root)

Writes audit/cp010-fox/art-audit.json. Every claim in that file is a count this
script printed; nothing is estimated.
"""
import hashlib
import json
import os

from PIL import Image

PIGMENTS = {
    "fur": (0xB7, 0x64, 0x3D),
    "cream": (0xEF, 0xE0, 0xC2),
    "sock": (0x2B, 0x1D, 0x14),
    "line": (0x3A, 0x23, 0x18),
}
TOL = 26  # per-channel tolerance, chosen so the gouache shade planes do not count
POSES = ["model-sheet", "wave", "point", "clock", "read", "cheer", "think", "sleep"]


def near(px, ref, tol=TOL):
    return all(abs(px[i] - ref[i]) <= tol for i in range(3))


def audit(path):
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    data = im.tobytes()
    counts = {k: 0 for k in PIGMENTS}
    black = 0
    opaque = 0
    for i in range(0, len(data), 4):
        r, g, b, a = data[i], data[i + 1], data[i + 2], data[i + 3]
        if a < 200:
            continue
        opaque += 1
        if r < 12 and g < 12 and b < 12:
            black += 1
        for name, ref in PIGMENTS.items():
            if near((r, g, b), ref):
                counts[name] += 1
                break
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    alpha = im.getchannel("A")
    return {
        "file": path,
        "size": [w, h],
        "bytes": os.path.getsize(path),
        "sha256": digest,
        "alpha_bbox": list(alpha.getbbox() or ()),
        "opaque_px": opaque,
        "pure_black_px": black,
        "pure_black_share": round(black / max(opaque, 1), 5),
        "pigment_px": counts,
        "pigment_share": {k: round(v / max(opaque, 1), 5) for k, v in counts.items()},
    }


def main():
    rows = []
    for p in POSES:
        path = ("assets/art/fox/fox-model-sheet.png" if p == "model-sheet"
                else f"assets/art/fox/fox-{p}.png")
        rows.append(audit(path))
    os.makedirs("audit/cp010-fox", exist_ok=True)
    with open("audit/cp010-fox/art-audit.json", "w") as fh:
        json.dump({"tolerance": TOL, "poses": rows}, fh, indent=2)
    for r in rows:
        print(f"{r['file']}: {r['size']} black={r['pure_black_share']:.4%} "
              f"pigments={r['pigment_share']}")


if __name__ == "__main__":
    main()
