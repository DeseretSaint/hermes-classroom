#!/usr/bin/env python3
"""CP-020b — build the component lab and its evidence sheets.

The lab is the product version of R-SYS (`docs/concept-parity/refs/system.png`): every primitive,
in every state, at the real token values, in both themes and at 100 % and 200 % text. Two files
come out of one run:

* ``docs/concept-parity/lab/contact-sheet.png`` — owner checkpoint: light/dark × 100 %/200 % plus the
  reduced-motion and forced-colors postures, each captioned with the cell id it came from;
* ``docs/concept-parity/lab/anatomy-vs-rsys.png`` — the card anatomy (S6) rendered from the shipped
  primitives, side by side with the same region of the R-SYS concept.

Both are **component previews**, not live Desktop captures: there is no host, no backend and no
`data-cb-v3-ready` settle marker, and ``lab.json`` says so. Live evidence for a screen is
``scripts/cp-capture.mjs`` only.

Usage::

    python3 scripts/cp-lab-frames.py                 # render cells + both sheets
    python3 scripts/cp-lab-frames.py --contact-only   # rebuild the sheets from existing cells
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.desktop_node_modules import stage_desktop_node_modules  # noqa: E402
from tests.test_desktop_lesson_views import SDK_STUB  # noqa: E402

OUT = ROOT / "docs" / "concept-parity" / "lab"
REF_SYS = ROOT / "docs" / "concept-parity" / "refs" / "system.png"
PLUGIN = ROOT / "desktop" / "plugin.js"
SHOT = ROOT / "scripts" / "cp-lab-shot.mjs"

#: The four cells the contact sheet compares, in reading order. The two posture cells are kept on
#: disk and named in the manifest; the sheet stays a 2×2 so each cell can be read at native size.
SHEET_CELLS = ("light-100", "dark-100", "light-200", "dark-200")

CAPTIONS = {
    "light-100": "light · 100% text",
    "dark-100": "dark · 100% text",
    "light-200": "light · 200% text",
    "dark-200": "dark · 200% text",
    "light-reduced-motion": "light · reduced motion",
    "dark-forced-colors": "dark · forced colors",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_module(root: Path) -> None:
    """A private render root: the module, a local SDK stub and symlinked React packages."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name":"cb-lab","private":true,"type":"module"}\n', encoding="utf-8")
    (root / "plugin.js").write_bytes(PLUGIN.read_bytes())
    sdk = stage_desktop_node_modules(root)
    if sdk is None:
        raise SystemExit("react/react-dom are not installed beside the desktop app")
    (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")


def render_cells(out: Path, width: int) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="cb-lab-"))
    try:
        stage_module(tmp)
        result = subprocess.run(
            ["node", str(SHOT), "--root", str(tmp), "--out", str(out), "--width", str(width)],
            capture_output=True, text=True, timeout=900,
        )
        if result.returncode != 0:
            raise SystemExit(f"cp-lab-shot.mjs failed:\n{result.stderr[-4000:]}")
        sys.stdout.write(result.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return json.loads((out / "lab.json").read_text(encoding="utf-8"))


def pil():
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for candidate in (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).is_file():
            font = ImageFont.truetype(candidate, 20)
            break
    return Image, ImageDraw, font or ImageFont.load_default()


def fitted(image, width: int, height: int):
    """Letterbox into a fixed cell so four different page heights read as one sheet."""
    from PIL import Image

    scale = min(width / image.width, height / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas


def build_contact_sheet(out: Path) -> Path:
    Image, ImageDraw, font = pil()
    cell_w, cell_h = 640, 1740
    pad, header, caption = 24, 76, 34
    sheet = Image.new(
        "RGB",
        (pad * 3 + cell_w * 2, header + (caption + cell_h + pad) * 2 + pad),
        (250, 248, 243),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 22), "Coursebook v3 component lab — component preview, not a live screen", fill=(26, 23, 19), font=font)
    draw.text(
        (pad, 48),
        "Every primitive × state, light/dark × 100%/200% text, rendered from the shipped module.",
        fill=(92, 83, 71),
        font=font,
    )
    for index, cell in enumerate(SHEET_CELLS):
        column, row = index % 2, index // 2
        x = pad + column * (cell_w + pad)
        y = header + row * (caption + cell_h + pad)
        draw.text((x, y), CAPTIONS[cell], fill=(92, 83, 71), font=font)
        image = Image.open(out / f"lab-{cell}.png").convert("RGB")
        sheet.paste(fitted(image, cell_w, cell_h), (x, y + caption))
        draw.rectangle([x, y + caption, x + cell_w - 1, y + caption + cell_h - 1], outline=(205, 184, 148))
    path = out / "contact-sheet.png"
    sheet.save(path, optimize=True)
    return path


def build_anatomy_panel(out: Path, width: int) -> Path:
    Image, ImageDraw, font = pil()
    tmp = Path(tempfile.mkdtemp(prefix="cb-lab-anatomy-"))
    try:
        stage_module(tmp)
        result = subprocess.run(
            ["node", str(SHOT), "--root", str(tmp), "--out", str(tmp), "--width", str(width), "--only", "anatomy"],
            capture_output=True, text=True, timeout=900,
        )
        if result.returncode != 0:
            raise SystemExit(f"anatomy render failed:\n{result.stderr[-4000:]}")
        anatomy = Image.open(tmp / "lab-light-100.png").convert("RGB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # R-SYS's left column carries the card-anatomy callouts in the concept sheet (1344x768).
    reference = Image.open(REF_SYS).convert("RGB")
    # R-SYS's card-anatomy block (a numbered callout list beside one collectible card) sits in the
    # sheet's right-upper quadrant.
    crop = reference.crop((660, 110, 960, 570))

    panel_w, panel_h = 660, 700
    sheet = Image.new("RGB", (panel_w * 2 + 72, 96 + panel_h), (250, 248, 243))
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 20), "Card anatomy: shipped primitives (left) vs R-SYS concept (right)", fill=(26, 23, 19), font=font)
    draw.text((24, 48), "Same six callouts; the product's are DOM text at the caption step.", fill=(92, 83, 71), font=font)
    draw.text((24, 74), "Component preview — not a live Desktop capture.", fill=(92, 83, 71), font=font)
    left = fitted(anatomy, panel_w, panel_h)
    right = fitted(crop, panel_w, panel_h)
    sheet.paste(left, (24, 96))
    sheet.paste(right, (48 + panel_w, 96))
    draw.rectangle([24, 96, 24 + panel_w - 1, 96 + panel_h - 1], outline=(205, 184, 148))
    draw.rectangle([48 + panel_w, 96, 47 + panel_w * 2, 96 + panel_h - 1], outline=(205, 184, 148))
    path = out / "anatomy-vs-rsys.png"
    sheet.save(path, optimize=True)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1049, help="route width the cells are captured at")
    parser.add_argument("--contact-only", action="store_true", help="rebuild the sheets from existing cells")
    args = parser.parse_args()

    if shutil.which("node") is None or shutil.which("chromium") is None:
        raise SystemExit("node and chromium are required to render the lab")

    OUT.mkdir(parents=True, exist_ok=True)
    if args.contact_only:
        stamp = json.loads((OUT / "lab.json").read_text(encoding="utf-8"))
    else:
        stamp = render_cells(OUT, args.width)

    contract = ROOT / "contracts" / "cb.tokens.v3.json"
    if stamp.get("plugin_sha256") != sha256(PLUGIN):
        raise SystemExit(
            "the cells were rendered from a different module than the checkout's desktop/plugin.js; "
            "re-run without --contact-only"
        )
    stamp["contract_sha256"] = sha256(contract)
    stamp["sheets"] = {
        "contact_sheet": "contact-sheet.png",
        "anatomy_vs_rsys": "anatomy-vs-rsys.png",
    }
    for name in ("contact-sheet.png", "anatomy-vs-rsys.png"):
        if not (OUT / name).exists() and args.contact_only:
            raise SystemExit(f"{name} is missing; run without --contact-only")

    contact = build_contact_sheet(OUT)
    anatomy = build_anatomy_panel(OUT, args.width)
    stamp["sheets"]["contact_sheet_sha256"] = sha256(contact)
    stamp["sheets"]["anatomy_vs_rsys_sha256"] = sha256(anatomy)
    (OUT / "lab.json").write_text(f"{json.dumps(stamp, indent=2)}\n", encoding="utf-8")
    print(f"contact sheet: {contact.relative_to(ROOT)} ({sha256(contact)[:12]})")
    print(f"anatomy panel: {anatomy.relative_to(ROOT)} ({sha256(anatomy)[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
