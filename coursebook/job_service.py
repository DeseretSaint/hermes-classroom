"""Durable backend job service: leases, fencing, checkpoints, cancellation, reconciliation.

``PREBUILD_SPEC.md`` §12 and ``AUDIT.md`` R2/H2 are the reasons this module exists rather than a
bare "spawn a task" call: a job is a durable row, an attempt is a leased worker, and a result is
adopted by key. Losing the in-process runner must never look like a successful cancellation, and
restarting the process must never repeat spend or duplicate an artifact.

Frozen rules enforced here:

* every claim/renew/checkpoint/complete is a ``BEGIN IMMEDIATE`` compare-and-swap on
  ``(job_id, attempt_id, lease_owner)`` — a stale worker cannot write newer state;
* provider/media calls always run **outside** any transaction (``db.active_transactions() == 0``
  while a stage executes);
* a cancellation marks intent and stops future stages; an already-running non-idempotent call is
  reconciled by operation/artifact key on return and becomes ``completed_late`` — never a rerun;
* progress comes from real completed stages, so ``steps_total`` may be null;
* unknown usage fields stay null; nothing is fabricated.
"""

from __future__ import annotations

import contextvars
import logging
import os
import threading
import time
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Sequence

from . import contracts
from . import db
from . import deadline as deadline_mod
from . import jobs as jobs_contract
from .api import RpcError
from .research import ResearchCancelled

logger = logging.getLogger("coursebook.job_service")

#: Lease length. Short enough that a killed process is detected within one poll interval, long
#: enough that a slow provider call does not lose its fence between heartbeats.
LEASE_SECONDS = 120

#: Seconds the row may go without a recorded worker heartbeat before a still-``running`` attempt
#: is presumed dead (G6). Every successful ``renew``/``checkpoint`` rewrites ``updated_at``; a
#: worker that stopped beating leaves that stamp behind. The default equals the lease: an expired
#: lease already means the beat is a full lease old. A deployment may shorten it with
#: ``COURSEBOOK_WORKER_LOST_SECONDS``, which is how a live probe asserts the watchdog window
#: without waiting two minutes.
WORKER_LOST_ENV = "COURSEBOOK_WORKER_LOST_SECONDS"

#: Typed reason carried in ``error.details`` when the watchdog fails a row. The job state is the
#: contract's own retryable ``failed``; this value is what tells an operator *why* it rested.
WORKER_LOST_REASON = "WORKER_LOST"

#: Seconds one job **attempt** may run before the in-flight provider call is cancelled and the
#: job is failed (CP-044). Per-call deadlines are not a job deadline: a plan attempt runs two
#: author/validate rounds, so bounded calls that each finish "in time" can still keep the row
#: ``running`` for well over half an hour. Resolved from ``COURSEBOOK_JOB_DEADLINE_SECONDS`` when
#: a deployment sets it; the value travels into every bounded call as the *remaining* budget.
JOB_DEADLINE_SECONDS = deadline_mod.JOB_DEADLINE_SECONDS
JOB_DEADLINE_ENV = deadline_mod.JOB_DEADLINE_ENV

#: Identity of this process's worker. Random per process: never a hostname or pid, which can be
#: reused and would make two workers look like one.
WORKER_ID = f"worker-{uuid.uuid4().hex[:12]}"

#: Bounded attempts at reading cancellation state before concluding it cannot be known (H-129).
#: A transient lock deserves a second look; an unreadable store must never be read as "keep going"
#: because cancellation is the user's spend control.
CANCEL_READ_ATTEMPTS = 3
CANCEL_READ_BACKOFF_S = 0.05

_MAX_ERROR_TEXT = 500


def _now(moment: datetime | None = None) -> datetime:
    return moment or datetime.now(timezone.utc)


def job_deadline_seconds() -> float:
    """The attempt budget for this deployment: env override, else the declared default.

    A malformed or non-positive override is logged and the default kept, exactly as the provider
    deadlines behave: a typo must not silently remove the bound (CP-044).
    """
    raw = os.environ.get(JOB_DEADLINE_ENV)
    default = float(JOB_DEADLINE_SECONDS)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("coursebook: ignoring %s=%r (not a number); using %.0fs", JOB_DEADLINE_ENV, raw, default)
        return default
    if value <= 0:
        logger.warning("coursebook: ignoring %s=%r (not positive); using %.0fs", JOB_DEADLINE_ENV, raw, default)
        return default
    return value


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str | None, default: Any) -> Any:
    import json

    if not value:
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def worker_lost_after_seconds() -> float:
    """How long a row may sit without a heartbeat before its worker is presumed lost.

    Resolved at call time so a probe or deployment can shorten the window. A malformed or
    non-positive override is logged and the default kept, exactly as the job deadline behaves: a
    typo must not silently remove the watchdog.
    """
    raw = os.environ.get(WORKER_LOST_ENV)
    default = float(LEASE_SECONDS)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("coursebook: ignoring %s=%r (not a number); using %.0fs", WORKER_LOST_ENV, raw, default)
        return default
    if value <= 0:
        logger.warning("coursebook: ignoring %s=%r (not positive); using %.0fs", WORKER_LOST_ENV, raw, default)
        return default
    return value


def last_worker_beat(row: Any) -> datetime | None:
    """Durable evidence of the worker's last heartbeat for one ``jobs`` row.

    ``claim``/``renew``/``checkpoint``/``finish`` all rewrite ``updated_at``, so it *is* the beat
    stamp; a worker that died stops moving it. ``created_at`` is the fallback for a row written
    before any of those transitions ran.
    """
    return _parse(row["updated_at"]) or _parse(row["created_at"])


def worker_is_lost(row: Any, *, now: datetime | None = None) -> bool:
    """Whether this live-state row's worker is gone: no live lease **and** a stale heartbeat.

    Both halves are required. A fresh lease is a worker still renewing, whoever owns it; a recent
    heartbeat keeps a short grace window after the lease lapses (clock skew, a beat landing
    between two passes). Only when neither is present is the row's owner provably gone.
    """
    moment = _now(now)
    held = _parse(row["lease_expires_at"])
    if held is not None and held > moment:
        return False
    beat = last_worker_beat(row)
    if beat is None:
        return True
    return (moment - beat).total_seconds() >= worker_lost_after_seconds()


