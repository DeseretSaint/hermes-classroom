"""Agent-side job tick: the resolver table plus the bounded pump.

``coursebook/generation.py`` implements the plan and lesson pipelines and
``coursebook/job_service.py`` implements the durable job state machine, but until this module
nothing in a production path registered a resolver or called :func:`job_service.run_pending`.
A ``jobs.create`` from the Desktop therefore stayed ``queued`` forever.

Frozen decisions this module does **not** re-open (``docs/CONTRACTS.md`` §v6, decision (e)):

* there is **one** job kind, ``plan``. ``brief.stage`` selects the work: absent or ``"plan"``
  authors the plan; ``"lessons"`` with ``brief.plan_id`` materialises lessons for an approved
  plan. ``lesson`` is not a job kind because ``cb.vocabulary#job_kind`` is referenced by every
  pack manifest and adding it would force a ``cb.pack`` v2 that rejects installed v1 packs.
* the brief is the persisted ``jobs.brief_json`` row, so a retry after a restart or an edit never
  needs the original form.
* the existing lease / checkpoint / cancel semantics are reused. This is a resolver registration
  and a pump, not a second job engine.

The pump is bounded twice: at most :data:`MAX_JOBS_PER_TICK` jobs per call and one resolver run
per job. Provider work happens with **no transaction open** (``job_service.execute`` calls the
stage outside its fenced writes, and the generation pipeline owns its own short transactions).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime
from typing import Any, Callable, Sequence

from . import db, generation, job_service, media as media_mod, research

logger = logging.getLogger("coursebook.executor")

#: The single job kind this executor serves. Kept as a constant so a caller can assert it.
JOB_KIND = "plan"

#: Stage names. They are progress labels, never job kinds.
PLAN_STAGE = "plan"
LESSONS_STAGE = "lessons"

#: At most this many queued jobs are claimed in one tick. A tick must be short enough that the
#: next poll can observe a cancellation; draining an unbounded backlog in one call is not.
MAX_JOBS_PER_TICK = 5

#: Seconds between ticks in the agent process. Small enough that a queued job starts promptly,
#: large enough that an idle profile does no meaningful work.
TICK_SECONDS = 5.0

_STOP = threading.Event()
_TICK_TASK: Any = None
_TICK_THREAD: Any = None


def _resolve_search(explicit: Any) -> Any:
    """Return the search seam for this run: explicit, else the bound host tools, else none.

    ``None`` is honest: ``generation.run_plan_job`` records research status ``unavailable`` and
    marks every claim ``unverified`` instead of inventing a URL.
    """
    if explicit is not None:
        return explicit
    try:
        return research.host_search()
    except Exception:  # noqa: BLE001 - an unusable host seam is "unavailable", not a crash
        logger.warning("coursebook: host search seam unavailable for the job tick")
        return None


def _rejecting_stage(stage: str) -> Callable[[job_service.Lease], job_service.StageResult]:
    """A stage that fails the job visibly instead of leaving a typo'd brief queued forever."""

    def run(lease: job_service.Lease) -> job_service.StageResult:
        raise generation.GenerationRejected(f"unknown plan-job stage {stage!r}")

    return run


