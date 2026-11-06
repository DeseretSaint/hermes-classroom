#!/usr/bin/env python3
"""Prove the over-cap lesson.body defect at the API layer, without the UI."""
from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:44241"
TOKEN = "sentinel-perf-token"
ENROLLMENT = "enr_5b8683c2286945399f34992af7f68351"
COURSE = "crs_ddb6465ba1694ac59ceea7ab852636fa"


def call(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def rpc(method: str, payload: dict) -> dict:
    return call("/rpc", {
        "contract": "cb.rpc",
        "contract_version": int(call("/runtime")["wire_version"]),
        "method": method,
        "operation_id": f"sentinel-{uuid.uuid4().hex[:10]}",
        "payload": payload,
    })


def main() -> int:
    out = rpc("course.outline", {"enrollment_id": ENROLLMENT})
    if not out.get("ok"):
        print("outline failed:", out)
        return 1
    objectives = out["result"]["objectives"]
    report = {"course_id": COURSE, "enrollment_id": ENROLLMENT, "objective_count": len(objectives), "rows": []}
    for objective in objectives[:3]:
        oid = objective["objective_id"]
        page = rpc("lesson.page", {"enrollment_id": ENROLLMENT, "objective_id": oid})
        if page.get("ok"):
            segs = page["result"].get("segments") or []
            report["rows"].append({
                "objective_id": oid,
                "ok": True,
                "segments": len(segs),
                "segment_chars": [len(s.get("text") or "") for s in segs],
                "revision": page["result"].get("revision"),
            })
        else:
            report["rows"].append({"objective_id": oid, "ok": False, "error": page.get("error")})
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
