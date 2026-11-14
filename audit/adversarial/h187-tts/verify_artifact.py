#!/usr/bin/env python3
"""Independent re-read of the captured artifact and the served page.

Nothing here generates media. It re-opens the prepared store, resolves the artifact the lesson
page references, and re-computes size/sha256/magic with fresh bytes; the stored row's
``content_hash`` is only compared against that fresh digest. Also dumps the full ``lesson.page``
result so the evidence can quote it verbatim.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ce380228")
EVIDENCE = REPO / "audit" / "adversarial" / "h187-tts"
ARTIFACT_DIR = EVIDENCE / "artifact"
LESSON_ID = "gen_lang_1"
ENROLLMENT_ID = "enr_22c18bf3305a4b0ca769b8219e0036dd"
OBJECTIVE_ID = "obj_903c89f63e4940d7a8220082e4d68429"
BLOCK_ID = "blk_280128ee1e4e4ded9d13"

sys.path.insert(0, str(REPO))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    import coursebook.domain  # noqa: F401  (registers lesson.page)
    from coursebook import api, artifacts, contracts, db

    out: dict = {
        "kind": "verification",
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "hermes_home": str(db.store_root().parent),
        "db_path": str(db.database_path()),
        "db_sha256": sha256_file(db.database_path()),
    }
    with db.read() as connection:
        lesson = connection.execute(
            "SELECT media_json, state FROM gen_lessons WHERE id = ?", (LESSON_ID,)
        ).fetchone()
        lesson_count = connection.execute("SELECT COUNT(*) AS n FROM gen_lessons").fetchone()["n"]
        artifact_rows = [dict(r) for r in connection.execute("SELECT * FROM artifacts").fetchall()]
    items = json.loads(lesson["media_json"])
    item = items[0]
    out["lesson_state"] = lesson["state"]
    out["lesson_count"] = int(lesson_count)
    out["artifact_row_count"] = len(artifact_rows)
    out["media_items"] = items

    artifact_id = item.get("artifact_id")
    row = next((r for r in artifact_rows if r["id"] == artifact_id), None)
    out["artifact_id"] = artifact_id
    out["db_row"] = row
    if row is None:
        out["ok"] = False
        out["error"] = "lesson media names no artifact row"
    else:
        stored = Path(row["path"])
        data = stored.read_bytes() if stored.is_file() else b""
        fresh = hashlib.sha256(data).hexdigest() if data else None
        out.update(
            {
                "stored_path": str(stored),
                "stored_exists": stored.is_file(),
                "size_bytes": len(data),
                "sha256": fresh,
                "db_bytes": row["bytes"],
                "db_content_hash": row["content_hash"],
                "hash_matches_db": fresh == str(row["content_hash"]).removeprefix("sha256:"),
                "size_matches_db": len(data) == int(row["bytes"]),
                "declared_mime": row["mime"],
                "sniffed_mime": artifacts.sniff_mime(data) if data else None,
                "first16_hex": data[:16].hex() if data else None,
                "id3_header": data[:3] == b"ID3",
                "mpeg_frame_sync": bool(data) and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0,
                "provenance": json.loads(row["provenance_json"]),
            }
        )
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        copy_path = ARTIFACT_DIR / "gen_lang_1-narration.mp3"
        if data:
            shutil.copyfile(stored, copy_path)
        out["evidence_copy"] = str(copy_path)
        out["evidence_copy_size"] = copy_path.stat().st_size if copy_path.is_file() else None
        out["evidence_copy_sha256"] = sha256_file(copy_path) if copy_path.is_file() else None
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(copy_path)],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            payload = json.loads(probe.stdout)
            stream = (payload.get("streams") or [{}])[0]
            fmt = payload.get("format") or {}
            out["ffprobe"] = {
                "exit": 0,
                "codec_name": stream.get("codec_name"),
                "codec_type": stream.get("codec_type"),
                "sample_rate": stream.get("sample_rate"),
                "channels": stream.get("channels"),
                "duration_s": fmt.get("duration"),
                "format_name": fmt.get("format_name"),
                "bit_rate": fmt.get("bit_rate"),
            }
        else:
            out["ffprobe"] = {"exit": probe.returncode, "stderr": probe.stderr.strip()[:500]}
        out["ok"] = bool(
            out["stored_exists"]
            and out["hash_matches_db"]
            and out["size_matches_db"]
            and out["sniffed_mime"] == "audio/mpeg"
            and out["mpeg_frame_sync"]
            and (out.get("ffprobe") or {}).get("codec_type") == "audio"
            and out["evidence_copy_sha256"] == fresh
        )

    served = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "h187-tts-verify-page",
            "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
        }
    )
    (EVIDENCE / "served_lesson_page.json").write_text(
        json.dumps(served, indent=2, ensure_ascii=False) + "\n"
    )
    page = served.get("result") or {}
    document = page.get("document") or {}
    block = next((b for b in document.get("blocks") or [] if b.get("id") == BLOCK_ID), None)
    out["serve"] = {
        "ok": bool(served.get("ok")),
        "error": served.get("error"),
        "response_keys": sorted(page.keys()),
        "provenance": page.get("provenance") or document.get("provenance"),
        "artifacts": page.get("artifacts"),
        "target_block": block,
        "page_references_artifact": bool(
            block
            and (block.get("media") or [{}])[0].get("artifact_id") == artifact_id
        ),
        "block_media_mime": ((block or {}).get("media") or [{}])[0].get("mime"),
    }
    out["ok"] = bool(out.get("ok")) and out["serve"]["ok"] and out["serve"]["page_references_artifact"]
    (EVIDENCE / "verification.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
