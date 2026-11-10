"""H-196 — the local Workshop catalogue and bundled installer.

The Workshop is a **read model over packs that already exist in this repository**. It is not a
marketplace: there is no server, no account, no upload, no price, no rating, no learner count and
no publication state. Two files own the contract:

* ``catalog/workshop.v1.json`` carries only the editorial facts a pack manifest does not: the
  categories a shelf groups by, one sentence of outcome, a creator note, what the course will not
  teach, a changelog and which manifest file (if any) is a usable visual for the card.
* Each pack's own ``pack.json`` remains the identity, hash, structure and licence authority.

Every read re-derives the pack from its directory: the manifest is validated, every declared file
is re-hashed, the teaching minima are re-audited, and the four trust labels are computed from those
facts. A catalogue entry whose pack cannot be read is reported as refused — never rendered as if it
existed. A catalogue entry can never add, relax or reinterpret a manifest field.

``install`` is the one write path. It takes a ``pack_id`` from this catalogue — never a path — and
resolves that id to a directory inside ``bundled/packs`` with a slug allowlist, so a request cannot
name a file outside the shipped fixtures. The bytes are then staged outside adopted storage and
handed to the existing atomic ``pack.import`` path, which re-validates everything. Installing an
already-installed pack returns the existing course instead of importing a duplicate.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from . import archive, db, packs, pack_flow

#: ``coursebook/workshop.py`` -> plugin root.
ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog" / "workshop.v1.json"
BUNDLED_ROOT = ROOT / "bundled" / "packs"

#: A catalogue is editorial data with a tiny surface; anything outside this is not a catalogue.
MAX_PACKS = 24
MAX_CATEGORIES = 6
MAX_CHANGELOG = 12
MAX_WILL_NOT_TEACH = 8
MAX_SOURCES = 20
MAX_TEXT = 2000

#: ``directory`` is not a path. It is one lowercase slug resolved beneath :data:`BUNDLED_ROOT`.
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class WorkshopError(Exception):
    """A catalogue or install refusal. The route returns it as data, never as a traceback."""


# ── catalogue document ─────────────────────────────────────────────────────


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any, *, limit: int = MAX_TEXT) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] if text else None


def _text_list(value: Any, *, limit: int, item_limit: int = 400) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        text = _text(item, limit=item_limit)
        if text:
            out.append(text)
    return out


def load_catalog() -> dict[str, Any]:
    """Read and bound the catalogue. A malformed file refuses the whole surface by name."""
    try:
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkshopError(f"the Workshop catalogue cannot be read: {exc}") from exc
    if not isinstance(document, Mapping):
        raise WorkshopError("the Workshop catalogue is not a JSON object")
    if document.get("contract") != "cb.workshop" or int(document.get("contract_version") or 0) != 1:
        raise WorkshopError("the Workshop catalogue declares an unknown contract")
    entries = document.get("packs")
    if not isinstance(entries, list) or not entries:
        raise WorkshopError("the Workshop catalogue lists no packs")
    if len(entries) > MAX_PACKS:
        raise WorkshopError(f"the Workshop catalogue lists more than {MAX_PACKS} packs")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise WorkshopError("a Workshop catalogue entry is not an object")
        pack_id = _text(entry.get("pack_id"), limit=128)
        if not pack_id or pack_id in seen:
            raise WorkshopError("a Workshop catalogue entry has no id or repeats one")
        seen.add(pack_id)
        slug = _text(entry.get("directory"), limit=80)
        if not slug or not _SLUG.match(slug):
            raise WorkshopError(f"catalogue entry {pack_id!r} names no safe bundled directory")
        if not _SHA256.match(str(entry.get("content_hash") or "")):
            raise WorkshopError(f"catalogue entry {pack_id!r} declares no pack content hash")
    return dict(document)


def _bundled_directory(slug: str) -> Path:
    """Resolve one catalogue slug beneath the shipped fixtures, refusing any escape."""
    if not _SLUG.match(str(slug or "")):
        raise WorkshopError("the catalogue entry names no safe bundled directory")
    root = BUNDLED_ROOT.resolve()
    candidate = (root / str(slug)).resolve()
    if candidate.parent != root or not candidate.is_dir():
        raise WorkshopError(f"bundled pack {slug!r} is not a directory under bundled/packs")
    if (root / str(slug)).is_symlink():
        raise WorkshopError(f"bundled pack {slug!r} is a symbolic link")
    return candidate


# ── live state ─────────────────────────────────────────────────────────────


def _installed_rows(pack_id: str, version: str) -> dict[str, Any] | None:
    """The one course and enrollment this profile holds for that pack release, if any."""
    db.ensure_schema()
    with db.read() as connection:
        row = connection.execute(
            "SELECT e.id AS enrollment_id, e.revision AS revision, e.status AS enrollment_status,"
            " e.updated_at AS updated_at, c.id AS course_id, c.title AS title,"
            " p.state AS pack_state"
            " FROM enrollments e JOIN courses c ON c.id = e.course_id"
            " JOIN packs p ON p.id = c.pack_id"
            " WHERE p.pack_id = ? AND p.version = ? AND c.status != 'deleted'"
            " ORDER BY e.created_at DESC, e.rowid DESC LIMIT 1",
            (pack_id, version),
        ).fetchone()
    return dict(row) if row is not None else None


def _course_visual_rows(connection, course_id: str):
    """This course's own visual artifacts, in the order the media route already serves them.

    An artifact row is keyed by ``(content_hash, kind)``, so a second import of the same pack
    reuses the first course's row; the join goes through this course's lesson segments to keep
    the read course-scoped. The artifact row's own course is the fallback for a generated visual.
    """
    return connection.execute(
        "SELECT a.id AS artifact_id, a.provenance_json AS provenance_json FROM lesson_segments s"
        " JOIN lesson_runs r ON r.id = s.lesson_run_id"
        " JOIN objectives o ON o.id = r.objective_id"
        " JOIN plans pl ON pl.id = o.plan_id"
        " JOIN artifacts a ON a.id = s.artifact_id"
        " WHERE pl.course_id = ? AND a.kind = 'visual'"
        " ORDER BY pl.version DESC, o.ordinal ASC, s.ordinal ASC",
        (course_id,),
    ).fetchall()


def _pack_provenance_artifact(connection, course_id: str, pack_file: str) -> str | None:
    """The artifact adopted from one pack file for this course's pack, regardless of lesson order.

    A cover is adopted at import but deliberately not written as a lesson segment, so it is not
    reachable through ``_course_visual_rows``. Its provenance still names the pack file it came
    from; that is the durable link the storefront reads. Pack identity comes from the course's own
    pack row, so a shared artifact row (keyed by content hash) cannot leak another pack's cover.
    """
    row = connection.execute(
        "SELECT a.id AS artifact_id FROM artifacts a"
        " JOIN courses c ON c.id = ?"
        " JOIN packs p ON p.id = c.pack_id"
        " WHERE a.kind = 'visual'"
        " AND json_extract(a.provenance_json, '$.pack_file') = ?"
        " AND json_extract(a.provenance_json, '$.pack_id') = p.pack_id"
        " ORDER BY a.created_at ASC, a.rowid ASC LIMIT 1",
        (course_id, pack_file),
    ).fetchone()
    return str(row["artifact_id"]) if row is not None else None


def _cover_artifact(connection, course_id: str, cover_path: str | None = None) -> str | None:
    """The course's cover artifact, read through the media route the app already has.

    A pack's cover is not a new kind of object: it is one of the pack's own visual files, adopted at
    import. When the catalogue names a cover file, that file is preferred by the artifact's own
    ``pack_file`` provenance, so a pack that later gains a figure *before* the plate in lesson order
    cannot silently change its cover. The lookup goes through this course's own lesson segments
    first, because an artifact row is keyed by ``(content_hash, kind)`` and a second import of the
    same pack reuses the first course's row. Falling back to the artifact row's own course keeps a
    generated visual working.
    """
    rows = _course_visual_rows(connection, course_id)
    if cover_path:
        adopted = _pack_provenance_artifact(connection, course_id, cover_path)
        if adopted:
            return adopted
        for row in rows:
            try:
                provenance = json.loads(row["provenance_json"] or "{}")
            except (TypeError, ValueError):
                continue
            if isinstance(provenance, Mapping) and str(provenance.get("pack_file")) == cover_path:
                return str(row["artifact_id"])
    if rows:
        return str(rows[0]["artifact_id"])
    row = connection.execute(
        "SELECT id AS artifact_id FROM artifacts"
        " WHERE course_id = ? AND kind = 'visual' ORDER BY created_at ASC, rowid ASC LIMIT 1",
        (course_id,),
    ).fetchone()
    return str(row["artifact_id"]) if row is not None else None


def _declared_cover_path(entry: Mapping[str, Any]) -> str | None:
    cover = _mapping(entry.get("cover"))
    return _text(cover.get("path"), limit=200) if cover else None


def declared_cover_path_for_pack(pack_id: str | None) -> str | None:
    """The catalogue's own declared cover file for one pack release, or None.

    Read-only and catalogue-scoped. A v1 pack carries no ``media[]`` link, so it declares no cover
    and keeps its composed typographic plate; that absence is a fact, not a lookup failure.
    """
    if not pack_id:
        return None
    try:
        document = load_catalog()
    except (WorkshopError, OSError):  # noqa: BLE001 - a shelf read never fails on a missing catalogue
        return None
    for entry in document.get("packs") or []:
        if isinstance(entry, Mapping) and str(entry.get("pack_id") or "") == str(pack_id):
            return _declared_cover_path(entry)
    return None


def pack_cover_artifact(connection, course_id: str, pack_id: str | None) -> str | None:
    """The pack's *declared* cover artifact for one course, else None (CP-005).

    Strict on purpose. The cover is the one artifact whose own provenance says
    ``pack_file == <the catalogue's cover path>``; the first lesson visual is a figure, not a
    cover, and a pack that declares no cover has none. The shelf card then shows the typographic
    plate instead of an unrelated picture, and nothing is invented to fill the slot.
    """
    path = declared_cover_path_for_pack(pack_id)
    if path is None:
        return None
    for row in _course_visual_rows(connection, course_id):
        try:
            provenance = json.loads(row["provenance_json"] or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(provenance, Mapping) and str(provenance.get("pack_file")) == path:
            return str(row["artifact_id"])
    return _pack_provenance_artifact(connection, course_id, path)



def _install_next_step(connection, enrollment_id: str, course_id: str) -> dict[str, Any] | None:
    from . import domain  # local import: ``domain`` imports this module's siblings at load

    try:
        return domain._library_next_step(connection, {"id": enrollment_id}, {"id": course_id})
    except Exception:  # noqa: BLE001
        return None


def _cover_problems(entry: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[str]:
    """H-197: a catalogue cover must be the pack's own first linked visual, or nothing.

    The Workshop serves a cover through the existing artifact route, and an import adopts an
    artifact only for a ``media[]`` link. So a catalogue cover that is not the pack's first linked
    visual would either never render or — worse — render some *other* figure as the cover. This
    check keeps the catalogue, the manifest and the artifact in one line: the plate the catalogue
    names is the plate the reader sees. A v1 pack declares no ``media[]``, so it cannot serve an
    artifact cover at all and must declare none; it keeps the composed typographic plate.
    """
    cover = _mapping(entry.get("cover"))
    path = _text(cover.get("path"), limit=200) if cover else None
    if not path:
        return []
    images = {
        str(item.get("path"))
        for item in manifest.get("files") or []
        if isinstance(item, Mapping) and str(item.get("mime", "")).startswith("image/")
    }
    if path not in images:
        return [f"catalogue cover {path!r} is not a declared image file of the pack"]
    media = [item for item in manifest.get("media") or [] if isinstance(item, Mapping)]
    if not media:
        return [
            f"catalogue cover {path!r} cannot be served: a v1 pack carries no media[] link, so "
            "its cover is the composed typographic plate"
        ]
    roles = {
        str(item.get("path")): str(item.get("role"))
        for item in manifest.get("files") or []
        if isinstance(item, Mapping)
    }
    linked_covers = [
        str(link.get("path"))
        for link in media
        if roles.get(str(link.get("path"))) == "cover"
    ]
    if roles.get(path) == "cover":
        if len(linked_covers) > 1:
            return [
                f"catalogue cover {path!r} is one of {len(linked_covers)} media-linked covers; "
                "exactly one cover may be served"
            ]
        if linked_covers != [path]:
            return [
                f"catalogue cover {path!r} is not the pack's one media-linked cover "
                f"({linked_covers!r} is); the storefront would show a different plate"
            ]
        if str(media[0].get("path")) != path:
            return [
                f"catalogue cover {path!r} is not the first media[] link "
                f"({media[0].get('path')!r} is); the storefront would show a different figure"
            ]
        return []
    # Legacy v2 packs from before the ``cover`` role: the catalogue cover is the first linked
    # visual. Kept so an older pack still validates; the bundled packs now use ``cover``.
    first_visual = next(
        (str(link.get("path")) for link in media if roles.get(str(link.get("path"))) == "visual"),
        None,
    )
    if first_visual != path:
        return [
            f"catalogue cover {path!r} is not the pack's first linked visual "
            f"({first_visual!r} is); the storefront would show a different figure as the cover"
        ]
    return []


# ── one catalogue entry ────────────────────────────────────────────────────


def _read_entry(entry: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify one bundled pack and return ``(manifest, trust document)`` or raise.

    The read is the same gate an import takes: manifest schema, teaching minima, content hash, the
    content audit, and every declared file's size and sha256. The catalogue's declared content hash
    must equal the manifest's own; a fixture edited without regenerating the catalogue is refused.
    """
    directory = _bundled_directory(str(entry["directory"]))
    manifest, files = archive.read_directory(directory)
    if str(manifest.get("pack_id")) != str(entry["pack_id"]):
        raise WorkshopError("catalogue pack_id does not match the bundled manifest")
    if str(manifest.get("pack_version")) != str(entry["pack_version"]):
        raise WorkshopError("catalogue pack_version does not match the bundled manifest")
    if str(manifest.get("content_hash")) != str(entry["content_hash"]):
        raise WorkshopError(
            "the bundled pack's content hash does not match the catalogue; rebuild the fixtures"
        )
    packs.validate_manifest(manifest)
    packs.validate_minima(manifest)
    packs.verify_content_hash(manifest)
    problems = packs.audit_bundle(directory)
    if problems:
        raise WorkshopError("bundled pack content audit failed: " + "; ".join(problems))
    cover_problems = _cover_problems(entry, manifest)
    if cover_problems:
        raise WorkshopError("; ".join(cover_problems))
    integrity = {
        "hashes_match": set(files) == {str(item["path"]) for item in manifest["files"]},
        "file_count": len(manifest["files"]),
        "expanded_bytes": sum(int(item["bytes"]) for item in manifest["files"]),
    }
    document = packs.preview(manifest, integrity=integrity, automated_checks_passed=True)
    return manifest, document


