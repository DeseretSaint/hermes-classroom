"""CP-044: a hung provider request must be cancelled at the job's deadline, not abandoned.

CP-015 checkpoint 4 measured a plan job still ``running`` at 648 s while the provider request sat
open, and read it as "the job's deadline stops waiting but does not cancel the call". Two facts
are asserted separately here, because they are different bounds:

* the **purpose** deadline (``coursebook.plan.generate`` = 900 s declared) already cancels the
  in-flight coroutine on the live host's async seam — the first case pins that so a regression
  cannot slip through unnoticed;
* the **job attempt** deadline is the one CP-015 was missing: bounded calls that each finish in
  time could still keep the row ``running`` for hours. It must cancel the in-flight request and
  fail the row with the contract's existing ``HOST_UNAVAILABLE`` shape.

A socket-level stub makes "cancelled" observable: the stub accepts the connection and never
answers, so the only way the server sees EOF is a real cancellation. Nothing here asserts provider
output, tokens or spend — the stub never sends a response body.
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

from coursebook import executor, generation as gen, job_service
from tests.kernel_support import KernelCase
from tests.test_generation import FakeSearch

NOW = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)

#: How long the stub provider is allowed to keep the request open before the test concludes the
#: deadline did not cancel it.
STUB_HOLD_SECONDS = 60.0

#: How long after the job deadline the provider socket may still take to close.
CLOSE_GRACE_SECONDS = 10.0


class HungProviderStub:
    """A provider endpoint that accepts the connection and never replies.

    Records the accept time and, separately, the moment the client closed the socket. A
    cancellation shows up as EOF on ``recv``; an abandoned call shows up as neither.
    """

    def __init__(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(4)
        self._server.settimeout(0.2)
        self.host, self.port = self._server.getsockname()
        self.accepted_at: float | None = None
        self.closed_at: float | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, name="cp044-stub-provider", daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        conn: socket.socket | None = None
        deadline = time.monotonic() + STUB_HOLD_SECONDS
        try:
            while not self._stop.is_set() and time.monotonic() < deadline:
                if conn is None:
                    try:
                        conn, _ = self._server.accept()
                    except socket.timeout:
                        continue
                    self.accepted_at = time.monotonic()
                    conn.settimeout(0.2)
                    continue
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    data = b""
                if data == b"":
                    self.closed_at = time.monotonic()
                    return
                # The request arrived; the stub deliberately never answers it.
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
            try:
                self._server.close()
            except OSError:
                pass

    def wait_closed(self, seconds: float) -> bool:
        deadline = time.monotonic() + float(seconds)
        while self.closed_at is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.closed_at is not None

    def stop(self) -> None:
        self._stop.set()


class HungHostSeam:
    """The host's shape: an async sibling whose request is a real socket that never answers."""

    def __init__(self, port: int) -> None:
        self.port = int(port)
        self.opened = 0
        self.cancelled = 0

    async def acomplete_structured(self, **kwargs):  # noqa: ANN003 - host signature
        self.opened += 1
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        try:
            request = (
                "POST /v1/chat/completions HTTP/1.1\r\n"
                "Host: stub\r\nContent-Type: application/json\r\n"
                "Content-Length: 2\r\n\r\n{}"
            )
            writer.write(request.encode("ascii"))
            await writer.drain()
            await reader.read()  # only EOF or cancellation ends this
            raise AssertionError("the stub never answers; a return here is impossible")
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001 - teardown must not mask the outcome
                pass

    def complete_structured(self, **kwargs):  # noqa: ANN003 - must not be chosen
        raise AssertionError("the async sibling must be used when the host exposes it")


def _async_threads() -> set[threading.Thread]:
    """Supervised async worker threads alive right now, as objects, not names.

    Identity matters, not names: another test module's worker (H-199 leaves
    ``coursebook-async-coursebook.lesson.generate`` threads winding down for a few seconds) may be
    alive with the same name this job would use. Only a thread that this job *started* is this
    job's leak.
    """
    return {
        thread
        for thread in threading.enumerate()
        if thread.is_alive() and thread.name.startswith("coursebook-async-")
    }


