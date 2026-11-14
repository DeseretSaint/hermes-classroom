"""Review queue scheduler: due, overdue, cap, snooze, stretch, drop.

The queue is **derived** from committed evidence, not from a separate authoritative table. That is
a deliberate constraint of ``cb.db`` v2, which has no review-schedule table: a second copy of
"what is due" would be a competing authority (``AUDIT.md`` R5). What is durable is the evidence:

* a cold layer-2 pass (``independent_evidence`` / ``delayed_retrieval``) is the clock start;
* the newest **committed attempt** starts the clock even when it was not a cold pass. An
  objective whose ladder never started returns on its first rung: the short beat after a miss,
  the ladder's own first rung after a pass that only *introduced* it. An objective that already
  earned a rung keeps it — a failed review never resets to the first rung and a hinted pass never
  advances — so the harder-earned spacing survives. Scheduling a return is not evidence: the L2
  rule is untouched, so a return pass is still not independent until it is cold
  (``coursebook.domain._objective_state_after``);
* learner review actions are layer-1 events (``review_snooze``, ``review_stretch``,
  ``review_drop``) recorded with ``evidence_class='self_reported'`` — the learner's own statement
  about scheduling, never evidence of mastery;
* the objective's ``review_due`` state is the contracted surface the library and lesson pane read.

Intervals are a declared **heuristic**, not a validated forgetting curve (``AUDIT.md`` R9/R10):
the ladder is a product default, shown to the learner, and never presented as an attainment
prediction.

The **starting rung** is read from the attempt record, not from the evidence target alone
(UP-18). The table below is declared, ordered and tiny on purpose — five cases, no learned
parameters, no score:

* the pass that needed no help on its first try starts one rung above the ladder's floor;
* a pass on the first try *with* a hint starts on the floor. The help was already priced into the
  evidence class (``coursebook.engagement.EVIDENCE_CLASS_WEIGHT``), so the scheduler does not
  invent an interval shorter than the target declares: the ladder's own floor is the return;
* a pass after a miss, or after more than one attempt, returns on the short beat
  (:data:`MISS_RETURN_DAYS`): the record says the item was not available first time. This *is* a
  second charge on the same fact — the card that introduced it says so plainly — and it is a
  declared spacing decision, never a mastery claim;
* a pass whose answer was shown returns on the short beat too — the strongest assistance is not
  earning spacing;
* an objective with no attempt record at all (hand-seeded layer-2 evidence, a pack import) keeps
  the floor: no record is not the same as a cold first-try record, so it earns nothing extra.

The first two are the ladder's *offset*, decided once from the record that opened it and kept for
the ladder's life; the short beat is decided per cycle from that cycle's record. A failed review
therefore keeps the rung it reached instead of falling back to the floor.

:data:`COLD_START_RUNG` and the short beat are the whole mechanism. The learner is told which
rule produced the date through ``interval_reason``, in their own words — never a reason code, an
evidence class or the word "rung".

Two rules are structural, not stylistic (``docs/MASTERY-PATH-POLICY.md`` §7): a failed review
writes no layer-2 pass event, so the objective keeps its rung instead of resetting to the first
one, and a pass advances exactly one rung via :func:`coursebook.mastery_path.review_step` instead
of jumping to the end of the ladder. ``needs_review`` stays in this queue; it never resets a
course and never locks the path.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db
from .mastery_path import DEFAULT_LADDER, LADDERS, review_step

#: Days until the next cold retrieval, per evidence target. The table itself lives in
#: :mod:`coursebook.mastery_path` so the generation policy and the scheduler cannot disagree.
#: A declared heuristic, not a law (research §5).
__all__ = ["LADDERS", "DEFAULT_LADDER", "queue", "item", "refresh_due", "apply_action"]

ACTIONS: tuple[str, ...] = ("snooze", "stretch", "drop", "resume")

#: Layer-1 event kinds owned by the scheduler. They are actions, never mastery evidence.
ACTION_KINDS = {
    "snooze": "review_snooze",
    "stretch": "review_stretch",
    "drop": "review_drop",
    "resume": "review_resume",
}

_CURRENT_PLAN = "pl.id = (SELECT id FROM plans WHERE course_id = pl.course_id AND state = 'approved' ORDER BY version DESC LIMIT 1)"

#: Objective states the queue may show. ``review_due``/``needs_review`` are already scheduled;
#: ``independent_evidence``/``delayed_evidence`` get their clock start from a cold layer-2 pass;
#: ``introduced`` is in because a non-cold pass that only introduced an objective is exactly the
#: claim a cold re-check must retire. Omitting it left the objectives that most need retrieval
#: as the only ones never scheduled.
ELIGIBLE_STATES: tuple[str, ...] = (
    "independent_evidence",
    "delayed_evidence",
    "review_due",
    "needs_review",
    "introduced",
)

#: The short beat a miss comes back on. It is the contract's minimum interval
#: (``review_item.interval_days`` has ``minimum: 1``): a miss earns a return sooner than any cold
#: rung of any ladder, never a same-day backlog entry.
MISS_RETURN_DAYS = 1

#: The rung a pass starts on when the attempt record shows it was earned unaided on the first
#: try. The ladder's floor stays reserved for a pass that needed help, so a cold first-try pass
#: earns exactly one rung more than a hinted one and two more than the short beat. A ladder with
#: a single rung cannot express that and keeps its floor.
COLD_START_RUNG = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _ladder(target: str | None) -> tuple[int, ...]:
    return LADDERS.get(str(target or ""), DEFAULT_LADDER)


def _events(connection, enrollment_id: str, objective_id: str) -> list[Any]:
    return connection.execute(
        "SELECT kind, created_at, rowid AS row_id FROM evidence"
        " WHERE enrollment_id = ? AND objective_id = ?"
        " AND kind IN ('independent_evidence','delayed_retrieval','review_snooze','review_stretch',"
        " 'review_drop','review_resume')"
        " ORDER BY created_at ASC, rowid ASC",
        (enrollment_id, objective_id),
    ).fetchall()


def _last_attempt(connection, enrollment_id: str, objective_id: str) -> Any:
    """The newest committed attempt for one objective, or ``None``.

    The evidence row is the learner-time record; ``verdict``/``evidence_class`` live on the
    attempt it is linked to. A ``needs_retry`` attempt is not committed and is excluded: a grading
    failure is not a verdict about the learner, so it may not move the schedule.
    """
    return connection.execute(
        "SELECT e.created_at AS created_at, e.rowid AS row_id, a.verdict AS verdict,"
        " a.evidence_class AS evidence_class"
        " FROM evidence e JOIN attempts a ON a.id = e.attempt_id"
        " WHERE e.enrollment_id = ? AND e.objective_id = ? AND e.layer = 1"
        " AND e.kind = 'attempt' AND a.state = 'committed'"
        " ORDER BY e.created_at DESC, e.rowid DESC LIMIT 1",
        (enrollment_id, objective_id),
    ).fetchone()


def _pass_record(connection, enrollment_id: str, objective_id: str, *, until: int,
                 since: int | None = None) -> dict[str, Any]:
    """The attempt record inside one evidence window, both bounds inclusive.

    The window is the committed attempts and the durable help events since the previous layer-2
    pass, inclusive of ``until`` — usually the pass itself. One pass, one window: an earlier
    cycle's hint cannot shorten a later cycle's spacing, and the record of a pack-imported
    objective is empty rather than borrowed from a neighbour.

    The bounds are evidence row ids, not timestamps. Row ids are the order the backend recorded
    the learner's actions in, and that is the question being asked ("what happened before this
    pass?"); an import or a repair that rewrites ``created_at`` must not be able to manufacture an
    attempt record that never existed.

    ``hints`` counts the rows the pane and the chat hook write before an answer (``hint_request``,
    ``answer_shown``), whether or not the answer consumed them: a consumed hint is linked to the
    attempt it contaminated, and it still happened.
    """
    since_clause = ""
    params: list[Any] = [enrollment_id, objective_id, int(until)]
    if since is not None:
        since_clause = " AND e.rowid > ?"
        params.append(int(since))
    attempts = connection.execute(
        "SELECT a.verdict AS verdict FROM evidence e JOIN attempts a ON a.id = e.attempt_id"
        " WHERE e.enrollment_id = ? AND e.objective_id = ? AND e.layer = 1"
        " AND e.kind = 'attempt' AND a.state = 'committed' AND e.rowid <= ?"
        + since_clause +
        " ORDER BY e.rowid ASC",
        tuple(params),
    ).fetchall()
    help_rows = connection.execute(
        "SELECT e.kind AS kind FROM evidence e"
        " WHERE e.enrollment_id = ? AND e.objective_id = ? AND e.layer = 1"
        " AND e.kind IN ('hint_request', 'answer_shown') AND e.rowid <= ?"
        + since_clause +
        " ORDER BY e.rowid ASC",
        tuple(params),
    ).fetchall()
    return {
        "attempts": len(attempts),
        "misses": sum(1 for row in attempts if str(row["verdict"]) != "pass"),
        "hints": sum(1 for row in help_rows if str(row["kind"]) == "hint_request"),
        "shown": any(str(row["kind"]) == "answer_shown" for row in help_rows),
    }


def _earned_rung(record: dict[str, Any], rungs: list[int]) -> int:
    """The rung the ladder *started* on, read from the record that opened it.

    One unaided first try earns one rung above the ladder's floor; a hint, a retry or a miss
    starts on the floor. This is the ladder's offset for its whole life — it is not re-decided by
    every review pass, which is why a later failed review keeps the rung it reached.
    """
    if not record["attempts"]:
        return 0                          # no record: earn nothing extra
    if record["hints"] or record["shown"] or record["misses"] or record["attempts"] > 1:
        return 0                          # the ladder began with help or a miss: the floor
    return min(COLD_START_RUNG, max(0, len(rungs) - 1))


def _short_beat(record: dict[str, Any]) -> bool:
    """Whether this cycle's pass was not available first time, so it returns on the short beat."""
    if not record["attempts"]:
        return False
    return bool(record["shown"] or record["misses"] or record["attempts"] > 1)


