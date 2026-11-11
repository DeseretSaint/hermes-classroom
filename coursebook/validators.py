"""Deterministic answer validators for closed-form checks.

``PREBUILD_SPEC.md`` §8 requires closed forms to be graded without a model: units, rounding,
tolerance, equivalent forms, Unicode/notation and multiple valid solutions. Nothing here calls a
provider, and nothing here returns a pass on a parse failure — an answer that cannot be read is
``not_yet`` with an explicit observed reason, while a *grader* failure (which is different) is
``needs_retry`` in :mod:`coursebook.grading`.

A reference spec is a JSON object stored in ``checks.reference_json``::

    {"kind": "exact",     "answers": ["alpha", "a"]}
    {"kind": "numeric",   "value": "3.5", "tolerance": {"abs": "0.05"}, "unit": "cm",
                          "accepted_units": ["cm", "m"]}
    {"kind": "selection", "answers": [["a", "b"], ["b", "a"]]}
    {"kind": "rubric_only"}                       # open response; aux grader only

The reference never leaves the backend: responses carry criteria observations only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

#: Reference kinds this module can grade without a model.
CLOSED_KINDS = ("exact", "numeric", "selection")

#: Every kind a stored reference may declare. ``rubric_only`` names the open lane explicitly, so
#: an authoring mistake cannot masquerade as an open-response check by omitting ``kind``.
#: ``conversation`` is a closed kind graded by :mod:`coursebook.conversation` from the stored
#: learner turns; it never reaches the aux lane (``docs/CONVERSATION-PRACTICE.md`` §7).
REFERENCE_KINDS = CLOSED_KINDS + ("rubric_only", "conversation")


class ReferenceSpecError(ValueError):
    """A reference spec does not declare a lane, or declares one it cannot satisfy."""


_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
_QUOTES = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
}
_FRACTION = re.compile(r"^([+-]?\d+)\s*/\s*(\d+)$")
_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")

#: unit -> (dimension, factor to the dimension's base unit)
_UNITS: dict[str, tuple[str, Decimal]] = {
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "m": ("length", Decimal("1")),
    "km": ("length", Decimal("1000")),
    "in": ("length", Decimal("0.0254")),
    "ft": ("length", Decimal("0.3048")),
    "mg": ("mass", Decimal("0.000001")),
    "g": ("mass", Decimal("0.001")),
    "kg": ("mass", Decimal("1")),
    "t": ("mass", Decimal("1000")),
    "ml": ("volume", Decimal("0.001")),
    "l": ("volume", Decimal("1")),
    "s": ("time", Decimal("1")),
    "sec": ("time", Decimal("1")),
    "min": ("time", Decimal("60")),
    "h": ("time", Decimal("3600")),
    "hr": ("time", Decimal("3600")),
    "%": ("ratio", Decimal("0.01")),
}


@dataclass(frozen=True)
class Outcome:
    """One graded criterion. ``observed`` is learner-facing and must never contain a key."""

    criterion_id: str
    met: bool
    observed: str


def normalize_text(value: str) -> str:
    """NFKC, straight quotes/dashes, casefold, collapsed whitespace, no trailing punctuation.

    This is notation folding, not meaning folding: ``2+2`` and ``2 + 2`` compare equal, but
    ``-2`` and ``2`` do not.
    """
    text = unicodedata.normalize("NFKC", str(value))
    for dash in _DASHES:
        text = text.replace(dash, "-")
    for quote, plain in _QUOTES.items():
        text = text.replace(quote, plain)
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    text = _strip_trailing_punctuation(text)
    if len(text) >= 2 and text[0] in "\"'" and text[-1] in "\"'":
        text = _strip_trailing_punctuation(text[1:-1].strip())
    return text


def _strip_trailing_punctuation(text: str) -> str:
    while text and text[-1] in ".,!?;:":
        text = text[:-1].rstrip()
    return text


def parse_number(value: Any) -> Decimal | None:
    """Parse a learner number: ``1,000``, ``1/2``, ``50%``, ``3.5e2``, ``-4``.

    Returns ``None`` when the text is not a single number. Never guesses.
    """
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFKC", value).strip().replace("\u00a0", " ")
    for dash in _DASHES:
        text = text.replace(dash, "-")
    text = text.replace(" ", "")
    percent = text.endswith("%")
    if percent:
        text = text[:-1]
    if not text:
        return None
    fraction = _FRACTION.match(text)
    if fraction:
        denominator = Decimal(fraction.group(2))
        if denominator == 0:
            return None
        number = Decimal(fraction.group(1)) / denominator
    else:
        cleaned = text.replace(",", "") if re.match(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$", text) else text
        if not _NUMBER.match(cleaned):
            return None
        try:
            number = Decimal(cleaned)
        except InvalidOperation:
            return None
    return number / 100 if percent else number


def split_unit(value: str) -> tuple[str, str | None]:
    """``"3.5 cm"`` -> ``("3.5", "cm")``. A bare number has no unit."""
    text = unicodedata.normalize("NFKC", value).strip()
    match = re.match(r"^(.*?)[\s]*([A-Za-z%]+)$", text)
    if match and match.group(2).casefold() in _UNITS and parse_number(match.group(1)) is not None:
        return match.group(1), match.group(2).casefold()
    return text, None


def convert(value: Decimal, from_unit: str | None, to_unit: str | None) -> Decimal | None:
    """Convert between units of the same dimension. ``None`` when the conversion is invalid."""
    if from_unit == to_unit:
        return value
    if from_unit is None or to_unit is None:
        return None
    source = _UNITS.get(from_unit)
    target = _UNITS.get(to_unit)
    if source is None or target is None or source[0] != target[0]:
        return None
    return value * source[1] / target[1]


def _tolerance(reference: dict[str, Any], expected: Decimal) -> Decimal:
    tolerance = reference.get("tolerance") or {}
    absolute = tolerance.get("abs")
    relative = tolerance.get("rel")
    limits = []
    if absolute is not None:
        parsed = parse_number(absolute)
        if parsed is not None:
            limits.append(abs(parsed))
    if relative is not None:
        parsed = parse_number(relative)
        if parsed is not None:
            limits.append(abs(expected * parsed))
    return max(limits) if limits else Decimal("0")


def reference_kind(reference: dict[str, Any] | None) -> str:
    """Return the grading lane a stored reference declares.

    A **missing** or unknown ``kind`` is an error, not an open-response check. Routing an absent
    declaration to the open lane made every generated lesson ungradeable while looking like a
    deliberate open response; :mod:`coursebook.grading` turns this error into a fail-closed
    ``GradingUnavailable``, and writers never persist a reference they could not seal.
    """
    kind = (reference or {}).get("kind")
    if not isinstance(kind, str) or kind not in REFERENCE_KINDS:
        raise ReferenceSpecError(f"reference declares no known grading lane: kind={kind!r}")
    return kind


def seal_reference(spec: dict[str, Any] | None) -> dict[str, Any]:
    """The only sanctioned constructor for a stored reference.

    Validates that the spec declares a lane and that the lane's required fields are usable, then
    returns a copy. Every writer of ``checks.reference_json`` calls this, so a reference without a
    ``kind`` cannot be produced by construction rather than by convention.
    """
    reference = dict(spec or {})
    kind = reference_kind(reference)
    if kind == "exact":
        answers = reference.get("answers")
        if (
            not isinstance(answers, list)
            or not answers
            or not all(isinstance(item, str) and item.strip() for item in answers)
        ):
            raise ReferenceSpecError("an exact reference needs a non-empty list of answer strings")
    elif kind == "numeric":
        if parse_number(reference.get("value")) is None:
            raise ReferenceSpecError("a numeric reference needs a readable value")
    elif kind == "selection":
        answers = reference.get("answers")
        if not isinstance(answers, list) or not answers:
            raise ReferenceSpecError("a selection reference needs accepted combinations")
        for group in answers:
            if not isinstance(group, list) or not group:
                raise ReferenceSpecError("each accepted selection must be a non-empty list")
    elif kind == "conversation":
        targets = reference.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ReferenceSpecError("a conversation reference declares its target key")
        seen: set[str] = set()
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("id"), str):
                raise ReferenceSpecError("each conversation target names an id")
            target_id = str(target["id"])
            if target_id in seen:
                raise ReferenceSpecError("conversation target ids are unique")
            seen.add(target_id)
            clauses = target.get("match")
            if not isinstance(clauses, list) or not clauses:
                raise ReferenceSpecError("a conversation target carries at least one match clause")
            for clause in clauses:
                if not isinstance(clause, dict) or clause.get("type") not in ("exact", "regex"):
                    raise ReferenceSpecError("a conversation clause is exact or regex")
                value = clause.get("value")
                if not isinstance(value, str) or not value.strip():
                    raise ReferenceSpecError("a conversation clause carries a value")
                if clause["type"] == "regex":
                    try:
                        pattern = re.compile(value)
                    except re.error as exc:
                        raise ReferenceSpecError(f"a conversation regex does not compile: {exc}") from exc
                    if pattern.search(""):
                        raise ReferenceSpecError("a conversation regex matches the empty string")
        low, high = reference.get("min_turns"), reference.get("max_turns")
        if (
            not isinstance(low, int)
            or isinstance(low, bool)
            or not isinstance(high, int)
            or isinstance(high, bool)
            or not (3 <= low <= high <= 5)
        ):
            raise ReferenceSpecError("a conversation reference declares a 3 to 5 learner-turn range")
    return reference


def grade_exact(reference: dict[str, Any], text: str) -> tuple[bool, str]:
    accepted = [normalize_text(item) for item in reference.get("answers") or []]
    observed = normalize_text(text)
    if not accepted:
        return False, "no accepted answer is configured for this check"
    if observed in accepted:
        return True, "matches an accepted answer"
    return False, "Your answer does not match an accepted answer."


def grade_numeric(reference: dict[str, Any], text: str) -> tuple[bool, str]:
    expected = parse_number(reference.get("value"))
    if expected is None:
        return False, "the check has no readable reference value"
    raw, unit = split_unit(text)
    observed = parse_number(raw)
    if observed is None:
        return False, "the answer is not a number this check can read"
    expected_unit = (reference.get("unit") or None)
    if expected_unit is not None:
        expected_unit = str(expected_unit).casefold()
        accepted_units = [str(u).casefold() for u in (reference.get("accepted_units") or [expected_unit])]
        if unit is None:
            return False, f"the answer has no unit; expected {expected_unit}"
        if unit not in accepted_units:
            return False, f"the unit {unit!r} is not accepted for this check"
        converted = convert(observed, unit, expected_unit)
        if converted is None:
            return False, f"cannot convert {unit!r} to {expected_unit!r}"
        observed = converted
    elif unit is not None:
        return False, "a unit was given but this check expects a plain number"
    limit = _tolerance(reference, expected)
    difference = abs(observed - expected)
    if difference <= limit:
        return True, f"within tolerance ({difference.normalize():f} <= {limit.normalize():f})"
    return False, f"outside tolerance by {difference.normalize():f}"


def grade_selection(reference: dict[str, Any], selection: list[str]) -> tuple[bool, str]:
    accepted = reference.get("answers") or []
    normalized = [normalize_text(item) for item in selection]
    order_sensitive = bool(reference.get("order_sensitive"))
    for candidate in accepted:
        candidate_normalized = [normalize_text(item) for item in candidate]
        if order_sensitive:
            if normalized == candidate_normalized:
                return True, "selection matches"
        elif sorted(normalized) == sorted(candidate_normalized):
            return True, "selection matches (order-insensitive)"
    return False, "selection does not match an accepted combination"


def grade_reference(reference: dict[str, Any], answer: dict[str, Any], *, criterion_id: str = "c1") -> Outcome:
    """Grade one closed-form answer. Raises ``ValueError`` for a non-closed reference kind."""
    kind = reference.get("kind")
    if kind == "exact":
        text = str(answer.get("text") or "")
        met, observed = grade_exact(reference, text)
    elif kind == "numeric":
        text = str(answer.get("text") or "")
        met, observed = grade_numeric(reference, text)
    elif kind == "selection":
        selection = answer.get("selection")
        if not isinstance(selection, list):
            met, observed = False, "the answer is not a selection"
        else:
            met, observed = grade_selection(reference, [str(item) for item in selection])
    else:
        raise ValueError(f"reference kind {kind!r} is not closed-form")
    return Outcome(criterion_id=criterion_id, met=met, observed=observed[:500])


def verdict_for(outcomes: list[Outcome], pass_rule: str = "all") -> str:
    """Map criterion outcomes to a contract verdict. No outcomes is never a pass."""
    if not outcomes:
        return "needs_retry"
    met = [outcome.met for outcome in outcomes]
    if pass_rule == "any" and any(met):
        return "pass"
    if all(met):
        return "pass"
    if any(met):
        return "partial"
    return "not_yet"
