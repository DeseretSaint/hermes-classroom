#!/usr/bin/env python3
"""CP-015c — the Workshop install proof for one real course, on a fresh profile.

The card's acceptance is about opt-in: a fresh library must not contain the course, the Workshop
catalogue must offer it with the pack's own content hash and licence, and after the learner's own
install the course must be on the shelf with a ``lesson.page`` that actually serves the pack's
lesson and media.

Nothing here is hand-built state:

* the catalogue is ``coursebook.workshop.catalog_view()`` — the same read the ``/workshop/catalog``
  route performs, which re-validates the manifest, re-hashes every declared file, re-audits the
  bundle and compares the catalogue's declared content hash with the manifest's own;
* the install is ``coursebook.workshop.install()`` — staging outside adopted storage, then the
  real atomic ``pack.import`` gate;
* the shelf rows are real ``library.list`` envelopes from ``coursebook.api.dispatch``;
* the page is the real ``lesson.page`` read, and the artifact count is what that read resolved.

The profile is a throwaway ``HERMES_HOME``, so "the library was empty" is a fact about a fresh
profile rather than a claim about the authoring home.

    python3 scripts/cp015c-workshop-install-proof.py
    python3 scripts/cp015c-workshop-install-proof.py --pack-id japanese-cafe-basics --out <path>

Exit status is 0 only when every step passed, the fresh shelf was empty of the pack, the installed
shelf carries it, the served page is non-empty, and no user-visible string carries demo/sample/
fixture wording.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_PACK = "japanese-cafe-basics"
DEFAULT_OUT = ROOT / "docs" / "concept-parity" / "demo" / "cp015c-install-proof.json"

#: Owner ruling 2026-11-10: these are starter courses, not demo data. Nothing a learner reads may
#: say demo, sample or fixture.
FIXTURE_WORDING = re.compile(r"demo|sample|fixture", re.IGNORECASE)


def strings_in(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(strings_in(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(strings_in(item))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-id", default=DEFAULT_PACK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    home = tempfile.mkdtemp(prefix="cp015c-install-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    failures: list[str] = []
    try:
        from coursebook import api, archive, db, packs, workshop  # noqa: E402
        from tests.kernel_support import request  # noqa: E402

        db.migrate()

        def envelope(method: str, payload: dict) -> dict:
            return api.dispatch(request(method, payload))

        shelf_before = envelope("library.list", {"filter": "all", "limit": 100, "sort": "title"})
        if not shelf_before["ok"]:
            failures.append(f"library.list failed on the fresh profile: {shelf_before.get('error')}")
        before_items = (shelf_before.get("result") or {}).get("items") or []

        catalog = workshop.catalog_view()
        if catalog.get("refused"):
            failures.append(f"catalogue refused entries: {catalog['refused']}")
        entry = next((item for item in catalog.get("items") or []
                      if item.get("pack_id") == args.pack_id), None)
        if entry is None:
            failures.append(f"{args.pack_id} is not in the Workshop catalogue")
            raise SystemExit(2)

        directory = ROOT / "bundled" / "packs" / str(entry["directory"])
        manifest, files = archive.read_directory(directory)
        packs.validate_manifest(manifest)
        packs.validate_minima(manifest)
        packs.verify_content_hash(manifest)
        audit = packs.audit_bundle(directory)
        if audit:
            failures.append(f"bundled pack content audit failed: {audit}")
        if str(manifest.get("content_hash")) != str(entry.get("content_hash")):
            failures.append("catalogue content_hash does not equal the pack manifest's")

        # Opt-in: the fresh profile must not already hold the course.
        if any(item.get("title") == manifest.get("title") for item in before_items):
            failures.append("the fresh shelf already carries the course before any install")
        installed = workshop.install(args.pack_id)
        if not installed.get("imported"):
            failures.append("workshop.install did not import the pack on a fresh profile")

        shelf_after = envelope("library.list", {"filter": "all", "limit": 100, "sort": "title"})
        after_items = (shelf_after.get("result") or {}).get("items") or []
        row = next((item for item in after_items
                    if item.get("course_id") == installed.get("course_id")), None)
        if row is None:
            failures.append("the installed course is missing from library.list")

        page = None
        if row is not None:
            objective_id = (row.get("evidence_summary") or {}).get("current_objective_id")
            if not objective_id:
                failures.append("the shelf row carries no current objective to open")
            else:
                served = envelope("lesson.page",
                                  {"enrollment_id": row["enrollment_id"],
                                   "objective_id": objective_id})
                if not served["ok"]:
                    failures.append(f"lesson.page refused: {served.get('error')}")
                else:
                    page = served["result"]

        # Idempotence: a second press must answer the same course, not a duplicate.
        repeat = workshop.install(args.pack_id)
        if repeat.get("imported"):
            failures.append("a second install imported a duplicate instead of reusing the course")

        blocks = (page or {}).get("blocks") or (page or {}).get("segments") or []
        document = (page or {}).get("document") or {}
        if document.get("blocks"):
            blocks = document["blocks"]
        artifacts = (page or {}).get("artifacts") or (page or {}).get("media") or []
        if page is not None:
            if not blocks:
                failures.append("lesson.page served no blocks")
            if (manifest.get("media") or []) and not artifacts:
                failures.append(
                    f"manifest declares {len(manifest.get('media') or [])} media[] link(s) but the "
                    "served page resolved no artifact"
                )

        # The fixture-word scan runs over everything a learner would read: the catalogue card, the
        # shelf row, the served page, and the manifest's own visible strings.
        visible = {
            "catalogue_item": entry,
            "library_row": row,
            "lesson_page": page,
            "manifest": {key: manifest.get(key) for key in
                         ("title", "subtitle", "attribution", "safety_notes", "content_notes")},
        }
        hits = []
        for where, value in visible.items():
            for text in strings_in(value):
                match = FIXTURE_WORDING.search(text)
                if match is not None:
                    hits.append([where, text, match.group(0)])

        record = {
            "pack_id": args.pack_id,
            "profile_home": home,
            "fresh_library_count": len(before_items),
            "fresh_library_titles": [item.get("title") for item in before_items],
            "catalogue": {
                "count": catalog.get("count"),
                "content_hash": entry.get("content_hash"),
                "pack_version": entry.get("pack_version"),
                "title": entry.get("title"),
                "level_label": entry.get("level_label"),
                "locale": entry.get("locale"),
                "license": entry.get("license"),
                "trust_labels": entry.get("trust_labels"),
                "objective_count": entry.get("objective_count"),
                "section_count": entry.get("section_count"),
            },
            "manifest": {
                "title": manifest.get("title"),
                "pack_id": manifest.get("pack_id"),
                "pack_version": manifest.get("pack_version"),
                "content_hash": manifest.get("content_hash"),
                "license": manifest.get("license"),
                "file_count": len(files),
                "declared_files": len(manifest.get("files") or []),
                "media_links": len(manifest.get("media") or []),
                "sources": len(manifest.get("sources") or []),
            },
            "install": installed,
            "install_repeat": repeat,
            "library_after": [
                {
                    "course_id": item.get("course_id"),
                    "title": item.get("title"),
                    "enrollment_id": item.get("enrollment_id"),
                    "next_step": item.get("next_step"),
                    "evidence_summary": item.get("evidence_summary"),
                }
                for item in after_items
            ],
            "lesson_page": {
                "state": (page or {}).get("state") or document.get("state"),
                "section_title": document.get("section_title"),
                "blocks": len(blocks),
                "artifacts": len(artifacts),
                "check": bool((page or {}).get("check") or document.get("check_id")),
                "first_block": (blocks[0] if blocks else None),
            },
            "fixture_word_hits": hits,
            "failures": failures,
        }
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({key: record[key] for key in
                      ("pack_id", "fresh_library_count", "install", "lesson_page",
                       "fixture_word_hits", "failures")}, indent=2, ensure_ascii=False))
    if failures or hits:
        print("FAIL")
        return 1
    print("PASS — fresh shelf empty, catalogue offer read, install lands, page serves content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
