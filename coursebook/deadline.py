"""Bounded execution for calls Coursebook does not own.

The execution path calls into two foreign seams: the host's ``ctx.llm`` (a provider request)
and the host's ``ctx.dispatch_tool`` (``web_search`` / ``web_extract`` / media tools). Either
can block far past any timeout the plugin *passes*: the host is free to ignore it, and a
blocked call is not interruptible from Python. Passing ``timeout=`` and checking elapsed time
after the call returns is a post-hoc verdict, not a deadline — that is H-66.

This module makes the deadline real without leaking a blocking thread on every call:

* :func:`run_async_bounded` runs a coroutine under :func:`asyncio.wait_for`, which *cancels*
  it at the deadline. This is the preferred shape, and is what the provider path uses when the
  host exposes an async sibling (``PluginLlm.acomplete_structured``).
* :class:`BoundedCallPool` runs a synchronous callable on a small, reused set of daemon
  workers. A worker stuck in a call is abandoned at the deadline, but the pool is **capped**:
  at most ``max_workers`` threads exist, so repeated timeouts cannot grow the process. Normal
  calls reuse the same worker — no thread per call.

A missed deadline raises :class:`DeadlineExceeded` (a ``TimeoutError``); callers translate it
into their own typed failure (``ProviderTimeout`` / ``ResearchTimeout`` / ``MediaTimeout``)
rather than leaking a generic exception to the job row.
"""

from __future__ import annotations

import asyncio
import contextvars
import queue
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


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
    def call(self, fn: Callable[[], T], *, timeout_s: float, label: str) -> T:
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
        if not call.done.wait(deadline_s):
            raise DeadlineExceeded(
                label, deadline_s, elapsed_s=round(time.monotonic() - started, 3)
            )
        if call.error is not None:
            raise call.error
        return call.result

    def shutdown(self) -> None:  # pragma: no cover - test/agent teardown helper
        for _ in range(self._workers):
            self._queue.put(None)


#: The process-wide pool for host tool dispatches and synchronous provider fallbacks.
HOST_CALLS = BoundedCallPool("coursebook-host-call", max_workers=4)


def run_bounded(fn: Callable[[], T], *, timeout_s: float, label: str) -> T:
    """Run a synchronous foreign call through :data:`HOST_CALLS`."""
    return HOST_CALLS.call(fn, timeout_s=timeout_s, label=label)


def has_running_loop() -> bool:
    """Whether the calling thread already owns a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def run_async_bounded(awaitable_factory: Callable[[], Any], *, timeout_s: float, label: str) -> Any:
    """Run a coroutine to completion under a hard deadline, cancelling it on overrun.

    Must be called from a thread with **no** running loop (the job pump runs on a worker
    thread). The coroutine is cancelled at the deadline, so unlike a blocked thread it does
    not linger. Callers on a loop thread must use :func:`run_bounded` instead.
    """
    if has_running_loop():
        raise RuntimeError(f"{label}: run_async_bounded needs a thread without a running loop")
    deadline_s = float(timeout_s)
    if deadline_s <= 0:
        raise ValueError(f"deadline for {label!r} must be positive, got {deadline_s}")
    started = time.monotonic()

    async def _bounded() -> Any:
        return await asyncio.wait_for(awaitable_factory(), timeout=deadline_s)

    try:
        return asyncio.run(_bounded())
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise DeadlineExceeded(
            label, deadline_s, elapsed_s=round(time.monotonic() - started, 3)
        ) from exc
