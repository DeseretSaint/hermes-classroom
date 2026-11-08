#!/usr/bin/env python3
"""Generate the committed M4 media gate fixtures in tests/fixtures/media/.

The M4 visual/media audit used to read its two media artifacts from
``~/.hermes/cache/scratch/cb-media-image.png`` and ``cb-media-audio.mp3``. Nothing in the tree
carried those bytes and the scratch janitor prunes idle entries, so the gate depended on files a
clean checkout cannot reproduce. H-136 replaces them with committed fixtures and this script
regenerates the image half deterministically.

    python3 scripts/make-m4-fixtures.py            # rewrite cb-media-image.png
    python3 scripts/make-m4-fixtures.py --check    # fail if the committed PNG is stale

The speech fixture is a real MP3 of the documented utterance. It is synthesized once and committed;
re-synthesizing it needs the free Microsoft Edge speech service, so the exact command lives in
``tests/fixtures/media/README.md`` rather than in this script (a network dependency is not part of
the gate). Both fixture files are labelled gate fixtures, not the M0 host-probe artifacts.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "media" / "cb-media-image.png"

WIDTH, HEIGHT = 1024, 576
SCALE = 2  # draw at 2x, downsample for clean edges

PAPER = (244, 239, 230, 255)
BENCH = (196, 176, 150, 255)
INK = (58, 52, 44, 255)
STEEL = (150, 155, 162, 255)
STEEL_DARK = (104, 108, 116, 255)
RING = (72, 78, 86, 255)
RING_LIGHT = (128, 134, 142, 255)
OCHRE = (198, 148, 72, 255)


def _ring(draw: ImageDraw.ImageDraw, cx: int, cy: int, outer: int, inner: int,
          fill, outline, width: int = 10) -> None:
    draw.ellipse([cx - outer, cy - outer, cx + outer, cy + outer], fill=fill, outline=outline, width=width)
    draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=PAPER, outline=outline, width=width)


def render() -> Image.Image:
    """A flat workshop-bench plate: one large-bore gasket ring, a torque wrench, hand tools.

    Deliberately carries no text, numbers, arrows, bolt sequence, clearance or orientation mark, so
    the illustration can only be context. This is a deterministic gate fixture, not a generated
    illustration: it exists to prove the player renders and decodes a real PNG of the documented
    size.
    """
    image = Image.new("RGBA", (WIDTH * SCALE, HEIGHT * SCALE), PAPER)
    draw = ImageDraw.Draw(image)
    s = SCALE

    # Bench plane and a soft shadow under the tools.
    draw.rectangle([0, 400 * s, WIDTH * s, HEIGHT * s], fill=BENCH)
    draw.rectangle([0, 400 * s, WIDTH * s, 412 * s], fill=(172, 152, 128, 255))
    draw.ellipse([150 * s, 430 * s, 760 * s, 500 * s], fill=(210, 194, 174, 255))

    # Head gasket: one large bore, two locating holes, a raised rim. Nothing that reads as a
    # torque value, a bolt order or a clearance.
    gasket = [300 * s, 180 * s, 640 * s, 440 * s]
    draw.ellipse(gasket, fill=RING_LIGHT, outline=RING, width=8 * s)
    draw.ellipse([330 * s, 210 * s, 610 * s, 410 * s], fill=RING, outline=RING, width=6 * s)
    draw.ellipse([368 * s, 244 * s, 572 * s, 376 * s], fill=PAPER, outline=STEEL_DARK, width=8 * s)
    draw.ellipse([412 * s, 278 * s, 528 * s, 342 * s], fill=(222, 216, 204, 255),
                 outline=STEEL_DARK, width=5 * s)
    for cx, cy in ((352, 232), (588, 232)):
        draw.ellipse([(cx - 14) * s, (cy - 14) * s, (cx + 14) * s, (cy + 14) * s],
                     fill=PAPER, outline=STEEL_DARK, width=5 * s)

    # Torque wrench to the right: handle, head, scale arm. No legible scale numerals.
    draw.rounded_rectangle([690 * s, 300 * s, 930 * s, 326 * s], radius=13 * s, fill=STEEL,
                           outline=STEEL_DARK, width=4 * s)
    draw.rounded_rectangle([700 * s, 300 * s, 760 * s, 326 * s], radius=13 * s, fill=OCHRE,
                           outline=STEEL_DARK, width=4 * s)
    draw.ellipse([650 * s, 286 * s, 716 * s, 340 * s], fill=STEEL, outline=STEEL_DARK, width=6 * s)
    draw.ellipse([670 * s, 300 * s, 696 * s, 326 * s], fill=PAPER, outline=STEEL_DARK, width=4 * s)
    draw.rectangle([880 * s, 304 * s, 936 * s, 322 * s], fill=STEEL_DARK)

    # Hand tools on the bench: a hammer and a screwdriver, again with no markings.
    draw.rounded_rectangle([120 * s, 470 * s, 360 * s, 486 * s], radius=8 * s, fill=(122, 96, 70, 255),
                           outline=INK, width=3 * s)
    draw.rounded_rectangle([330 * s, 436 * s, 400 * s, 510 * s], radius=8 * s, fill=STEEL,
                           outline=STEEL_DARK, width=4 * s)
    draw.rounded_rectangle([440 * s, 476 * s, 700 * s, 488 * s], radius=6 * s, fill=OCHRE,
                           outline=INK, width=3 * s)
    draw.rectangle([690 * s, 474 * s, 730 * s, 490 * s], fill=STEEL, outline=STEEL_DARK, width=3 * s)

    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).convert("RGB")


def main(argv: list[str]) -> int:
    expected = render()
    if "--check" in argv:
        if not FIXTURE.is_file():
            print(f"missing fixture: {FIXTURE}", file=sys.stderr)
            return 1
        committed = Image.open(FIXTURE).convert("RGB")
        if committed.size != (WIDTH, HEIGHT) or committed.tobytes() != expected.tobytes():
            print(f"{FIXTURE} does not match the generator; run scripts/make-m4-fixtures.py",
                  file=sys.stderr)
            return 1
        print(f"ok {FIXTURE.relative_to(ROOT)} sha256={hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}")
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    expected.save(FIXTURE, format="PNG", optimize=True)
    print(f"wrote {FIXTURE.relative_to(ROOT)} {FIXTURE.stat().st_size} bytes "
          f"sha256={hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
