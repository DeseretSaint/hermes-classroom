"""Read-only job activity for a polling client (H-139, backend half of H-117).

The pane needs to tell a long wait from a broken one. That answer already exists in durable
state — the job row's ``state``/``progress_json`` and the ``usage_events`` rows recorded against
the job id — so this module only *reads* it into one object. It is deliberately not a second job
engine and it invents nothing:

* ``stage`` is the last stage the backend checkpointed, or the stage the queued brief names;
* ``steps_total`` stays null until the backend knows it; there is no percentage;
* ``elapsed_seconds`` carries the basis it measured (``created_to_now`` while live,
  ``created_to_updated`` once the row rests);
* ``usage`` is summed from recorded ``usage_events`` for this job id, and a token field that no
  recorded call exposed stays ``null`` instead of a zero that would read as "nothing spent".

A durable progress column that cannot be parsed is a named read failure, never an empty progress
object: answering ``queued``/``0`` for a corrupt row would tell the user work had not started when
the truth is that this build cannot say. :func:`activity_for` raises
:class:`JobRecordUnreadable` and the RPC layer turns that into a typed error envelope.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import jobs as jobs_contract

#: States in which the job is still expected to advance. Every other state rests: its elapsed
#: time is measured to ``updated_at`` and it will not grow while the client watches.
LIVE_STATES = frozenset({"queued", "running", "cancel_requested", "cancelling"})

#: The four token fields a client may render. Names match ``usage.summary`` so one meter reads
#: the same numbers from both commands.
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_write")

#: Recorded aliases the generation writer uses for the two uncached counts. Reading a recorded
#: field is not an estimate; it is the same measurement under the name it was stored with.
TOKEN_ALIASES = {"input": ("input", "input_tokens"), "output": ("output", "output_tokens")}

_MAX_NAMES = 10


class JobRecordUnreadable(Exception):
    """A durable JSON column for this job cannot be parsed, so its activity is unknown.

    ``column`` names the surface (``progress_json`` or ``brief_json``) so the error envelope can
    say which read failed instead of a generic internal failure.
    """

    def __init__(self, job_id: str, column: str, cause: BaseException | None = None) -> None:
        self.job_id = str(job_id)
        self.column = column
        self.cause_type = type(cause).__name__ if cause is not None else None
        super().__init__(f"job {self.job_id}: {column} is not readable")
        if cause is not None:
            self.__cause__ = cause


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    # A durable stamp without an offset is UTC by this backend's own writer; treating it as
    # naive would make elapsed arithmetic raise instead of reporting a number.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _object(value: Any, job_id: str, column: str) -> dict[str, Any]:
    """Parse one durable JSON object column, raising on corruption rather than defaulting."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise JobRecordUnreadable(job_id, column, exc) from exc
    if not isinstance(parsed, dict):
        raise JobRecordUnreadable(job_id, column, TypeError("column is not a JSON object"))
    return parsed


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _stage(progress: dict[str, Any], brief: dict[str, Any], state: str) -> tuple[str | None, str]:
    recorded = progress.get("stage")
    if isinstance(recorded, str) and recorded:
        return recorded[:80], "checkpoint"
    named = brief.get("stage")
    if isinstance(named, str) and named:
        return named[:80], "brief"
    if state == "queued":
        return None, "queued"
    return None, "none"


