#!/usr/bin/env python3
"""Print the newest attempts for the demo enrollment (grading provenance, criteria, evidence class)."""
import json
import subprocess

raw = subprocess.run(
    ["python3", "scripts/cb013-rpc.py", "quiz.history",
     '{"enrollment_id":"enr_544f0aba033e4fc0a2f50fb61aceda25"}'],
    capture_output=True, text=True, check=True,
).stdout
payload = json.loads(raw)
for attempt in payload["result"]["attempts"][:4]:
    print(json.dumps({
        "attempt_id": attempt["attempt_id"],
        "objective_id": attempt["objective_id"],
        "verdict": attempt["verdict"],
        "evidence_class": attempt["evidence_class"],
        "answer": attempt["answer"],
        "criteria": attempt["criteria"],
        "provenance": attempt["grading_provenance"],
        "created_at": attempt["created_at"],
    }, ensure_ascii=False, indent=1))
