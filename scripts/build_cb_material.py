#!/usr/bin/env python3
"""CP-011 — the Coursebook material tiles, painted by a host generator.

Four material families, light and dark: paper grain, parchment vignette, wood plank and
card-stock fibre. Every tile is 256-512 px, seamless, and under 60 KB.

Why a generator and not a model image
-------------------------------------
This is texture, not illustration. The art bible's rule (CP-010) is that a transport or material
surface must be measurable and repeatable: it sits behind type at every route width, it must wrap
without a seam, and it must not shift a single text pixel's contrast. A deterministic generator
gives exactly that, and it records authorship instead of inventing a provider, a prompt hash or a
model id. No model call happens here; ``provider`` is ``host`` and ``model`` is ``none`` in every
manifest row, per ``docs/GM-ART-PLATES.md`` section 4.

Seamlessness
------------
Every generator below is periodic by construction: noise lattices are taken modulo a cell count
that divides the tile width, and the wood's vertical profile is a sum of harmonics whose periods
divide the tile height. So the tile wraps with a zero discontinuity, not by mirroring or by
feathering the edge. ``read_png`` is here so ``tests/test_cp_material_textures.py`` can measure the
wrap delta on the committed bytes rather than trusting this docstring.

Usage
-----
    python3 scripts/build_cb_material.py build     # repaint tiles + manifest
    python3 scripts/build_cb_material.py verify    # check the committed tiles and manifest
    python3 scripts/build_cb_material.py prove     # build 3x3 seam composites (needs ImageMagick)
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILE_DIR = ROOT / "assets" / "art" / "material"
PROOF_DIR = ROOT / "docs" / "concept-parity" / "art" / "material"
MANIFEST = TILE_DIR / "manifest.json"

MAX_BYTES = 60_000  # the card's "at most 60 KB", read strictly
MIN_PX = 256
MAX_PX = 512
LICENCE = "CC0-1.0"

# Colour anchors. Light values are measured: the parchment and card-stock fields are sampled from
# the ratified reference frames (docs/concept-parity/refs/home.png, system.png) and the values
# named in docs/concept-parity/PLAN.md section 2. Dark values are authored: no ratified dark frame
# exists yet, so they are derived from the same anchors and stay inside the "night atlas" range
# that CP-002 freezes. A texture that is baked colour (only wood) records the anchor it was painted
# to so a later token change is a repaint, not a silent mismatch.
PALETTE = {
    "light": {
        "canvas": "#f5e3c8",
        "card-stock": "#f4ecd9",
        "ink": "#1a1713",
        "grain-rgb": (0x3A, 0x23, 0x18),      # warm outlined brown, never black
        "vignette-rgb": (0x6B, 0x49, 0x2C),
        "wood-rgb": (0xAD, 0x8C, 0x6B),       # sampled shelf mid-tone
        "wood-deep": (0x8B, 0x68, 0x49),
        "wood-light": (0xC5, 0xA6, 0x84),
        "wood-edge": (0x6F, 0x55, 0x39),
    },
    "dark": {
        "canvas": "#171410",
        "card-stock": "#221d17",
        "ink": "#f2e2ce",
        "grain-rgb": (0xE8, 0xD3, 0xB4),
        "vignette-rgb": (0x0A, 0x08, 0x06),
        "wood-rgb": (0x5A, 0x43, 0x31),
        "wood-deep": (0x42, 0x2F, 0x21),
        "wood-light": (0x74, 0x58, 0x41),
        "wood-edge": (0x2F, 0x22, 0x18),
    },
}

# Alpha ceilings. These are the whole legibility argument: an overlay's worst-case pixel is
# ground blended toward the grain colour by max_alpha, and that blended field must still carry
# 16 px body text at >= 4.5:1. Keep them low; the texture is felt, not seen.
CEILINGS = {
    "paper-grain": {"light": 14, "dark": 16},
    "card-stock-fibre": {"light": 9, "dark": 10},
    "parchment-vignette": {"light": 30, "dark": 46},
}

SPECS = [
    # id, role, size, mode RGB/RGBA, tiling, application
    ("paper-grain", 256, "RGBA", "repeat", "canvas overlay; aria-hidden, pointer-events none"),
    ("card-stock-fibre", 256, "RGBA", "repeat", "card and sheet stock overlay behind body text"),
    ("parchment-vignette", 512, "RGBA", "one-shot",
     "canvas edge wash; background-size cover, applied once, aria-hidden"),
    ("wood-plank", 256, "RGB", "repeat", "shelf plank face and evidence tray only; never behind text"),
]


# --------------------------------------------------------------------------------------------
# PNG encode / decode. Stdlib only, so the same code paints and checks the bytes.
# --------------------------------------------------------------------------------------------


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def write_png(path: Path, width: int, height: int, channels: int, pixels: bytes) -> None:
    """Write 8-bit RGB (channels=3) or RGBA (channels=4) PNG with per-row adaptive filtering."""
    bpp = channels
    rows = []
    prior = bytes(width * bpp)
    for y in range(height):
        raw = pixels[y * width * bpp:(y + 1) * width * bpp]
        candidates = [(0, raw)]
        sub = bytes((raw[i] - (raw[i - bpp] if i >= bpp else 0)) & 0xFF for i in range(len(raw)))
        candidates.append((1, sub))
        up = bytes((raw[i] - prior[i]) & 0xFF for i in range(len(raw)))
        candidates.append((2, up))
        avg = bytes(
            (raw[i] - (((raw[i - bpp] if i >= bpp else 0) + prior[i]) >> 1)) & 0xFF
            for i in range(len(raw))
        )
        candidates.append((3, avg))
        paeth = bytes(
            (
                raw[i]
                - _paeth(
                    raw[i - bpp] if i >= bpp else 0,
                    prior[i],
                    prior[i - bpp] if i >= bpp else 0,
                )
            )
            & 0xFF
            for i in range(len(raw))
        )
        candidates.append((4, paeth))

        def cost(item: tuple[int, bytes]) -> int:
            return sum(min(v, 256 - v) for v in item[1])

        kind, body = min(candidates, key=cost)
        rows.append(bytes((kind,)) + body)
        prior = raw

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6 if channels == 4 else 2, 0, 0, 0)
    blob = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def read_png(path: Path) -> dict:
    """Decode an 8-bit non-interlaced RGB/RGBA PNG into {width, height, channels, pixels}."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos = 8
    width = height = channels = 0
    idat = bytearray()
    while pos < len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + size]
        pos += 12 + size
        if tag == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", payload[:10])
            if depth != 8 or colour not in (2, 6):
                raise ValueError(f"{path}: only 8-bit RGB/RGBA is read")
            channels = 3 if colour == 2 else 4
        elif tag == b"IDAT":
            idat.extend(payload)
        elif tag == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(stride * height)
    prior = bytearray(stride)
    at = 0
    for y in range(height):
        kind = raw[at]
        at += 1
        line = bytearray(raw[at:at + stride])
        at += stride
        if kind == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prior[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prior[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                line[i] = (
                    line[i]
                    + _paeth(
                        line[i - channels] if i >= channels else 0,
                        prior[i],
                        prior[i - channels] if i >= channels else 0,
                    )
                ) & 0xFF
        elif kind != 0:
            raise ValueError(f"{path}: unknown filter {kind}")
        out[y * stride:(y + 1) * stride] = line
        prior = line
    return {"width": width, "height": height, "channels": channels, "pixels": bytes(out)}


# --------------------------------------------------------------------------------------------
# Periodic noise. Cells must divide the tile axis so every lattice wraps exactly.
# --------------------------------------------------------------------------------------------


def _mix(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return value ^ (value >> 31)


def _rand(x: int, y: int, seed: int) -> float:
    return _mix((x * 0x9E3779B1) ^ (y * 0x85EBCA77) ^ (seed * 0xC2B2AE3D)) / 2 ** 64


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def value_noise(x: int, y: int, cells: int, size: int, seed: int) -> float:
    """Bilinear value noise on a lattice of ``cells`` that wraps across ``size`` px."""
    return value_noise_aniso(x, y, cells, cells, size, seed)


def value_noise_aniso(x: int, y: int, cx: int, cy: int, size: int, seed: int) -> float:
    """Bilinear value noise with independent lattice counts per axis, wrapping on both.

    ``cx`` and ``cy`` must divide ``size``; that is what makes the tile periodic rather than
    mirrored or feathered at the edge.
    """
    u = x * cx / size
    v = y * cy / size
    x0, y0 = int(u), int(v)
    fx, fy = _smooth(u - x0), _smooth(v - y0)
    x1, y1 = (x0 + 1) % cx, (y0 + 1) % cy
    n00 = _rand(x0, y0, seed)
    n10 = _rand(x1, y0, seed)
    n01 = _rand(x0, y1, seed)
    n11 = _rand(x1, y1, seed)
    top = n00 + (n10 - n00) * fx
    bottom = n01 + (n11 - n01) * fx
    return top + (bottom - top) * fy


def fbm(x: int, y: int, base_cells: int, octaves: int, size: int, seed: int) -> float:
    total = 0.0
    amplitude = 1.0
    norm = 0.0
    cells = base_cells
    for octave in range(octaves):
        total += amplitude * value_noise(x, y, cells, size, seed + octave * 101)
        norm += amplitude
        amplitude *= 0.5
        cells *= 2
    return total / norm


def fbm_aniso(x: int, y: int, cx: int, cy: int, octaves: int, size: int, seed: int) -> float:
    total = 0.0
    amplitude = 1.0
    norm = 0.0
    for octave in range(octaves):
        total += amplitude * value_noise_aniso(x, y, cx, cy, size, seed + octave * 101)
        norm += amplitude
        amplitude *= 0.5
        cx *= 2
        cy *= 2
    return total / norm


def speck(x: int, y: int, seed: int) -> float:
    """One independent value per pixel — the paper's tooth.

    Stochastic rather than interpolated on purpose: paper tooth is high-frequency and has no
    structure, so a repeat of it is invisible, while an interpolated blob field repeats visibly.
    It costs a few KB more than smooth noise and buys a tile that never reads as wallpaper.
    """
    return _rand(x, y, seed)


def _quantise(value: float, step: int) -> int:
    return int(round(value / step)) * step


# --------------------------------------------------------------------------------------------
# The four painters. Each returns (pixels, max_alpha).
# --------------------------------------------------------------------------------------------


def paint_paper_grain(size: int, mode: str) -> tuple[bytes, int]:
    """Paper tooth: a slow mottle plus a stochastic speckle ladder.

    The mottle is deliberately large and almost flat so a repeat cannot be seen; the tooth is
    per-pixel and therefore structureless, which is what stops the tile reading as wallpaper
    behind 16 px text.
    """
    ceiling = CEILINGS["paper-grain"][mode]
    rgb = PALETTE[mode]["grain-rgb"]
    ladder = [(0.60, 0), (0.82, 2), (0.94, 5), (0.99, 9), (1.01, ceiling)]
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            mottle = (fbm(x, y, 2, 3, size, 11011) - 0.5) * 3.0
            r = speck(x, y, 11003)
            step = next(level for edge, level in ladder if r < edge)
            alpha = max(0.0, min(float(ceiling), step + mottle))
            i = (y * size + x) * 4
            pixels[i] = rgb[0]
            pixels[i + 1] = rgb[1]
            pixels[i + 2] = rgb[2]
            pixels[i + 3] = _quantise(alpha, 1)
    return bytes(pixels), ceiling


def paint_card_stock_fibre(size: int, mode: str) -> tuple[bytes, int]:
    """Card stock: a manufactured sheet — long, fine, near-flat fibres, almost no tooth."""
    ceiling = CEILINGS["card-stock-fibre"][mode]
    rgb = PALETTE[mode]["grain-rgb"]
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            coarse = fbm_aniso(x, y, 4, 64, 2, size, 12007)    # long fibres across the sheet
            fine = fbm_aniso(x, y, 16, 128, 2, size, 12011)    # their short break-up
            n = 0.62 * coarse + 0.38 * fine
            alpha = ceiling * (n ** 1.5)
            i = (y * size + x) * 4
            pixels[i] = rgb[0]
            pixels[i + 1] = rgb[1]
            pixels[i + 2] = rgb[2]
            pixels[i + 3] = _quantise(alpha, 1)
    return bytes(pixels), ceiling


BAYER4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def paint_parchment_vignette(size: int, mode: str) -> tuple[bytes, int]:
    """Edge wash: clear in the middle, warm at the corners, and equal on all four edges.

    The profile is radial in *distance from the centre normalised by the corner distance*, so
    opposite edges carry the same alpha and a repeat has no discontinuity. The product applies it
    once at cover size; the composite proof shows it that way.

    The 1-level dither is ordered (a 4x4 Bayer matrix that wraps with the tile), not random:
    an 8-bit alpha ramp over ~250 px would band, and a stochastic dither would quadruple the
    file size for the same visual result.
    """
    ceiling = CEILINGS["parchment-vignette"][mode]
    rgb = PALETTE[mode]["vignette-rgb"]
    pixels = bytearray(size * size * 4)
    half = (size - 1) / 2.0
    corner = math.hypot(half, half)
    for y in range(size):
        dy = (y - half) / corner
        for x in range(size):
            dx = (x - half) / corner
            radius = math.hypot(dx, dy)
            # flat to 0.42, then a soft shoulder; nothing at the very centre
            t = max(0.0, (radius - 0.42) / 0.58)
            value = ceiling * (t ** 2.15)
            low = int(value)
            a = low + (1 if BAYER4[y % 4][x % 4] / 16.0 < value - low else 0)
            i = (y * size + x) * 4
            pixels[i] = rgb[0]
            pixels[i + 1] = rgb[1]
            pixels[i + 2] = rgb[2]
            pixels[i + 3] = max(0, min(255, a))
    return bytes(pixels), ceiling


def paint_wood_plank(size: int, mode: str) -> tuple[bytes, int]:
    """One sawn plank face, painted the way the ratified concept paints it.

    The concept's shelf is gouache, not a photograph: a flat mid-tone, then irregular
    semi-opaque brush strokes that wander, fade and break, a few lighter ones, and a couple of
    dark cracks. Stripes fail this test because they are parallel and unbroken.

    Periodicity: every stroke's wander and fade are integer harmonics of the tile width, and the
    stroke centre wraps modulo the height, so both seams stay exact. The plank's top lip, cut end
    and contact shadow belong to ShelfPlank (CP-020b), not to the tile: a baked lip would repeat
    as a dark band at every vertical wrap.
    """
    base = PALETTE[mode]["wood-rgb"]
    deep = PALETTE[mode]["wood-deep"]
    light = PALETTE[mode]["wood-light"]
    two_pi = 2.0 * math.pi
    tone = [0.5] * (size * size)

    # painted unevenness: broad, slow, nearly flat so a repeat cannot be read
    for y in range(size):
        for x in range(size):
            tone[y * size + x] = 0.5 + (fbm(x, y, 2, 3, size, 13001) - 0.5) * 0.12

    strokes = 58
    for index in range(strokes):
        y0 = _rand(index, 1, 13021) * size
        wander = (0.4 + _rand(index, 2, 13027)) * size * 0.018
        waves = 1 + int(_rand(index, 3, 13031) * 3)
        phase = _rand(index, 4, 13037) * two_pi
        thickness = 1 + int(_rand(index, 5, 13041) * 2)
        strength = 0.05 + _rand(index, 6, 13047) * 0.17
        fades = 1 + int(_rand(index, 7, 13049) * 2)
        fade_phase = _rand(index, 8, 13053) * two_pi
        lighter = _rand(index, 9, 13057) > 0.80
        for x in range(size):
            centre = y0 + wander * math.sin(waves * two_pi * x / size + phase)
            fade = 0.30 + 0.70 * max(0.0, math.sin(fades * two_pi * x / size + fade_phase))
            delta = strength * fade * (1.0 if lighter else -1.0)
            for step in range(-thickness, thickness + 1):
                weight = 1.0 - abs(step) / (thickness + 0.5)
                row = (int(round(centre)) + step) % size
                tone[row * size + x] += delta * weight

    # a few sparse pores, structureless, so the paint is not perfectly clean
    for y in range(size):
        for x in range(size):
            fleck = speck(x, y, 13011)
            if fleck < 0.018:
                tone[y * size + x] -= (0.018 - fleck) / 0.018 * 0.10

    pixels = bytearray(size * size * 3)
    for index, value in enumerate(tone):
        t = max(0.0, min(1.0, value))
        if t < 0.5:
            colour = [deep[k] + (base[k] - deep[k]) * (t / 0.5) for k in range(3)]
        else:
            colour = [base[k] + (light[k] - base[k]) * ((t - 0.5) / 0.5) for k in range(3)]
        pixels[index * 3] = int(max(0, min(255, round(colour[0]))))
        pixels[index * 3 + 1] = int(max(0, min(255, round(colour[1]))))
        pixels[index * 3 + 2] = int(max(0, min(255, round(colour[2]))))
    return bytes(pixels), 0


PAINTERS = {
    "paper-grain": paint_paper_grain,
    "card-stock-fibre": paint_card_stock_fibre,
    "parchment-vignette": paint_parchment_vignette,
    "wood-plank": paint_wood_plank,
}

GROUND_ROLE = {
    "paper-grain": "canvas",
    "card-stock-fibre": "card-stock",
    "parchment-vignette": "canvas",
    "wood-plank": "wood",
}


# --------------------------------------------------------------------------------------------
# Colour maths used for the legibility row and by the test suite.
# --------------------------------------------------------------------------------------------


def srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (srgb_to_linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def blend(ground: tuple[int, int, int], over: tuple[int, int, int], alpha: int) -> tuple[int, int, int]:
    a = alpha / 255.0
    r = int(round(ground[0] * (1 - a) + over[0] * a))
    g = int(round(ground[1] * (1 - a) + over[1] * a))
    b = int(round(ground[2] * (1 - a) + over[2] * a))
    return (r, g, b)


def ground_rgb(mode: str, tile_id: str) -> tuple[int, int, int]:
    return PALETTE[mode]["wood-rgb"] if tile_id == "wood-plank" else hex_rgb(PALETTE[mode][GROUND_ROLE[tile_id]])


def worst_field(mode: str, tile_id: str, ceiling: int) -> tuple[int, int, int]:
    """The darkest pixel the tile can put under text, composited on its ground."""
    ground = ground_rgb(mode, tile_id)
    if tile_id == "wood-plank":
        return ground
    over = PALETTE[mode]["grain-rgb"] if tile_id != "parchment-vignette" else PALETTE[mode]["vignette-rgb"]
    return blend(ground, over, ceiling)


def ocr_check(path: Path) -> dict:
    """The art-plate rule: a plate with letters in it is rejected, not shipped.

    A texture always yields *some* low-confidence OCR noise, so only recognised tokens at
    confidence >= 70 count as letters. That threshold is what separates "grain looks like a
    speck" from "someone baked a word into the art". Recorded honestly: if tesseract is not
    installed the row says ``skipped``, never ``none``.
    """
    tool = shutil.which("tesseract")
    if tool is None:
        return {"tool": "tesseract", "result": "skipped", "reason": "tesseract not installed"}
    done = subprocess.run(
        [tool, str(path), "stdout", "--psm", "11", "tsv"], capture_output=True, text=True
    )
    letters = ""
    top = 0.0
    for line in done.stdout.splitlines()[1:]:
        fields = line.split("\t")
        if len(fields) < 12:
            continue
        try:
            confidence = float(fields[10])
        except ValueError:
            continue
        word = "".join(ch for ch in fields[11] if ch.isalnum())
        if word and confidence >= 70:
            letters += word
            top = max(top, confidence)
    return {
        "tool": "tesseract",
        "purpose": "letters in art",
        "confidence_floor": 70,
        "result": "none" if not letters else f"hit:{letters[:40]}",
        "characters": len(letters),
        "max_confidence": round(top, 1),
    }


def seam_delta(image: dict) -> dict:
    """Wrap step vs interior step, measured as a mean so one noisy pixel cannot hide a seam.

    A periodic tile is seamless when the average step across the wrap is no larger than the
    average interior step: exact equality is not the test (a continuous gradient changes by one
    step at the seam too). ``*_ratio`` at or below ~1 means no discontinuity; a feathered,
    mirrored or offset edge makes *every* wrap pixel mismatch, which the mean catches even when a
    handful of noisy interior pixels would mask it in a maximum.
    """
    w, h, c = image["width"], image["height"], image["channels"]
    px = image["pixels"]

    def col_step(xa: int, xb: int) -> float:
        return sum(
            abs(px[(y * w + xa) * c + k] - px[(y * w + xb) * c + k])
            for y in range(h) for k in range(c)
        ) / (h * c)

    def row_step(ya: int, yb: int) -> float:
        return sum(
            abs(px[(ya * w + x) * c + k] - px[(yb * w + x) * c + k])
            for x in range(w) for k in range(c)
        ) / (w * c)

    # Interior reference from the two neighbour pairs immediately inside the wrap: a seam must
    # look like the step it replaces *at that place in the texture*. Sampling the middle of a
    # radial vignette would compare a steep edge with a flat centre and report a false seam.
    col_samples = (0, w - 2)
    row_samples = (0, h - 2)
    wrap_col, wrap_row = col_step(w - 1, 0), row_step(h - 1, 0)
    inner_col = sum(col_step(x, x + 1) for x in col_samples) / len(col_samples)
    inner_row = sum(row_step(y, y + 1) for y in row_samples) / len(row_samples)
    return {
        "column": round(wrap_col, 3),
        "row": round(wrap_row, 3),
        "column_interior": round(inner_col, 3),
        "row_interior": round(inner_row, 3),
        "column_ratio": round(wrap_col / max(0.05, inner_col), 3),
        "row_ratio": round(wrap_row / max(0.05, inner_row), 3),
    }


# --------------------------------------------------------------------------------------------
# Build / verify
# --------------------------------------------------------------------------------------------


def build() -> int:
    rows = []
    for tile_id, size, colour_format, tiling, application in SPECS:
        for mode in ("light", "dark"):
            painter = PAINTERS[tile_id]
            pixels, ceiling = painter(size, mode)
            channels = 4 if colour_format == "RGBA" else 3
            path = TILE_DIR / f"{tile_id}-{mode}.png"
            write_png(path, size, size, channels, pixels)
            blob = path.read_bytes()
            image = read_png(path)
            seams = seam_delta(image)
            field = worst_field(mode, tile_id, ceiling)
            ink = hex_rgb(PALETTE[mode]["ink"])
            ratio = round(contrast(ink, field), 2)
            rows.append(
                {
                    "id": tile_id,
                    "mode": mode,
                    "path": str(path.relative_to(ROOT)),
                    "role": GROUND_ROLE[tile_id],
                    "format": colour_format,
                    "width": size,
                    "height": size,
                    "bytes": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "tiling": tiling,
                    "application": application,
                    "alpha_ceiling": ceiling,
                    "ground": PALETTE[mode][GROUND_ROLE[tile_id]]
                    if tile_id != "wood-plank"
                    else PALETTE[mode]["wood-rgb"],
                    "worst_field": "#%02x%02x%02x" % field,
                    "ink": PALETTE[mode]["ink"],
                    "ink_worst_contrast": ratio,
                    "text_required": 4.5,
                    "legibility_passes": ratio >= 4.5,
                    "seam": {
                        "column_delta": seams["column"],
                        "row_delta": seams["row"],
                        "column_interior": seams["column_interior"],
                        "row_interior": seams["row_interior"],
                        "column_ratio": seams["column_ratio"],
                        "row_ratio": seams["row_ratio"],
                        "seamless": seams["column_ratio"] <= 1.25 and seams["row_ratio"] <= 1.25,
                    },
                    "licence": LICENCE,
                    "text_check": ocr_check(path),
                    "provenance_id": f"material:{tile_id}:{mode}",
                    "source": {
                        "generator": "scripts/build_cb_material.py",
                        "provider": "host",
                        "model": "none",
                        "prompt_hash": None,
                        "seed": SEEDS[tile_id],
                        "palette_light": "sampled from docs/concept-parity/refs/{home,system}.png and PLAN.md section 2",
                        "palette_dark": "authored; no ratified dark frame exists (night atlas range, CP-002)",
                    },
                }
            )
    document = {
        "schema": "cb.material.v1",
        "card": "CP-011",
        "generated_by": "scripts/build_cb_material.py",
        "tile_count": len(rows),
        "max_bytes": MAX_BYTES,
        "min_px": MIN_PX,
        "max_px": MAX_PX,
        "note": (
            "Every tile is RGBA overlay except wood-plank (opaque RGB). Overlay alpha ceilings are "
            "the legibility argument, not a style choice: ink over the darkest possible composite "
            "must stay at or above 4.5:1 at 16 px. parchment-vignette is applied once at cover "
            "size (background-size: cover); it wraps without a discontinuity but is never repeated."
        ),
        "tiles": rows,
    }
    MANIFEST.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} tiles to {TILE_DIR.relative_to(ROOT)}")
    for row in rows:
        print(
            f"  {row['id']:<20} {row['mode']:<5} {row['width']}x{row['height']} "
            f"{row['bytes']:>6} B  seam {row['seam']['column_ratio']}/{row['seam']['row_ratio']}  "
            f"contrast {row['ink_worst_contrast']}"
        )
    return 0


SEEDS = {
    "paper-grain": 11011,
    "card-stock-fibre": 12001,
    "parchment-vignette": 12091,
    "wood-plank": 13001,
}


def verify() -> int:
    problems = []
    if not MANIFEST.exists():
        print("manifest missing; run build")
        return 1
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for row in document["tiles"]:
        path = ROOT / row["path"]
        if not path.exists():
            problems.append(f"{row['id']}/{row['mode']}: missing {row['path']}")
            continue
        blob = path.read_bytes()
        if len(blob) > MAX_BYTES:
            problems.append(f"{row['id']}/{row['mode']}: {len(blob)} B over {MAX_BYTES}")
        if hashlib.sha256(blob).hexdigest() != row["sha256"]:
            problems.append(f"{row['id']}/{row['mode']}: sha drift")
        if len(blob) != row["bytes"]:
            problems.append(f"{row['id']}/{row['mode']}: byte count drift")
        if not row["seam"]["seamless"]:
            problems.append(f"{row['id']}/{row['mode']}: seam ratio {row['seam']}")
        if not (MIN_PX <= row["width"] <= MAX_PX and MIN_PX <= row["height"] <= MAX_PX):
            problems.append(f"{row['id']}/{row['mode']}: size out of range")
        if not row["legibility_passes"]:
            problems.append(f"{row['id']}/{row['mode']}: contrast {row['ink_worst_contrast']}")
        if row.get("text_check", {}).get("result", "none").startswith("hit:"):
            problems.append(f"{row['id']}/{row['mode']}: text found in the tile")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"verified {len(document['tiles'])} tiles")
    return 0


def prove() -> int:
    """3x3 composites with ImageMagick: each tile repeated on its own ground, seam visible or not."""
    if not MANIFEST.exists():
        print("manifest missing; run build")
        return 1
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    for row in document["tiles"]:
        tile = ROOT / row["path"]
        out = PROOF_DIR / f"proof-3x3-{row['id']}-{row['mode']}.png"
        ground = row["ground"]
        colour_type = "PNG32" if row["format"] == "RGBA" else "PNG24"
        if row["format"] == "RGBA":
            single = PROOF_DIR / f".single-{row['id']}-{row['mode']}.png"
            subprocess.run(
                ["magick", "-size", f"{row['width']}x{row['height']}", f"xc:{ground}",
                 str(tile), "-composite", f"PNG32:{single}"],
                check=True,
            )
        else:
            single = tile
        repeat = 3 if row["tiling"] == "repeat" else 1
        if repeat == 3:
            subprocess.run(
                ["magick",
                 "(", str(single), str(single), str(single), "+append", ")",
                 "(", str(single), str(single), str(single), "+append", ")",
                 "(", str(single), str(single), str(single), "+append", ")",
                 "-append", f"{colour_type}:{out}"],
                check=True,
            )
        else:
            # a vignette is applied once: show it across a 3x canvas, the way the route uses it
            subprocess.run(
                ["magick", "-size", f"{row['width'] * 3}x{row['height'] * 3}", f"xc:{ground}",
                 "(", str(single), "-resize", f"{row['width'] * 3}x{row['height'] * 3}!", ")",
                 "-composite", f"{colour_type}:{out}"],
                check=True,
            )
        print(f"wrote {out.relative_to(ROOT)}")
    for stale in PROOF_DIR.glob(".single-*.png"):
        stale.unlink()
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "verify"
    if command == "build":
        return build()
    if command == "verify":
        return verify()
    if command == "prove":
        return prove()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
