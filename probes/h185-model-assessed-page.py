#!/usr/bin/env python3
"""H-185 probe: a fresh isolated store, a fixture model_assessed page, and a real attempt.

Run from the repo root::

    python3 probes/h185-model-assessed-page.py

It prints the served ``lesson.page`` shape (block/segment/media counts), the provenance banner,
and the result of one check attempt on the model_assessed page. Every fact comes from a real
SQLite store created by the real migrations; no provider is called.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_lesson_page_model_assessed import (
    GENERATED_MEDIA,
    SEPARATOR,
    ModelAssessedLessonPageTest,
    authored_page,
)


def main() -> int:
    case = ModelAssessedLessonPageTest("test_model_assessed_page_is_served_with_provenance_and_media")
    case.setUp()
    try:
        lesson = case.prepare()
        case.seed_generated_lesson(
            lesson, authored_page(), state="model_assessed", media=GENERATED_MEDIA
        )
        case.set_check_audit(lesson["check_id"], state="open", audit_state="pending")

        page = case.read_page(lesson)
        document = page["document"]
        media = case.media_children(document)
        summary = {
            "objective_id": page["section"]["objective_id"],
            "document_state": document["state"],
            "views": document["views"],
            "block_count": len(document["blocks"]),
            "segment_count": len(page["segments"]),
            "media_count": len(media),
            "media": media,
            "document_check_id": document["check_id"],
            "check_rows": page["checks"],
            "provenance": page["provenance"],
        }
        print("lesson.page =", json.dumps(summary, indent=2, ensure_ascii=False)[:4000])

        question = case.ok(
            "check.get", {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]}
        )["result"]
        print("check.get =", json.dumps(
            {"check_id": question["check_id"], "state": question["state"],
             "audit_state": question["audit_state"], "stimulus_keys": sorted(question["stimulus"])},
            ensure_ascii=False,
        ))

        submitted = case.submit(lesson, SEPARATOR)
        print("attempt.submit =", json.dumps(
            {
                "ok": submitted["ok"],
                "verdict": (submitted.get("result") or {}).get("verdict"),
                "evidence_class": (submitted.get("result") or {}).get("evidence_class"),
                "audit_state_after": case.scalar(
                    "SELECT audit_state FROM checks WHERE id = ?", (lesson["check_id"],)
                ),
                "error": submitted.get("error"),
            },
            ensure_ascii=False,
        ))
        print("provenance.warning =", page["provenance"]["warning"])
    finally:
        case.tearDown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
