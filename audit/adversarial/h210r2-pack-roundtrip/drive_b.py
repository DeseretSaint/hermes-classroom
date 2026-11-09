"""H-210-R2 store B (fresh home): re-import the two exports from store A, then re-export.

Nothing is copied from store A except the two exported archive files; the database, pack library,
staging area and artifact store are all created new by this backend.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import h210r2lib
from h210r2lib import Client, page_report, sha256_file

SCRATCH = h210r2lib.SCRATCH
EXPORTS = SCRATCH / "storeA" / "plugin-data" / "coursebook" / "pack-exports"
EVIDENCE = SCRATCH / "evidence-storeB.json"
BASE = "http://127.0.0.1:44340"
TOKEN = "h210r2-storeB-token"


def sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> int:
    client = Client(BASE, TOKEN)
    evidence: dict = {"base": BASE, "store": "storeB", "wire_version": client.wire_version()}
    status, runtime = client.http("GET", "/api/plugins/coursebook/runtime?profile=")
    evidence["runtime"] = {"http": status, "response": runtime}
    status, intake = client.http("GET", "/api/plugins/coursebook/packs/intake?profile=")
    evidence["packs_intake"] = {"http": status, "response": intake}

    inputs = {}
    for label, filename in (
        ("japanese", "japanese-affection-context-l0-2.1.0-5343526daa29a310.zip"),
        ("demo", "technical-demo-pack-2.0.0-ff5594a816570084.zip"),
    ):
        archive_path = EXPORTS / filename
        inputs[label] = {
            "path": str(archive_path),
            "sha256": sha256_file(archive_path),
            "bytes": archive_path.stat().st_size,
        }
        status, granted = client.http(
            "POST", "/api/plugins/coursebook/packs/grant?profile=", {"path": str(archive_path)}
        )
        evidence[f"grant_{label}"] = {"http": status, "response": granted}
        assert granted.get("ok"), granted
        staged_id = granted["staged_id"]
        evidence[f"preview_{label}"] = client.rpc("pack.preview", {"staged_id": staged_id})
        imported = client.rpc(
            "pack.import", {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key=f"h210r2-b-reimport-{label}-{time.time_ns()}",
        )
        evidence[f"import_{label}"] = imported
    evidence["reimport_inputs"] = inputs

    imports = {label: evidence[f"import_{label}"].get("result") or {} for label in ("japanese", "demo")}
    for label, enrollment in imports.items():
        evidence[f"pages_{label}"] = page_report(client, enrollment["enrollment_id"])
        evidence[f"inspect_{label}"] = client.rpc("pack.inspect", {
            "pack_id": enrollment["pack_id"],
            "pack_version": "2.1.0" if label == "japanese" else "2.0.0",
        })

    # Media fetch on the fresh store: every segment, hash, handle.
    media = {}
    for label in ("japanese", "demo"):
        for index, segment in enumerate(evidence[f"pages_{label}"]["media_segments"], start=1):
            artifact_id = segment["artifact_id"]
            key = f"{label}:{index}:{artifact_id}"
            detail = client.rpc("artifact.get", {"artifact_id": artifact_id})
            entry = {"pack": label, "segment": segment, "artifact_get": detail}
            download = (detail.get("result") or {}).get("download") or {}
            if detail.get("ok") and download.get("url"):
                status, content_type, data = client.fetch(download["url"])
                entry["handle"] = {
                    "url": download["url"],
                    "http": status,
                    "content_type": content_type,
                    "bytes": len(data),
                    "sha256": sha_bytes(data),
                }
            media[key] = entry
    evidence["media_artifacts"] = media

    # A fresh export from store B: same content hash and same archive bytes as store A wrote.
    for label in ("japanese", "demo"):
        evidence[f"export_{label}"] = client.rpc(
            "pack.export", {"enrollment_id": imports[label]["enrollment_id"]},
            idempotency_key=f"h210r2-b-export-{label}-{time.time_ns()}",
        )
    export_dir = SCRATCH / "storeB" / "plugin-data" / "coursebook" / "pack-exports"
    evidence["export_files"] = {
        str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(export_dir.glob("*.zip"))
    }

    EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "wire_version": evidence["wire_version"],
        "reimport_inputs": inputs,
        "imports": imports,
        "pages": {label: {
            "segment_totals": evidence[f"pages_{label}"]["segment_totals"],
            "media_segments": evidence[f"pages_{label}"]["media_segments"],
        } for label in ("japanese", "demo")},
        "media": {k: {"ok": v["artifact_get"].get("ok"),
                      "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
                      "error": (v["artifact_get"].get("error") or {}).get("code"),
                      "handle": v.get("handle")} for k, v in media.items()},
        "exports": {label: evidence[f"export_{label}"].get("result") for label in ("japanese", "demo")},
        "export_files": evidence["export_files"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
