#!/usr/bin/env python3
"""CP-013 provenance rows: hash every prompt and every shipped plate.

Nothing here is typed by hand except the provider's returned media URLs, which are recorded in
`MEDIA_URL` because the host image tool returns them and nothing else. The output is the machine
record `audit/cp013-scenes/provenance.json`; the markdown table printed to stdout is pasted into
`docs/concept-parity/ART-PROVENANCE.md` without editing a value.

Usage: python3 scripts/cp013-provenance.py
"""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(HERE, "audit", "cp013-scenes")

MEDIA_URL = {
    "A4-banner-r3": "https://v3b.fal.media/files/b/0ab1ed0e/wlc4cUboeU9AvSr27IYsK_FW8iDjfQ.png",
    "A4-cafe": "https://v3b.fal.media/files/b/0ab1ecf7/6qH3m5cDMTuHd-ZsKj11G_A938Nki5.png",
    "A4-map": "https://v3b.fal.media/files/b/0ab1ecf7/rsfnzMpKMmpXR9LZsrVgH_jwo19DD2.png",
    "A5-stamp-rim": "https://v3b.fal.media/files/b/0ab1ecf8/8dYXzlqQu2gJlb8QPGLco_Ts4iyRiA.png",
    "A5-medallion-rim": "https://v3b.fal.media/files/b/0ab1ecf8/ELIesa8CJXblpDqVabtnI_GtHWgMq9.png",
    "A5-clock": "https://v3b.fal.media/files/b/0ab1ecf8/j7PqHrNn4p4ZpN4NA8M6D_GtPIkaxL.png",
    "A5-tag": "https://v3b.fal.media/files/b/0ab1ecf8/tzAc1aE1MoujqbY4kpth1_cwISStgb.png",
    "A5-ticket": "https://v3b.fal.media/files/b/0ab1ecf9/6xF6AF5kcp7MRoQi7uycp_rWIQaZev.png",
    "A5-passport-tray-r2": "https://v3b.fal.media/files/b/0ab1ed0e/b3Pjsj2zNLGXn2Cye3Znx_3x1EDwjM.png",
    "A5-shelf-plank": "https://v3b.fal.media/files/b/0ab1ecf9/y2qAhByYzMalzbm2MV8ao_y1GIwNX0.png",
}

RAW = {
    "A4-banner-r3": "audit/cp013-scenes/raw/scene-banner-raw-r3.png",
    "A4-cafe": "audit/cp013-scenes/raw/scene-cafe-raw.png",
    "A4-map": "audit/cp013-scenes/raw/scene-map-raw.png",
    "A5-stamp-rim": "audit/cp013-scenes/raw/object-stamp-rim-raw.png",
    "A5-medallion-rim": "audit/cp013-scenes/raw/object-medallion-rim-raw.png",
    "A5-clock": "audit/cp013-scenes/raw/object-clock-raw.png",
    "A5-tag": "audit/cp013-scenes/raw/object-tag-raw.png",
    "A5-ticket": "audit/cp013-scenes/raw/object-ticket-raw.png",
    "A5-passport-tray-r2": "audit/cp013-scenes/raw/object-passport-tray-raw-r2.png",
    "A5-shelf-plank": "audit/cp013-scenes/raw/object-shelf-plank-raw.png",
}

ASSET = {
    "A4-banner-r3": "assets/art/scenes/discover-banner.png",
    "A4-cafe": "assets/art/scenes/lesson-cafe.png",
    "A4-map": "assets/art/scenes/course-map.png",
    "A5-stamp-rim": "assets/art/objects/stamp-rim.png",
    "A5-medallion-rim": "assets/art/objects/medallion-rim.png",
    "A5-clock": "assets/art/objects/clock.png",
    "A5-tag": "assets/art/objects/tag.png",
    "A5-ticket": "assets/art/objects/ticket.png",
    "A5-passport-tray-r2": "assets/art/objects/passport-tray.png",
    "A5-shelf-plank": "assets/art/objects/shelf-plank.png",
}


def sha(path):
    if not os.path.exists(path):
        return "MISSING"
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def ocr(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(AUDIT, "ocr", stem + ".txt")
    if not os.path.exists(out):
        return {"run": False, "text": ""}
    text = open(out, encoding="utf-8").read().replace("\f", "").strip()
    return {"run": True, "psm": 3, "text": text}


def size(path):
    from PIL import Image

    with Image.open(path) as im:
        return im.size


def main():
    prompts = json.load(open(os.path.join(AUDIT, "prompts.json"), encoding="utf-8"))
    previous = {}
    prov_path = os.path.join(AUDIT, "provenance.json")
    if os.path.exists(prov_path):
        for row in json.load(open(prov_path, encoding="utf-8"))["rows"]:
            previous[row["prompt_id"]] = row.get("recorded_at")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for prompt in prompts["prompts"]:
        pid = prompt["id"]
        asset = ASSET[pid]
        width, height = size(os.path.join(HERE, asset))
        rows.append({
            "prompt_id": pid,
            "plate": prompt["plate"],
            "round": prompt["round"],
            "kind": "scene" if asset.startswith("assets/art/scenes/") else "object",
            "prompt": prompt["prompt"][:80] + ("…" if len(prompt["prompt"]) > 80 else ""),
            "prompt_sha256": hashlib.sha256(prompt["prompt"].encode("utf-8")).hexdigest(),
            "provider": "host image_generate (nous image gateway); model id not reported by the host tool",
            "media_url": MEDIA_URL[pid],
            "raw_asset": RAW[pid],
            "raw_sha256": sha(os.path.join(HERE, RAW[pid])),
            "asset": asset,
            "asset_sha256": sha(os.path.join(HERE, asset)),
            "bytes": os.path.getsize(os.path.join(HERE, asset)),
            "width": width,
            "height": height,
            "ocr": ocr(os.path.join(HERE, RAW[pid])),
            "recorded_at": previous.get(pid, now),
        })

    rejected = []
    for item in prompts["rejected"]:
        rejected.append({
            "prompt_id": item["id"],
            "plate": item["plate"],
            "round": item["round"],
            "media_url": item["media_url"],
            "raw_sha256": item["raw_sha256"],
            "bytes_kept": False,
            "reason": item["reason"],
        })

    document = {
        "card": "CP-013",
        "bible": prompts["bible"],
        "recorded_at": now,
        "rows": rows,
        "rejected": rejected,
    }
    with open(prov_path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2)
        fh.write("\n")

    print("| plate | prompt | prompt_hash (16) | asset sha256 (16) | bytes | OCR | round |")
    print("|---|---|---|---|---|---|---|")
    for row in rows:
        text = row["ocr"]["text"]
        print("| `%s` | %s | `%s` | `%s` | %d | %s | %d |" % (
            row["plate"], row["prompt_id"], row["prompt_sha256"][:16], row["asset_sha256"][:16],
            row["bytes"], "no text" if not text else "found text", row["round"]))
    print("\nrejected rounds recorded, bytes deleted: %d" % len(rejected))
    print("wrote %s" % os.path.relpath(prov_path, HERE))


if __name__ == "__main__":
    main()