def _interval_reason(record: dict[str, Any], *, days: int) -> str | None:
    """Why this date, in the learner's words. ``None`` when there is no record to explain.

    Never a reason code, a stage name, an evidence class or the scheduler's own nouns: a learner
    reading this should see what they did, not the pipeline's name for it.
    """
    if not record["attempts"]:
        return None
    when = "tomorrow" if days == 1 else f"in {days} days"
    if record["shown"]:
        return f"The answer was shown, so this comes back {when}."
    if record["misses"]:
        return f"You missed it before you got it, so this comes back {when}."
    if record["attempts"] > 1:
        return f"You needed {record['attempts']} tries, so this comes back {when}."
    if record["hints"]:
        return f"You used a hint, so this comes back {when}."
    return f"You got this first try with no help, so this comes back {when}."


def _clock_start(passes: list[Any], attempt: Any,
                 ladder: tuple[int, ...]) -> tuple[Any, list[int]]:
    """``(created_at, rungs)`` for this objective's return clock, or ``(None, rungs)``.

    A cold layer-2 pass starts the declared ladder. An attempt that was *not* a cold pass starts
    the clock from that attempt:

    * on an objective that has never recorded a cold pass, the ladder has not started, so the
      return is its first rung — the short beat after a miss, the cold re-check when a non-cold
      pass only *introduced* the objective;
    * on an objective that already earned a rung, the rung is kept (a failed review never resets
      to the first rung, ``docs/MASTERY-PATH-POLICY.md`` §7) and a hinted pass simply does not
      advance it: the next return is the rung a cold pass would have left behind.
    """
    rungs = [int(step) for step in ladder]
    if attempt is not None and not (
        attempt["verdict"] == "pass" and attempt["evidence_class"] == "cold"
    ):
        if passes:
            return attempt["created_at"], rungs
        if attempt["verdict"] == "pass":
            return attempt["created_at"], rungs  # introduced: a cold re-check on the first rung
        return attempt["created_at"], [MISS_RETURN_DAYS] + rungs
    if passes:
        return passes[-1]["created_at"], rungs
    if attempt is not None:
        # A cold pass with no layer-2 row (a revisit records the pass without moving the
        # objective) still starts a return.
        return attempt["created_at"], rungs
    return None, rungs


