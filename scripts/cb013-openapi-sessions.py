#!/usr/bin/env python3
"""Print the request/response shape of the host's session-create route."""
import json
import urllib.request

req = urllib.request.Request("http://127.0.0.1:44219/openapi.json", headers={"Authorization": "Bearer cb013-test-token"})
spec = json.load(urllib.request.urlopen(req, timeout=10))
item = spec["paths"]["/api/sessions"]
for method, op in item.items():
    if method not in ("post", "get"):
        continue
    print("==", method.upper(), op.get("summary"))
    body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    print("body:", json.dumps(body, ensure_ascii=False)[:800])
    params = op.get("parameters") or []
    print("params:", json.dumps(params, ensure_ascii=False)[:500])
    print("responses:", list(op.get("responses", {}).keys()))
