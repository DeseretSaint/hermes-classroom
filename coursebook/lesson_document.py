"""The durable lesson document: one validated block list, many presentation views.

``docs/VISUAL_MEDIA_PLAN.md`` §5 replaces the linear segment list with a block document. A block
has a structural ``role``, a ``headline``, a ``short`` and a ``deep`` rendering of the same
authored material, at most one ``check_id`` and ``media[]`` children. Every view (Textbook,
Guided, Field Quest, Field Notes) is a lens over this one document; no view is a second
authority and no view may add a fact.

This module is deliberately **projection-only**. It never writes a row, never calls a provider
and never mints an id that claims new content:

* :func:`document_from_page` projects a stored ``gen_lessons.page_json`` (the older v7 shape:
  ``segments`` + ``worked_example`` + ``learner_explanation`` + ``media``) into blocks;
* :func:`document_from_segments` projects the durable ``lesson_segments`` rows that
  ``lesson.page`` renders;
* :func:`document_from_blocks` validates blocks that were authored directly (the v8 path), and
  is what makes the ``complete`` state reachable.

Old rows are never rewritten. A page projected from the v7 shapes has ``short = null`` on every
block, so it reports ``state = "textbook_only"`` and ``views.guided = false`` with a human note —
never a toggle that pretends a Guided view exists.

Honesty rules encoded here:

* a block ``short`` may omit detail but can only be authored, never synthesised from ``deep``;
* media is attached to a block by a documented deterministic rule because the v7 page recorded
  media at document level; a media row whose artifact is unknown is preserved as text, not
  relabelled with a guessed kind;
* source ids travel with the block that cites them (``lesson_segments.source_id``); a v7 page
  recorded provenance only at document level, so the projection says so by attaching none at
  block level and preserving the page's list at document level;
* the document never contains a reference answer, accepted answers or rubric text, and the
  validator rejects a document that does.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "SCHEMA_VERSION",
    "BLOCK_ROLES",
    "MEDIA_KINDS",
    "MEDIA_ROLES",
    "DOCUMENT_STATES",
    "LessonDocumentError",
    "canonical",
    "narrative_text",
    "answer_material",
    "leaks_answer",
    "validate_blocks",
    "validate_document",
    "document_from_page",
    "document_from_segments",
    "document_from_blocks",
]

#: Bumped only with a cb.rpc contract change. The document is storage-neutral: no column.
SCHEMA_VERSION = 1

#: Structural roles. A role describes where a block sits in the teaching sequence, never a skin
#: and never a difficulty claim.
BLOCK_ROLES = ("orient", "explain", "example", "practice", "recap")
MEDIA_KINDS = ("visual", "audio")
MEDIA_ROLES = ("illustration", "schematic", "sourced_technical", "narration")

#: ``complete`` = every block has authored short + deep text. ``textbook_only`` = projected from
#: the older segment shape (deep only). ``empty`` = the section has no teaching content yet.
DOCUMENT_STATES = ("complete", "textbook_only", "empty")

MAX_BLOCKS = 500
MAX_MEDIA_PER_BLOCK = 8
MAX_DOCUMENT_SOURCE_IDS = 200
MAX_BLOCK_SOURCE_IDS = 8
MAX_HEADLINE = 300
MAX_SHORT = 2000
MAX_DEEP = 8000
MAX_PURPOSE = 200
MAX_TEXT_EQUIVALENT = 1200
MAX_LABEL = 200
MAX_REASON = 300

BLOCK_FIELDS = ("id", "role", "headline", "short", "deep", "check_id", "media", "source_ids")
MEDIA_FIELDS = ("kind", "role", "artifact_id", "purpose", "text_equivalent", "label", "degraded", "reason")

DOCUMENT_FIELDS = (
    "schema_version",
    "document_id",
    "content_hash",
    "section_title",
    "objective_id",
    "state",
    "view_note",
    "views",
    "blocks",
    "check_id",
    "source_ids",
)
VIEW_FIELDS = ("textbook", "guided", "field_quest", "field_notes")

#: Keys that carry answer material. The projection is built from an allowlist, and the validator
#: re-checks the result, so a stored page that smuggled one in cannot reach a learner.
FORBIDDEN_DOCUMENT_KEYS = frozenset(
    {"reference_answer", "accepted_answers", "accepted_alternatives", "rubric", "reference"}
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")

#: ``lesson.page`` segment kinds that carry authored teaching prose, and the block role each one
#: projects to. ``teaching`` is the pack/chat/turn kind; the other four are lesson-prompt kinds.
_PAGE_SEGMENT_ROLE = {
    "model": "example",
    "explain": "explain",
    "guided": "practice",
    "retrieval": "recap",
}
_TEACHING_KINDS = ("model", "explain", "guided", "retrieval", "teaching")

_VIEW_NOTE_TEXTBOOK_ONLY = (
    "This lesson was authored before the block document existed, so it has no short-text or "
    "sequenced view. Textbook view only."
)
_VIEW_NOTE_EMPTY = "This section has no teaching content yet."

#: Fixed structural labels used where the older storage recorded no heading. They are labels,
#: not titles: no string slice of the teaching text is ever presented as a heading.
_LABEL_FOR_ROLE = {
    "orient": "Lesson",
    "explain": "Lesson",
    "example": "Example",
    "practice": "Practice",
    "recap": "Recap",
}
_MEDIA_LABEL = "Media"
_CHECK_LABEL = "Check"


class LessonDocumentError(ValueError):
    """A document or block list violates the v8 shape. Carries every problem, not the first."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "invalid lesson document")


