#!/usr/bin/env python3
"""Exercise the Coursebook backend routes exactly as the Desktop half reaches them.

Runs against a throwaway ``HERMES_HOME`` so no operator profile, plugin-data directory or
database is touched. The router is loaded the way the gateway loads it — by path from
``dashboard/plugin_api.py`` — and driven through FastAPI's TestClient (the real ASGI app).

Prints one JSON object per request and a summary. Exit code is non-zero when an expectation
fails, so it can run as a gate in ``scripts/validate.sh`` and as the RPC trace in a review packet.

    python3 scripts/probe-backend.py [--trace path/to/trace.json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import contracts  # noqa: E402 - path must be set first

WIRE_VERSION = contracts.WIRE_CONTRACT_VERSION


def load_router():
    spec = importlib.util.spec_from_file_location(
        "coursebook_plugin_api_probe", ROOT / "dashboard" / "plugin_api.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load dashboard/plugin_api.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


def envelope(method: str, payload: dict, **overrides) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": WIRE_VERSION,
        "method": method,
        "operation_id": f"probe-{method.replace('.', '-')}",
        "payload": payload,
    }
    body.update(overrides)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", help="write the full trace JSON to this path")
    args = parser.parse_args()

    home = tempfile.TemporaryDirectory(prefix="coursebook-probe-home-")
    os.environ["HERMES_HOME"] = home.name
    # plugin_storage resolves paths per call, but a stale module-level cache would defeat the
    # isolation; import order below is deliberate (HERMES_HOME first).

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(load_router(), prefix="/api/plugins/coursebook")
    client = TestClient(app)

    trace: list[dict] = []
    failures: list[str] = []

    def record(name: str, expectation: bool, request, response) -> None:
        entry = {
            "step": name,
            "ok": expectation,
            "status": response.status_code,
            "body": response.json(),
        }
        trace.append(entry)
        print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        if not expectation:
            failures.append(name)

    health = client.get("/api/plugins/coursebook/health")
    record(
        "GET /health answers an ok envelope and states db readiness",
        health.status_code == 200
        and health.json().get("ok") is True
        and "ready" in health.json()["result"]["db"],
        None,
        health,
    )

    schema = client.get("/api/plugins/coursebook/schema")
    listed = {entry["id"] for entry in schema.json()["result"]["contracts"]} if schema.status_code == 200 else set()
    record(
        "GET /schema lists every frozen contract in the inventory",
        schema.status_code == 200 and listed == set(contracts.contract_ids()),
        None,
        schema,
    )

    runtime = client.get("/api/plugins/coursebook/runtime")
    implemented = runtime.json().get("implemented_methods")
    record(
        "GET /runtime exposes the backend method registry (Desktop reads this)",
        runtime.status_code == 200 and isinstance(implemented, list) and "binding.get" in implemented,
        None,
        runtime,
    )

    rpc_health = client.post("/api/plugins/coursebook/rpc", json=envelope("health.get", {}))
    record(
        "POST /rpc health.get",
        rpc_health.status_code == 200 and rpc_health.json().get("ok") is True,
        None,
        rpc_health,
    )

    bad = client.post("/api/plugins/coursebook/rpc", json={"method": "health.get"})
    record(
        "POST /rpc malformed envelope is a VALIDATION_FAILED envelope (HTTP 200)",
        bad.status_code == 200 and bad.json().get("error", {}).get("code") == "VALIDATION_FAILED",
        None,
        bad,
    )

    binding_none = client.post("/api/plugins/coursebook/rpc", json=envelope("binding.get", {}))
    record(
        "POST /rpc binding.get without an identifier is VALIDATION_FAILED",
        binding_none.json().get("error", {}).get("code") == "VALIDATION_FAILED",
        None,
        binding_none,
    )

    binding_both = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope("binding.get", {"session_id": "s1", "enrollment_id": "e1"}),
    )
    record(
        "POST /rpc binding.get with both identifiers is VALIDATION_FAILED",
        binding_both.json().get("error", {}).get("code") == "VALIDATION_FAILED",
        None,
        binding_both,
    )

    binding_unmigrated = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope("binding.get", {"session_id": "stored-session-abc"}),
    )
    record(
        "POST /rpc binding.get on an unmigrated database refuses instead of claiming 'unbound'",
        binding_unmigrated.json().get("error", {}).get("code") == "NOT_IMPLEMENTED",
        None,
        binding_unmigrated,
    )

    later = client.post("/api/plugins/coursebook/rpc", json=envelope("library.list", {}))
    record(
        "POST /rpc for a frozen method with no handler is refused, never faked",
        later.json().get("ok") is False,
        None,
        later,
    )

    if args.trace:
        Path(args.trace).write_text(json.dumps(trace, indent=2), encoding="utf-8")
        print(f"\ntrace written to {args.trace}")

    home.cleanup()
    if failures:
        print(f"\nFAILED: {len(failures)} expectation(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"\nAll {len(trace)} backend expectations passed against an isolated HERMES_HOME.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