def _item(connection, objective, *, enrollment_id: str, now: datetime) -> dict[str, Any] | None:
    """One schedulable objective, or ``None`` when it is not eligible."""
    events = _events(connection, enrollment_id, objective["id"])
    passes = [e for e in events if e["kind"] in ("independent_evidence", "delayed_retrieval")]
    attempt = _last_attempt(connection, enrollment_id, objective["id"])
    ladder = _ladder(objective["evidence_target"])
    start_at, rungs = _clock_start(passes, attempt, ladder)
    if start_at is None:
        return None
    # Two windows, because two different questions are being asked.
    #
    # The *ladder's* offset comes from the record that opened it (the first layer-2 pass), and
    # lasts for the ladder's whole life: one unaided first try starts it a rung up.
    ladder_until = int(passes[0]["row_id"]) if passes else (
        int(attempt["row_id"]) if attempt is not None else None)
    if ladder_until is None:  # pragma: no cover - _clock_start returned a start, so one exists
        return None
    ladder_record = _pass_record(connection, enrollment_id, objective["id"], until=ladder_until)
    start_index = _earned_rung(ladder_record, rungs)
    # The *current cycle's* record decides only whether this return is the short beat: it runs
    # back to the previous layer-2 pass, never further, so one cycle's help cannot shorten the
    # next cycle's spacing.
    if passes and str(passes[-1]["created_at"]) == str(start_at):
        until_row = int(passes[-1]["row_id"])
        previous_row = int(passes[-2]["row_id"]) if len(passes) > 1 else None
    elif attempt is not None:
        until_row = int(attempt["row_id"])
        previous_row = int(passes[-1]["row_id"]) if passes else None
    else:  # pragma: no cover - _clock_start only returns a start when one of the two exists
        return None
    current_record = _pass_record(connection, enrollment_id, objective["id"],
                                  until=until_row, since=previous_row)
    capped_days = MISS_RETURN_DAYS if _short_beat(current_record) else None
    dropped = False
    index = start_index
    base = _parse(start_at)
    for event in events:
        if event["kind"] == "review_drop":
            dropped = True
        elif event["kind"] == "review_resume":
            dropped = False
        elif event["kind"] == "review_snooze":
            base = _parse(event["created_at"])
        elif event["kind"] in ("review_stretch", "delayed_retrieval"):
            index = review_step(index, passed=True, ladder=rungs)
    if dropped or base is None:
        return None
    step = rungs[index] if rungs else 0
    if capped_days is not None and index <= start_index:
        # The ladder's floor is a target default, not a floor for a pass the record says was not
        # available first time: that pass returns sooner. A stretch the learner asked for still
        # wins, because it moves the index past the starting rung.
        step = min(step, capped_days)
    due = base + timedelta(days=step)
    return {
        "objective_id": objective["id"],
        "title": objective["title"],
        "ordinal": int(objective["ordinal"]),
        "evidence_target": objective["evidence_target"],
        "state": objective["state"],
        "interval_days": step,
        "step": index,
        "ladder_days": rungs,
        "last_evidence_at": start_at,
        "due_at": due.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "overdue": due < now,
        "overdue_days": max(0, (now - due).days) if due < now else 0,
        "interval_reason": _interval_reason(
            current_record if current_record["attempts"] else ladder_record, days=step),
    }


