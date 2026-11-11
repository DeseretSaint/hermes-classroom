#!/usr/bin/env python3
"""Verify the store shelf: every community pack audits, and the index matches the bytes.

This is the check a store pull request runs. It is deliberately the same gate the importer uses,
so a green run here means "this pack will import", not "this pack looks plausible".

Exit codes follow the repository convention: 0 clean, 1 findings, 3 refused to run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CB_STORE_ROOT") or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))

from coursebook import archive, packs, pack_flow  # noqa: E402

STORE = ROOT / "store"
COMMUNITY = STORE / "packs"


def verify() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    problems: list[dict[str, str]] = []
    verified: list[dict[str, str]] = []
    try:
        index = json.loads((STORE / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [{"pack": "store/index.json", "problem": f"unreadable: {exc}"}], verified
    indexed = {
        str(row.get("pack_id")): row
        for row in index.get("packs") or []
        if isinstance(row, dict) and row.get("origin") == "community"
    }
    files = set()
    for source in sorted(COMMUNITY.glob("*.zip")) if COMMUNITY.is_dir() else []:
        files.add(source.stem)
        row = indexed.get(source.stem)
        if row is None:
            problems.append({"pack": source.name, "problem": "not in store/index.json; run scripts/store_index.py"})
            continue
        import tempfile

        with tempfile.TemporaryDirectory(prefix="cb-store-verify-") as temporary:
            target = Path(temporary) / "pack"
            try:
                manifest = archive.extract_archive(source, target)
                roots = [child for child in target.iterdir() if child.is_dir()]
                if len(roots) != 1:
                    raise archive.PackRejected("the archive must carry exactly one root directory")
                staged = archive.StagedPack(
                    staged_id="store-verify", directory=roots[0], manifest=manifest,
                    integrity={}, granted_from=str(source),
                )
                pack_flow.validate_and_audit(staged)
            except (archive.PackRejected, packs.PackRejected) as exc:
                problems.append({"pack": source.name, "problem": str(exc)})
                continue
            if str(manifest["pack_id"]) != source.stem:
                problems.append({"pack": source.name, "problem": f"pack_id is {manifest['pack_id']!r}"})
                continue
            if str(manifest["content_hash"]) != str(row.get("content_hash")):
                problems.append({"pack": source.name, "problem": "index content_hash does not match the pack"})
                continue
            verified.append({
                "pack": source.name,
                "pack_id": str(manifest["pack_id"]),
                "mode": str((manifest.get("presentation") or {}).get("mode") or "textbook"),
                "objectives": str(len(manifest.get("objectives") or [])),
                "media": str(len(manifest.get("media") or [])),
            })
    for pack_id in sorted(set(indexed) - files):
        problems.append({"pack": f"{pack_id}.zip", "problem": "indexed but missing from store/packs"})
    return problems, verified


def main(argv: list[str] | None = None) -> int:
    global ROOT, STORE, COMMUNITY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default="",
        help="repository root holding store/ (default: this checkout); the workflow runs the base "
        "branch's copy of this script against the pull request's tree",
    )
    args = parser.parse_args(argv)
    if args.root:
        ROOT = Path(args.root).resolve()
        STORE = ROOT / "store"
        COMMUNITY = STORE / "packs"
    problems, verified = verify()
    for row in verified:
        print(f"ok   {row['pack']}: {row['mode']}, {row['objectives']} objective(s), {row['media']} media")
    for row in problems:
        print(f"FAIL {row['pack']}: {row['problem']}", file=sys.stderr)
    if problems:
        return 1
    print(f"store: {len(verified)} community pack(s) verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
