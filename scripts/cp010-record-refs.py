#!/usr/bin/env python3
"""CP-010: record the reference image each pose was actually generated from.

Every pose call passed M1's provider media URL in ``reference_image_urls``; this
script writes that fact into prompts.json so the provenance row is not a claim
made from memory. It is idempotent and refuses to overwrite a differing value.

Usage: python3 scripts/cp010-record-refs.py
"""
import json

PATH = "audit/cp010-fox/prompts.json"

with open(PATH) as fh:
    doc = json.load(fh)

sheet = next(p for p in doc["prompts"] if p["id"] == "M1")["media_url"]
changed = 0
for p in doc["prompts"]:
    if not p["id"].startswith("P-"):
        continue
    current = p.get("reference_image_urls")
    if current is None:
        p["reference_image_urls"] = [sheet]
        changed += 1
    elif current != [sheet]:
        raise SystemExit(f"{p['id']} already records a different reference: {current}")

with open(PATH, "w") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print(f"recorded the model sheet reference on {changed} pose prompts")
