"""Bounded execution for calls Coursebook does not own.

The execution path calls into two foreign seams: the host's ``ctx.llm`` (a provider request)
and the host's ``ctx.dispatch_tool`` (``web_search`` / ``web_extract`` / media tools). Either
can block far past any timeout the plugin *passes*: the host is free to ignore it, and a
blocked call is not interruptible from Python. Passing ``timeout=`` and checking elapsed time
after the call returns is a post-hoc verdict, not a deadline — that is H-66.

This module makes the deadline real **on the call path** (H-199):

* :func:`run_async_bounded` runs the host's async sibling on a supervised worker thread with
  its own event loop. The *calling* thread waits on an event with the deadline as its bound, so
  the caller returns at the deadline no matter what the loop thread is doing. This matters
  because ``asyncio.wait_for`` is not sufficient: a coroutine that blocks its loop thread
  (``time.sleep``, a synchronous client call) never lets the timer fire, and one that awaits
  ``asyncio.to_thread`` makes ``asyncio.run`` block in executor shutdown *after* the timeout
  fired. Both shapes overran the declared deadline live (H-199: an 888.4 s job against a 420 s
  deadline, and a 600 s deadline that never fired at all). On expiry the coroutine's task is
  cancelled best-effort and the worker is abandoned: the caller never waits for it.
* :class:`BoundedCallPool` runs a synchronous callable on a small, reused set of daemon
  workers. A worker stuck in a call is abandoned at the deadline, but the pool is **capped**:
  at most ``max_workers`` threads exist, so repeated timeouts cannot grow the process. Normal
  calls reuse the same worker — no thread per call.

Both paths accept ``on_wait``, a callable invoked with the elapsed seconds every
:data:`WAIT_HEARTBEAT_SECONDS` while the call is in flight. It runs on the **calling** thread,
which owns the caller's database connection, so a job can record a durable liveness row
without a second connection or a second thread.

A missed deadline raises :class:`DeadlineExceeded` (a ``TimeoutError``); callers translate it
into their own typed failure (``ProviderTimeout`` / ``ResearchTimeout`` / ``MediaTimeout``)
rather than leaking a generic exception to the job row.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import queue
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger("coursebook.deadline")

#: Seconds between wait-heartbeats while a foreign call is in flight. Small enough that a reader
#: sees a stalled job as *waiting* within one poll, large enough to cost one short write per beat.
WAIT_HEARTBEAT_SECONDS = 5.0

#: Cap on concurrently supervised async calls. A call that overran its deadline still holds its
#: slot until the worker actually returns, so a provider that hangs forever cannot grow the
#: process one abandoned loop thread per retry.
MAX_ASYNC_CALLS = 8


class DeadlineExceeded(TimeoutError):
    """A foreign call did not finish inside its declared deadline."""

    def __init__(self, label: str, deadline_s: float, *, elapsed_s: float | None = None) -> None:
        self.label = str(label)
        self.deadline_s = float(deadline_s)
        self.elapsed_s = elapsed_s
        message = f"{self.label} exceeded its {self.deadline_s:g}s deadline"
        if elapsed_s is not None:
            message += f" (waited {elapsed_s:g}s)"
        super().__init__(message)


class CallCapacityExhausted(RuntimeError):
    """Every bounded worker is stuck in a call that already missed its deadline.

    The caller must fail with a typed unavailable error rather than open another thread: an
    unbounded thread allowance for a hung foreign call is the defect this module replaces.
    """


def _await_with_heartbeat(
    done: threading.Event | Any,
    *,
    deadline_s: float,
    label: str,
    started: float,
    on_wait: Callable[[float], None] | None = None,
    heartbeat_s: float | None = None,
) -> None:
    """Wait for ``done`` up to the deadline, calling ``on_wait(elapsed_s)`` while waiting.

    ``done`` is a :class:`threading.Event`. The deadline is decided by *this* thread's clock, so
    no behaviour of the waited-on call can postpone the verdict. A heartbeat that raises is
    logged and ignored: liveness reporting must never decide a provider call.
    """
    interval = float(heartbeat_s or WAIT_HEARTBEAT_SECONDS)
    if interval <= 0:  # pragma: no cover - defensive
        interval = WAIT_HEARTBEAT_SECONDS
    while True:
        remaining = deadline_s - (time.monotonic() - started)
        if remaining <= 0:
            raise DeadlineExceeded(
                label, deadline_s, elapsed_s=round(time.monotonic() - started, 3)
            )
        if on_wait is None:
            if done.wait(remaining):
                return
            continue
        if done.wait(min(remaining, interval)):
            return
        try:
            on_wait(round(time.monotonic() - started, 3))
        except Exception as exc:  # noqa: BLE001 - a heartbeat never decides the call
            logger.debug("coursebook: wait heartbeat for %s failed: %s: %s", label, type(exc).__name__, exc)


class _Call:
    __slots__ = ("fn", "context", "done", "result", "error")

    def __init__(self, fn: Callable[[], Any], context: contextvars.Context) -> None:
        self.fn = fn
        self.context = context
        self.done = threading.Event()
        self.result: Any = None
        self.error: BaseException | None = None


class BoundedCallPool:
    """A capped pool of reused daemon workers for synchronous foreign calls."""

    def __init__(self, name: str, *, max_workers: int = 4) -> None:
        self.name = str(name)
        self.max_workers = max(1, int(max_workers))
        self._lock = threading.Lock()
        self._queue: "queue.Queue[_Call | None]" = queue.Queue()
        self._workers = 0
        self._inflight = 0

    # -- worker ------------------------------------------------------------
    def _work(self) -> None:
        while True:
            call = self._queue.get()
            if call is None:  # pragma: no cover - only the tests send a sentinel
                return
            try:
                call.result = call.context.run(call.fn)
            except BaseException as exc:  # noqa: BLE001 - handed to the waiting caller
                call.error = exc
            finally:
                with self._lock:
                    self._inflight -= 1
                call.done.set()

    def _spawn_locked(self) -> None:
        # Called with ``self._lock`` held. The worker starts blocked on the queue.
        self._workers += 1
        thread = threading.Thread(
            target=self._work, name=f"{self.name}-{self._workers}", daemon=True
        )
        thread.start()

    # -- public ------------------------------------------------------------
    def call(
        self,
        fn: Callable[[], T],
        *,
        timeout_s: float,
        label: str,
        on_wait: Callable[[float], None] | None = None,
        heartbeat_s: float | None = None,
    ) -> T:
        """Run ``fn`` under the caller's context; raise :class:`DeadlineExceeded` on overrun.

        A timed-out call is *not* cancelled (Python cannot interrupt it). Its worker is left
        to finish and rejoin the pool; meanwhile the occupied slot counts against
        ``max_workers``, so the process never accumulates threads faster than that bound.
        """
        deadline_s = float(timeout_s)
        if deadline_s <= 0:
            raise ValueError(f"deadline for {label!r} must be positive, got {deadline_s}")
        call = _Call(fn, contextvars.copy_context())
        with self._lock:
            if self._inflight >= self.max_workers:
                raise CallCapacityExhausted(
                    f"{self.name}: all {self.max_workers} bounded worker(s) are still inside "
                    f"calls that missed their deadline; refusing to start {label!r}"
                )
            self._inflight += 1
            # If fewer workers exist than calls in flight, every worker is busy: add one.
            if self._workers < self._inflight:
                self._spawn_locked()
        started = time.monotonic()
        self._queue.put(call)
        _await_with_heartbeat(
            call.done,
            deadline_s=deadline_s,
            label=label,
            started=started,
            on_wait=on_wait,
            heartbeat_s=heartbeat_s,
        )
        if call.error is not None:
            raise call.error
        return call.result

    def shutdown(self) -> None:  # pragma: no cover - test/agent teardown helper
        for _ in range(self._workers):
            self._queue.put(None)


#: The process-wide pool for host tool dispatches and synchronous provider fallbacks.
HOST_CALLS = BoundedCallPool("coursebook-host-call", max_workers=4)


def run_bounded(
    fn: Callable[[], T],
    *,
    timeout_s: float,
    label: str,
    on_wait: Callable[[float], None] | None = None,
    heartbeat_s: float | None = None,
) -> T:
    """Run a synchronous foreign call through :data:`HOST_CALLS`."""
    return HOST_CALLS.call(
        fn, timeout_s=timeout_s, label=label, on_wait=on_wait, heartbeat_s=heartbeat_s
    )


def has_running_loop() -> bool:
    """Whether the calling thread already owns a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


