"""Lesson-page segment sizing: the frozen ``cb.rpc`` cap and how stored text is cut to fit it.

A lesson page returns ``segments[].text``; ``cb.rpc`` v6 caps one segment at 8,000 characters and
one page at 500 segments. The pack manifest, meanwhile, allows a section file of up to 32 MB. Those
two numbers were never reconciled: :func:`coursebook.pack_flow._write_lesson_page` stored a whole
section file as *one* teaching segment, so a pack with a long chapter imported successfully and then
every ``lesson.page`` for that objective returned ``INTERNAL_ERROR`` at ``segments/0/text`` — a
permanent, unretryable unreadable section (release-gate defect D1).

This module owns the one rule that closes it:

* text longer than the cap is **cut into ordered pieces at semantic boundaries** — paragraph first,
  then line, then word, never inside a fenced code block — and the pieces concatenate back to the
  original string exactly (no character is added, dropped or rewritten);
* a pack whose lesson would need more segments than the page allows is **refused before any
  database write**, naming the file, its measured length and the cap;
* stored text already over the cap is **repaired once**, in place, without a re-import, so a course
  imported before this fix becomes readable.

The cap and the page budget come from the contract, never from a second hardcoded copy.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from functools import lru_cache
from typing import Any, Mapping, Sequence

from .contracts import contract

_HEADING = re.compile(r"^ {0,3}#{1,6}\s")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@lru_cache(maxsize=1)
def lesson_page_caps() -> tuple[int, int]:
    """``(max characters per segment, max segments per page)`` read from ``cb.rpc``.

    Raises :class:`coursebook.contracts.ContractError` when the contract no longer carries those
    bounds, because then this build cannot know what a readable page is.
    """
    from .contracts import ContractError

    try:
        response = contract("cb.rpc")["$defs"]["methods"]["properties"]["lesson.page"]["response"]
        segments = response["properties"]["segments"]
    except (KeyError, TypeError) as exc:  # pragma: no cover - contract drift
        raise ContractError(
            "cb.rpc lesson.page response no longer declares a segments array",
            contract_id="cb.rpc",
            path="lesson.page.response.segments",
        ) from exc
    try:
        return int(segments["items"]["properties"]["text"]["maxLength"]), int(segments["maxItems"])
    except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - contract drift
        raise ContractError(
            "cb.rpc lesson.page segments must declare text.maxLength and maxItems",
            contract_id="cb.rpc",
            path="lesson.page.response.segments.items.properties.text.maxLength",
        ) from exc


def max_segment_chars() -> int:
    return lesson_page_caps()[0]


def max_segments_per_page() -> int:
    return lesson_page_caps()[1]


def lesson_section_char_bound() -> int:
    """Characters one lesson section may hold before it can never render on one lesson page.

    Derived, never a second constant: the product of the contract's per-segment character cap and
    its per-page segment budget (8,000 x 500 = 4,000,000 at ``cb.rpc`` v7). The page budget also
    carries the objective's check prompts, so import's own refusal can sit below this number; this
    is the absolute ceiling for a single section, and the authoring warning names it.
    """
    limit, budget = lesson_page_caps()
    return limit * budget


def declared_section_paths(manifest: Mapping[str, Any]) -> list[str]:
    """Every file path an objective declares as a ``sections[]`` entry, in manifest order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for objective in manifest.get("objectives") or []:
        for section in objective.get("sections") or []:
            path = str(section.get("path") or "")
            if path and path not in seen:
                seen.add(path)
                ordered.append(path)
    return ordered