class JobDeadlineCancelsHangingProviderCallTest(KernelCase):
    """A job against a provider that never answers ends in bounded wall time."""

    def _run_plan_job(self, *, call_deadline_s: float, job_deadline_s: float | None):
        # Snapshot before the job starts: whatever was already alive belongs to another test.
        prior_threads = _async_threads()
        stub = HungProviderStub()
        self.addCleanup(stub.stop)
        seam = HungHostSeam(stub.port)
        brief = {
            "stage": "plan",
            "goal": "Order coffee in Japanese",
            "recipe": "committed",
            "dials": {},
            "locale": "ja-JP",
            "level": "L0",
        }
        job_id = job_service.create("plan", brief, now=NOW)["job_id"]
        stages = executor.resolvers(
            llm=gen.PluginLLMAdapter(seam), search=FakeSearch(), now=NOW
        )[executor.JOB_KIND](brief)
        env = {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": str(call_deadline_s)}
        if job_deadline_s is not None:
            env["COURSEBOOK_JOB_DEADLINE_SECONDS"] = str(job_deadline_s)
        started = time.monotonic()
        with mock.patch.dict(os.environ, env):
            view = job_service.execute(job_id, stages, now=NOW)
        elapsed = time.monotonic() - started
        return view, seam, stub, elapsed, job_id, prior_threads

    def _assert_terminal_and_cancelled(
        self, view, seam, stub, elapsed, prior_threads, *, bound_s: float
    ) -> None:
        # 1. The job left ``running`` inside a bound only the deadline can explain.
        self.assertEqual(view["state"], "failed", view)
        self.assertLess(elapsed, bound_s, f"the job was not bounded by its deadline: {elapsed:.1f}s")
        self.assertIsNone(view["lease"], "the lease was not released on the failure path")
        self.assertEqual(view["error"]["code"], "HOST_UNAVAILABLE", view["error"])
        self.assertEqual(view["error"]["category"], "capability", view["error"])
        self.assertEqual(view["error"]["details"]["purpose"], "coursebook.plan.generate")

        # 2. The provider request was cancelled, not abandoned: the stub saw the socket close.
        self.assertIsNotNone(stub.accepted_at, "the provider request never reached the stub")
        self.assertTrue(
            stub.wait_closed(CLOSE_GRACE_SECONDS),
            "the provider socket stayed open after the deadline: the call was abandoned, not cancelled",
        )
        self.assertEqual(seam.opened, 1)
        self.assertEqual(seam.cancelled, 1, "the in-flight coroutine was never cancelled")

        # 3. No supervised worker *this job started* survived the deadline. Threads that were
        #    already alive before it (another module's) are not this job's leak, so they are not
        #    evidence either way: the claim is about new threads only.
        survivors = self._new_threads_after_grace(prior_threads)
        self.assertEqual(
            survivors,
            [],
            f"async worker(s) started by this job survived the deadline: {survivors}",
        )

    def _new_threads_after_grace(self, prior_threads: set[threading.Thread]) -> list[str]:
        """Wait (bounded) for this job's worker threads to exit, then name any that did not."""
        give_up = time.monotonic() + CLOSE_GRACE_SECONDS
        while time.monotonic() < give_up:
            new = _async_threads() - prior_threads
            if not new:
                return []
            time.sleep(0.05)
        return sorted(thread.name for thread in _async_threads() - prior_threads)

    def test_job_deadline_cancels_hanging_provider_call_before_its_purpose_deadline(self) -> None:
        """CP-044 RED case: the job deadline is 1.5 s, the call's own bound is 60 s."""
        view, seam, stub, elapsed, _job_id, prior_threads = self._run_plan_job(
            call_deadline_s=60.0, job_deadline_s=1.5
        )
        self._assert_terminal_and_cancelled(
            view, seam, stub, elapsed, prior_threads, bound_s=8.0
        )
        details = view["error"]["details"]
        self.assertTrue(details.get("job_deadline"), details)
        self.assertLessEqual(float(details["deadline_s"]), 2.0, details)
        self.assertIn("job's deadline", view["error"]["message"])

    def test_purpose_deadline_cancels_hanging_provider_call_and_closes_the_socket(self) -> None:
        """The live host's async seam already cancels at the call's own deadline (regression)."""
        view, seam, stub, elapsed, _job_id, prior_threads = self._run_plan_job(
            call_deadline_s=1.0, job_deadline_s=None
        )
        self._assert_terminal_and_cancelled(
            view, seam, stub, elapsed, prior_threads, bound_s=15.0
        )
        self.assertFalse(view["error"]["details"].get("job_deadline"), view["error"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
