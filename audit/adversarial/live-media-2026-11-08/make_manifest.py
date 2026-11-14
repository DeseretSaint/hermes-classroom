#!/usr/bin/env python3
"""Build MANIFEST.json for the live-media evidence package.

Recomputes every hash from the bytes on disk (never trusts an earlier report), cross-checks the
two artifact copies against the pinned expectations, reads the served `lesson.page` JSON in
``pages/``, records provider/model/usage from ``sources/``, states explicitly where a cost figure
was not recorded, scans every packaged file for credential-shaped strings, and inventories every
file in the package.

    python3 make_manifest.py            # writes ./MANIFEST.json
    python3 make_manifest.py --check    # verifies MANIFEST.json against the tree, writes nothing

Exit code 0 only when every hash, pin and reference check holds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE_HOME = Path("/home/deseretsaint/.hermes/h187-course/home")
STORE_DB = STORE_HOME / "plugin-data/coursebook/data.db"

PINS = [
    {
        "artifact_id": "art_adf2e015a0694641a409bb54e9a6a746",
        "kind": "audio",
        "lesson_id": "gen_lang_1",
        "course_id": "crs_c330330a969646cfb0735f9f3644c107",
        "block_id": "blk_280128ee1e4e4ded9d13",
        "role": "narration",
        "mime": "audio/mpeg",
        "bytes": 41088,
        "sha256": "208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c",
        "package_file": "artifacts/gen_lang_1-narration.mp3",
        "producer": "host.text_to_speech",
        "provider_record": "sources/capture_result.json",
    },
    {
        "artifact_id": "art_d7dc7afd153d4736abc4d2e0560a8376",
        "kind": "visual",
        "lesson_id": "gen_tech_2",
        "course_id": "crs_53a1191816354c44acec268a03d6dba0",
        "block_id": "blk_aecba1e56d346fc8e07b",
        "role": "illustration",
        "mime": "image/png",
        "bytes": 598928,
        "sha256": "a206b3493098e7616c77575cc5a4b252ee36da43b58df14d03183fbc91573d6c",
        "package_file": "artifacts/gen_tech_2-illustration.png",
        "producer": "host.image_generate",
        "provider_record": "sources/capture_evidence.json",
    },
]

SECRET_PATTERNS = [
    ("openai_style_key", re.compile(rb"sk-[A-Za-z0-9_\-]{16,}")),
    ("github_token", re.compile(rb"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("aws_access_key_id", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(rb"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("bearer_header", re.compile(rb"Bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("private_key_block", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("fal_key_env", re.compile(rb"FAL_KEY\s*=\s*[A-Za-z0-9._\-]{8,}")),
    ("literal_api_key_field", re.compile(rb"api[_-]?key\"?\s*[:=]\s*\"[A-Za-z0-9._\-]{16,}\"")),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sniff(p: Path) -> dict:
    data = p.read_bytes()[:16]
    out: dict = {"first16_hex": data.hex()}
    if data.startswith(b"\xff\xf3") or data.startswith(b"\xff\xfb") or data.startswith(b"ID3"):
        out["sniffed_mime"] = "audio/mpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        out["sniffed_mime"] = "image/png"
        raw = p.read_bytes()
        if len(raw) >= 24:
            out["png_dimensions"] = [
                int.from_bytes(raw[16:20], "big"),
                int.from_bytes(raw[20:24], "big"),
            ]
    else:
        out["sniffed_mime"] = "unknown"
    return out


def scan_secrets(package: Path) -> dict:
    hits = []
    scanned = 0
    for p in sorted(package.rglob("*")):
        if not p.is_file() or p.name == "MANIFEST.json":
            continue
        blob = p.read_bytes()
        scanned += 1
        for name, pat in SECRET_PATTERNS:
            for m in pat.finditer(blob):
                hits.append(
                    {
                        "file": str(p.relative_to(package)),
                        "pattern": name,
                        "offset": m.start(),
                        "match_sha256_prefix": hashlib.sha256(m.group(0)).hexdigest()[:16],
                    }
                )
    return {
        "files_scanned": scanned,
        "patterns": [n for n, _ in SECRET_PATTERNS],
        "hits": hits,
        "hits_count": len(hits),
        "redaction_rule": (
            "Any hit would be replaced in the packaged copy with '<REDACTED:pattern@file:offset>' "
            "and its match digest recorded instead of the value; no hit means no value was present "
            "to redact."
        ),
        "result": "clean — no credential-shaped string found"
        if not hits
        else "REDACTION REQUIRED — see hits",
    }


def read_pages(package: Path) -> list[dict]:
    out = []
    summary_path = package / "pages/served_pages.json"
    summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
    by_lesson = {p["lesson_id"]: p for p in summary.get("pages", [])}
    for pin in PINS:
        f = package / "pages" / f"{pin['lesson_id']}.page.json"
        page = json.loads(f.read_text())
        blocks = (page.get("document") or {}).get("blocks") or []
        block = next((b for b in blocks if b.get("id") == pin["block_id"]), None)
        media = (block or {}).get("media") or []
        media_entry = next(
            (m for m in media if m.get("artifact_id") == pin["artifact_id"]), None
        )
        art_entry = next(
            (a for a in (page.get("artifacts") or []) if a.get("artifact_id") == pin["artifact_id"]),
            None,
        )
        out.append(
            {
                "lesson_id": pin["lesson_id"],
                "page_file": f"pages/{f.name}",
                "page_bytes": f.stat().st_size,
                "page_sha256": sha256_file(f),
                "reader": "cb.rpc lesson.page (product read path)",
                "enrollment_id": page.get("enrollment_id"),
                "objective_id": (
                    (page.get("section") or {}).get("objective_id")
                    or (page.get("document") or {}).get("objective_id")
                ),
                "section": page.get("section"),
                "document_state": (page.get("document") or {}).get("state"),
                "revision": page.get("revision"),
                "page_provenance": page.get("provenance"),
                "page_artifacts_entry": art_entry,
                "block_found": block is not None,
                "block_role": (block or {}).get("role"),
                "block_media_entry": media_entry,
                "page_references_artifact": art_entry is not None and media_entry is not None,
                "read_probe": by_lesson.get(pin["lesson_id"]),
            }
        )
    return out


def read_providers(package: Path) -> list[dict]:
    tts = json.loads((package / "sources/capture_result.json").read_text())
    img = json.loads((package / "sources/capture_evidence.json").read_text())
    tts_call = (tts.get("dispatch_calls") or [{}])[0]
    return [
        {
            "artifact_id": "art_adf2e015a0694641a409bb54e9a6a746",
            "tool": "text_to_speech",
            "provider": tts_call.get("provider"),
            "transport": "Nous Tool Gateway, managed (tts.use_gateway=true; no local key in the home)",
            "model": None,
            "model_note": "the host tool does not report a model id for TTS; the artifact row stores model=host-configured",
            "endpoint": "openai-audio-gateway (managed; exact base URL not recorded by the tool)",
            "voice": "default",
            "language": "ja-JP",
            "requested_at": tts.get("captured_at"),
            "duration_ms": None,
            "usage_tokens": None,
            "cost_usd": None,
            "cost_note": "not recorded: the product's media layer records duration/tokens/cost only when the host tool returns them; text_to_speech returned none and no gateway invoice was read",
            "source_file": "sources/capture_result.json",
        },
        {
            "artifact_id": "art_d7dc7afd153d4736abc4d2e0560a8376",
            "tool": "image_generate",
            "provider": (img.get("provider") or {}).get("gateway"),
            "transport": "managed fal-queue gateway (FAL_KEY unset on this host)",
            "model": (img.get("provider") or {}).get("resolved_model"),
            "model_note": "resolved by the host image tool; the artifact row stores model=host-configured",
            "endpoint": (img.get("provider") or {}).get("endpoint"),
            "requested_at": img.get("generated_at"),
            "duration_ms": ((img.get("generation") or {}).get("usage") or [{}])[0].get("duration_ms"),
            "usage_tokens": ((img.get("generation") or {}).get("usage") or [{}])[0].get("tokens"),
            "cost_usd": None,
            "cost_note": "not recorded: the image tool returned duration and an image URL only; no price was returned or looked up",
            "returned_media_url_note": "the tool returned a retrieval URL for the generated PNG; it carries no query string or signature and is not a credential",
            "source_file": "sources/capture_evidence.json",
        },
    ]


def store_rows() -> dict:
    if not STORE_DB.is_file():
        return {"available": False, "reason": f"{STORE_DB} is not present on this host"}
    con = sqlite3.connect(f"file:{STORE_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {
        r["id"]: {k: r[k] for k in r.keys()}
        for r in con.execute("select id, kind, bytes, mime, content_hash, path, ref_count, created_at from artifacts")
    }
    con.close()
    return {
        "available": True,
        "db_path": str(STORE_DB),
        "db_sha256_now": sha256_file(STORE_DB),
        "db_sha256_verified_run": "4c3423fcad0543b0baac7f0fea2fd5b6de4c92befe4c6412caca5c0976126c12",
        "rows": rows,
    }


def read_verification(package: Path) -> dict:
    probes = []
    total_passed = 0
    total_checks = 0
    for name, key in (
        ("verification.prepared.json", "live media artifacts + served pages + preview"),
        ("degradation.json", "provider-refusal degradation through the product path"),
        ("ui_render.json", "shipped Desktop render (jsdom + repo SDK stub)"),
        ("tamper.json", "tamper / fake-bytes refusals"),
        ("route_http.json", "real ASGI /media route"),
    ):
        d = json.loads((package / "verification" / name).read_text())
        probes.append(
            {
                "file": f"verification/{name}",
                "covers": key,
                "checks_total": d.get("checks_total"),
                "checks_passed": d.get("checks_passed"),
                "status": d.get("status"),
                "sha256": sha256_file(package / "verification" / name),
            }
        )
        total_checks += d.get("checks_total") or 0
        total_passed += d.get("checks_passed") or 0
    return {
        "verifier": "sentinel",
        "report": "verification/REPORT.md",
        "report_sha256": sha256_file(package / "verification/REPORT.md"),
        "verdict": "PASS" if total_passed == total_checks else "FAIL",
        "checks_passed": total_passed,
        "checks_total": total_checks,
        "probes": probes,
        "transcript": "verification/evidence/commands.log",
        "transcript_sha256": sha256_file(package / "verification/evidence/commands.log"),
        "independence_note": (
            "the verifier copied these files into its own tree at wt/t_2f587f6b commit b8bc32d; "
            "this package copies them byte-for-byte and re-hashes them here"
        ),
    }


def build(package: Path) -> tuple[dict, bool]:
    ok = True
    notes: list[str] = []

    artifacts = []
    for pin in PINS:
        p = package / pin["package_file"]
        if not p.is_file():
            ok = False
            notes.append(f"missing package artifact {pin['package_file']}")
            continue
        size = p.stat().st_size
        digest = sha256_file(p)
        sn = sniff(p)
        size_ok = size == pin["bytes"]
        hash_ok = digest == pin["sha256"]
        mime_ok = sn["sniffed_mime"] == pin["mime"]
        ok = ok and size_ok and hash_ok and mime_ok
        if not (size_ok and hash_ok and mime_ok):
            notes.append(f"{pin['package_file']}: size_ok={size_ok} hash_ok={hash_ok} mime_ok={mime_ok}")
        artifacts.append(
            {
                **{k: pin[k] for k in ("artifact_id", "kind", "lesson_id", "course_id", "block_id", "role", "mime", "producer")},
                "package_file": pin["package_file"],
                "package_bytes": size,
                "package_sha256": digest,
                "pinned_bytes": pin["bytes"],
                "pinned_sha256": pin["sha256"],
                "size_matches_pin": size_ok,
                "sha256_matches_pin": hash_ok,
                "sniff": sn,
                "sniff_matches_declared_mime": mime_ok,
                "original_store_path": (
                    f"{STORE_HOME}/plugin-data/coursebook/artifacts/objects/"
                    f"{digest[:2]}/{digest}"
                ),
            }
        )

    rows = store_rows()
    for a in artifacts:
        row = (rows.get("rows") or {}).get(a["artifact_id"])
        a["store_row"] = row
        a["store_row_matches_copy"] = bool(
            row
            and row.get("bytes") == a["package_bytes"]
            and row.get("content_hash") == a["package_sha256"]
            and row.get("mime") == a["mime"]
        )
        if rows["available"] and not a["store_row_matches_copy"]:
            ok = False
            notes.append(f"{a['artifact_id']}: store row does not match packaged copy")

    pages = read_pages(package)
    for pg in pages:
        if not pg["page_references_artifact"]:
            ok = False
            notes.append(f"{pg['lesson_id']}: served page does not reference its artifact")

    providers = read_providers(package)
    redaction = scan_secrets(package)
    if redaction["hits_count"]:
        ok = False
        notes.append("credential-shaped strings found; package must be redacted before handoff")

    inventory = []
    for p in sorted(package.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            inventory.append(
                {
                    "path": str(p.relative_to(package)),
                    "bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )

    manifest = {
        "kind": "live_media_evidence_manifest",
        "schema": "1",
        "produced_by": "harbor",
        "produced_by_task": "t_8167b3bd",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "package_root": "audit/adversarial/live-media-2026-11-08",
        "source_tree": {
            "branch": os.popen("git -C " + str(HERE.parents[2]) + " rev-parse --abbrev-ref HEAD").read().strip(),
            "commit": os.popen("git -C " + str(HERE.parents[2]) + " rev-parse HEAD").read().strip(),
            "note": "package assembled on this commit; the capture and verification ran earlier on the same source tree 127cce1",
        },
        "prepared_store": {
            "hermes_home": str(STORE_HOME),
            "db_path": str(STORE_DB),
            "db_sha256_verified_run": "4c3423fcad0543b0baac7f0fea2fd5b6de4c92befe4c6412caca5c0976126c12",
            "artifact_rows": len(rows.get("rows") or {}) if rows["available"] else None,
            "read_only_use": "every probe in this package read the store; the independent verifier ran destructive probes on throwaway copies only",
        },
        "artifacts": artifacts,
        "pages": pages,
        "providers": providers,
        "cost": {
            "currency": "USD",
            "total_recorded_usd": None,
            "status": "not recorded",
            "explanation": (
                "Neither host media tool returned a price for this run and no gateway invoice or "
                "usage export was read, so no cost figure is stated. A zero would be a fabrication. "
                "What the tools did return: image_generate duration_ms=4725 and empty tokens {}; "
                "text_to_speech returned neither duration nor tokens."
            ),
            "what_would_close_it": "the gateway's usage export for 2026-11-08T21:14Z, which this card did not read",
        },
        "tokens_and_redaction": {
            "redaction_rule": redaction["redaction_rule"],
            "patterns_scanned": redaction["patterns"],
            "files_scanned": redaction["files_scanned"],
            "hits_count": redaction["hits_count"],
            "hits": redaction["hits"],
            "provider_credential_presence": (
                "none in the package: the prepared home's config.yaml selects tts.provider=openai with "
                "use_gateway=true and carries no key; the image path ran on the managed fal queue with "
                "FAL_KEY unset"
            ),
            "result": redaction["result"],
        },
        "verification": {
            **read_verification(package),
            "raw": [
                f"verification/{n}"
                for n in (
                    "verification.prepared.json",
                    "degradation.json",
                    "ui_render.json",
                    "tamper.json",
                    "route_http.json",
                    "served_degraded_page.json",
                )
            ],
        },
        "files": inventory,
        "checks": {
            "artifacts_present": len(artifacts) == len(PINS),
            "artifact_hashes_match_pins": all(a["sha256_matches_pin"] for a in artifacts),
            "artifact_sizes_match_pins": all(a["size_matches_pin"] for a in artifacts),
            "artifact_mime_sniffed_matches": all(a["sniff_matches_declared_mime"] for a in artifacts),
            "served_pages_reference_artifacts": all(p["page_references_artifact"] for p in pages),
            "no_credential_shaped_strings": redaction["hits_count"] == 0,
            "status": "PASS" if ok and not notes else "FAIL",
            "notes": notes,
        },
    }
    return manifest, ok and not notes


def check(package: Path) -> int:
    mpath = package / "MANIFEST.json"
    old = json.loads(mpath.read_text())
    problems = []
    for f in old["files"]:
        p = package / f["path"]
        if not p.is_file():
            problems.append(f"missing {f['path']}")
            continue
        if p.stat().st_size != f["bytes"] or sha256_file(p) != f["sha256"]:
            problems.append(f"changed {f['path']}")
    known = {f["path"] for f in old["files"]} | {"MANIFEST.json"}
    for p in sorted(package.rglob("*")):
        if p.is_file() and str(p.relative_to(package)) not in known:
            problems.append(f"unlisted {p.relative_to(package)}")
    for a in old["artifacts"]:
        p = package / a["package_file"]
        if sha256_file(p) != a["pinned_sha256"]:
            problems.append(f"pin mismatch {a['package_file']}")
    if problems:
        for x in problems:
            print("FAIL", x)
        return 1
    print(f"OK: {len(old['files'])} files match MANIFEST.json; 2 artifact pins match")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    package = HERE
    if args.check:
        return check(package)
    manifest, ok = build(package)
    (package / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["checks"], indent=1))
    print("files:", len(manifest["files"]))
    for note in manifest["checks"]["notes"]:
        print("NOTE", note)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
