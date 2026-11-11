#!/usr/bin/env python3
"""VQ-006 — seed (or point at) a real course library for the installed capture harness.

"Real library" means what the product itself would have: the bundled packs imported through the
same grant -> preview -> import path a learner takes (`scripts/seed-demo-course.py`), at least one
user-created Game course with an approved world, and no hand-inserted rows.

This script never creates art and never approves a world on the product's behalf. A Game course is
reported, not invented: it asks `world.read` for each library item and picks a course whose stored
`presentation_mode` is `game`. If none exists the script fails with the exact next action, because a
Textbook course photographed as Game evidence is worse than a held card.

    python3 scripts/vq-library.py --base-url http://127.0.0.1:44319 --token «token» \
        [--json out/library.json] [--game-course crs_…] [--allow-no-game]

Exit codes: 0 library ready (bundled packs present and a Game course found, or --allow-no-game);
3 no Game course (reported in the JSON); 1 the backend refused a read or a seed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKS = (
    "bundled/packs/japanese-affection-context-l0",
    "bundled/packs/parent-measurement-practice",
    "bundled/packs/technical-pack-literacy",
)


def call(base: str, token: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def rpc(base: str, token: str, version: int, method: str, payload: dict) -> dict:
    return call(
        base,
        token,
        "/rpc",
        {
            "contract": "cb.rpc",
            "contract_version": version,
            "method": method,
            "operation_id": f"vq-{method.replace('.', '-')}-{uuid.uuid4().hex[:8]}",
            "payload": payload,
        },
    )


def library(base: str, token: str, version: int) -> list[dict]:
    answer = rpc(base, token, version, "library.list", {"filter": "all", "limit": 100, "sort": "recent"})
    if not answer.get("ok"):
        raise SystemExit(f"library.list refused: {answer.get('error')}")
    return list((answer.get("result") or {}).get("items") or [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:44219")
    parser.add_argument("--token", default="")
    parser.add_argument("--pack", action="append", default=None,
                        help=f"pack directory to import (default: all bundled packs)")
    parser.add_argument("--game-course", default=None,
                        help="course_id to require as the user-created Game course")
    parser.add_argument("--allow-no-game", action="store_true",
                        help="report the missing Game course but let the harness continue")
    parser.add_argument("--json", default=None, help="write the library report here")
    args = parser.parse_args()

    packs = args.pack or list(DEFAULT_PACKS)
    runtime = call(args.base_url, args.token, "/runtime")
    version = int(runtime.get("wire_version") or 0)
    if not version:
        print(f"backend did not report a wire_version: {runtime}", file=sys.stderr)
        return 1
    print(f"backend : {args.base_url}  cb.rpc v{version}")

    report: dict = {
        "schema": "vq.library.v1",
        "backend": {"url": args.base_url, "wire_version": version,
                    "plugin_root": runtime.get("plugin_root"),
                    "implemented_count": runtime.get("implemented_count")},
        "seeds": [],
        "items": [],
        "game_course": None,
        "problems": [],
    }

    for pack in packs:
        source = ROOT / pack
        if not source.is_dir():
            report["problems"].append(f"bundled pack is missing from the checkout: {pack}")
            continue
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seed-demo-course.py"),
             "--base-url", args.base_url, "--token", args.token, "--pack", pack],
            capture_output=True, text=True,
        )
        seeded = completed.returncode == 0
        report["seeds"].append({
            "pack": pack,
            "ok": seeded,
            "output": (completed.stdout or "").strip().splitlines()[-6:],
            "error": (completed.stderr or "").strip()[-400:] or None,
        })
        print(f"seed {pack}: {'ok' if seeded else 'FAILED'}")
        if not seeded:
            report["problems"].append(f"could not import {pack}")

    items = library(args.base_url, args.token, version)
    report["items"] = [
        {
            "course_id": item.get("course_id"),
            "enrollment_id": item.get("enrollment_id"),
            "title": item.get("title"),
            "recipe": item.get("recipe"),
            "provenance": item.get("provenance"),
            "enrollment_status": item.get("enrollment_status"),
        }
        for item in items
    ]
    print(f"library : {len(items)} course(s)")

    game_reads = []
    for item in items:
        answer = rpc(args.base_url, args.token, version, "world.read", {"course_id": item["course_id"]})
        if not answer.get("ok"):
            game_reads.append({"course_id": item["course_id"], "error": answer.get("error")})
            continue
        result = answer.get("result") or {}
        world = result.get("world") or {}
        game_reads.append({
            "course_id": item["course_id"],
            "presentation_mode": result.get("presentation_mode"),
            "world_state": (world or {}).get("state"),
            "world_id": (world or {}).get("world_id"),
        })
    report["world_reads"] = game_reads

    candidates = [
        row for row in game_reads
        if row.get("presentation_mode") == "game" and row.get("world_state") == "approved"
    ]
    if args.game_course:
        chosen = next((row for row in candidates if row["course_id"] == args.game_course), None)
        if chosen is None:
            report["problems"].append(
                f"--game-course {args.game_course} is not an approved Game course in this library"
            )
    else:
        chosen = candidates[0] if candidates else None
    report["game_course"] = chosen

    if chosen:
        print(f"game    : {chosen['course_id']} ({chosen.get('world_id')})")
    else:
        report["problems"].append(
            "no course in this library has presentation_mode=game with an approved world"
        )
        print("game    : none", file=sys.stderr)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"report  : {Path(args.json).resolve()}")

    if report["problems"] and not (args.allow_no_game and len(report["problems"]) == 1):
        for problem in report["problems"]:
            print(f"problem : {problem}", file=sys.stderr)
        return 1
    if chosen is None:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
