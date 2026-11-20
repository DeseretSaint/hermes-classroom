#!/usr/bin/env python3
"""Re-check the published plugin catalog instead of trusting a frozen timestamp.

Release documents used to prove that `coursebook` was installable by quoting the
catalog index's `generated_at`. That field is regenerated whenever the index is
rebuilt, so the sentence was true for one snapshot and could not be re-checked by
a reader afterwards. The stable facts are the entry's presence and its pinned sha;
this probe reads those live and reports the rotating value as context only.

It is a read-only, by-hand probe: it is never imported by the test suite, and the
offline gate `scripts/check-docs-truth.py` does not call it.

    python3 scripts/catalog-live-check.py
    python3 scripts/catalog-live-check.py --expect-sha 0000000   # must refuse
    python3 scripts/catalog-live-check.py --timeout 10

Exit codes:
    0  the entry is present and its sha is the expected pin
    1  the entry is absent, ambiguous, or pinned to a different sha
    2  the index could not be fetched or was not a catalog index

Stdlib only (`urllib`, `json`); no third-party dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

CATALOG_URL = "https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json"
ENTRY_NAME = "coursebook"

# The pin the release documents record: `plugin-catalog/coursebook.yaml` on
# `hermes-agent` `main`, merged in PR #152920 (2026-11-13, merge commit 3359ee03).
DEFAULT_EXPECT_SHA = "14a2dbb6870e81044dfb644964257fe9ccba992b"


class CatalogError(Exception):
    """The fetched document is not a catalog index this probe can read."""


def parse_index(index: Any) -> tuple[str, list[dict[str, Any]]]:
    """Return `(generated_at, entries)` or raise when the document has the wrong shape."""
    if not isinstance(index, dict):
        raise CatalogError(f"index is {type(index).__name__}, not an object")
    generated_at = index.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise CatalogError("index has no non-empty string `generated_at`")
    entries = index.get("entries")
    if not isinstance(entries, list):
        raise CatalogError("index has no `entries` list")
    rows = [entry for entry in entries if isinstance(entry, dict)]
    return generated_at, rows


def find_entries(entries: list[dict[str, Any]], name: str = ENTRY_NAME) -> list[dict[str, Any]]:
    """Every entry whose `name` is exactly `name` (case-sensitive, as the catalog spells it)."""
    return [entry for entry in entries if entry.get("name") == name]


def evaluate(index: Any, *, name: str = ENTRY_NAME, expect_sha: str = DEFAULT_EXPECT_SHA) -> dict[str, Any]:
    """Pure check over a decoded index. Makes no network call and writes nothing.

    `ok` is true only when exactly one entry carries `name` and its `sha` is
    `expect_sha`. `generated_at` is reported but never compared: it rotates by
    design, which is the whole reason this probe exists.
    """
    generated_at, entries = parse_index(index)
    matches = find_entries(entries, name)
    result: dict[str, Any] = {
        "generated_at": generated_at,
        "entry_count": len(entries),
        "name": name,
        "matches": len(matches),
        "entry": matches[0] if matches else None,
        "expect_sha": expect_sha,
        "ok": False,
        "reason": "",
    }
    if not matches:
        result["reason"] = f"no entry named {name!r} among {len(entries)} entries"
        return result
    if len(matches) > 1:
        result["reason"] = f"{len(matches)} entries named {name!r}; the catalog must name exactly one"
        return result
    entry = matches[0]
    actual = entry.get("sha")
    if actual != expect_sha:
        result["reason"] = f"sha drift: published {actual!r} != expected {expect_sha!r}"
        return result
    result["ok"] = True
    result["reason"] = f"entry present and pinned at {expect_sha}"
    return result


def fetch_index(url: str = CATALOG_URL, timeout: float = 30.0) -> Any:
    """Fetch and decode the index. The only network call in this file."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "coursebook-catalog-live-check/1 (read-only probe)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def format_report(result: dict[str, Any]) -> list[str]:
    """Human-readable lines: the rotating value, the count, the entry, then the verdict."""
    lines = [
        f"url: {CATALOG_URL}",
        f"generated_at: {result['generated_at']}  (rotates; not a pin)",
        f"entries: {result['entry_count']}",
    ]
    entry = result["entry"]
    if entry is None:
        lines.append(f"{result['name']}: ABSENT ({result['matches']} matches)")
    else:
        lines.append(
            f"{result['name']}: name={entry.get('name')} version={entry.get('version')} "
            f"sha={entry.get('sha')} tier={entry.get('tier')}"
        )
    lines.append(("OK: " if result["ok"] else "FAIL: ") + result["reason"])
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the published plugin catalog and check the coursebook entry's pin.",
    )
    parser.add_argument(
        "--expect-sha",
        default=DEFAULT_EXPECT_SHA,
        help=f"sha the coursebook entry must carry (default: {DEFAULT_EXPECT_SHA})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="seconds before the fetch is abandoned (default: 30)",
    )
    args = parser.parse_args(argv)

    try:
        index = fetch_index(timeout=args.timeout)
        result = evaluate(index, expect_sha=args.expect_sha)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"catalog-live-check: could not fetch {CATALOG_URL}: {exc}", file=sys.stderr)
        return 2
    except (CatalogError, json.JSONDecodeError) as exc:
        print(f"catalog-live-check: unusable index: {exc}", file=sys.stderr)
        return 2

    for line in format_report(result):
        print(line)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
