"""Structural completeness gate for authored teaching text.

A provider truncation does not produce an invalid document: the string is still a non-empty string
of the right shape, so a schema (and a length ceiling) cannot see that the sentence stops in the
middle. ``docs/GENERIC-ACCEPTANCE-AUDIT.md`` D8 recorded exactly that — two authored shorts were
accepted with a clipped ending and were then served to a learner as if complete.

This module judges the **shape of the ending**, never the size of the text. A long complete body
passes; a short clipped one does not; no length threshold is used as a proxy for completeness.

The signals are structural:

``unclosed code fence``
    A text opens a fenced block and never closes it. An odd fence count is a truncation, not a
    style choice.

``heading with an empty body``
    A Markdown heading followed by no content before the next heading (or the end of the text).
    A lesson that stops on a heading is missing its body.

``empty list item``
    A bullet or numbered item with no text after its marker, including an unchecked
    ``- [ ]`` task item.

``truncated list item``
    The text ends on a list item whose own text stops at a comma, colon or dangling function
    word — the checklist lost its last row.

``repeated terminal punctuation``
    The text ends on a repeated terminal mark (``..``, ``，，``, ``。。``). The ASCII ellipsis is
    exactly three dots and is a continuation marker; two dots is a truncation artifact.

``ends on a dangling function word``
    The final word cannot end a sentence ("and", "not", "the", "to", "because", ...). This is the
    signal that catches an ending which *did* keep its terminal period but lost its complement
    (the audit's ``"…, not."`` shape).

``ends mid-sentence``
    The final prose line carries no terminal punctuation and declares no continuation marker.

Exemptions are structural, not stylistic: a text that ends inside a list item, on a table row, on a
closed fence line or on a labelled value line (``Answer: …``, ``Step 2: …``) is terminated by that
structure and is not judged as prose. An explicit continuation marker (``…``, ``...``, an em dash
or ``(continued)``) is an author saying the sentence is deliberately unfinished, so it passes.

Deliberately accepted false-positive risk: a prose body that the author meant as a fragment and
wrote without terminal punctuation or a continuation marker is rejected, and so is a body in a
script that conventionally omits it at the end of a wildcard/label line. Both are fixed by the
author adding the punctuation or the marker the text already implies; neither can be fixed by
lengthening the text, which is why no length heuristic is used here.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["completeness_problems", "CONTINUATION_MARKERS", "COMPLETENESS"]

#: The stable name every completeness problem carries, so a rejection reason, a test and a
#: reviewer all agree on which check spoke.
COMPLETENESS = "text_completeness"

#: What an author writes when the sentence is *meant* to stop unfinished. The ASCII ellipsis is
#: three dots; two dots is not a marker and is judged as a repeated terminal mark instead.
CONTINUATION_MARKERS = (
    "...",
    "\u2026",  # horizontal ellipsis
    "\u22ef",  # midline horizontal ellipsis
    "\u2014",  # em dash
    "\u2013",  # en dash
    "\u2192",  # rightwards arrow
    "(continued)",
    "[continued]",
    "(continues)",
    "[continues]",
    "(cont.)",
)

#: Characters that end a sentence in a Latin or CJK sentence.
_TERMINAL = frozenset(".!?\u2026\u3002\uff01\uff1f\uff61")

#: Closing wrappers that may follow the terminal mark (a quoted or emphasised sentence keeps its
#: punctuation before the closer).
_CLOSERS = "”\"’')]}>»」』）】〕*_~`"

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([^`\s]*)\s*$")
_TASK_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+\[[ xX]\]\s*(.*)$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
#: A labelled value line ("Answer: …", "Step 2: …") is data, not a sentence.
_LABEL_LINE = re.compile(r"^\s*([A-Za-z][\w-]{0,20}|Step \d{1,2}):\s*\S")

#: Words that cannot end a declarative sentence. Closed and English-only by construction: a
#: truncation that keeps its period still ends on one of these.
#:
#: Auxiliaries and copulas (``is``, ``was``, ``do``, ``did``, ``has``, ``will``, ``can``, ...) are
#: deliberately **absent**: a stranded auxiliary is a complete sentence ("what the learner just
#: did.", "It is what it is."), so flagging them would reject honest prose. A clipped clause that
#: ends on one of those is caught by the missing-terminator rule instead when the period went with
#: it, which is the truncation shape D8 recorded.
_DANGLING_WORDS = frozenset(
    """
    a an the
    and or but nor yet
    because if when while unless until than
    of in on at to from with without by for about into onto over under
    between through during before after above below across against toward towards
    as
    not
    this these those its their his her our your my
    which who whom whose
    """.split()
)


def _is_blank(line: str) -> bool:
    return not line.strip()


def _trailing_marker(text: str) -> str | None:
    """Return the continuation marker the text ends with, if any (case-insensitive tail).

    Checked before and after stripping closing wrappers: ``"…"`` and ``"(continued)"`` end on
    punctuation of their own, so one order alone would miss the other.
    """
    candidates = {text.strip().lower(), _strip_closers(text).lower()}
    for marker in CONTINUATION_MARKERS:
        if any(candidate.endswith(marker) for candidate in candidates):
            return marker
    return None


def _strip_closers(text: str) -> str:
    return text.rstrip(_CLOSERS).rstrip()


def _last_word(text: str) -> str:
    match = re.search(r"([^\s]+)$", text)
    return match.group(1) if match else ""


def _repeated_terminal(text: str) -> str | None:
    """A run of two or more identical terminal marks at the end, except a real ellipsis."""
    match = re.search(r"([.!?\u3002\uff01\uff1f])\1+\s*$", text)
    if not match:
        return None
    mark, run = match.group(1), match.group(0).rstrip()
    if mark == "." and len(run) >= 3:
        return None  # an ASCII ellipsis is a continuation marker, not an artifact
    return run


def _fence_state(lines: list[str]) -> tuple[bool, str | None]:
    """(closed, opener) for the first fence in the text; ``closed`` is False when one is open."""
    open_char: str | None = None
    open_len = 0
    for line in lines:
        match = _FENCE.match(line)
        if not match:
            continue
        marker, info = match.group(1), match.group(2) or ""
        if open_char is None:
            open_char, open_len = marker[0], len(marker)
        elif marker[0] == open_char and len(marker) >= open_len and not info:
            open_char = None
    return (open_char is None), open_char


def completeness_problems(text: Any, *, where: str, prose: bool = True) -> list[str]:
    """Structural completeness problems in one authored text field.

    ``where`` prefixes every message ("blocks[2].short"). ``prose=False`` judges the structural
    shapes only (fences, empty headings, empty items) and skips the sentence-ending rules, which a
    title or a label does not obey.
    """
    value = str(text or "")
    if not value.strip():
        return []  # emptiness is a different rule, reported by the caller
    problems: list[str] = []
    lines = value.splitlines()
    prefix = f"{where} [{COMPLETENESS}]"

    closed, opener = _fence_state(lines)
    if not closed:
        problems.append(
            prefix + f" unclosed_code_fence: opens a fence with {opener!r} and never closes it"
        )
        # Nothing after an open fence can be judged as prose reliably.
        return problems

    for index, line in enumerate(lines):
        heading = _HEADING.match(line)
        if not heading:
            continue
        following = index + 1
        while following < len(lines) and _is_blank(lines[following]):
            following += 1
        if following >= len(lines) or _HEADING.match(lines[following]):
            problems.append(
                prefix
                + " empty_heading_body: ends the heading "
                + repr(heading.group(2).strip())
                + " with an empty body"
            )

    for line in lines:
        task = _TASK_ITEM.match(line)
        item = _LIST_ITEM.match(line)
        if task is not None and not task.group(1).strip():
            problems.append(prefix + " empty_list_item: has an empty checklist item")
        elif task is None and item is not None and not item.group(1).strip():
            problems.append(prefix + " empty_list_item: has an empty list item")

    last_index = len(lines) - 1
    while last_index >= 0 and _is_blank(lines[last_index]):
        last_index -= 1
    if last_index < 0:
        return problems
    last = lines[last_index].strip()

    # Structural terminators: the block shape, not punctuation, ends the text.
    if _TABLE_ROW.match(last) or _FENCE.match(last):
        return problems
    if _HEADING.match(last):
        return problems  # already reported above as a heading with an empty body

    task = _TASK_ITEM.match(last)
    item = task if task is not None else _LIST_ITEM.match(last)
    if item is not None:
        body = item.group(1).strip()
        if _trailing_marker(body) is not None:
            return problems
        dangling = _last_word(body.rstrip(".,;:")).lower()
        if body.endswith((",", ";", ":")) or (dangling in _DANGLING_WORDS):
            problems.append(
                prefix
                + " truncated_checklist: ends on a list item that stops mid-item "
                + repr(body[-40:])
            )
        return problems

    if _LABEL_LINE.match(last):
        return problems  # a labelled value is data, not a sentence

    if not prose:
        return problems

    core = _strip_closers(last)
    if _trailing_marker(last) is not None:
        return problems
    repeated = _repeated_terminal(core)
    if repeated is not None:
        problems.append(
            prefix
            + " repeated_terminal_punctuation: ends with "
            + repr(repeated)
            + "; a truncated text keeps the mark it was cut on"
        )
        return problems
    if core and core[-1] in _TERMINAL:
        dangling = _last_word(core.rstrip(".!?\u2026\u3002\uff01\uff1f\uff61")).lower()
        if dangling in _DANGLING_WORDS:
            problems.append(
                prefix
                + " dangling_terminal_word: ends on "
                + repr(dangling)
                + ", so the sentence lost its complement"
            )
        return problems
    problems.append(
        prefix
        + " mid_sentence_end: stops mid-sentence without terminal punctuation or a "
        + "continuation marker ("
        + repr(core[-40:])
        + ")"
    )
    return problems
