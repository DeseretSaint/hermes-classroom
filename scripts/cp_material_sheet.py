#!/usr/bin/env python3
"""CP-011 — the texture sheet: every material tile behind real body text at 16 px.

Two sheets are rendered, one per mode. Each sheet puts a **flat control** beside the **textured**
field carrying the identical paragraph, so "legibility is unaffected" is a comparison the reviewer
can make by eye and that the test can make by measuring the committed manifest.

Wood is on the sheet too, but with no text over it: the card's rule is that wood carries the shelf
plank and the evidence tray only, and a label never sits on wood. Showing that as a positive (a
plank strip and a tray, both textless) is the honest proof; leaving wood off the sheet is not.

Evidence status: this is a **proof sheet**, not a UI capture. `scripts/cp-capture.mjs` is CP-000's
deliverable and is not on this branch, so nothing here claims to be a live route frame. The stamp
records the commit, the tile hashes, the text source and the render engine so a reviewer can
reproduce it byte-for-byte.

Usage:
    python3 scripts/cp_material_sheet.py            # render both sheets + stamps
    python3 scripts/cp_material_sheet.py --check    # verify sheets and stamps are current
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILE_DIR = ROOT / "assets" / "art" / "material"
OUT_DIR = ROOT / "docs" / "concept-parity" / "art" / "material"
MANIFEST = TILE_DIR / "manifest.json"

# Real product prose, taken from a bundled pack's own teaching text. Never invented copy.
TEXT_SOURCE = ROOT / "bundled" / "packs" / "technical-pack-literacy" / "content" / "section-01-anatomy.md"

BODY_PX = 16
MEASURE_CH = 62

# Canvas colours must match PALETTE in scripts/build_cb_material.py.
CANVAS = {"light": "#f5e3c8", "dark": "#171410"}
CARD = {"light": "#f4ecd9", "dark": "#221d17"}
INK = {"light": "#1a1713", "dark": "#f2e2ce"}
INK_SOFT = {"light": "#4a3f33", "dark": "#c8b79e"}
FONT = "Liberation Serif, Noto Serif, serif"

WIDTH = 1120
PAD = 40


def body_text() -> str:
    """Two paragraphs of the pack's real prose, stripped of markdown syntax."""
    raw = TEXT_SOURCE.read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw.split("\n\n")]
    kept = []
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        cleaned = re.sub(r"[`*_>-]", "", paragraph)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > 180:
            kept.append(cleaned)
        if len(kept) == 2:
            break
    if not kept:
        raise SystemExit("no usable body text in the pack source")
    return "\n\n".join(kept)


