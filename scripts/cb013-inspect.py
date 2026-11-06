#!/usr/bin/env python3
"""Print the live CB rows that the pane and the hooks read, from the isolated test home."""
import os
import sqlite3
import sys

home = os.environ.get("CB_HOME") or os.path.expanduser("~/.hermes/coursebook-test/home")
db = os.path.join(home, "plugin-data", "coursebook", "data.db")
print("db:", db, os.path.exists(db))
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
print("tables:", ", ".join(tables))
for tbl in ("enrollments", "bindings", "checks", "attempts", "objectives", "sessions"):
    if tbl not in tables:
        continue
    print(f"\n== {tbl} ==")
    try:
        cols = [d[1] for d in con.execute(f"pragma table_info({tbl})")]
        keep = [c for c in cols if c not in ("spec_json", "plan_json", "content_json", "graph_json")]
        rows = list(con.execute(f"select {', '.join(keep)} from {tbl} order by rowid desc limit 8"))
        for row in rows:
            print(dict(row))
    except Exception as exc:  # noqa: BLE001
        print("err", exc)
