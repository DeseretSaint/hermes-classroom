"""Grading a conversation practice transcript — provider-free, learner turns only.

This is the ``conversation`` reference kind's whole grader (``docs/CONVERSATION-PRACTICE.md`` §7).
It reads only the stored **learner** turns and the declared key; tutor text is never inspected, so
nothing the model says can produce a pass. ``grading.grade`` routes the kind here and the aux lane
is never consulted.

A reference it cannot read raises ``ValueError``. ``domain.practice_end`` persists that failure as
``needs_retry`` and advances nothing, exactly like any other grader that cannot finish.
"""

from __future__ import annotations

import re
from typing import Any

from . import grading, practice, validators


def _learner_text(turns: Any) -> list[str]:
    if not isinstance(turns, list):
        raise ValueError("a conversation transcript needs a turns list")
    texts: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            raise ValueError("each transcript turn is an object")
        speaker = turn.get("speaker")
        text = turn.get("text")
        if speaker not in ("learner", "tutor"):
            raise ValueError(f"transcript turn declares an unknown speaker {speaker!r}")
        if not isinstance(text, str):
            raise ValueError("each transcript turn carries text")
        if speaker == "learner":
            texts.append(text)
    return texts


def _clause_matches(clause: dict[str, Any], text: str) -> bool:
    kind = clause.get("type")
    value = str(clause.get("value") or "")
    if kind == "exact":
        return validators.normalize_text(value) in validators.normalize_text(text)
    if kind == "regex":
        return re.search(value, text, re.IGNORECASE) is not None
    raise ValueError(f"a match clause declares an unknown type {kind!r}")


def _reference_targets(reference: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    targets = reference.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("a conversation reference declares no targets")
    resolved: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("each conversation target is an object")
        target_id = target.get("id")
        clauses = target.get("match")
        if not isinstance(target_id, str) or not isinstance(clauses, list) or not clauses:
            raise ValueError("each conversation target names an id and its match clauses")
        for clause in clauses:
            if not isinstance(clause, dict):
                raise ValueError("a match clause is an object")
            if clause.get("type") not in ("exact", "regex"):
                raise ValueError(f"unknown match clause type {clause.get('type')!r}")
        resolved[target_id] = clauses
    return resolved


def grade_transcript(
    *,
    reference: dict[str, Any],
    rubric: dict[str, Any] | None,
    turns: Any,
    stimulus: dict[str, Any] | None = None,
    targets_visible: bool = True,
) -> grading.GradingResult:
    """Grade the stored learner turns against the declared target key and turn range."""
    if not isinstance(reference, dict) or reference.get("kind") != "conversation":
        raise ValueError("grade_transcript needs a conversation reference")
    practice_block = practice.declaration(stimulus) or {}
    if "targets_visible" in practice_block:
        targets_visible = bool(practice_block.get("targets_visible"))
    labels = {
        str(target.get("id")): str(target.get("label") or "")
        for target in practice_block.get("targets") or []
        if isinstance(target, dict)
    }
    learner = _learner_text(turns)
    targets = _reference_targets(reference)
    rubric = rubric if isinstance(rubric, dict) else {}
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("a conversation rubric declares criteria")
    try:
        low = int(reference.get("min_turns") or 0)
        high = int(reference.get("max_turns") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("a conversation reference declares min_turns and max_turns") from exc
    if not (0 < low <= high):
        raise ValueError("a conversation reference declares a readable turn range")

    outcomes: list[validators.Outcome] = []
    for index, criterion in enumerate(criteria, start=1):
        item = criterion if isinstance(criterion, dict) else {}
        detector = item.get("detector")
        detector = detector if isinstance(detector, dict) else {}
        kind = str(detector.get("kind") or "")
        criterion_id = str(item.get("id") or f"c{index}")
        if kind == "target_phrase":
            target_id = str(detector.get("target_id") or "")
            clauses = targets.get(target_id)
            if clauses is None:
                raise ValueError(f"criterion {criterion_id!r} names an undeclared target {target_id!r}")
            produced = any(
                _clause_matches(clause, text) for text in learner for clause in clauses
            )
            if targets_visible:
                observed = labels.get(target_id) or f"target {target_id} produced"
            else:
                observed = f"target {target_id} not produced" if not produced else "produced a hidden target"
            outcomes.append(validators.Outcome(criterion_id=criterion_id, met=produced, observed=observed))
        elif kind == "turn_count":
            count = len(learner)
            met = low <= count <= high
            outcomes.append(
                validators.Outcome(
                    criterion_id=criterion_id,
                    met=met,
                    observed=f"{count} learner turns; the practice asks for {low} to {high}",
                )
            )
        else:
            raise ValueError(f"criterion {criterion_id!r} declares an unknown detector {kind!r}")

    verdict = validators.verdict_for(outcomes, pass_rule=str(rubric.get("pass_rule") or "all"))
    observed = [
        {"id": outcome.criterion_id[:80], "observed": outcome.observed[:500], "met": bool(outcome.met)}
        for outcome in outcomes[:40]
    ]
    return grading.GradingResult(
        verdict=verdict,
        criteria=observed,
        provenance={
            "grader": "deterministic:conversation",
            "reference_sha256": grading.reference_hash(reference),
        },
    )


def _label_for(criterion: dict[str, Any], target_id: str) -> str:
    """The criterion's own text is author-facing; a target label is only safe when targets are shown.

    This helper deliberately returns nothing secret: the caller only uses it when
    ``targets_visible`` is true, where the label was already in view.
    """
    return str(criterion.get("criterion") or target_id)


__all__ = ["grade_transcript"]
