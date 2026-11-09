"""Game-only engagement layer: XP, cosmetic levels and ``Game progress`` (GM-009).

The owner override recorded in ``docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`` §10B permits XP, levels
and a game progress bar **in game mode only**, because the mode must be fun rather than a textbook
with a skin. That permission is bounded by one structural rule: the play layer is not learning
evidence. This module therefore:

* awards XP only for a **named real action** that already exists as a durable row — a lesson
  segment of this enrollment, a committed attempt, a completed review retrieval, a completed
  homework task, or a return to a lesson run at least a day after the previous run. There is no
  timer, no page-open and no click action, and the wire enum has no value for one;
* writes only ``game_engagement`` rows. It never writes an attempt, a transition, an objective
  state or an evidence row, and no evidence, parent, pack, course-export or print read joins it;
* is idempotent twice over: one ``(enrollment_id, action_kind, action_id)`` row at most, and the
  standard envelope idempotency key replays the stored answer (a different payload under the same
  key is ``IDEMPOTENCY_CONFLICT``);
* derives the level from accumulated XP as a cosmetic label and returns counts for ``Game
  progress`` — never a mastery percentage and never a claim about skill;
* is refused outside a ``game`` course. A Textbook (or legacy ``NULL``) course has no engagement
  surface; switching modes retains the rows and switching back restores the same layer.

``Game feedback`` is a declared plugin setting read by :func:`configure_feedback`. Turning it off
hides the layer in the returned read model (``progress.feedback_visible = false`` and no recent
events) while every ledger row and the XP total stay intact. It never deletes play history.

The module registers its two commands itself, exactly like ``pronunciation`` and ``syllabus``: a
build whose frozen ``cb.rpc`` lacks ``engagement.read``/``engagement.award`` stays
``NOT_IMPLEMENTED`` instead of inventing a method.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from . import db, gm_contract
from .api import RpcError
from .contracts import method_names

#: Points per named real action (§10B.2). A value is a product decision, shown here so a test and
#: a future UI read the same number instead of hardcoding one in JavaScript.
XP_POINTS: dict[str, int] = {
    gm_contract.EngagementAction.LESSON_STEP.value: 5,
    gm_contract.EngagementAction.CHECK_SUBMITTED.value: 20,
    gm_contract.EngagementAction.REVIEW.value: 15,
    gm_contract.EngagementAction.HOMEWORK_COMPLETED.value: 25,
    gm_contract.EngagementAction.RETURNED.value: 10,
}

#: Cosmetic level width. A level is a label, never a gate: nothing in the course reads this.
XP_PER_LEVEL = 100

#: Cosmetic titles, cycled. None of these names a skill, credential or mastery claim.
LEVEL_TITLES: tuple[str, ...] = (
    "Curious",
    "Explorer",
    "Pathfinder",
    "Wayfinder",
    "Trailblazer",
    "Luminary",
)

#: Bound on the recent-event preview the Game header renders.
RECENT_EVENTS_LIMIT = 20

#: A return needs a real interval between two recorded lesson runs. One day is the smallest
#: interval this slice recognises; a shorter gap is not a return.
RETURN_INTERVAL_DAYS = 1.0

_read_setting: Callable[[str, Any], Any] | None = None


def configure_feedback(read_setting: Callable[[str, Any], Any] | None) -> None:
    """Bind the plugin settings reader for the ``game_feedback`` preference once, at register."""
    global _read_setting
    _read_setting = read_setting


def feedback_enabled() -> bool:
    """Whether the Game surface should show the play layer. Defaults to on."""
    if _read_setting is None:
        return True
    try:
        value = _read_setting("game_feedback", True)
    except Exception:  # noqa: BLE001 - a broken settings file must not hide the player's ledger
        return True
    return True if value is None else bool(value)


def level_for(xp_total: int) -> dict[str, Any]:
    """The cosmetic level object for *xp_total*. Pure and display-derived."""
    total = max(0, int(xp_total))
    level = 1 + total // XP_PER_LEVEL
    title = LEVEL_TITLES[(level - 1) % len(LEVEL_TITLES)]
    return {
        "level": level,
        "title": title,
        "xp_into_level": total % XP_PER_LEVEL,
        "xp_for_next_level": XP_PER_LEVEL,
        "is_cosmetic": True,
    }


def _kernel() -> Any:
    """The kernel's fence helpers, imported lazily to avoid an import cycle with ``domain``."""
    from . import domain

    return domain


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _performance(course_id: str, enrollment_id: str) -> RpcError:
    return RpcError.of(
        "VALIDATION_FAILED",
        "the game engagement layer exists only for a game course.",
        reason="engagement_is_game_only",
        course_id=course_id,
        enrollment_id=enrollment_id,
    )