def html(mode: str) -> str:
    text = body_text()
    tiles = {row["id"]: row for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["tiles"]
             if row["mode"] == mode}
    grain = tiles["paper-grain"]
    fibre = tiles["card-stock-fibre"]
    vignette = tiles["parchment-vignette"]
    wood = tiles["wood-plank"]

    def file_url(row: dict) -> str:
        return (ROOT / row["path"]).as_uri()

    ink, ground = INK[mode], CANVAS[mode]

    grain_css = f"url('{file_url(grain)}')"
    fibre_css = f"url('{file_url(fibre)}')"
    vignette_css = f"url('{file_url(vignette)}')"
    wood_css = f"url('{file_url(wood)}')"

    rows = []
    rows.append(f"""
<section class="row">
  <h2>paper grain <span class="sub">canvas overlay · repeat · {grain['bytes']} B · alpha ≤ {grain['alpha_ceiling']}</span></h2>
  <div class="pair">
    <figure>
      <div class="field flat" style="background:{ground};color:{ink}">{text}</div>
      <figcaption>flat control — token canvas, no tile</figcaption>
    </figure>
    <figure>
      <div class="field" style="background:{ground} {grain_css} repeat;color:{ink}">{text}</div>
      <figcaption>same text over paper grain</figcaption>
    </figure>
  </div>
</section>""")

    rows.append(f"""
<section class="row">
  <h2>card-stock fibre <span class="sub">card stock overlay · repeat · {fibre['bytes']} B · alpha ≤ {fibre['alpha_ceiling']}</span></h2>
  <div class="pair">
    <figure>
      <div class="field flat" style="background:{CARD[mode]};color:{ink}">{text}</div>
      <figcaption>flat control — token card stock</figcaption>
    </figure>
    <figure>
      <div class="field" style="background:{CARD[mode]} {fibre_css} repeat;color:{ink}">{text}</div>
      <figcaption>same text over card-stock fibre</figcaption>
    </figure>
  </div>
</section>""")

    rows.append(f"""
<section class="row">
  <h2>parchment vignette <span class="sub">canvas edge wash · one application, cover size · {vignette['bytes']} B · alpha ≤ {vignette['alpha_ceiling']}</span></h2>
  <div class="wide" style="background:{ground} {vignette_css} center / cover no-repeat;color:{ink}">
    <p class="corner">{text}</p>
    <p class="centre">{text}</p>
  </div>
  <figcaption>text at the darkest corner and at the centre of one applied wash — the worst case for edge text</figcaption></section>""")

    rows.append(f"""
<section class="row">
  <h2>wood plank <span class="sub">shelf plank + evidence tray · repeat · {wood['bytes']} B · no text, ever</span></h2>
  <div class="plank" style="background:{wood_css} repeat"></div>
  <div class="tray" style="background:{wood_css} repeat"></div>
  <figcaption>plank face and tray; every label on those surfaces is DOM text placed beside or above them,
  never on the wood. That is the card rule, shown rather than asserted.</figcaption>
</section>""")

    meta = []
    for tile_id in ("paper-grain", "card-stock-fibre", "parchment-vignette", "wood-plank"):
        row = tiles[tile_id]
        if row["text_bearing"]:
            contrast = f"ink worst-case {row['ink_worst_contrast']}:1"
        else:
            contrast = "no text surface — contrast not gated"
        meta.append(
            f"<li><b>{tile_id}</b> {row['width']}×{row['height']} · {row['bytes']} B · "
            f"seam {row['seam']['column_ratio']}/{row['seam']['row_ratio']} · "
            f"{contrast} · <code>{row['sha256'][:12]}</code></li>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Coursebook material sheet — {mode}</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: {ground}; }}
  body {{ width: {WIDTH}px; padding: {PAD}px; font-family: {FONT}; color: {ink}; }}
  header {{ border-bottom: 1px solid {INK_SOFT[mode]}; padding-bottom: 14px; margin-bottom: 22px; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; letter-spacing: -0.01em; }}
  .lede {{ font-size: 15px; line-height: 1.45; margin: 0; color: {INK_SOFT[mode]}; max-width: 78ch; }}
  h2 {{ font-size: 15px; margin: 0 0 8px; font-family: Liberation Sans, sans-serif; }}
  .sub {{ font-weight: 400; color: {INK_SOFT[mode]}; font-size: 12px; }}
  section.row {{ margin: 0 0 26px; }}
  .pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  figure {{ margin: 0; }}
  .field {{ height: 186px; overflow: hidden; padding: 14px 16px; font-size: {BODY_PX}px;
            line-height: 1.5; border-radius: 6px; }}
  .field.flat {{ box-shadow: inset 0 0 0 1px {INK_SOFT[mode]}; }}
  figcaption {{ font-family: Liberation Sans, sans-serif; font-size: 11px; color: {INK_SOFT[mode]};
                margin-top: 6px; }}
  .wide {{ height: 340px; border-radius: 6px; position: relative; overflow: hidden; }}
  .wide p {{ position: absolute; margin: 0; font-size: {BODY_PX}px; line-height: 1.5;
             width: 300px; height: 310px; overflow: hidden; }}
  .wide .corner {{ left: 12px; top: 12px; }}
  .wide .centre {{ left: 390px; top: 14px; }}
  .plank {{ height: 46px; border-radius: 3px; }}
  .tray {{ height: 64px; margin-top: 12px; border-radius: 3px; }}
  footer {{ border-top: 1px solid {INK_SOFT[mode]}; padding-top: 14px; font-family: Liberation Sans, sans-serif;
            font-size: 11.5px; line-height: 1.6; color: {INK_SOFT[mode]}; }}
  ul {{ margin: 6px 0 10px; padding-left: 18px; }}
  code {{ font-family: Liberation Mono, monospace; }}
</style></head>
<body>
<header>
  <h1>Material textures — {mode}</h1>
  <p class="lede">Every tile in this card behind real body text at {BODY_PX} px, next to a flat control
  carrying the same paragraph. The text is the bundled technical pack's own teaching prose, not copy
  written for this sheet. This is a proof sheet: it exercises the committed PNGs in a browser, it is
  not a capture of a product route.</p>
</header>
{''.join(rows)}
<footer>
  <ul>{''.join(meta)}</ul>
  Compose order: ground token → tile overlay (<code>aria-hidden</code>, <code>pointer-events:none</code>) →
  vignette once at cover size → text. Under <code>@media (forced-colors: active)</code> both layers are
  hidden and the ground is the system colour. Text size {BODY_PX} px, measure capped at
  {MEASURE_CH} ch. Rendered from the committed tiles, sha-pinned below.
</footer>
</body></html>"""


def chromium_version() -> str:
    out = subprocess.run(["chromium", "--version"], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def render(mode: str) -> Path:
    html_path = Path(tempfile.mkdtemp(prefix="cb-material-")) / f"sheet-{mode}.html"
    html_path.write_text(html(mode), encoding="utf-8")
    target = OUT_DIR / f"texture-sheet-{mode}.png"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "chromium", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
            "--force-device-scale-factor=1", f"--default-background-color={CANVAS[mode].lstrip('#')}ff",
            f"--window-size={WIDTH},2600", "--virtual-time-budget=4000",
            f"--screenshot={target}", html_path.as_uri(),
        ],
        check=True, capture_output=True,
    )
    return target


def stamp(mode: str, sheet: Path) -> Path:
    from build_cb_material import read_png, write_png  # same repo, same PNG code

    image = read_png(sheet)
    width, height, channels = image["width"], image["height"], image["channels"]
    pixels = image["pixels"]
    corner = pixels[channels * (width + 1):channels * (width + 1) + channels]  # the page margin

    def row_is_blank(y: int) -> bool:
        row = pixels[y * width * channels:(y + 1) * width * channels]
        return all(row[i:i + channels] == corner for i in range(0, len(row), channels))

    last = height - 1
    while last > 0 and row_is_blank(last):
        last -= 1
    trimmed = min(height, last + 1 + 24)
    if trimmed < height:
        write_png(sheet, width, trimmed, channels, pixels[: trimmed * width * channels])

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record = {
        "schema": "cb.material.sheet.v1",
        "card": "CP-011",
        "mode": mode,
        "sheet": str(sheet.relative_to(ROOT)),
        "sheet_sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
        "sheet_bytes": sheet.stat().st_size,
        "sheet_size": {"width": width, "height": trimmed},
        "commit": commit,
        "branch": branch,
        "engine": chromium_version(),
        "device_scale": 1,
        "body_px": BODY_PX,
        "font_family": FONT,
        "text_source": {
            "path": str(TEXT_SOURCE.relative_to(ROOT)),
            "sha256": hashlib.sha256(TEXT_SOURCE.read_bytes()).hexdigest(),
            "note": "the bundled technical pack's own teaching prose; no copy invented for the sheet",
        },
        "tiles": [
            {
                "id": row["id"], "sha256": row["sha256"], "bytes": row["bytes"],
                "alpha_ceiling": row["alpha_ceiling"], "ground": row["ground"],
                "text_bearing": row["text_bearing"],
                "ink_worst_contrast": row["ink_worst_contrast"],
                "text_gate": row["text_required"],
                "legibility_passes": row.get("legibility_passes"),
                "seam_ratio": [row["seam"]["column_ratio"], row["seam"]["row_ratio"]],
            }
            for row in document["tiles"] if row["mode"] == mode
        ],
        "wood_has_no_text": True,
        "contrast_note": (
            "ink_worst_contrast is the minimum over the committed tile pixels against the row's ink; "
            "the 4.5:1 gate is applied only where text_bearing is true. wood-plank carries no text, "
            "so its figure is informational and legibility_passes is null."
        ),
        "capture_rig": "scripts/cp_material_sheet.py (proof sheet; scripts/cp-capture.mjs is CP-000 and not on this branch)",
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    path = OUT_DIR / f"texture-sheet-{mode}.stamp.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def check() -> int:
    problems = []
    for mode in ("light", "dark"):
        sheet = OUT_DIR / f"texture-sheet-{mode}.png"
        stamp_path = OUT_DIR / f"texture-sheet-{mode}.stamp.json"
        if not sheet.exists() or not stamp_path.exists():
            problems.append(f"{mode}: sheet or stamp missing")
            continue
        record = json.loads(stamp_path.read_text(encoding="utf-8"))
        if hashlib.sha256(sheet.read_bytes()).hexdigest() != record["sheet_sha256"]:
            problems.append(f"{mode}: sheet sha drift")
        if len(record["tiles"]) != 4:
            problems.append(f"{mode}: stamp does not name four tiles")
        for tile in record["tiles"]:
            if tile["text_bearing"]:
                if tile["ink_worst_contrast"] < 4.5 or tile["legibility_passes"] is not True:
                    problems.append(f"{mode}/{tile['id']}: contrast {tile['ink_worst_contrast']}")
            elif tile["legibility_passes"] is not None:
                problems.append(f"{mode}/{tile['id']}: non-text surface claims a legibility pass")
            if tile["seam_ratio"][0] > 1.25 or tile["seam_ratio"][1] > 1.25:
                problems.append(f"{mode}/{tile['id']}: seam {tile['seam_ratio']}")
    if problems:
        print("\n".join(problems))
        return 1
    print("sheets and stamps verified")
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check()
    sys.path.insert(0, str(ROOT / "scripts"))
    for mode in ("light", "dark"):
        sheet = render(mode)
        path = stamp(mode, sheet)
        print(f"wrote {sheet.relative_to(ROOT)} and {path.relative_to(ROOT)}")
    return check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
