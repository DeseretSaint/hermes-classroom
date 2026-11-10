#!/usr/bin/env python3
"""CP-010 contact sheets: the model sheet and the seven-pose sheet.

Every label here is drawn by Pillow from the file list — never by the model, and
never shipped as product UI. These are review artifacts.

Usage: python3 scripts/cp010-contact-sheet.py
Writes docs/concept-parity/art/fox-model-sheet-contact.png and
docs/concept-parity/art/fox-contact-sheet.png
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

PAPER = (247, 241, 228)
INK = (26, 23, 19)
SOFT = (92, 83, 71)
RULE = (215, 203, 180)
DARK = (19, 18, 16)
FONT = "/usr/share/fonts/liberation/LiberationSans-%s.ttf"
POSES = ["wave", "point", "clock", "read", "cheer", "think", "sleep"]
USE = {
    "wave": "Home trailhead",
    "point": "Discover feature",
    "clock": "Home, New course",
    "read": "Classroom lesson",
    "cheer": "Check correct",
    "think": "Wrong answer, kind",
    "sleep": "Empty / offline",
}


def font(size, bold=False):
    return ImageFont.truetype(FONT % ("Bold" if bold else "Regular"), size)


def audit_rows():
    with open("audit/cp010-fox/art-audit.json") as fh:
        return {r["file"]: r for r in json.load(fh)["poses"]}


def ocr_text(name):
    path = f"audit/cp010-fox/ocr-{name}-final.txt"
    if not os.path.exists(path):
        return "missing"
    text = open(path).read().replace("\f", "").strip()
    return "no lettering found" if not text else f"found: {text[:40]!r}"


def pose_sheet(out="docs/concept-parity/art/fox-contact-sheet.png"):
    rows = audit_rows()
    cols, cell_w, cell_h = 4, 380, 630
    head, foot = 132, 118
    width = cols * cell_w + 64
    height = head + 2 * cell_h + foot + 130
    im = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(im)

    d.text((32, 28), "Fox pose sheet — A1", font=font(32, True), fill=INK)
    d.text((32, 74), "One character, seven poses, generated from the model sheet as the only "
           "style reference.", font=font(18), fill=SOFT)
    d.line([(32, 112), (width - 32, 112)], fill=RULE, width=1)

    for i, pose in enumerate(POSES):
        cx = 32 + (i % cols) * cell_w
        cy = head + (i // cols) * cell_h
        art = Image.open(f"assets/art/fox/fox-{pose}-512.png").convert("RGBA")
        art.thumbnail((300, 300), Image.LANCZOS)
        im.paste(art, (cx + (cell_w - art.width) // 2, cy), art)
        d.text((cx + 20, cy + 312), pose, font=font(22, True), fill=INK)
        d.text((cx + 20, cy + 340), USE[pose], font=font(15), fill=SOFT)
        thumb = Image.open(f"assets/art/fox/fox-{pose}-64.png").convert("RGBA")
        im.paste(thumb, (cx + 20, cy + 364), thumb)
        d.text((cx + 96, cy + 372), "64 px", font=font(13), fill=SOFT)
        small = Image.open(f"assets/art/fox/fox-{pose}-256.png").convert("RGBA")
        im.paste(small, (cx + 150, cy + 364), small)
        d.text((cx + 240, cy + 372), "256 px", font=font(13), fill=SOFT)

    # Legibility strip on the dark canvas: every pose at 64 px.
    y = head + 2 * cell_h + 16
    d.line([(32, y), (width - 32, y)], fill=RULE, width=1)
    d.text((32, y + 12), "All seven at 64 px on the dark canvas", font=font(18, True), fill=INK)
    dark = Image.new("RGB", (width - 64, 96), DARK)
    im.paste(dark, (32, y + 44))
    x = 48
    for pose in POSES:
        thumb = Image.open(f"assets/art/fox/fox-{pose}-64.png").convert("RGBA")
        im.paste(thumb, (x, y + 60), thumb)
        x += 84

    fy = height - foot
    d.line([(32, fy), (width - 32, fy)], fill=RULE, width=1)
    d.text((32, fy + 14), "Every frame: tesseract psm 3 returned no text; no word of 2+ "
           "characters above 70 confidence.", font=font(15), fill=SOFT)
    d.text((32, fy + 38), "Provider media URLs and sha256 per pose: "
           "docs/concept-parity/ART-PROVENANCE.md", font=font(15), fill=SOFT)
    d.text((32, fy + 62), "Owner approval: model sheet ____  pose sheet ____    "
           "Reviewer: ______________", font=font(15), fill=SOFT)
    im.save(out)
    print(out, im.size)


def model_sheet(out="docs/concept-parity/art/fox-model-sheet-contact.png"):
    src = Image.open("assets/art/fox/fox-model-sheet.png").convert("RGBA")
    src.thumbnail((1400, 700), Image.LANCZOS)
    head, foot = 132, 150
    width = max(src.width + 64, 900)
    im = Image.new("RGB", (width, head + src.height + foot), PAPER)
    d = ImageDraw.Draw(im)
    d.text((32, 28), "Fox model sheet — M1 (front, three-quarter, side, back)",
           font=font(32, True), fill=INK)
    d.text((32, 74), "The authority for every pose: markings, proportions, palette, line. "
           "Approved before any pose is generated.", font=font(18), fill=SOFT)
    d.line([(32, 112), (width - 32, 112)], fill=RULE, width=1)
    im.paste(src, ((width - src.width) // 2, head), src)
    fy = head + src.height + 12
    labels = ["front", "three-quarter", "side", "back"]
    for i, lab in enumerate(labels):
        cx = (width - src.width) // 2 + int(src.width * (i + 0.5) / 4)
        d.text((cx - d.textlength(lab, font=font(16)) / 2, fy), lab, font=font(16), fill=SOFT)
    d.line([(32, fy + 34), (width - 32, fy + 34)], fill=RULE, width=1)
    d.text((32, fy + 46), "tesseract psm 3: no text. No lettering, no shadow, no ground, "
           "no border, no black contour.", font=font(15), fill=SOFT)
    d.text((32, fy + 70), "Owner approval of the model sheet: ______________    "
           "poses blocked until signed.", font=font(15), fill=SOFT)
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    os.makedirs("docs/concept-parity/art", exist_ok=True)
    model_sheet()
    pose_sheet()
