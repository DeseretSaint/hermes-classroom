#!/usr/bin/env python3
"""Capture a REAL narration artifact for gen_lang_1 through Coursebook's product media path.

The path exercised here is the shipped one, not a provider script:

    host ctx.dispatch_tool  ->  coursebook.media.bind_host_seam(ctx)
      -> coursebook.media.host_media()/HostMedia.speech
        -> coursebook.media.generate_for_lessons
          -> artifacts.ArtifactStore (sniff, cap, content-addressed adopt, DB row)

``dispatch_tool`` is bound to ``tools.registry.dispatch`` — the exact call
``hermes_cli.plugins.HermesPluginContext.dispatch_tool`` makes — after importing
``tools.tts_tool`` so the host's ``text_to_speech`` entry is registered with the host's own
config/auth resolution. Nothing here reads a TTS provider key or calls a vendor API directly.

Run with HERMES_HOME pointing at the prepared store home (set by the caller).

Outputs (all under audit/adversarial/h187-tts/):
  artifact/<name>.mp3   byte-identical copy of the stored artifact
  capture_result.json   fresh size/sha256/magic/ffprobe + served lesson.page
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ce380228")
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")
EVIDENCE = REPO / "audit" / "adversarial" / "h187-tts"
ARTIFACT_DIR = EVIDENCE / "artifact"
LESSON_ID = "gen_lang_1"
COURSE_ID = "crs_c330330a969646cfb0735f9f3644c107"
ENROLLMENT_ID = "enr_22c18bf3305a4b0ca769b8219e0036dd"
OBJECTIVE_ID = "obj_903c89f63e4940d7a8220082e4d68429"
BLOCK_ID = "blk_280128ee1e4e4ded9d13"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERMES_AGENT))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class HostCtx:
    """The host half of the plugin contract: only ``dispatch_tool`` is needed for media."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def dispatch_tool(self, name: str, args: dict, **kwargs):
        from tools.registry import registry

        envelope = registry.dispatch(name, args, **kwargs)
        recorded = None
        try:
            parsed = json.loads(envelope) if isinstance(envelope, str) else envelope
            recorded = {
                "tool": name,
                "args": {k: v for k, v in args.items() if k != "text"},
                "success": bool(parsed.get("success")) if isinstance(parsed, dict) else None,
                "provider": parsed.get("provider") if isinstance(parsed, dict) else None,
                "error": parsed.get("error") if isinstance(parsed, dict) else None,
            }
        except Exception:  # noqa: BLE001 - recording must never change the seam result
            recorded = {"tool": name, "args": sorted(args), "unparseable": True}
        self.calls.append(recorded)
        return envelope


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True,
    )
    data: dict = {"exit": proc.returncode}
    if proc.returncode != 0:
        data["stderr"] = proc.stderr.strip()[:800]
        return data
    payload = json.loads(proc.stdout)
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    data.update(
        {
            "codec_name": stream.get("codec_name"),
            "codec_type": stream.get("codec_type"),
            "sample_rate": stream.get("sample_rate"),
            "channels": stream.get("channels"),
            "duration": fmt.get("duration") or stream.get("duration"),
            "format_name": fmt.get("format_name"),
        }
    )
    return data


