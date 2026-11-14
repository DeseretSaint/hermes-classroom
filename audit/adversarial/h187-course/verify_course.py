#!/usr/bin/env python3
"""Verify the H-187 preparation courses without generating any media.

Reads the durable store built by ``build_course.py``, re-serves every lesson page through the
product read path, and checks each stored media spec against the real media policy and producer
table (``media.producer_for``) so the mime constraint is observed, not asserted from prose.
Refuses if any artifact row already exists: this task declares requirements and produces no bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ac36aad4")
HOME = Path.home() / ".hermes" / "h187-course" / "home"
EVIDENCE = REPO / "audit" / "adversarial" / "h187-course"

os.environ["HERMES_HOME"] = str(HOME)
sys.path.insert(0, str(REPO))

from coursebook import api, artifacts, contracts, db, domain, generation, media, policy  # noqa: E402,F401

VERSION = contracts.WIRE_CONTRACT_VERSION

#: The host seam only has to exist for producer_for to return the closure; it is never invoked.
class _HostNotInvoked:
    def image(self, *a, **k):
        raise AssertionError("verify_course must not call the image provider")

    def speech(self, *a, **k):
        raise AssertionError("verify_course must not call the speech provider")


#: What each producer's declared mime means for the bytes a real run must return. ``sniff_mime``
#: rejects a declared type that contradicts the magic bytes, so this is the acceptance rule.
MIME_RULES = {
    "audio/mpeg": {
        "declared": "audio/mpeg",
        "magic": ["ID3", "MPEG frame sync 0xFF 0xEx/0xFx"],
        "kind": "audio",
        "max_bytes": artifacts._MAX_BYTES["audio"],
    },
    "image/svg+xml": {
        "declared": "image/svg+xml",
        "magic": ["<svg (sanitized allowlist subset; scripts, foreignObject, external hrefs removed/rejected)"],
        "kind": "visual",
        "max_bytes": artifacts._MAX_BYTES["visual"],
    },
    "image/png": {
        "declared": "image/png",
        "magic": ["89 50 4E 47 0D 0A 1A 0A"],
        "kind": "visual",
        "max_bytes": artifacts._MAX_BYTES["visual"],
    },
}


def request(method: str, payload: dict) -> dict:
    response = api.dispatch({
        "contract": "cb.rpc",
        "contract_version": VERSION,
        "method": method,
        "operation_id": f"h187verify-{method.replace('.', '-')}",
        "payload": payload,
    })
    if not response.get("ok"):
        raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'))}")
    return response["result"]


def main() -> int:
    facts_path = EVIDENCE / "course_facts.json"
    facts = json.loads(facts_path.read_text())
    db.ensure_schema()

    with db.read() as connection:
        artifact_count = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    if artifact_count:
        raise RuntimeError(f"this store already holds {artifact_count} artifact row(s); "
                           "preparation must not generate media")

    report = {
        "hermes_home": str(HOME),
        "wire_contract_version": VERSION,
        "artifacts_in_store": artifact_count,
        "courses": [],
    }

    for course in facts["courses"]:
        with db.read() as connection:
            plan = dict(connection.execute("SELECT * FROM plans WHERE id = ?", (course["plan_id"],)).fetchone())
            enrollment = dict(connection.execute(
                "SELECT * FROM enrollments WHERE id = ?", (course["enrollment_id"],)).fetchone())
        entry = {
            "course_id": course["course_id"],
            "title": course["title"],
            "recipe": course["recipe"],
            "locale": course["locale"],
            "subject_domain": course["subject_domain"],
            "plan_id": course["plan_id"],
            "plan_state": plan["state"],
            "plan_hash": plan["plan_hash"],
            "enrollment_id": course["enrollment_id"],
            "in_library": course["in_library"],
            "lessons": [],
        }
        if plan["state"] != "approved":
            raise RuntimeError(f"plan {course['plan_id']} is {plan['state']}, not approved")
        for lesson in course["lessons"]:
            page = request("lesson.page", {
                "enrollment_id": course["enrollment_id"],
                "objective_id": lesson["objective_id"],
            })
            document = page.get("document") or {}
            with db.read() as connection:
                row = dict(connection.execute(
                    "SELECT * FROM gen_lessons WHERE id = ?", (lesson["lesson_id"],)).fetchone())
                items = json.loads(row["media_json"] or "[]")
            capability = json.loads(row["policy_json"] or "{}")
            media_out = []
            for item in items:
                spec = media._media_spec(item, locale=course["locale"])
                artifacts.assert_media_ok(spec)
                producer, expected_mime = media.producer_for(spec, _HostNotInvoked())
                rule = MIME_RULES[expected_mime]
                spec_fp = artifacts.spec_hash(spec.as_cache_spec())
                media_out.append({
                    "kind": spec.kind,
                    "role": spec.role,
                    "purpose": item.get("purpose"),
                    "text_equivalent": spec.text_equivalent,
                    "transcript": spec.transcript,
                    "language": spec.language,
                    "voice": spec.voice,
                    "prompt": spec.prompt,
                    "facts": spec.facts,
                    "expected_mime": expected_mime,
                    "mime_rule": rule,
                    "spec_fingerprint": spec_fp,
                    "producer": "deterministic_schematic" if expected_mime == "image/svg+xml"
                                else ("host.image_generate" if spec.kind == "visual" else "host.text_to_speech"),
                    "store_state": {
                        "artifact_id": item.get("artifact_id"),
                        "mime": item.get("mime"),
                        "degraded": item.get("degraded"),
                        "reason": item.get("reason"),
                    },
                })
            placement = [
                {
                    "block_id": block.get("id"),
                    "block_role": block.get("role"),
                    "block_headline": block.get("headline"),
                    "media_index_in_block": index,
                    "kind": child.get("kind"),
                    "role": child.get("role"),
                    "artifact_id": child.get("artifact_id"),
                }
                for block in document.get("blocks") or []
                for index, child in enumerate(block.get("media") or [])
            ]
            entry["lessons"].append({
                "lesson_id": lesson["lesson_id"],
                "section_id": lesson["section_id"],
                "objective_id": lesson["objective_id"],
                "objective_title": lesson["objective_title"]
                    if "objective_title" in lesson else (page.get("section") or {}).get("title"),
                "lesson_state": row["state"],
                "validation_id": row["validation_id"],
                "plan_hash_on_row": row["plan_hash"],
                "generation_digest": course["generation_digest"],
                "media_need": lesson["media_need"],
                "capability": capability,
                "served_page": {
                    "document_id": document.get("document_id"),
                    "content_hash": document.get("content_hash"),
                    "document_state": document.get("state"),
                    "provenance": page.get("provenance"),
                    "check_id": document.get("check_id"),
                    "block_roles": [b.get("role") for b in document.get("blocks") or []],
                },
                "media_requirements": media_out,
                "placement": placement,
            })
        report["courses"].append(entry)

    db_file = HOME / "plugin_data" / "coursebook" / "coursebook.db"
    if not db_file.exists():
        candidates = sorted(HOME.rglob("*.db"))
        db_file = candidates[0] if candidates else db_file
    report["db_path"] = str(db_file)
    report["db_sha256"] = hashlib.sha256(db_file.read_bytes()).hexdigest() if db_file.exists() else None

    EVIDENCE.joinpath("verification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps({
        "artifacts_in_store": report["artifacts_in_store"],
        "db": report["db_path"],
        "db_sha256": report["db_sha256"],
        "courses": [
            {
                "course_id": c["course_id"], "plan_state": c["plan_state"], "in_library": c["in_library"],
                "lessons": [
                    {"lesson_id": l["lesson_id"], "state": l["lesson_state"],
                     "media": [{"kind": m["kind"], "role": m["role"], "mime": m["expected_mime"]}
                               for m in l["media_requirements"]],
                     "placement": [(p["block_id"], p["block_role"], p["kind"]) for p in l["placement"]]}
                    for l in c["lessons"]
                ],
            }
            for c in report["courses"]
        ],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
