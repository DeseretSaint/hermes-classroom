#!/usr/bin/env python3
"""H-197 — the Press Plate acceptance block, run over the generator's fallback bytes.

CP-014 moved the bundled packs to the CP-012 painted plates, so the Press Plate is no longer a
shipped file; it remains the composed typographic fallback for a pack that declares no cover.
This script therefore materialises the builder's Press Plate output into a temporary tree and runs
the same acceptance block over it, so the fallback lane stays provable without a shipped file.

The art direction measured the host image pipeline and wrote a hard acceptance list for a cover
plate. The plates in this repository are printed by `bundled/packs/build_bundled_packs.py` instead of
by a model, so the same list is enforced mechanically here:

* exactly five identity inks, and none of them outside the Atlas Lamp token set;
* the left 4% carries only ground, band or flood (the app paints a 6px lamp spine there);
* the form's centroid sits inside the middle 84% so the 3:2 card crop survives;
* one lamp band, full bleed, at the imprint's fixed y, 8–12% of the frame height;
* the flood and the band stay inside their area budget;
* the 3:2 file is the mechanical centre crop of the 16:9 master, not a second drawing;
* the file is under 40 KB and has no alpha channel.

The things vision must judge — "no legible mark, object, gradient or shadow at 1:1", "legible at
240x160" — are recorded in docs/H197-COVERS.md with the inspection that was actually performed.
This script is the machine half of that evidence, not a substitute for it.

Run from the plugin root:

    python3 scripts/h197-cover-accept.py
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "bundled" / "packs"

COVER_W, COVER_H = 1024, 576
CROP_W = 864
LEFT_CLEAR = 41  # 4% of the width
BAND_TOP = 518  # 58px band = 10.1% of the height
BAND_HEIGHT = COVER_H - BAND_TOP

PAPER = (247, 241, 228)  # #f7f1e4
INK = (26, 23, 19)  # #1a1713
RULE = (215, 203, 180)  # #d7cbb4
ACCENT = (44, 74, 140)  # #2c4a8c
LAMP = (232, 169, 58)  # #e8a93a
LAMP_SOFT = (251, 235, 203)  # #fbebcb
PLUM = (106, 62, 116)  # #6a3e74
TOKENS = {PAPER, INK, RULE, ACCENT, LAMP, LAMP_SOFT, PLUM}
GROUND = {PAPER, LAMP, LAMP_SOFT}

PLATES = (
    ("japanese", "japanese-affection-context-l0", {PAPER, INK, ACCENT, LAMP_SOFT, LAMP}),
    ("technical", "technical-pack-literacy", {PAPER, INK, RULE, LAMP_SOFT, LAMP}),
)
MAX_BYTES = 40 * 1024


def read_png(path: Path) -> tuple[int, int, bytes, int]:
    """Decode an 8-bit RGB/RGBA non-interlaced PNG to ``(width, height, rgb_bytes, channels)``."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path.name}: not a PNG")
    offset = 8
    width = height = 0
    colour_type = 2
    idat = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        tag = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if bit_depth != 8 or interlace != 0:
                raise AssertionError(f"{path.name}: expected an 8-bit non-interlaced PNG")
        elif tag == b"IDAT":
            idat.extend(payload)
        elif tag == b"IEND":
            break
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(width * height * 3)
    previous = bytearray(stride)
    position = 0
    for row in range(height):
        filter_type = raw[position]
        position += 1
        line = bytearray(raw[position : position + stride])
        position += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:  # Sub
            for index in range(channels, stride):
                line[index] = (line[index] + line[index - channels]) & 0xFF
        elif filter_type == 2:  # Up
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:  # Average
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for index in range(stride):
                a = line[index - channels] if index >= channels else 0
                b = previous[index]
                c = previous[index - channels] if index >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[index] = (line[index] + predictor) & 0xFF
        else:
            raise AssertionError(f"{path.name}: unknown PNG filter {filter_type}")
        previous = line
        for column in range(width):
            source = column * channels
            target = (row * width + column) * 3
            out[target : target + 3] = line[source : source + 3]
    return width, height, bytes(out), channels


def pixel(rgb: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * width + x) * 3
    return (rgb[offset], rgb[offset + 1], rgb[offset + 2])


