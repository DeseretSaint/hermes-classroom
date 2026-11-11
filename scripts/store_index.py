#!/usr/bin/env python3
"""Build ``store/index.json`` — the shelf a storefront reads.

The store is the repository, not a service: a course pack that is in this tree ships with the next
plugin update, and a user's copy sees it after that update. Two shelves feed the index:

* ``bundled/packs/<slug>/``   — the packs this build already ships (first-party).
* ``store/packs/<slug>.zip`` — community packs accepted through a pull request (one zip each).

The index is generated, never hand-edited, so it can never claim a hash the bytes do not have. Run
with ``--check`` in CI to fail a pull request whose index is stale.

Usage:
    python3 scripts/store_index.py            # write store/index.json
    python3 scripts/store_index.py --check    # exit 1 when the file is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coursebook import archive  # noqa: E402

SCHEMA = 1
STORE = ROOT / "store"
INDEX = STORE / "index.json"
BUNDLED = ROOT / "bundled" / "packs"
COMMUNITY = STORE / "packs"


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _entry(manifest: dict[str, Any], *, origin: str, path: str, archive_sha: str | None) -> dict[str, Any]:
    licence = manifest.get("license") or {}
    presentation = manifest.get("presentation") or {}
    return {
        "pack_id": str(manifest["pack_id"]),
        "pack_version": str(manifest["pack_version"]),
        "title": str(manifest["title"]),
        "subtitle": str(manifest.get("subtitle") or ""),
        "locale": manifest.get("locale"),
        "level_label": manifest.get("level_label"),
        "objectives": len(manifest.get("objectives") or []),
        "recipe": str(manifest.get("recipe") or ""),
        "mode": str(presentation.get("mode") or "textbook"),
        "content_hash": str(manifest["content_hash"]),
        "archive_sha256": archive_sha,
        "license": licence.get("id"),
        "redistribution": licence.get("redistribution"),
        "contributors": list(manifest.get("contributors") or []),
        "minimum_coursebook_version": manifest.get("minimum_coursebook_version"),
        "origin": origin,
        "path": path,
    }


def _from_bundled(directory: Path) -> dict[str, Any]:
    manifest, _files = archive.read_directory(directory)
    return _entry(
        manifest,
        origin="bundled",
        path=str(directory.relative_to(ROOT)),
        archive_sha=None,
    )


def _from_archive(archive_path: Path) -> dict[str, Any]:
    """Read one community zip through the same extractor the importer uses."""
    with tempfile.TemporaryDirectory(prefix="cb-store-") as temporary:
        manifest = archive.extract_archive(archive_path, Path(temporary) / "pack")
        sha = _digest(archive_path.read_bytes())
        entry = _entry(
            manifest,
            origin="community",
            path=str(archive_path.relative_to(ROOT)),
            archive_sha=sha,
        )
        # The filename is the store's identity for a community pack; a mismatch means the file was
        # renamed by hand and the shelf would lie about which pack it holds.
        if archive_path.stem != entry["pack_id"]:
            raise SystemExit(
                f"{archive_path.name}: file name {archive_path.stem!r} does not match pack_id "
                f"{entry['pack_id']!r}; rename the file to <pack_id>.zip"
            )
        return entry


def build() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if BUNDLED.is_dir():
        for directory in sorted(p for p in BUNDLED.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if (directory / archive.root_file()).is_file():
                entries.append(_from_bundled(directory))
    if COMMUNITY.is_dir():
        for archive_path in sorted(COMMUNITY.glob("*.zip")):
            entries.append(_from_archive(archive_path))
    seen: dict[str, str] = {}
    for entry in entries:
        prior = seen.get(entry["pack_id"])
        if prior is not None:
            raise SystemExit(
                f"two shelves carry pack_id {entry['pack_id']!r}: {prior} and {entry['path']}"
            )
        seen[entry["pack_id"]] = entry["path"]
    entries.sort(key=lambda item: (item["origin"] != "bundled", item["pack_id"]))
    body = {"schema": SCHEMA, "pack_count": len(entries), "packs": entries}
    return body


def render(body: dict[str, Any]) -> str:
    # Stable bytes: a rebuild that changes nothing produces an identical file.
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when store/index.json is stale")
    args = parser.parse_args(argv)
    text = render(build())
    if args.check:
        current = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else None
        if current != text:
            print("store/index.json is stale; run python3 scripts/store_index.py", file=sys.stderr)
            return 1
        print(f"store/index.json is current: {json.loads(text)['pack_count']} pack(s)")
        return 0
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(text, encoding="utf-8")
    print(f"wrote {INDEX.relative_to(ROOT)}: {json.loads(text)['pack_count']} pack(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
