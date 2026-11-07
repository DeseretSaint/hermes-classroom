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
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Sequence

from . import contracts
from . import db
from . import jobs as jobs_contract
from .api import RpcError
from .research import ResearchCancelled

logger = logging.getLogger("coursebook.job_service")

#: Lease length. Short enough that a killed process is detected within one poll interval, long
#: enough that a slow provider call does not lose its fence between heartbeats.
LEASE_SECONDS = 120

#: Identity of this process's worker. Random per process: never a hostname or pid, which can be
#: reused and would make two workers look like one.
WORKER_ID = f"worker-{uuid.uuid4().hex[:12]}"

_MAX_ERROR_TEXT = 500


def _now(moment: datetime | None = None) -> datetime:
    return moment or datetime.now(timezone.utc)


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


class JobLeaseLost(RuntimeError):
    """Another attempt owns the job now. The caller must stop, not retry the write."""


class JobCancelled(ResearchCancelled):
    """The job's cancellation reached a safe boundary; the stage loop stops."""

    def __init__(self, reason: str, *, usage: list[Any] | None = None) -> None:
        super().__init__(reason)
        # Calls that already happened before the boundary are still real spend and must be
        # recorded; the executor takes them from here on the cancellation path.
        self.usage = list(usage or [])


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
    with db.read() as connection:
        row = connection.execute("SELECT state FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row is not None and str(row["state"]) in ("cancel_requested", "cancelling")


def request_cancel(job_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Record cancellation intent. ``cancelled`` means nothing further will run."""
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
    try:
        for index, stage in enumerate(stages, start=1):
            if stage.name in skip:
                continue
            if is_cancel_requested(job_id):
                begin_cancelling(lease)
                finish(lease, state="cancelled", now=now)
                return _view(job_id)
            renew(lease)
            try:
                result = _run_with_heartbeat(lease, stage, heartbeat_seconds)
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
                if is_cancel_requested(job_id):
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
            if is_cancel_requested(job_id):
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


#: Stage exceptions that are the *host's* problem, mapped to the contract's capability code.
#: ``HOST_UNAVAILABLE`` means "the Hermes host (gateway, auxiliary model, media provider) is
#: unavailable"; ``GRADER_UNAVAILABLE`` is about grading an answer, and reporting a provider
#: deadline as a grader failure sends the reader to the wrong subsystem (CB-011-D1).
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
    for attribute in ("purpose", "duration_ms", "deadline_s"):
        value = getattr(exc, attribute, None)
        if value is not None:
            details[attribute] = value
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
    """
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


def reconcile_expired(*, now: datetime | None = None) -> dict[str, int]:
    """Move **expired-lease** live rows to a terminal/honest state; safe to call repeatedly.

    This is the live-process twin of :func:`reconcile_startup` and exists because that pass runs
    once per process (H-66): a job whose worker stopped beating — a crashed pump thread, a stage
    stranded in a foreign call, a lost profile context — sat ``running`` with a past lease until
    the next restart. The rule here is intentionally narrower than startup recovery:

    * a **live** lease is honoured, whoever owns it: a worker is still renewing it;
    * ``running`` with an expired/absent lease becomes ``interrupted_requires_retry`` (brief and
      checkpoint survive, nothing is retried automatically);
    * ``cancel_requested``/``cancelling`` with an expired/absent lease becomes ``cancelled``: no
      worker can still reach a boundary, so the intent is final.

    No artifact reconciliation here: this runs every few seconds, and only the startup pass may
    sweep files.
    """
    moment = _now(now)
    stamp = _iso(moment)
    with db.read() as connection:
        candidates = connection.execute(
            "SELECT id, state, lease_expires_at FROM jobs WHERE state IN"
            " ('running','cancel_requested','cancelling')"
        ).fetchall()
    stale = [
        row
        for row in candidates
        if (held := _parse(row["lease_expires_at"])) is None or held <= moment
    ]
    if not stale:
        return {"interrupted": 0, "cancelled": 0}
    interrupted = cancelled = 0
    with db.transaction() as connection:
        for row in stale:
            # Re-read under the write lock: a beat may have renewed it since the read pass.
            current = connection.execute(
                "SELECT state, lease_expires_at FROM jobs WHERE id = ?", (row["id"],)
            ).fetchone()
            if current is None:
                continue
            state = str(current["state"])
            if state not in ("running", "cancel_requested", "cancelling"):
                continue
            held = _parse(current["lease_expires_at"])
            if held is not None and held > moment:
                continue  # a live worker is still beating; leaving it alone is the whole point
            target = "interrupted_requires_retry" if state == "running" else "cancelled"
            jobs_contract.assert_transition(state, target)
            connection.execute(
                "UPDATE jobs SET state = ?, lease_owner = NULL, lease_expires_at = NULL,"
                " updated_at = ? WHERE id = ?",
                (target, stamp, row["id"]),
            )
            if target == "cancelled":
                cancelled += 1
            else:
                interrupted += 1
    return {"interrupted": interrupted, "cancelled": cancelled}


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
