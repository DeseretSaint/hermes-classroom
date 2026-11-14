#!/usr/bin/env python3
"""Prove the media preview is reachable over the real ASGI route, not only as a function call.

Builds the shipped ``dashboard.plugin_api.router`` into a FastAPI app (the host mounts it at
``/api/plugins/coursebook/``) and issues real HTTP requests through Starlette's TestClient.
Host auth middleware is not part of this module; it is noted as an out-of-scope seam.

Usage: python3 route_http_probe.py --home /path/to/prepared/home --out route.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")
AUDIO = "art_adf2e015a0694641a409bb54e9a6a746"
IMAGE = "art_d7dc7afd153d4736abc4d2e0560a8376"
AUDIO_SHA = "208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c"
IMAGE_SHA = "a206b3493098e7616c77575cc5a4b252ee36da43b58df14d03183fbc91573d6c"
CHECKS: list[dict] = []


def check(check_id: str, ok: bool, detail: object) -> None:
    CHECKS.append({"id": check_id, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + check_id + " :: " + json.dumps(detail, ensure_ascii=False)[:300])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    home = Path(args.home).resolve()
    os.environ["HERMES_HOME"] = str(home)
    sys.path.insert(0, str(REPO))
    sys.path.append(str(HERMES_AGENT))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from dashboard import plugin_api

    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/coursebook")
    client = TestClient(app)

    for artifact_id, want_sha, want_mime in (
        (AUDIO, AUDIO_SHA, "audio/mpeg"),
        (IMAGE, IMAGE_SHA, "image/png"),
    ):
        response = client.get(f"/api/plugins/coursebook/media/{artifact_id}")
        body = response.json()
        prefix = artifact_id[:12]
        check(f"{prefix}:http_200", response.status_code == 200, response.status_code)
        check(f"{prefix}:http_body_ok", body.get("ok") is True, body.get("code"))
        data_url = str(body.get("data_url") or "")
        check(f"{prefix}:http_data_url_mime",
              data_url.startswith(f"data:{want_mime};base64,"), data_url[:40])
        decoded = base64.b64decode(data_url.split(",", 1)[1]) if "," in data_url else b""
        check(f"{prefix}:http_sha256_matches_record",
              hashlib.sha256(decoded).hexdigest() == want_sha,
              hashlib.sha256(decoded).hexdigest())

    missing = client.get("/api/plugins/coursebook/media/art_missing00000000000000000000000000")
    check("missing:refused_as_data", missing.status_code == 200 and missing.json().get("ok") is not True,
          {"status": missing.status_code, "body": missing.json()})

    failures = [c for c in CHECKS if not c["ok"]]
    result = {
        "kind": "http_route_probe",
        "verifier": "sentinel",
        "checks_total": len(CHECKS),
        "checks_passed": len(CHECKS) - len(failures),
        "failures": [c["id"] for c in failures],
        "status": "PASS" if not failures else "FAIL",
        "checks": CHECKS,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "checks_total", "checks_passed", "failures")},
                     indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