def main() -> int:
    from hermes_constants import get_hermes_home

    import tools.tts_tool  # noqa: F401  (registers the host text_to_speech tool)
    import coursebook.domain  # noqa: F401  (registers the cb.rpc handlers, incl. lesson.page)
    from coursebook import api, artifacts, contracts, db, media

    home = Path(get_hermes_home())
    result: dict = {
        "kind": "capture",
        "captured_at": utcnow(),
        "branch": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip(),
        "commit": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "hermes_home": str(home),
        "db_path": str(db.database_path()),
        "host_tool": "text_to_speech (tools.registry dispatch, tts toolset)",
        "attempted": False,
        "succeeded": False,
    }

    ctx = HostCtx()
    media.bind_host_seam(ctx)
    bound = media.host_media()
    result["seam_bound"] = bound is not None
    if bound is None:
        result["error"] = "ctx.dispatch_tool was not callable; host seam unbound"
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "capture_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    db.ensure_schema()
    with db.read() as connection:
        before = connection.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"]
        result["artifacts_before"] = int(before)
        result["attempted"] = True
        summary = media.generate_for_lessons(
            connection,
            lesson_ids=[LESSON_ID],
            job_id="h187-tts-capture",
            host=bound,
        )
    result["summary"] = summary.as_checkpoint()
    result["dispatch_calls"] = ctx.calls

    # ---- read back what the store actually holds for this lesson -------------------
    db.ensure_schema()
    with db.read() as connection:
        lesson = connection.execute(
            "SELECT media_json, state FROM gen_lessons WHERE id = ?", (LESSON_ID,)
        ).fetchone()
    items = json.loads(lesson["media_json"] or "[]") if lesson is not None else []
    item = next((i for i in items if isinstance(i, dict) and i.get("artifact_id")), None)
    with db.read() as connection:
        row = (
            connection.execute(
                "SELECT * FROM artifacts WHERE id = ?", (item["artifact_id"],)
            ).fetchone()
            if item is not None
            else None
        )
    result["lesson_state"] = lesson["state"] if lesson is not None else None
    result["lesson_media"] = items
    result["artifact_row"] = dict(row) if row is not None else None

    if item is None or row is None:
        result["error"] = (
            "no artifact attached; media caller degraded to text (see dispatch_calls/lesson_media)"
        )
    else:
        stored = Path(row["path"])
        stored_exists = stored.is_file()
        result["stored_path"] = str(stored)
        result["stored_exists"] = stored_exists
        if stored_exists:
            data = stored.read_bytes()
            fresh_hash = hashlib.sha256(data).hexdigest()
            result.update(
                {
                    "size_bytes": len(data),
                    "sha256": fresh_hash,
                    "db_content_hash_matches": fresh_hash == str(row["content_hash"]),
                    "declared_mime": row["mime"],
                    "sniffed_mime": artifacts.sniff_mime(data),
                    "first16_hex": data[:16].hex(),
                    "id3_header": data[:3] == b"ID3",
                    "mpeg_frame_sync": len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0,
                }
            )
            ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            copy_path = ARTIFACT_DIR / f"{LESSON_ID}-narration{stored.suffix or '.bin'}"
            shutil.copyfile(stored, copy_path)
            result["evidence_copy"] = str(copy_path)
            result["evidence_copy_size"] = copy_path.stat().st_size
            result["evidence_copy_sha256"] = sha256_file(copy_path)
            result["evidence_copy_identical"] = result["evidence_copy_sha256"] == fresh_hash
            result["ffprobe"] = ffprobe(copy_path)
            result["succeeded"] = (
                fresh_hash == str(row["content_hash"])
                and result["sniffed_mime"] == "audio/mpeg"
                and result["ffprobe"].get("codec_type") == "audio"
            )

    # ---- served page ---------------------------------------------------------------
    served = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "h187-tts-capture-page",
            "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
        }
    )
    page = served.get("result") or {}
    document = page.get("document") or {}
    result["serve_ok"] = bool(served.get("ok"))
    result["serve_error"] = served.get("error")
    result["served_artifacts"] = page.get("artifacts") or []
    result["served_blocks"] = [
        {
            "block_id": block.get("id"),
            "role": block.get("role"),
            "media": [
                {
                    "kind": m.get("kind"),
                    "role": m.get("role"),
                    "artifact_id": m.get("artifact_id"),
                    "mime": m.get("mime"),
                    "degraded": m.get("degraded"),
                    "reason": m.get("reason"),
                }
                for m in (block.get("media") or [])
            ],
        }
        for block in (document.get("blocks") or [])
    ]
    target = next((b for b in result["served_blocks"] if b["block_id"] == BLOCK_ID), None)
    result["target_block"] = target
    result["served_page_references_artifact"] = bool(
        target and target["media"] and target["media"][0].get("artifact_id")
    )
    result["provenance"] = document.get("provenance")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "capture_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
