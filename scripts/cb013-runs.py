#!/usr/bin/env python3
"""Show lesson runs + the newest chat sessions, so a bind can be driven from the host seam."""
import os
import sqlite3
import sys

home = os.environ.get("CB_HOME") or os.path.expanduser("~/.hermes/coursebook-test/home")
cb = os.path.join(home, "plugin-data", "coursebook", "data.db")
con = sqlite3.connect(cb)
con.row_factory = sqlite3.Row
print("== lesson_runs ==")
for row in con.execute("select * from lesson_runs order by rowid desc limit 10"):
    d = dict(row)
    d.pop("context_json", None)
    print(d)

st = os.path.join(home, "state.db")
print("\n== sessions ==", os.path.exists(st))
scon = sqlite3.connect(st)
scon.row_factory = sqlite3.Row
cols = [r[1] for r in scon.execute("pragma table_info(sessions)")]
print("cols:", cols)
pick = [c for c in ("id", "session_id", "title", "created_at", "updated_at", "profile", "model") if c in cols]
for row in scon.execute(f"select {', '.join(pick)} from sessions order by rowid desc limit 6"):
    print(dict(row))
