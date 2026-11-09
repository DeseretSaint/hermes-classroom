"""Coursebook-owned tools exposed to the agent.

``coursebook_status`` is read-only introspection: it can be honest before anything else exists.
``coursebook_due`` is the learner-facing read: it answers "what is waiting on me?" from the same
profile-scoped SQLite store the Desktop reads (``library.list``'s next step and the derived
``review.queue``), and it writes nothing — no reminder, no plan, no review, no provider call.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import __version__
from . import api, db, domain

STATUS_TOOL_NAME = "coursebook_status"
STATUS_TOOL_DESCRIPTION = (
    "Report Coursebook backend health: plugin version, wire contract version, SQLite schema "
    "state for the active profile, and whether a cross-model validator route is configured. "
    "Read-only; use it to diagnose why the Coursebook pane is degraded or whether a generated "
    "course can be checked by a different model instead of guessing."
)

#: Manifest ``config_schema`` keys this build actually reads. Declaring a setting nothing
#: consumes is a partially wired control, so the schema and this table move together.
#: ``validator_model`` / ``validator_provider`` are read by ``__init__.py::register`` (they bind the
#: validation route before ``coursebook.tools`` is ever invoked), not by this module.
CONFIG_KEYS: tuple[str, ...] = (
    "status_include_contracts",
    "validator_model",
    "validator_provider",
)
DEFAULT_STATUS_INCLUDE_CONTRACTS = True

_read_setting: Callable[[str, Any], Any] | None = None


def configure(read_setting: Callable[[str, Any], Any] | None) -> None:
    """Bind the plugin's settings reader (``ctx.get_config``) once, at register time.

    The reader is the documented agent-half API for ``plugins.entries.coursebook.settings.*``.
    Tool handlers receive only their own kwargs, so this is how a declared setting reaches them.
    """
    global _read_setting
    _read_setting = read_setting


def _setting(key: str, default: Any) -> Any:
    if _read_setting is None:
        return default
    try:
        value = _read_setting(key, default)
    except Exception:  # noqa: BLE001 - a broken settings file must not break a status read
        return default
    return default if value is None else value


def status_schema() -> dict[str, Any]:
    return {
        "name": STATUS_TOOL_NAME,
        "description": STATUS_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def status_handler(args: dict[str, Any] | None = None, **_kwargs: Any) -> str:
    """Return a JSON string; the shape is the ``health.get`` response body plus diagnostics.

    The host dispatches every registered tool as ``entry.handler(args, **kwargs)`` — the model's
    argument dict arrives **positionally** (``tools/registry.py::dispatch``), and only the
    context kwargs the signature names are forwarded. ``args`` is accepted here because the tool
    schema declares no parameters; naming it positionally, rather than only as ``**kwargs``, is
    what keeps ``coursebook_status`` callable through the registry at all.
    """
    payload = {
        "plugin_version": __version__,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "db": _db_health(),
        "validator": _validator_status(),
        "implemented_methods": list(api.implemented_methods()),
    }
    if bool(_setting("status_include_contracts", DEFAULT_STATUS_INCLUDE_CONTRACTS)):
        payload["contracts"] = api.contract_summary()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _db_health() -> dict[str, Any]:
    try:
        return db.health()
    except Exception as exc:  # noqa: BLE001 - a status tool reports failure, it never raises
        return {"ready": False, "schema_version": None, "error": type(exc).__name__}


def _validator_status() -> dict[str, Any]:
    """Report whether a cross-model validator route is *declared*, and never more than that.

    The values come from ``generation.validator_config()`` — the same settings ``register`` used
    to bind the route. This says nothing about whether the provider answered; a configured route
    still fails loudly at call time if the host trust gate refuses the override. Read locally: no
    secret is involved, and the block is exactly
    ``{configured, provider, model, reason, output_bound}``. ``output_bound`` is the declared
    validator output cap (H-192c): ``registered`` is false when the host would not accept the
    auxiliary task, which means no cap is applied.
    """
    try:
        from . import generation

        config = generation.validator_config()
        return {
            "configured": bool(config.get("configured")),
            "provider": config.get("provider"),
            "model": config.get("model"),
            "reason": str(config.get("reason") or ""),
            "output_bound": dict(config.get("output_bound") or {}),
        }
    except Exception as exc:  # noqa: BLE001 - a status read must never take the tool down
        return {
            "configured": False,
            "provider": None,
            "model": None,
            "reason": (
                "the validator configuration could not be read "
                f"({type(exc).__name__}); treat the route as unconfigured"
            ),
        }


# ── coursebook_due: the learner's next real step, read only ─────────────────
#
# The Desktop home answers "what do I do next?" from `library.list` (the row's next_step) and
# `review.queue` (the derived, evidence-dated review count). The agent gets the same answer from
# the same profile-scoped store here. Two deliberate constraints:
#
# * No `db.ensure_schema()` and no transaction: this tool never provisions, never runs the
#   library's `refresh_due` write tick and never advances a revision. Its review count is derived
#   from evidence dates, exactly what `refresh_due` would mark on the next real read. A tool that
#   silently wrote a scheduler state would not be a read.
# * No provider call, no RPC dispatch and no host seam: every field is a stored column or an
#   existing pure derivation (`domain._library_next_step`, `review.queue`). Nothing is invented.

DUE_TOOL_NAME = "coursebook_due"
DUE_TOOL_DESCRIPTION = (
    "List the learner's next real Coursebook step from this Hermes profile's local SQLite store: "
    "each active classroom, the same next step the Coursebook desktop shows, its current section "
    "and check state, and the backend's derived review count when a review is overdue. "
    "Read-only and profile-scoped: it uses the host's active profile store (there is no profile "
    "argument), writes nothing, starts no reminder, invents no plan or review, and makes no "
    "provider or network call. Optional course_id narrows one classroom; an unknown id is refused "
    "with NOT_FOUND, and an unavailable database is reported as available:false, never as an empty "
    "list that looks like 'nothing due'."
)

#: Rows returned by one call. The library caps a page at 100; the due answer obeys the same bound.
DUE_MAX_COURSES = 100

#: The plan `library.list` and `_library_next_step` resolve: approved first, else the newest.
_CURRENT_PLAN = (
    "pl.id = (SELECT id FROM plans WHERE course_id = pl.course_id"
    " ORDER BY (state = 'approved') DESC, version DESC LIMIT 1)"
)


class _UnknownCourse(Exception):
    def __init__(self, course_id: str) -> None:
        self.course_id = course_id
        super().__init__(course_id)


class _Unavailable(Exception):
    """The store cannot answer. ``reason`` is a stable token, never a fabricated empty list."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def due_schema() -> dict[str, Any]:
    return {
        "name": DUE_TOOL_NAME,
        "description": DUE_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "course_id": {
                    "type": "string",
                    "description": (
                        "Optional Coursebook course id (for example 'course_…') to narrow the "
                        "answer to one classroom. Omit for every active classroom in this profile."
                    ),
                }
            },
            "additionalProperties": False,
        },
    }


