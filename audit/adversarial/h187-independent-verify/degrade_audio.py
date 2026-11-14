#!/usr/bin/env python3
"""Independent (Sentinel) probe of the audio degradation path.

The provider refuses. Nothing here calls a network service: the host seam returns the same
``{"success": false, "error": ...}`` envelope the tools registry returns when a provider refuses.
The probe runs the shipped path:

    media.generate_for_lessons -> artifacts.produce_with_fallback -> gen_lessons.media_json
    api.dispatch('lesson.page') -> the served document a learner's Desktop renders

and then records what the learner-facing surface would be told. It runs only against a
dedicated copy of the prepared home; it refuses to run against the prepared home itself.

Usage:
    python3 degrade_audio.py --home /path/to/COPY/home --out result.json --served served.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")

LESSON_ID = "gen_lang_1"
COURSE_ID = "crs_c330330a969646cfb0735f9f3644c107"
ENROLLMENT_ID = "enr_22c18bf3305a4b0ca769b8219e0036dd"
OBJECTIVE_ID = "obj_903c89f63e4940d7a8220082e4d68429"
BLOCK_ID = "blk_280128ee1e4e4ded9d13"
AUDIO_ARTIFACT_ID = "art_adf2e015a0694641a409bb54e9a6a746"

CHECKS: list[dict] = []


def check(check_id: str, ok: bool, detail: object) -> None:
    CHECKS.append({"id": check_id, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + check_id + " :: " + json.dumps(detail, ensure_ascii=False)[:400])


class RefusingHost:
    """The host seam, with a provider that refuses. No network, no key."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def dispatch_tool(self, name: str, args: dict, **kwargs):
        self.calls.append({"tool": name, "keys": sorted(args)})
        return json.dumps(
            {
                "success": False,
                "error": "provider refused the request (simulated refusal; no bytes produced)",
                "provider": "openai",
                "error_type": "provider_refusal",
            }
        )