def _require_context(connection, course_id: str, enrollment_id: str) -> Any:
    """Resolve the enrollment, prove it belongs to the course, and prove the course is a game."""
    kernel = _kernel()
    enrollment = kernel._enrollment(connection, enrollment_id)
    if str(enrollment["course_id"]) != str(course_id):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "that enrollment does not belong to this course.",
            field="enrollment_id",
            reason="enrollment_not_in_course",
        )
    course = connection.execute(
        "SELECT id, presentation_mode FROM courses WHERE id = ?", (course_id,)
    ).fetchone()
    if course is None:
        raise kernel._not_found("course", course_id)
    if gm_contract.read_presentation_mode(course["presentation_mode"]) != (
        gm_contract.PresentationMode.GAME.value
    ):
        raise _performance(str(course_id), str(enrollment_id))
    return enrollment


def _real_action(connection, kind: str, action_id: str, enrollment_id: str) -> bool:
    """True only when *action_id* names a durable row this enrollment actually produced.

    Each branch reads the table that already owns the action. Nothing is inferred from a timestamp
    typed by the caller: a click or a timer has no row here, so it cannot be priced.
    """
    if kind == gm_contract.EngagementAction.LESSON_STEP.value:
        row = connection.execute(
            "SELECT 1 FROM lesson_segments s JOIN lesson_runs r ON r.id = s.lesson_run_id"
            " WHERE s.id = ? AND r.enrollment_id = ?",
            (action_id, enrollment_id),
        ).fetchone()
        return row is not None
    if kind == gm_contract.EngagementAction.CHECK_SUBMITTED.value:
        row = connection.execute(
            "SELECT 1 FROM attempts WHERE id = ? AND enrollment_id = ? AND state = 'committed'",
            (action_id, enrollment_id),
        ).fetchone()
        return row is not None
    if kind == gm_contract.EngagementAction.REVIEW.value:
        # A completed scheduled review writes a layer-2 ``delayed_retrieval`` row. Scheduling
        # actions (snooze/stretch) are not a review and cannot be priced as one.
        row = connection.execute(
            "SELECT 1 FROM evidence WHERE id = ? AND enrollment_id = ?"
            " AND kind = 'delayed_retrieval'",
            (action_id, enrollment_id),
        ).fetchone()
        return row is not None
    if kind == gm_contract.EngagementAction.HOMEWORK_COMPLETED.value:
        placeholders = ", ".join("?" for _ in gm_contract.HOMEWORK_COMPLETION_STATES)
        row = connection.execute(
            f"SELECT 1 FROM homework_tasks WHERE id = ? AND enrollment_id = ?"
            f" AND state IN ({placeholders})",
            (action_id, enrollment_id, *gm_contract.HOMEWORK_COMPLETION_STATES),
        ).fetchone()
        return row is not None
    if kind == gm_contract.EngagementAction.RETURNED.value:
        row = connection.execute(
            "SELECT 1 FROM lesson_runs r WHERE r.id = ? AND r.enrollment_id = ?"
            " AND EXISTS (SELECT 1 FROM lesson_runs p WHERE p.enrollment_id = r.enrollment_id"
            "             AND julianday(p.created_at) <= julianday(r.created_at) - ?)",
            (action_id, enrollment_id, RETURN_INTERVAL_DAYS),
        ).fetchone()
        return row is not None
    return False


def _xp_total(connection, enrollment_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(points), 0) AS total FROM game_engagement WHERE enrollment_id = ?",
        (enrollment_id,),
    ).fetchone()
    return int(row["total"])


