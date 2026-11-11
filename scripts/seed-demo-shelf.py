#!/usr/bin/env python3
"""Rebuild the four-course demo shelf from the committed exports in one pass.

The shelf is not hand-built data. Each zip under ``docs/concept-parity/demo/exports/`` is a real
``course.export`` artifact: an approved plan, validated lesson pages and the pack's own manifest,
produced by ``scripts/cp015-demo-courses.py`` against the running product. This script only takes
the learner's import path — stage the file, preview it, import it — and then reads
``library.list`` back to prove the shelf.

    scripts/seed-demo-shelf.sh                       # the demo home on 127.0.0.1:44501
    scripts/seed-demo-shelf.sh --base-url ... --token ...
    scripts/seed-demo-shelf.sh --dry-run             # list what would be imported

Exit code 0 requires all four courses present on the shelf afterwards.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs/concept-parity/demo/exports"
EXPECTED = ("Japanese Cafe Basics", "Auto Repair Fundamentals", "Astronomy", "Sourdough")


def call(base: str, token: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def wire(base: str, token: str) -> int:
    runtime = call(base, token, "/runtime?profile=")
    version = int(runtime.get("wire_version") or 0)
    if not version:
        raise SystemExit(f"backend reported no wire_version: {runtime}")
    return version


def rpc(base: str, token: str, version: int, method: str, payload: dict, key: str | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": version,
        "method": method,
        "operation_id": f"seed-shelf-{method.replace('.', '-')}-{uuid.uuid4().hex[:8]}",
        "payload": payload,
    }
    if key:
        body["idempotency_key"] = key
    return call(base, token, "/rpc", body)


def shelf(base: str, token: str, version: int) -> list[dict]:
    listed = rpc(base, token, version, "library.list",
                 {"filter": "all", "limit": 100, "sort": "recent"})
    if not listed.get("ok"):
        raise SystemExit(f"library.list refused: {listed.get('error')}")
    return listed["result"].get("items") or []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:44501")
    parser.add_argument("--token", default="cp015-demo-token")
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--mode", default="fresh", choices=["fresh", "resume"])
    parser.add_argument("--force", action="store_true",
                        help="import even when that pack is already on the shelf")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    archives = sorted(Path(args.dir).glob("*.zip"))
    if not archives:
        print(f"no exported packs in {args.dir}", file=sys.stderr)
        return 1
    print(f"exports: {len(archives)} in {args.dir}")

    version = wire(args.base_url, args.token)
    print(f"wire   : cb.rpc v{version}")

    if args.dry_run:
        for archive in archives:
            print(f"  would import {archive.name} ({archive.stat().st_size} bytes)")
        return 0

    existing = {(item.get("provenance") or {}).get("pack_id"): item for item in shelf(
        args.base_url, args.token, version)}
    problems: list[str] = []
    for archive in archives:
        granted = call(args.base_url, args.token, "/packs/grant", {"path": str(archive)})
        if not granted.get("ok"):
            problems.append(f"{archive.name}: grant refused: {granted.get('error')}")
            continue
        staged = granted["staged_id"]
        preview = rpc(args.base_url, args.token, version, "pack.preview", {"staged_id": staged})
        if not preview.get("ok"):
            problems.append(f"{archive.name}: preview refused: {preview.get('error')}")
            continue
        manifest = preview["result"]["manifest"]
        pack_id = manifest["pack_id"]
        print(f"preview: {pack_id} {manifest['pack_version']} "
              f"content_hash={str(manifest['content_hash'])[:23]}…")
        if pack_id in existing and not args.force:
            print(f"  already on the shelf: {existing[pack_id].get('title')} — skipped")
            continue
        imported = rpc(
            args.base_url, args.token, version, "pack.import",
            {"staged_id": staged, "mode": args.mode},
            key=f"seed-shelf-{pack_id}-{uuid.uuid4().hex[:8]}",
        )
        if not imported.get("ok"):
            problems.append(f"{archive.name}: import refused: {imported.get('error')}")
            continue
        result = imported["result"]
        print(f"  imported: {result.get('enrollment_id')} "
              f"objective={(result.get('current_objective_id') or 'none')}")

    rows = shelf(args.base_url, args.token, version)
    print("\nshelf:")
    titles = []
    for item in rows:
        titles.append(str(item.get("title") or ""))
        print(f"  {item.get('title')!r:34} next={item.get('next_step')!r} "
              f"evidence={item.get('evidence_summary')!r}")
    missing = [title for title in EXPECTED if title not in titles]
    if missing:
        problems.append(f"missing from the shelf: {', '.join(missing)}")
    for problem in problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
