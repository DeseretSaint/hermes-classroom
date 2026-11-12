#!/usr/bin/env python3
"""Does the catalog actually carry what master ships?

The catalog is the only path by which a user receives this plugin: an entry in
`NousResearch/hermes-agent` pins one 40-character commit, `hermes plugins install coursebook`
clones that commit, and `hermes plugins update coursebook` re-pins to a new entry SHA. A merged
master that nobody pinned reaches nobody. This script is the check for that, and it is meant to
run at release time, not on every commit.

    python3 scripts/catalog-delivery.py                 # report
    python3 scripts/catalog-delivery.py --strict        # exit 1 on a stale pin (release gate)

Exit codes: 0 = the entry pins a commit that contains every runtime change on master (or the
only difference is documentation, tests, audit evidence or scripts); 1 = the entry is stale by
code, or the pin is not an ancestor of master; 2 = the entry file could not be read or parsed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ENTRY_DEFAULT = Path.home() / "Projects/hermes-fork/plugin-catalog/coursebook.yaml"
LIVE_URL = "https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json"
# Paths whose contents never reach an installed copy: a commit touching only these does not
# require a new pin. Everything else does.
NON_RUNTIME = ("docs/", "tests/", "audit/", "probes/", "scripts/", ".github/", "store/", "coverage/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def load_entry(path: Path) -> dict:
    import yaml  # noqa: PLC0415 — only needed when the script runs

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def live_entry(name: str) -> dict | None:
    try:
        with urllib.request.urlopen(LIVE_URL, timeout=20) as fh:
            data = json.load(fh)
    except Exception:  # health: allow BLE001 — offline is a reported state, not a crash
        return None
    return next((e for e in data.get("entries", []) if e.get("name") == name), None)


def runtime_diff(pin: str, head: str) -> list[str]:
    files = [f for f in git("diff", "--name-only", f"{pin}..{head}").splitlines() if f]
    return [f for f in files if not f.startswith(NON_RUNTIME)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", type=Path, default=ENTRY_DEFAULT)
    ap.add_argument("--name", default="coursebook")
    ap.add_argument("--head", default="origin/master")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = ap.parse_args()

    try:
        entry = load_entry(args.entry)
        pin = str(entry.get("sha") or "").lower()
        repo = str(entry.get("repo") or "")
    except Exception as exc:  # health: allow BLE001 — an unreadable entry is the verdict
        print(f"entry unreadable: {args.entry}: {exc}")
        return 2

    head = git("rev-parse", args.head)
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", pin, head]).returncode == 0
    ahead = int(git("rev-list", "--count", f"{pin}..{head}"))
    runtime = runtime_diff(pin, head) if ancestor else []
    published = live_entry(args.name)

    print(f"entry      {args.entry}")
    print(f"repo       {repo}")
    print(f"pin        {pin[:8]}  ({'ancestor of' if ancestor else 'NOT an ancestor of'} {args.head} {head[:8]})")
    print(f"master     {head}  ({ahead} commit(s) ahead of the pin)")
    print(f"runtime    {len(runtime)} changed runtime file(s) since the pin"
          + (f": {', '.join(runtime[:5])}{' …' if len(runtime) > 5 else ''}" if runtime else ""))
    if published is None:
        print(f"live       {args.name} is NOT in the published catalog — users cannot install it yet")
    else:
        same = str(published.get("sha") or "").lower() == pin
        print(f"live       published at {str(published.get('sha'))[:8]}"
              f" ({'matches' if same else 'DIFFERS FROM'} the entry)")

    if args.json:
        print(json.dumps({"name": args.name, "entry": str(args.entry), "repo": repo, "pin": pin,
                          "head": head, "ahead": ahead, "ancestor": ancestor,
                          "runtime": runtime, "published": bool(published),
                          "published_sha": (published or {}).get("sha")}))
        if not ancestor:
            return 1
        return 1 if runtime else 0

    if not ancestor:
        print("FAIL: the pin is not on master — the entry installs a commit nobody can find upstream")
        return 1
    if runtime:
        print("FAIL: master ships runtime changes the catalog pin does not carry; bump the entry "
              "(new PR, per catalog rule 4) and re-run the admission gate")
        return 1
    print("OK: the pin carries every runtime change on master")
    return 0


if __name__ == "__main__":
    sys.exit(main())
