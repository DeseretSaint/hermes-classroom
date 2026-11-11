#!/usr/bin/env python3
"""Build the Coursebook brand-asset segment: fonts, material tiles, fox poses, object kit.

Inputs are the approved masters under ``assets/masters/``, the painted object kit under
``assets/art/objects/``, the owner-signed painted fox exports under ``assets/art/fox/``, plus the two
pinned upstream font masters. Outputs are the shipped files under ``assets/{fonts,material,fox,objects}/``, their
``manifest.json`` rows, and the single frozen ``CB_ASSETS`` object in
``desktop/cb-assets.generated.js``.

The build is deterministic: the same masters and the same tool versions produce byte-identical
output twice. Two things make that true and both are load-bearing:

* ``fontTools.subset`` runs with ``recalc_timestamp=False`` and every head.created/modified is
  pinned to 0 before the WOFF2 compile, so no build clock leaks into the bytes;
* Pillow encoders are called with explicit, fixed parameters and no metadata, so no encoder
  default or timestamp wanders between runs.

Size budgets are the tests' job (``tests/test_cb_assets.py``); this script prints the report and
``--check`` turns an over-budget build into a non-zero exit.

Usage
-----
    uv venv --python 3.12 .venv-cb-assets
    uv pip install --python .venv-cb-assets/bin/python "fonttools[woff]==4.59.2" "brotli==1.1.0"
    .venv-cb-assets/bin/python scripts/build_cb_assets.py            # build
    .venv-cb-assets/bin/python scripts/build_cb_assets.py --check    # build + budgets
    .venv-cb-assets/bin/python scripts/build_cb_assets.py --write-masters  # re-draw the art

The system Python has no fontTools, so the script re-executes itself inside the private venv when
it finds one; it never installs into the system interpreter.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MASTERS = ASSETS / "masters"
#: CP-013's painted object masters (card-owned art). Not embedded; the shipped assets/objects/*
#: files are encodes of these.
ART_OBJECTS = ASSETS / "art" / "objects"
#: CP-010's owner-signed painted fox exports (660x660 RGBA masters plus 512/256/128/64 PNG
#: exports). Not embedded; the shipped assets/fox/*.webp files are encodes of the per-size PNGs.
#: The procedural SVG set under assets/masters/fox/ stays on disk for rollback and is no longer
#: read by this build.
ART_FOX = ASSETS / "art" / "fox"
#: VQ-002's owner-approved display-plate kit (`field_atlas@2`). The kit is the source of truth for
#: its own hashes: this build never re-derives art, it encodes the curated plates and records the
#: kit's declaration beside each row so a drifted plate fails the build instead of shipping.
KIT = ASSETS / "visual-kits" / "field_atlas"
KIT_JSON = KIT / "kit.json"
#: Where the embedded encodes live. ``assets/kit/`` is a shipped group like the fox's.
KIT_EMBED = ASSETS / "kit"
#: The two full-plate roles carry a 2x provider source; the six covers are already 2x of the render.
KIT_FULL_ROLES = (("hero", 72), ("lesson_scene", 72))
KIT_COVER_QUALITY = 80
GENERATED = ROOT / "desktop" / "cb-assets.generated.js"
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
VENV = ROOT / ".venv-cb-assets"

SEGMENT_BUDGET = 2_500_000
ASSET_BUDGET = 300_000
PLUGIN_BUDGET = 4_500_000

FOX_POSES = ("wave", "point", "clock", "read", "cheer", "think", "sleep")
#: The four painted export sizes under assets/art/fox/. Every pose ships all four: the primitive
#: picks 512 at >=416 px, 256 at >=208, 128 at >=128 and 64 below that.
FOX_EXPORTS = (512, 256, 128, 64)
OBJECTS = (
    "clock",
    "tag",
    "stamp-rim",
    "medallion-rim",
    "passport-tray",
    "ticket",
    "shelf-plank",
)

INK = "#3a2318"
FUR = "#c4643f"
FUR_DARK = "#9d4527"
CREAM = "#f4e7cf"
BRASS = "#c9a227"
BRASS_DARK = "#8a6d14"
SAGE = "#7d8c6a"
PARCHMENT = "#efe3c9"

# Latin plus punctuation, exactly the subset the contract names. Latin-1 covers accented names;
# General Punctuation covers the dashes, quotes and ellipsis the copy deck actually uses.
FONT_CODEPOINTS = (
    list(range(0x20, 0x7F))
    + list(range(0xA0, 0x100))
    + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x00B7, 0x00D7, 0x00B0]
)

FONT_SOURCES = {
    "display": {
        "master": "assets/masters/fonts/Fraunces-VF.ttf",
        "family": "CB Display",
        "upstream_family": "Fraunces",
        "source": (
            "google/fonts@5bb28733cec313b63fbd415b574b5ae35c8aa8b8 "
            "ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf"
        ),
        "licence": "OFL-1.1",
        "licence_file": "assets/fonts/licenses/OFL-Fraunces.txt",
        "postscript": "CBDisplay-Roman",
        "rfn": False,
    },
    "ui": {
        "master": "assets/masters/fonts/SourceSans3-VF.ttf",
        "family": "CB UI",
        "upstream_family": "Source Sans 3",
        "source": (
            "google/fonts@5bb28733cec313b63fbd415b574b5ae35c8aa8b8 "
            "ofl/sourcesans3/SourceSans3[wght].ttf"
        ),
        "licence": "OFL-1.1",
        "licence_file": "assets/fonts/licenses/OFL-SourceSans3.txt",
        "postscript": "CBUI-Roman",
        # Source Sans 3's OFL declares Reserved Font Name 'Source'. Subsetting is a Modified
        # Version, so the shipped family name must not be the reserved name. We rename to CB UI
        # and keep the copyright line and the licence text verbatim.
        "rfn": True,
    },
}


# --------------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def data_url(mime: str, data: bytes) -> str:
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))


def ensure_venv() -> None:
    """Re-exec inside the private venv when the running interpreter cannot import fontTools.

    An inherited ``PYTHONPATH`` can shadow this venv's site-packages (a host-managed Python on the
    path makes ``PIL`` resolve to an incompatible build). The private venv is the whole point of the
    isolation, so an inherited path is dropped once, before the interpreter goes looking for a
    module: the build then either runs clean or fails with the honest missing-module message.
    """
    if os.environ.get("PYTHONPATH") and not os.environ.get("CB_ASSETS_CLEAN_ENV"):
        env = dict(os.environ, CB_ASSETS_CLEAN_ENV="1")
        env.pop("PYTHONPATH", None)
        os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], env)
    try:
        import fontTools  # noqa: F401
    except ImportError:
        candidate = VENV / "bin" / "python"
        if candidate.exists() and Path(sys.executable).resolve() != candidate.resolve():
            os.execv(str(candidate), [str(candidate), str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.exit(
            "fontTools is missing. Create the private venv first:\n"
            "  uv venv --python 3.12 .venv-cb-assets\n"
            '  uv pip install --python .venv-cb-assets/bin/python "fonttools[woff]==4.59.2" "brotli==1.1.0"'
        )


def contract_material_files() -> list[str]:
    data = json.loads(CONTRACT.read_text())
    files = []
    for row in data["materials"].values():
        if not isinstance(row, dict) or "light" not in row:
            continue
        for mode in ("light", "dark"):
            files.append(row[mode]["file"])
    return files


# --------------------------------------------------------------------------------------------
# masters: material tiles
# --------------------------------------------------------------------------------------------


def _value_noise(width: int, height: int, cells: int, seed: int) -> "object":
    """Tileable value noise: a low-res lattice wrapped by tiling, then bicubic upsampled."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    lattice = rng.random((cells, cells)).astype("float32")
    tiled = np.tile(lattice, (3, 3))
    img = Image.fromarray((tiled * 255).astype("uint8"), mode="L")
    big = img.resize(
        (cells * 3 * (width // cells), cells * 3 * (height // cells)), Image.Resampling.BICUBIC
    )
    left = big.width // 3
    top = big.height // 3
    crop = big.crop((left, top, left + width, top + height))
    return np.asarray(crop).astype("float32") / 255.0


def _tint(gray: "object", base: tuple[int, int, int], spread: float) -> "object":
    import numpy as np

    arr = np.zeros(gray.shape + (3,), dtype="float32")
    for i, channel in enumerate(base):
        arr[..., i] = channel * (1.0 - spread) + channel * spread * (0.55 + 0.9 * gray)
    return np.clip(arr, 0, 255).astype("uint8")


def material_master_bytes(name: str) -> bytes:
    """Draw one seamless 192x192 master tile. Pure functions of (name, fixed seeds)."""
    import numpy as np
    from PIL import Image

    w = h = 192
    if name == "grain-paper":
        noise = 0.55 * _value_noise(w, h, 12, 11) + 0.45 * _value_noise(w, h, 48, 12)
        arr = _tint(noise, (238, 226, 203), 0.16)
    elif name == "grain-night":
        noise = 0.55 * _value_noise(w, h, 12, 21) + 0.45 * _value_noise(w, h, 48, 22)
        arr = _tint(noise, (26, 22, 17), 0.45)
    elif name in ("vignette-parchment", "vignette-night"):
        yy, xx = np.mgrid[0:h, 0:w].astype("float32")
        # periodic in x and y, so the four edges match when the tile repeats 3x3
        radial = (np.cos(2 * np.pi * xx / w) + np.cos(2 * np.pi * yy / h)) / 2.0
        fall = np.clip((0.5 - 0.5 * radial) ** 1.6, 0, 1)
        noise = _value_noise(w, h, 24, 31 if name.endswith("parchment") else 32)
        base = (231, 214, 184) if name.endswith("parchment") else (18, 15, 11)
        arr = np.zeros((h, w, 3), dtype="float32")
        for i, channel in enumerate(base):
            arr[..., i] = channel * (1.0 - 0.45 * fall - 0.05 * noise)
        arr = np.clip(arr, 0, 255).astype("uint8")
    elif name in ("wood-plank", "wood-plank-night"):
        yy, xx = np.mgrid[0:h, 0:w].astype("float32")
        grain = (
            np.sin(2 * np.pi * (xx / w) * 5 + 1.7 * np.sin(2 * np.pi * yy / h))
            * 0.5
            + np.sin(2 * np.pi * (xx / w) * 17 + 0.8 * np.sin(2 * np.pi * yy / h * 3))
            * 0.28
            + _value_noise(w, h, 32, 41 if name.endswith("plank") else 42) * 0.5
            + 0.5
        ) / 1.6
        base = (150, 104, 62) if name.endswith("plank") else (86, 58, 35)
        arr = _tint(np.clip(grain, 0, 1), base, 0.42)
    else:
        raise SystemExit("unknown material master: %s" % name)

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------------------------
# masters: vector art (SVG)
# --------------------------------------------------------------------------------------------


def _fox_svg(pose: str) -> str:
    """One flat, textless fox in the Field Atlas palette; ink line, cream bib, dark socks."""
    # Shared body. The figure is drawn in a 512 square; the ink line is 9 units so it stays
    # visible at the 64 px export without turning into a black blob.
    body = f"""
  <path d="M150 470 C120 420 128 352 168 316 C205 282 262 270 300 292 C342 316 356 372 344 420
           C334 462 300 484 258 486 C214 488 172 486 150 470 Z" fill="{FUR}"/>
  <path d="M206 486 C206 452 214 424 238 408 C258 394 282 396 296 410 C312 426 314 458 310 486 Z"
        fill="{CREAM}"/>
  <path d="M196 470 C182 486 170 494 158 498 L206 500 Z" fill="{INK}"/>
  <path d="M300 470 C314 486 326 494 338 498 L290 500 Z" fill="{INK}"/>
"""
    tail = f"""
  <path d="M352 396 C406 372 442 330 448 282 C452 248 440 226 424 220 C438 250 428 288 396 314
           C376 330 358 340 344 348 Z" fill="{FUR}"/>
  <path d="M424 220 C438 250 428 288 396 314 C412 300 432 292 446 296 C452 268 446 236 424 220 Z"
        fill="{CREAM}"/>
"""
    eyes = "" if pose == "sleep" else (
        f'<circle cx="240" cy="266" r="9" fill="{INK}"/>'
        f'<circle cx="290" cy="266" r="9" fill="{INK}"/>'
    )
    head = f"""
  <path d="M258 208 C300 208 332 236 336 276 C340 318 314 350 276 354 C238 358 208 332 204 292
           C200 252 220 214 258 208 Z" fill="{FUR}"/>
  <path d="M222 220 L212 168 L252 196 Z" fill="{FUR_DARK}"/>
  <path d="M300 216 L322 168 L330 210 Z" fill="{FUR_DARK}"/>
  <path d="M240 300 C262 288 290 288 310 300 C300 330 278 342 258 340 C244 338 236 322 240 300 Z"
        fill="{CREAM}"/>
  {eyes}
  <path d="M262 300 L276 300 L269 310 Z" fill="{INK}"/>
"""
    clock = f"""
  <g>
    <circle cx="338" cy="452" r="46" fill="{BRASS}" stroke="{INK}" stroke-width="8"/>
    <circle cx="338" cy="452" r="34" fill="{PARCHMENT}"/>
    <path d="M338 452 L338 428 M338 452 L356 442" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>
    <path d="M316 410 L306 396 M360 410 L370 396" stroke="{BRASS_DARK}" stroke-width="10" stroke-linecap="round"/>
    <path d="M312 400 C326 388 350 388 364 400" fill="none" stroke="{INK}" stroke-width="7"/>
  </g>
"""
    book = f"""
  <g>
    <path d="M362 430 L452 442 L452 490 L362 480 Z" fill="{CREAM}" stroke="{INK}" stroke-width="7"/>
    <path d="M362 430 L286 448 L286 496 L362 480 Z" fill="{PARCHMENT}" stroke="{INK}" stroke-width="7"/>
    <path d="M362 432 L362 482" stroke="{INK}" stroke-width="7"/>
    <path d="M300 462 L350 454 M300 476 L350 468 M374 456 L436 462 M374 470 L436 476"
          stroke="{SAGE}" stroke-width="4" stroke-linecap="round"/>
  </g>
"""
    tag = f"""
  <g>
    <path d="M300 424 L372 404 L392 452 L320 474 Z" fill="{CREAM}" stroke="{INK}" stroke-width="7"/>
    <circle cx="368" cy="416" r="7" fill="{PARCHMENT}" stroke="{INK}" stroke-width="5"/>
  </g>
"""
    arms = {
        "wave": f'<path d="M196 360 C176 330 176 296 188 268" fill="none" stroke="{FUR}" stroke-width="26" stroke-linecap="round"/>'
        f'<path d="M188 268 C184 250 190 238 200 232" fill="none" stroke="{FUR_DARK}" stroke-width="18" stroke-linecap="round"/>',
        "point": f'<path d="M330 352 C368 344 392 326 404 300" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>'
        f'<path d="M404 300 L428 288" stroke="{FUR_DARK}" stroke-width="14" stroke-linecap="round"/>',
        "clock": f'<path d="M320 372 C344 392 352 414 348 432" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>',
        "read": f'<path d="M310 374 C330 392 342 408 348 422" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>'
        f'<path d="M212 382 C232 400 246 412 254 424" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>',
        "cheer": f'<path d="M192 352 C170 322 166 292 174 268" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>'
        f'<path d="M336 352 C358 322 362 292 354 268" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>',
        "think": f'<path d="M316 372 C338 382 348 396 344 410" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>'
        f'<circle cx="330" cy="326" r="18" fill="{FUR_DARK}"/>',
        "sleep": f'<path d="M306 386 C330 400 344 416 344 434" fill="none" stroke="{FUR}" stroke-width="24" stroke-linecap="round"/>',
    }[pose]
    face_extras = ""
    if pose == "sleep":
        face_extras = (
            f'<path d="M228 266 C236 272 246 272 254 266" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M278 266 C286 272 296 272 304 266" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
        )
    accessory = {"clock": clock, "read": book, "wave": tag}.get(pose, "")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <g stroke="{INK}" stroke-width="9" stroke-linejoin="round">{tail}{body}{head}{arms}{accessory}</g>
  {face_extras}
</svg>
"""


def _object_svg(name: str) -> str:
    common = f'stroke="{INK}" stroke-width="8" stroke-linejoin="round"'
    art = {
        "clock": f"""
  <circle cx="128" cy="132" r="84" fill="{BRASS}" {common}/>
  <circle cx="128" cy="132" r="62" fill="{PARCHMENT}"/>
  <path d="M128 132 L128 88 M128 132 L162 146" stroke="{INK}" stroke-width="9" stroke-linecap="round"/>
  <path d="M78 66 L64 40 M178 66 L192 40" stroke="{BRASS_DARK}" stroke-width="14" stroke-linecap="round"/>
  <path d="M72 56 C104 32 152 32 184 56" fill="none" {common}/>
""",
        "tag": f"""
  <path d="M46 84 L200 48 L222 142 L68 178 Z" fill="{CREAM}" {common}/>
  <circle cx="196" cy="66" r="12" fill="{PARCHMENT}" {common}/>
  <path d="M92 108 L170 90" stroke="{SAGE}" stroke-width="6" stroke-linecap="round"/>
""",
        "stamp-rim": f"""
  <circle cx="128" cy="128" r="96" fill="none" stroke="{INK}" stroke-width="12"/>
  <circle cx="128" cy="128" r="78" fill="none" stroke="{BRASS}" stroke-width="5"/>
  <path d="M128 34 L128 54 M128 202 L128 222 M34 128 L54 128 M202 128 L222 128"
        stroke="{BRASS}" stroke-width="7" stroke-linecap="round"/>
""",
        "medallion-rim": f"""
  <circle cx="128" cy="128" r="92" fill="{PARCHMENT}" stroke="{INK}" stroke-width="10"/>
  <circle cx="128" cy="128" r="72" fill="none" stroke="{BRASS}" stroke-width="6"/>
  <path d="M128 26 L142 52 L128 44 L114 52 Z" fill="{BRASS}" stroke="none"/>
""",
        "passport-tray": f"""
  <path d="M28 96 L228 96 L212 204 L44 204 Z" fill="{PARCHMENT}" {common}/>
  <path d="M48 116 L208 116 L196 184 L60 184 Z" fill="none" stroke="{SAGE}" stroke-width="5"/>
""",
        "ticket": f"""
  <path d="M30 104 L226 104 L226 152 L30 152 Z" fill="{CREAM}" {common}/>
  <path d="M70 104 L70 152 M186 104 L186 152" stroke="{SAGE}" stroke-width="5" stroke-linecap="round"/>
  <circle cx="226" cy="128" r="14" fill="{PARCHMENT}" {common}/>
""",
        "shelf-plank": f"""
  <path d="M12 96 L244 96 L236 152 L20 152 Z" fill="#96683e" {common}/>
  <path d="M26 112 L230 112 M26 134 L230 134" stroke="#7a5330" stroke-width="4"/>
""",
    }[name]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  {art}
</svg>
"""


def write_masters() -> None:
    """(Re)draw every master file. Committed output; CP-010/CP-013 replace the SVGs they own."""
    for rel in (
        "fonts",
        "material",
        "fox",
        "objects",
    ):
        (MASTERS / rel).mkdir(parents=True, exist_ok=True)
    for name in contract_material_files():
        stem = Path(name).stem
        (MASTERS / "material" / (stem + ".png")).write_bytes(material_master_bytes(stem))
    for pose in FOX_POSES:
        (MASTERS / "fox" / ("fox-%s.svg" % pose)).write_text(_fox_svg(pose), encoding="utf-8")
    for name in OBJECTS:
        if (ART_OBJECTS / (name + ".png")).is_file():
            continue  # CP-013 painted the blank; --write-masters must never clobber it
        (MASTERS / "objects" / (name + ".svg")).write_text(_object_svg(name), encoding="utf-8")
    print("masters written under %s" % MASTERS)


# --------------------------------------------------------------------------------------------
# raster + encode
# --------------------------------------------------------------------------------------------


def rasterize_svg(svg: Path, width: int, height: int) -> "object":
    from PIL import Image

    tool = shutil.which("rsvg-convert")
    if not tool:
        raise SystemExit("rsvg-convert is required to rasterise the SVG masters")
    out = subprocess.run(
        [tool, "-w", str(width), "-h", str(height), "--format", "png", str(svg)],
        capture_output=True,
        check=True,
    )
    img = Image.open(io.BytesIO(out.stdout))
    img.load()
    return img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")


def encode(img, fmt: str, quality: int = 88) -> bytes:
    from PIL import features

    buf = io.BytesIO()
    if fmt == "webp":
        img.save(buf, format="WEBP", quality=quality, method=6, exact=True)
    elif fmt == "avif":
        if not features.check("avif"):
            raise SystemExit("AVIF encoder unavailable")
        img.save(buf, format="AVIF", quality=70, speed=6)
    else:
        raise SystemExit("unknown format")
    return buf.getvalue()


def may_emit_avif(webp_bytes: bytes) -> bool:
    from PIL import features

    return len(webp_bytes) >= 8_000 and bool(features.check("avif"))


# --------------------------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------------------------


def build_font(key: str, spec: dict) -> tuple[bytes, dict]:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    master = ROOT / spec["master"]
    if not master.exists():
        raise SystemExit("missing font master: %s" % master)
    font = TTFont(str(master), recalcTimestamp=False)
    original_family = spec["upstream_family"]

    options = subset.Options()
    options.layout_features = ["kern", "liga", "calt", "ccmp", "mark", "mkmk"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.recommended_glyphs = True
    options.hinting = False
    options.desubroutinize = True
    options.drop_tables += ["DSIG"]
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.flavor = "woff2"

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=FONT_CODEPOINTS)
    subsetter.subset(font)

    # Rename the *font names* only. Copyright (0), licence (13) and licence URL (14) keep the
    # upstream text verbatim, which is what OFL asks for -- and is why RFN compliance is checked
    # against IDs 1/3/4/6/16/17, not against every string in the file.
    family = spec["family"]
    style = "Regular"
    ps = spec["postscript"]
    version = font["name"].getDebugName(5) or "Version 1.000"
    replacements = {
        1: family,
        2: style,
        3: "%s;%s;1.000" % (family.replace(" ", ""), ps),
        4: "%s %s" % (family, style),
        6: ps,
        16: family,
        17: style,
        21: family,
        22: style,
        # WWS names some VFs carry
        18: "%s %s" % (family, style),
    }
    name_table = font["name"]
    for record in list(name_table.names):
        if record.nameID in replacements:
            record.string = replacements[record.nameID].encode(record.getEncoding())
        elif record.nameID in (0, 7, 8, 9, 11, 12, 13, 14):
            continue

    # Determinism: no build clock anywhere in the bytes. fontTools stores head dates in seconds
    # since 1904-01-01, so 3_850_000_000 is 2025-12-31T04:26:40Z in that epoch (not 2026-01-01).
    font["head"].created = 3_850_000_000
    font["head"].modified = 3_850_000_000
    if "meta" in font:
        del font["meta"]

    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    data = buf.getvalue()

    # Re-read to prove the renamed names and the RFN position.
    check = TTFont(io.BytesIO(data), recalcTimestamp=False)
    names = {}
    for nid in (1, 2, 4, 6, 16, 17):
        value = check["name"].getDebugName(nid)
        if value:
            names[nid] = value
    if any(original_family.lower() in str(v).lower() for v in names.values()):
        raise SystemExit("RFN violation: %s still names %r" % (key, original_family))
    if not check["name"].getDebugName(1).startswith("CB "):
        raise SystemExit("family must start with 'CB ': %r" % check["name"].getDebugName(1))

    return data, {
        "master": spec["master"],
        "master_sha256": sha256_file(master),
        "names": names,
        "upstream_family": original_family,
        "upstream_sha256": sha256_file(master),
        "rfn_declared": spec["rfn"],
    }


# --------------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------------


def _row(role, source, licence, sha, width, height, size, provenance, path, kind="image", **extra):
    row = {
        "role": role,
        "source": source,
        "licence": licence,
        "sha256": sha,
        "width": width,
        "height": height,
        "bytes": size,
        "provenance_id": provenance,
        "path": path,
        "kind": kind,
    }
    row.update(extra)
    return row


def kit_plates() -> list[dict]:
    """The nine curated plates this segment carries, each with the kit's declared source hash.

    ``kit.json`` is the authority: the declaration is read, never recomputed, and the file it names
    must hash to the declared value or the build stops. Nothing here reads ``assets/masters/``.
    """
    kit = json.loads(KIT_JSON.read_text(encoding="utf-8"))
    if kit.get("kit_id") != "field_atlas@2":
        raise SystemExit("unexpected kit id in %s: %r" % (KIT_JSON, kit.get("kit_id")))
    plates = []
    resolution = kit.get("resolution") or {}
    roles = kit.get("roles") or {}
    for role, quality in KIT_FULL_ROLES:
        rows = roles.get(role) or []
        if len(rows) != 1:
            raise SystemExit("kit role %s must carry exactly one plate" % role)
        plate = rows[0]
        source = (resolution.get(role) or {}).get("source") or {}
        if not source.get("path") or not source.get("sha256"):
            raise SystemExit("kit role %s has no 2x source declaration" % role)
        plates.append(
            {
                "id": plate["id"],
                "kit_role": role,
                "source": source["path"],
                "source_size": tuple(source["size"]),
                "render_size": tuple(plate["size"]),
                "quality": quality,
                "declared_sha256": source["sha256"],
            }
        )
    covers = roles.get("cover") or []
    if len(covers) != 6:
        raise SystemExit("kit must carry six covers, found %d" % len(covers))
    for plate in covers:
        plates.append(
            {
                "id": plate["id"],
                "kit_role": "cover",
                "source": plate["path"],
                "source_size": tuple(plate["size"]),
                "render_size": tuple(plate["size"]),
                "quality": KIT_COVER_QUALITY,
                "declared_sha256": plate["sha256"],
            }
        )
    return plates


def build_kit(hi_res: bool = True) -> tuple[list, dict, str]:
    """Encode the curated kit into ``assets/kit/`` and its data-url entries.

    The two full plates are emitted at the provider's 2688x1536 when the segment can afford it, and
    at the shipped 1344x768 when it cannot. Covers are always emitted at their natural size, which
    the kit already documents as 2x of the render.
    """
    from PIL import Image

    rows, entries, notes = [], {}, []
    for plate in kit_plates():
        source = KIT / plate["source"]
        if not source.is_file():
            raise SystemExit("missing kit plate: %s" % source)
        actual = sha256_file(source)
        if actual != plate["declared_sha256"]:
            raise SystemExit(
                "kit plate %s hashes to %s, %s declares %s"
                % (source, actual, KIT_JSON.name, plate["declared_sha256"])
            )
        target = plate["render_size"]
        if plate["kit_role"] != "cover" and hi_res:
            target = plate["source_size"]
        with Image.open(source) as opened:
            img = opened.convert("RGB")
            if img.size != target:
                if target[0] > img.size[0] or target[1] > img.size[1]:
                    raise SystemExit(
                        "kit plate %s is %dx%d; %dx%d would be an upscale"
                        % (source, *img.size, *target)
                    )
                img = img.resize(target, Image.Resampling.LANCZOS)
            webp = encode(img, "webp", quality=plate["quality"])
        rel = "assets/kit/field_atlas-%s.webp" % plate["id"]
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(webp)
        prov = "cb.asset.kit.field_atlas.%s" % plate["id"]
        row = _row(
            "kit.%s.%s" % (plate["kit_role"], plate["id"]),
            "curated:assets/visual-kits/%s/%s" % (KIT.name, plate["source"]),
            "CC0-1.0",
            sha256_bytes(webp),
            target[0],
            target[1],
            len(webp),
            prov,
            rel,
            master="assets/visual-kits/%s/%s" % (KIT.name, plate["source"]),
            master_sha256=plate["declared_sha256"],
            kit_id="field_atlas@2",
            kit_role=plate["kit_role"],
            quality=plate["quality"],
        )
        rows.append(row)
        entries[prov] = {
            "group": "kit",
            "role": row["role"],
            "path": rel,
            "mime": "image/webp",
            "width": target[0],
            "height": target[1],
            "bytes": len(webp),
            "sha256": row["sha256"],
            "licence": "CC0-1.0",
            "src": data_url("image/webp", webp),
        }
        notes.append(
            "kit %-24s %4dx%-4d q%-2d %7d B -> %s"
            % (plate["id"], target[0], target[1], plate["quality"], len(webp), rel)
        )
    rows.sort(key=lambda r: r["path"])
    (KIT_EMBED / "manifest.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    scale = "2x" if hi_res else "1x"
    note = "kit field_atlas@2: hero and lesson scene emitted at %s\n%s" % (scale, "\n".join(notes))
    return rows, entries, note


def segment_source(entries: dict) -> str:
    """The exact text of ``desktop/cb-assets.generated.js`` for a set of data-url entries."""
    assets_obj = {
        "schema": 1,
        "generated_by": "scripts/build_cb_assets.py",
        "note": (
            "Brand assets only: typefaces, material tiles, the fox, the object kit and the curated "
            "field_atlas@2 display plates. Per-course pack covers, scene headers and world plates "
            "are never embedded; they stay pack or world media served by /media/{artifact_id} and "
            "/artifacts/{handle}."
        ),
        "fonts": {
            spec["family"]: entries["cb.asset.font.%s" % key]["src"]
            for key, spec in FONT_SOURCES.items()
        },
        "assets": entries,
    }
    body = json.dumps(assets_obj, indent=2, sort_keys=True, ensure_ascii=True)
    return (
        "// GENERATED by scripts/build_cb_assets.py -- do not edit by hand.\n"
        "// One frozen brand-asset object: typefaces, material tiles, fox poses, object kit, and the\n"
        "// curated field_atlas@2 display plates. Per-course covers are not in here.\n"
        "const CB_ASSETS = Object.freeze(%s);\n"
        "if (typeof globalThis !== \"undefined\") { globalThis.CB_ASSETS = CB_ASSETS; }\n" % body
    )


def build(check: bool = False) -> dict:
    fonts_rows, font_entries = [], {}
    material_rows, material_entries = [], {}
    fox_rows, fox_entries = [], {}
    object_rows, object_entries = [], {}

    # fonts ---------------------------------------------------------------------------------
    for key, spec in FONT_SOURCES.items():
        data, meta = build_font(key, spec)
        rel = "assets/fonts/%s.woff2" % ("CBDisplay-VF" if key == "display" else "CBUI-VF")
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        prov = "cb.asset.font.%s" % key
        row = _row(
            "typeface.%s" % key,
            spec["source"],
            spec["licence"],
            sha256_bytes(data),
            0,
            0,
            len(data),
            prov,
            rel,
            kind="font",
            family=spec["family"],
            unicode_range="U+0020-007E, U+00A0-00FF, U+2013-2014, U+2018-201D, U+2022, U+2026, U+00B7, U+00D7, U+00B0",
            rfn_declared=meta["rfn_declared"],
            licence_file=spec["licence_file"],
            master=spec["master"],
            master_sha256=meta["master_sha256"],
        )
        fonts_rows.append(row)
        font_entries[prov] = {
            "group": "fonts",
            "family": spec["family"],
            "role": row["role"],
            "path": rel,
            "mime": "font/woff2",
            "bytes": len(data),
            "sha256": row["sha256"],
            "licence": spec["licence"],
            "src": data_url("font/woff2", data),
        }

    # material ------------------------------------------------------------------------------
    for contract_rel in contract_material_files():
        stem = Path(contract_rel).stem
        master = MASTERS / "material" / (stem + ".png")
        if not master.exists():
            raise SystemExit("missing material master: %s" % master)
        from PIL import Image

        img = Image.open(io.BytesIO(master.read_bytes())).convert("RGB")
        tile = 96
        img = img.resize((tile, tile), Image.Resampling.LANCZOS)
        webp = encode(img, "webp")
        rel = "assets/" + contract_rel
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(webp)
        prov = "cb.asset.material.%s" % stem
        row = _row(
            "material.tile.%s" % stem,
            "authored:assets/masters/material/%s.png" % stem,
            "CC0-1.0",
            sha256_bytes(webp),
            tile,
            tile,
            len(webp),
            prov,
            rel,
            master="assets/masters/material/%s.png" % stem,
            master_sha256=sha256_file(master),
            seamless_3x3=True,
        )
        material_rows.append(row)
        entry = {
            "group": "material",
            "role": row["role"],
            "path": rel,
            "mime": "image/webp",
            "width": tile,
            "height": tile,
            "bytes": len(webp),
            "sha256": row["sha256"],
            "licence": "CC0-1.0",
            "src": data_url("image/webp", webp),
        }
        material_entries[prov] = entry

    # fox -----------------------------------------------------------------------------------
    # CP-005f: the owner-signed painted set is canonical. Each shipped WebP/AVIF is an encode of
    # the painted PNG export at that size, so alpha, palette and resampling are the art team's,
    # not this script's. A missing export fails the build; it never falls back to the procedural
    # SVG fox, which would silently re-ship the placeholder.
    for pose in FOX_POSES:
        for px in FOX_EXPORTS:
            painted = ART_FOX / ("fox-%s-%d.png" % (pose, px))
            if not painted.is_file():
                raise SystemExit("missing painted fox export: %s" % painted)
            from PIL import Image

            with Image.open(painted) as opened:
                img = opened.convert("RGBA")
            if img.size != (px, px):
                raise SystemExit(
                    "painted fox %s is %dx%d, not %dx%d" % (painted.name, *img.size, px, px)
                )
            webp = encode(img, "webp")
            rel = "assets/fox/fox-%s-%d.webp" % (pose, px)
            out = ROOT / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(webp)
            master_rel = "assets/art/fox/fox-%s-%d.png" % (pose, px)
            prov = "cb.asset.fox.%s.%d" % (pose, px)
            row = _row(
                "mascot.pose.%s@%d" % (pose, px),
                "authored:%s" % master_rel,
                "CC0-1.0",
                sha256_bytes(webp),
                px,
                px,
                len(webp),
                prov,
                rel,
                master=master_rel,
                master_sha256=sha256_file(painted),
            )
            az = None
            if may_emit_avif(webp):
                avif = encode(img, "avif")
                avif_rel = "assets/fox/fox-%s-%d.avif" % (pose, px)
                (ROOT / avif_rel).write_bytes(avif)
                az = avif_rel
                row["avif"] = avif_rel
                row["avif_sha256"] = sha256_bytes(avif)
                row["avif_bytes"] = len(avif)
            fox_rows.append(row)
            entry = {
                "group": "fox",
                "role": row["role"],
                "path": rel,
                "mime": "image/webp",
                "width": px,
                "height": px,
                "bytes": len(webp),
                "sha256": row["sha256"],
                "licence": "CC0-1.0",
                "src": data_url("image/webp", webp),
            }
            if az:
                entry["src_avif"] = data_url("image/avif", (ROOT / az).read_bytes())
            fox_entries[prov] = entry

    # objects -------------------------------------------------------------------------------
    # CP-013 replaced the provisional SVG kit with painted blanks. The painted master is the
    # single source: it lives in assets/art/objects/<name>.png, is never embedded, and the shipped
    # assets/objects/<name>.webp is only an encode of it. An object with no painted master still
    # falls back to the procedural SVG so the pipeline keeps a typographic fallback.
    for name in OBJECTS:
        painted = ART_OBJECTS / (name + ".png")
        svg_master = MASTERS / "objects" / (name + ".svg")
        if painted.is_file():
            from PIL import Image

            with Image.open(painted) as opened:
                img = opened.convert("RGBA")
            if img.size != (256, 256):
                raise SystemExit("painted object %s is %dx%d, not 256x256" % (painted, *img.size))
            master_rel = "assets/art/objects/%s.png" % name
            source = "generated:audit/cp013-scenes/provenance.json#%s" % name
        elif svg_master.is_file():
            img = rasterize_svg(svg_master, 256, 256)
            master_rel = "assets/masters/objects/%s.svg" % name
            source = "authored:%s" % master_rel
        else:
            raise SystemExit("missing object master: %s" % painted)
        webp = encode(img, "webp")
        rel = "assets/objects/%s.webp" % name
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(webp)
        prov = "cb.asset.object.%s" % name
        row = _row(
            "object.%s" % name,
            source,
            "CC0-1.0",
            sha256_bytes(webp),
            256,
            256,
            len(webp),
            prov,
            rel,
            master=master_rel,
            master_sha256=sha256_file(ROOT / master_rel),
        )
        object_rows.append(row)
        entry = {
            "group": "objects",
            "role": row["role"],
            "path": rel,
            "mime": "image/webp",
            "width": 256,
            "height": 256,
            "bytes": len(webp),
            "sha256": row["sha256"],
            "licence": "CC0-1.0",
            "src": data_url("image/webp", webp),
        }
        if may_emit_avif(webp):
            avif = encode(img, "avif")
            avif_rel = "assets/objects/%s.avif" % name
            (ROOT / avif_rel).write_bytes(avif)
            row["avif"] = avif_rel
            row["avif_sha256"] = sha256_bytes(avif)
            row["avif_bytes"] = len(avif)
            entry["src_avif"] = data_url("image/avif", avif)
        object_entries[prov] = entry

    # curated kit (field_atlas@2) --------------------------------------------------------------
    # VQ-002's owner-approved display plates. The kit ships its own hashes; this branch encodes
    # the curated files and stops if any of them has drifted from kit.json. The 2x hero and lesson
    # scene are used only while the whole segment stays under SEGMENT_BUDGET.
    kit_rows, kit_entries, kit_note = build_kit(hi_res=True)

    manifests = {
        "fonts": fonts_rows,
        "material": material_rows,
        "fox": fox_rows,
        "objects": object_rows,
        "kit": kit_rows,
    }
    for group, rows in manifests.items():
        rows.sort(key=lambda r: r["path"])
        (ASSETS / group / "manifest.json").write_text(
            json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    # gated masters: the pipeline's own inputs, never embedded, never counted in the budget
    master_rows = []
    for path in sorted(MASTERS.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rel = str(path.relative_to(ROOT))
        if path.suffix == ".svg":
            width = height = 512 if "/fox/" in rel else 256
        elif path.suffix in (".png",):
            from PIL import Image

            with Image.open(path) as im:
                width, height = im.size
        else:
            width = height = 0
        master_rows.append(
            _row(
                "master.%s" % path.stem,
                "google/fonts@5bb28733cec313b63fbd415b574b5ae35c8aa8b8" if path.suffix == ".ttf"
                else "authored:scripts/build_cb_assets.py --write-masters",
                "OFL-1.1" if path.suffix == ".ttf" else "CC0-1.0",
                sha256_file(path),
                width,
                height,
                path.stat().st_size,
                "cb.master.%s" % rel.split("assets/masters/", 1)[1].replace("/", ".").rsplit(".", 1)[0],
                rel,
                kind="master",
                embedded=False,
            )
        )
    (MASTERS / "manifest.json").write_text(
        json.dumps(master_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # generated segment ---------------------------------------------------------------------
    entries = {}
    entries.update(font_entries)
    entries.update(material_entries)
    entries.update(fox_entries)
    entries.update(object_entries)
    entries.update(kit_entries)
    js = segment_source(entries)
    if len(js.encode("utf-8")) > SEGMENT_BUDGET:
        # The card's rule: 2x when the segment can hold it, otherwise the shipped 1x plates.
        kit_rows, kit_entries, kit_note = build_kit(hi_res=False)
        manifests["kit"] = kit_rows
        entries.update(kit_entries)
        js = segment_source(entries)
    GENERATED.parent.mkdir(parents=True, exist_ok=True)
    GENERATED.write_text(js, encoding="utf-8")

    report = size_report(manifests, entries, js)
    print(kit_note)
    print(report["text"])
    if check and not report["ok"]:
        raise SystemExit(1)
    return report


def size_report(manifests: dict, entries: dict, js: str) -> dict:
    lines = ["Coursebook brand assets -- size report", ""]
    ok = True
    total = 0
    for group, rows in manifests.items():
        group_total = sum(r["bytes"] + r.get("avif_bytes", 0) for r in rows)
        total += group_total
        largest = max(rows, key=lambda r: max(r["bytes"], r.get("avif_bytes", 0)))
        lines.append(
            "%-10s %2d assets %8d B  largest %s (%d B)"
            % (group, len(rows), group_total, largest["path"], max(largest["bytes"], largest.get("avif_bytes", 0)))
        )
        for row in rows:
            for field, label in (("bytes", row["path"]), ("avif_bytes", row.get("avif", ""))):
                size = row.get(field, 0)
                if size > ASSET_BUDGET:
                    ok = False
                    lines.append("  OVER 300 KB: %s (%d B)" % (label or row["path"], size))
    segment = len(js.encode("utf-8"))
    plugin = (ROOT / "desktop" / "plugin.js").stat().st_size
    lines += [
        "",
        "shipped files        %8d B" % total,
        "generated segment    %8d B  budget %8d B" % (segment, SEGMENT_BUDGET),
        "desktop/plugin.js    %8d B  budget %8d B" % (plugin, PLUGIN_BUDGET),
        # CP-020a concatenates the segment into plugin.js, so plugin.js already carries those
        # bytes. The earlier "plugin + segment" line counted the same payload twice and reported
        # 5.5 MB for a 4.1 MB artifact; the budget is on the shipped file, counted once.
        "  of which segment   %8d B  (carried by plugin.js, counted once)" % segment,
        "plugin source only   %8d B" % (plugin - segment),
        "data-url entries     %8d" % len(entries),
    ]
    if segment > SEGMENT_BUDGET:
        ok = False
        lines.append("OVER: generated segment exceeds %d B" % SEGMENT_BUDGET)
    if plugin > PLUGIN_BUDGET:
        ok = False
        lines.append("OVER: plugin.js exceeds %d B" % PLUGIN_BUDGET)
    lines.append("")
    lines.append("VERDICT: %s" % ("within budget" if ok else "OVER BUDGET"))
    return {"ok": ok, "segment": segment, "plugin": plugin, "total": total, "entries": len(entries), "text": "\n".join(lines)}


def committed_state() -> tuple[dict, dict, str]:
    """Read the committed manifests and segment. Never writes; this is the --report path."""
    manifests = {}
    for group in ("fonts", "material", "fox", "objects", "kit"):
        path = ASSETS / group / "manifest.json"
        if not path.is_file():
            raise SystemExit(
                "no committed manifest at %s; run a build first" % path.relative_to(ROOT)
            )
        manifests[group] = json.loads(path.read_text(encoding="utf-8"))
    if not GENERATED.is_file():
        raise SystemExit(
            "no committed segment at %s; run a build first" % GENERATED.relative_to(ROOT)
        )
    js = GENERATED.read_text(encoding="utf-8")
    start = js.index("Object.freeze(") + len("Object.freeze(")
    entries = json.loads(js[start : js.rindex(");")])["assets"]
    return manifests, entries, js


def report_only() -> dict:
    """Print the size report for the committed tree. Read-only: no master, no segment, no build."""
    manifests, entries, js = committed_state()
    report = size_report(manifests, entries, js)
    print(report["text"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit non-zero when a budget fails")
    parser.add_argument("--write-masters", action="store_true", help="redraw every art master")
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the size report for the committed tree; writes nothing and needs no venv",
    )
    args = parser.parse_args()
    if args.report:
        report = report_only()
        if args.check and not report["ok"]:
            raise SystemExit(1)
        return
    ensure_venv()
    if args.write_masters:
        write_masters()
        return
    build(check=args.check)


if __name__ == "__main__":
    main()