def activity_for(
    row: Any, *, now: datetime | None = None, usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The ``job.activity`` object for one ``jobs`` row. Pure read; never writes.

    ``row`` is a row from ``SELECT * FROM jobs``. ``now`` exists so a test can measure elapsed
    time deterministically; the RPC path passes nothing. ``usage`` is supplied by
    :func:`activity_with_usage`; on its own this returns the empty contract-legal usage object,
    never a partial one.
    """
    job_id = str(row["id"])
    state = str(row["state"])
    progress = _object(row["progress_json"], job_id, "progress_json")
    brief = _object(row["brief_json"], job_id, "brief_json")

    stage, stage_source = _stage(progress, brief, state)
    stages = [item for item in (progress.get("stages") or []) if isinstance(item, dict)]
    last_progress_at = None
    if stages:
        recorded_at = stages[-1].get("at")
        last_progress_at = recorded_at if isinstance(recorded_at, str) else None

    live = state in LIVE_STATES
    created = _parse(row["created_at"])
    if created is None:
        elapsed: int | None = None
        basis = "created_to_now" if live else "created_to_updated"
    else:
        end = (now or datetime.now(timezone.utc)) if live else (_parse(row["updated_at"]) or created)
        elapsed = max(0, int((end - created).total_seconds()))
        basis = "created_to_now" if live else "created_to_updated"

    return {
        "stage": stage,
        "stage_source": stage_source,
        "steps_done": _int_or_none(progress.get("steps_done")) or 0,
        "steps_total": _int_or_none(progress.get("steps_total")),
        "elapsed_seconds": elapsed,
        "elapsed_basis": basis,
        "can_cancel": jobs_contract.cancellable(state),
        "can_retry": state in ("failed", "interrupted_requires_retry"),
        "terminal": jobs_contract.is_terminal(state),
        "readable": True,
        "message": str(progress.get("message") or "")[:300],
        "last_progress_at": last_progress_at,
        "usage": dict(usage) if usage is not None else empty_usage(),
    }


def unreadable_activity(*, terminal: bool = False) -> dict[str, Any]:
    """The activity facts that survive when a durable column cannot be parsed.

    Used by list-shaped reads, where one corrupt row must not blank the whole response: the
    stage is null and the step counts are null (never 0) so a client renders "cannot read" and
    not "queued, nothing done".
    """
    return {
        "stage": None,
        "stage_source": "none",
        "steps_done": None,
        "steps_total": None,
        "elapsed_seconds": None,
        "elapsed_basis": "created_to_updated" if terminal else "created_to_now",
        "can_cancel": False,
        "can_retry": False,
        "terminal": terminal,
        "readable": False,
        "message": "",
        "last_progress_at": None,
        "usage": empty_usage(),
    }


def empty_usage() -> dict[str, Any]:
    return {
        "calls": 0,
        "tokens": {field: None for field in TOKEN_FIELDS},
        "cost_usd": None,
        "unknown_cost_calls": 0,
        "artifacts": 0,
        "providers": [],
        "models": [],
    }


def _tokens(values: dict[str, Any]) -> dict[str, int | None]:
    totals: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        total = 0
        seen = False
        for name in TOKEN_ALIASES.get(field, (field,)):
            value = values.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                total += value
                seen = True
        totals[field] = total if seen else None
    return totals


def _bounded(names: list[str]) -> list[str]:
    return sorted({name for name in names if name})[:_MAX_NAMES]


def usage_for_job(connection, job_id: str) -> dict[str, Any]:
    """Sum the recorded ``usage_events`` rows whose ``operation_id`` is this job id.

    Nothing is estimated: a field no recorded call exposed stays null, and a call whose cost was
    not recorded is counted in ``unknown_cost_calls`` rather than priced at zero.
    """
    rows = connection.execute(
        "SELECT provider, model, tokens_json, artifact_count FROM usage_events"
        " WHERE operation_id = ?",
        (job_id,),
    ).fetchall()
    tokens = {field: 0 for field in TOKEN_FIELDS}
    seen = {field: False for field in TOKEN_FIELDS}
    cost: float | None = None
    unknown_cost = 0
    artifacts = 0
    providers: list[str] = []
    models: list[str] = []
    for row in rows:
        raw = row["tokens_json"]
        values: dict[str, Any] = {}
        if isinstance(raw, str) and raw:
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                values = parsed
        for field, value in _tokens(values).items():
            if value is not None:
                tokens[field] += value
                seen[field] = True
        recorded_cost = values.get("cost_usd")
        if isinstance(recorded_cost, (int, float)) and not isinstance(recorded_cost, bool):
            cost = float(recorded_cost) + (cost or 0.0)
        else:
            unknown_cost += 1
        artifacts += int(row["artifact_count"] or 0)
        providers.append(str(row["provider"] or ""))
        models.append(str(row["model"] or ""))
    return {
        "calls": len(rows),
        "tokens": {field: tokens[field] if seen[field] else None for field in TOKEN_FIELDS},
        "cost_usd": cost,
        "unknown_cost_calls": unknown_cost,
        "artifacts": artifacts,
        "providers": _bounded(providers),
        "models": _bounded(models),
    }


def activity_with_usage(connection, row: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """``activity_for`` plus the usage recorded against this job id."""
    activity = activity_for(row, now=now)
    activity["usage"] = usage_for_job(connection, str(row["id"]))
    return activity
