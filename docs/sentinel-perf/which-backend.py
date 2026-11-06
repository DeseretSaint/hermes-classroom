#!/usr/bin/env python3
"""Which backend is the window actually reading? Compare library titles per port."""
import json
import sys
import urllib.request
import uuid

PORTS = {
    44219: "cb013-test-token",
    44220: "cb013-test-token",
    44241: "sentinel-perf-token",
}


def call(base, token, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}/api/plugins/coursebook{path}",
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


for port, token in PORTS.items():
    base = f"http://127.0.0.1:{port}"
    try:
        runtime = call(base, token, "/runtime")
        version = int(runtime["wire_version"])
        library = call(base, token, "/rpc", {
            "contract": "cb.rpc", "contract_version": version, "method": "library.list",
            "operation_id": f"probe-{uuid.uuid4().hex[:8]}", "payload": {"filter": "all", "limit": 100},
        })
        items = (library.get("result") or {}).get("items", [])
        print(port, "plugin_root=", runtime.get("plugin_root"))
        for item in items:
            print("   ", item.get("enrollment_id"), "|", ((item.get("course") or {}).get("title") or "")[:90])
    except Exception as exc:  # noqa: BLE001
        print(port, "ERROR", exc)
