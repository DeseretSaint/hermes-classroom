#!/usr/bin/env python3
"""Call one Coursebook contract method against the live isolated backend.

Kept tiny on purpose: the reviewer can paste the same call, and the revision/idempotency fields are
supplied explicitly instead of being guessed.

    scripts/cb013-rpc.py check.open '{"enrollment_id": "...", "objective_id": "..."}' [expected_revision]

Environment: CB013_BASE (default http://127.0.0.1:44219), CB013_TOKEN (default cb013-test-token).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44219")
TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")


def wire_version() -> int:
    """The backend's own wire version — never a hard-coded one."""
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/runtime?profile=",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        runtime = json.loads(response.read())
    return int(runtime.get("wire_version") or 0)


def call(method: str, payload: dict, expected_revision: int | None = None, **extra) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": wire_version(),
        "method": method,
        "operation_id": f"cb013-{method.replace('.', '-')}-{int(time.time() * 1000)}",
        "idempotency_key": f"cb013-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    body.update(extra)
    request = urllib.request.Request(
        f"{BASE}/api/plugins/coursebook/rpc?profile=",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    method = sys.argv[1]
    payload = json.loads(sys.argv[2])
    revision = int(sys.argv[3]) if len(sys.argv) > 3 else None
    print(json.dumps(call(method, payload, revision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
