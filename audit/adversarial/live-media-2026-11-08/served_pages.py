#!/usr/bin/env python3
"""Read the served `lesson.page` for the two H-187 media enrollments, read-only.

No provider is called and nothing is written inside HERMES_HOME. The product's own
``lesson.page`` RPC is the reader, so the JSON recorded here is exactly what the learner
surface is handed, not the stored row the author wrote.

    HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
      python3 served_pages.py --home /home/deseretsaint/.hermes/h187-course/home \
      --out pages

Writes ``<out>/gen_lang_1.page.json`` and ``<out>/gen_tech_2.page.json``.
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

TARGETS = [
    {
        "lesson_id": "gen_lang_1",
        "enrollment_id": "enr_22c18bf3305a4b0ca769b8219e0036dd",
        "objective_id": "obj_903c89f63e4940d7a8220082e4d68429",
        "block_id": "blk_280128ee1e4e4ded9d13",
        "artifact_id": "art_adf2e015a0694641a409bb54e9a6a746",
    },
    {
        "lesson_id": "gen_tech_2",
        "enrollment_id": "enr_5906d9d5f01a420cba6d2d202db8da53",
        "objective_id": "obj_75056df1acb84e4ea637b30421c5cca9",
        "block_id": "blk_aecba1e56d346fc8e07b",
        "artifact_id": "art_d7dc7afd153d4736abc4d2e0560a8376",
    },
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    home = Path(args.home).resolve()
    out_dir = Path(args.out).resolve()
    if str(out_dir).startswith(str(home)):
        raise SystemExit("refusing to write output inside the prepared home")
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HERMES_HOME"] = str(home)
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(HERMES_AGENT))

    import coursebook.domain  # noqa: F401  (registers cb.rpc handlers incl. lesson.page)
    from coursebook import api, contracts, db

    db_path = Path(db.database_path())
    db_before = sha256_file(db_path)

    summary = []
    for t in TARGETS:
        served = api.dispatch(
            {
                "contract": "cb.rpc",
                "contract_version": contracts.WIRE_CONTRACT_VERSION,
                "method": "lesson.page",
                "operation_id": f"harbor-live-media-{t['lesson_id']}",
                "payload": {
                    "enrollment_id": t["enrollment_id"],
                    "objective_id": t["objective_id"],
                },
            }
        )
        if not served.get("ok"):
            print("FAIL", t["lesson_id"], served.get("error"))
            return 1
        page = served["result"]
        dest = out_dir / f"{t['lesson_id']}.page.json"
        dest.write_text(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")

        blocks = ((page.get("document") or {}).get("blocks") or [])
        block = next(
            (b for b in blocks if b.get("id") == t["block_id"] or b.get("block_id") == t["block_id"]),
            None,
        )
        media = ((block or {}).get("media") or [])
        art_entry = next(
            (a for a in (page.get("artifacts") or []) if a.get("artifact_id") == t["artifact_id"]),
            None,
        )
        ref_ok = bool(block) and any(m.get("artifact_id") == t["artifact_id"] for m in media)
        summary.append(
            {
                "lesson_id": t["lesson_id"],
                "page_file": dest.name,
                "page_bytes": dest.stat().st_size,
                "page_sha256": sha256_file(dest),
                "document_state": (page.get("document") or {}).get("state"),
                "provenance": page.get("provenance"),
                "block_found": bool(block),
                "block_media_entry": media[0] if media else None,
                "page_artifacts_entry": art_entry,
                "page_references_artifact": ref_ok and art_entry is not None,
            }
        )
        print(f"{t['lesson_id']}: block_found={bool(block)} refs={ref_ok} art={art_entry is not None}")

    db_after = sha256_file(db_path)
    report = {
        "kind": "served_lesson_pages",
        "reader": "cb.rpc lesson.page (product read path)",
        "home": str(home),
        "db_sha256_before": db_before,
        "db_sha256_after": db_after,
        "db_unchanged": db_before == db_after,
        "pages": summary,
    }
    (out_dir / "served_pages.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("db_unchanged:", report["db_unchanged"])
    return 0 if report["db_unchanged"] and all(p["page_references_artifact"] for p in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