def _progress(connection, course_id: str, enrollment_id: str) -> dict[str, Any]:
    """Assigned steps in the current plan and steps with a committed pass. Counts, no percent."""
    plan = connection.execute(
        "SELECT id FROM plans WHERE course_id = ? AND state = 'approved'"
        " ORDER BY version DESC LIMIT 1",
        (course_id,),
    ).fetchone()
    if plan is None:
        plan = connection.execute(
            "SELECT id FROM plans WHERE course_id = ? ORDER BY version DESC LIMIT 1",
            (course_id,),
        ).fetchone()
    assigned = 0
    if plan is not None:
        assigned = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM objectives WHERE plan_id = ?", (plan["id"],)
            ).fetchone()["n"]
        )
    completed = int(
        connection.execute(
            "SELECT COUNT(DISTINCT c.objective_id) AS n FROM attempts a"
            " JOIN checks c ON c.id = a.check_id"
            " WHERE a.enrollment_id = ? AND a.state = 'committed' AND a.verdict = 'pass'",
            (enrollment_id,),
        ).fetchone()["n"]
    )
    return {
        "label": "Game progress",
        "is_play_progress": True,
        "assigned_steps": assigned,
        "completed_steps": completed,
        "feedback_visible": feedback_enabled(),
    }


def _recent(connection, enrollment_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT action_kind, action_id, points, level_after, created_at FROM game_engagement"
        " WHERE enrollment_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (enrollment_id, RECENT_EVENTS_LIMIT),
    ).fetchall()
    return [
        {
            "action_kind": row["action_kind"],
            "action_id": row["action_id"],
            "points": int(row["points"]),
            "level_after": None if row["level_after"] is None else int(row["level_after"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def read_model(connection, course_id: str, enrollment_id: str) -> dict[str, Any]:
    """The Game header read model. Pure read; no row is written and no revision moves."""
    _require_context(connection, course_id, enrollment_id)
    total = _xp_total(connection, enrollment_id)
    return {
        "xp_total": total,
        "level": level_for(total),
        "progress": _progress(connection, course_id, enrollment_id),
        "recent_events": _recent(connection, enrollment_id) if feedback_enabled() else [],
    }


# ── handlers ────────────────────────────────────────────────────────────────


def read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``engagement.read``: the Game header only, refused outside a game course."""
    db.ensure_schema()
    with db.read() as connection:
        result = read_model(connection, payload["course_id"], payload["enrollment_id"])
    return 0, result


def award(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``engagement.award``: append one XP event for one real action, idempotently."""
    db.ensure_schema()
    kernel = _kernel()
    method = "engagement.award"
    payload_hash = kernel._payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    course_id = str(payload["course_id"])
    enrollment_id = str(payload["enrollment_id"])
    kind = str(payload["action_kind"])
    action_id = str(payload["action_id"])
    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        _require_context(connection, course_id, enrollment_id)

        points = XP_POINTS.get(kind)
        if points is None:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "that action is not a named engagement action.",
                field="action_kind",
                reason="unknown_action_kind",
            )
        if not _real_action(connection, kind, action_id, enrollment_id):
            raise RpcError.of(
                "VALIDATION_FAILED",
                "XP is awarded only for a real recorded action; that action id is not one.",
                field="action_id",
                reason="not_a_real_action",
            )

        recorded = connection.execute(
            "SELECT points FROM game_engagement WHERE enrollment_id = ? AND action_kind = ?"
            " AND action_id = ?",
            (enrollment_id, kind, action_id),
        ).fetchone()
        if recorded is not None:
            total = _xp_total(connection, enrollment_id)
            result = {
                "awarded": False,
                "points": 0,
                "xp_total": total,
                "level": level_for(total),
            }
            kernel._remember(
                connection, key, method, payload_hash,
                envelope.get("operation_id", ""), 0, result,
            )
            return 0, result

        total = _xp_total(connection, enrollment_id) + points
        level = level_for(total)
        connection.execute(
            "INSERT INTO game_engagement (id, course_id, enrollment_id, action_kind, action_id,"
            " points, level_after, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_new_id("eng"), course_id, enrollment_id, kind, action_id, points,
             int(level["level"]), db.utcnow()),
        )
        result = {
            "awarded": True,
            "points": points,
            "xp_total": total,
            "level": level,
        }
        kernel._remember(
            connection, key, method, payload_hash,
            envelope.get("operation_id", ""), 0, result,
        )
    return 0, result


HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[int, dict[str, Any]]]] = {
    "engagement.read": read,
    "engagement.award": award,
}


def ensure_registered() -> tuple[str, ...]:
    available = set(method_names())
    registered: list[str] = []
    for method, handler in HANDLERS.items():
        if method in available:
            from . import api

            api.register_handler(method, handler)
            registered.append(method)
    return tuple(sorted(registered))


ensure_registered()
