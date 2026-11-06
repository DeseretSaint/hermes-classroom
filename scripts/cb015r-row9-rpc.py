#!/usr/bin/env python3
"""Row 9, RPC half: after an ACTIVE final approval, change the plan the way the studio does
(plan.replan -> parent.plan.edit), then read the export gate and try to export.

Never invents a value: the revision comes from library.list, the fence hash from
parent.blueprint.read, and every refusal is printed as returned.

    python3 row9-revise.py <course_id> <out.json>
"""
from __future__ import annotations
import json, os, sys, time, urllib.error, urllib.request

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44219")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")
LOG = []


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {TOKEN}"},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


WIRE = request("GET", "/api/plugins/coursebook/runtime?profile=")
VERSION = int(WIRE.get("wire_version") or 1)


def call(method, payload, expected_revision=None):
    body = {"contract": "cb.rpc", "contract_version": VERSION, "method": method,
            "operation_id": f"row9-{method.replace('.', '-')}-{time.time_ns()}",
            "idempotency_key": f"row9-{method.replace('.', '-')}-{time.time_ns()}", "payload": payload}
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    reply = request("POST", "/api/plugins/coursebook/rpc?profile=", body)
    LOG.append({"method": method, "expected_revision": expected_revision,
                "ok": reply.get("ok"), "error": reply.get("error"),
                "revision": reply.get("revision")})
    return reply


def main():
    course_id = sys.argv[1]
    out_path = sys.argv[2]
    listing = request("POST", "/api/plugins/coursebook/rpc?profile=", {
        "contract": "cb.rpc", "contract_version": VERSION, "method": "library.list",
        "operation_id": f"row9-list-{time.time_ns()}",
        "idempotency_key": f"row9-list-{time.time_ns()}", "payload": {}})
    row = next(r for r in listing["result"]["items"] if r["course_id"] == course_id)
    enrollment_id, revision = row["enrollment_id"], int(row["revision"])

    before_reply = call("parent.blueprint.read", {"course_id": course_id})
    if not before_reply.get("ok"):
        print("blueprint.read refused:", json.dumps(before_reply.get("error")))
        raise SystemExit(1)
    before = before_reply["result"]
    print("BEFORE approval:", json.dumps(before["approval"]))
    print("BEFORE export:", json.dumps(before["export"]))

    outline = call("course.outline", {"enrollment_id": enrollment_id})["result"]
    plan = outline["plan"]
    objectives = outline["objectives"]
    changes = [{"objective_id": o["objective_id"], "change": "keep"} for o in objectives]
    changes[0] = {**changes[0], "change": "retitle",
                  "title": "Name one warm and one cold thing in the kitchen (revised)"}
    replan = call("plan.replan", {"enrollment_id": enrollment_id, "objective_changes": changes},
                  expected_revision=revision)
    if replan.get("ok"):
        revision = int(replan["result"]["revision"])
    print("replan:", replan.get("ok"), replan.get("error"))

    mid = call("parent.blueprint.read", {"course_id": course_id})["result"]
    print("AFTER replan approval:", json.dumps(mid["approval"]))
    print("AFTER replan export:", json.dumps(mid["export"]))

    new_plan = mid["plan"]
    edited = call("parent.plan.edit", {
        "enrollment_id": enrollment_id,
        "plan_id": new_plan["plan_id"],
        "expected_plan_hash": new_plan["plan_hash"],
        "course_title": "Japanese café basics, revised",
    }, expected_revision=revision)
    if edited.get("ok"):
        revision = int(edited["result"]["revision"])
    print("plan.edit:", edited.get("ok"), edited.get("error"))

    after = call("parent.blueprint.read", {"course_id": course_id})["result"]
    print("AFTER edit approval:", json.dumps(after["approval"]))
    print("AFTER edit export:", json.dumps(after["export"]))

    export = call("parent.export", {"enrollment_id": enrollment_id, "formats": ["pack", "pdf"]})
    print("export refusal:", export.get("ok"), json.dumps(export.get("error")))

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"course_id": course_id, "enrollment_id": enrollment_id,
                   "wire_version": VERSION, "revision_after": revision,
                   "before": before, "after_replan": mid, "after_edit": after,
                   "export_attempt": {"ok": export.get("ok"), "error": export.get("error")},
                   "calls": LOG}, fh, indent=2)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
