#!/usr/bin/env python3
"""CP-000 — frame inventory for the visual-review packets.

Every PNG committed under `docs/visual-review/` must be accounted for: either a manifest row that
names it (with the packet's stated capture path and module sha), or an explicit `unverifiable`
entry naming why it cannot be classified. A packet image with no row is exactly the provenance hole
CP-000 exists to close, so this script fails `--check` when the committed inventory and the disk /
manifests disagree.

    python3 scripts/cp-frame-inventory.py                 # write the inventory
    python3 scripts/cp-frame-inventory.py --check         # verify it against disk + manifests

Packets:
    docs/visual-review/gm-002                    live-evidence.json  (live rig)
    docs/visual-review/gm-002/renderer-frames    evidence.json       (static render)
    docs/visual-review/gm-004                    live-evidence.json  (live rig)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VISUAL = ROOT / "docs" / "visual-review"
DEFAULT_OUT = ROOT / "docs" / "concept-parity" / "frame-inventory.json"

PACKETS = [
    {"id": "gm-002", "dir": VISUAL / "gm-002", "manifest": "live-evidence.json"},
    {"id": "gm-002/renderer-frames", "dir": VISUAL / "gm-002" / "renderer-frames", "manifest": "evidence.json"},
    {"id": "gm-004", "dir": VISUAL / "gm-004", "manifest": "live-evidence.json"},
]

# Frames that exist on disk with no manifest row. Each needs a recorded reason and a classification;
# the report must name the truly unverifiable ones, because an unlisted frame can never be evidence.
UNVERIFIABLE = {
    "gm-002": {
        "home.course--460--light--200--continue.png": {
            "classification": "unverifiable",
            "reason": (
                "No row in gm-002/live-evidence.json: no module sha, state dir, hash or captured state. "
                "Present on disk only; cannot be classified as live or static and must not be used as evidence."
            ),
        },
    },
    "gm-002/renderer-frames": {
        "home.course--1049--light--100--no-outline.png": {
            "classification": "static-render",
            "reason": (
                "Still from the static-render packet (scripts/gm002-shot.mjs); evidence.json records the "
                "frame by id but carries no per-file row and no plugin sha. Static render, never evidence."
            ),
        },
        "home.global--900--light--100--overflow.png": {
            "classification": "static-render",
            "reason": (
                "Still from the static-render packet (scripts/gm002-shot.mjs); evidence.json records the "
                "frame by id but carries no per-file row and no plugin sha. Static render, never evidence."
            ),
        },
    },
    "gm-004": {},
}


def file_digest(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.md5(data).hexdigest(), len(data)


def build() -> dict:
    packets = {}
    for packet in PACKETS:
        directory: Path = packet["dir"]
        manifest_path = directory / packet["manifest"]
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        rows = manifest.get("frames") or []
        by_file = {row.get("file"): row for row in rows if row.get("file")}
        kind = str(manifest.get("kind") or "")
        classification = "static-render" if "static render" in kind else "live-rig" if "live capture" in kind else "unknown"
        frames = []
        for png in sorted(directory.glob("*.png")):
            md5, size = file_digest(png)
            row = by_file.get(png.name)
            if row is None:
                entry = UNVERIFIABLE.get(packet["id"], {}).get(png.name)
                if not entry:
                    raise SystemExit(f"unclassified frame: {packet['id']}/{png.name} — add a manifest row or a recorded reason")
                frames.append({
                    "file": png.name,
                    "md5": md5,
                    "bytes": size,
                    "source": "unlisted",
                    "classification": entry["classification"],
                    "reason": entry["reason"],
                    "manifest_sha256": manifest.get("plugin_sha256"),
                })
                continue
            frames.append({
                "file": png.name,
                "md5": md5,
                "bytes": size,
                "source": "manifest",
                "classification": classification,
                "manifest_id": row.get("id"),
                "manifest_sha256": manifest.get("plugin_sha256"),
                "manifest_kind": kind,
                "md5_matches_manifest": row.get("md5") == md5,
            })
        unlisted = [frame["file"] for frame in frames if frame["source"] == "unlisted"]
        packets[packet["id"]] = {
            "directory": str(directory.relative_to(ROOT)),
            "manifest": packet["manifest"],
            "manifest_kind": kind,
            "classification": classification,
            "manifest_sha256": manifest.get("plugin_sha256"),
            "png_count": len(frames),
            "manifest_row_count": len(rows),
            "unlisted_count": len(unlisted),
            "unlisted": unlisted,
            "frames": frames,
        }
    return {
        "generated_by": "scripts/cp-frame-inventory.py",
        "packets": packets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed inventory instead of writing it")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    current = build()
    if args.check:
        if not args.out.is_file():
            print(f"FAIL: inventory missing at {args.out}", file=sys.stderr)
            return 1
        committed = json.loads(args.out.read_text())
        if committed != current:
            print("FAIL: committed frame inventory is stale; rerun scripts/cp-frame-inventory.py", file=sys.stderr)
            return 1
        print(f"OK: frame inventory matches disk + manifests ({sum(p['png_count'] for p in current['packets'].values())} PNGs)")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(current, indent=2) + "\n")
    print(f"wrote {args.out}")
    for packet_id, packet in current["packets"].items():
        print(f"  {packet_id}: {packet['png_count']} PNG / {packet['manifest_row_count']} rows / {packet['unlisted_count']} unlisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
