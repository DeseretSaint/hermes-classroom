"""Read back one CP-015g/D1 live run: job view, outline, validation records, usage.

Read-only. Takes the job id and enrollment id from the run record produced by
repro_cp015g_d1.py, so nothing is authored by this script.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

CONTRACT = "cb.rpc"
CONTRACT_VERSION = 26


def rpc(port: int, token: str, method: str, payload: dict) -> dict:
    body = {
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "method": method,
        "operation_id": f"cp015g-d1-read-{method.replace('.', '-')}-{os.urandom(4).hex()}",
        "payload": payload,
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/plugins/coursebook/rpc",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--enrollment", required=True)
    parser.add_argument("--course", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = {
        "job": rpc(args.port, args.token, "jobs.get", {"job_id": args.job}),
        "outline": rpc(args.port, args.token, "course.outline", {"enrollment_id": args.enrollment}),
        "usage": rpc(args.port, args.token, "usage.summary", {"course_id": args.course}),
        "course": rpc(args.port, args.token, "course.get", {"course_id": args.course}),
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2)
    job = (out["job"].get("result") or {}).get("job") or {}
    print(json.dumps(
        {
            "state": job.get("state"),
            "error": job.get("error"),
            "usage": (job.get("activity") or {}).get("usage"),
            "objectives": len(((out["outline"].get("result") or {}).get("objectives") or [])),
            "plan_state": (((out["outline"].get("result") or {}).get("plan") or {}).get("state")),
            "validation": (((out["outline"].get("result") or {}).get("plan") or {}).get("validation")),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