def due_handler(args: dict[str, Any] | None = None, **_kwargs: Any) -> str:
    """Return a JSON string; read-only and side-effect free.

    Shape: ``{available, reason?, due: [...], next: {...}|null, checked_at}``. ``due`` is ordered
    by the backend: overdue reviews first, then most recently touched. ``next`` is the first row,
    or ``null`` when the store genuinely holds nothing waiting.
    """
    args = args if isinstance(args, dict) else {}
    checked_at = db.utcnow()
    course_id = args.get("course_id")
    if isinstance(course_id, str):
        course_id = course_id.strip() or None
    if course_id is not None and not isinstance(course_id, str):
        return json.dumps(
            {
                "available": False,
                "reason": "invalid_course_id",
                "error": _error("VALIDATION_FAILED", "course_id must be a string.", field="course_id"),
                "due": [],
                "next": None,
                "checked_at": checked_at,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    try:
        due = _due_rows(str(course_id) if course_id else None)
    except _UnknownCourse as exc:
        return json.dumps(
            {
                "available": False,
                "reason": "unknown_course",
                "error": _error(
                    "NOT_FOUND",
                    f"course {exc.course_id} does not exist in this profile's Coursebook store.",
                    id=exc.course_id,
                ),
                "due": [],
                "next": None,
                "checked_at": checked_at,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    except _Unavailable as exc:
        return _unavailable(exc.reason, checked_at)
    except Exception as exc:  # noqa: BLE001 - a read tool reports failure, it never raises
        reason = "database_unavailable" if isinstance(exc, db.DatabaseUnavailable) else "read_failed"
        return _unavailable(reason, checked_at)
    return json.dumps(
        {
            "available": True,
            "due": due,
            "next": due[0] if due else None,
            "checked_at": checked_at,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    """The frozen ``cb.errors`` object, built by the package's own contract helper."""
    from .contracts import build_error

    return build_error(code, message, **details)


def _unavailable(reason: str, checked_at: str) -> str:
    return json.dumps(
        {
            "available": False,
            "reason": reason,
            "due": [],
            "next": None,
            "checked_at": checked_at,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _due_rows(course_id: str | None) -> list[dict[str, Any]]:
    """The active classrooms and their next step, from one short-lived read connection."""
    from . import domain, review

    if not db.store_exists():
        # Nothing has been provisioned for this profile. That is not "nothing due".
        raise _Unavailable("no_database")
    try:
        version = db.applied_schema_version()
        target = db.target_schema_version()
    except Exception as exc:  # noqa: BLE001 - an unreadable store is unavailable, not empty
        raise _Unavailable("database_unavailable") from exc
    if version is None or version < target:
        # Reading before migrations is not "empty"; it is "this store cannot answer yet".
        raise _Unavailable("schema_not_migrated")

    with db.read() as connection:
        if course_id is not None:
            exists = connection.execute(
                "SELECT id FROM courses WHERE id = ? AND status != 'deleted'", (course_id,)
            ).fetchone()
            if exists is None:
                raise _UnknownCourse(course_id)
        clauses = ["c.status != 'deleted'", "e.status IN ('active', 'paused')"]
        params: list[Any] = []
        if course_id is not None:
            clauses.append("c.id = ?")
            params.append(course_id)
        rows = connection.execute(
            "SELECT e.id AS enrollment_id, e.updated_at AS updated_at, e.rowid AS enrollment_rowid,"
            " c.id AS course_id, c.title AS title, c.pack_id AS pack_id"
            " FROM enrollments e JOIN courses c ON c.id = e.course_id"
            f" WHERE {' AND '.join(clauses)}"
            " ORDER BY e.updated_at DESC, e.rowid DESC LIMIT ?",
            (*params, DUE_MAX_COURSES),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            enrollment = {"id": row["enrollment_id"]}
            course = {"id": row["course_id"], "pack_id": row["pack_id"]}
            # The declared cap only bounds returned rows; total_due is always the full count.
            queue = review.queue(
                connection, row["enrollment_id"], cap=1, include_upcoming=False
            )
            due_count = int(queue.get("total_due") or 0)
            next_step = dict(domain._library_next_step(connection, enrollment, course))
            if due_count > 0 and next_step.get("kind") != "resolve_review_due":
                # `refresh_due` would mark these eligible objectives `review_due` on the next
                # Desktop read. This read does not write it; it reports the same next move.
                next_step = {
                    "kind": "resolve_review_due",
                    "label": f"Review {due_count} objective(s)",
                }
            section, check = _section_and_check(
                connection,
                course_id=row["course_id"],
                enrollment_id=row["enrollment_id"],
                next_step=next_step,
                queue=queue,
            )
            item: dict[str, Any] = {
                "course_id": row["course_id"],
                "title": row["title"],
                "next_step": next_step,
                "section": section,
                "check": check,
            }
            if due_count > 0:
                item["due_count"] = due_count
            items.append(item)
    # `library.list` sorts `next_step` by the review-due count, then recency. `rows` is already
    # recency-ordered, so a stable sort on the count preserves that tiebreak.
    items.sort(key=lambda item: -int(item.get("due_count") or 0))
    return items


def _section_and_check(
    connection,
    *,
    course_id: str,
    enrollment_id: str,
    next_step: dict[str, Any],
    queue: dict[str, Any],
) -> tuple[str | None, str | None]:
    """The section the next step opens and that objective's stored check state.

    Identity comes from the backend's own row (objective id), never from the label text. A step
    that opens no objective (a plan/pack review) answers ``(None, None)`` rather than guessing.
    """
    kind = str(next_step.get("kind") or "")
    objective_id: str | None = None
    if kind == "resolve_review_due":
        queued = queue.get("items") or []
        if queued:
            objective_id = str(queued[0]["objective_id"])
        else:
            found = connection.execute(
                "SELECT o.id FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
                f" WHERE pl.course_id = ? AND {_CURRENT_PLAN}"
                " AND o.state IN ('review_due', 'needs_review')"
                " ORDER BY o.ordinal LIMIT 1",
                (course_id,),
            ).fetchone()
            objective_id = str(found["id"]) if found is not None else None
    elif kind in ("resume_lesson", "rebind_session", "start_lesson"):
        # H-186: every kind that opens a section must open the same objective the label names.
        # Ordering by lesson-run recency returned the last imported run instead of the current
        # objective, and the ordinal-based answer is shared with `domain._library_next_step`.
        current = domain._current_objective(connection, course_id)
        objective_id = str(current["id"]) if current is not None else None
    if objective_id is None:
        return None, None
    row = connection.execute(
        "SELECT o.title AS title,"
        " (SELECT c.state FROM checks c WHERE c.objective_id = o.id"
        "   ORDER BY c.version DESC LIMIT 1) AS check_state"
        " FROM objectives o WHERE o.id = ?",
        (objective_id,),
    ).fetchone()
    if row is None:
        return None, None
    return str(row["title"]), str(row["check_state"] or "none")
