#!/usr/bin/env python3
"""Project verification.json into the compact target list downstream media cards consume."""
from __future__ import annotations

import json
from pathlib import Path

EVIDENCE = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ac36aad4") / "audit" / "adversarial" / "h187-course"


def main() -> int:
    report = json.loads((EVIDENCE / "verification.json").read_text())
    targets = []
    for course in report["courses"]:
        for lesson in course["lessons"]:
            for media, place in zip(lesson["media_requirements"], lesson["placement"]):
                targets.append({
                    "hermes_home": report["hermes_home"],
                    "course_id": course["course_id"],
                    "enrollment_id": course["enrollment_id"],
                    "objective_id": lesson["objective_id"],
                    "lesson_id": lesson["lesson_id"],
                    "lesson_page_call": {"enrollment_id": course["enrollment_id"],
                                         "objective_id": lesson["objective_id"]},
                    "media_kind": media["kind"],
                    "media_role": media["role"],
                    "producer": media["producer"],
                    "expected_mime": media["expected_mime"],
                    "mime_rule": media["mime_rule"],
                    "spec_fingerprint": media["spec_fingerprint"],
                    "attach_to": {
                        "block_id": place["block_id"],
                        "block_role": place["block_role"],
                        "media_index_in_block": place["media_index_in_block"],
                    },
                    "current_store_state": media["store_state"],
                })
    payload = {
        "note": "Requirements only. No artifact row exists; generate the bytes, then re-read "
                "lesson.page and take the artifact_id from the block's media child.",
        "artifacts_in_store": report["artifacts_in_store"],
        "db_path": report["db_path"],
        "db_sha256": report["db_sha256"],
        "targets": targets,
    }
    (EVIDENCE / "downstream_media_targets.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