def authoring_warnings(manifest: Mapping[str, Any], texts: Mapping[str, str]) -> list[str]:
    """Non-blocking warnings for a pack that is contract-valid but cannot be read as authored.

    A lesson section above :func:`lesson_section_char_bound` characters would need more segments
    than one ``lesson.page`` returns, so its tail can never render. Import refuses such a pack
    before any write (:func:`audit_objective_texts`); this function only warns, naming the file and
    its measured length, so an author learns it while the pack is still a draft.
    """
    bound = lesson_section_char_bound()
    limit, budget = lesson_page_caps()
    warnings: list[str] = []
    for path in declared_section_paths(manifest):
        text = texts.get(path)
        if text is None or len(text) <= bound:
            continue
        warnings.append(
            f"section file {path!r} measures {len(text):,} characters, above the "
            f"{bound:,}-character authoring bound for one lesson section (cb.rpc lesson.page "
            f"returns at most {budget:,} segments of {limit:,} characters, so a section of "
            f"{bound:,} characters is the most one page can carry); the page budget also carries "
            "the objective's check prompts, so import may refuse a slightly shorter section. "
            "Import will refuse this pack before writing anything. Split the section into smaller "
            "files."
        )
    return warnings


def _ends_with_heading(piece: str) -> bool:
    for line in reversed(piece.rstrip().splitlines()):
        if line.strip():
            return bool(_HEADING.match(line))
    return False


def _fence_open_at(text: str, cut: int) -> int | None:
    """Offset of the opening fence when ``cut`` falls inside a fenced block, else ``None``."""
    opening: int | None = None
    offset = 0
    for line in text[:cut].splitlines(keepends=True):
        if _FENCE.match(line):
            opening = None if opening is not None else offset
        offset += len(line)
    return opening