def _entry_item(entry: Mapping[str, Any], manifest: Mapping[str, Any], preview: Mapping[str, Any], installed: dict[str, Any] | None) -> dict[str, Any]:
    objectives = [objective for objective in manifest.get("objectives") or [] if isinstance(objective, Mapping)]
    sections: list[dict[str, Any]] = []
    minutes = 0
    for objective in sorted(objectives, key=lambda item: int(item.get("ordinal") or 0)):
        minutes += int(objective.get("estimated_minutes") or 0)
        for section in objective.get("sections") or []:
            if isinstance(section, Mapping):
                sections.append(
                    {
                        "title": _text(section.get("title"), limit=200) or "Untitled section",
                        "objective": _text(objective.get("title"), limit=200) or "",
                        "minutes": int(objective.get("estimated_minutes") or 0),
                    }
                )
    trust_block = _mapping(preview.get("trust"))
    integrity_block = _mapping(preview.get("integrity"))
    labels = [str(label) for label in (trust_block.get("labels") or [])]
    cover: Mapping[str, Any] = _mapping(entry.get("cover"))
    cover_path = _text(cover.get("path"), limit=200) if cover else None
    declared_visual = any(
        str(item.get("path")) == cover_path and str(item.get("mime", "")).startswith("image/")
        for item in manifest.get("files") or []
        if isinstance(item, Mapping)
    )
    attribution = _text(manifest.get("attribution"), limit=1200) or ""
    license_block: Mapping[str, Any] = _mapping(manifest.get("license"))
    sources = []
    for source in (manifest.get("sources") or [])[:MAX_SOURCES]:
        if not isinstance(source, Mapping):
            continue
        sources.append(
            {
                "title": _text(source.get("title"), limit=300) or "",
                "publisher": _text(source.get("publisher"), limit=200) or "",
                "url": _text(source.get("url"), limit=500) or "",
                "license_note": _text(source.get("license_note"), limit=400) or "",
                "support_status": _text(source.get("support_status"), limit=60) or "",
            }
        )
    return {
        "pack_id": str(manifest["pack_id"]),
        "pack_version": str(manifest["pack_version"]),
        "title": _text(manifest.get("title"), limit=200) or "Untitled pack",
        "subtitle": _text(manifest.get("subtitle"), limit=300),
        "recipe": str(manifest.get("recipe") or ""),
        "level_label": _text(manifest.get("level_label"), limit=60),
        "locale": _text(manifest.get("locale"), limit=40),
        "content_hash": str(manifest.get("content_hash")),
        "attribution": attribution,
        "license": {
            "id": _text(license_block.get("id"), limit=60) or "unspecified",
            "note": _text(license_block.get("note"), limit=800),
            "redistribution": _text(license_block.get("redistribution"), limit=40),
        },
        "contributors": [
            {"name": _text(item.get("name"), limit=200) or "", "role": _text(item.get("role"), limit=60) or ""}
            for item in (manifest.get("contributors") or [])[:12]
            if isinstance(item, Mapping) and _text(item.get("name"), limit=200)
        ],
        "outcome": _text(entry.get("outcome"), limit=400) or _text(manifest.get("subtitle"), limit=300) or "",
        "creator_note": _text(entry.get("creator_note"), limit=1200),
        "categories": _text_list(entry.get("categories"), limit=MAX_CATEGORIES, item_limit=60),
        "will_not_teach": _text_list(entry.get("will_not_teach"), limit=MAX_WILL_NOT_TEACH, item_limit=400),
        "featured": entry.get("featured") is True,
        "changelog": [
            {
                "version": _text(item.get("version"), limit=40) or "",
                "date": _text(item.get("date"), limit=20) or "",
                "note": _text(item.get("note"), limit=600) or "",
            }
            for item in (entry.get("changelog") or [])[:MAX_CHANGELOG]
            if isinstance(item, Mapping)
        ],
        "objective_count": len(objectives),
        "section_count": len(sections),
        "minutes": minutes,
        "sections": sections[:40],
        "sources": sources,
        "integrity": {
            "hashes_match": bool(integrity_block.get("hashes_match")),
            "file_count": int(integrity_block.get("file_count") or 0),
            "expanded_bytes": int(integrity_block.get("expanded_bytes") or 0),
        },
        # The four labels stay a list of separate facts. `validated` is only ever "these two machine
        # checks", which is what the card's caption says beside the word.
        "trust_labels": labels,
        "validated": "integrity_verified" in labels and "automated_checks_passed" in labels,
        "cover": {
            "kind": "artifact" if (installed and declared_visual and installed.get("cover_artifact_id")) else "typographic",
            "artifact_id": (installed or {}).get("cover_artifact_id") if declared_visual else None,
            "alt": _text(cover.get("alt"), limit=1200) if declared_visual and cover else None,
            "caption": _text(cover.get("caption"), limit=200) if declared_visual and cover else None,
        },
        "installed": None if installed is None else {
            "course_id": installed["course_id"],
            "enrollment_id": installed["enrollment_id"],
            "next_step": installed.get("next_step"),
            "evidence_summary": installed.get("evidence_summary"),
            "updated_at": installed.get("updated_at"),
        },
    }


