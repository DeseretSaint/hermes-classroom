#!/usr/bin/env python3
"""Import the Sentinel performance fixtures through the real pack path.

grant (POST /packs/grant) -> pack.preview -> pack.import. No database write and no fixture rows:
the backend validates, hashes and adopts the archive exactly as a learner's import would.

    python3 docs/sentinel-perf/seed-packs.py \
        --base-url http://127.0.0.1:44241 --token sentinel-perf-token
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


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


def rpc(base: str, token: str, version: int, method: str, payload: dict, key: str | None = None) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": version,
        "method": method,
        "operation_id": f"sentinel-{uuid.uuid4().hex[:12]}",
        "payload": payload,
    }
    if key:
        body["idempotency_key"] = key
    return call(base, token, "/rpc", body)


def import_one(base: str, token: str, version: int, archive: Path) -> dict:
    granted = call(base, token, "/packs/grant", {"path": str(archive)})
    if not granted.get("ok"):
        raise SystemExit(f"grant refused for {archive}: {granted}")
    staged = granted["staged_id"]
    preview = rpc(base, token, version, "pack.preview", {"staged_id": staged})
    if not preview.get("ok"):
        raise SystemExit(f"preview refused for {archive}: {preview.get('error')}")
    imported = rpc(
        base,
        token,
        version,
        "pack.import",
        {"staged_id": staged, "mode": "fresh"},
        key=f"sentinel-import-{archive.stem}-{uuid.uuid4().hex[:8]}",
    )
    if not imported.get("ok"):
        raise SystemExit(f"import refused for {archive}: {imported.get('error')}")
    return {
        "archive": str(archive),
        "staged_id": staged,
        "pack_id": preview["result"]["manifest"]["pack_id"],
        "content_hash": preview["result"]["manifest"]["content_hash"],
        "result": imported["result"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:44241")
    parser.add_argument("--token", default="sentinel-perf-token")
    parser.add_argument("--out", default=str(Path.home() / ".hermes" / "sentinel-perf" / "packs"))
    args = parser.parse_args()

    out = Path(args.out).expanduser()
    runtime = call(args.base_url, args.token, "/runtime")
    version = int(runtime.get("wire_version") or 0)
    if not version:
        raise SystemExit(f"backend reported no wire_version: {runtime}")
    print(f"wire: cb.rpc v{version}  plugin_root={runtime.get('plugin_root')}")

    report = {}
    library_before = rpc(args.base_url, args.token, version, "library.list", {"filter": "all", "limit": 100})
    installed = {
        ((item.get("provenance") or {}).get("pack_id"))
        for item in (library_before.get("result") or {}).get("items", [])
    }
    for name in ("sentinel-baseline-3", "sentinel-long-55", "sentinel-long-60-legal"):
        if name in installed:
            print(f"skip {name}: already installed")
            continue
        report[name] = import_one(args.base_url, args.token, version, out / f"{name}.zip")
        print(json.dumps(report[name], indent=2)[:1200])

    library = rpc(args.base_url, args.token, version, "library.list", {"filter": "all", "limit": 100})
    print("\nlibrary:", json.dumps(
        [
            {
                "enrollment_id": item.get("enrollment_id"),
                "course_id": item.get("course_id"),
                "title": (item.get("course") or {}).get("title") or item.get("title"),
                "objectives": (item.get("evidence_summary") or {}).get("total_objectives"),
            }
            for item in (library.get("result") or {}).get("items", [])
        ],
        indent=2,
        ensure_ascii=False,
    ))
    print("\nREPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