def canonical(value: Any) -> str:
    """Stable JSON, so a content hash is a fact about the document rather than about key order."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.match(value))


def _unique(values: Iterable[Any], *, limit: int = MAX_DOCUMENT_SOURCE_IDS) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = _clean(value)
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= limit:
            break
    return seen


def _media_child(
    *,
    kind: Any,
    role: Any,
    artifact_id: Any,
    purpose: Any,
    text_equivalent: Any,
    label: Any = None,
    degraded: Any = False,
    reason: Any = None,
) -> dict[str, Any]:
    return {
        "kind": kind if kind in MEDIA_KINDS else None,
        "role": role if role in MEDIA_ROLES else None,
        "artifact_id": artifact_id if _identifier(artifact_id) else None,
        "purpose": _clean(purpose),
        "text_equivalent": _clean(text_equivalent),
        "label": (_clean(label) or None),
        "degraded": bool(degraded),
        "reason": (_clean(reason) or None),
    }


def _block(
    *,
    index: int,
    role: str,
    headline: str,
    short: str | None,
    deep: str,
    media: Sequence[dict[str, Any]] | None = None,
    source_ids: Sequence[Any] | None = None,
    block_id: Any = None,
    check_id: Any = None,
) -> dict[str, Any]:
    """One block with a deterministic, content-derived id.

    The id is derived from position, role and text so re-projecting the same page twice returns
    byte-identical output. A document id that changed per read would make a view's cursor and a
    review hash meaningless. An authored block may supply its own identifier; the projector never
    does.
    """
    digest = hashlib.sha256(
        canonical([index, role, headline, short, deep]).encode("utf-8")
    ).hexdigest()
    return {
        "id": block_id if _identifier(block_id) else f"blk_{digest[:20]}",
        "role": role,
        "headline": headline,
        "short": short,
        "deep": deep,
        "check_id": check_id if _identifier(check_id) else None,
        "media": list(media or [])[:MAX_MEDIA_PER_BLOCK],
        "source_ids": _unique(source_ids or [], limit=MAX_BLOCK_SOURCE_IDS),
    }


def _state_and_views(blocks: Sequence[Mapping[str, Any]], check_id: str | None) -> tuple[str, dict[str, bool], str | None]:
    if not blocks:
        return "empty", {"textbook": False, "guided": False, "field_quest": False, "field_notes": False}, _VIEW_NOTE_EMPTY
    complete = all(bool(_clean(block.get("short"))) for block in blocks)
    views = {
        "textbook": True,
        "guided": complete,
        "field_quest": complete and bool(check_id),
        "field_notes": complete,
    }
    if complete:
        return "complete", views, None
    return "textbook_only", views, _VIEW_NOTE_TEXTBOOK_ONLY


def _attach_check(blocks: Sequence[dict[str, Any]], check_id: str | None) -> str | None:
    """Attach the one check to exactly one block.

    Rule: the first ``practice`` block; when the page has no practice block, the final block —
    the page's terminal teaching position. The check is never duplicated across blocks and never
    duplicated across views, so an attempt can only ever be opened against one block.
    """
    if not check_id or not blocks:
        return None
    claimed = [block["check_id"] for block in blocks if block["check_id"]]
    if claimed:
        # An authored claim is preserved so the validator can judge it; overriding it here would
        # silently move a check the author attached, and two claims must be rejected, not merged.
        return claimed[0]
    for block in blocks:
        if block["role"] == "practice":
            block["check_id"] = check_id
            return check_id
    blocks[-1]["check_id"] = check_id
    return check_id


def _attach_media(blocks: Sequence[dict[str, Any]], media: Sequence[dict[str, Any]]) -> None:
    """Attach document-level media to blocks by a documented structural rule.

    The v7 page stored media at document level, so the projection has to choose. Narration belongs
    with the block the learner produces the phrase in (practice, else the last block); a visual
    belongs with the example, else the explanation, else the first block. This is placement, not
    a claim: the media child keeps its authored kind, role, purpose and text equivalent.
    """
    for item in media:
        if item["kind"] == "audio" or item["role"] == "narration":
            owner = next((b for b in blocks if b["role"] == "practice"), blocks[-1])
        else:
            owner = next((b for b in blocks if b["role"] == "example"), None)
            if owner is None:
                owner = next((b for b in blocks if b["role"] == "explain"), None)
            if owner is None:
                owner = blocks[0]
        if len(owner["media"]) < MAX_MEDIA_PER_BLOCK:
            owner["media"].append(item)


def _page_segment_blocks(page: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for segment in page.get("segments") or []:
        if not isinstance(segment, Mapping):
            continue
        kind = _clean(segment.get("kind"))
        if kind not in _PAGE_SEGMENT_ROLE:
            continue
        deep = _clean(segment.get("body"))
        if not deep:
            continue
        blocks.append(
            _block(
                index=len(blocks),
                role=_PAGE_SEGMENT_ROLE[kind],
                headline=_clean(segment.get("heading"))[:_HEADLINE_LIMIT] or _LABEL_FOR_ROLE[_PAGE_SEGMENT_ROLE[kind]],
                short=None,
                deep=deep,
            )
        )
    example = page.get("worked_example")
    if isinstance(example, Mapping) and _clean(example.get("prompt")):
        steps = [_clean(step) for step in example.get("steps") or [] if _clean(step)]
        answer = _clean(example.get("answer"))
        body = "\n".join(steps + ([f"Answer: {answer}"] if answer else []))
        if body:
            blocks.append(
                _block(
                    index=len(blocks),
                    role="example",
                    headline=_clean(example.get("prompt"))[:MAX_HEADLINE],
                    short=None,
                    deep=body,
                )
            )
    explanation = _clean(page.get("learner_explanation"))
    if explanation:
        blocks.append(
            _block(
                index=len(blocks),
                role="recap",
                headline="Recap",
                short=None,
                deep=explanation,
            )
        )
    media = [_page_media_child(item) for item in page.get("media") or [] if isinstance(item, Mapping)]
    if media and not blocks:
        # Media is a child of a block, never a free-floating gallery item. With no teaching prose
        # the media's own text equivalent is the only authored text, so it becomes the block body.
        blocks.append(
            _block(
                index=0,
                role="example",
                headline=_MEDIA_LABEL,
                short=None,
                deep=media[0]["text_equivalent"] or media[0]["purpose"] or _MEDIA_LABEL,
                media=media[:1],
            )
        )
        media = media[1:]
    if media:
        _attach_media(blocks, media)
    return blocks


_HEADLINE_LIMIT = MAX_HEADLINE


def _page_media_child(item: Mapping[str, Any]) -> dict[str, Any]:
    kind = _clean(item.get("kind"))
    return _media_child(
        kind=kind if kind in MEDIA_KINDS else None,
        role=_clean(item.get("role")) or None,
        artifact_id=item.get("artifact_id"),
        purpose=item.get("purpose") or item.get("text_equivalent") or _MEDIA_LABEL,
        text_equivalent=item.get("text_equivalent") or item.get("purpose") or _MEDIA_LABEL,
        label=item.get("label"),
        degraded=item.get("degraded"),
        reason=item.get("reason"),
    )


def _authored_blocks(raw_blocks: Sequence[Any]) -> list[dict[str, Any]]:
    """Normalise blocks authored directly (the v8 path) without inventing content."""
    blocks: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, raw in enumerate(raw_blocks or []):
        if not isinstance(raw, Mapping):
            problems.append(f"blocks[{index}] is not an object")
            continue
        unknown = set(raw) - set(BLOCK_FIELDS)
        if unknown:
            problems.append(f"blocks[{index}] has unknown field(s): {', '.join(sorted(unknown))}")
        role = _clean(raw.get("role"))
        deep = _clean(raw.get("deep"))
        short = raw.get("short")
        blocks.append(
            _block(
                index=index,
                role=role if role in BLOCK_ROLES else role,
                headline=_clean(raw.get("headline"))[:MAX_HEADLINE] or _LABEL_FOR_ROLE.get(role, "Lesson"),
                short=(str(short).strip() if isinstance(short, str) and short.strip() else None),
                deep=deep,
                media=[_authored_media_child(item, index) for item in raw.get("media") or [] if isinstance(item, Mapping)],
                source_ids=raw.get("source_ids") or [],
                block_id=raw.get("id"),
                check_id=raw.get("check_id"),
            )
        )
    if problems:
        raise LessonDocumentError(problems)
    return blocks


def _authored_media_child(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise LessonDocumentError([f"blocks[{index}].media entry is not an object"])
    return _media_child(
        kind=_clean(item.get("kind")) or None,
        role=_clean(item.get("role")) or None,
        artifact_id=item.get("artifact_id"),
        purpose=item.get("purpose") or item.get("text_equivalent") or _MEDIA_LABEL,
        text_equivalent=item.get("text_equivalent") or item.get("purpose") or _MEDIA_LABEL,
        label=item.get("label"),
        degraded=item.get("degraded"),
        reason=item.get("reason"),
    )


def _finish(
    *,
    section_title: str,
    objective_id: str | None,
    blocks: list[dict[str, Any]],
    check_id: str | None,
    source_ids: Sequence[Any],
) -> dict[str, Any]:
    attached = _attach_check(blocks, check_id)
    document_source_ids = _unique(source_ids, limit=MAX_DOCUMENT_SOURCE_IDS)
    for block in blocks:
        for source_id in block["source_ids"]:
            if source_id not in document_source_ids and len(document_source_ids) < MAX_DOCUMENT_SOURCE_IDS:
                document_source_ids.append(source_id)
    state, views, note = _state_and_views(blocks, attached)
    core = {
        "schema_version": SCHEMA_VERSION,
        "section_title": section_title,
        "objective_id": objective_id if _identifier(objective_id) else None,
        "check_id": attached,
        "source_ids": document_source_ids,
        "blocks": blocks,
    }
    digest = hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()
    document = {
        "schema_version": SCHEMA_VERSION,
        "document_id": f"doc_{digest[:20]}",
        "content_hash": f"sha256:{digest}",
        "section_title": core["section_title"],
        "objective_id": core["objective_id"],
        "state": state,
        "view_note": note,
        "views": views,
        "blocks": blocks,
        "check_id": attached,
        "source_ids": document_source_ids,
    }
    problems = _document_problems(document)
    if problems:
        raise LessonDocumentError(problems)
    return document


def document_from_page(page: Mapping[str, Any], *, check_id: str | None = None) -> dict[str, Any]:
    """Project a stored ``gen_lessons.page_json`` into a document.

    Deterministic and read-only: the same page and check id always produce the same document id
    and content hash. A page that already carries an authored ``document``/``blocks`` array is
    validated and used; every older page is projected from its validated segments.
    """
    if not isinstance(page, Mapping):
        raise LessonDocumentError(["page must be an object"])
    section_title = _clean(page.get("section_title")) or "Lesson"
    source_ids = _unique(
        entry.get("source_id") for entry in page.get("sources") or [] if isinstance(entry, Mapping)
    )
    authored = page.get("document")
    raw_blocks = None
    if isinstance(authored, Mapping):
        raw_blocks = authored.get("blocks")
        source_ids = _unique(list(authored.get("source_ids") or []) + source_ids)
    elif isinstance(page.get("blocks"), list):
        raw_blocks = page.get("blocks")
    if raw_blocks is not None:
        blocks = _authored_blocks(raw_blocks)
        objective_id = authored.get("objective_id") if isinstance(authored, Mapping) else page.get("objective_id")
    else:
        blocks = _page_segment_blocks(page)
        objective_id = page.get("objective_id")
    return _finish(
        section_title=section_title,
        objective_id=objective_id,
        blocks=blocks,
        check_id=check_id,
        source_ids=source_ids,
    )


def document_from_segments(
    segments: Sequence[Mapping[str, Any]],
    *,
    section_title: str,
    objective_id: str | None = None,
    check_id: str | None = None,
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    source_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Project durable ``lesson_segments`` rows (the ``lesson.page`` shape) into a document.

    Older rows carry no heading and no short text, so every block keeps ``short = null`` and the
    document reports ``textbook_only``. Teaching roles are positional (first ``orient``, last
    ``recap``, middle ``explain``); a ``check_prompt`` segment becomes the ``practice`` block the
    check attaches to; a ``media`` segment becomes a media child of the preceding block. A media
    segment whose artifact row is unknown is preserved as an ``example`` block's text instead of
    being labelled with a guessed kind.
    """
    rows = [row for row in segments or [] if isinstance(row, Mapping)]
    teaching_count = sum(1 for row in rows if _clean(row.get("kind")) == "teaching")
    artifact_index = artifacts or {}
    blocks: list[dict[str, Any]] = []
    pending_media: list[dict[str, Any]] = []
    seen_teaching = 0
    for row in rows:
        kind = _clean(row.get("kind"))
        text = _clean(row.get("text"))
        if kind == "teaching":
            if not text:
                continue
            seen_teaching += 1
            if seen_teaching == 1:
                role = "orient"
            elif seen_teaching == teaching_count:
                role = "recap"
            else:
                role = "explain"
            blocks.append(
                _block(
                    index=len(blocks),
                    role=role,
                    headline=_LABEL_FOR_ROLE[role],
                    short=None,
                    deep=text,
                    source_ids=[row.get("source_id")] if row.get("source_id") else [],
                )
            )
            if pending_media:
                _attach_media(blocks[-1:], pending_media)
                pending_media = []
        elif kind == "check_prompt":
            if not text:
                continue
            blocks.append(
                _block(
                    index=len(blocks),
                    role="practice",
                    headline=_CHECK_LABEL,
                    short=None,
                    deep=text,
                    source_ids=[row.get("source_id")] if row.get("source_id") else [],
                )
            )
        elif kind == "media":
            artifact_id = row.get("artifact_id")
            artifact = artifact_index.get(str(artifact_id)) if artifact_id else None
            media_kind = _clean((artifact or {}).get("kind")) or None
            if media_kind not in MEDIA_KINDS:
                mime = _clean((artifact or {}).get("mime"))
                media_kind = "audio" if mime.startswith("audio/") else ("visual" if mime.startswith("image/") else None)
            if media_kind is None:
                # No artifact row and no trustworthy MIME: keep the authored text as prose rather
                # than invent a media kind for a child the Desktop might try to fetch.
                blocks.append(
                    _block(
                        index=len(blocks),
                        role="example",
                        headline=_MEDIA_LABEL,
                        short=None,
                        deep=text or _MEDIA_LABEL,
                        source_ids=[row.get("source_id")] if row.get("source_id") else [],
                    )
                )
                continue
            child = _media_child(
                kind=media_kind,
                role=None,
                artifact_id=artifact_id,
                purpose=text or _MEDIA_LABEL,
                text_equivalent=text or _MEDIA_LABEL,
                label=None,
            )
            if blocks:
                _attach_media(blocks[-1:], [child])
            else:
                pending_media.append(child)
    if pending_media:
        if not blocks:
            first = pending_media.pop(0)
            blocks.append(
                _block(
                    index=0,
                    role="example",
                    headline=_MEDIA_LABEL,
                    short=None,
                    deep=first["text_equivalent"] or first["purpose"],
                    media=[first],
                )
            )
        if pending_media:
            _attach_media(blocks, pending_media)
    return _finish(
        section_title=_clean(section_title) or "Lesson",
        objective_id=objective_id,
        blocks=blocks,
        check_id=check_id,
        source_ids=list(source_ids or []),
    )