def catalog_view() -> dict[str, Any]:
    """The whole Discover surface in one read. One call, no per-card fetch, no network."""
    document = load_catalog()
    items: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    db.ensure_schema()
    with db.read() as connection:
        for entry in document["packs"]:
            try:
                manifest, trust = _read_entry(entry)
            except (WorkshopError, archive.PackRejected, packs.PackRejected) as exc:
                refused.append({"pack_id": str(entry.get("pack_id") or ""), "reason": str(exc)})
                continue
            installed_row = _installed_rows(str(manifest["pack_id"]), str(manifest["pack_version"]))
            installed = None
            if installed_row is not None:
                installed = {
                    **installed_row,
                    "cover_artifact_id": _cover_artifact(
                        connection,
                        str(installed_row["course_id"]),
                        _declared_cover_path(entry),
                    ),
                    "next_step": _install_next_step(
                        connection, str(installed_row["enrollment_id"]), str(installed_row["course_id"])
                    ),
                    "evidence_summary": _evidence_summary(connection, str(installed_row["course_id"])),
                }
            items.append(_entry_item(entry, manifest, trust, installed))
    featured = next((item for item in items if item["featured"]), items[0] if items else None)
    return {
        "generated": document.get("generated"),
        "items": items,
        "featured_pack_id": featured["pack_id"] if featured else None,
        "refused": refused,
        "count": len(items),
    }


