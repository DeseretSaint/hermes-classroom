#!/usr/bin/env python3
"""CP-028 — equal-width concept/product board builder for the v3 screens.

`scripts/cp-sbs.py` scales both sides to the *shorter* height, so a board is only at equal width
when both inputs have the same aspect ratio. A route capture is as tall as the route it holds, and
the concept frames are all 1344x768, so piping them straight into cp-sbs produces a board whose
product side is narrower than the concept side (the old sbs-home-live-1049-light.png is 1344 vs 691).

This tool fixes the aspect, not the truth: it crops the concept to the region named in
docs/concept-parity/gate/BOARD-TEMPLATE.md, crops the product to the same aspect ratio from the top
of its route box, and then hands the two prepared crops to `scripts/cp-sbs.py`. Both sides are then
scaled to one common width with no side stretched relative to the other. It never labels or scores
anything and it never invents pixels: a product capture too short for the crop is refused.

    python3 docs/concept-parity/gate/board.py --screen R-HOME \
        --product docs/concept-parity/captures/home-v3-1049-light.png \
        --out docs/concept-parity/gate/boards/board-home-v3-1049-light.png

    python3 docs/concept-parity/gate/board.py --screen R-HOME \
        --product <capture.png> --out <board.png> --dry-run --allow-unstamped

The product side must come from `scripts/cp-capture.mjs` (route-clipped, with a `.stamp.json`).
`--allow-unstamped` exists only for a mechanics dry run and prints a warning; a board built that way
is not parity evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is present on the build hosts
    print("board.py needs Pillow (python3 -c 'import PIL')", file=sys.stderr)
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parents[3]
REFS = "docs/concept-parity/refs"

# screen -> (concept ref, crop rectangle at the concept's native 1344x768, region compared)
SCREENS: dict[str, dict] = {
    "R-HOME": {
        "ref": f"{REFS}/home.png",
        "crop": (104, 60, 1240, 708),
        "region": "threshold band + action pair + wooden shelf + lower ledge with fox and clock",
        "matrix": "home.v3",
    },
    "R-DISC": {
        "ref": f"{REFS}/discover.png",
        "crop": (220, 96, 1124, 616),
        "region": "forest rail + feature banner + grid sharing one column track + fox at the grid foot",
        "matrix": "discover.v3",
    },
    "R-CLASS": {
        "ref": f"{REFS}/classroom.png",
        "crop": (156, 200, 1188, 568),
        "region": "stamp stepper + framed scene + dialogue + check card + aside + evidence tray",
        "matrix": "classroom.v3",
    },
    "R-SYS": {
        "ref": f"{REFS}/system.png",
        "crop": (160, 100, 1138, 640),
        "region": "fox specimens + card anatomy + medallion row + palette + type + materials",
        "matrix": "lab.v3",
    },
    "R-MAP": {
        "ref": f"{REFS}/map.png",
        "crop": (150, 150, 1090, 550),
        "region": "painted route field with hero plate + Continue aside + other-course shelf",
        "matrix": "course-home.v3",
    },
}


def parse_box(text: str) -> tuple[int, int, int, int]:
    parts = [int(piece) for piece in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--product-box wants x,y,width,height in CSS px")
    return parts[0], parts[1], parts[2], parts[3]


def resolve_geometry(product: Path, override, allow_unstamped: bool):
    """Return (route box in CSS px, device scale, stamp summary) for the product capture."""
    stamp_path = product.with_suffix(".stamp.json")
    stamp = None
    if stamp_path.exists():
        stamp = json.loads(stamp_path.read_text())
    if override:
        box, scale = override, 1.0
    elif stamp and stamp.get("clip"):
        clip = stamp["clip"]
        box = (int(clip["x"]), int(clip["y"]), int(clip["width"]), int(clip["height"]))
        with Image.open(product) as probe:
            scale = probe.width / box[2] if box[2] else 1.0
    else:
        if not allow_unstamped:
            print(
                f"REFUSED: {product} has no .stamp.json and no --product-box; a product side without "
                "a capture stamp is not parity evidence (RUBRIC-V3 E1).",
                file=sys.stderr,
            )
            raise SystemExit(2)
        with Image.open(product) as probe:
            box, scale = (0, 0, probe.width, probe.height), 1.0
        print("WARNING: --allow-unstamped used; this board is a mechanics dry run, not evidence.")
    return box, scale, stamp


def main() -> int:
    parser = argparse.ArgumentParser(description="Equal-width concept/product board for v3 screens.")
    parser.add_argument("--screen", required=True, choices=sorted(SCREENS))
    parser.add_argument("--product", required=True, help="route-clipped capture from scripts/cp-capture.mjs")
    parser.add_argument("--out", required=True, help="board PNG to write")
    parser.add_argument("--width", type=int, default=1049, help="width of each side in the board (default 1049)")
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--background", default="247,241,228")
    parser.add_argument("--product-box", type=parse_box, default=None, help="route box in CSS px when the capture has no stamp")
    parser.add_argument("--allow-unstamped", action="store_true", help="mechanics dry run only")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and the cp-sbs argv, write nothing")
    args = parser.parse_args()

    spec = SCREENS[args.screen]
    concept_path = REPO_ROOT / spec["ref"]
    product_path = (REPO_ROOT / args.product) if not Path(args.product).is_absolute() else Path(args.product)
    out_path = (REPO_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)

    if not concept_path.exists():
        print(f"missing concept frame {concept_path}", file=sys.stderr)
        return 2
    if not product_path.exists():
        print(f"missing product capture {product_path}", file=sys.stderr)
        return 2

    box, scale, stamp = resolve_geometry(product_path, args.product_box, args.allow_unstamped)
    crop_x, crop_y, crop_w, crop_h = spec["crop"]
    aspect = crop_h / crop_w

    # The product side is the top of the route box, cropped to the concept crop's aspect ratio.
    need_css_h = args.width * aspect
    if need_css_h > box[3] + 1:
        print(
            f"REFUSED: {args.screen} needs {need_css_h:.0f} CSS px of route height at width "
            f"{args.width} but the capture's route box is {box[2]}x{box[3]}. Capture the screen "
            "again with a taller route (or compare a region that fits) — do not pad.",
            file=sys.stderr,
        )
        return 2
    product_crop = (
        int(round(box[0] * scale)),
        int(round(box[1] * scale)),
        int(round(args.width * scale)),
        int(round(need_css_h * scale)),
    )

    with Image.open(concept_path) as image:
        if crop_x + crop_w > image.width or crop_y + crop_h > image.height:
            print(f"crop {spec['crop']} runs outside {concept_path} ({image.width}x{image.height})", file=sys.stderr)
            return 2

    plan = {
        "screen": args.screen,
        "matrix_id": spec["matrix"],
        "region": spec["region"],
        "concept": spec["ref"],
        "concept_crop": spec["crop"],
        "product": str(args.product),
        "product_box_css": box,
        "product_crop_px": product_crop,
        "device_scale": scale,
        "side_width": args.width,
        "stamp_sha": (stamp or {}).get("plugin", {}).get("window_sha256"),
        "stamp_ok": (stamp or {}).get("ok"),
        "crop_mode": (stamp or {}).get("crop_mode"),
    }
    print(json.dumps(plan, indent=2))

    with tempfile.TemporaryDirectory(prefix="cp-board-") as tmp:
        left = Path(tmp) / "left.png"
        right = Path(tmp) / "right.png"
        with Image.open(concept_path) as image:
            image.convert("RGB").crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h)).save(left)
        with Image.open(product_path) as image:
            x, y, w, h = product_crop
            if x + w > image.width or y + h > image.height:
                print(f"product crop {product_crop} runs outside {image.width}x{image.height}", file=sys.stderr)
                return 2
            image.convert("RGB").crop((x, y, x + w, y + h)).save(right)

        argv = [
            sys.executable,
            "scripts/cp-sbs.py",
            "--concept", str(left),
            "--product", str(right),
            "--out", str(out_path),
            "--gap", str(args.gap),
            "--background", args.background,
        ]
        print("delegating:", " ".join(argv))
        if args.dry_run:
            print("dry run: nothing written")
            return 0
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            return result.returncode
        # cp-sbs prints "wrote <out> (<w>x<h>, left=<lw> right=<rw>)"; assert equal sides.
        line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if "left=" in line and "right=" in line:
            left_w = int(line.split("left=")[1].split()[0])
            right_w = int(line.split("right=")[1].rstrip(")").strip())
            if abs(left_w - right_w) > 1:
                print(f"REFUSED: board sides are unequal ({left_w} vs {right_w}); aspect fix failed.", file=sys.stderr)
                return 2
            print(f"equal width verified (1 px rounding): left={left_w} right={right_w}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