def document_from_blocks(
    blocks: Sequence[Mapping[str, Any]],
    *,
    section_title: str,
    objective_id: str | None = None,
    check_id: str | None = None,
    source_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Validate and build a document from blocks authored directly (the v8 path)."""
    return _finish(
        section_title=_clean(section_title) or "Lesson",
        objective_id=objective_id,
        blocks=_authored_blocks(blocks),
        check_id=check_id,
        source_ids=list(source_ids or []),
    )


def narrative_text(document: Mapping[str, Any]) -> str:
    """Every learner-facing string in the document, normalised for answer matching."""
    parts: list[str] = [str(document.get("section_title") or "")]
    for block in document.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        parts.append(str(block.get("headline") or ""))
        parts.append(str(block.get("short") or ""))
        parts.append(str(block.get("deep") or ""))
        for item in block.get("media") or []:
            if isinstance(item, Mapping):
                parts.append(str(item.get("purpose") or ""))
                parts.append(str(item.get("text_equivalent") or ""))
                parts.append(str(item.get("label") or ""))
    return _normalize("\n".join(parts))


def leaks_answer(document: Mapping[str, Any], secrets: Iterable[Any]) -> list[str]:
    """Return the secrets that appear in the document's learner-facing narrative."""
    text = narrative_text(document)
    return [str(secret) for secret in secrets if _clean(secret) and _normalize(str(secret)) in text]


def answer_material(value: Any) -> list[str]:
    """Forbidden answer-bearing keys anywhere in a document object."""
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_DOCUMENT_KEYS:
                found.append(str(key))
            found.extend(answer_material(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(answer_material(child))
    return found


# ── validation ──────────────────────────────────────────────────────────────


def _block_problems(block: Any, index: int) -> list[str]:
    where = f"blocks[{index}]"
    if not isinstance(block, Mapping):
        return [f"{where} is not an object"]
    problems: list[str] = []
    unknown = set(block) - set(BLOCK_FIELDS)
    if unknown:
        problems.append(f"{where} has unknown field(s): {', '.join(sorted(unknown))}")
    missing = [field for field in BLOCK_FIELDS if field not in block]
    if missing:
        problems.append(f"{where} is missing {', '.join(missing)}")
        return problems
    if not _identifier(block.get("id")):
        problems.append(f"{where}.id is not a Coursebook identifier")
    if block.get("role") not in BLOCK_ROLES:
        problems.append(f"{where}.role {block.get('role')!r} is not one of {', '.join(BLOCK_ROLES)}")
    headline = block.get("headline")
    if not isinstance(headline, str) or not _clean(headline):
        problems.append(f"{where}.headline is empty")
    elif len(headline) > MAX_HEADLINE:
        problems.append(f"{where}.headline exceeds {MAX_HEADLINE} characters")
    deep = block.get("deep")
    if not isinstance(deep, str) or not _clean(deep):
        problems.append(f"{where}.deep is empty")
    elif len(deep) > MAX_DEEP:
        problems.append(f"{where}.deep exceeds {MAX_DEEP} characters")
    short = block.get("short")
    if short is not None:
        if not isinstance(short, str) or not _clean(short):
            problems.append(f"{where}.short must be null or non-empty text")
        elif len(short) > MAX_SHORT:
            problems.append(f"{where}.short exceeds {MAX_SHORT} characters")
    check_id = block.get("check_id")
    if check_id is not None and not _identifier(check_id):
        problems.append(f"{where}.check_id is not an identifier")
    media = block.get("media")
    if not isinstance(media, list):
        problems.append(f"{where}.media is not an array")
    elif len(media) > MAX_MEDIA_PER_BLOCK:
        problems.append(f"{where}.media exceeds {MAX_MEDIA_PER_BLOCK} items")
    else:
        for media_index, item in enumerate(media):
            problems.extend(_media_problems(item, f"{where}.media[{media_index}]"))
    source_ids = block.get("source_ids")
    if not isinstance(source_ids, list):
        problems.append(f"{where}.source_ids is not an array")
    elif len(source_ids) > MAX_BLOCK_SOURCE_IDS:
        problems.append(f"{where}.source_ids exceeds {MAX_BLOCK_SOURCE_IDS} ids")
    else:
        if len(set(source_ids)) != len(source_ids):
            problems.append(f"{where}.source_ids contains duplicates")
        for source_id in source_ids:
            if not _identifier(source_id):
                problems.append(f"{where}.source_ids entry {source_id!r} is not an identifier")
    return problems


def _media_problems(item: Any, where: str) -> list[str]:
    if not isinstance(item, Mapping):
        return [f"{where} is not an object"]
    problems: list[str] = []
    unknown = set(item) - set(MEDIA_FIELDS)
    if unknown:
        problems.append(f"{where} has unknown field(s): {', '.join(sorted(unknown))}")
    missing = [field for field in MEDIA_FIELDS if field not in item]
    if missing:
        problems.append(f"{where} is missing {', '.join(missing)}")
        return problems
    if item.get("kind") not in MEDIA_KINDS:
        problems.append(f"{where}.kind {item.get('kind')!r} is not one of {', '.join(MEDIA_KINDS)}")
    if item.get("role") is not None and item.get("role") not in MEDIA_ROLES:
        problems.append(f"{where}.role {item.get('role')!r} is not a media role")
    artifact_id = item.get("artifact_id")
    if artifact_id is not None and not _identifier(artifact_id):
        problems.append(f"{where}.artifact_id is not an identifier")
    purpose = item.get("purpose")
    if not isinstance(purpose, str) or not _clean(purpose):
        problems.append(f"{where}.purpose is empty")
    elif len(purpose) > MAX_PURPOSE:
        problems.append(f"{where}.purpose exceeds {MAX_PURPOSE} characters")
    equivalent = item.get("text_equivalent")
    if not isinstance(equivalent, str) or not _clean(equivalent):
        problems.append(f"{where}.text_equivalent is empty")
    elif len(equivalent) > MAX_TEXT_EQUIVALENT:
        problems.append(f"{where}.text_equivalent exceeds {MAX_TEXT_EQUIVALENT} characters")
    label = item.get("label")
    if label is not None and (not isinstance(label, str) or not _clean(label)):
        problems.append(f"{where}.label must be null or non-empty text")
    elif isinstance(label, str) and len(label) > MAX_LABEL:
        problems.append(f"{where}.label exceeds {MAX_LABEL} characters")
    if not isinstance(item.get("degraded"), bool):
        problems.append(f"{where}.degraded is not a boolean")
    reason = item.get("reason")
    if reason is not None and not isinstance(reason, str):
        problems.append(f"{where}.reason must be null or text")
    elif isinstance(reason, str) and len(reason) > MAX_REASON:
        problems.append(f"{where}.reason exceeds {MAX_REASON} characters")
    return problems


def _block_list_problems(blocks: Any, check_id: str | None) -> list[str]:
    if not isinstance(blocks, list):
        return ["blocks is not an array"]
    problems: list[str] = []
    if len(blocks) > MAX_BLOCKS:
        problems.append(f"blocks exceeds {MAX_BLOCKS} items")
    seen: set[str] = set()
    claimed = 0
    for index, block in enumerate(blocks):
        problems.extend(_block_problems(block, index))
        if not isinstance(block, Mapping):
            continue
        block_id = block.get("id")
        if isinstance(block_id, str):
            if block_id in seen:
                problems.append(f"duplicate block id {block_id!r}")
            seen.add(block_id)
        claimed_id = block.get("check_id")
        if claimed_id is not None:
            claimed += 1
            if claimed_id != check_id:
                problems.append(
                    f"blocks[{index}].check_id {claimed_id!r} is not the document check {check_id!r}"
                )
    if claimed > 1:
        problems.append(f"{claimed} blocks claim a check; one check attaches to exactly one block")
    if check_id is not None and claimed == 0 and blocks:
        problems.append("the document has a check but no block carries it")
    return problems


def validate_blocks(blocks: Any, *, check_id: str | None = None) -> None:
    """Raise :class:`LessonDocumentError` when a block list is not a valid document body."""
    problems = _block_list_problems(blocks, check_id)
    if problems:
        raise LessonDocumentError(problems)


def _document_problems(document: Any) -> list[str]:
    if not isinstance(document, Mapping):
        return ["document is not an object"]
    problems: list[str] = []
    unknown = set(document) - set(DOCUMENT_FIELDS)
    if unknown:
        problems.append(f"document has unknown field(s): {', '.join(sorted(unknown))}")
    missing = [field for field in DOCUMENT_FIELDS if field not in document]
    if missing:
        return problems + [f"document is missing {', '.join(missing)}"]
    if document.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    if not _identifier(document.get("document_id")):
        problems.append("document_id is not an identifier")
    if not isinstance(document.get("section_title"), str) or not _clean(document.get("section_title")):
        problems.append("section_title is empty")
    objective_id = document.get("objective_id")
    if objective_id is not None and not _identifier(objective_id):
        problems.append("objective_id is not an identifier")
    check_id = document.get("check_id")
    if check_id is not None and not _identifier(check_id):
        problems.append("check_id is not an identifier")
    blocks = document.get("blocks")
    problems.extend(_block_list_problems(blocks, check_id))
    source_ids = document.get("source_ids")
    if not isinstance(source_ids, list) or len(source_ids) > MAX_DOCUMENT_SOURCE_IDS:
        problems.append("source_ids is not a bounded array")
    else:
        for source_id in source_ids:
            if not _identifier(source_id):
                problems.append(f"source_ids entry {source_id!r} is not an identifier")
    if isinstance(blocks, list):
        block_sources = {
            source_id
            for block in blocks
            if isinstance(block, Mapping)
            for source_id in (block.get("source_ids") or [])
        }
        if isinstance(source_ids, list):
            missing_sources = block_sources - set(source_ids)
            if missing_sources:
                problems.append(
                    "document.source_ids is missing block source(s): "
                    + ", ".join(sorted(str(item) for item in missing_sources))
                )
    views = document.get("views")
    if not isinstance(views, Mapping) or set(views) != set(VIEW_FIELDS):
        problems.append("views must name exactly textbook, guided, field_quest, field_notes")
    elif not all(isinstance(value, bool) for value in views.values()):
        problems.append("views values must be booleans")
    if document.get("state") not in DOCUMENT_STATES:
        problems.append(f"state {document.get('state')!r} is not a document state")
    elif isinstance(blocks, list) and all(isinstance(block, Mapping) for block in blocks):
        expected_state, expected_views, _note = _state_and_views(blocks, check_id)
        if document.get("state") != expected_state:
            problems.append(f"state {document.get('state')!r} disagrees with the blocks ({expected_state})")
        if isinstance(views, Mapping) and dict(views) != expected_views:
            problems.append("views disagree with the blocks")
    note = document.get("view_note")
    if note is not None and not isinstance(note, str):
        problems.append("view_note must be null or text")
    if isinstance(blocks, list) and all(isinstance(block, Mapping) for block in blocks):
        expected_hash = _document_hash(document)
        if document.get("content_hash") != expected_hash:
            problems.append("content_hash does not match the document content")
        if document.get("document_id") != f"doc_{expected_hash.split(':', 1)[1][:20]}":
            problems.append("document_id does not match the content hash")
    return problems


def _document_hash(document: Mapping[str, Any]) -> str:
    core = {
        "schema_version": SCHEMA_VERSION,
        "section_title": document.get("section_title"),
        "objective_id": document.get("objective_id"),
        "check_id": document.get("check_id"),
        "source_ids": list(document.get("source_ids") or []),
        "blocks": list(document.get("blocks") or []),
    }
    return "sha256:" + hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def validate_document(document: Any) -> None:
    """Raise :class:`LessonDocumentError` when a document breaks the v8 shape or honesty rules."""
    problems = _document_problems(document)
    if problems:
        raise LessonDocumentError(problems)
