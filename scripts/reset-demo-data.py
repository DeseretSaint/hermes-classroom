#!/usr/bin/env python3
"""Collapse duplicate demo rows through the contract's own verbs.

The Desktop groups duplicate enrollments/plans on the shelf (H-99), so a dirty demo store is
readable. This is the *data* half, deliberately kept outside the product route: it is an operator
script, not a button a learner can press.

What it does, exactly:

  1. reads `library.list` from a running backend (no direct database access);
  2. groups rows the way the shelf groups them — one object per pack, or per normalised
     title + recipe for authored plans;
  3. keeps the primary record of each group (active first, then most recently touched, then the
     highest revision, then the lowest id — the same order the UI uses);
  4. previews and then deletes the other enrollments with `enrollment.delete`, carrying the
     preview's `data_scope_hash` and each row's own revision.

Dry run by default. Nothing is deleted until `--apply` is passed, and the script prints the exact
verb arguments for every delete it would issue.

    python3 scripts/reset-demo-data.py --base-url http://127.0.0.1:44219 --token "$TOKEN"
    python3 scripts/reset-demo-data.py --base-url ... --token ... --apply
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from collections import OrderedDict
from typing import Any


def call(base: str, token: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def rpc(base: str, token: str, wire: int, method: str, payload: dict, **envelope: Any) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire,
        "method": method,
        "operation_id": f"reset-{method.replace('.', '-')}-{uuid.uuid4().hex[:8]}",
        "payload": payload,
        **envelope,
    }
    return call(base, token, "/rpc", body)


def normalised(row: dict) -> str:
    return " ".join(str(row.get("title") or "").lower().split())


def group_key(row: dict) -> str:
    """Mirrors `cbShelfGroupKey` in desktop/plugin.js."""
    provenance = row.get("provenance") or {}
    if provenance.get("pack_id"):
        return f"pack:{provenance['pack_id']}"
    return f"plan:{normalised(row)}|{row.get('recipe') or ''}|{row.get('locale') or ''}"


def order_key(row: dict) -> tuple:
    """Mirrors `cbShelfMemberOrder`: active, newest, highest revision, then id."""
    return (
        0 if row.get("enrollment_status") == "active" else 1,
        _negated_text(str(row.get("updated_at") or "")),
        -int(row.get("revision") or 0),
        str(row.get("enrollment_id") or ""),
    )


def _negated_text(value: str) -> tuple:
    # Strings sort ascending; a newest-first order is a descending tuple of inverted code units.
    return tuple(-ord(character) for character in value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:44219")
    parser.add_argument("--token", default="")
    parser.add_argument("--apply", action="store_true", help="actually delete (default: print the plan)")
    args = parser.parse_args()

    runtime = call(args.base_url, args.token, "/runtime")
    wire = int(runtime.get("wire_version") or 0)
    if not wire:
        print(f"backend did not report a wire_version: {runtime}", file=sys.stderr)
        return 1
    listed = rpc(args.base_url, args.token, wire, "library.list", {"filter": "all", "limit": 100, "sort": "recent"})
    if not listed.get("ok"):
        print(f"library.list refused: {listed.get('error')}", file=sys.stderr)
        return 1
    rows = listed["result"].get("items") or []

    groups: "OrderedDict[str, list[dict]]" = OrderedDict()
    for row in rows:
        groups.setdefault(group_key(row), []).append(row)

    print(f"cb.rpc v{wire} · {len(rows)} rows · {len(groups)} distinct course objects")
    doomed: list[dict] = []
    for key, members in groups.items():
        members.sort(key=order_key)
        keep = members[0]
        if len(members) > 1:
            print(f"\n{key}")
            print(f"  keep   {keep['enrollment_id']}  {keep.get('title')}  rev {keep.get('revision')}")
        for member in members[1:]:
            print(f"  delete {member['enrollment_id']}  {member.get('title')}  rev {member.get('revision')}")
            doomed.append(member)

    if not doomed:
        print("\nNothing to do: one enrollment per course object already.")
        return 0
    if not args.apply:
        print(f"\nDry run: {len(doomed)} enrollment(s) would be deleted. Re-run with --apply.")
        return 0

    for row in doomed:
        preview = rpc(
            args.base_url,
            args.token,
            wire,
            "enrollment.delete",
            {"enrollment_id": row["enrollment_id"], "dry_run": True},
            idempotency_key=f"reset-preview-{row['enrollment_id']}",
            expected_revision=int(row.get("revision") or 0),
        )
        if not preview.get("ok"):
            print(f"  preview refused for {row['enrollment_id']}: {preview.get('error')}", file=sys.stderr)
            return 1
        scope = preview["result"]["data_scope"]
        deleted = rpc(
            args.base_url,
            args.token,
            wire,
            "enrollment.delete",
            {
                "enrollment_id": row["enrollment_id"],
                "dry_run": False,
                "data_scope_hash": scope["scope_hash"],
            },
            idempotency_key=f"reset-delete-{row['enrollment_id']}-{scope['scope_id']}",
            expected_revision=int(row.get("revision") or 0),
        )
        if not deleted.get("ok"):
            print(f"  delete refused for {row['enrollment_id']}: {deleted.get('error')}", file=sys.stderr)
            return 1
        print(f"  deleted {row['enrollment_id']}")

    after = rpc(args.base_url, args.token, wire, "library.list", {"filter": "all", "limit": 100, "sort": "recent"})
    remaining = len((after.get("result") or {}).get("items") or []) if after.get("ok") else -1
    print(f"\nDone. {remaining} enrollment(s) remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