class _Resolvers:
    """Builds stages from a persisted brief. One resolver, dispatched on ``brief.stage``."""

    def __init__(self, llm: Any, search: Any, now: datetime | None) -> None:
        self.llm = llm
        self.search = search
        self.now = now

    def _llm(self) -> Any:
        # Resolved per stage, not per pump: an unbound host fails the *job* with a typed error
        # instead of making every idle tick raise.
        return self.llm if self.llm is not None else generation.host_llm()

    def __call__(self, brief: dict[str, Any]) -> Sequence[job_service.Stage]:
        stage = str((brief or {}).get("stage") or PLAN_STAGE)
        if stage == PLAN_STAGE:
            return [job_service.Stage(PLAN_STAGE, self._plan_stage(dict(brief or {})))]
        if stage == LESSONS_STAGE:
            return [job_service.Stage(LESSONS_STAGE, self._lessons_stage(dict(brief or {})))]
        return [job_service.Stage(stage or "invalid", _rejecting_stage(stage))]

    # ── stage bodies ────────────────────────────────────────────────────────

    def _plan_stage(self, brief: dict[str, Any]) -> Callable[[job_service.Lease], job_service.StageResult]:
        def run(lease: job_service.Lease) -> job_service.StageResult:
            # Cancellation boundary: a job cancelled before the stage starts spends nothing.
            if job_service.is_cancel_requested(lease.job_id):
                raise job_service.JobCancelled("cancelled before the plan stage")
            connection = db.connect()
            try:
                result = generation.run_plan_job(
                    connection,
                    {"job_id": lease.job_id, "brief": brief},
                    self._llm(),
                    search=self.search,
                    now=self.now,
                )
            finally:
                connection.close()
            return job_service.StageResult(
                artifacts=[],
                usage=[],  # generation already recorded the real usage against this job id
                checkpoint={
                    "plan_id": result.get("plan_id"),
                    "plan_hash": result.get("plan_hash"),
                    "plan_version": result.get("plan_version"),
                    "generation_state": result.get("status"),
                },
                message=f"plan authored ({result.get('status')})",
            )

        return run

    def _lessons_stage(self, brief: dict[str, Any]) -> Callable[[job_service.Lease], job_service.StageResult]:
        def run(lease: job_service.Lease) -> job_service.StageResult:
            if job_service.is_cancel_requested(lease.job_id):
                raise job_service.JobCancelled("cancelled before the lessons stage")
            connection = db.connect()
            try:
                result = generation.run_lesson_job(
                    connection,
                    {"job_id": lease.job_id, "brief": brief},
                    self._llm(),
                    plan_id=brief.get("plan_id"),
                    now=self.now,
                )
                lesson_ids = [
                    str(item.get("lesson_id"))
                    for item in result.get("lessons") or []
                    if isinstance(item, dict) and item.get("lesson_id")
                ]
                # Media is optional: the complete text lesson exists before this runs. A media
                # failure is recorded on the lesson item and never rolls back authored content.
                try:
                    media_result = media_mod.generate_for_lessons(
                        connection,
                        lesson_ids=lesson_ids,
                        job_id=lease.job_id,
                        now=self.now,
                    )
                except Exception as exc:  # noqa: BLE001 - media must not erase the lesson
                    logger.warning("coursebook: lesson media generation failed: %s", exc)
                    media_result = media_mod.MediaGenerationSummary(
                        artifact_ids=[], usage=[], skipped=len(lesson_ids)
                    )
                    media_error = f"{type(exc).__name__}: {exc}"
                else:
                    media_error = None
            finally:
                connection.close()
            media_usage = [
                job_service.UsageRecord(
                    provider=str(item.get("provider") or "media"),
                    model=item.get("model"),
                    tokens={},
                    duration_ms=int(item.get("duration_ms") or 0),
                    artifact_count=1,
                )
                for item in media_result.usage
            ]
            checkpoint = {
                "plan_id": result.get("plan_id"),
                "plan_hash": result.get("plan_hash"),
                "lessons": len(result.get("lessons") or []),
                "media": media_result.as_checkpoint(),
            }
            if media_error:
                checkpoint["media"]["error"] = media_error
            return job_service.StageResult(
                artifacts=list(media_result.artifact_ids),
                usage=media_usage,
                checkpoint=checkpoint,
                message=(
                    f"{len(result.get('lessons') or [])} lessons authored; "
                    f"{media_result.generated} media artifacts generated"
                ),
            )

        return run


def resolvers(*, llm: Any = None, search: Any = None, now: datetime | None = None) -> dict[str, Callable[..., Any]]:
    """The registration table a host passes to :func:`job_service.run_pending`.

    ``llm`` defaults to the host-bound adapter (``generation.host_llm()``), which fails loudly
    rather than falling back to a raw provider. ``search`` defaults to the host's own
    ``web_search``/``web_extract`` tools through :mod:`coursebook.research`.
    """
    resolved_llm = llm  # resolved lazily at stage run so an idle tick never raises
    resolved_search = _resolve_search(search)
    return {JOB_KIND: _Resolvers(resolved_llm, resolved_search, now)}


