#!/usr/bin/env python3
"""Read back the notebook rows the UI wrote — independent of the renderer's own state."""
import json
import subprocess
import sys

marker = sys.argv[1]
raw = subprocess.run(
    ["python3", "scripts/cb013-rpc.py", "notebook.list",
     '{"enrollment_id":"enr_544f0aba033e4fc0a2f50fb61aceda25"}'],
    capture_output=True, text=True, check=True,
).stdout
payload = json.loads(raw)
rows = [e for e in payload["result"]["entries"] if marker in (e.get("note") or "")]
for row in rows:
    print(json.dumps({
        "entry_id": row["entry_id"],
        "revision": row["revision"],
        "note": row["note"],
        "tags": row["tags"],
        "objective_id": row["objective_id"],
        "updated_at": row["updated_at"],
    }, ensure_ascii=False))
print("matching_rows", len(rows))
