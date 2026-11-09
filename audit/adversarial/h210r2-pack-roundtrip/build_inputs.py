"""Build the shipped bundled packs into archive files for the H-210-R2 round trip.

Reads each bundled directory through the repo's own reader, then writes the archive with the
repo's own deterministic writer, exactly as a release artifact would be packaged. Nothing here
decides whether an archive is importable: pack.preview/pack.import re-validate it independently.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_a7761dfc")
sys.path.insert(0, str(ROOT))

from coursebook import archive  # noqa: E402

OUT = Path("/home/deseretsaint/.hermes/profiles/lattice/cache/scratch/h210r2/inputs")

PACKS = {
    "japanese-affection-context-l0": ROOT / "bundled/packs/japanese-affection-context-l0",
    "technical-demo-pack": ROOT / "bundled/packs/technical-demo-pack",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, directory in PACKS.items():
        manifest, files = archive.read_directory(directory)
        destination = OUT / f"{manifest['pack_id']}-{manifest['pack_version']}.zip"
        archive.write_archive(destination, manifest, files)
        data = destination.read_bytes()
        declared_media = {
            str(entry["path"]): next(
                (str(f["sha256"]) for f in manifest["files"] if str(f["path"]) == str(entry["path"])),
                None,
            )
            for entry in manifest.get("media") or []
        }
        report[name] = {
            "path": str(destination),
            "zip_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "content_hash": str(manifest["content_hash"]),
            "pack_version": str(manifest["pack_version"]),
            "objectives": len(manifest.get("objectives") or []),
            "sections": sum(len(o.get("sections") or []) for o in manifest.get("objectives") or []),
            "checks": sum(len(o.get("checks") or []) for o in manifest.get("objectives") or []),
            "files": len(manifest.get("files") or []),
            "media": declared_media,
            "media_count": len(declared_media),
        }
        print(json.dumps({name: report[name]}, indent=2, sort_keys=True))
    (OUT / "inputs.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    total = sum(item["media_count"] for item in report.values())
    print(f"declared media segments across both packs: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