def pump_once(
    *,
    limit: int | None = None,
    owner: str | None = None,
    llm: Any = None,
    search: Any = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Drain up to ``limit`` queued jobs once. Safe to call from any thread.

    Returns the finished job views. A job whose kind has no resolver stays queued (the job
    service's rule, not this module's), and an unmigrated profile does nothing at all — a read
    path must never create the store it is reading.
    """
    if db.applied_schema_version() is None:
        return []
    count = MAX_JOBS_PER_TICK if limit is None else max(1, min(int(limit), MAX_JOBS_PER_TICK))
    return job_service.run_pending(
        resolvers(llm=llm, search=search, now=now), limit=count, owner=owner
    )


# ── the tick ────────────────────────────────────────────────────────────────


def stop() -> None:
    """Ask the tick loop to stop. Idempotent; the current pump finishes first."""
    _STOP.set()


async def _tick_loop(interval: float) -> None:
    wait = max(float(interval), 0.05)
    _STOP.clear()
    while not _STOP.is_set():
        try:
            # Job execution is blocking (SQLite + provider calls): never on the event loop.
            finished = await asyncio.to_thread(pump_once)
            if finished:
                logger.debug("coursebook job tick finished %d job(s)", len(finished))
        except Exception:  # noqa: BLE001 - one bad tick must not kill the loop
            logger.exception("coursebook job tick failed")
        waited = 0.0
        while not _STOP.is_set() and waited < wait:
            step = min(1.0, wait - waited)
            await asyncio.sleep(step)
            waited += step


def start_tick(ctx: Any, *, interval: float | None = None) -> Any:
    """Start the bounded tick in the agent process. Returns the spawned task/thread, or ``None``.

    Only a host that exposes ``ctx.spawn_task`` gets a loop: a bare test context or a
    dashboard-only process has no agent event loop, and inventing a thread there would outlive
    the object that owns it. ``on_unload``, when present, stops the loop.

    CB-011 integration fix (Vellum): ``ctx.spawn_task`` requires a *running* asyncio loop, but the
    Hermes plugin loader calls ``register(ctx)`` synchronously (observed on ``hermes serve`` and
    ``plugins doctor``: ``RuntimeWarning: coroutine '_tick_loop' was never awaited`` /
    ``ERROR: Plugin registration failed: no running event loop``). The result was that no queued
    ``plan`` job ever advanced in the real agent process, which is the whole Parent Studio pipeline.
    So: use ``spawn_task`` when a loop is already running, otherwise own a daemon thread with its
    own loop that calls the same bounded :func:`_tick_loop`. The pump itself is thread-safe
    (``job_service.run_pending`` opens its own connections), and ``on_unload`` stops either shape.
    Cinder owns this file: this is wiring only, no job state or provider logic changed.
    """
    global _TICK_TASK, _TICK_THREAD
    spawn = getattr(ctx, "spawn_task", None)
    if not callable(spawn):
        return None
    if _TICK_TASK is not None and not getattr(_TICK_TASK, "done", lambda: True)():
        return _TICK_TASK
    if _TICK_THREAD is not None and _TICK_THREAD.is_alive():
        return _TICK_THREAD
    configured = interval
    if configured is None:
        try:
            configured = float(os.environ.get("COURSEBOOK_JOB_TICK_SECONDS", TICK_SECONDS))
        except ValueError:
            configured = TICK_SECONDS
    _STOP.clear()
    unload = getattr(ctx, "on_unload", None)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No loop at registration time: own one so the tick is not silently absent.
        coro = _tick_loop(configured)

        def run() -> None:
            try:
                asyncio.run(coro)
            except Exception:  # noqa: BLE001 - a dead tick must not take the process down
                logger.exception("coursebook job tick thread stopped")

        _TICK_THREAD = threading.Thread(target=run, name="coursebook-job-tick", daemon=True)
        _TICK_THREAD.start()
        if callable(unload):
            unload(stop)
        logger.warning(
            "coursebook job tick started on its own thread: kind=%s interval=%.1fs limit=%d",
            JOB_KIND,
            configured,
            MAX_JOBS_PER_TICK,
        )
        return _TICK_THREAD
    _TICK_TASK = spawn(_tick_loop(configured), name="coursebook-job-tick")
    if callable(unload):
        unload(stop)
    logger.info(
        "coursebook job tick started: kind=%s interval=%.1fs limit=%d",
        JOB_KIND,
        configured,
        MAX_JOBS_PER_TICK,
    )
    return _TICK_TASK
