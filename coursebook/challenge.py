"""A challenge-out item is a *different case* of the same target, never the answered item again.

``progression.challenge_out`` promises an audited item the learner has not answered. An authored
objective carries its alternatives in ``check_spec.variants``; a generated objective stores its one
authored check in ``checks`` and has no variant list, so the handler used to clone that check —
serving the exact stimulus the learner had just answered and calling it a challenge. Recognition of
a seen question is not retrieval of the target.

This module derives the variant instead of replaying. It is deliberately narrow: it only builds a
case the backend can *prove* is correct, with no model call (provider work never runs fenced, see
:mod:`coursebook.domain`). Today that is a numeric check — the arithmetic expression in the prompt
is re-cased with different operands and the reference value is recomputed exactly, so the new item
is a new case of the same target and its answer is arithmetic, not an invention. Every other shape
returns ``None`` and the caller refuses with ``no_varied_challenge_available``; a replay is never a
fallback, and a same-item return is labelled "review this item" on the surface, never "challenge".
"""

from __future__ import annotations

import re
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any, Mapping

#: One binary arithmetic expression inside a prompt: ``2 + 2``, ``-3 × 4``, ``10 / 5``. The
#: operator must stand alone between spaces — a date like ``2026-11-14`` is not an expression.
_EXPRESSION = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)[ \t]+([+\-*/×÷])[ \t]+(-?\d+(?:\.\d+)?)(?![\w.])"
)

#: How many deterministic re-casings to try before giving up. Each attempt shifts both operands,
#: so attempt 1 is a different case from the answered item and every later attempt differs again.
_ATTEMPTS = 8

_OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "×": lambda a, b: a * b,
    "/": lambda a, b: None if b == 0 else a / b,
    "÷": lambda a, b: None if b == 0 else a / b,
}


def _literal(text: str) -> Fraction:
    return Fraction(text)


def _number(value: Fraction) -> str | None:
    """A plain decimal spelling, or ``None`` when the value has no finite decimal form."""
    if value.denominator == 1:
        return str(value.numerator)
    denominator = value.denominator
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    if denominator != 1:
        return None
    with localcontext() as context:
        context.prec = 40
        exact = Decimal(value.numerator) / Decimal(value.denominator)
        text = format(exact.normalize(), "f")
    return text or "0"


def _reference_value(reference: Mapping[str, Any]) -> Fraction | None:
    try:
        return _literal(str(reference.get("value")))
    except (TypeError, ValueError):
        return None


def variant_of(
    stimulus: Mapping[str, Any],
    reference: Mapping[str, Any],
    *,
    attempt: int = 1,
) -> dict[str, Any] | None:
    """A new case of the same numeric target, or ``None`` when none can be proved.

    The check must be a numeric, text-format question whose prompt holds exactly one arithmetic
    expression and whose choices/items/practice carry no pre-built answer set. ``attempt`` selects
    the re-casing deterministically, so the caller can walk attempts until the stimulus is unused.
    """
    if str(reference.get("kind") or "") != "numeric":
        return None
    if str(stimulus.get("format") or "text") != "text":
        return None
    if stimulus.get("choices") or stimulus.get("items") or stimulus.get("practice"):
        return None
    prompt = str(stimulus.get("prompt") or "")
    matches = list(_EXPRESSION.finditer(prompt))
    if len(matches) != 1:
        return None
    old_value = _reference_value(reference)
    if old_value is None:
        return None
    match = matches[0]
    operator = match.group(2)
    operation = _OPERATORS.get(operator)
    if operation is None:
        return None
    try:
        left = _literal(match.group(1))
        right = _literal(match.group(3))
    except (TypeError, ValueError):
        return None
    shift = max(1, int(attempt))
    for step in range(shift, shift + _ATTEMPTS):
        new_left = left + step
        new_right = right + step
        value = operation(new_left, new_right)
        if value is None or value == old_value:
            continue
        spelled = _number(value)
        left_text = _number(new_left)
        right_text = _number(new_right)
        if spelled is None or left_text is None or right_text is None:
            continue
        expression = f"{left_text} {operator} {right_text}"
        new_prompt = prompt[: match.start()] + expression + prompt[match.end():]
        if new_prompt == prompt:
            continue
        new_stimulus = dict(stimulus)
        new_stimulus["prompt"] = new_prompt
        new_reference = dict(reference)
        new_reference["value"] = spelled
        return {"stimulus": new_stimulus, "reference": new_reference, "shift": step}
    return None
