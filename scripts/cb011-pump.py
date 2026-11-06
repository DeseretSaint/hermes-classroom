#!/usr/bin/env python3
"""Drain one bounded Coursebook job tick in this process and print what happened.

Used to tell a *resolver* problem (job fails with a typed error) from a *host wiring* problem
(the tick thread is not running or is reading a different database). Run it with the same
``HERMES_HOME`` and single-home env the backend uses:

    set -a; . ~/.hermes/coursebook-test/home/coursebook-single-home.env; set +a
    HERMES_HOME=~/.hermes/coursebook-test/home python3 scripts/cb011-pump.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursebook import db, executor  # noqa: E402


def main() -> int:
    root = db.store_root()
    print("store_root:", root)
    print("schema:", db.applied_schema_version())
    with db.read() as connection:
        rows = connection.execute(
            "SELECT id, kind, state, created_at FROM jobs ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    print("recent jobs:", json.dumps([dict(row) for row in rows], indent=2))
    finished = executor.pump_once(limit=1)
    print("pump_once finished:", json.dumps(finished, indent=2))
    with db.read() as connection:
        rows = connection.execute(
            "SELECT id, kind, state, error_json FROM jobs ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
    print("after:", json.dumps([dict(row) for row in rows], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