def _cut_index(text: str, limit: int) -> int:
    """Where to end the next piece of ``text`` so it is at most ``limit`` characters.

    Preference order: after a blank line (paragraph boundary), after a line, after a word, then a
    hard cut. A candidate is only taken when it keeps the piece at least a third of the limit long;
    otherwise the next, coarser strategy applies. The cut is then moved back out of an open code
    fence and off a trailing heading, in that order, so a piece never ends with a dangling heading
    or half a code block.
    """
    floor = max(1, limit // 3)
    cut = text.rfind("\n\n", 0, limit)
    if cut >= floor:
        cut += 2
    else:
        newline = text.rfind("\n", 0, limit)
        if newline >= floor:
            cut = newline + 1
        else:
            space = text.rfind(" ", 0, limit)
            cut = space + 1 if space >= floor else limit

    fence = _fence_open_at(text, cut)
    if fence is not None and fence >= floor:
        cut = fence
    while _ends_with_heading(text[:cut]):
        earlier = text.rfind("\n\n", 0, cut - 1)
        if earlier < floor:
            break
        cut = earlier + 2
    return max(1, min(cut, limit))


def split_text(text: str, limit: int | None = None) -> list[str]:
    """``text`` as ordered pieces of at most ``limit`` characters; ``"".join(...) == text``."""
    if limit is None:
        limit = max_segment_chars()
    if limit < 1:
        raise ValueError("segment limit must be positive")
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = _cut_index(remaining, limit)
        pieces.append(remaining[:cut])
        remaining = remaining[cut:]
    pieces.append(remaining)
    return pieces


def _new_segment_id() -> str:
    return f"seg_{uuid.uuid4().hex}"


def _section_texts(objective: Mapping[str, Any], root: Any) -> list[tuple[str, str]]:
    """``(declared path, text)`` for every section file of one objective that exists on disk."""
    found: list[tuple[str, str]] = []
    for section in objective.get("sections") or []:
        path = str(section.get("path") or "")
        if not path:
            continue
        candidate = root / path
        if not candidate.is_file():
            continue
        found.append((path, candidate.read_text(encoding="utf-8")))
    return found


def plan_objective(objective: Mapping[str, Any], root: Any) -> list[tuple[str, int, list[str]]]:
    """``(path, characters, pieces)`` per section file — the exact plan import will write."""
    limit = max_segment_chars()
    return [(path, len(text), split_text(text, limit)) for path, text in _section_texts(objective, root)]


def audit_objective_texts(manifest: Mapping[str, Any], root: Any) -> None:
    """Refuse a pack whose lesson page could not be read within the contract.

    Called from :func:`coursebook.pack_flow.validate_and_audit`, i.e. during ``pack.preview`` and
    ``pack.import`` and therefore *before* the first database write. A section longer than the cap
    is fine — it is cut at import. What is refused is a section so long that the lesson would need
    more segments than a page can return (the remainder would silently never render), or a section
    that cannot be cut at all.
    """
    from .archive import PackRejected

    limit, budget = lesson_page_caps()
    for objective in manifest.get("objectives") or []:
        checks = len(objective.get("checks") or [])
        plans = plan_objective(objective, root)
        teaching_segments = 0
        for path, characters, pieces in plans:
            if not pieces:
                raise PackRejected(f"{path!r} holds no readable teaching text")
            teaching_segments += len(pieces)
        needed = teaching_segments + checks
        if needed > budget:
            longest_path, longest_chars = _longest_section(objective, root)
            raise PackRejected(
                f"objective {objective.get('objective_id')!r} needs {needed} lesson segments "
                f"({teaching_segments} teaching from {len(plans)} section file(s) plus {checks} check "
                f"prompt(s)), but a lesson page returns at most {budget}. Longest section file: "
                f"{longest_path!r} at {longest_chars:,} characters (cb.rpc caps one segment at "
                f"{limit:,} characters). Make the section files shorter."
            )


def _longest_section(objective: Mapping[str, Any], root: Any) -> tuple[str, int]:
    texts = _section_texts(objective, root)
    if not texts:
        return ("(no section files)", 0)
    path, text = max(texts, key=lambda item: len(item[1]))
    return path, len(text)


def repair_stored(connection: sqlite3.Connection) -> int:
    """Cut every stored teaching text over the cap in place; return the rows repaired.

    Order is preserved, ids and ``created_at`` are kept for the first piece of a split row, and the
    run's ordinals are renumbered to stay contiguous so the page renders in reading order. Runs on
    the kernel's own fenced transaction; idempotent (a second pass finds nothing over the cap).
    """
    limit = max_segment_chars()
    runs = [
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT lesson_run_id FROM lesson_segments"
            " WHERE kind = 'teaching' AND text IS NOT NULL AND length(text) > ?",
            (limit,),
        )
    ]
    repaired = 0
    for run_id in runs:
        rows = connection.execute(
            "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal, rowid", (run_id,)
        ).fetchall()
        plan: list[tuple[sqlite3.Row, list[str] | None]] = []
        for row in rows:
            text = row["text"]
            if row["kind"] != "teaching" or not text or len(text) <= limit:
                plan.append((row, None))
                continue
            plan.append((row, split_text(text, limit)))
            repaired += 1
        if all(payload is None for _, payload in plan):
            continue
        # Two passes so the UNIQUE (lesson_run_id, ordinal) fence never collides mid-renumber.
        connection.execute(
            "UPDATE lesson_segments SET ordinal = ordinal + 1000000 WHERE lesson_run_id = ?", (run_id,)
        )
        ordinal = 0
        for row, payload in plan:
            if payload is None:
                ordinal += 1
                connection.execute(
                    "UPDATE lesson_segments SET ordinal = ? WHERE id = ?", (ordinal, row["id"])
                )
                continue
            for index, piece in enumerate(payload):
                ordinal += 1
                if index == 0:
                    connection.execute(
                        "UPDATE lesson_segments SET ordinal = ?, text = ? WHERE id = ?",
                        (ordinal, piece, row["id"]),
                    )
                    continue
                connection.execute(
                    "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id,"
                    " source_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        _new_segment_id(),
                        run_id,
                        ordinal,
                        row["kind"],
                        piece,
                        row["artifact_id"],
                        row["source_id"],
                        row["created_at"],
                    ),
                )
    return repaired


def stored_overlong(connection: sqlite3.Connection) -> Sequence[tuple[str, int]]:
    """``(lesson_run_id, length)`` for stored teaching text over the cap — diagnostics only."""
    return [
        (str(row[0]), int(row[1]))
        for row in connection.execute(
            "SELECT lesson_run_id, length(text) FROM lesson_segments"
            " WHERE kind = 'teaching' AND text IS NOT NULL AND length(text) > ?",
            (max_segment_chars(),),
        )
    ]
