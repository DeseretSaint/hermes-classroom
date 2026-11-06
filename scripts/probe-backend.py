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
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import zipfile
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
        content_type = response.headers.get("content-type", "")
        entry = {
            "step": name,
            "ok": expectation,
            "status": response.status_code,
        }
        if "json" in content_type:
            entry["body"] = response.json()
        else:
            # A download is bytes, not a document: record what travelled, never decode it.
            entry["body"] = {
                "binary": True,
                "content_type": content_type,
                "bytes": len(response.content),
                "sha256": "sha256:" + hashlib.sha256(response.content).hexdigest(),
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
    record(
        "GET /schema lists all six frozen contracts",
        schema.status_code == 200 and len(schema.json()["result"]["contracts"]) == 6,
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

    # CB-010: every frozen method now has a handler, so this probe uses a method name that is not
    # in the contract at all — the envelope must be refused, never silently accepted.
    later = client.post("/api/plugins/coursebook/rpc", json=envelope("course.teleport", {}))
    record(
        "POST /rpc for a method not in the mounted contract is refused, never faked",
        later.json().get("ok") is False,
        None,
        later,
    )

    # ── CB-010: local pack intake → import → export → authenticated download ──────────
    from coursebook import archive as pack_archive

    intake = client.get("/api/plugins/coursebook/packs/intake")
    record(
        "GET /packs/intake answers the host intake capability",
        intake.status_code == 200 and intake.json().get("can_grant") is True,
        None,
        intake,
    )

    bad_grant = client.post("/api/plugins/coursebook/packs/grant", json={"path": "relative/pack.zip"})
    record(
        "POST /packs/grant refuses a relative path instead of guessing a location",
        bad_grant.status_code == 200 and bad_grant.json().get("ok") is False,
        None,
        bad_grant,
    )

    source = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
    manifest, files = pack_archive.read_directory(source)
    bundle = Path(home.name) / "probe-pack.zip"
    pack_archive.write_archive(bundle, manifest, files)
    granted = client.post("/api/plugins/coursebook/packs/grant", json={"path": str(bundle)})
    record(
        "POST /packs/grant mints a staged_id for a real archive",
        granted.status_code == 200 and bool(granted.json().get("staged_id")),
        None,
        granted,
    )

    staged_id = granted.json().get("staged_id", "")
    preview = client.post("/api/plugins/coursebook/rpc", json=envelope("pack.preview", {"staged_id": staged_id}))
    record(
        "pack.preview returns the manifest, integrity and separate trust labels",
        preview.json().get("ok") is True
        and set(preview.json()["result"]) == {"manifest", "integrity", "trust"}
        and preview.json()["result"]["manifest"]["content_hash"] == manifest["content_hash"],
        None,
        preview,
    )

    imported = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key="probe-pack-import-0001",
        ),
    )
    record(
        "pack.import creates a course and enrollment from the bundle",
        imported.json().get("ok") is True
        and imported.json()["result"]["pack_id"] == manifest["pack_id"]
        and bool(imported.json()["result"]["enrollment_id"]),
        None,
        imported,
    )

    enrollment_id = imported.json().get("result", {}).get("enrollment_id", "")
    exported = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope(
            "pack.export",
            {"enrollment_id": enrollment_id, "options": {"expected_content_hash": manifest["content_hash"]}},
        ),
    )
    export_body = exported.json().get("result") or {}
    record(
        "pack.export returns the exact reviewed content hash",
        exported.json().get("ok") is True and export_body.get("content_hash") == manifest["content_hash"],
        None,
        exported,
    )

    artifact = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope("artifact.get", {"artifact_id": export_body.get("artifact_id", "")}),
    )
    handle = (artifact.json().get("result") or {}).get("download", {}).get("handle", "")
    download = client.get(f"/api/plugins/coursebook/artifacts/{handle}")
    digest = "sha256:" + hashlib.sha256(download.content).hexdigest()
    record(
        "GET /artifacts/<handle> streams the exported bytes with a matching hash",
        download.status_code == 200
        and download.headers.get("content-type", "").startswith("application/zip")
        and len(download.content) == int(export_body.get("bytes") or 0)
        and digest == (artifact.json().get("result") or {}).get("content_hash"),
        None,
        download,
    )

    missing = client.get("/api/plugins/coursebook/artifacts/art_" + "0" * 32 + "_99999999999")
    record(
        "GET /artifacts/<handle> refuses an unknown handle without a path or traceback",
        missing.status_code == 404 and "path" not in missing.text.lower(),
        None,
        missing,
    )

    # ── reimport: resume keeps progress, fresh separates it; a tampered pack leaves no residue ──
    def library_total() -> int:
        listed = client.post("/api/plugins/coursebook/rpc", json=envelope("library.list", {}))
        return int((listed.json().get("result") or {}).get("total") or 0)

    def grant(path: Path) -> str:
        """Every import needs its own grant: adoption consumes the staged pack."""
        response = client.post("/api/plugins/coursebook/packs/grant", json={"path": str(path)})
        return str(response.json().get("staged_id", ""))

    resume = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope(
            "pack.import",
            {"staged_id": grant(bundle), "mode": "resume"},
            idempotency_key="probe-pack-resume-0001",
        ),
    )
    record(
        "pack.import mode=resume re-opens the same enrollment instead of a second course",
        resume.json().get("ok") is True
        and (resume.json().get("result") or {}).get("enrollment_id") == enrollment_id,
        None,
        resume,
    )

    second = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope(
            "pack.import",
            {"staged_id": grant(bundle), "mode": "fresh"},
            idempotency_key="probe-pack-fresh-0002",
        ),
    )
    second_body = second.json().get("result") or {}
    record(
        "pack.import mode=fresh cuts a distinct course over the same immutable content",
        second.json().get("ok") is True
        and second_body.get("enrollment_id") not in ("", None, enrollment_id)
        and second_body.get("course_id") not in ("", None, imported.json()["result"]["course_id"])
        and second_body.get("pack_id") == manifest["pack_id"],
        None,
        second,
    )

    tampered_path = Path(home.name) / "tampered-pack.zip"
    with zipfile.ZipFile(bundle) as source_zip:
        entries = [(info.filename, source_zip.read(info.filename)) for info in source_zip.infolist()]
    with zipfile.ZipFile(tampered_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for name, data in entries:
            if name.endswith("section-01-two-ways.md"):
                # One byte appended: the manifest hash can no longer match the file.
                data = data + b"\n"
            out_zip.writestr(name, data)

    before = library_total()
    tampered = client.post(
        "/api/plugins/coursebook/rpc",
        json=envelope("pack.preview", {"staged_id": grant(tampered_path)}),
    )
    after = library_total()
    record(
        "a pack whose bytes no longer match its manifest is refused with no library residue",
        tampered.json().get("ok") is False
        and (tampered.json().get("error") or {}).get("code") == "PACK_REJECTED"
        and after == before,
        None,
        tampered,
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
