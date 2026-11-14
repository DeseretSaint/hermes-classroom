#!/usr/bin/env python3
"""Independent verification for the H-187 image capture.

Re-reads the store and the served page from scratch (separate process from the generator) and
writes ``verification.json`` beside ``capture_evidence.json``. It also exercises the host preview
route ``media.preview_artifact``, which is the surface the Desktop renderer actually uses.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = "/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_b0e4b0e8"
HERMES_HOME = "/home/deseretsaint/.hermes/h187-course/home"
DB = Path(HERMES_HOME) / "plugin-data" / "coursebook" / "data.db"
ARTIFACT_ID = "art_d7dc7afd153d4736abc4d2e0560a8376"
LESSON_ID = "gen_tech_2"
BLOCK_ID = "blk_aecba1e56d346fc8e07b"
ENROLLMENT_ID = "enr_5906d9d5f01a420cba6d2d202db8da53"
OBJECTIVE_ID = "obj_75056df1acb84e4ea637b30421c5cca9"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

os.environ["HERMES_HOME"] = HERMES_HOME
sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, REPO)

from coursebook import api, artifacts, db, domain, media  # noqa: E402,F401
from coursebook.contracts import WIRE_CONTRACT_VERSION  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    evidence_dir = Path(__file__).resolve().parent
    report: dict = {
        "task": "t_b0e4b0e8",
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": str(DB),
        "db_sha256": sha(DB),
    }

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        report["artifacts_total"] = int(con.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
        row = con.execute("SELECT * FROM artifacts WHERE id = ?", (ARTIFACT_ID,)).fetchone()
        lesson = con.execute("SELECT media_json FROM gen_lessons WHERE id = ?", (LESSON_ID,)).fetchone()
    finally:
        con.close()

    if row is None:
        report["status"] = "failed"
        report["error"] = "artifact row missing"
        (evidence_dir / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    path = Path(row["path"])
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    report["artifact"] = {
        "artifact_id": str(row["id"]),
        "course_id": str(row["course_id"]),
        "kind": str(row["kind"]),
        "mime": str(row["mime"]),
        "path": str(path),
        "bytes_row": int(row["bytes"]),
        "bytes_on_disk": len(data),
        "content_hash_row": str(row["content_hash"]),
        "sha256_on_disk": digest,
        "png_magic": data.startswith(PNG_MAGIC),
        "sniffed_mime": artifacts.sniff_mime(data, str(row["mime"])),
        "inside_artifact_store": db.within(path, artifacts.read_root()),
    }
    lesson_item = json.loads(lesson["media_json"] or "[]")[0]
    report["lesson_media_item"] = lesson_item

    page = api.dispatch({
        "contract": "cb.rpc",
        "contract_version": WIRE_CONTRACT_VERSION,
        "method": "lesson.page",
        "operation_id": f"h187-media-verify-{int(datetime.now().timestamp())}",
        "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
    })
    block_media = None
    if page.get("ok"):
        for block in page["result"]["document"].get("blocks") or []:
            if block.get("id") == BLOCK_ID:
                block_media = (block.get("media") or [None])[0]
                break
    preview = media.preview_artifact(ARTIFACT_ID)
    report["served_page"] = {
        "rpc_ok": bool(page.get("ok")),
        "rpc_error": page.get("error"),
        "document_state": (page.get("result", {}).get("document") or {}).get("state") if page.get("ok") else None,
        "block_media": block_media,
        "page_artifacts_count": len(page.get("result", {}).get("artifacts") or []) if page.get("ok") else None,
        "page_artifact_ids": [a.get("artifact_id") for a in (page.get("result", {}).get("artifacts") or [])] if page.get("ok") else None,
    }
    report["preview_route"] = {
        "ok": bool(preview.get("ok")),
        "error": preview.get("error"),
        "mime": preview.get("mime"),
        "bytes": preview.get("bytes"),
        "label": preview.get("label"),
        "lesson_state": preview.get("lesson_state"),
        "independent": preview.get("independent"),
        "data_url_prefix": (preview.get("data_url") or "")[:30] or None,
        "data_url_bytes": len(preview.get("data_url") or ""),
    }

    checks = {
        "artifact_row_exists": True,
        "size_matches_row": len(data) == int(row["bytes"]),
        "hash_matches_row": digest == str(row["content_hash"]),
        "png_magic_ok": data.startswith(PNG_MAGIC),
        "sniffed_mime_is_png": report["artifact"]["sniffed_mime"] == "image/png",
        "stored_inside_profile_artifact_store": report["artifact"]["inside_artifact_store"],
        "lesson_media_has_artifact_id": lesson_item.get("artifact_id") == ARTIFACT_ID,
        "lesson_media_not_degraded": lesson_item.get("degraded") is False,
        "served_block_references_artifact": bool(block_media and block_media.get("artifact_id") == ARTIFACT_ID),
        "served_block_not_degraded": bool(block_media) and block_media.get("degraded") is False,
        "preview_route_serves_png": report["preview_route"]["ok"] and report["preview_route"]["mime"] == "image/png",
        "evidence_copy_matches": (evidence_dir / f"{digest}.png").is_file()
        and sha(evidence_dir / f"{digest}.png") == digest,
    }
    report["checks"] = checks
    report["status"] = "succeeded" if all(checks.values()) else "failed"
    (evidence_dir / "verification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "checks": checks, "artifact": report["artifact"],
                      "preview": report["preview_route"]}, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
