#!/usr/bin/env python3
"""Rehearsal only: prove the prepared specs are actionable for the media caller.

Runs media.generate_for_lessons against a THROWAWAY COPY of the prepared store with a fake host
that returns synthetic PNG/MP3 bytes. Those bytes are not evidence and are never written to the
prepared store; this script exists to catch a spec the caller would refuse before a downstream
worker spends a provider call on it. The output is labelled as a rehearsal accordingly.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ac36aad4")
HOME = Path.home() / ".hermes" / "h187-course" / "home"
EVIDENCE = REPO / "audit" / "adversarial" / "h187-course"
SCRATCH_ROOT = Path(tempfile.mkdtemp(prefix="h187-media-rehearsal-"))

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 64
MP3 = b"\xff\xfb\x90\x00" + b"x" * 64


class FakeHost:
    def __init__(self):
        self.images = []
        self.speeches = []

    def image(self, prompt, *, aspect_ratio="landscape"):
        self.images.append(prompt)
        return PNG, "image/png"

    def speech(self, text, *, voice=None, language=None, instructions=None):
        self.speeches.append({"text": text, "voice": voice, "language": language})
        return MP3, "audio/mpeg"


def main() -> int:
    rehearsal_home = SCRATCH_ROOT / "home"
    shutil.copytree(HOME, rehearsal_home)
    os.environ["HERMES_HOME"] = str(rehearsal_home)
    sys.path.insert(0, str(REPO))
    from coursebook import api, artifacts, contracts, db, domain, media  # noqa: E402

    facts = json.loads((EVIDENCE / "course_facts.json").read_text())
    lesson_ids = [l["lesson_id"] for c in facts["courses"] for l in c["lessons"]]
    host = FakeHost()
    store = artifacts.ArtifactStore()
    with db.read() as connection:
        summary = media.generate_for_lessons(
            connection, lesson_ids=lesson_ids, job_id="h187-rehearsal", host=host, store=store
        )
    db.ensure_schema()
    served = []
    for course in facts["courses"]:
        for lesson in course["lessons"]:
            response = api.dispatch({
                "contract": "cb.rpc",
                "contract_version": contracts.WIRE_CONTRACT_VERSION,
                "method": "lesson.page",
                "operation_id": f"h187rehearsal-{lesson['lesson_id']}",
                "payload": {"enrollment_id": course["enrollment_id"],
                            "objective_id": lesson["objective_id"]},
            })
            page = response.get("result") or {}
            document = page.get("document") or {}
            served.append({
                "lesson_id": lesson["lesson_id"],
                "artifacts": page.get("artifacts") or [],
                "placed": [
                    {"block_id": b.get("id"), "kind": m.get("kind"),
                     "artifact_id": m.get("artifact_id"), "mime": m.get("mime")}
                    for b in document.get("blocks") or []
                    for m in b.get("media") or []
                ],
            })
    report = {
        "kind": "rehearsal",
        "fake_bytes": True,
        "not_evidence": "synthetic PNG/MP3 bytes; the prepared store is untouched",
        "rehearsal_home": str(rehearsal_home),
        "summary": summary.as_checkpoint(),
        "provider_calls": {"image": host.images, "speech": host.speeches},
        "served": served,
    }
    EVIDENCE.joinpath("rehearsal_media_path.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
