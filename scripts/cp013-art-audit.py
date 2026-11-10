#!/usr/bin/env python3
"""CP-013 measured audit: what the scene plates and object blanks actually are.

Writes `audit/cp013-scenes/art-audit.json`. Every number in the provenance document is copied from
this file, never typed from memory. The script judges only what a pixel can settle:

* a scene's aspect ratio and its **reserved quiet field** — the detail energy and the luminance
  spread under the rectangle where DOM type will sit, plus the WCAG contrast between the contract's
  `ink` value and the darkest 5 % of that field;
* the pure-black fraction of every plate (the art bible forbids a black contour);
* the **cool-pigment** share of every plate (`b - max(r, g) > 10`) and, for the two plates that
  carry one, how much of it falls outside the named noren region the bible ratifies under ruling
  `D-CP013-A`. That is the measurement `test_no_scene_carries_a_pigment_outside_the_bible_palette`
  enforces: one cool pigment, one cloth, one region, nothing else;
* for an object: binary alpha, zero chroma residue on opaque pixels, the transparent margin, and —
  for the rims — that the centre really is a blank for a runtime `sdk.Codicon`.

It does not judge whether a plate is beautiful. That is the contact sheet and the reviewer's eye.

Usage: python3 scripts/cp013-art-audit.py
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "assets" / "art" / "scenes"
OBJECTS = ROOT / "assets" / "art" / "objects"
OUT = ROOT / "audit" / "cp013-scenes" / "art-audit.json"
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"

#: plate -> (reserved field as fractions of the plate: x0, y0, x1, y1, why)
#: SPEC-V3 D5: the banner's quiet field is the left 40 %, inset by its own inner pad.
#: SPEC-V3 §5.4: the course-home hero plate (M4) reserves the course title; the map's field is its
#: upper-left third, measured on the 16:9 master. The cafe frame is a scene, not a type ground: C6
#: carries the line, C5 the art.
QUIET_FIELD = {
    "discover-banner": (0.0, 0.0, 0.40, 1.0),
    "course-map": (0.0, 0.0, 0.33, 0.45),
}

#: The one ratified cool pigment — noren indigo — measured, not assumed. ART-BIBLE §9 rule 5 and
#: §2 carry the exception as ruling `D-CP013-A`; these boxes are the named noren regions on the two
#: shipped plates, in pixels, and each one sits outside that plate's quiet field.
NOREN = {
    "discover-banner": (700, 0, 961, 160),
    "lesson-cafe": (760, 20, 1024, 310),
}

#: A pigment is "strongly cool" when blue leads both other channels by more than this.
COOL_LEAD = 10

#: object -> centre probe: only the two rims take a runtime icon, so only they must carry a blank
CENTRE = {
    "stamp-rim": ("flat", 0.18),
    "medallion-rim": ("flat", 0.22),
}


def rel_lum(rgb):
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (chan(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def quantile(gray, fraction):
    hist = gray.histogram()
    total = sum(hist)
    acc = 0
    for value, count in enumerate(hist):
        acc += count
        if acc >= total * fraction:
            return value
    return 255


def cool_share(img, box=None):
    """Share of the plate (or of the plate outside ``box``) whose blue leads both other channels.

    The metric is the one the reviewer measured: ``b - max(r, g) > COOL_LEAD``. It reads a pigment
    as cool on the pixel, not on an average that would hide a small saturated mass.
    """
    width, height = img.size
    px = img.load()
    inside = outside = 0
    for y in range(height):
        for x in range(width):
            r, g, b = px[x, y]
            if b - max(r, g) <= COOL_LEAD:
                continue
            if box and box[0] <= x < box[2] and box[1] <= y < box[3]:
                inside += 1
            else:
                outside += 1
    return inside, outside


def scene_row(path, ink):
    img = Image.open(path).convert("RGB")
    width, height = img.size
    gray = img.convert("L")
    row = {
        "file": str(path.relative_to(ROOT)),
        "kind": "scene",
        "width": width,
        "height": height,
        "aspect": round(width / height, 3),
    }
    dark = sum(gray.histogram()[:8]) / (width * height)
    row["pure_black_fraction"] = round(dark, 5)

    #: The darkest 5 % of the plate must be a warm pigment family, not neutral black or blue-grey.
    cutoff = quantile(gray, 0.05)
    total = 0
    sums = [0, 0, 0]
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            lum = gray.getpixel((x, y))
            px = img.getpixel((x, y))
            if not isinstance(lum, int) or not isinstance(px, tuple):
                continue
            if lum <= cutoff:
                sums[0] += px[0]
                sums[1] += px[1]
                sums[2] += px[2]
                total += 1
    if total:
        tint = [round(v / total) for v in sums]
        row["dark_tint"] = {"rgb": tint, "hex": "#%02x%02x%02x" % tuple(tint),
                            "warm": tint[0] >= tint[2] and tint[0] + 2 >= tint[1]}

    box = NOREN.get(path.stem)
    cool_in, cool_out = cool_share(img, box)
    row["cool_share_of_plate"] = round((cool_in + cool_out) / (width * height), 5)
    if box:
        area = (box[2] - box[0]) * (box[3] - box[1])
        out_lum = []
        out_rgb = []
        for y in range(0, height, 2):
            for x in range(0, width, 2):
                inside = box[0] <= x < box[2] and box[1] <= y < box[3]
                if inside:
                    continue
                px = img.getpixel((x, y))
                out_lum.append(0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2])
                out_rgb.append(px)
        out_cutoff = sorted(out_lum)[max(0, int(0.05 * len(out_lum)) - 1)] if out_lum else 0
        n = 0
        acc = [0, 0, 0]
        for lum, px in zip(out_lum, out_rgb):
            if lum <= out_cutoff:
                acc = [a + c for a, c in zip(acc, px)]
                n += 1
        out_tint = [round(v / n) for v in acc] if n else [0, 0, 0]
        row["noren"] = {
            "ruling": "D-CP013-A",
            "box_px": list(box),
            "share_of_plate": round(area / (width * height), 3),
            "cool_share_of_plate": row["cool_share_of_plate"],
            "cool_share_outside_region": round(cool_out / (width * height), 5),
            "dark_tint_outside_region": {
                "rgb": out_tint,
                "hex": "#%02x%02x%02x" % tuple(out_tint),
                "warm": out_tint[0] >= out_tint[2] and out_tint[0] + 2 >= out_tint[1],
            },
        }

    field = QUIET_FIELD.get(path.stem)
    if field:
        x0, y0, x1, y1 = field
        box = (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
        patch = img.crop(box)
        patch_gray = patch.convert("L")
        row["quiet_field"] = {
            "box_px": box,
            "share_of_plate": round((box[2] - box[0]) * (box[3] - box[1]) / (width * height), 3),
            "detail_energy": round(ImageStat.Stat(patch_gray.filter(ImageFilter.FIND_EDGES)).mean[0], 2),
            "luminance_median": quantile(patch_gray, 0.50),
            "luminance_p05": quantile(patch_gray, 0.05),
            "luminance_p95": quantile(patch_gray, 0.95),
            "ink_contrast_median": contrast(ink, (quantile(patch_gray, 0.50),) * 3),
            "ink_contrast_p05": contrast(ink, (quantile(patch_gray, 0.05),) * 3),
        }
    return row


def object_row(path):
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    alpha = img.getchannel("A")
    hist = alpha.histogram()
    opaque = sum(hist[9:])
    semi = sum(hist[1:9])
    bbox = alpha.getbbox()
    rgb = img.convert("RGB")
    gray = rgb.convert("L")
    black = 0
    for (r, g, b, a) in img.getdata():
        if a > 8 and r < 12 and g < 12 and b < 12:
            black += 1
    row = {
        "file": str(path.relative_to(ROOT)),
        "kind": "object",
        "width": width,
        "height": height,
        "opaque_fraction": round(opaque / (width * height), 3),
        "semi_transparent_pixels": semi,
        "bbox": list(bbox) if bbox else None,
        "pure_black_fraction_of_opaque": round(black / opaque, 5) if opaque else None,
        "footer_bytes": path.stat().st_size,
    }
    #: No cutout carries the ratified noren pigment, and none carries any other cool mass.
    cool_opaque = 0
    for (r, g, b, a) in img.getdata():
        if a > 8 and b - max(r, g) > COOL_LEAD:
            cool_opaque += 1
    row["cool_fraction_of_opaque"] = round(cool_opaque / opaque, 5) if opaque else None
    mode_radius = CENTRE.get(path.stem)
    if mode_radius is None:
        return row
    mode, radius = mode_radius
    cx, cy = width / 2, height / 2
    if mode == "transparent":
        # Largest fully transparent circle at the centre: the blank a 20 px Codicon sits in.
        free = 0
        while free < width / 2:
            r = free + 1
            ok = True
            for a in range(0, 360, 5):
                x = int(cx + r * math.cos(math.radians(a)))
                y = int(cy + r * math.sin(math.radians(a)))
                value = alpha.getpixel((x, y)) if 0 <= x < width and 0 <= y < height else 0
                if isinstance(value, int) and value > 8:
                    ok = False
                    break
            if not ok:
                break
            free = r
        row["centre_probe"] = {"mode": mode, "transparent_radius_px": free}
        return row
    r = radius * width
    inside = [
        (x, y)
        for y in range(int(cy - r), int(cy + r) + 1)
        for x in range(int(cx - r), int(cx + r) + 1)
        if (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    ]
    alphas = [alpha.getpixel(p) for p in inside]
    centre = {"mode": mode, "radius_fraction": radius}
    if mode == "transparent":
        centre["opaque_pixels"] = sum(1 for a in alphas if a > 8)
    else:
        patch = gray.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r)))
        centre["detail_energy"] = round(ImageStat.Stat(patch.filter(ImageFilter.FIND_EDGES)).mean[0], 2)
    row["centre_probe"] = centre
    return row


def main():
    ink = hex_rgb(json.loads(CONTRACT.read_text())["modes"]["light"]["ink"])
    rows = [scene_row(p, ink) for p in sorted(SCENES.glob("*.png"))]
    rows += [object_row(p) for p in sorted(OBJECTS.glob("*.png"))]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"ink": "#%02x%02x%02x" % ink, "plates": rows}, indent=2) + "\n")
    for row in rows:
        if row["kind"] == "scene":
            q = row.get("quiet_field", {})
            print("%-28s %dx%d aspect %.3f  black %.4f  %s"
                  % (row["file"], row["width"], row["height"], row["aspect"],
                     row["pure_black_fraction"],
                     "quiet detail %.2f ink contrast %s/%s" % (q["detail_energy"],
                                                               q["ink_contrast_median"],
                                                               q["ink_contrast_p05"]) if q else "no reserved field"))
        else:
            print("%-28s %dx%d opaque %.3f semi %d black %.4f centre %s"
                  % (row["file"], row["width"], row["height"], row["opaque_fraction"],
                     row["semi_transparent_pixels"], row["pure_black_fraction_of_opaque"] or 0,
                     row.get("centre_probe", "n/a")))
    print("wrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