def _eligible_objectives(connection, enrollment_id: str) -> list[Any]:
    states = ", ".join(f"'{state}'" for state in ELIGIBLE_STATES)
    return connection.execute(
        "SELECT o.* FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        f" WHERE pl.course_id = (SELECT course_id FROM enrollments WHERE id = ?) AND {_CURRENT_PLAN}"
        f" AND o.state IN ({states})"
        " ORDER BY o.ordinal",
        (enrollment_id,),
    ).fetchall()


def _enrollment_id_for_objective(connection, objective_id: str) -> str:
    row = connection.execute(
        "SELECT e.id FROM enrollments e JOIN plans pl ON pl.course_id = e.course_id"
        " JOIN objectives o ON o.plan_id = pl.id WHERE o.id = ? ORDER BY e.rowid LIMIT 1",
        (objective_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"objective {objective_id} has no enrollment")
    return str(row["id"])


def queue(connection, enrollment_id: str, *, now: datetime | None = None,
          cap: int = 10, include_upcoming: bool = True) -> dict[str, Any]:
    """The review queue for one enrollment.

    ``due`` first (most overdue first), then upcoming by due date, bounded by ``cap``. The cap is
    a UI/attention limit; ``total_due`` and ``total_overdue`` are always the full counts so a
    hidden backlog can never look like an empty one.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    items = []
    for objective in _eligible_objectives(connection, enrollment_id):
        item = _item(connection, objective, enrollment_id=enrollment_id, now=now)
        if item is not None:
            items.append(item)
    due_items = sorted([i for i in items if i["overdue"]], key=lambda i: (i["due_at"], i["ordinal"]))
    upcoming = sorted([i for i in items if not i["overdue"]], key=lambda i: (i["due_at"], i["ordinal"]))
    limited = max(0, int(cap))
    return {
        "enrollment_id": enrollment_id,
        "now": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "cap": limited,
        "total_due": len(due_items),
        "total_overdue": len(due_items),
        "total_scheduled": len(items),
        "items": (due_items + upcoming)[:limited] if include_upcoming else due_items[:limited],
        "upcoming_hidden": max(0, len(upcoming) - limited),
    }


def item(connection, enrollment_id: str, objective_id: str, *,
         now: datetime | None = None) -> dict[str, Any] | None:
    """The derived queue item for exactly one objective, or ``None``.

    Same derivation as :func:`queue` without the cap. ``review.action`` needs the post-action
    ``due_at`` for the objective it just touched, and a capped queue may legitimately omit that
    row, so it cannot be read back out of ``queue()["items"]``.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    states = ", ".join(f"'{state}'" for state in ELIGIBLE_STATES)
    objective = connection.execute(
        "SELECT o.* FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        " WHERE o.id = ? AND pl.course_id = (SELECT course_id FROM enrollments WHERE id = ?)"
        f" AND {_CURRENT_PLAN} AND o.state IN ({states})",
        (objective_id, enrollment_id),
    ).fetchone()
    if objective is None:
        return None
    return _item(connection, objective, enrollment_id=enrollment_id, now=now)


def refresh_due(connection, enrollment_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Mark eligible objectives ``review_due`` when their date has passed.

    Idempotent: it only changes state in the contracted direction ``independent_evidence`` /
    ``delayed_evidence`` → ``review_due``. It never un-schedules, never writes new evidence rows
    and never touches ``needs_review`` (that objective already has an open problem) or
    ``introduced`` (a non-cold pass only opened it). Those two are still *scheduled*: :func:`queue`
    derives their short return from their own committed attempt, and relabelling them
    ``review_due`` here would claim a cold review the learner has not been given.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    marked: list[str] = []
    for objective in _eligible_objectives(connection, enrollment_id):
        if objective["state"] not in ("independent_evidence", "delayed_evidence"):
            continue
        item = _item(connection, objective, enrollment_id=enrollment_id, now=now)
        if item is None or not item["overdue"]:
            continue
        connection.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective["id"],))
        marked.append(objective["id"])
    return {"marked_due": marked, "count": len(marked)}


