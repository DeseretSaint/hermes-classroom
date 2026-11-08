"""Review queue scheduler: due, overdue, cap, snooze, stretch, drop.

The queue is **derived** from committed evidence, not from a separate authoritative table. That is
a deliberate constraint of ``cb.db`` v2, which has no review-schedule table: a second copy of
"what is due" would be a competing authority (``AUDIT.md`` R5). What is durable is the evidence:

* a cold layer-2 pass (``independent_evidence`` / ``delayed_retrieval``) is the clock start;
* learner review actions are layer-1 events (``review_snooze``, ``review_stretch``,
  ``review_drop``) recorded with ``evidence_class='self_reported'`` — the learner's own statement
  about scheduling, never evidence of mastery;
* the objective's ``review_due`` state is the contracted surface the library and lesson pane read.

Intervals are a declared **heuristic**, not a validated forgetting curve (``AUDIT.md`` R9/R10):
the ladder is a product default, shown to the learner, and never presented as an attainment
prediction.

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
#: ``independent_evidence``/``delayed_evidence`` get their clock start from a cold layer-2 pass.
ELIGIBLE_STATES: tuple[str, ...] = (
    "independent_evidence",
    "delayed_evidence",
    "review_due",
    "needs_review",
)


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
        "SELECT kind, created_at FROM evidence WHERE enrollment_id = ? AND objective_id = ?"
        " AND kind IN ('independent_evidence','delayed_retrieval','review_snooze','review_stretch',"
        " 'review_drop','review_resume')"
        " ORDER BY created_at ASC, rowid ASC",
        (enrollment_id, objective_id),
    ).fetchall()


def _item(connection, objective, *, enrollment_id: str, now: datetime) -> dict[str, Any] | None:
    """One schedulable objective, or ``None`` when it is not eligible."""
    events = _events(connection, enrollment_id, objective["id"])
    passes = [e for e in events if e["kind"] in ("independent_evidence", "delayed_retrieval")]
    if not passes:
        return None
    dropped = False
    index = 0
    base = _parse(passes[-1]["created_at"])
    ladder = _ladder(objective["evidence_target"])
    for event in events:
        if event["kind"] == "review_drop":
            dropped = True
        elif event["kind"] == "review_resume":
            dropped = False
        elif event["kind"] == "review_snooze":
            base = _parse(event["created_at"])
        elif event["kind"] == "review_stretch":
            index = review_step(index, passed=True, ladder=ladder)
        elif event["kind"] == "delayed_retrieval":
            index = review_step(index, passed=True, ladder=ladder)
    if dropped or base is None:
        return None
    step = ladder[index]
    due = base + timedelta(days=step)
    return {
        "objective_id": objective["id"],
        "title": objective["title"],
        "ordinal": int(objective["ordinal"]),
        "evidence_target": objective["evidence_target"],
        "state": objective["state"],
        "interval_days": step,
        "step": index,
        "ladder_days": list(ladder),
        "last_evidence_at": passes[-1]["created_at"],
        "due_at": due.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "overdue": due < now,
        "overdue_days": max(0, (now - due).days) if due < now else 0,
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
    and never touches ``needs_review`` (that objective already has an open problem).
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
