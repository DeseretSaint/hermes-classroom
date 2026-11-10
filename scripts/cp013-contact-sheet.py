#!/usr/bin/env python3
"""CP-013 review sheets: the three scene plates and the seven object blanks.

Every label is drawn by Pillow from the audit JSON and the file list — never by the model, and never
shipped as product UI. These are review artifacts for the owner and the reviewer.

Usage: python3 scripts/cp013-contact-sheet.py
Writes docs/concept-parity/art/cp013-scenes.png and docs/concept-parity/art/cp013-objects.png
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

SCENE_USE = {
    "discover-banner": ("Discover feature banner ground", "4.4:1 — DOM title and primary on the quiet field"),
    "lesson-cafe": ("Classroom lesson frame", "16:9 — cropped mechanically to the 3:1 frame at render"),
    "course-map": ("Course-home expedition ground", "16:9 — route nodes are DOM over the plate"),
}
OBJECT_USE = {
    "stamp-rim": "Stamp-node rim · Codicon centre",
    "medallion-rim": "Medallion rim · one per recorded event",
    "passport-tray": "Passport tray · evidence",
    "ticket": "Ticket · evidence",
    "clock": "Brass alarm clock · prop, 10:10",
    "tag": "Kraft tag blank · DOM line",
    "shelf-plank": "Shelf plank · wood ledge",
}


def font(size, bold=False):
    return ImageFont.truetype(FONT % ("Bold" if bold else "Regular"), size)


def audit_rows():
    with open("audit/cp013-scenes/art-audit.json") as fh:
        return {r["file"].rsplit("/", 1)[-1]: r for r in json.load(fh)["plates"]}


def ocr_text(plate):
    """Read the recorded text check from provenance.json, keyed by plate id."""
    with open("audit/cp013-scenes/provenance.json") as fh:
        for row in json.load(fh)["rows"]:
            if row["plate"] == plate:
                if not row["ocr"]["run"]:
                    return "text check not recorded"
                return "no lettering found" if not row["ocr"]["text"] else "found: %r" % row["ocr"]["text"][:40]
    return "plate not in provenance"


def scene_sheet(out="docs/concept-parity/art/cp013-scenes.png"):
    rows = audit_rows()
    plates = ["discover-banner", "course-map", "lesson-cafe"]
    width = 1100
    cell_h = 430
    head, foot = 150, 200
    im = Image.new("RGB", (width, head + 3 * cell_h + foot), PAPER)
    d = ImageDraw.Draw(im)
    d.text((32, 28), "Scene plates — A4", font=font(32, True), fill=INK)
    d.text((32, 74), "Textless gouache plates. The reserved quiet field is outlined where DOM type "
           "will sit; the nodes, pins and labels are never painted.",
           font=font(17), fill=SOFT)
    d.text((32, 100), "Terracotta outline = quiet field.  Violet outline = the ratified noren region "
           "(D-CP013-A), the one cool pigment a plate may carry.",
           font=font(14), fill=SOFT)
    d.line([(32, 126), (width - 32, 126)], fill=RULE, width=1)

    for i, plate in enumerate(plates):
        y = head + i * cell_h
        row = rows["%s.png" % plate]
        art = Image.open("assets/art/scenes/%s.png" % plate).convert("RGB")
        box_w = 700
        art.thumbnail((box_w, 260), Image.Resampling.LANCZOS)
        im.paste(art, (32, y + 16))
        title, use = SCENE_USE[plate]
        d.text((32, y + 16 + art.height + 14), title, font=font(21, True), fill=INK)
        d.text((32, y + 16 + art.height + 42), use, font=font(15), fill=SOFT)
        q = row.get("quiet_field")
        stats = ["%dx%d  aspect %.3f" % (row["width"], row["height"], row["aspect"])]
        if q:
            left, top, right, bottom = q["box_px"]
            sx = art.width / row["width"]
            sy = art.height / row["height"]
            d.rectangle([32 + left * sx, y + 16 + top * sy, 32 + right * sx, y + 16 + bottom * sy],
                        outline=(180, 84, 47), width=2)
            stats.append("quiet field detail %.2f" % q["detail_energy"])
            stats.append("ink contrast %.2f (p05) / %.2f (median)"
                         % (q["ink_contrast_p05"], q["ink_contrast_median"]))
        if row.get("noren"):
            left, top, right, bottom = row["noren"]["box_px"]
            sx = art.width / row["width"]
            sy = art.height / row["height"]
            d.rectangle([32 + left * sx, y + 16 + top * sy, 32 + right * sx, y + 16 + bottom * sy],
                        outline=(91, 90, 160), width=2)
        stats.append("pure black %.3f%%" % (row["pure_black_fraction"] * 100))
        stats.append("darkest 5%% %s" % row.get("dark_tint", {}).get("hex", "n/a"))
        noren = row.get("noren")
        if noren:
            stats.append("noren indigo %.3f%% (D-CP013-A)"
                         % (noren["cool_share_of_plate"] * 100,))
            stats.append("cool outside region %.3f%%" % (noren["cool_share_outside_region"] * 100,))
        else:
            stats.append("cool pigment %.3f%%" % (row["cool_share_of_plate"] * 100))
        for j, line in enumerate(stats):
            d.text((760, y + 24 + j * 26), line, font=font(15), fill=SOFT)
        d.text((760, y + 24 + len(stats) * 26 + 8), ocr_text(plate),
               font=font(15), fill=SOFT)

    fy = head + 3 * cell_h
    d.line([(32, fy), (width - 32, fy)], fill=RULE, width=1)
    d.text((32, fy + 14), "No plate is embedded: scenes stay pack or world media on the media "
           "route (assets/README.md).", font=font(15), fill=SOFT)
    d.text((32, fy + 40), "Provider media URLs, prompt hashes and per-plate sha256: "
           "docs/concept-parity/ART-PROVENANCE-A4A5.md", font=font(15), fill=SOFT)
    d.text((32, fy + 66), "Owner approval: scenes ____    Reviewer: ______________",
           font=font(15), fill=SOFT)
    im.save(out)
    print(out, im.size)


def object_sheet(out="docs/concept-parity/art/cp013-objects.png"):
    rows = audit_rows()
    names = list(OBJECT_USE)
    cols, cell_w, cell_h = 4, 260, 300
    head, foot = 132, 190
    width = cols * cell_w + 64
    im = Image.new("RGB", (width, head + 2 * cell_h + foot), PAPER)
    d = ImageDraw.Draw(im)
    d.text((32, 28), "Object blanks — A5", font=font(32, True), fill=INK)
    d.text((32, 74), "Cutouts at 256 px. Nothing here carries a letter: the Codicon and the label "
           "are added at runtime.", font=font(17), fill=SOFT)
    d.line([(32, 112), (width - 32, 112)], fill=RULE, width=1)

    for i, name in enumerate(names):
        cx = 32 + (i % cols) * cell_w
        cy = head + (i // cols) * cell_h
        art = Image.open("assets/art/objects/%s.png" % name).convert("RGBA")
        big = art.copy()
        big.thumbnail((150, 150), Image.Resampling.LANCZOS)
        im.paste(big, (cx + 24, cy + 8), big)
        d.text((cx + 24, cy + 166), name, font=font(18, True), fill=INK)
        d.text((cx + 24, cy + 190), OBJECT_USE[name], font=font(13), fill=SOFT)
        row = rows["%s.png" % name]
        centre = row.get("centre_probe")
        note = "centre: %s" % (centre["mode"] if centre else "prop, no icon")
        d.text((cx + 24, cy + 212), note, font=font(13), fill=SOFT)
        d.text((cx + 24, cy + 232), "black %.3f%%  alpha edges %d"
               % ((row["pure_black_fraction_of_opaque"] or 0) * 100, row["semi_transparent_pixels"]),
               font=font(13), fill=SOFT)

    # Dark canvas strip: every blank at 48 px, the stamp-node's real size.
    y = head + 2 * cell_h + 10
    d.line([(32, y), (width - 32, y)], fill=RULE, width=1)
    d.text((32, y + 10), "All seven at 48 px on the dark canvas", font=font(17, True), fill=INK)
    dark = Image.new("RGB", (width - 64, 74), DARK)
    im.paste(dark, (32, y + 42))
    x = 48
    for name in names:
        small = Image.open("assets/art/objects/%s.png" % name).convert("RGBA")
        small.thumbnail((48, 48), Image.Resampling.LANCZOS)
        im.paste(small, (x, y + 56), small)
        x += 90

    fy = head + 2 * cell_h + foot - 84
    d.line([(32, fy), (width - 32, fy)], fill=RULE, width=1)
    d.text((32, fy + 12), "Every plate: no OCR token of two or more characters clears 70 confidence; "
           "the rim centres are a measured blank for sdk.Codicon.", font=font(14), fill=SOFT)
    d.text((32, fy + 36), "Pipeline: scripts/cp013-scene-prep.py → assets/objects/*.webp via "
           "scripts/build_cb_assets.py.", font=font(14), fill=SOFT)
    d.text((32, fy + 60), "Owner approval: objects ____    Reviewer: ______________",
           font=font(14), fill=SOFT)
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    os.makedirs("docs/concept-parity/art", exist_ok=True)
    scene_sheet()
    object_sheet()