def check_plate(kind: str, slug: str, palette: set[tuple[int, int, int]], failures: list[str]) -> None:
    master_path = PACKS / slug / "content" / "cover-16x9.png"
    crop_path = PACKS / slug / "content" / "cover-3x2.png"

    def fail(message: str) -> None:
        failures.append(f"{kind}: {message}")

    for path in (master_path, crop_path):
        if not path.exists():
            fail(f"{path.name} is missing")
            return
        if path.stat().st_size > MAX_BYTES:
            fail(f"{path.name} is {path.stat().st_size} bytes (limit {MAX_BYTES})")

    width, height, rgb, channels = read_png(master_path)
    if (width, height) != (COVER_W, COVER_H):
        fail(f"master is {width}x{height}, expected {COVER_W}x{COVER_H}")
    if channels != 3:
        fail(f"master has {channels} channels; an alpha channel is not allowed")

    colours: dict[tuple[int, int, int], int] = {}
    for y in range(height):
        for x in range(width):
            value = pixel(rgb, width, x, y)
            colours[value] = colours.get(value, 0) + 1
    if len(colours) != 5:
        fail(f"master uses {len(colours)} inks, expected exactly 5: {sorted(colours)}")
    stray = set(colours) - TOKENS
    if stray:
        fail(f"master uses colours outside the token table: {sorted(stray)}")
    if set(colours) != palette:
        fail(f"master palette is {sorted(colours)}, expected {sorted(palette)}")

    # The left 4%: ground, band or flood only. The app paints its 6px lamp spine over it.
    left = {pixel(rgb, width, x, y) for x in range(LEFT_CLEAR) for y in range(height)}
    if left - GROUND:
        fail(f"left 4% is not clear of the form: {sorted(left - GROUND)}")

    # The form's centroid must sit inside the middle 84% so the 3:2 crop keeps it.
    xs = []
    for y in range(height):
        for x in range(width):
            if pixel(rgb, width, x, y) not in GROUND:
                xs.append(x)
    if not xs:
        fail("no form found")
    else:
        centroid = sum(xs) / len(xs)
        if not (0.08 * width <= centroid <= 0.92 * width):
            fail(f"form centroid x={centroid:.1f} is outside the middle 84%")

    # One lamp band, full bleed, at the imprint's fixed y.
    lamp_rows = [
        y for y in range(height) if all(pixel(rgb, width, x, y) == LAMP for x in range(width))
    ]
    if not lamp_rows:
        fail("no full-bleed lamp band")
    else:
        first, last = min(lamp_rows), max(lamp_rows)
        if first != BAND_TOP:
            fail(f"lamp band starts at y={first}, expected {BAND_TOP} (+/-2px)")
        if abs((last - first + 1) - BAND_HEIGHT) > 2:
            fail(f"lamp band is {last - first + 1}px tall, expected {BAND_HEIGHT}px (+/-2px)")
        share = BAND_HEIGHT / height
        if not 0.08 <= share <= 0.12:
            fail(f"lamp band is {share:.1%} of the frame height, expected 8-12%")

    flood_share = colours.get(LAMP_SOFT, 0) / (width * height)
    if flood_share > 0.45:
        fail(f"lamp-soft flood is {flood_share:.1%} of the frame, above the 45% budget")

    # The 3:2 file must be the mechanical centre crop, not a second drawing.
    crop_width, crop_height, crop_rgb, _ = read_png(crop_path)
    if (crop_width, crop_height) != (CROP_W, COVER_H):
        fail(f"crop is {crop_width}x{crop_height}, expected {CROP_W}x{COVER_H}")
    else:
        offset_x = (COVER_W - CROP_W) // 2
        mismatches = 0
        for y in range(COVER_H):
            for x in range(CROP_W):
                if pixel(crop_rgb, crop_width, x, y) != pixel(rgb, width, x + offset_x, y):
                    mismatches += 1
        if mismatches:
            fail(f"crop differs from the master's centre crop in {mismatches} pixels")


def main() -> int:
    import importlib.util
    import tempfile

    spec = importlib.util.spec_from_file_location(
        "h197_fallback_builder", ROOT / "bundled" / "packs" / "build_bundled_packs.py"
    )
    if spec is None or spec.loader is None:
        print("cannot load the demo pack builder")
        return 1
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    scratch = Path(tempfile.mkdtemp(prefix="coursebook-press-plate-"))
    global PACKS
    PACKS = scratch
    for kind, _slug, _palette in PLATES:
        folder = scratch / kind / "content"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "cover-16x9.png").write_bytes(builder.cover_plate_png(kind))
        (folder / "cover-3x2.png").write_bytes(builder.cover_crop_png(kind))

    failures: list[str] = []
    for kind, _slug, palette in PLATES:
        check_plate(kind, kind, palette, failures)
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"\n{len(failures)} acceptance failure(s)")
        return 1
    print("Press Plate acceptance: PASS")
    for kind, _slug, palette in PLATES:
        master = PACKS / kind / "content" / "cover-16x9.png"
        crop = PACKS / kind / "content" / "cover-3x2.png"
        print(
            f"  {kind:9s} {COVER_W}x{COVER_H} master {master.stat().st_size:>5d} B · "
            f"{CROP_W}x{COVER_H} crop {crop.stat().st_size:>5d} B · 5 inks "
            f"{sorted(f'#{r:02x}{g:02x}{b:02x}' for r, g, b in palette)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