def apply_action(connection, *, enrollment_id: str, objective_id: str, action: str,
                 now: datetime | None = None) -> dict[str, Any]:
    """Record a learner review action as a durable layer-1 event.

    ``snooze`` restarts one interval from now, ``stretch`` advances the interval step, ``drop``
    removes the item from the queue, ``resume`` puts it back. Each is a scheduling preference,
    recorded as ``self_reported`` — never as evidence that the objective is known or unknown.
    """
    if action not in ACTION_KINDS:
        raise ValueError(f"unknown review action {action!r}")
    objective = connection.execute("SELECT * FROM objectives WHERE id = ?", (objective_id,)).fetchone()
    if objective is None:
        raise LookupError(f"objective {objective_id} does not exist")
    now_iso = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
    connection.execute(
        "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class, created_at)"
        " VALUES (?, ?, ?, NULL, 1, ?, 'self_reported', ?)",
        (f"evd_{uuid.uuid4().hex}", enrollment_id, objective_id, ACTION_KINDS[action], now_iso),
    )
    state = str(objective["state"])
    if action == "drop" and state in ("review_due", "delayed_evidence"):
        connection.execute(
            "UPDATE objectives SET state = 'independent_evidence' WHERE id = ?", (objective_id,)
        )
    if action == "resume" and state == "independent_evidence":
        connection.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective_id,))
    return {"objective_id": objective_id, "action": action, "recorded_at": now_iso}