def worker_lost_error(row: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """The contract-legal error a watchdog-failed row carries.

    ``failed`` is a *resting* contract state: it is retryable, so the operator is told the retry is
    a real action and the checkpoint survives for it. The typed ``WORKER_LOST`` reason is the
    distinction between "the worker went away" and "the stage raised".
    """
    moment = _now(now)
    beat = last_worker_beat(row)
    window = worker_lost_after_seconds()
    return contracts.build_error(
        "HOST_UNAVAILABLE",
        (
            f"job {row['id']} stopped reporting: its worker has not heartbeat for at least "
            f"{window:.0f}s and its lease is no longer held. The attempt was stopped; retry it "
            "and it resumes from the last checkpoint."
        ),
        retryable=True,
        reason=WORKER_LOST_REASON,
        retry_hint="retry the job; the brief and last checkpoint are preserved",
        last_heartbeat_at=_iso(beat) if beat is not None else None,
        lease_expires_at=row["lease_expires_at"],
        stale_after_seconds=window,
        observed_at=_iso(moment),
    )


class JobLeaseLost(RuntimeError):
    """Another attempt owns the job now. The caller must stop, not retry the write."""


class JobCancelled(ResearchCancelled):
    """The job's cancellation reached a safe boundary; the stage loop stops."""

    def __init__(self, reason: str, *, usage: list[Any] | None = None) -> None:
        super().__init__(reason)
        # Calls that already happened before the boundary are still real spend and must be
        # recorded; the executor takes them from here on the cancellation path.
        self.usage = list(usage or [])


class CancelStateUnreadable(RuntimeError):
    """The job's cancel flag could not be read, so "not cancelled" cannot be concluded (H-129).

    Cancellation is a spend control, which makes this the one read that must fail closed: an
    unreadable store used to answer ``False`` from the generation probe, so a user-requested
    cancel became "keep spending" at every provider boundary. Callers stop the job at the
    boundary and record this typed failure instead.
    """

    #: Contract-legal code: an unexpected backend failure, retryable once the store answers again.
    code = "INTERNAL_ERROR"

    def __init__(self, job_id: str, *, attempts: int, cause: BaseException | None = None) -> None:
        self.job_id = str(job_id)
        self.attempts = int(attempts)
        self.cause_type = type(cause).__name__ if cause is not None else None
        detail = f" after {self.attempts} attempts" if self.attempts > 1 else ""
        suffix = f" ({self.cause_type})" if self.cause_type else ""
        super().__init__(f"job {self.job_id} cancel state could not be read{detail}{suffix}")
        if cause is not None:
            self.__cause__ = cause


@dataclass(frozen=True)
class Lease:
    job_id: str
    attempt_id: str
    owner: str
    expires_at: str

    def as_dict(self) -> dict[str, Any]:
        return {"owner": self.owner, "expires_at": self.expires_at}


@dataclass
class UsageRecord:
    """One real provider call. Unknown fields stay ``None`` and are stored as NULL."""

    provider: str | None = None
    model: str | None = None
    tokens: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    artifact_count: int = 0


@dataclass
class StageResult:
    artifacts: list[str] = field(default_factory=list)
    usage: list[UsageRecord] = field(default_factory=list)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    message: str | None = None


@dataclass(frozen=True)
class Stage:
    """A named unit of work. ``run`` executes with no transaction open."""

    name: str
    run: Callable[[Lease], StageResult]


def _job(connection, job_id: str) -> Any:
    row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise RpcError.of("NOT_FOUND", f"job {job_id} does not exist.", job_id=job_id)
    return row


def job_view(row: Any) -> dict[str, Any]:
    """The ``cb.jobs`` row as the RPC contract's job object."""
    progress = _load(row["progress_json"], {})
    checkpoint = _load(row["checkpoint_json"], {})
    brief = _load(row["brief_json"], {})
    error = _load(row["error_json"], {})
    artifact_ids: list[str] = []
    for item in progress.get("stages") or []:
        for artifact_id in item.get("artifact_ids") or []:
            if artifact_id not in artifact_ids:
                artifact_ids.append(str(artifact_id))
    lease = None
    if row["lease_owner"]:
        lease = {"owner": row["lease_owner"], "expires_at": row["lease_expires_at"]}
    return {
        "job_id": row["id"],
        "kind": row["kind"],
        "state": row["state"],
        "operation_id": row["operation_id"],
        "attempt_id": row["attempt_id"] or "unassigned",
        "brief": brief,
        "checkpoint": checkpoint,
        "progress": {
            "stage": progress.get("stage") or "queued",
            "steps_done": int(progress.get("steps_done") or 0),
            "steps_total": progress.get("steps_total"),
            "message": progress.get("message") or "",
        },
        "lease": lease,
        "artifact_ids": artifact_ids,
        "error": error or None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "cancel_requested_at": None,
    }


# ── creation ────────────────────────────────────────────────────────────────


def create(
    kind: str,
    brief: dict[str, Any],
    *,
    operation_id: str | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
    connection=None,
) -> dict[str, Any]:
    """Create a queued job, idempotent on ``operation_id``/``idempotency_key``.

    The kernel's ``jobs.create`` command calls this so a retried POST never mints a second job
    (and therefore never a second spend). Pass ``connection`` to join the caller's fenced
    transaction; otherwise a short transaction is opened and closed here.
    """
    if connection is not None:
        return _create(connection, kind, brief, operation_id, idempotency_key, now)
    with db.transaction() as connection:
        return _create(connection, kind, brief, operation_id, idempotency_key, now)


def _create(connection, kind, brief, operation_id, idempotency_key, now) -> dict[str, Any]:
    moment = _now(now)
    stamp = _iso(moment)
    key = idempotency_key
    if key:
        row = connection.execute(
            "SELECT response_json FROM idempotency_keys WHERE key = ?", (key,)
        ).fetchone()
        if row is not None:
            return _load(row["response_json"], {})
    elif operation_id:
        row = connection.execute(
            "SELECT id, state FROM jobs WHERE operation_id = ? ORDER BY created_at LIMIT 1",
            (operation_id,),
        ).fetchone()
        if row is not None:
            return {"job_id": row["id"], "state": row["state"]}
    job_id = f"job_{uuid.uuid4().hex}"
    connection.execute(
        "INSERT INTO jobs (id, kind, state, operation_id, brief_json, checkpoint_json, attempt_id,"
        " lease_owner, lease_expires_at, progress_json, error_json, created_at, updated_at)"
        " VALUES (?, ?, 'queued', ?, ?, '{}', NULL, NULL, NULL, '{}', '{}', ?, ?)",
        (job_id, kind, operation_id, _json(brief), stamp, stamp),
    )
    result = {"job_id": job_id, "state": "queued"}
    if key:
        connection.execute(
            "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json, created_at)"
            " VALUES (?, ?, 'jobs.create', ?, ?, ?)",
            (key, _json(brief), operation_id or f"op-{job_id}", _json(result), stamp),
        )
    return result


# ── leases ──────────────────────────────────────────────────────────────────


def claim(job_id: str, *, owner: str | None = None, now: datetime | None = None) -> Lease:
    """Take the lease for one attempt. Fenced by state and current lease expiry."""
    owner = owner or WORKER_ID
    moment = _now(now)
    expires = _iso(moment + timedelta(seconds=LEASE_SECONDS))
    attempt_id = f"att_{uuid.uuid4().hex}"
    with db.transaction() as connection:
        row = _job(connection, job_id)
        state = str(row["state"])
        if state not in ("queued", "running"):
            raise RpcError.of(
                "JOB_STATE_INVALID", f"job is {state} and cannot be claimed.", job_id=job_id, state=state
            )
        held_until = _parse(row["lease_expires_at"])
        if state == "running" and held_until is not None and held_until > moment:
            if row["lease_owner"] != owner:
                raise JobLeaseLost(f"job {job_id} is leased by {row['lease_owner']} until {row['lease_expires_at']}")
        if state == "queued":
            jobs_contract.assert_transition(state, "running")
        connection.execute(
            "UPDATE jobs SET state = 'running', attempt_id = ?, lease_owner = ?, lease_expires_at = ?,"
            " updated_at = ?, error_json = '{}' WHERE id = ? AND state = ?",
            (attempt_id, owner, expires, _iso(moment), job_id, state),
        )
    return Lease(job_id=job_id, attempt_id=attempt_id, owner=owner, expires_at=expires)


def _fenced_row(connection, lease: Lease) -> Any:
    row = _job(connection, lease.job_id)
    if row["attempt_id"] != lease.attempt_id or row["lease_owner"] != lease.owner:
        raise JobLeaseLost(
            f"attempt {lease.attempt_id} no longer owns job {lease.job_id}"
            f" (now {row['attempt_id']}/{row['lease_owner']})"
        )
    return row


def renew(lease: Lease, *, now: datetime | None = None, extra_seconds: int | None = None) -> Lease:
    """Extend a still-owned lease. A lost fence raises rather than silently continuing."""
    moment = _now(now)
    expires = _iso(moment + timedelta(seconds=extra_seconds or LEASE_SECONDS))
    with db.transaction() as connection:
        _fenced_row(connection, lease)
        connection.execute(
            "UPDATE jobs SET lease_expires_at = ?, updated_at = ? WHERE id = ? AND attempt_id = ?",
            (expires, _iso(moment), lease.job_id, lease.attempt_id),
        )
    return Lease(lease.job_id, lease.attempt_id, lease.owner, expires)


def is_cancel_requested(job_id: str) -> bool:
    """Raw read of the cancel flag. Raises whatever the store raises; never guesses."""
    with db.read() as connection:
        row = connection.execute("SELECT state FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row is not None and str(row["state"]) in ("cancel_requested", "cancelling")


def _job_store_absent() -> bool:
    """True only when the profile has no job schema at all (so no durable job can exist)."""
    try:
        return db.applied_schema_version() is None
    except Exception:  # noqa: BLE001 - a store we cannot even inspect is not "absent"
        return False


def cancel_requested(job_id: str, *, attempts: int | None = None) -> bool:
    """Whether this job was asked to stop, retrying a bounded number of times (H-129).

    A store that cannot answer this is **not** evidence that the user did not cancel. After the
    bounded retries this raises :class:`CancelStateUnreadable` so the caller stops at the
    boundary instead of spending another provider call on a cancel that may already exist.
    """
    tries = max(1, int(attempts if attempts is not None else CANCEL_READ_ATTEMPTS))
    last: BaseException | None = None
    for attempt in range(1, tries + 1):
        try:
            return is_cancel_requested(job_id)
        except Exception as exc:  # noqa: BLE001 - retried, then raised as the typed failure
            if _job_store_absent():
                # A profile with no schema has never held a durable job, so there is nothing to
                # cancel. That is a fact about the store, not an unread failure — pure helper
                # calls (no job engine in the process) keep working instead of stopping wrongly.
                return False
            last = exc
            logger.warning(
                "coursebook: cancel state unreadable for job %s (attempt %d/%d): %s",
                job_id,
                attempt,
                tries,
                type(exc).__name__,
            )
            if attempt < tries:
                time.sleep(CANCEL_READ_BACKOFF_S)
    raise CancelStateUnreadable(job_id, attempts=tries, cause=last) from last


def request_cancel(job_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Record cancellation intent. ``cancelled`` means nothing further will run.

    A ``running`` row whose worker is provably gone (:func:`worker_is_lost`) is settled directly:
    there is no thread left to reach a stage boundary. A live row keeps ``cancel_requested`` and
    stops at its own boundary.
    """
    moment = _now(now)
    with db.transaction() as connection:
        row = _job(connection, job_id)
        state = str(row["state"])
        if jobs_contract.is_terminal(state):
            raise RpcError.of(
                "JOB_NOT_CANCELLABLE", f"job is already {state}.", job_id=job_id, state=state
            )
        if state == "queued":
            target = "cancelled"
        elif state == "interrupted_requires_retry":
            target = "cancelled"
        elif state in ("cancel_requested", "cancelling"):
            return {"job_id": job_id, "state": state}
        elif state == "running" and worker_is_lost(row, now=moment):
            # G6: no worker is left to reach a stage boundary, so "cancel" must be settlement
            # here, not a request posted to a thread that is gone. Two contract-legal edges
            # (running -> cancel_requested -> cancelled) in one fenced transaction end durably.
            jobs_contract.assert_transition(state, "cancel_requested")
            jobs_contract.assert_transition("cancel_requested", "cancelled")
            connection.execute(
                "UPDATE jobs SET state = 'cancelled', lease_owner = NULL, lease_expires_at = NULL,"
                " updated_at = ? WHERE id = ?",
                (_iso(moment), job_id),
            )
            return {"job_id": job_id, "state": "cancelled"}
        else:
            target = "cancel_requested"
        jobs_contract.assert_transition(state, target)
        connection.execute(
            "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?", (target, _iso(moment), job_id)
        )
    return {"job_id": job_id, "state": target}


def begin_cancelling(lease: Lease, *, now: datetime | None = None) -> None:
    """Move a leased ``cancel_requested`` job to ``cancelling`` at a stage boundary."""
    moment = _now(now)
    with db.transaction() as connection:
        row = _fenced_row(connection, lease)
        state = str(row["state"])
        if state == "running":
            return
        if state == "cancel_requested":
            jobs_contract.assert_transition(state, "cancelling")
            connection.execute(
                "UPDATE jobs SET state = 'cancelling', updated_at = ? WHERE id = ?", (_iso(moment), lease.job_id)
            )
        elif state not in ("cancelling",):
            raise RpcError.of("JOB_STATE_INVALID", f"job is {state}; cannot begin cancelling.", state=state)


# ── checkpoints and terminal transitions ────────────────────────────────────


def checkpoint(
    lease: Lease,
    *,
    stage: str,
    steps_done: int,
    steps_total: int | None,
    message: str | None = None,
    checkpoint: dict[str, Any] | None = None,
    artifact_ids: Sequence[str] = (),
    now: datetime | None = None,
) -> None:
    """Persist a safe resume point plus real progress. Provider calls are already done."""
    moment = _now(now)
    with db.transaction() as connection:
        row = _fenced_row(connection, lease)
        progress = _load(row["progress_json"], {})
        stages = [item for item in (progress.get("stages") or []) if isinstance(item, dict)]
        stages.append(
            {
                "stage": stage,
                "steps_done": int(steps_done),
                "steps_total": steps_total,
                "artifact_ids": list(artifact_ids),
                "at": _iso(moment),
            }
        )
        progress.update(
            {
                "stage": stage,
                "steps_done": int(steps_done),
                "steps_total": steps_total,
                "message": (message or "")[:300],
                "stages": stages,
            }
        )
        stored = _load(row["checkpoint_json"], {})
        stored.update(checkpoint or {})
        stored["last_stage"] = stage
        connection.execute(
            "UPDATE jobs SET progress_json = ?, checkpoint_json = ?, updated_at = ?"
            " WHERE id = ? AND attempt_id = ?",
            (_json(progress), _json(stored), _iso(moment), lease.job_id, lease.attempt_id),
        )


def finish(
    lease: Lease,
    *,
    state: str = "completed",
    artifact_ids: Sequence[str] = (),
    error: dict[str, Any] | None = None,
    message: str | None = None,
    checkpoint: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> str:
    """Close the attempt. A completion that raced a cancel becomes ``completed_late``.

    ``checkpoint`` merges into the persisted checkpoint on a *failed* attempt too: a typed
    recovery record (what survived, what was spent) is the only thing that lets a retry skip
    finished work, so it must not be lost just because the stage raised.
    """
    moment = _now(now)
    with db.transaction() as connection:
        row = _fenced_row(connection, lease)
        current = str(row["state"])
        target = state
        if state == "completed" and current in ("cancel_requested", "cancelling"):
            target = "completed_late"
        jobs_contract.assert_transition(current, target)
        progress = _load(row["progress_json"], {})
        if message:
            progress["message"] = message[:300]
        stored = _load(row["checkpoint_json"], {})
        stored.update({k: v for k, v in (checkpoint or {}).items() if k not in ("progress", "stages")})
        connection.execute(
            "UPDATE jobs SET state = ?, progress_json = ?, checkpoint_json = ?, error_json = ?,"
            " lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ? AND attempt_id = ?",
            (
                target,
                _json(progress),
                _json(stored),
                _json(error) if error else "{}",
                _iso(moment),
                lease.job_id,
                lease.attempt_id,
            ),
        )
    return target


def fail(
    lease: Lease,
    error: dict[str, Any],
    *,
    checkpoint: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> str:
    return finish(lease, state="failed", error=error, checkpoint=checkpoint, now=now)


def resume(job_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Re-queue a failed/interrupted job with the persisted brief and checkpoint.

    A retry is a new attempt id; the checkpoint is what lets a caller skip finished stages
    instead of paying for them again.
    """
    moment = _now(now)
    with db.transaction() as connection:
        row = _job(connection, job_id)
        state = str(row["state"])
        if state not in ("failed", "interrupted_requires_retry"):
            raise RpcError.of(
                "JOB_STATE_INVALID", f"job is {state} and cannot be resumed.", job_id=job_id, state=state
            )
        jobs_contract.assert_transition(state, "queued")
        attempt_id = f"att_{uuid.uuid4().hex}"
        connection.execute(
            "UPDATE jobs SET state = 'queued', attempt_id = ?, lease_owner = NULL, lease_expires_at = NULL,"
            " error_json = '{}', updated_at = ? WHERE id = ?",
            (attempt_id, _iso(moment), job_id),
        )
        checkpoint = _load(row["checkpoint_json"], {})
    return {"job_id": job_id, "state": "queued", "attempt_id": attempt_id, "checkpoint": checkpoint}


# ── execution ───────────────────────────────────────────────────────────────


def _record_usage(
    connection,
    job_id: str,
    usage: Iterable[UsageRecord],
    now: datetime | None,
    payment_kind: str,
) -> None:
    stamp = _iso(_now(now))
    for item in usage:
        connection.execute(
            "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model, tokens_json,"
            " duration_ms, artifact_count, recorded_at)"
            " VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
            (
                f"use_{uuid.uuid4().hex}",
                job_id,
                item.provider,
                item.model,
                _json(item.tokens or {}),
                item.duration_ms,
                int(item.artifact_count or 0),
                stamp,
            ),
        )


def _run_with_heartbeat(
    lease: Lease,
    stage: Stage,
    heartbeat_seconds: float | None = None,
) -> "StageResult":
    """Run one stage while keeping its lease alive.

    A stage is where the provider work happens: the lesson stage authors a section at a time and
    can run for several minutes, far past ``LEASE_SECONDS``. Renewing only *between* stages meant
    a live job's lease lapsed mid-stage, so any other process's startup reconciliation (or a
    crash-recovery pass) was entitled to reclaim it — the lesson stage died
    ``interrupted_requires_retry`` seconds after it began. The lease now expires only when the
    worker process is actually gone, which is the only thing a lease can prove.

    H-66: the heartbeat thread must run under the **caller's context**. A bare ``Thread`` starts
    with an empty ``contextvars.Context``; a gateway carries the active profile as a context-local
    override, so every ``renew`` there resolved a *different* database (where the job does not
    exist). The ``NOT_FOUND`` was swallowed by the generic ``except`` and the lease silently
    lapsed while the stage was blocked. The beat now runs in ``copy_context()`` and a run of
    failures is logged instead of disappearing.
    """
    interval = heartbeat_seconds if heartbeat_seconds is not None else max(1.0, LEASE_SECONDS / 3.0)
    stop = threading.Event()
    context = contextvars.copy_context()
    failures = 0

    def beat() -> None:
        nonlocal failures
        while not stop.wait(interval):
            try:
                context.run(renew, lease)
                failures = 0
            except JobLeaseLost:
                logger.warning(
                    "coursebook: heartbeat for %s lost its lease; the stage's writes will be fenced",
                    lease.job_id,
                )
                return
            except Exception as exc:  # noqa: BLE001 - a transient miss must not kill the stage
                failures += 1
                if failures == 1 or failures % 5 == 0:
                    logger.warning(
                        "coursebook: heartbeat for %s failed %d time(s): %s: %s",
                        lease.job_id,
                        failures,
                        type(exc).__name__,
                        exc,
                    )
                continue

    thread = threading.Thread(target=beat, name=f"job-heartbeat-{lease.job_id}", daemon=True)
    thread.start()
    try:
        return stage.run(lease)
    finally:
        stop.set()
        thread.join(timeout=5.0)


def execute(
    job_id: str,
    stages: Sequence[Stage],
    *,
    owner: str | None = None,
    skip_stages: Iterable[str] = (),
    now: datetime | None = None,
    heartbeat_seconds: float | None = None,
) -> dict[str, Any]:
    """Run stages under one lease, checkpointing after each, honoring cancellation.

    Returns the final job view. Never raises for an expected stage failure: the job row records
    ``failed`` with a typed error so the UI can offer retry with the same brief/checkpoint.
    """
    try:
        lease = claim(job_id, owner=owner, now=now)
    except RpcError as exc:
        if exc.error.get("code") == "JOB_STATE_INVALID" and str(_view(job_id)["state"]) in jobs_contract.terminal_states():
            # A job that is already terminal spends nothing further.
            return _view(job_id)
        raise
    steps_total = len(stages)
    skip = set(skip_stages)
    #: CP-044: one wall-clock budget for the whole attempt. Every bounded foreign call inside a
    #: stage is clamped to what is left of it, so an in-flight provider request is cancelled at
    #: the job's deadline instead of running to its own (larger) purpose bound.
    attempt_deadline = time.monotonic() + job_deadline_seconds()
    try:
        for index, stage in enumerate(stages, start=1):
            if stage.name in skip:
                continue
            try:
                cancelled = cancel_requested(job_id)
            except CancelStateUnreadable as exc:
                # H-129: the boundary cannot prove the job is not cancelled, so it spends nothing.
                return _stop_on_unreadable_cancel(lease, stage.name, exc, now=now)
            if cancelled:
                begin_cancelling(lease)
                finish(lease, state="cancelled", now=now)
                return _view(job_id)
            remaining = attempt_deadline - time.monotonic()
            if remaining <= 0:
                # The budget is spent before another call starts: no socket is opened that the
                # job will not wait for. Recorded with the same HOST_UNAVAILABLE shape a provider
                # deadline uses, so nothing new appears in the contract.
                return _stop_on_job_deadline(
                    lease, stage.name, job_deadline_seconds(), now=now
                )
            renew(lease)
            try:
                with deadline_mod.job_budget(remaining):
                    result = _run_with_heartbeat(lease, stage, heartbeat_seconds)
            except CancelStateUnreadable as exc:
                # The stage hit a provider/research boundary whose cancel read failed. Stop here,
                # with the typed reason on the row, instead of answering "continue" (H-129).
                return _stop_on_unreadable_cancel(
                    lease, stage.name, exc, checkpoint=_stage_checkpoint(exc), now=now
                )
            except ResearchCancelled as exc:
                usage = list(getattr(exc, "usage", []) or [])
                if usage:
                    with db.transaction() as connection:
                        _record_usage(connection, job_id, usage, now, "job")
                begin_cancelling(lease)
                finish(lease, state="cancelled", now=now)
                return _view(job_id)
            except JobLeaseLost:
                # Another attempt owns the row now; this worker must not write anything else.
                return _view(job_id)
            except Exception as exc:  # noqa: BLE001 - a stage failure is durable, not a crash
                recovery = _stage_checkpoint(exc)
                try:
                    cancelled = cancel_requested(job_id)
                except CancelStateUnreadable as read_exc:
                    return _stop_on_unreadable_cancel(
                        lease, stage.name, read_exc, checkpoint=recovery, now=now
                    )
                if cancelled:
                    # The stage ended because its bounded call hit a deadline; the user had
                    # already asked to stop. The honest outcome is ``cancelled`` with the
                    # recovery record, not a host failure the reader would retry (H-66).
                    begin_cancelling(lease)
                    finish(
                        lease,
                        state="cancelled",
                        checkpoint=recovery,
                        message=f"cancelled during {stage.name}: {type(exc).__name__}",
                        now=now,
                    )
                    return _view(job_id)
                fail(lease, _stage_error(exc), checkpoint=recovery)
                return _view(job_id)
            with db.transaction() as connection:
                _record_usage(connection, job_id, result.usage, now, "job")
            checkpoint(
                lease,
                stage=stage.name,
                steps_done=index,
                steps_total=steps_total,
                message=result.message,
                checkpoint=result.checkpoint,
                artifact_ids=result.artifacts,
                now=now,
            )
            try:
                cancelled = cancel_requested(job_id)
            except CancelStateUnreadable as exc:
                return _stop_on_unreadable_cancel(
                    lease, stage.name, exc, checkpoint=result.checkpoint, now=now
                )
            if cancelled:
                # A cancellation that arrived while the stage ran stops here: the finished
                # stage's work and checkpoint are durable, but the job does not go on to
                # another provider call and does not report itself completed.
                begin_cancelling(lease)
                finish(
                    lease,
                    state="cancelled",
                    checkpoint=result.checkpoint,
                    message=f"cancelled after {stage.name} reached its boundary",
                    now=now,
                )
                return _view(job_id)
            done_after = index
        state = finish(lease, artifact_ids=())
        return _view(job_id)
    except JobLeaseLost:
        return _view(job_id)


def _stop_on_job_deadline(
    lease: Lease,
    stage_name: str,
    deadline_s: float,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fail the attempt because its own deadline is spent, without opening another call (CP-044).

    The row leaves ``running`` with the contract's existing ``HOST_UNAVAILABLE`` shape (retryable
    capability failure, the same code a provider timeout uses) and the lease is released by
    :func:`fail`. ``details`` name the stage and the budget, so a reader can tell a spent job
    budget from a slow provider.
    """
    exc = deadline_mod.JobDeadlineExceeded(stage_name, deadline_s=deadline_s, elapsed_s=0.0)
    try:
        fail(lease, _stage_error(exc), now=now)
    except JobLeaseLost:
        return _view(lease.job_id)
    logger.warning(
        "coursebook: job %s stopped before %s: the %.0fs job deadline is spent",
        lease.job_id,
        stage_name,
        deadline_s,
    )
    return _view(lease.job_id)


def _stop_on_unreadable_cancel(
    lease: Lease,
    stage_name: str,
    exc: CancelStateUnreadable,
    *,
    checkpoint: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Stop a job at a boundary whose cancel read failed, with a reason on the row (H-129).

    ``interrupted_requires_retry`` is the honest resting state: the brief and checkpoint survive,
    so the user can run the stage again once the store answers. The one exception is a row that
    is already ``cancel_requested``/``cancelling`` — that transition is not legal from the frozen
    state machine, and the user's stop wins anyway, so the job closes ``cancelled``.
    """
    error = _stage_error(exc)
    details = dict(error.get("details") or {})
    details.update({"reason": "cancel_state_unreadable", "stage": stage_name, "attempts": exc.attempts})
    error["details"] = details
    message = (
        f"stopped before more work at {stage_name}: the job's cancel state could not be read; "
        "no further provider call was made"
    )
    try:
        finish(
            lease,
            state="interrupted_requires_retry",
            error=error,
            checkpoint=checkpoint,
            message=message,
            now=now,
        )
    except RpcError as invalid:
        if invalid.error.get("code") != "JOB_STATE_INVALID":
            logger.exception("coursebook: could not record an unreadable cancel state for %s", lease.job_id)
            return _view(lease.job_id)
        logger.warning(
            "coursebook: job %s was already cancelling; closing it cancelled after an unreadable state read",
            lease.job_id,
        )
        try:
            finish(lease, state="cancelled", error=error, checkpoint=checkpoint, message=message, now=now)
        except JobLeaseLost:
            return _view(lease.job_id)
        except RpcError:
            logger.exception("coursebook: could not cancel job %s after an unreadable state read", lease.job_id)
            return _view(lease.job_id)
        return _view(lease.job_id)
    except JobLeaseLost:
        return _view(lease.job_id)
    except Exception:  # noqa: BLE001 - the store is unreadable; the lease reaper is the backstop
        logger.exception("coursebook: could not persist the unreadable cancel state for %s", lease.job_id)
        return _view(lease.job_id)
    logger.warning(
        "coursebook: job %s stopped at %s: cancel state unreadable (%s)",
        lease.job_id,
        stage_name,
        exc,
    )
    return _view(lease.job_id)


#: Exceptions that are the *host's* problem, mapped to the contract's capability code.
#: ``HOST_UNAVAILABLE`` means "the Hermes host (gateway, auxiliary model, media provider) is
#: unavailable"; ``GRADER_UNAVAILABLE`` is about grading an answer, and reporting a provider
#: deadline as a grader failure sends the reader to the wrong subsystem (CB-011-D1).
#:
#: ``ModelOutputInvalid`` is deliberately *absent*: the host and the provider answered, so an
#: outage label is false (H-191: one 81-character validator ``item`` label discarded a 54 s paid
#: call and surfaced as retryable ``HOST_UNAVAILABLE``). It carries ``code = "VALIDATION_FAILED"``
#: itself — the *payload* violated the frozen response contract — and reports
#: ``retryable: false``: blind re-running of the same stage is not the honest next step. It is
#: still not a rejection: nothing was validated or rejected, and no validation record is written.
_PROVIDER_ERRORS = frozenset({"ProviderTimeout", "ProviderFailure", "ResearchTimeout", "MediaTimeout"})

#: Exceptions that are a declared policy ceiling, not a bug or a host outage. A cost ceiling is a
#: deterministic stop, so the same request will fail the same way until the operator raises it —
#: the recovery checkpoint, not an automatic retry, is the next step.
_POLICY_ERRORS = frozenset({"ResearchUnavailable", "CostCeilingExceeded", "CostPreflightRefused"})


def _error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code
    name = type(exc).__name__
    if name in _PROVIDER_ERRORS:
        return "HOST_UNAVAILABLE"
    if name in _POLICY_ERRORS:
        return "POLICY_VIOLATION"
    return "INTERNAL_ERROR"


def _stage_error(exc: Exception) -> dict[str, Any]:
    """The durable failure record: a contract-legal code plus non-sensitive context.

    ``cb.errors`` is the single authority for category/retryability, so this builds the error
    from it instead of repeating ``category: capability`` for every failure. Structured
    ``details`` name the purpose and the measured duration, never a secret or a reference answer.
    A cost abort also carries its ceiling arithmetic so the operator can act on the numbers.
    """
    code = _error_code(exc)
    message = str(exc)[:_MAX_ERROR_TEXT] or type(exc).__name__
    details: dict[str, Any] = {}
    for attribute in (
        "purpose",
        "duration_ms",
        "deadline_s",
        "job_deadline",
        "schema_name",
        "repair_attempted",
        # E2E S4: a prerequisite refusal names the unit it refused and the prerequisite units
        # that are incomplete, so an operator reads why the job stopped instead of a bare message.
        "unit_ordinal",
        "unmet_units",
    ):
        value = getattr(exc, attribute, None)
        if value is not None:
            details[attribute] = value
    # G5: a typed refusal names its subsystem cause in ``details.reason`` (docs/CONTRACTS.md
    # H-130 — the catalogue stays frozen) and carries its structured context there. The exception
    # owns both, so the mapping does not have to learn one branch per refusal type.
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason:
        details["reason"] = reason
    refusal_details = getattr(exc, "error_details", None)
    if isinstance(refusal_details, dict):
        for key, value in refusal_details.items():
            if len(details) >= 32:
                break
            details.setdefault(key, value)
    # A shape violation quotes the model's own rejected answer, which is the only way an operator
    # can read the rule that actually failed. It is bounded by the exception itself and carries no
    # key or credential.
    if getattr(exc, "violation", None):
        details["violation"] = str(getattr(exc, "violation"))[:500]
    details.update(_cost_details(exc))
    return contracts.build_error(code, message, **details)


def _cost_details(exc: Exception) -> dict[str, Any]:
    """Bounded typed cost facts for ``error.details``. Absent for non-cost failures."""
    if not hasattr(exc, "estimated_cost_usd"):
        return {}
    details: dict[str, Any] = {
        "reason": "cost_preflight_insufficient" if type(exc).__name__ == "CostPreflightRefused" else "cost_ceiling_exceeded",
        "sections_total": int(getattr(exc, "sections_total", 0) or 0),
        "sections_completed_count": int(len(getattr(exc, "sections_completed", []) or [])),
        "calls": int(getattr(exc, "calls", 0) or 0),
        "estimated_cost_usd": float(getattr(exc, "estimated_cost_usd", 0.0) or 0.0),
        "unknown_calls": int(getattr(exc, "unknown_calls", 0) or 0),
    }
    # Where the ceiling came from. Together with ``details.purpose`` (the call it refused, added by
    # ``_stage_error`` from the exception) and ``details.reason`` this cannot be read as a
    # validator's verdict (CP-015e).
    if getattr(exc, "budget_source", None):
        details["budget_source"] = str(getattr(exc, "budget_source"))
    for attribute in ("max_cost_usd", "max_calls"):
        value = getattr(exc, attribute, None)
        if value is not None:
            details[attribute] = value
    actions = list(getattr(exc, "actions", []) or [])
    if actions:
        details["actions"] = actions
    return details


def _stage_checkpoint(exc: Exception) -> dict[str, Any]:
    """The typed recovery checkpoint a failed stage wants persisted, if it has one."""
    factory = getattr(exc, "to_checkpoint", None)
    if not callable(factory):
        return {}
    try:
        checkpoint = factory()
    except Exception:  # noqa: BLE001 - a broken recovery record must not mask the failure
        return {}
    return checkpoint if isinstance(checkpoint, dict) else {}


def _view(job_id: str) -> dict[str, Any]:
    with db.read() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return {"job_id": job_id, "state": "failed"}
    return job_view(row)


def run_pending(
    resolvers: dict[str, Callable[[dict[str, Any]], Sequence[Stage]]],
    *,
    limit: int = 5,
    owner: str | None = None,
) -> list[dict[str, Any]]:
    """Drain up to ``limit`` queued jobs whose kind has a resolver.

    This is the pump a host calls (poll tick or ``ctx.spawn_task`` body). A job whose kind has no
    resolver stays ``queued`` rather than being failed: the family may be implemented by another
    package, and inventing a failure would be a false statement. ``resolvers`` build stages from
    the persisted brief, so a retry after edit never needs the original form.

    A store with no schema yet has no jobs to drain by definition (H-182/D6): the pump starts at
    plugin registration, before any Coursebook action has migrated anything, and opening the file
    then raised ``no such table: jobs`` (and created the empty database) on every tick.
    """
    if db.applied_schema_version() is None:
        return []
    with db.read() as connection:
        rows = connection.execute(
            "SELECT id, kind, brief_json FROM jobs WHERE state = 'queued' ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
    views: list[dict[str, Any]] = []
    for row in rows:
        resolver = resolvers.get(str(row["kind"]))
        if resolver is None:
            continue
        brief = _load(row["brief_json"], {})
        try:
            stages = resolver(brief)
        except Exception:  # noqa: BLE001 - a bad brief must not kill the pump
            continue
        views.append(execute(str(row["id"]), stages, owner=owner))
    return views


def list_jobs(*, state: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if state:
        clauses.append("state = ?")
        params.append(state)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with db.read() as connection:
        rows = connection.execute(
            f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ?", (*params, int(limit))
        ).fetchall()
    return [job_view(row) for row in rows]


# ── startup reconciliation ──────────────────────────────────────────────────

_RECONCILED = False


def ensure_startup_reconciled() -> dict[str, Any]:
    """Run the crash-recovery pass once per process, at plugin load.

    Guarded on an already-migrated database so importing the plugin never creates schema as a
    side effect of a load. Idempotent and safe to call from a host that reimports the module.
    """
    global _RECONCILED
    if _RECONCILED:
        return {"skipped": True, "reason": "already reconciled in this process"}
    if db.applied_schema_version() is None:
        return {"skipped": True, "reason": "database has no schema yet"}
    recovered = db.recover_interrupted()
    jobs = reconcile_startup(artifact_store=_default_store())
    _RECONCILED = True
    return {"attempts": recovered.get("attempts", 0), "jobs": jobs}


def _default_store() -> Any:
    from .artifacts import ArtifactStore

    return ArtifactStore()


def reconcile_expired(*, now: datetime | None = None) -> dict[str, Any]:
    """The liveness watchdog: settle live-state rows whose worker is provably gone.

    This is the live-process twin of :func:`reconcile_startup` and exists because that pass runs
    once per process (H-66): a job whose worker stopped beating — a crashed pump thread, a stage
    stranded in a foreign call, a lost profile context — sat ``running`` with a past lease until
    the next restart. G6 adds the second half of the evidence and a typed verdict:

    * a **live** lease is honoured, whoever owns it: a worker is still renewing it;
    * ``running`` whose lease lapsed **and** whose heartbeat is older than
      :func:`worker_lost_after_seconds` becomes ``failed`` carrying ``WORKER_LOST`` and a retry
      hint — the contract's retryable resting state, with the brief and checkpoint intact;
    * ``cancel_requested``/``cancelling`` with an expired/absent lease becomes ``cancelled``: no
      worker can still reach a boundary, so the intent is final.

    Every pass is idempotent: the write is conditional on the state and stale evidence re-read
    under the write lock, and a row already failed/cancelled is no longer a candidate.

    No artifact reconciliation here: this runs every few seconds, and only the startup pass may
    sweep files.

    A store with **no schema yet** is a skip, not a failure (H-182/D6). The reaper starts at plugin
    registration, before the first Coursebook action has migrated anything, and opening the file
    then both created an empty database and raised ``no such table: jobs`` every five seconds.
    Absent is not unreadable: a *migrated* store that cannot be read still raises exactly as before.
    """
    if db.applied_schema_version() is None:
        return {
            "worker_lost": 0,
            "cancelled": 0,
            "skipped": True,
            "reason": "database has no schema yet",
        }
    moment = _now(now)
    stamp = _iso(moment)

    def _settleable(row: Any) -> bool:
        """Same verdict as the pass below, usable on ugly and cheap reads alike."""
        state = str(row["state"])
        if state not in ("running", "cancel_requested", "cancelling"):
            return False
        held = _parse(row["lease_expires_at"])
        if held is not None and held > moment:
            return False  # a live worker is still beating; leaving it alone is the whole point
        if state == "running":
            return worker_is_lost(row, now=moment)
        return True

    with db.read() as connection:
        candidates = connection.execute(
            "SELECT id, state, lease_expires_at, updated_at, created_at FROM jobs WHERE state IN"
            " ('running','cancel_requested','cancelling')"
        ).fetchall()
    stale = [row for row in candidates if _settleable(row)]
    if not stale:
        return {"worker_lost": 0, "cancelled": 0}
    lost = cancelled = 0
    with db.transaction() as connection:
        for row in stale:
            # Re-read under the write lock: a beat may have renewed it since the read pass.
            current = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (row["id"],)
            ).fetchone()
            if current is None or not _settleable(current):
                continue
            if str(current["state"]) == "running":
                jobs_contract.assert_transition("running", "failed")
                connection.execute(
                    "UPDATE jobs SET state = 'failed', error_json = ?, lease_owner = NULL,"
                    " lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                    (_json(worker_lost_error(current, now=moment)), stamp, row["id"]),
                )
                lost += 1
            else:
                jobs_contract.assert_transition(str(current["state"]), "cancelled")
                connection.execute(
                    "UPDATE jobs SET state = 'cancelled', lease_owner = NULL, lease_expires_at = NULL,"
                    " updated_at = ? WHERE id = ?",
                    (stamp, row["id"]),
                )
                cancelled += 1
    return {"worker_lost": lost, "cancelled": cancelled}


def reconcile_startup(
    *,
    artifact_store: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Make the database honest after a crash/restart, once, at startup.

    * ``running`` jobs whose lease expired, or whose lease belongs to a *previous* process, are
      ``interrupted_requires_retry`` — the brief and checkpoint survive;
    * ``cancel_requested``/``cancelling`` jobs cannot still be running after a restart, so they are
      ``cancelled``;
    * orphaned staged/object artifact files are reconciled against the table;
    * nothing in flight is retried automatically, because an uncertain non-idempotent call must
      never be re-run blind.
    """
    moment = _now(now)
    stamp = _iso(moment)
    interrupted = cancelled = 0
    with db.transaction() as connection:
        rows = connection.execute(
            "SELECT id, state, lease_owner, lease_expires_at FROM jobs WHERE state IN"
            " ('running','cancel_requested','cancelling')"
        ).fetchall()
        for row in rows:
            state = str(row["state"])
            if state in ("cancel_requested", "cancelling"):
                jobs_contract.assert_transition(state, "cancelled")
                connection.execute(
                    "UPDATE jobs SET state = 'cancelled', lease_owner = NULL, lease_expires_at = NULL,"
                    " updated_at = ? WHERE id = ?",
                    (stamp, row["id"]),
                )
                cancelled += 1
                continue
            held = _parse(row["lease_expires_at"])
            # A *live* lease is honoured whoever owns it. ``WORKER_ID`` is random per process, so
            # treating another owner as stale let any second process that merely imported the
            # plugin (``hooks.STARTUP_RECONCILIATION``) reclaim a running job mid-stage — the
            # lesson stage died ``interrupted_requires_retry`` ~5s after it started. A process
            # that really died stops renewing, and its lease expires within ``LEASE_SECONDS``,
            # which is the only evidence of death this table actually has.
            stale = held is None or held <= moment
            if stale:
                jobs_contract.assert_transition(state, "interrupted_requires_retry")
                connection.execute(
                    "UPDATE jobs SET state = 'interrupted_requires_retry', lease_owner = NULL,"
                    " lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                    (stamp, row["id"]),
                )
                interrupted += 1
    cleanup: dict[str, int] = {}
    if artifact_store is not None:
        cleanup = artifact_store.reconcile(now=moment)
    return {"interrupted": interrupted, "cancelled": cancelled, "artifacts": cleanup}
