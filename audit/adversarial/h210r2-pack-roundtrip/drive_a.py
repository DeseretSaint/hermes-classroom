"""H-210-R2 store A: import both bundled packs, export twice each, mint handles, hash the bytes.

Every call goes over the live HTTP route (``POST /api/plugins/coursebook/rpc``) exactly as the
Desktop sends it. No handler is imported in this process; the only local reads are of files the
backend itself wrote (export archives, artifact objects) so their bytes can be hashed independently.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import h210r2lib
from h210r2lib import Client, page_report, sha256_file

SCRATCH = h210r2lib.SCRATCH
INPUTS = SCRATCH / "inputs"
EVIDENCE = SCRATCH / "evidence-storeA.json"
BASE = "http://127.0.0.1:44339"
TOKEN = "h210r2-storeA-token"


def sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> int:
    client = Client(BASE, TOKEN)
    evidence: dict = {
        "base": BASE,
        "store": "storeA",
        "release_commit": __import__("subprocess").check_output(
            ["git", "-C", str(h210r2lib.ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "wire_version": client.wire_version(),
    }
    status, runtime = client.http("GET", "/api/plugins/coursebook/runtime?profile=")
    evidence["runtime"] = {"http": status, "response": runtime}
    status, intake = client.http("GET", "/api/plugins/coursebook/packs/intake?profile=")
    evidence["packs_intake"] = {"http": status, "response": intake}

    inputs = json.loads((INPUTS / "inputs.json").read_text(encoding="utf-8"))
    evidence["input_archives"] = inputs

    imports = {}
    for label, filename in (
        ("japanese", "japanese-affection-context-l0-2.1.0.zip"),
        ("demo", "technical-demo-pack-2.0.0.zip"),
    ):
        zip_path = INPUTS / filename
        status, granted = client.http(
            "POST", "/api/plugins/coursebook/packs/grant?profile=", {"path": str(zip_path)}
        )
        evidence[f"grant_{label}"] = {"http": status, "response": granted}
        assert granted.get("ok"), granted
        staged_id = granted["staged_id"]
        evidence[f"preview_{label}"] = client.rpc("pack.preview", {"staged_id": staged_id})
        imported = client.rpc(
            "pack.import", {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key=f"h210r2-import-{label}-{time.time_ns()}",
        )
        evidence[f"import_{label}"] = imported
        imports[label] = imported.get("result") or {}
        evidence[f"input_zip_sha256_{label}"] = sha256_file(zip_path)
        print(label, "import:", json.dumps(imports[label], sort_keys=True))

    # Second import of the same content must not duplicate a course or an artifact row.
    again = INPUTS / "japanese-affection-context-l0-2.1.0.zip"
    status, granted = client.http("POST", "/api/plugins/coursebook/packs/grant?profile=",
                                  {"path": str(again)})
    evidence["grant_japanese_resume"] = {"http": status, "response": granted}
    replay = client.rpc("pack.import", {"staged_id": granted["staged_id"], "mode": "resume"},
                        idempotency_key=f"h210r2-import-japanese-resume-{time.time_ns()}")
    evidence["import_japanese_resume"] = replay

    # Third import with mode=fresh: a second `fresh` on the same store must still dedupe.
    status, granted = client.http("POST", "/api/plugins/coursebook/packs/grant?profile=",
                                  {"path": str(again)})
    evidence["grant_japanese_second_fresh"] = {"http": status, "response": granted}
    second_fresh = client.rpc("pack.import", {"staged_id": granted["staged_id"], "mode": "fresh"},
                              idempotency_key=f"h210r2-import-japanese-fresh2-{time.time_ns()}")
    evidence["import_japanese_second_fresh"] = second_fresh

    evidence["inspect_japanese"] = client.rpc("pack.inspect", {
        "pack_id": "japanese-affection-context-l0", "pack_version": "2.1.0"})
    evidence["inspect_demo"] = client.rpc("pack.inspect", {
        "pack_id": "technical-demo-pack", "pack_version": "2.0.0"})
    evidence["pack_list"] = client.rpc("pack.list", {})

    # Two exports per pack on the same store: identical bytes and identical content_hash.
    exports = {}
    for label in ("japanese", "demo"):
        enrollment_id = imports[label]["enrollment_id"]
        attempts = []
        for attempt in (1, 2):
            result = client.rpc(
                "pack.export", {"enrollment_id": enrollment_id},
                idempotency_key=f"h210r2-export-{label}-{attempt}-{time.time_ns()}",
            )
            attempts.append(result)
            evidence[f"export_{label}_attempt_{attempt}"] = result
        exports[label] = attempts

    export_dir = SCRATCH / "storeA" / "plugin-data" / "coursebook" / "pack-exports"
    evidence["export_files"] = {
        str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(export_dir.glob("*.zip"))
    }

    # Export artifact: artifact.get must stay prefixed and the handle must return the archive bytes.
    export_fetches = {}
    for label, attempts in exports.items():
        artifact_id = (attempts[0].get("result") or {}).get("artifact_id")
        detail = client.rpc("artifact.get", {"artifact_id": artifact_id})
        entry = {"artifact_id": artifact_id, "artifact_get": detail}
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
        export_fetches[label] = entry
        evidence[f"export_artifact_{label}"] = entry

    # course.export on a pack-backed enrollment: the contract's typed refusal, recorded not hidden.
    japanese_enrollment = imports["japanese"]["enrollment_id"]
    evidence["course_export_read"] = client.rpc("course.export.read",
                                                {"enrollment_id": japanese_enrollment})
    evidence["course_export"] = client.rpc(
        "course.export",
        {"enrollment_id": japanese_enrollment, "expected_content_hash": "sha256:" + "0" * 64},
        idempotency_key=f"h210r2-course-export-{time.time_ns()}",
    )

    # Every lesson page of both courses, read through the contract.
    for label, enrollment in imports.items():
        evidence[f"pages_{label}"] = page_report(client, enrollment["enrollment_id"])
        evidence[f"outline_{label}"] = client.rpc("course.outline",
                                                  {"enrollment_id": enrollment["enrollment_id"]})
        evidence[f"binding_{label}"] = client.rpc("binding.get",
                                                  {"enrollment_id": enrollment["enrollment_id"]})

    # Every media segment: artifact.get must answer a contract-shaped, manifest-matching hash and
    # the download handle must return the exact pack bytes.
    media = {}
    for label, filename in (
        ("japanese", "japanese-affection-context-l0-2.1.0.zip"),
        ("demo", "technical-demo-pack-2.0.0.zip"),
    ):
        key_name = ("japanese-affection-context-l0" if label == "japanese"
                    else "technical-demo-pack")
        declared = inputs[key_name]
        segments = evidence[f"pages_{label}"]["media_segments"]
        for index, segment in enumerate(segments, start=1):
            artifact_id = segment["artifact_id"]
            key = f"{label}:{index}:{artifact_id}"
            detail = client.rpc("artifact.get", {"artifact_id": artifact_id})
            declared_hash = declared["media"].get(str(segment.get("path"))) if segment.get("path") else None
            entry = {
                "pack": label,
                "segment": segment,
                "declared_sha256": declared_hash,
                "artifact_get": detail,
            }
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

    EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "release_commit": evidence["release_commit"],
        "wire_version": evidence["wire_version"],
        "intake": intake,
        "imports": imports,
        "resume": (replay.get("result") or replay),
        "second_fresh": (second_fresh.get("result") or second_fresh),
        "exports": {label: [(a.get("result") or a) for a in attempts] for label, attempts in exports.items()},
        "export_files": evidence["export_files"],
        "export_artifacts": export_fetches,
        "pages": {label: {
            "segment_totals": evidence[f"pages_{label}"]["segment_totals"],
            "media_segments": evidence[f"pages_{label}"]["media_segments"],
        } for label in ("japanese", "demo")},
        "media": {k: {"ok": v["artifact_get"].get("ok"),
                      "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
                      "error": (v["artifact_get"].get("error") or {}).get("code"),
                      "handle": v.get("handle")} for k, v in media.items()},
        "course_export": evidence["course_export"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
