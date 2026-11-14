#!/usr/bin/env python3
"""H-187 media capture — real ``image_generate`` bytes through the product media seam.

This drives the *product* path exactly as the plugin's agent half does:

    HostMedia(ctx.dispatch_tool)  ->  coursebook.media.generate_for_lessons(...)
        -> artifacts.produce_with_fallback  ->  ArtifactStore.save

``ctx.dispatch_tool`` is reproduced with the host's own registry dispatcher
(``tools.registry.registry.dispatch``), the same call ``PluginContext.dispatch_tool`` makes in
``hermes_cli/plugins.py``. The provider is whatever the host selected (managed FAL gateway or
FAL_KEY); this script never reads a provider key and never calls a raw image API.

It writes ``capture_evidence.json`` and a copy of the artifact bytes beside it under the run
evidence directory. If the provider is unavailable the script records the exact tool error and the
degraded surface the learner sees instead — it never fabricates bytes.

Usage:
    HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
        python3 capture_image_artifact.py --evidence-dir audit/adversarial/h187-media-capture
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

AGENT_ROOT = os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent"))
REPO = os.environ.get(
    "COURSEBOOK_SOURCE",
    str(Path(__file__).resolve().parents[3]),
)
DEFAULT_HERMES_HOME = "/home/deseretsaint/.hermes/h187-course/home"

TARGET = {
    "course_id": "crs_53a1191816354c44acec268a03d6dba0",
    "enrollment_id": "enr_5906d9d5f01a420cba6d2d202db8da53",
    "objective_id": "obj_75056df1acb84e4ea637b30421c5cca9",
    "lesson_id": "gen_tech_2",
    "attach_block_id": "blk_aecba1e56d346fc8e07b",
    "media_index_in_block": 0,
    "expected_mime": "image/png",
}

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    os.environ.setdefault("HERMES_HOME", DEFAULT_HERMES_HOME)
    sys.path.insert(0, AGENT_ROOT)
    sys.path.insert(0, REPO)

    # Importing the tool module registers ``image_generate`` in the host registry (the same
    # registration a Hermes session performs when it loads its toolset).
    import tools.image_generation_tool as image_tool  # noqa: E402
    from tools.registry import registry  # noqa: E402

    from coursebook import api, artifacts, db, domain, media  # noqa: E402,F401
    from coursebook.contracts import WIRE_CONTRACT_VERSION  # noqa: E402

    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Host-selected provider, recorded without reading any secret.
    try:
        model_id, meta = image_tool._resolve_fal_model()
    except Exception as exc:  # noqa: BLE001
        model_id, meta = None, {"_resolve_error": f"{type(exc).__name__}: {exc}"}
    provider = {
        "tool": "image_generate",
        "selection_provider": image_tool._read_configured_image_provider(),
        "selection_model": image_tool._read_configured_image_model(),
        "resolved_model": model_id,
        "endpoint": None,
        "gateway": "managed fal-queue" if not os.environ.get("FAL_KEY") else "direct FAL_KEY",
        "backend_available": None,
    }
    try:
        provider["backend_available"] = bool(image_tool.check_fal_api_key())
    except Exception as exc:  # noqa: BLE001
        provider["backend_available"] = f"{type(exc).__name__}: {exc}"

    dispatch_log: list[dict] = []

    def host_dispatch_tool(name: str, tool_args: dict, **_kwargs):
        """Stand-in for ``ctx.dispatch_tool`` — the host registry dispatch, unchanged."""
        started = datetime.now(timezone.utc)
        try:
            raw = registry.dispatch(name, dict(tool_args))
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised for the seam
            dispatch_log.append({
                "tool": name,
                "args": dict(tool_args),
                "raised": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            raise
        dispatch_log.append({
            "tool": name,
            "args": dict(tool_args),
            "raw_type": type(raw).__name__,
            "payload": json.loads(raw) if isinstance(raw, str) else raw,
            "at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return raw

    host = media.HostMedia(host_dispatch_tool)

    evidence: dict = {
        "task": "t_b0e4b0e8",
        "generated_at": now_iso(),
        "hermes_home": os.environ["HERMES_HOME"],
        "coursebook_source": REPO,
        "target": dict(TARGET),
        "provider": provider,
        "store": {},
        "generation": {},
        "served_page": {},
        "artifact": {},
        "verification": {},
        "dispatch_log": dispatch_log,
    }

    with db.read() as connection:
        before = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    evidence["store"]["db_path"] = str(db.database_path())
    evidence["store"]["artifacts_before"] = int(before)

    # A real endpoint read (payload construction only, no submission) so the evidence names the
    # exact FAL endpoint the host tool would call.
    try:
        endpoint, _arguments = image_tool._prepare_fal_request(
            model_id,
            meta,
            "probe",
            "landscape",
            None,
            {},
            [],
        )
        provider["endpoint"] = endpoint
    except Exception as exc:  # noqa: BLE001
        provider["endpoint_error"] = f"{type(exc).__name__}: {exc}"

    connection = db.connect()
    try:
        summary = media.generate_for_lessons(
            connection,
            lesson_ids=[TARGET["lesson_id"]],
            job_id=None,
            host=host,
        )
    finally:
        connection.close()

    evidence["generation"] = {
        "summary": summary.as_checkpoint(),
        "usage": summary.usage,
    }

    # Read back the stored media item and the served page, and identify the attachment from the
    # block's media child (lesson.page's artifacts[] is course-scoped, not per lesson).
    with db.read() as connection:
        row = connection.execute(
            "SELECT media_json FROM gen_lessons WHERE id = ?", (TARGET["lesson_id"],)
        ).fetchone()
        items = json.loads(row["media_json"] or "[]") if row else []
        lesson_item = items[0] if items else {}
        artifact_row = None
        if lesson_item.get("artifact_id"):
            artifact_row = connection.execute(
                "SELECT * FROM artifacts WHERE id = ?", (lesson_item["artifact_id"],)
            ).fetchone()

    page = api.dispatch({
        "contract": "cb.rpc",
        "contract_version": WIRE_CONTRACT_VERSION,
        "method": "lesson.page",
        "operation_id": f"h187-media-page-{int(datetime.now().timestamp())}",
        "payload": {
            "enrollment_id": TARGET["enrollment_id"],
            "objective_id": TARGET["objective_id"],
        },
    })
    block_media = None
    block_found = False
    if page.get("ok"):
        document = page["result"]["document"]
        for block in document.get("blocks") or []:
            if block.get("id") == TARGET["attach_block_id"]:
                block_found = True
                media_list = block.get("media") or []
                if len(media_list) > TARGET["media_index_in_block"]:
                    block_media = media_list[TARGET["media_index_in_block"]]
                break

    evidence["served_page"] = {
        "rpc_ok": bool(page.get("ok")),
        "rpc_error": page.get("error"),
        "document_state": (page.get("result", {}).get("document") or {}).get("state") if page.get("ok") else None,
        "attach_block_id": TARGET["attach_block_id"],
        "attach_block_found": block_found,
        "media_index_in_block": TARGET["media_index_in_block"],
        "media_child": block_media,
        "page_artifacts_count": len(page.get("result", {}).get("artifacts") or []) if page.get("ok") else None,
        "page_artifacts_note": "lesson.page returns a course-scoped artifacts[]; attachment is identified from the block's media.artifact_id",
    }

    status = "failed"
    degraded_surface = None
    if lesson_item.get("artifact_id") and artifact_row is not None:
        path = Path(str(artifact_row["path"]))
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        real_png = data.startswith(PNG_MAGIC)
        detected = artifacts.sniff_mime(data, "image/png")
        evidence["artifact"] = {
            "artifact_id": str(artifact_row["id"]),
            "store_path": str(path),
            "declared_mime": str(artifact_row["mime"]),
            "kind": str(artifact_row["kind"]),
            "bytes_row": int(artifact_row["bytes"]),
            "bytes_on_disk": len(data),
            "content_hash_row": str(artifact_row["content_hash"]),
            "sha256_on_disk": sha256,
            "magic_check": "PNG signature" if real_png else "no PNG signature",
            "sniffed_mime": detected,
            "provenance": json.loads(artifact_row["provenance_json"] or "{}"),
            "evidence_copy": None,
        }
        evidence["verification"] = {
            "size_matches_row": len(data) == int(artifact_row["bytes"]),
            "hash_matches_row": sha256 == str(artifact_row["content_hash"]),
            "png_magic_ok": real_png,
            "sniffed_mime_matches_declared": detected == "image/png",
            "page_references_artifact": bool(block_media and block_media.get("artifact_id") == str(artifact_row["id"])),
            "page_media_mime": (block_media or {}).get("mime"),
            "page_media_degraded": (block_media or {}).get("degraded"),
            "page_media_artifact_id": (block_media or {}).get("artifact_id"),
        }
        if all([
            evidence["verification"]["size_matches_row"],
            evidence["verification"]["hash_matches_row"],
            evidence["verification"]["png_magic_ok"],
            evidence["verification"]["sniffed_mime_matches_declared"],
            evidence["verification"]["page_references_artifact"],
        ]):
            status = "succeeded"
        # Store a byte-identical copy under the run evidence directory.
        copy_path = evidence_dir / f"{sha256}.png"
        shutil.copyfile(path, copy_path)
        copied = hashlib.sha256(copy_path.read_bytes()).hexdigest()
        evidence["artifact"]["evidence_copy"] = str(copy_path)
        evidence["artifact"]["evidence_copy_sha256"] = copied
        evidence["artifact"]["evidence_copy_matches"] = copied == sha256
        if copied != sha256:
            status = "failed"
    else:
        # Honest degradation: name the exact tool error and the surface the learner sees.
        degraded_surface = {
            "media_child": block_media,
            "served_media_state": (block_media or {}).get("degraded"),
            "served_reason": (block_media or {}).get("reason"),
            "text_equivalent_shown": (block_media or {}).get("text_equivalent"),
            "tool_error": next(
                (entry.get("payload", {}).get("error") for entry in dispatch_log if isinstance(entry.get("payload"), dict)),
                None,
            ),
            "dispatch_raised": next((entry.get("raised") for entry in dispatch_log if entry.get("raised")), None),
        }
        evidence["degraded_surface"] = degraded_surface
        evidence["verification"] = {
            "page_references_artifact": False,
            "degraded_honestly_recorded": True,
        }

    evidence["status"] = status
    out_path = evidence_dir / "capture_evidence.json"
    out_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": status,
        "evidence": str(out_path),
        "artifact": evidence.get("artifact") or None,
        "verification": evidence["verification"],
        "summary": evidence["generation"]["summary"],
        "provider": provider,
        "degraded_surface": degraded_surface,
    }, indent=2, ensure_ascii=False))
    return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
