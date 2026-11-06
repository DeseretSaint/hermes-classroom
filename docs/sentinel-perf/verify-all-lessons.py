#!/usr/bin/env python3
"""Read EVERY objective's lesson page in the legal and over-cap courses; write a JSON verdict."""
from __future__ import annotations

import json
import os
import urllib.request
import uuid
from pathlib import Path

# The recorded rig's defaults stay the defaults; a fresh rig overrides them by environment so the
# same script can verify any seed without editing it.
BASE = os.environ.get("COURSEBOOK_VERIFY_BASE", "http://127.0.0.1:44241")
TOKEN = os.environ.get("COURSEBOOK_VERIFY_TOKEN", "sentinel-perf-token")
COURSES = {
    "legal-60": "enr_e3464043da494c20a66257c7d340f898",
    "overcap-55": "enr_5b8683c2286945399f34992af7f68351",
}
_override = os.environ.get("COURSEBOOK_VERIFY_ENROLLMENTS")
if _override:
    _path = Path(_override)
    COURSES = json.loads(_path.read_text() if _path.is_file() else _override)
_OUT = Path(os.environ.get("COURSEBOOK_VERIFY_OUT", "docs/sentinel-perf/results/lesson-readability.json"))


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read())


def rpc(version, method, payload):
    return call("/rpc", {
        "contract": "cb.rpc",
        "contract_version": version,
        "method": method,
        "operation_id": f"verify-{uuid.uuid4().hex[:10]}",
        "payload": payload,
    })


version = int(call("/runtime")["wire_version"])
out = {}
for name, enrollment in COURSES.items():
    outline = rpc(version, "course.outline", {"enrollment_id": enrollment})
    objectives = outline["result"]["objectives"]
    failures = []
    segment_sizes = []
    for objective in objectives:
        page = rpc(version, "lesson.page", {"enrollment_id": enrollment, "objective_id": objective["objective_id"]})
        if page.get("ok"):
            segs = page["result"].get("segments") or []
            segment_sizes.append(max((len(s.get("text") or "") for s in segs), default=0))
        else:
            failures.append({
                "ordinal": objective["ordinal"],
                "objective_id": objective["objective_id"],
                "code": page["error"]["code"],
                "path": (page["error"].get("details") or {}).get("path"),
                "retryable": page["error"].get("retryable"),
            })
    out[name] = {
        "enrollment_id": enrollment,
        "objectives": len(objectives),
        "readable": len(objectives) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "max_segment_chars": max(segment_sizes) if segment_sizes else None,
    }

Path(_OUT).write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
