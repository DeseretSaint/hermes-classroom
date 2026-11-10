"""Build contracts/db.v14.json from the frozen v13 inventory (one constraint removed)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "contracts" / "db.v13.json"
dst = ROOT / "contracts" / "db.v14.json"
doc = json.loads(src.read_text())
doc["$id"] = "https://contracts.coursebook.hermes/db/v14"
doc["title"] = "Coursebook database schema v14"
doc["description"] = (
    "Authoritative record shapes for the Coursebook SQLite database, which is the single source "
    "of truth. v14 is additive over v13 and changes one constraint, not one column: migration "
    "0014_takehome_pack_revision_scope.sql rebuilds takehome_packs without the 0013 key "
    "UNIQUE (source_course_id, source_objective_id, source_lesson_version, audience, kind, "
    "revision). A pack's revision is its own optimistic counter (create starts a pack at 0; "
    "approve and export increment that row), so keying it to the source slot made a second pack "
    "for a re-opened lesson unable to progress past draft once the first pack was approved or "
    "exported. Duplicate drafts stay prevented by takehome.create, which returns the existing "
    "draft row instead of inserting one, and id remains the pack identity. Every column, type, "
    "nullability, default, CHECK, foreign key and index is unchanged from v13, no row is "
    "rewritten or backfilled, no v13 table is dropped, and no other v13 entry moves."
)
doc["x-contract-version"] = 14
doc["schema_version"] = 14
doc["x-supersedes"] = "https://contracts.coursebook.hermes/db/v13"

table = doc["tables"]["takehome_packs"]
table.pop("unique", None)
table["notes"] = (
    "A take-home pack is a rendered print artifact bound to the exact source lesson version and "
    "content hash; it never clones, rewrites or re-approves the source course. revision is the "
    "pack's own compare-and-swap counter: create starts a new pack at 0 and approve/export "
    "increment that same row, so re-opening a lesson after an approved or exported pack mints a "
    "new pack identity instead of colliding with the predecessor's revision. Duplicate drafts "
    "for one source slot are refused in the handler (the existing draft is returned). kind "
    "separates the parent print pack, the short activity plan and the one-page homework sheet. "
    "Export requires a previewed and approved row; approval_hash is the hash fence. The learner "
    "page carries no answer key: the answer guide is a distinct section of content_json rendered "
    "for the parent audience only."
)

doc["migration_plan"].append(
    {
        "version": 14,
        "from": 13,
        "migration": "0014_takehome_pack_revision_scope.sql",
        "summary": (
            "Rebuild takehome_packs without UNIQUE (source_course_id, source_objective_id, "
            "source_lesson_version, audience, kind, revision): a pack's revision is scoped to "
            "the pack, not to the source slot."
        ),
        "impact": [
            "No column, type, nullability, default, CHECK, foreign key or index changes; the same rows are copied with the same values and no row is rewritten or backfilled.",
            "No v13 table is dropped: takehome_packs is rebuilt in place and its two indexes are recreated.",
            "A second pack for a re-opened lesson starts at revision 0 and can be approved and exported after the first pack, instead of failing with IntegrityError when it reached the predecessor's revision number.",
            "Duplicate drafts for one source slot are still prevented by takehome.create, which returns the existing draft row; the dropped key was never that guard.",
            "Source courses, lessons, evidence, attempts, artifacts and world assets are not read or written by this migration.",
        ],
    }
)

dst.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
print(dst, dst.stat().st_size, "bytes")
print("keys:", list(doc.keys()))
