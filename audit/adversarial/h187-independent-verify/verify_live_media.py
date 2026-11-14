#!/usr/bin/env python3
"""Independent (Sentinel) verification of the H-187 live media artifacts.

This is a *verifier*, not a capture: it never asks a provider for bytes. It reads the
artifact store, re-hashes the bytes on disk, sniffs the type from the bytes, calls the
product's own preview route and the product's ``lesson.page`` read, and asserts that the
served page references exactly the artifact the store holds.

Run against a prepared home (or a byte-identical copy of one):

    HERMES_HOME=/path/to/home python3 verify_live_media.py --home /path/to/home --out result.json

Exit code 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")

EXPECTED = {
    "art_adf2e015a0694641a409bb54e9a6a746": {
        "kind": "audio",
        "mime": "audio/mpeg",
        "bytes": 41088,
        "sha256": "208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c",
        "lesson_id": "gen_lang_1",
        "course_id": "crs_c330330a969646cfb0735f9f3644c107",
        "enrollment_id": "enr_22c18bf3305a4b0ca769b8219e0036dd",
        "objective_id": "obj_903c89f63e4940d7a8220082e4d68429",
        "block_id": "blk_280128ee1e4e4ded9d13",
        "role": "narration",
    },
    "art_d7dc7afd153d4736abc4d2e0560a8376": {
        "kind": "visual",
        "mime": "image/png",
        "bytes": 598928,
        "sha256": "a206b3493098e7616c77575cc5a4b252ee36da43b58df14d03183fbc91573d6c",
        "dimensions": [1024, 576],
        "lesson_id": "gen_tech_2",
        "course_id": "crs_53a1191816354c44acec268a03d6dba0",
        "enrollment_id": "enr_5906d9d5f01a420cba6d2d202db8da53",
        "objective_id": "obj_75056df1acb84e4ea637b30421c5cca9",
        "block_id": "blk_aecba1e56d346fc8e07b",
        "role": "illustration",
    },
}

CHECKS: list[dict] = []


def check(check_id: str, ok: bool, detail: object) -> None:
    CHECKS.append({"id": check_id, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + check_id + " :: " + json.dumps(detail, ensure_ascii=False)[:400])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_dimensions(data: bytes) -> list[int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return list(struct.unpack(">II", data[16:24]))


def ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"exit": proc.returncode, "stderr": proc.stderr.strip()[:600]}
    payload = json.loads(proc.stdout)
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    return {
        "exit": 0,
        "codec_name": stream.get("codec_name"),
        "codec_type": stream.get("codec_type"),
        "sample_rate": stream.get("sample_rate"),
        "channels": stream.get("channels"),
        "duration": fmt.get("duration") or stream.get("duration"),
        "format_name": fmt.get("format_name"),
        "size": fmt.get("size"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    home = Path(args.home).resolve()
    os.environ["HERMES_HOME"] = str(home)

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(HERMES_AGENT))

    import coursebook.domain  # noqa: F401  (registers cb.rpc handlers incl. lesson.page)
    from coursebook import api, artifacts as artifacts_mod, contracts, db, media

    # The DSH: use the product's own DB resolver rather than a guessed path.
    db_path = Path(db.database_path())
    check("db.path_is_under_home", str(db_path).startswith(str(home)), str(db_path))
    check("db.file_present", db_path.is_file(), str(db_path))
    db_hash_before = sha256_bytes(db_path.read_bytes()) if db_path.is_file() else None

    store_root = Path(artifacts_mod.read_root()).resolve()
    check(
        "store.read_root_under_home",
        str(store_root).startswith(str(home)),
        str(store_root),
    )

    with db.read() as connection:
        rows = {
            str(row["id"]): dict(row)
            for row in connection.execute("SELECT * FROM artifacts").fetchall()
        }

    check("store.exactly_the_two_expected_rows", set(rows) == set(EXPECTED), sorted(rows))

    for artifact_id, want in EXPECTED.items():
        prefix = artifact_id
        row = rows.get(artifact_id)
        check(f"{prefix}:row_present", row is not None, artifact_id)
        if row is None:
            continue

        path = Path(str(row["path"]))
        check(f"{prefix}:path_under_store_root",
              str(path.resolve()).startswith(str(store_root)), str(path.resolve())[:200])
        check(f"{prefix}:file_exists", path.is_file(), str(path))
        if not path.is_file():
            continue

        data = path.read_bytes()
        digest = sha256_bytes(data)

        check(f"{prefix}:size_row_matches_disk", len(data) == int(row["bytes"]) == want["bytes"],
              {"disk": len(data), "row": int(row["bytes"]), "expected": want["bytes"]})
        check(f"{prefix}:sha256_row_matches_disk", digest == str(row["content_hash"]) == want["sha256"],
              {"disk": digest, "row": str(row["content_hash"]), "expected": want["sha256"]})
        check(f"{prefix}:content_addressed_path", path.name == digest,
              {"filename": path.name, "sha256": digest})
        check(f"{prefix}:declared_mime", str(row["mime"]) == want["mime"], str(row["mime"]))
        check(f"{prefix}:kind", str(row["kind"]) == want["kind"], str(row["kind"]))
        check(f"{prefix}:course_id", str(row["course_id"]) == want["course_id"], str(row["course_id"]))

        # Magic bytes, not a declaration.
        check(f"{prefix}:png_magic" if want["kind"] == "visual" else f"{prefix}:mpeg_frame_sync",
              (data[:8] == b"\x89PNG\r\n\x1a\n") if want["kind"] == "visual"
              else (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0),
              data[:16].hex())

        sniffed = artifacts_mod.sniff_mime(data, want["mime"])
        check(f"{prefix}:sniffed_mime", sniffed == want["mime"], sniffed)
        artifacts_mod.assert_render_safe(data, sniffed)
        check(f"{prefix}:render_safe", True, sniffed)

        if want["kind"] == "visual":
            dims = png_dimensions(data)
            check(f"{prefix}:png_dimensions", dims == want["dimensions"],
                  {"actual": dims, "expected": want["dimensions"]})
            check(f"{prefix}:png_iend", data[-12:] == b"\x00\x00\x00\x00IEND\xaeB`\x82", data[-12:].hex())
        else:
            probe = ffprobe(path)
            check(f"{prefix}:ffprobe_audio", probe.get("exit") == 0 and probe.get("codec_type") == "audio"
                  and probe.get("codec_name") == "mp3", probe)

        provenance = json.loads(row["provenance_json"] or "{}")
        check(f"{prefix}:provenance_lesson_id", provenance.get("lesson_id") == want["lesson_id"],
              provenance.get("lesson_id"))
        check(f"{prefix}:provenance_not_independent", provenance.get("independent") is False,
              provenance.get("independent"))
        check(f"{prefix}:text_equivalent_present",
              bool(str(provenance.get("text_equivalent") or "").strip()),
              str(provenance.get("text_equivalent"))[:160])
        check(f"{prefix}:honesty_label_present",
              bool(str(provenance.get("label") or "").strip()), str(provenance.get("label"))[:160])

        # ── product preview route (the only door the Desktop has to bytes) ──────────────
        preview = media.preview_artifact(artifact_id)
        check(f"{prefix}:preview_ok", preview.get("ok") is True,
              {k: preview.get(k) for k in ("ok", "code", "message")})
        if preview.get("ok") is True:
            data_url = str(preview.get("data_url") or "")
            head = f"data:{want['mime']};base64,"
            check(f"{prefix}:preview_data_url_prefix", data_url.startswith(head), data_url[:40])
            decoded = base64.b64decode(data_url.split(",", 1)[1]) if "," in data_url else b""
            check(f"{prefix}:preview_bytes_equal_disk", decoded == data,
                  {"decoded": len(decoded), "disk": len(data)})
            check(f"{prefix}:preview_sha256_equal_row",
                  sha256_bytes(decoded) == str(row["content_hash"]) if decoded else False,
                  sha256_bytes(decoded) if decoded else None)
            check(f"{prefix}:preview_mime", preview.get("mime") == want["mime"], preview.get("mime"))
            check(f"{prefix}:preview_has_no_path",
                  "path" not in preview and str(store_root) not in json.dumps(preview),
                  sorted(preview))

        # ── the dashboard HTTP route handler (same function the plugin's /media/ route calls) ──
        from dashboard import plugin_api
        routed = asyncio.run(plugin_api.media_preview(artifact_id))
        check(f"{prefix}:dashboard_route_ok", routed.get("ok") is True,
              {k: routed.get(k) for k in ("ok", "code", "message")})
        check(f"{prefix}:dashboard_route_matches_preview",
              routed.get("data_url") == preview.get("data_url") if routed.get("ok") else False,
              "identical data_url" if routed.get("data_url") == preview.get("data_url") else "differs")

    # ── served lesson.page: the product read, not the row ───────────────────────────────
    for artifact_id, want in EXPECTED.items():
        prefix = artifact_id
        served = api.dispatch(
            {
                "contract": "cb.rpc",
                "contract_version": contracts.WIRE_CONTRACT_VERSION,
                "method": "lesson.page",
                "operation_id": f"sentinel-verify-{want['lesson_id']}",
                "payload": {
                    "enrollment_id": want["enrollment_id"],
                    "objective_id": want["objective_id"],
                },
            }
        )
        check(f"{prefix}:lesson_page_ok", bool(served.get("ok")),
              served.get("error"))
        page = served.get("result") or {}
        document = page.get("document") or {}
        provenance = page.get("provenance") or {}
        check(f"{prefix}:served_provenance_not_independent",
              provenance.get("independent") is False and provenance.get("outcome") == "model_assessed",
              {k: provenance.get(k) for k in ("outcome", "independent")})
        check(f"{prefix}:served_provenance_warning",
              "not independently validated" in str(provenance.get("warning") or ""),
              str(provenance.get("warning")))
        check(f"{prefix}:served_document_state_complete",
              document.get("state") == "complete", document.get("state"))
        served_artifacts = page.get("artifacts") or []
        match = next((a for a in served_artifacts if a.get("artifact_id") == artifact_id), None)
        check(f"{prefix}:served_artifacts_lists_it", match is not None,
              [a.get("artifact_id") for a in served_artifacts])
        if match is not None:
            check(f"{prefix}:served_artifact_bytes",
                  int(match.get("bytes") or 0) == want["bytes"], match.get("bytes"))
            check(f"{prefix}:served_artifact_hash",
                  str(match.get("content_hash")) == f"sha256:{want['sha256']}", match.get("content_hash"))
            check(f"{prefix}:served_artifact_mime", match.get("mime") == want["mime"], match.get("mime"))

        blocks = document.get("blocks") or []
        target = next((b for b in blocks if b.get("id") == want["block_id"]), None)
        check(f"{prefix}:served_target_block_present", target is not None,
              [b.get("id") for b in blocks])
        if target is not None:
            media_children = target.get("media") or []
            child = next((m for m in media_children if m.get("artifact_id") == artifact_id), None)
            check(f"{prefix}:block_media_references_artifact", child is not None,
                  [m.get("artifact_id") for m in media_children])
            if child is not None:
                check(f"{prefix}:block_media_not_degraded", child.get("degraded") is False,
                      child.get("degraded"))
                check(f"{prefix}:block_media_kind", child.get("kind") == want["kind"],
                      child.get("kind"))
                check(f"{prefix}:block_media_role", child.get("role") == want["role"],
                      child.get("role"))
                check(f"{prefix}:block_media_text_equivalent",
                      bool(str(child.get("text_equivalent") or "").strip()),
                      str(child.get("text_equivalent"))[:160])
                check(f"{prefix}:block_media_no_degraded_reason",
                      not child.get("reason"), child.get("reason"))

        # The authored page_json is immutable input; the served media_json overlay is the
        # observed state. Record both so a stale "not generated yet" in page_json cannot be
        # mistaken for what the learner is served.
        with db.read() as connection:
            lesson = connection.execute(
                "SELECT page_json, media_json, state FROM gen_lessons WHERE id = ?", (want["lesson_id"],)
            ).fetchone()
        authored = json.loads(lesson["page_json"] or "{}").get("media") or []
        overlay = json.loads(lesson["media_json"] or "[]")
        CHECKS.append({
            "id": f"{prefix}:authored_vs_served_media",
            "ok": True,
            "detail": {
                "page_json_media_degraded": [m.get("degraded") for m in authored],
                "media_json_degraded": [m.get("degraded") for m in overlay],
                "media_json_artifact_ids": [m.get("artifact_id") for m in overlay],
                "note": "page_json holds the authored spec (degraded placeholder); media_json is the generated overlay the serve path uses",
            },
        })

    failures = [c for c in CHECKS if not c["ok"]]
    db_hash_after = sha256_bytes(db_path.read_bytes()) if db_path.is_file() else None
    check("db.unchanged_by_verification", db_hash_before == db_hash_after,
          {"before": db_hash_before, "after": db_hash_after})
    failures = [c for c in CHECKS if not c["ok"]]
    result = {
        "kind": "independent_verification",
        "verifier": "sentinel",
        "home": str(home),
        "db_path": str(db_path),
        "db_sha256": db_hash_after,
        "checks_total": len(CHECKS),
        "checks_passed": len(CHECKS) - len(failures),
        "failures": [c["id"] for c in failures],
        "status": "PASS" if not failures else "FAIL",
        "checks": CHECKS,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "checks_total", "checks_passed", "failures")},
                     indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
