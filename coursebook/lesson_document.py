"""The durable lesson document: one validated block list, many presentation views.

``docs/VISUAL_MEDIA_PLAN.md`` §5 replaces the linear segment list with a block document. A block
has a structural ``role``, a ``headline``, a ``short`` and a ``deep`` rendering of the same
authored material, at most one ``check_id`` and ``media[]`` children. Every view (Textbook,
Guided, Field Quest, Field Notes) is a lens over this one document; no view is a second
authority and no view may add a fact.

This module is deliberately **projection-only**. It never writes a row, never calls a provider
and never mints an id that claims new content:

* :func:`document_from_page` projects a stored ``gen_lessons.page_json`` (the older v7 shape:
  ``segments`` + ``worked_example`` + ``learner_explanation`` + ``media``) into blocks. A page
  authored after the guided-writing change also carries a ``short`` beside each ``deep`` field
  (``segments[].short``, ``worked_example.short``, ``learner_explanation_short``); when those are
  present the projection publishes them and the document reaches ``complete``;
* :func:`document_from_segments` projects the durable ``lesson_segments`` rows that
  ``lesson.page`` renders;
* :func:`document_from_blocks` validates blocks that were authored directly (the v8 path), and
  is what makes the ``complete`` state reachable.

Old rows are never rewritten. A page projected from the v7 shapes has ``short = null`` on every
block, so it reports ``state = "textbook_only"`` and ``views.guided = false`` with a human note —
never a toggle that pretends a Guided view exists. A page written by the lesson author after the
guided-writing change stores the authored ``short`` next to each ``deep`` field, so the same
projection publishes both and the document is ``complete``.

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

from . import localization, text_completeness

__all__ = [
    "SCHEMA_VERSION",
    "BLOCK_ROLES",
    "MEDIA_KINDS",
    "MEDIA_ROLES",
    "PROCEDURE_PERMISSIONS",
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
MAX_LANG = 35

BLOCK_FIELDS = ("id", "role", "headline", "short", "deep", "check_id", "media", "source_ids")
MEDIA_FIELDS = ("kind", "role", "artifact_id", "purpose", "text_equivalent", "label", "degraded", "reason")

#: Optional, additive document field (docs/VISUAL_MEDIA_PLAN.md §8). A procedure is a *layout*
#: over the same blocks: it adds a header and an ordered step list that references block ids, so
#: it can never become a second copy of the teaching text or a second check.
PROCEDURE_FIELDS = ("tools", "parts", "hazards", "stop_condition", "steps", "schematic", "source")
PROCEDURE_STEP_FIELDS = ("block_id", "check")
PROCEDURE_SCHEMATIC_FIELDS = ("title", "text_equivalent", "artifact_id", "source_id", "rows")
PROCEDURE_SOURCE_FIELDS = ("source_id", "permission")
PROCEDURE_ROW_FIELDS = ("label", "value", "row")

#: Permission statuses a procedure source card may print. ``unknown`` is refused: a technical
#: procedure is never presented beside a reference whose rights are not established.
PROCEDURE_PERMISSIONS = ("public_domain", "licensed", "linked")

MAX_PROCEDURE_ITEMS = 20
MAX_PROCEDURE_ITEM = 200
MAX_PROCEDURE_HAZARD = 300
MAX_PROCEDURE_STOP = 400
MAX_PROCEDURE_STEPS = 40
MAX_PROCEDURE_CHECK = 300
MAX_PROCEDURE_ROWS = 40
MAX_PROCEDURE_ROW_LABEL = 120
MAX_PROCEDURE_ROW_VALUE = 80

#: Document keys that are optional. They are absent on every non-procedure document, so the
#: procedure layout changes no existing document, its content hash or its id.
#:
#: ``lang`` and ``direction`` are additive (H-18): a document projected from a page that recorded
#: a locale carries a text language and ltr/rtl direction; a page that never recorded one omits
#: both and keeps its old bytes, hash and id. Direction is a property of the text, never of the
#: learner, and it never changes evidence semantics.
OPTIONAL_DOCUMENT_FIELDS = ("procedure", "lang", "direction")

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
_LANG_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")

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
    """Project a stored page into blocks, publishing only shorts the author wrote.

    A v7 page has no ``short`` anywhere, so every block keeps ``short = None``. A page written
    after the guided-writing change carries ``segments[].short``, ``worked_example.short`` and a
    top-level ``learner_explanation_short``; each one is published beside its own ``deep`` text and
    never generated here — this function has no licence to slice or summarise.
    """
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
                short=_clean(segment.get("short")) or None,
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
                    short=_clean(example.get("short")) or None,
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
                short=_clean(page.get("learner_explanation_short")) or None,
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


def _procedure_items(value: Any, field: str, *, max_len: int, problems: list[str]) -> list[str]:
    if not isinstance(value, list):
        problems.append(f"procedure.{field} is not an array")
        return []
    if len(value) > MAX_PROCEDURE_ITEMS:
        problems.append(f"procedure.{field} exceeds {MAX_PROCEDURE_ITEMS} items")
    items: list[str] = []
    for index, entry in enumerate(value[:MAX_PROCEDURE_ITEMS]):
        text = _clean(entry)
        if not text:
            problems.append(f"procedure.{field}[{index}] is empty")
            continue
        if len(text) > max_len:
            problems.append(f"procedure.{field}[{index}] exceeds {max_len} characters")
            continue
        if text not in items:
            items.append(text)
    return items


def _procedure_schematic(value: Any, source_ids: Sequence[str], problems: list[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        problems.append("procedure.schematic is not an object")
        return None
    unknown = set(value) - set(PROCEDURE_SCHEMATIC_FIELDS)
    if unknown:
        problems.append("procedure.schematic has unknown field(s): " + ", ".join(sorted(unknown)))
    title = _clean(value.get("title"))
    if not title:
        problems.append("procedure.schematic.title is empty")
    elif len(title) > MAX_PROCEDURE_ITEM:
        problems.append(f"procedure.schematic.title exceeds {MAX_PROCEDURE_ITEM} characters")
    equivalent = _clean(value.get("text_equivalent"))
    if not equivalent:
        problems.append("procedure.schematic.text_equivalent is empty")
    elif len(equivalent) > MAX_TEXT_EQUIVALENT:
        problems.append(f"procedure.schematic.text_equivalent exceeds {MAX_TEXT_EQUIVALENT} characters")
    artifact_id = value.get("artifact_id")
    if artifact_id is not None and not _identifier(artifact_id):
        problems.append("procedure.schematic.artifact_id is not an identifier")
    source_id = _clean(value.get("source_id"))
    # The structured facts are checked against the source ledger: a schematic may only be shown
    # beside a source the document already cites.
    if not _identifier(source_id):
        problems.append("procedure.schematic.source_id is not an identifier")
    elif source_id not in source_ids:
        problems.append(f"procedure.schematic.source_id {source_id!r} is not a document source")
    raw_rows = value.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        problems.append("procedure.schematic.rows must be a non-empty array of structured facts")
        raw_rows = []
    elif len(raw_rows) > MAX_PROCEDURE_ROWS:
        problems.append(f"procedure.schematic.rows exceeds {MAX_PROCEDURE_ROWS} rows")
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_rows[:MAX_PROCEDURE_ROWS]):
        if not isinstance(entry, Mapping):
            problems.append(f"procedure.schematic.rows[{index}] is not an object")
            continue
        unknown_row = set(entry) - set(PROCEDURE_ROW_FIELDS)
        if unknown_row:
            problems.append(
                f"procedure.schematic.rows[{index}] has unknown field(s): "
                + ", ".join(sorted(unknown_row))
            )
        label = _clean(entry.get("label"))
        val = _clean(entry.get("value"))
        if not label or len(label) > MAX_PROCEDURE_ROW_LABEL:
            problems.append(f"procedure.schematic.rows[{index}].label is empty or too long")
        if not val or len(val) > MAX_PROCEDURE_ROW_VALUE:
            problems.append(f"procedure.schematic.rows[{index}].value is empty or too long")
        try:
            row_number = int(entry.get("row", index))
        except (TypeError, ValueError):
            problems.append(f"procedure.schematic.rows[{index}].row is not an integer")
            row_number = index
        if label and val:
            rows.append({"label": label, "value": val, "row": row_number})
    return {
        "title": title,
        "text_equivalent": equivalent,
        "artifact_id": artifact_id if _identifier(artifact_id) else None,
        "source_id": source_id if _identifier(source_id) else None,
        "rows": rows,
    }


def _procedure(raw: Any, blocks: Sequence[Mapping[str, Any]], source_ids: Sequence[str]) -> dict[str, Any] | None:
    """Normalise an authored procedure header; ``None`` when the document has none.

    A procedure never carries teaching prose or a second check: ``steps`` are ordered references
    to the document's own blocks plus an optional per-step verification cue. The header is the
    only new content, and every fact in it is typed.
    """
    if raw is None:
        return None
    problems: list[str] = []
    if not isinstance(raw, Mapping):
        raise LessonDocumentError(["procedure is not an object"])
    unknown = set(raw) - set(PROCEDURE_FIELDS)
    if unknown:
        problems.append("procedure has unknown field(s): " + ", ".join(sorted(unknown)))
    missing = [field for field in PROCEDURE_FIELDS if field not in raw]
    if missing:
        raise LessonDocumentError(problems + ["procedure is missing " + ", ".join(missing)])
    tools = _procedure_items(raw.get("tools"), "tools", max_len=MAX_PROCEDURE_ITEM, problems=problems)
    parts = _procedure_items(raw.get("parts"), "parts", max_len=MAX_PROCEDURE_ITEM, problems=problems)
    hazards = _procedure_items(raw.get("hazards"), "hazards", max_len=MAX_PROCEDURE_HAZARD, problems=problems)
    if not hazards:
        # The header must name hazards or state explicitly that none apply; silence is not a
        # safety statement.
        problems.append("procedure.hazards must name the hazards or state that none apply")
    stop = _clean(raw.get("stop_condition"))
    if not stop:
        problems.append("procedure.stop_condition is empty")
    elif len(stop) > MAX_PROCEDURE_STOP:
        problems.append(f"procedure.stop_condition exceeds {MAX_PROCEDURE_STOP} characters")

    block_ids = [str(block.get("id")) for block in blocks if isinstance(block, Mapping)]
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        problems.append("procedure.steps must be a non-empty array")
        raw_steps = []
    elif len(raw_steps) > MAX_PROCEDURE_STEPS:
        problems.append(f"procedure.steps exceeds {MAX_PROCEDURE_STEPS} steps")
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_steps[:MAX_PROCEDURE_STEPS]):
        if not isinstance(entry, Mapping):
            problems.append(f"procedure.steps[{index}] is not an object")
            continue
        unknown_step = set(entry) - set(PROCEDURE_STEP_FIELDS)
        if unknown_step:
            problems.append(
                f"procedure.steps[{index}] has unknown field(s): " + ", ".join(sorted(unknown_step))
            )
        block_id = _clean(entry.get("block_id"))
        if not _identifier(block_id):
            problems.append(f"procedure.steps[{index}].block_id is not an identifier")
            continue
        if block_id not in block_ids:
            problems.append(f"procedure.steps[{index}].block_id {block_id!r} is not a document block")
            continue
        if block_id in seen:
            problems.append(f"procedure.steps[{index}] repeats block {block_id!r}")
            continue
        seen.add(block_id)
        check = _clean(entry.get("check")) or None
        if check is not None and len(check) > MAX_PROCEDURE_CHECK:
            problems.append(f"procedure.steps[{index}].check exceeds {MAX_PROCEDURE_CHECK} characters")
        steps.append({"block_id": block_id, "check": check})

    schematic = _procedure_schematic(raw.get("schematic"), source_ids, problems)

    raw_source = raw.get("source")
    source: dict[str, Any] | None = None
    if not isinstance(raw_source, Mapping):
        problems.append("procedure.source is missing; a procedure carries a cited reference")
    else:
        unknown_source = set(raw_source) - set(PROCEDURE_SOURCE_FIELDS)
        if unknown_source:
            problems.append("procedure.source has unknown field(s): " + ", ".join(sorted(unknown_source)))
        source_id = _clean(raw_source.get("source_id"))
        permission = _clean(raw_source.get("permission"))
        if not _identifier(source_id):
            problems.append("procedure.source.source_id is not an identifier")
        elif source_id not in source_ids:
            problems.append(f"procedure.source.source_id {source_id!r} is not a document source")
        if permission not in PROCEDURE_PERMISSIONS:
            problems.append(
                "procedure.source.permission "
                f"{permission!r} is not one of {', '.join(PROCEDURE_PERMISSIONS)}"
            )
        source = {"source_id": source_id, "permission": permission}
    if problems:
        raise LessonDocumentError(problems)
    return {
        "tools": tools,
        "parts": parts,
        "hazards": hazards,
        "stop_condition": stop,
        "steps": steps,
        "schematic": schematic,
        "source": source,
    }


def _finish(
    *,
    section_title: str,
    objective_id: str | None,
    blocks: list[dict[str, Any]],
    check_id: str | None,
    source_ids: Sequence[Any],
    procedure: Any = None,
    lang: Any = None,
    direction: Any = None,
    completeness: bool = True,
) -> dict[str, Any]:
    attached = _attach_check(blocks, check_id)
    document_source_ids = _unique(source_ids, limit=MAX_DOCUMENT_SOURCE_IDS)
    for block in blocks:
        for source_id in block["source_ids"]:
            if source_id not in document_source_ids and len(document_source_ids) < MAX_DOCUMENT_SOURCE_IDS:
                document_source_ids.append(source_id)
    normalised_procedure = _procedure(procedure, blocks, document_source_ids)
    state, views, note = _state_and_views(blocks, attached)
    lang_value = localization.normalize_locale(lang)
    direction_value = localization.direction_for_locale(lang_value)
    if direction is not None:
        if direction not in localization.TEXT_DIRECTIONS:
            raise LessonDocumentError(
                [f"direction {direction!r} is not one of {', '.join(localization.TEXT_DIRECTIONS)}"]
            )
        direction_value = str(direction)
    core = {
        "schema_version": SCHEMA_VERSION,
        "section_title": section_title,
        "objective_id": objective_id if _identifier(objective_id) else None,
        "check_id": attached,
        "source_ids": document_source_ids,
        "blocks": blocks,
    }
    if lang_value is not None:
        core["lang"] = lang_value
    if direction_value is not None:
        core["direction"] = direction_value
    if normalised_procedure is not None:
        core["procedure"] = normalised_procedure
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
    if lang_value is not None:
        document["lang"] = lang_value
    if direction_value is not None:
        document["direction"] = direction_value
    if normalised_procedure is not None:
        document["procedure"] = normalised_procedure
    problems = _document_problems(document, completeness=completeness)
    if problems:
        raise LessonDocumentError(problems)
    return document


def _page_segment_block_count(page: Mapping[str, Any]) -> int:
    """How many blocks ``_page_segment_blocks`` will mint from this page's segments.

    Segment blocks are projected first and in order, so this count is exactly the prefix of the
    block list that a page-level procedure step may reference.
    """
    count = 0
    for segment in page.get("segments") or []:
        if not isinstance(segment, Mapping):
            continue
        if _clean(segment.get("kind")) not in _PAGE_SEGMENT_ROLE:
            continue
        if not _clean(segment.get("body")):
            continue
        count += 1
    return count


def _resolve_page_procedure(
    raw: Any, blocks: Sequence[Mapping[str, Any]], segment_count: int
) -> dict[str, Any] | None:
    """Turn a page-level procedure's segment ordinals into the document's block references.

    The authored lesson knows segment positions, never block ids: ids are content-derived by the
    projector. Resolution is positional and deterministic, and an ordinal that does not name a
    projected teaching block is refused rather than silently dropped.
    """
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise LessonDocumentError(["procedure is not an object"])
    steps = raw.get("steps")
    if not isinstance(steps, list):
        return dict(raw)
    resolved: list[Any] = []
    for index, entry in enumerate(steps):
        if not isinstance(entry, Mapping) or "block_id" in entry or "segment" not in entry:
            resolved.append(dict(entry) if isinstance(entry, Mapping) else entry)
            continue
        segment = entry.get("segment")
        if isinstance(segment, bool) or not isinstance(segment, int):
            raise LessonDocumentError([f"procedure.steps[{index}].segment is not an integer"])
        if segment < 1 or segment > segment_count or segment > len(blocks):
            raise LessonDocumentError(
                [
                    f"procedure.steps[{index}].segment {segment} refers to no projected block"
                    f" (the page projects {segment_count} teaching block(s))"
                ]
            )
        converted: dict[str, Any] = {"block_id": str(blocks[segment - 1]["id"])}
        if entry.get("check") is not None:
            converted["check"] = entry.get("check")
        resolved.append(converted)
    procedure = dict(raw)
    procedure["steps"] = resolved
    return procedure


def document_from_page(
    page: Mapping[str, Any],
    *,
    check_id: str | None = None,
    locale: str | None = None,
    completeness: bool = False,
) -> dict[str, Any]:
    """Project a stored ``gen_lessons.page_json`` into a document.

    Deterministic and read-only: the same page and check id always produce the same document id
    and content hash. A page that already carries an authored ``document``/``blocks`` array is
    validated and used; a page that carries authored ``short`` text beside its segments is
    projected from its segments **with** that text; every older page is projected without it and
    reports ``textbook_only``.

    ``locale`` is the course/brief locale when the caller has it. A page authored after H-18
    records ``lang`` and ``direction`` itself; an older page has neither, so the projection omits
    both (keeping its old hash and id) unless the caller supplies the locale. ``direction`` is
    derived from the text's script, never from a claim about the learner.
    """
    if not isinstance(page, Mapping):
        raise LessonDocumentError(["page must be an object"])
    section_title = _clean(page.get("section_title")) or "Lesson"
    source_ids = _unique(
        entry.get("source_id") for entry in page.get("sources") or [] if isinstance(entry, Mapping)
    )
    authored = page.get("document")
    raw_blocks = None
    procedure = None
    lang = page.get("lang")
    direction = page.get("direction")
    if isinstance(authored, Mapping):
        raw_blocks = authored.get("blocks")
        procedure = authored.get("procedure")
        lang = authored.get("lang") or lang
        direction = authored.get("direction") or direction
        source_ids = _unique(list(authored.get("source_ids") or []) + source_ids)
    elif isinstance(page.get("blocks"), list):
        raw_blocks = page.get("blocks")
        procedure = page.get("procedure")
    if raw_blocks is not None:
        blocks = _authored_blocks(raw_blocks)
        objective_id = authored.get("objective_id") if isinstance(authored, Mapping) else page.get("objective_id")
    else:
        blocks = _page_segment_blocks(page)
        objective_id = page.get("objective_id")
        # A page written by authoring carries segment ordinals; resolve them against the blocks
        # just projected. An older page has no ``procedure`` key and is unchanged.
        procedure = _resolve_page_procedure(
            page.get("procedure"), blocks, _page_segment_block_count(page)
        )
    return _finish(
        section_title=section_title,
        objective_id=objective_id,
        blocks=blocks,
        check_id=check_id,
        source_ids=source_ids,
        procedure=procedure,
        lang=locale or lang,
        direction=direction,
        completeness=completeness,
    )


def document_from_segments(
    segments: Sequence[Mapping[str, Any]],
    *,
    section_title: str,
    objective_id: str | None = None,
    check_id: str | None = None,
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    source_ids: Sequence[Any] | None = None,
    locale: str | None = None,
    completeness: bool = False,
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
        lang=locale,
        completeness=completeness,
    )


def document_from_blocks(
    blocks: Sequence[Mapping[str, Any]],
    *,
    section_title: str,
    objective_id: str | None = None,
    check_id: str | None = None,
    source_ids: Sequence[Any] | None = None,
    procedure: Any = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Validate and build a document from blocks authored directly (the v8 path)."""
    return _finish(
        section_title=_clean(section_title) or "Lesson",
        objective_id=objective_id,
        blocks=_authored_blocks(blocks),
        check_id=check_id,
        source_ids=list(source_ids or []),
        procedure=procedure,
        lang=locale,
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
    procedure = document.get("procedure")
    if isinstance(procedure, Mapping):
        # Every typed procedure string is learner-facing, so answer leakage is checked against it
        # exactly as it is against the prose.
        for field in ("tools", "parts", "hazards"):
            parts.extend(str(item) for item in procedure.get(field) or [])
        parts.append(str(procedure.get("stop_condition") or ""))
        schematic = procedure.get("schematic")
        if isinstance(schematic, Mapping):
            parts.append(str(schematic.get("title") or ""))
            parts.append(str(schematic.get("text_equivalent") or ""))
            for row in schematic.get("rows") or []:
                if isinstance(row, Mapping):
                    parts.append(str(row.get("label") or ""))
                    parts.append(str(row.get("value") or ""))
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


def _block_problems(block: Any, index: int, *, completeness: bool = True) -> list[str]:
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
    elif completeness:
        # A headline is a label, not a sentence: only the structural shapes apply to it.
        problems.extend(
            text_completeness.completeness_problems(
                headline, where=f"{where}.headline", prose=False
            )
        )
    deep = block.get("deep")
    if not isinstance(deep, str) or not _clean(deep):
        problems.append(f"{where}.deep is empty")
    elif len(deep) > MAX_DEEP:
        problems.append(f"{where}.deep exceeds {MAX_DEEP} characters")
    elif completeness:
        # The deep text is the authored body a learner reads. A body that stops mid-sentence is a
        # truncation, not a short lesson: the rule judges the ending, never the size.
        problems.extend(
            text_completeness.completeness_problems(deep, where=f"{where}.deep")
        )
    short = block.get("short")
    if short is not None:
        if not isinstance(short, str) or not _clean(short):
            problems.append(f"{where}.short must be null or non-empty text")
        elif len(short) > MAX_SHORT:
            problems.append(f"{where}.short exceeds {MAX_SHORT} characters")
        elif completeness:
            # The Guided view serves the short on its own, so a clipped short is the same defect
            # in a second surface: D8 recorded exactly this shape.
            problems.extend(
                text_completeness.completeness_problems(short, where=f"{where}.short")
            )
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


def _block_list_problems(blocks: Any, check_id: str | None, *, completeness: bool = True) -> list[str]:
    if not isinstance(blocks, list):
        return ["blocks is not an array"]
    problems: list[str] = []
    if len(blocks) > MAX_BLOCKS:
        problems.append(f"blocks exceeds {MAX_BLOCKS} items")
    seen: set[str] = set()
    claimed = 0
    for index, block in enumerate(blocks):
        problems.extend(_block_problems(block, index, completeness=completeness))
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


def validate_blocks(blocks: Any, *, check_id: str | None = None, completeness: bool = True) -> None:
    """Raise :class:`LessonDocumentError` when a block list is not a valid document body.

    ``completeness`` runs :mod:`coursebook.text_completeness` over the authored ``headline``,
    ``deep`` and ``short``. It is on by default: this is the gate the lesson author calls before
    storing a page, and a body that stops mid-sentence is a provider truncation, not a lesson.
    A caller projecting rows that were written before this rule passes ``completeness=False`` so
    a historical page is never newly refused for text it already stored.
    """
    problems = _block_list_problems(blocks, check_id, completeness=completeness)
    if problems:
        raise LessonDocumentError(problems)


def _document_problems(document: Any, *, completeness: bool = True) -> list[str]:
    if not isinstance(document, Mapping):
        return ["document is not an object"]
    problems: list[str] = []
    unknown = set(document) - set(DOCUMENT_FIELDS) - set(OPTIONAL_DOCUMENT_FIELDS)
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
    problems.extend(_block_list_problems(blocks, check_id, completeness=completeness))
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
    lang = document.get("lang")
    if lang is not None:
        if not isinstance(lang, str) or len(lang) > MAX_LANG or not _LANG_TAG.match(lang):
            problems.append("lang must be a bounded text language tag or absent")
    direction = document.get("direction")
    if direction is not None and direction not in localization.TEXT_DIRECTIONS:
        problems.append(
            f"direction {direction!r} is not one of {', '.join(localization.TEXT_DIRECTIONS)}"
        )
    if document.get("procedure") is not None and isinstance(blocks, list):
        try:
            _procedure(document.get("procedure"), blocks, document.get("source_ids") or [])
        except LessonDocumentError as exc:
            problems.extend(exc.problems)
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
    if document.get("lang") is not None:
        core["lang"] = document.get("lang")
    if document.get("direction") is not None:
        core["direction"] = document.get("direction")
    if document.get("procedure") is not None:
        core["procedure"] = document.get("procedure")
    return "sha256:" + hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def validate_document(document: Any, *, completeness: bool = True) -> None:
    """Raise :class:`LessonDocumentError` when a document breaks the v8 shape or honesty rules."""
    problems = _document_problems(document, completeness=completeness)
    if problems:
        raise LessonDocumentError(problems)