class _AsyncCall:
    """One supervised async call: its worker event loop, its task, and its completion signal."""

    __slots__ = ("factory", "done", "result", "error", "loop", "task")

    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory = factory
        self.done = threading.Event()
        self.result: Any = None
        self.error: BaseException | None = None
        self.loop: Any = None
        self.task: Any = None


#: Slots held by supervised async calls that have not finished on their worker thread yet.
_async_lock = threading.Lock()
_async_inflight = 0


def _release_async_slot() -> None:
    global _async_inflight
    with _async_lock:
        _async_inflight = max(0, _async_inflight - 1)


def _reserve_async_slot(label: str) -> None:
    global _async_inflight
    with _async_lock:
        if _async_inflight >= MAX_ASYNC_CALLS:
            raise CallCapacityExhausted(
                f"all {MAX_ASYNC_CALLS} supervised async call(s) are still inside calls that "
                f"overran their deadline; refusing to start {label!r}"
            )
        _async_inflight += 1


def _drive_async(call: _AsyncCall, context: contextvars.Context) -> None:
    """Worker body: own a fresh loop, run the coroutine, publish the outcome, release the slot.

    Executed on a daemon thread. If the caller already gave up at the deadline, nobody reads
    ``result``/``error``; the thread still finishes and frees its slot when the call returns.
    """

    async def _main() -> Any:
        call.task = asyncio.current_task()
        return await call.factory()

    def _run() -> None:
        loop = asyncio.new_event_loop()
        call.loop = loop
        try:
            asyncio.set_event_loop(loop)
            call.result = loop.run_until_complete(_main())
        except BaseException as exc:  # noqa: BLE001 - handed to the waiting caller
            call.error = exc
        finally:
            try:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:  # pragma: no cover - only a cancelled-then-abandoned coroutine
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except BaseException:  # noqa: BLE001 - teardown must never mask the outcome
                pass
            try:
                loop.close()
            except BaseException:  # noqa: BLE001
                pass
            _release_async_slot()
            call.done.set()

    try:
        context.run(_run)
    except BaseException:  # pragma: no cover - _run already swallows its own failures
        _release_async_slot()
        call.done.set()


