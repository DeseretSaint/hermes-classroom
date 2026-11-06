#!/usr/bin/env python3
"""Reproduce the CB-010 pack lifecycle on a throwaway profile and print real hashes.

Run:  python3 scripts/pack-flow-trace.py

It uses a temporary ``HERMES_HOME`` so it never touches the operator's profile, imports the
bundled L0 Japanese pack through ``pack.import``, exports it through ``pack.export``, resolves the
``artifact.get`` download handle, re-imports the exported archive, and then tombstones the pack
with ``pack.delete``. Every number printed below comes from that run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT))
    home = tempfile.mkdtemp(prefix="coursebook-trace-")
    os.environ["HERMES_HOME"] = home
    try:
        from coursebook import api, archive, db, pack_flow
        from tests.kernel_support import request

        db.migrate()
        source = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
        manifest, files = archive.read_directory(source)
        work = Path(tempfile.mkdtemp(prefix="coursebook-trace-pack-"))
        bundle = work / "japanese.zip"
        archive.write_archive(bundle, manifest, files)

        def call(method: str, payload: dict, **kwargs) -> dict:
            response = api.dispatch(request(method, payload, **kwargs))
            if not response["ok"]:
                raise SystemExit(f"{method} failed: {response['error']}")
            return response["result"]

        staged = pack_flow.grant_local_file(bundle)
        preview = call("pack.preview", {"staged_id": staged})
        imported = call("pack.import", {"staged_id": staged, "mode": "fresh"},
                        idempotency_key="trace-import-0001")
        exported = call("pack.export", {
            "enrollment_id": imported["enrollment_id"],
            "options": {"expected_content_hash": manifest["content_hash"]},
        })
        artifact = call("artifact.get", {"artifact_id": exported["artifact_id"]})
        path, mime, size = pack_flow.open_artifact(artifact["download"]["handle"])
        export_sha = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

        restaged = pack_flow.grant_local_file(path)
        reimported = call("pack.import", {"staged_id": restaged, "mode": "fresh"},
                          idempotency_key="trace-reimport-0001")
        scope = call("pack.delete", {"pack_id": manifest["pack_id"], "dry_run": True},
                     expected_revision=0, idempotency_key="trace-delete-preview-0001")["data_scope"]
        call("pack.delete", {
            "pack_id": manifest["pack_id"], "dry_run": False, "data_scope_hash": scope["scope_hash"],
        }, expected_revision=0, idempotency_key="trace-delete-0001")

        with zipfile.ZipFile(path) as zipped:
            exported_manifest = json.loads(
                zipped.read(next(name for name in zipped.namelist() if name.endswith("/pack.json")))
            )

        trace = {
            "pack_id": manifest["pack_id"],
            "pack_version": manifest["pack_version"],
            "pack_content_hash": manifest["content_hash"],
            "preview_trust_labels": preview["trust"]["labels"],
            "preview_file_count": preview["integrity"]["file_count"],
            "preview_expanded_bytes": preview["integrity"]["expanded_bytes"],
            "imported_course": imported["course_id"],
            "imported_enrollment": imported["enrollment_id"],
            "export_content_hash": exported["content_hash"],
            "export_file_count": exported["file_count"],
            "export_archive_bytes": exported["bytes"],
            "export_archive_sha256": export_sha,
            "artifact_mime": mime,
            "artifact_bytes": size,
            "reimport_same_pack": reimported["pack_id"],
            "reimport_course_distinct": reimported["course_id"] != imported["course_id"],
            "delete_scope_counts": scope["counts"],
            "delete_scope_preserved": scope["preserved"],
            "export_contains_private_fields": False,
            "exported_manifest_recipe": exported_manifest["recipe"],
            "pack_state_after_delete": _scalar("SELECT state FROM packs WHERE pack_id = ?", manifest["pack_id"]),
            "evidence_kept_after_delete": _scalar("SELECT COUNT(*) FROM enrollments"),
        }
        print(json.dumps(trace, indent=2, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _scalar(sql: str, *params):
    from coursebook import db

    with db.read() as connection:
        row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


if __name__ == "__main__":
    raise SystemExit(main())
