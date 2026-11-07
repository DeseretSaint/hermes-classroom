"""Read lesson.page over the real plugin HTTP route on the isolated M1-U2 rig.

Two reads, same backend, same database:

1. the pre-existing real course ``Japanese affection and register`` — its stored page predates
   ``lesson-prompt.v5``, so it must still report ``textbook_only`` (no migration, no rewrite);
2. the lesson authored by ``scripts/m1u-guided-probe.py`` — it must report ``complete`` with
   ``views.guided = true`` and the authored shorts.

usage: M1U_RIG=<rig dir> python3 scripts/m1u-guided-http.py [--port 44331]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RIG = Path(os.environ["M1U_RIG"])
PORT = int(os.environ.get("M1U_PORT", "44331"))
TOKEN = os.environ.get("M1U_TOKEN", "cb013-test-token")
BASE = f"http://127.0.0.1:{PORT}/api/plugins/coursebook"
OLD_ENROLLMENT = "enr_36266a77f6024e4da1130d6bd2404bbf"
OLD_OBJECTIVE = "obj_70327ddd55a348858228a15590a664da"


def call(method: str, payload: dict) -> dict:
    body = json.dumps(
        {
            "contract": "cb.rpc",
            "contract_version": 8,
            "method": method,
            "operation_id": uuid.uuid4().hex,
            "payload": payload,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE}/rpc",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def summary(result: dict) -> dict:
    document = result["document"]
    return {
        "state": document["state"],
        "views": document["views"],
        "view_note": document["view_note"],
        "block_roles": [block["role"] for block in document["blocks"]],
        "block_shorts": [block["short"] for block in document["blocks"]],
        "check_id": document["check_id"],
        "blocks_claiming_the_check": [
            index for index, block in enumerate(document["blocks"]) if block["check_id"]
        ],
        "segment_count": len(result["segments"]),
        "content_hash": document["content_hash"],
    }


def main() -> None:
    pipeline = json.loads(
        (REPO / "audit" / "visual" / "m1-guided-authoring" / "pipeline-evidence.json").read_text(
            encoding="utf-8"
        )
    )
    authored = pipeline["lesson_page"]

    runtime = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                f"{BASE}/runtime?profile=", headers={"Authorization": f"Bearer {TOKEN}"}
            ),
            timeout=10,
        ).read()
    )
    old = call("lesson.page", {"enrollment_id": OLD_ENROLLMENT, "objective_id": OLD_OBJECTIVE})
    new = call(
        "lesson.page",
        {"enrollment_id": authored["enrollment_id"], "objective_id": authored["objective_id"]},
    )
    for label, response in (("old", old), ("new", new)):
        if not response.get("ok"):
            raise SystemExit(f"{label} lesson.page failed: {response.get('error')}")

    evidence = {
        "backend": {
            "route": f"{BASE}/rpc",
            "plugin_root": runtime["plugin_root"],
            "wire_version": runtime["wire_version"],
            "contract_methods": runtime["contract_methods"],
        },
        "pre_existing_course": {
            "course": "Japanese affection and register - an L0 demonstration classroom",
            "enrollment_id": OLD_ENROLLMENT,
            "objective_id": OLD_OBJECTIVE,
            **summary(old["result"]),
        },
        "authored_lesson": {
            "enrollment_id": authored["enrollment_id"],
            "objective_id": authored["objective_id"],
            **summary(new["result"]),
        },
    }
    target = REPO / "audit" / "visual" / "m1-guided-authoring" / "http-evidence.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
