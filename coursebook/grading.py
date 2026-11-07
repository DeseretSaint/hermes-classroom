"""The grading gate.

Two lanes, deliberately separate:

* **closed form** — graded here, deterministically, by :mod:`coursebook.validators`. No provider,
  no model, no network.
* **open response** — graded only through a bounded aux adapter that the host provides. The
  adapter is injected (:func:`configure_aux_grader`) so this module never reaches for a model
  itself and tests never pretend to have one. Until the aux lane is measured and switched on
  (Sentinel probe #4), an open response fails closed with :class:`GradingUnavailable`.

Failure semantics are the point of this module: a grader that cannot finish produces
``needs_retry`` at the command layer, which persists the answer and advances **nothing**. A
timeout, an exception, invalid JSON or an out-of-schema result can never become a pass
(``PREBUILD_SPEC.md`` §8, ``AUDIT.md`` R2/R10/R11).

The reference answer never leaves the backend. Criteria observations and a hash of the reference
are returned; the reference itself is not.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from . import validators

#: Default ceiling for the aux lane. The Hermes hook timeout is the outer bound; this is the
#: inner one and must stay strictly below it (``coursebook/hooks.py``).
DEFAULT_DEADLINE_MS = 8000

#: The contract verdict for "the grader could not finish". Never a pass.
RETRY_VERDICT = "needs_retry"

#: The one evidence class the confirmation lane may claim. ``domain.attempt_submit`` accepts this
#: value from a grader result and nothing else, so no adapter can smuggle ``cold`` through.
CONFIRMATION_EVIDENCE_CLASS = "self_reported"


class GradingUnavailable(RuntimeError):
    """The grader could not finish. The caller persists ``needs_retry``; nothing advances."""


class ConfirmationAnswerError(ValueError):
    """A confirmation answer that cannot be read as a selection of declared items.

    ``reason`` is the frozen contract reason (``docs/CHECKLIST-CONFIRMATION.md`` §4.3). The command
    layer translates it into ``VALIDATION_FAILED`` **before** the write transaction: a refusal is
    not a failed attempt, so no attempt row, evidence or revision bump is written.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class GradingResult:
    verdict: str
    criteria: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    evidence_class: str | None = None


#: ``grader(answer, rubric, construct, context, attempt_id) -> dict``.
AuxGrader = Callable[..., dict[str, Any]]

_aux_grader: AuxGrader | None = None
_aux_task_name: str = ""

_VERDICTS = ("pass", "partial", "not_yet", "clarification")


def configure_aux_grader(grader: AuxGrader | None, *, task_name: str = "") -> None:
    """Install the bounded aux grader. ``None`` disables the open lane (the default)."""
    global _aux_grader, _aux_task_name
    _aux_grader = grader
    _aux_task_name = task_name


def aux_grader_configured() -> bool:
    return _aux_grader is not None


