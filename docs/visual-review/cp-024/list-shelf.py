#!/usr/bin/env python3
"""Print library.list rows in shelf order with enrollment ids (CP-024 fixture selection helper)."""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44427")
TOKEN = os.environ.get("CB013_TOKEN", "cp024-test-token")
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 12


def post(payload):
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


with urllib.request.urlopen(
    urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    ),
    timeout=15,
) as response:
    wire = json.load(response)["wire_version"]

body = post(
    {
        "contract": "cb.rpc",
        "contract_version": wire,
        "method": "library.list",
        "operation_id": "cp024-list",
        "idempotency_key": "cp024-list",
        "payload": {"limit": limit},
    }
)
items = (body.get("result") or {}).get("items") or []
for index, item in enumerate(items):
    print(
        index,
        item.get("course_id"),
        item.get("title"),
        "done=%s/%s" % (item.get("sections_done"), item.get("sections_total")),
        item.get("next_step", {}).get("label"),
    )
