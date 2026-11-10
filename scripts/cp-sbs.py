#!/usr/bin/env python3
"""CP-000 — equal-height side-by-side proof sheet (concept crop left, product capture right).

The concept images are AI stills: they carry garbled labels and invented data, so this tool never
claims they are the product. It only puts a crop of a reference image next to a stamped product
capture at the same height, so a parity review can compare material, type and density honestly.

    python3 scripts/cp-sbs.py \
        --concept docs/concept-parity/refs/home.png --crop 0,0,1000,700 \
        --product docs/concept-parity/captures/home-live-1049-light.png \
        --out docs/concept-parity/captures/sbs-home.png [--gap 24] [--background 247,241,228]

Both sides are scaled to the shorter side's height; no labels are burned into the PNG because every
label in a proof sheet must be real DOM text or an explicit caption outside the image.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is present on the build hosts
    print("cp-sbs.py needs Pillow (python3 -c 'import PIL')", file=sys.stderr)
    raise SystemExit(2)


def parse_crop(text: str) -> tuple[int, int, int, int]:
    parts = [int(piece) for piece in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop wants x,y,width,height")
    return parts[0], parts[1], parts[2], parts[3]


def parse_colour(text: str) -> tuple[int, int, int]:
    parts = [int(piece) for piece in text.split(",")]
    if len(parts) != 3 or any(piece < 0 or piece > 255 for piece in parts):
        raise argparse.ArgumentTypeError("--background wants r,g,b in 0..255")
    return parts[0], parts[1], parts[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concept", required=True)
    parser.add_argument("--crop", default=None, type=parse_crop)
    parser.add_argument("--product", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--background", type=parse_colour, default=(247, 241, 228))
    args = parser.parse_args()

    concept = Image.open(args.concept).convert("RGB")
    if args.crop:
        x, y, width, height = args.crop
        concept = concept.crop((x, y, x + width, y + height))
    product = Image.open(args.product).convert("RGB")

    target_height = min(concept.height, product.height)

    def scaled(image: Image.Image) -> Image.Image:
        ratio = target_height / image.height
        return image.resize((max(1, round(image.width * ratio)), target_height), Image.Resampling.LANCZOS)

    left, right = scaled(concept), scaled(product)
    canvas = Image.new(
        "RGB",
        (left.width + args.gap + right.width, target_height),
        args.background,
    )
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + args.gap, 0))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)
    print(f"wrote {out} ({canvas.width}x{canvas.height}, left={left.width} right={right.width})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