def reference_hash(reference: dict[str, Any]) -> str:
    payload = json.dumps(reference, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _criteria_from(outcomes: list[validators.Outcome]) -> list[dict[str, Any]]:
    return [
        {"id": outcome.criterion_id[:80], "observed": outcome.observed[:500], "met": bool(outcome.met)}
        for outcome in outcomes[:40]
    ]


def grade_closed(
    *,
    reference: dict[str, Any],
    rubric: dict[str, Any] | None,
    answer: dict[str, Any],
    criterion_id: str = "c1",
) -> GradingResult:
    """Deterministic grading. Raises ``ValueError`` when the reference is not closed-form."""
    outcome = validators.grade_reference(reference, answer, criterion_id=criterion_id)
    pass_rule = str((rubric or {}).get("pass_rule") or "all")
    verdict = validators.verdict_for([outcome], pass_rule=pass_rule)
    return GradingResult(
        verdict=verdict,
        criteria=_criteria_from([outcome]),
        provenance={
            "grader": f"deterministic:{reference.get('kind')}",
            "reference_sha256": reference_hash(reference),
        },
    )


def confirmation_items(
    reference: dict[str, Any] | None, stimulus: dict[str, Any] | None
) -> list[dict[str, str]] | None:
    """The declared checklist items when this check is confirmation-shaped, else ``None``.

    Frozen predicate (``docs/CHECKLIST-CONFIRMATION.md`` §4.1): ``reference.kind == rubric_only``
    and ``stimulus.format == verification`` with a non-empty list of ``{id, label}``. The answer
    kind and the course recipe are checked by the caller, because they are not properties of the
    check. A malformed item list is *not* confirmation-shaped: it falls through to the existing
    router unchanged, which fails closed.
    """
    if not isinstance(reference, dict) or reference.get("kind") != "rubric_only":
        return None
    if not isinstance(stimulus, dict) or stimulus.get("format") != "verification":
        return None
    raw = stimulus.get("items")
    if not isinstance(raw, list) or not raw:
        return None
    items: list[dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None
        item_id = entry.get("id")
        label = entry.get("label")
        if not isinstance(item_id, str) or not item_id or not isinstance(label, str):
            return None
        items.append({"id": item_id, "label": label})
    return items


def grade_confirmation(
    items: list[dict[str, str]],
    answer: dict[str, Any],
    *,
    reference: dict[str, Any] | None = None,
) -> GradingResult:
    """Grade a tick-list by membership only: provider-free, deterministic, self-reported.

    A criterion exists for **every declared item**, in declared order, so a partial confirmation
    records which steps were and were not confirmed. ``met`` is membership in the deduped
    selection; nothing compares labels, and nothing consults a model.
    """
    selection = answer.get("selection") if isinstance(answer, dict) else None
    submitted: list[str] = []
    if isinstance(selection, list):
        for entry in selection:
            if entry not in submitted:
                submitted.append(entry)
    if not submitted:
        raise ConfirmationAnswerError("checklist_no_items_confirmed")
    declared = {item["id"] for item in items}
    for entry in submitted:
        if not isinstance(entry, str) or entry not in declared:
            raise ConfirmationAnswerError("unknown_check_item")
    confirmed = set(submitted)
    criteria = [
        {
            "id": item["id"][:80],
            "observed": item["label"][:500],
            "met": item["id"] in confirmed,
        }
        for item in items[:40]
    ]
    verdict = "pass" if all(criterion["met"] for criterion in criteria) else "partial"
    return GradingResult(
        verdict=verdict,
        criteria=criteria,
        provenance={
            "grader": "provider-free:confirmation",
            "reference_sha256": reference_hash(reference or {"kind": "rubric_only"}),
            "declared_items": len(items),
            "confirmed_items": len(confirmed),
        },
        evidence_class=CONFIRMATION_EVIDENCE_CLASS,
    )


def _run_with_deadline(grader: AuxGrader, deadline_ms: int, **kwargs: Any) -> dict[str, Any]:
    """Run the aux adapter in a worker thread and refuse to wait past the deadline.

    A hung provider call leaves a daemon thread behind, but the command has already returned
    ``needs_retry`` and no state was written — the alternative (blocking the turn) is worse.
    """
    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["value"] = grader(**kwargs)
        except BaseException as exc:  # noqa: BLE001 - surfaced as a typed failure
            box["error"] = exc

    thread = threading.Thread(target=runner, name="coursebook-aux-grader", daemon=True)
    thread.start()
    thread.join(max(deadline_ms, 1) / 1000)
    if thread.is_alive():
        raise GradingUnavailable(f"aux grader exceeded its {deadline_ms} ms deadline")
    if "error" in box:
        raise GradingUnavailable(f"aux grader failed: {type(box['error']).__name__}")
    value = box.get("value")
    if not isinstance(value, dict):
        raise GradingUnavailable("aux grader returned no structured result")
    return value


def _validate_aux_result(result: dict[str, Any]) -> GradingResult:
    """Locally validate the adapter's structure. Invalid output is never accepted as a verdict."""
    verdict = result.get("verdict")
    if verdict not in _VERDICTS:
        raise GradingUnavailable(f"aux grader returned an unknown verdict {verdict!r}")
    raw_criteria = result.get("criteria")
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise GradingUnavailable("aux grader returned no criteria observations")
    criteria: list[dict[str, Any]] = []
    for item in raw_criteria[:40]:
        if not isinstance(item, dict):
            raise GradingUnavailable("aux grader criterion is not an object")
        criterion_id = item.get("id")
        observed = item.get("observed")
        met = item.get("met")
        if not isinstance(criterion_id, str) or not criterion_id:
            raise GradingUnavailable("aux grader criterion has no id")
        if not isinstance(observed, str):
            raise GradingUnavailable("aux grader criterion has no observation")
        if not isinstance(met, bool):
            raise GradingUnavailable("aux grader criterion has no boolean met flag")
        criteria.append({"id": criterion_id[:80], "observed": observed[:500], "met": met})
    if verdict == "pass" and not all(item["met"] for item in criteria):
        # A pass with unmet criteria would be a fabricated pass.
        raise GradingUnavailable("aux grader claimed a pass with unmet criteria")
    rationale = result.get("rationale")
    provenance: dict[str, Any] = {
        "grader": f"aux:{_aux_task_name or 'unnamed'}",
        "deadline_ms": None,
    }
    if isinstance(rationale, str) and rationale:
        provenance["rationale"] = rationale[:500]
    return GradingResult(verdict=str(verdict), criteria=criteria, provenance=provenance)


def grade_open(
    *,
    reference: dict[str, Any],
    rubric: dict[str, Any] | None,
    stimulus: dict[str, Any] | None,
    answer: dict[str, Any],
    attempt_id: str,
    locale: str | None,
    deadline_ms: int = DEFAULT_DEADLINE_MS,
) -> GradingResult:
    """Grade an open response through the bounded aux adapter, or fail closed.

    The adapter receives only answer, rubric, construct and permitted context — never the whole
    course, and never the learner's history.
    """
    if _aux_grader is None:
        raise GradingUnavailable(
            "the open-response aux grader is not configured; this build fails closed to needs_retry"
        )
    rubric = rubric or {}
    result = _run_with_deadline(
        _aux_grader,
        deadline_ms,
        answer=answer,
        rubric=rubric,
        construct=rubric.get("construct"),
        context={"stimulus": stimulus or {}, "locale": locale},
        attempt_id=attempt_id,
    )
    graded = _validate_aux_result(result)
    provenance = dict(graded.provenance)
    provenance["deadline_ms"] = deadline_ms
    provenance["reference_sha256"] = reference_hash(reference)
    return GradingResult(verdict=graded.verdict, criteria=graded.criteria, provenance=provenance)


def grade(
    *,
    reference: dict[str, Any],
    rubric: dict[str, Any] | None,
    stimulus: dict[str, Any] | None,
    answer: dict[str, Any],
    attempt_id: str,
    locale: str | None = None,
    deadline_ms: int = DEFAULT_DEADLINE_MS,
    allow_confirmation: bool = True,
) -> GradingResult:
    """Route one answer to the lane its reference declares.

    A closed kind takes the deterministic lane and ``rubric_only`` takes the open lane. A missing
    or unknown kind is a **grader failure**, not an open response: silently falling through to the
    open lane is how every generated lesson became ungradeable while looking deliberate. Callers
    persist that failure as ``needs_retry``, exactly like any other unavailable grader.

    A verification checklist answered with a ``selection`` takes the **confirmation lane** first:
    provider-free, membership-only, evidence class ``self_reported``. The caller passes
    ``allow_confirmation=False`` for a parent-recipe enrollment, whose only recording path is
    ``observation.record`` (``docs/CHECKLIST-CONFIRMATION.md`` §6).
    """
    try:
        kind = validators.reference_kind(reference)
    except validators.ReferenceSpecError as exc:
        raise GradingUnavailable(str(exc)) from exc
    if (
        allow_confirmation
        and isinstance(answer, dict)
        and answer.get("kind") == "selection"
    ):
        items = confirmation_items(reference, stimulus)
        if items is not None:
            return grade_confirmation(items, answer, reference=reference)
    if kind in validators.CLOSED_KINDS:
        return grade_closed(reference=reference, rubric=rubric, answer=answer)
    return grade_open(
        reference=reference or {},
        rubric=rubric,
        stimulus=stimulus,
        answer=answer,
        attempt_id=attempt_id,
        locale=locale,
        deadline_ms=deadline_ms,
    )
