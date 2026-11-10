"""Render the CP-002 primary-action comparison on parchment.

Two legal ways to reach 4.5:1 for the one terracotta primary were offered in the card:

  A. keep the concept fill #db6c45 and put ink on it
  B. deepen the fill to #b4532f and put a cream label on it

This script draws both at contract values on the contract parchment and prints the computed
ratios. The PNG is a contract sample for the reviewer, not a product screenshot and not evidence
of a rendered route: nothing here is captured from the running app.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "contracts" / "cb.tokens.v3.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "docs" / "coursebook-visual-identity-v3"
OUT = OUT_DIR / "cta-choice.png"

SANS = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
SANS_BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
SERIF = "/usr/share/fonts/noto/NotoSerif-Bold.ttf"

LIGHT = CONTRACT["modes"]["light"]


def luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def ratio(a: str, b: str) -> float:
    x, y = luminance(a), luminance(b)
    hi, lo = max(x, y), min(x, y)
    return (hi + 0.05) / (lo + 0.05)


OPTIONS = [
    {
        "name": "A - concept fill, ink label",
        "fill": "#db6c45",
        "label": LIGHT["ink"],
        "note": "keeps the reference hue exactly",
    },
    {
        "name": "B - deepened fill, cream label (shipped)",
        "fill": LIGHT["terracotta"],
        "label": LIGHT["on-terracotta"],
        "note": "fill edge clears 3:1 against parchment too",
    },
]

W, H = 1200, 760
PAD = 72


def draw() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (W, H), LIGHT["canvas"])
    d = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(SERIF, 46)
    sub_font = ImageFont.truetype(SANS, 20)
    body_font = ImageFont.truetype(SANS, 24)
    bold_font = ImageFont.truetype(SANS_BOLD, 26)
    small_font = ImageFont.truetype(SANS, 17)

    d.text((PAD, PAD - 18), "One primary action, two legal fills", font=title_font, fill=LIGHT["ink"])
    d.text(
        (PAD, PAD + 46),
        "Contract sample for CP-002 - drawn on the contract parchment, not a product capture.",
        font=sub_font,
        fill=LIGHT["ink-soft"],
    )

    y = PAD + 128
    for option in OPTIONS:
        r = ratio(option["label"], option["fill"])
        d.text((PAD, y), option["name"], font=bold_font, fill=LIGHT["ink"])
        d.text((PAD, y + 36), option["note"], font=small_font, fill=LIGHT["ink-soft"])

        pill_w, pill_h = 320, 68
        pill_x = PAD
        pill_y = y + 72
        d.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=pill_h // 2,
            fill=option["fill"],
        )
        label = "Start a new course"
        tw = d.textlength(label, font=body_font)
        d.text(
            (pill_x + (pill_w - tw) / 2, pill_y + 20),
            label,
            font=body_font,
            fill=option["label"],
        )
        d.text(
            (pill_x + pill_w + 32, pill_y + 12),
            f"{r:.2f}:1  label on fill",
            font=body_font,
            fill=LIGHT["ink"],
        )
        d.text(
            (pill_x + pill_w + 32, pill_y + 42),
            f"{ratio(option['fill'], LIGHT['canvas']):.2f}:1  fill on parchment",
            font=small_font,
            fill=LIGHT["ink-soft"],
        )
        y += 210

    d.text(
        (PAD, H - 96),
        "Fail 4.5:1 = rejected. Both options pass the label floor; option B is the one the contract ships",
        font=small_font,
        fill=LIGHT["ink-soft"],
    )
    d.text(
        (PAD, H - 70),
        "because the primary also has to separate from parchment as an object (3:1), where A reaches only 2.68:1.",
        font=small_font,
        fill=LIGHT["ink-soft"],
    )

    img.save(OUT)
    for option in OPTIONS:
        print(f"{option['name']}: label {ratio(option['label'], option['fill']):.2f}:1, "
              f"fill on canvas {ratio(option['fill'], LIGHT['canvas']):.2f}:1")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    draw()