def _cancel_async(call: _AsyncCall) -> None:
    """Ask the supervised loop to cancel its task. Best effort, never blocks the caller."""
    loop, task = call.loop, call.task
    if loop is None or task is None:
        return
    try:
        loop.call_soon_threadsafe(task.cancel)
    except BaseException:  # noqa: BLE001 - a closed loop means the call already ended
        pass


def run_async_bounded(
    awaitable_factory: Callable[[], Any],
    *,
    timeout_s: float,
    label: str,
    on_wait: Callable[[float], None] | None = None,
    heartbeat_s: float | None = None,
) -> Any:
    """Run a coroutine to completion under a hard deadline **on the calling thread's clock**.

    Must be called from a thread with **no** running loop (the job pump runs on a worker
    thread). The coroutine runs on its own daemon thread with its own event loop; this thread
    waits on an event, so the deadline is decided here and cannot be postponed by a coroutine
    that blocks its loop or by asyncio's executor shutdown. On expiry the task is cancelled
    best-effort and :class:`DeadlineExceeded` is raised immediately.
    """
    if has_running_loop():
        raise RuntimeError(f"{label}: run_async_bounded needs a thread without a running loop")
    deadline_s = float(timeout_s)
    if deadline_s <= 0:
        raise ValueError(f"deadline for {label!r} must be positive, got {deadline_s}")
    started = time.monotonic()
    call = _AsyncCall(awaitable_factory)
    _reserve_async_slot(label)
    thread = threading.Thread(
        target=_drive_async,
        args=(call, contextvars.copy_context()),
        name=f"coursebook-async-{label[:40]}",
        daemon=True,
    )
    try:
        thread.start()
    except BaseException:  # pragma: no cover - thread start failure releases the slot
        _release_async_slot()
        raise
    try:
        _await_with_heartbeat(
            call.done,
            deadline_s=deadline_s,
            label=label,
            started=started,
            on_wait=on_wait,
            heartbeat_s=heartbeat_s,
        )
    except DeadlineExceeded:
        _cancel_async(call)
        raise
    if call.error is not None:
        raise call.error
    return call.result
