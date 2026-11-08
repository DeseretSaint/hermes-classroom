#!/usr/bin/env python3
"""Seed a running Coursebook backend with the bundled demonstration pack.

This is the same path a learner takes — grant the host's local file, preview it, import it — not a
database write. It exists so a live Desktop capture can start from a real course with real
objectives and checks instead of hand-inserted rows.

    python3 scripts/seed-demo-course.py \
        --base-url http://127.0.0.1:44219 --token cb013-test-token \
        [--pack bundled/packs/japanese-affection-context-l0] [--mode fresh]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import archive as pack_archive  # noqa: E402 - path first


def call(base: str, token: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:44219")
    parser.add_argument("--token", default="")
    parser.add_argument("--pack", default="bundled/packs/japanese-affection-context-l0")
    parser.add_argument("--mode", default="fresh", choices=["fresh", "resume"])
    parser.add_argument("--archive", help="where to write the .zip (default: a temp path)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="import even when this pack already has an enrollment (default: leave the clean seed alone)",
    )
    args = parser.parse_args()

    source = ROOT / args.pack
    manifest, files = pack_archive.read_directory(source)
    pack_id = manifest.get("pack_id")
    archive = Path(args.archive) if args.archive else Path(
        f"/tmp/coursebook-demo-{uuid.uuid4().hex[:8]}.zip"
    )
    pack_archive.write_archive(archive, manifest, files)
    print(f"archive: {archive} ({archive.stat().st_size} bytes)")

    # A clean demo seed is one course per plan. Re-running this script must not add a fourteenth
    # copy of the same course, so the existing library is read first — the same read the Desktop
    # shelf makes. `scripts/reset-demo-data.py` is the destructive counterpart.
    runtime = call(args.base_url, args.token, "/runtime")
    wire_version = int(runtime.get("wire_version") or 0)
    if not wire_version:
        print(f"backend did not report a wire_version: {runtime}", file=sys.stderr)
        return 1
    print(f"wire   : cb.rpc v{wire_version}")
    if pack_id and not args.force:
        listed = call(
            args.base_url,
            args.token,
            "/rpc",
            {
                "contract": "cb.rpc",
                "contract_version": wire_version,
                "method": "library.list",
                "operation_id": f"seed-list-{uuid.uuid4().hex[:8]}",
                "payload": {"filter": "all", "limit": 100, "sort": "recent"},
            },
        )
        if listed.get("ok"):
            existing = [
                item for item in listed["result"].get("items") or []
                if (item.get("provenance") or {}).get("pack_id") == pack_id
            ]
            if existing:
                print(f"already seeded: {pack_id}")
                for item in existing:
                    print(f"  {item['enrollment_id']}  {item.get('title')}")
                print("Nothing imported. Use --force to add another enrollment anyway.")
                return 0
        else:
            print(f"library.list refused: {listed.get('error')}", file=sys.stderr)
            return 1

    granted = call(args.base_url, args.token, "/packs/grant", {"path": str(archive)})
    if not granted.get("ok"):
        print(f"grant refused: {granted}", file=sys.stderr)
        return 1
    staged = granted["staged_id"]
    print(f"staged : {staged}")

    # The wire version was read above, before the duplicate check; it is never assumed, because a
    # hard-coded version turns every seed run into a VALIDATION_FAILED as the contract advances.

    preview = call(
        args.base_url,
        args.token,
        "/rpc",
        {
            "contract": "cb.rpc",
            "contract_version": wire_version,
            "method": "pack.preview",
            "operation_id": f"seed-preview-{uuid.uuid4().hex[:8]}",
            "payload": {"staged_id": staged},
        },
    )
    if not preview.get("ok"):
        print(f"preview refused: {preview.get('error')}", file=sys.stderr)
        return 1
    print(f"preview: {preview['result']['manifest']['pack_id']} "
          f"{preview['result']['manifest']['pack_version']} "
          f"content_hash={preview['result']['manifest']['content_hash']}")

    imported = call(
        args.base_url,
        args.token,
        "/rpc",
        {
            "contract": "cb.rpc",
            "contract_version": wire_version,
            "method": "pack.import",
            "operation_id": f"seed-import-{uuid.uuid4().hex[:8]}",
            "idempotency_key": f"seed-import-{uuid.uuid4().hex}",
            "payload": {"staged_id": staged, "mode": args.mode},
        },
    )
    if not imported.get("ok"):
        print(f"import refused: {imported.get('error')}", file=sys.stderr)
        return 1
    print(json.dumps(imported["result"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
