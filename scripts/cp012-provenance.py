#!/usr/bin/env python3
"""CP-012 provenance: hash every A3 file and write the machine record.

Reads `audit/cp012-covers/prompts.json` (prompt text, provider media URL, raw file)
and the shipped cover files, then writes `audit/cp012-covers/provenance.json`.

Nothing here is typed from memory: every hash, dimension, byte count and paper
sample is printed by this script from the file on disk, so a changed file and a
changed document fail together.

Usage:
    python3 scripts/cp012-provenance.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit" / "cp012-covers"
COVERS = ROOT / "assets" / "art" / "covers"
PAPER = (247, 241, 228)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def magick(*args: str) -> str:
    r = subprocess.run(("magick",) + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"magick failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def measure(path: Path) -> dict:
    dims = magick(str(path), "-format", "%w %h %[channels]", "info:").split()
    corner = magick(
        str(path), "-gravity", "northeast", "-crop", "32x32+0+0", "+repage",
        "-format", "%[fx:round(255*mean.r)] %[fx:round(255*mean.g)] %[fx:round(255*mean.b)]",
        "info:")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "width": int(dims[0]),
        "height": int(dims[1]),
        "channels": dims[2],
        "paper_corner": [int(v) for v in corner.split()],
    }


def main() -> int:
    prompts = json.loads((AUDIT / "prompts.json").read_text())
    rows = []
    for src in prompts["rows"]:
        raw = ROOT / src["raw"]

        slug = {
            "japanese-affection-context-l0": "japanese",
            "parent-measurement-practice": "parent",
            "technical-demo-pack": "technical",
        }[src["pack"]]

        shipped = [
            COVERS / f"{slug}-master-1200x800.png",
            COVERS / f"{slug}-crop-3x2-1200x800.png",
            COVERS / f"{slug}-crop-4x5-640x800.png",
        ]
        rows.append({
            "id": src["id"],
            "pack": src["pack"],
            "prompt_sha256": hashlib.sha256(src["prompt"].encode()).hexdigest(),
            "prompt_chars": len(src["prompt"]),
            "round": src["round"],
            "provider": prompts["provider"],
            "media_url": src["media_url"],
            "generated_on": prompts["generated_at"],
            "raw": measure(raw),
            "shipped": [measure(p) for p in shipped],
            "pipeline": {
                "prep": "scripts/cp012-cover-prep.py",
                "temper": "-modulate 97,78,100",
                "paper_match": "corner scaled onto #f7f1e4, gain clamp 0.90-1.10",
                "master": "square raw -> measured ink box fitted to the 640x800 crop window "
                          "(16 px paper margin) -> Lanczos plate on a 1200x800 sheet of #f7f1e4",
                "crop_4x5": "640x800 centre crop of the master, no resampling",
                "crop_3x2": "byte-identical export of the master",
            },
            "owner_approval": "unsigned",
        })

    out = {
        "card": "CP-012",
        "branch": "wt/cp-012-covers",
        "art_authority": "docs/concept-parity/ART-BIBLE.md (painted plate medium) + docs/GM-SUBJECT-WORLDS.md (subject worlds)",
        "provider": prompts["provider"],
        "generated_on": prompts["generated_at"],
        "target_paper": list(PAPER),
        "rows": rows,
        "claims_not_made": [
            "no model id, because the host tool does not report one",
            "no human illustrator, native-speaker or colour-professional review",
            "no claim that the fallback press plates were replaced by this kit in the packs (CP-014 integrates)",
            "no owner signature: the contact sheet is submitted for approval, not approved",
        ],
    }
    (AUDIT / "provenance.json").write_text(json.dumps(out, indent=2) + "\n")
    for r in rows:
        print(f"{r['pack']:34s} prompt {r['prompt_sha256'][:16]} "
              f"master {r['shipped'][0]['sha256'][:16]} {r['shipped'][0]['bytes']}B")
    print(f"wrote {AUDIT / 'provenance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
