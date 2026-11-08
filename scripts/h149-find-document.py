#!/usr/bin/env python3
import json, sys
sys.path.insert(0, "scripts")
from importlib import import_module
cb = import_module("cb013-rpc")

listing = cb.call("library.list", {})
for row in (listing.get("result") or {}).get("items") or []:
    enr = row.get("enrollment_id")
    outline = cb.call("course.outline", {"enrollment_id": enr})
    units = ((outline.get("result") or {}).get("plan") or {}).get("units") or []
    print("=", row.get("title"), row.get("recipe"))
    for unit in units:
        for obj in unit.get("objectives") or []:
            page = cb.call("lesson.page", {"enrollment_id": enr, "objective_id": obj.get("objective_id")})
            result = page.get("result") or {}
            doc = result.get("document") or {}
            blocks = doc.get("blocks") or []
            print("  ", obj.get("ordinal"), obj.get("title")[:40], "| doc", bool(doc), "blocks", len(blocks),
                  "check", doc.get("check_id"), "state", doc.get("state"), "views", doc.get("views"),
                  "segments", len(result.get("segments") or []))
