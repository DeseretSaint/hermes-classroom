#!/usr/bin/env python3
"""CP-010 provenance rows: hash every prompt and every shipped asset.

Nothing here is typed by hand. The output is the machine record
`audit/cp010-fox/provenance.json`; the markdown table printed to stdout is pasted
into `docs/concept-parity/ART-PROVENANCE.md` without editing a value.

Usage: python3 scripts/cp010-provenance.py
"""
import hashlib
import json
import os
from datetime import datetime, timezone

PROMPT_TO_ASSET = {
    "M1": "assets/art/fox/fox-model-sheet.png",
    "P-wave": "assets/art/fox/fox-wave.png",
    "P-point-r3": "assets/art/fox/fox-point.png",
    "P-clock": "assets/art/fox/fox-clock.png",
    "P-read": "assets/art/fox/fox-read.png",
    "P-cheer": "assets/art/fox/fox-cheer.png",
    "P-think": "assets/art/fox/fox-think.png",
    "P-sleep": "assets/art/fox/fox-sleep.png",
}
POSE_NAME = {k: k.split("-", 1)[1] for k in PROMPT_TO_ASSET if k != "M1"}


def plate_of(pid):
    """fox-point-r3 is the third attempt at the plate fox-point, not a new plate."""
    name = POSE_NAME[pid]
    return name[:-3] if name[-3:-1] == "-r" and name[-1].isdigit() else name
RAW = {
    "M1": "audit/cp010-fox/raw/model-sheet-raw-r2.png",
    "P-wave": "audit/cp010-fox/raw/pose-wave-raw.png",
    "P-point-r3": "audit/cp010-fox/raw/pose-point-raw-r3.png",
    "P-clock": "audit/cp010-fox/raw/pose-clock-raw-r2.png",
    "P-read": "audit/cp010-fox/raw/pose-read-raw.png",
    "P-cheer": "audit/cp010-fox/raw/pose-cheer-raw.png",
    "P-think": "audit/cp010-fox/raw/pose-think-raw.png",
    "P-sleep": "audit/cp010-fox/raw/pose-sleep-raw.png",
}


def sha(path):
    if not os.path.exists(path):
        return "MISSING"
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    with open("audit/cp010-fox/prompts.json") as fh:
        prompts = {p["id"]: p for p in json.load(fh)["prompts"]}

    # Keep the first recorded generation timestamp for a plate that already has one: a re-run of
    # this script must not restamp a plate with the time the script ran. Only a genuinely new or
    # regenerated plate (new media URL) gets a new timestamp.
    previous = {}
    if os.path.exists("audit/cp010-fox/provenance.json"):
        with open("audit/cp010-fox/provenance.json") as fh:
            for row in json.load(fh)["rows"]:
                previous[row["plate_id"]] = row

    rows = []
    for pid, asset in PROMPT_TO_ASSET.items():
        p = prompts[pid]
        ocr_path = f"audit/cp010-fox/ocr-{'model-sheet' if pid == 'M1' else plate_of(pid)}-final.txt"
        ocr = "no text (psm 3)" if os.path.exists(ocr_path) and not open(ocr_path).read().strip() else "TEXT FOUND"
        plate_id = f"fox-{'model-sheet' if pid == 'M1' else plate_of(pid)}"
        old = previous.get(plate_id)
        generated_at = (
            old["generated_at"]
            if old and old.get("media_url") == p["media_url"]
            else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        rows.append({
            "plate_id": plate_id,
            "prompt_id": pid,
            "role": "character model sheet" if pid == "M1" else "character pose",
            "provider": "nous image gateway (media served from v3b.fal.media)",
            "model": "not reported by the host tool",
            "prompt_hash": hashlib.sha256(p["text"].encode()).hexdigest(),
            "reference_image_urls": p.get("reference_image_urls", []),
            "media_url": p["media_url"],
            "generated_at": generated_at,
            "raw_sha256": sha(RAW[pid]),
            "raw_asset": RAW[pid],
            "asset": asset,
            "asset_sha256": sha(asset),
            "bytes": os.path.getsize(asset) if os.path.exists(asset) else 0,
            "text_check": ocr,
        })

    with open("audit/cp010-fox/provenance.json", "w") as fh:
        json.dump({"rows": rows}, fh, indent=2)

    print("| plate | prompt id | prompt_hash | asset | sha256 | OCR |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| `{r['plate_id']}` | {r['prompt_id']} | `{r['prompt_hash'][:16]}…` | "
              f"`{r['asset']}` | `{r['asset_sha256'][:16]}…` | {r['text_check']} |")
    print()
    for r in rows:
        print(f"{r['plate_id']}: prompt {r['prompt_hash']}")
        print(f"  raw {r['raw_sha256']}")
        print(f"  asset {r['asset_sha256']} ({r['bytes']} bytes)")


if __name__ == "__main__":
    main()
