#!/usr/bin/env python3
"""CP-042 shipping proof — reproducible from a clean checkout.

Runs the real Workshop read and install path against a throwaway ``HERMES_HOME`` and writes the two
evidence files beside this script:

* ``manifest-validation.json`` — every bundled manifest validates, and the identity/licence that is
  actually in the file;
* ``install-proof.json`` — Discover lists the three shipped courses; each ``workshop.install`` lands
  in ``library.list``; each ``lesson.page`` opens and serves the pack's own prose. The served page
  text is scanned for demo/sample/fixture wording and the full first served segment is recorded, so
  the proof cannot pass by truncating before the prose.

Usage (from the plugin root):

    python3 audit/cp042-shipping/prove_shipping.py

Exit status is 0 only when every step passed and no served page text matched the forbidden wording.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

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
    home = tempfile.mkdtemp(prefix="cp042-proof-")
    os.environ["HERMES_HOME"] = home
    print(f"HERMES_HOME={home}")

    from coursebook import api, archive, db, packs, workshop  # noqa: E402
    from tests.kernel_support import request  # noqa: E402

    db.migrate()

    catalogue = json.loads((ROOT / "catalog" / "workshop.v1.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    # ── 1. each committed manifest validates ──────────────────────────────
    validated: list[dict] = []
    for entry in catalogue["packs"]:
        directory = ROOT / "bundled" / "packs" / entry["directory"]
        manifest, files = archive.read_directory(directory)
        packs.validate_manifest(manifest)
        packs.validate_minima(manifest)
        packs.verify_content_hash(manifest)
        audit = packs.audit_bundle(directory)
        if audit:
            failures.append(f"{entry['pack_id']}: content audit {audit}")
        if str(manifest["content_hash"]) != str(entry["content_hash"]):
            failures.append(f"{entry['pack_id']}: catalogue content_hash is stale")
        if str(manifest["pack_version"]) != str(entry["pack_version"]):
            failures.append(f"{entry['pack_id']}: catalogue pack_version is stale")
        validated.append(
            {
                "pack_id": entry["pack_id"],
                "pack_version": manifest["pack_version"],
                "directory": entry["directory"],
                "content_hash": manifest["content_hash"],
                "title": manifest["title"],
                "license": manifest["license"]["id"],
                "redistribution": manifest["license"]["redistribution"],
                "validated": True,
                "file_count": len(files),
            }
        )
    (HERE / "manifest-validation.json").write_text(
        json.dumps({"count": len(validated), "packs": validated}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ── 2. Discover ───────────────────────────────────────────────────────
    view = workshop.catalog_view()
    if view["count"] != 3 or view["refused"]:
        failures.append(f"Discover is not three clean courses: count={view['count']} refused={view['refused']}")
    discover = {
        "count": view["count"],
        "refused": view["refused"],
        "items": [
            {
                "pack_id": item["pack_id"],
                "title": item["title"],
                "level_label": item.get("level_label"),
                "license": item.get("license"),
            }
            for item in view["items"]
        ],
    }

    # ── 3. install each pack, then read the library and the served page ───
    installs: list[dict] = []
    library: list[dict] = []
    pages: list[dict] = []
    for entry in catalogue["packs"]:
        pack_id = entry["pack_id"]
        installed = workshop.install(pack_id)
        installs.append(installed)
        listed = api.dispatch(request("library.list", {"limit": 100}))
        if not listed["ok"]:
            failures.append(f"{pack_id}: library.list failed: {listed.get('error')}")
            continue
        library = listed["result"]["items"]
        row = next((item for item in library if item["course_id"] == installed["course_id"]), None)
        if row is None:
            failures.append(f"{pack_id}: installed course is missing from library.list")
            continue
        with db.read() as connection:
            objective = connection.execute(
                "SELECT o.id AS id, o.title AS title FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ? ORDER BY o.ordinal LIMIT 1",
                (installed["course_id"],),
            ).fetchone()
        if objective is None:
            failures.append(f"{pack_id}: installed course has no objective")
            continue
        page = api.dispatch(
            request(
                "lesson.page",
                {"enrollment_id": installed["enrollment_id"], "objective_id": objective["id"]},
            )
        )
        if not page["ok"]:
            failures.append(f"{pack_id}: lesson.page failed: {page.get('error')}")
            continue
        document = page["result"].get("document") or {}
        blocks = document.get("blocks") or []
        served = [text for text in strings_in(blocks) if len(text.split()) >= 4]
        hits: list[list[str]] = []
        for text in served:
            match = FIXTURE_WORDING.search(text)
            if match is not None:
                hits.append([text, match.group(0)])
        if hits:
            failures.append(f"{pack_id}: served page carries fixture wording: {hits}")
        if not served:
            failures.append(f"{pack_id}: lesson.page served no readable prose")
        pages.append(
            {
                "pack_id": pack_id,
                "course_id": installed["course_id"],
                "objective_id": objective["id"],
                "section_title": document.get("section_title") or objective["title"],
                "block_count": len(blocks),
                "served_text_count": len(served),
                "fixture_word_hits": hits,
                "first_served_text": served[0] if served else None,
                "all_served_text": served,
            }
        )

    proof = {
        "plugin_root": str(ROOT),
        "hermes_home": home,
        "discover": discover,
        "installs": installs,
        "library": [
            {"course_id": item["course_id"], "title": item.get("title"), "enrollment_id": item.get("enrollment_id")}
            for item in library
        ],
        "lesson_pages": pages,
        "failures": failures,
    }
    (HERE / "install-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps({"discover_count": discover["count"], "installs": len(installs),
                      "library": len(library), "pages": len(pages),
                      "fixture_word_hits": sum(len(p["fixture_word_hits"]) for p in pages)},
                     indent=2))
    if failures:
        print("FAIL")
        for failure in failures:
            print("  -", failure)
        return 1
    print("PASS — three store courses list, install, and serve prose without fixture wording")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
