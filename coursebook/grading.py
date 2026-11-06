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


class GradingUnavailable(RuntimeError):
    """The grader could not finish. The caller persists ``needs_retry``; nothing advances."""


@dataclass(frozen=True)
class GradingResult:
    verdict: str
    criteria: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)


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
) -> GradingResult:
    """Route one answer to the lane its reference declares.

    Only an explicitly closed kind takes the deterministic lane. Anything else — including a
    missing or unknown kind — is open, because guessing a lane would be guessing a verdict.
    """
    kind = (reference or {}).get("kind")
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
