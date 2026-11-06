#!/usr/bin/env python3
"""CB-014 correction evidence (t_652f3d71): are `course.get`/`course.outline` actually served?

Black-box through the real ASGI app (same router loading as ``scripts/probe-backend.py``) against
a throwaway ``HERMES_HOME``: grant the bundled demo pack, import it fresh, then call the two reads
the REVIEW_CB014 limits bullet once called unimplemented, and re-read the /runtime registry.

    python3 tests/adversarial/verify_v6_reads.py [--repo ROOT] [--json OUT]

Exit code 0 only when both reads answer ``ok: true`` and the registry reports every contracted
method implemented with no contract problems.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from coursebook import contracts  # noqa: E402

WIRE_VERSION = contracts.WIRE_CONTRACT_VERSION


def load_router():
    spec = importlib.util.spec_from_file_location(
        "coursebook_plugin_api_v6reads", ROOT / "dashboard" / "plugin_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="write the step records here")
    args = parser.parse_args()

    home = tempfile.TemporaryDirectory(prefix="cb-014-reads-")
    os.environ["HERMES_HOME"] = home.name

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from coursebook import archive as pack_archive

    app = FastAPI()
    app.include_router(load_router(), prefix="/api/plugins/coursebook")
    client = TestClient(app)

    source = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
    manifest, files = pack_archive.read_directory(source)
    bundle = Path(home.name) / "bundle.zip"
    pack_archive.write_archive(bundle, manifest, files)

    records: list[dict] = []

    def rpc(method: str, payload: dict) -> tuple[int, dict]:
        body = {
            "contract": "cb.rpc",
            "contract_version": WIRE_VERSION,
            "method": method,
            "operation_id": f"cb014-{method.replace('.', '-')}",
            "payload": payload,
        }
        response = client.post("/api/plugins/coursebook/rpc", json=body)
        return response.status_code, response.json()

    grant = client.post("/api/plugins/coursebook/packs/grant", json={"path": str(bundle)}).json()
    status, imported = rpc("pack.import", {"staged_id": grant["staged_id"], "mode": "fresh"})
    records.append({"step": "pack.import", "http": status, "body": imported})
    print(json.dumps(records[-1]))
    if imported.get("ok") is not True:
        print("SUMMARY: FAIL pack.import did not create a course")
        return 1

    enrollment_id = imported["result"]["enrollment_id"]
    course_id = imported["result"]["course_id"]

    failures: list[str] = []
    for method, payload in (
        ("course.get", {"course_id": course_id}),
        ("course.outline", {"enrollment_id": enrollment_id}),
    ):
        status, body = rpc(method, payload)
        ok = status == 200 and body.get("ok") is True
        records.append({
            "step": method,
            "http": status,
            "ok": ok,
            "result_keys": sorted(body.get("result", {}).keys()),
            "error": body.get("error"),
        })
        print(json.dumps(records[-1]))
        if not ok:
            failures.append(method)

    runtime_response = client.get("/api/plugins/coursebook/runtime").json()
    runtime = runtime_response.get("body", runtime_response)
    implemented = runtime.get("implemented_methods", [])
    registry = {
        "step": "registry",
        "contract_methods": runtime.get("contract_methods"),
        "implemented": len(implemented),
        "contract_problems": runtime.get("contract_problems"),
        "course.get": "course.get" in implemented,
        "course.outline": "course.outline" in implemented,
    }
    records.append(registry)
    print(json.dumps(registry))
    if not (registry["course.get"] and registry["course.outline"]
            and registry["contract_problems"] == []
            and registry["implemented"] == registry["contract_methods"]):
        failures.append("registry")

    print("SUMMARY:", "PASS" if not failures else f"FAIL {failures}")
    if args.json:
        Path(args.json).write_text(json.dumps(records, indent=2) + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
