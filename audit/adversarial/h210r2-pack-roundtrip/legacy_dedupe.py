"""H-210-R2 step 5: the (content_hash, kind) dedupe across both stored spellings, driven live.

The repair writes new rows in the labelled ``sha256:<64 hex>`` form and normalises on read. A store
that predates the repair holds *bare* 64-hex rows. This script reproduces that legacy storage state
faithfully in the isolated test store — it rewrites the pack media rows from the labelled spelling
back to the bare spelling they had before ``160c522`` (backing the database up first) — and then
drives the live route to prove three things:

1. ``artifact.get`` on a legacy bare row still answers the labelled contract hash and a fetchable
   handle whose bytes hash to the manifest's declared digest (read-boundary normalisation);
2. re-importing the same pack twice into that same store does **not** create a second row for any
   ``(content_hash, kind)`` — the legacy bare row absorbs the labelled write (``ref_count`` grows);
3. the legacy row keeps the spelling it already had (no row is rewritten by any read path).

The injected rows are labelled as injected in the capture; the pre-injection database copy is kept
beside it.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

import h210r2lib
from h210r2lib import Client

S = h210r2lib.SCRATCH
DB = S / "storeA" / "plugin-data" / "coursebook" / "data.db"
BACKUP = S / "storeA-data-before-legacy-injection.db"
OUT = S / "evidence-dedupe.json"
BASE = "http://127.0.0.1:44339"
TOKEN = "h210r2-storeA-token"
INPUTS = S / "inputs"


def sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def snapshot() -> dict:
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [
            {k: row[k] for k in ("id", "kind", "content_hash", "ref_count", "bytes")}
            for row in connection.execute("SELECT * FROM artifacts ORDER BY kind, content_hash")
        ]
    finally:
        connection.close()
    return {
        "row_count": len(rows),
        "spellings": sorted({"bare" if not r["content_hash"].startswith("sha256:") else "labelled"
                             for r in rows}),
        "rows": rows,
    }


def media_entries() -> dict[str, dict]:
    store_a = json.loads((S / "evidence-storeA.json").read_text(encoding="utf-8"))
    return {
        entry["artifact_get"]["result"]["artifact_id"]: entry
        for entry in store_a["media_artifacts"].values()
    }


def fetch_detail(client: Client, artifact_id: str) -> dict:
    detail = client.rpc("artifact.get", {"artifact_id": artifact_id})
    record = {"artifact_id": artifact_id, "artifact_get": detail}
    download = (detail.get("result") or {}).get("download") or {}
    if detail.get("ok") and download.get("url"):
        status, content_type, data = client.fetch(download["url"])
        record["handle"] = {
            "url": download["url"],
            "http": status,
            "content_type": content_type,
            "bytes": len(data),
            "sha256": sha_bytes(data),
        }
    return record


def main() -> int:
    client = Client(BASE, TOKEN)
    client.wire_version()
    evidence: dict = {"store": "storeA", "wire_version": client._wire}
    inputs = json.loads((INPUTS / "inputs.json").read_text(encoding="utf-8"))
    declared = {
        **inputs["japanese-affection-context-l0"]["media"],
        **inputs["technical-demo-pack"]["media"],
    }
    entries = media_entries()

    # 0. Consistent copy of the database before anything is touched.
    if not BACKUP.exists():
        with sqlite3.connect(str(DB)) as source, sqlite3.connect(str(BACKUP)) as target:
            source.backup(target)
    evidence["backup"] = {
        "path": str(BACKUP),
        "sha256": "sha256:" + hashlib.sha256(BACKUP.read_bytes()).hexdigest(),
    }
    evidence["before"] = snapshot()

    # 1. Reproduce the pre-repair storage spelling for the pack media rows.
    evidence["injected"] = []
    with sqlite3.connect(str(DB)) as connection:
        for row in evidence["before"]["rows"]:
            if row["id"] not in entries:
                continue
            bare = row["content_hash"].removeprefix("sha256:")
            connection.execute("UPDATE artifacts SET content_hash = ? WHERE id = ?",
                               (bare, row["id"]))
            evidence["injected"].append({"artifact_id": row["id"], "kind": row["kind"],
                                         "was": row["content_hash"], "now": bare})
    evidence["after_injection"] = snapshot()

    # 2. artifact.get on each legacy bare row: labelled answer + fetchable exact bytes.
    fetches = {}
    for row in evidence["injected"]:
        artifact_id = row["artifact_id"]
        record = fetch_detail(client, artifact_id)
        segment_path = (entries[artifact_id]["segment"] or {}).get("path")
        record["declared_sha256"] = declared.get(str(segment_path)) if segment_path else None
        fetches[artifact_id] = record
    evidence["legacy_read"] = fetches

    # 3. Two more live imports of the same pack into the same store.
    archive_path = INPUTS / "japanese-affection-context-l0-2.1.0.zip"
    imports = []
    for attempt in (1, 2):
        status, granted = client.http(
            "POST", "/api/plugins/coursebook/packs/grant?profile=", {"path": str(archive_path)}
        )
        assert granted.get("ok"), granted
        imported = client.rpc(
            "pack.import", {"staged_id": granted["staged_id"], "mode": "fresh"},
            idempotency_key=f"h210r2-dedupe-{attempt}-{time.time_ns()}",
        )
        imports.append(imported)
    evidence["reimports"] = imports
    evidence["after_reimport"] = snapshot()

    # 4. artifact.get again after the labelled re-imports hit the legacy rows.
    refetches = {artifact_id: fetch_detail(client, artifact_id)
                 for artifact_id in fetches}
    evidence["legacy_read_after_reimport"] = refetches

    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "backup_sha256": evidence["backup"]["sha256"],
        "before": {"row_count": evidence["before"]["row_count"],
                   "spellings": evidence["before"]["spellings"]},
        "injected": evidence["injected"],
        "after_injection": {"row_count": evidence["after_injection"]["row_count"],
                            "spellings": evidence["after_injection"]["spellings"]},
        "legacy_read": {k: {"ok": v["artifact_get"].get("ok"),
                            "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
                            "declared_sha256": v.get("declared_sha256"),
                            "handle_sha256": (v.get("handle") or {}).get("sha256"),
                            "http": (v.get("handle") or {}).get("http")}
                        for k, v in fetches.items()},
        "reimports": [(r.get("result") or r) for r in imports],
        "after_reimport": {"row_count": evidence["after_reimport"]["row_count"],
                           "spellings": evidence["after_reimport"]["spellings"],
                           "rows": evidence["after_reimport"]["rows"]},
        "legacy_read_after_reimport": {
            k: {"ok": v["artifact_get"].get("ok"),
                "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
                "handle_sha256": (v.get("handle") or {}).get("sha256")}
            for k, v in refetches.items()},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