class NoToolHost:
    """An old host with no dispatch_tool: the seam must stay unbound."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--served", required=True)
    args = parser.parse_args()

    home = Path(args.home).resolve()
    if home == Path("/home/deseretsaint/.hermes/h187-course/home").resolve():
        raise SystemExit("refusing to run the destructive degradation probe against the prepared home")
    os.environ["HERMES_HOME"] = str(home)

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(HERMES_AGENT))

    import coursebook.domain  # noqa: F401
    from coursebook import api, artifacts as artifacts_mod, contracts, db, media

    result: dict = {"kind": "audio_degradation_probe", "verifier": "sentinel", "home": str(home)}

    # ── arrange: a lesson that has never received bytes, and no cached audio to reuse ──
    with db.read() as connection:
        lesson = connection.execute(
            "SELECT page_json, media_json, state FROM gen_lessons WHERE id = ?", (LESSON_ID,)
        ).fetchone()
        artifacts_before = connection.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"]
    authored_media = json.loads(lesson["page_json"] or "{}").get("media") or []
    check("arrange.authored_item_exists", len(authored_media) == 1, authored_media)
    authored_item = dict(authored_media[0])

    with db.transaction() as write:
        write.execute(
            "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
            (json.dumps([authored_item], ensure_ascii=False, sort_keys=True), LESSON_ID),
        )
        audio_row = write.execute(
            "SELECT path FROM artifacts WHERE id = ?", (AUDIO_ARTIFACT_ID,)
        ).fetchone()
        write.execute("DELETE FROM artifacts WHERE id = ?", (AUDIO_ARTIFACT_ID,))
    if audio_row is not None:
        cached_path = Path(str(audio_row["path"]))
        # The copy's own object, not the prepared store's row path.
        local = Path(artifacts_mod.read_root()) / "objects" / cached_path.name[:2] / cached_path.name
        local.unlink(missing_ok=True)
        result["removed_cached_object"] = str(local)
    with db.read() as connection:
        artifacts_before = connection.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"]
    result["artifacts_before"] = int(artifacts_before)

    # ── act: the provider refuses ─────────────────────────────────────────────────────
    host = RefusingHost()
    media.bind_host_seam(host)
    check("seam.bound", media.host_media() is not None, True)
    with db.read() as connection:
        summary = media.generate_for_lessons(
            connection, lesson_ids=[LESSON_ID], job_id="sentinel-degrade-probe",
            host=media.host_media(),
        )
    result["summary"] = summary.as_checkpoint()
    result["dispatch_calls"] = host.calls

    check("generate.no_artifact", summary.artifact_ids == [], summary.artifact_ids)
    check("generate.generated_zero", summary.generated == 0, summary.generated)
    check("generate.degraded_one", summary.degraded == 1, summary.degraded)
    check("generate.provider_was_asked", any(c["tool"] == "text_to_speech" for c in host.calls),
          host.calls)

    with db.read() as connection:
        stored = json.loads(
            connection.execute(
                "SELECT media_json FROM gen_lessons WHERE id = ?", (LESSON_ID,)
            ).fetchone()["media_json"]
        )
        artifacts_after = connection.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"]
    item = stored[0] if stored else {}
    result["stored_item"] = item
    check("stored.no_artifact_id", not item.get("artifact_id"), item.get("artifact_id"))
    check("stored.no_content_hash", not item.get("content_hash"), item.get("content_hash"))
    check("stored.no_mime", not item.get("mime"), item.get("mime"))
    check("stored.degraded_true", item.get("degraded") is True, item.get("degraded"))
    check("stored.reason_present", bool(str(item.get("reason") or "").strip()), item.get("reason"))
    check("stored.reason_says_text",
          "text" in str(item.get("reason") or "").lower(), item.get("reason"))
    check("stored.text_equivalent_kept",
          item.get("text_equivalent") == authored_item.get("text_equivalent"),
          item.get("text_equivalent"))
    check("store.no_new_row", int(artifacts_after) == int(artifacts_before),
          {"before": artifacts_before, "after": artifacts_after})
    result["artifacts_after"] = int(artifacts_after)

    # ── serve: what the learner's page actually says ───────────────────────────────────
    served = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "sentinel-degradation-serve",
            "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
        }
    )
    page = served.get("result") or {}
    document = page.get("document") or {}
    check("serve.ok", bool(served.get("ok")), served.get("error"))
    blocks = document.get("blocks") or []
    target = next((b for b in blocks if b.get("id") == BLOCK_ID), None)
    check("serve.target_block_present", target is not None, [b.get("id") for b in blocks])
    media_children = (target or {}).get("media") or []
    result["served_block_media"] = media_children
    check("serve.block_has_one_media_child", len(media_children) == 1, len(media_children))
    child = media_children[0] if media_children else {}
    check("serve.no_artifact_id", not child.get("artifact_id"), child.get("artifact_id"))
    check("serve.degraded_true", child.get("degraded") is True, child.get("degraded"))
    check("serve.reason_present", bool(str(child.get("reason") or "").strip()), child.get("reason"))
    check("serve.text_equivalent_present",
          bool(str(child.get("text_equivalent") or "").strip()), child.get("text_equivalent"))
    served_artifacts = page.get("artifacts") or []
    check("serve.no_audio_artifact_advertised",
          not any(a.get("kind") == "audio" for a in served_artifacts),
          served_artifacts)

    Path(args.served).write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ── second refusal shape: no host seam at all (old host) ──────────────────────────
    with db.transaction() as write:
        write.execute(
            "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
            (json.dumps([authored_item], ensure_ascii=False, sort_keys=True), LESSON_ID),
        )
    media.bind_host_seam(NoToolHost())
    check("seam.unbound_without_dispatch_tool", media.host_media() is None, media.host_media())
    with db.read() as connection:
        summary2 = media.generate_for_lessons(connection, lesson_ids=[LESSON_ID], host=None)
    check("unbound.skipped", summary2.skipped == 1, summary2.as_checkpoint())
    served2 = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "sentinel-degradation-serve-unbound",
            "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
        }
    )
    page2 = served2.get("result") or {}
    doc2 = page2.get("document") or {}
    target2 = next((b for b in (doc2.get("blocks") or []) if b.get("id") == BLOCK_ID), None)
    child2 = ((target2 or {}).get("media") or [{}])[0]
    check("unbound.served_still_honest",
          not child2.get("artifact_id") and child2.get("degraded") is True
          and bool(str(child2.get("reason") or "").strip()),
          child2)
    result["unbound_served_block_media"] = (target2 or {}).get("media")

    failures = [c for c in CHECKS if not c["ok"]]
    result.update(
        {
            "checks_total": len(CHECKS),
            "checks_passed": len(CHECKS) - len(failures),
            "failures": [c["id"] for c in failures],
            "status": "PASS" if not failures else "FAIL",
            "checks": CHECKS,
        }
    )
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "checks_total", "checks_passed", "failures")},
                     indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
