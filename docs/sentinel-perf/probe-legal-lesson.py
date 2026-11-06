#!/usr/bin/env python3
"""Verify the legal long course: objective 1 and 60 must return 4 segments under the cap."""
from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:44241"
TOKEN = "sentinel-perf-token"
ENROLLMENT = "enr_e3464043da494c20a66257c7d340f898"


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def rpc(method, payload):
    return call("/rpc", {
        "contract": "cb.rpc",
        "contract_version": int(call("/runtime")["wire_version"]),
        "method": method,
        "operation_id": f"sentinel-{uuid.uuid4().hex[:10]}",
        "payload": payload,
    })


outline = rpc("course.outline", {"enrollment_id": ENROLLMENT})
objectives = outline["result"]["objectives"]
print("objectives:", len(objectives))
for index in (0, 1, len(objectives) - 1):
    oid = objectives[index]["objective_id"]
    page = rpc("lesson.page", {"enrollment_id": ENROLLMENT, "objective_id": oid})
    if page.get("ok"):
        segs = page["result"]["segments"]
        print(json.dumps({
            "ordinal": objectives[index]["ordinal"],
            "ok": True,
            "segments": len(segs),
            "segment_chars": [len(s.get("text") or "") for s in segs],
            "kinds": [s["kind"] for s in segs],
            "revision": page["result"]["revision"],
        }))
    else:
        print(json.dumps({"ordinal": objectives[index]["ordinal"], "ok": False, "error": page["error"]["code"]}))