def _evidence_summary(connection, course_id: str) -> dict[str, Any]:
    from . import domain

    row = connection.execute(
        "SELECT"
        " SUM(CASE WHEN o.state IN ('independent_evidence','delayed_evidence') THEN 1 ELSE 0 END) AS independent,"
        " SUM(CASE WHEN o.state IN ('review_due','needs_review') THEN 1 ELSE 0 END) AS review_due,"
        " COUNT(*) AS total"
        " FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        f" WHERE pl.course_id = ? AND {domain._current_plan_sql()}",
        (course_id,),
    ).fetchone()
    return {
        "independent": int((row["independent"] if row else 0) or 0),
        "review_due": int((row["review_due"] if row else 0) or 0),
        "total_objectives": int((row["total"] if row else 0) or 0),
    }


# ── install ────────────────────────────────────────────────────────────────


def install(pack_id: str) -> dict[str, Any]:
    """Add one catalogued bundled pack to this profile, once.

    Refusals: an unknown id, an unreadable or drifted bundle, a frozen pack (the existing import
    policy), or a second import of the same release. The last one is not an error: it returns the
    course that already holds it, so pressing Add twice never duplicates a pack.
    """
    document = load_catalog()
    entry = next((item for item in document["packs"] if item.get("pack_id") == pack_id), None)
    if entry is None:
        raise WorkshopError("that pack is not in the Workshop catalogue")
    manifest, _trust = _read_entry(entry)
    version = str(manifest["pack_version"])
    existing = _installed_rows(str(manifest["pack_id"]), version)
    if existing is not None:
        return {
            "pack_id": str(manifest["pack_id"]),
            "pack_version": version,
            "course_id": existing["course_id"],
            "enrollment_id": existing["enrollment_id"],
            "revision": int(existing["revision"]),
            "imported": False,
            "message": "This pack is already in your library; nothing was imported twice.",
        }
    staged_id = pack_flow.staging().stage_directory(_bundled_directory(str(entry["directory"])))
    revision, result = pack_flow.pack_import(
        {"staged_id": staged_id, "mode": "fresh"},
        {"idempotency_key": f"cb-workshop-install-{manifest['pack_id']}-{manifest['content_hash'].split(':')[-1][:16]}"},
    )
    return {
        "pack_id": str(result["pack_id"]),
        "pack_version": version,
        "course_id": str(result["course_id"]),
        "enrollment_id": str(result["enrollment_id"]),
        "revision": int(revision),
        "imported": True,
    }
