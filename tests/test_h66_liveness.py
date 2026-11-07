"""H-66 liveness regressions: every foreign call is bounded, leases are reaped live.

The defect: a live ``plan`` job sat ``running`` for nine minutes with an expired lease, no
heartbeat renewal, empty progress, and a cancellation that never reached a boundary. Three
unbounded waits plus one silently broken heartbeat caused it; each has a test here.

Run only these with::

    python3 -m unittest tests.test_h66_liveness -v
"""

from __future__ import annotations

import asyncio
import contextvars
import os
import shutil
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from coursebook import db, deadline as deadline_mod, executor, generation, job_service, research
from tests.kernel_support import KernelCase

T0 = datetime(2026, 11, 7, 19, 25, 39, tzinfo=timezone.utc)


def _request(purpose: str = "coursebook.plan.generate", *, timeout_s: float = 0.25):
    return generation.LLMRequest(
        purpose=purpose,
        prompt_version="h66",
        system_prompt="h66",
        instructions="h66",
        input_text="h66",
        schema={"type": "object"},
        schema_name="h66",
        max_tokens=8,
        timeout_s=timeout_s,
    )


def _response(text: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(text=text, parsed={}, provider="fake", model="fake", usage=None)


def _threads(prefix: str) -> list[str]:
    return [t.name for t in threading.enumerate() if t.is_alive() and t.name.startswith(prefix)]


class HostToolDeadlineTest(KernelCase):
    """A host tool that blocks is a typed ``ResearchTimeout`` at the declared deadline."""

    def test_stalled_web_search_returns_a_typed_timeout(self) -> None:
        release = threading.Event()

        class StallingHost:
            calls = 0

            def dispatch_tool(self, name: str, args: dict, **kwargs):  # noqa: ANN001
                StallingHost.calls += 1
                release.wait(10.0)
                return '{"success": true, "data": {"web": []}}'

        seam = research.HermesToolSearch(StallingHost(), timeout_s=0.2)
        started = time.monotonic()
        try:
            with self.assertRaises(research.ResearchTimeout) as caught:
                seam.search("braise short ribs", 3)
        finally:
            release.set()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0, "the adapter must enforce its own deadline")
        self.assertEqual(caught.exception.deadline_s, 0.2)
        self.assertEqual(caught.exception.tool, "web_search")

    def test_one_stalled_tool_does_not_burn_the_whole_query_budget(self) -> None:
        release = threading.Event()
        calls = {"n": 0}

        class StallingHost:
            def dispatch_tool(self, name: str, args: dict, **kwargs):  # noqa: ANN001
                calls["n"] += 1
                release.wait(10.0)
                return "{}"

        seam = research.HermesToolSearch(StallingHost(), timeout_s=0.15)
        budget = research.ResearchBudget(max_queries=6, max_pages=4, max_sources=4)
        started = time.monotonic()
        try:
            run = research.run_research("braise short ribs", search=seam, budget=budget)
        finally:
            release.set()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertEqual(run.status, "unavailable")
        self.assertEqual(calls["n"], 1, "a timed-out host tool must stop the pass, not repeat it")
        # The failure is recorded honestly, not invented into a source.
        self.assertEqual(run.sources, [])
        self.assertTrue(any("deadline" in (entry.get("error") or "") for entry in run.queries))

    def test_a_host_exception_propagates_to_the_caller(self) -> None:
        """Unchanged contract: a host *error* is not a deadline; research records it per query."""

        class BrokenHost:
            def dispatch_tool(self, name: str, args: dict, **kwargs):  # noqa: ANN001
                raise RuntimeError("provider exploded")

        seam = research.HermesToolSearch(BrokenHost(), timeout_s=1.0)
        with self.assertRaises(RuntimeError):
            seam.search("q", 1)


class ProviderDeadlineTest(KernelCase):
    """The provider deadline is executable, not a post-hoc elapsed-time verdict."""

    def test_sync_only_host_is_cut_off_at_its_deadline(self) -> None:
        release = threading.Event()

        class StallingLLM:
            def complete_structured(self, **kwargs):  # noqa: ANN003
                release.wait(10.0)
                return _response()

        adapter = generation.PluginLLMAdapter(StallingLLM())
        started = time.monotonic()
        try:
            with self.assertRaises(generation.ProviderTimeout) as caught:
                generation._call_llm(adapter, _request(timeout_s=0.2), generation._Usage(generation.default_cost_budget()))
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(caught.exception.purpose, "coursebook.plan.generate")
        self.assertEqual(caught.exception.deadline_s, 0.2)

    def test_async_sibling_is_preferred_and_cancelled_at_the_deadline(self) -> None:
        class AsyncOnly:
            def complete_structured(self, **kwargs):  # noqa: ANN003
                raise AssertionError("the async sibling must be used when present")

            async def acomplete_structured(self, **kwargs):  # noqa: ANN003
                await asyncio.sleep(10.0)
                return _response()

        adapter = generation.PluginLLMAdapter(AsyncOnly())
        before = len(threading.enumerate())
        started = time.monotonic()
        with self.assertRaises(generation.ProviderTimeout):
            generation._call_llm(
                adapter, _request(timeout_s=0.2), generation._Usage(generation.default_cost_budget())
            )
        self.assertLess(time.monotonic() - started, 2.0)
        # A bounded coroutine is cancelled, not parked on a leaking daemon thread.
        self.assertLessEqual(len(threading.enumerate()), before + 1)

    def test_bounded_pool_reuses_one_worker_in_the_normal_path(self) -> None:
        pool = deadline_mod.BoundedCallPool("h66-pool-reuse", max_workers=2)
        try:
            for _ in range(5):
                self.assertEqual(pool.call(lambda: 7, timeout_s=1.0, label="ok"), 7)
            self.assertEqual(len(_threads("h66-pool-reuse")), 1)
        finally:
            pool.shutdown()

    def test_stuck_pool_capacity_fails_fast_instead_of_growing_threads(self) -> None:
        pool = deadline_mod.BoundedCallPool("h66-pool-cap", max_workers=1)
        release = threading.Event()
        try:
            with self.assertRaises(deadline_mod.DeadlineExceeded):
                pool.call(lambda: release.wait(5.0), timeout_s=0.1, label="stuck")
            started = time.monotonic()
            with self.assertRaises(deadline_mod.CallCapacityExhausted):
                pool.call(lambda: 1, timeout_s=1.0, label="next")
            self.assertLess(time.monotonic() - started, 0.5, "no second unbounded wait")
            self.assertEqual(len(_threads("h66-pool-cap")), 1, "the pool stays capped")
        finally:
            release.set()
            pool.shutdown()


class HeartbeatTest(KernelCase):
    """The heartbeat must keep renewing the lease under the caller's profile context."""

    def test_lease_is_renewed_while_a_stage_runs_under_a_context_local_home(self) -> None:
        import hermes_constants

        job_id = job_service.create("plan", {"goal": "probe", "stage": "plan"})["job_id"]
        fallback = tempfile.mkdtemp(prefix="h66-fallback-")
        previous_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = fallback  # what a bare thread would resolve
        token = hermes_constants.set_hermes_home_override(self.home)  # the gateway's profile
        started = threading.Event()
        release = threading.Event()

        class BlockingStage:
            def __call__(self, lease):  # noqa: ANN001
                started.set()
                release.wait(5.0)
                return job_service.StageResult(checkpoint={"ran": True})

        context = contextvars.copy_context()
        real_renew = job_service.renew
        renewed = {"count": 0}

        def counting_renew(lease, **kwargs):  # noqa: ANN001
            result = real_renew(lease, **kwargs)  # only a *successful* renew counts
            renewed["count"] += 1
            return result

        def run_stage() -> None:
            job_service.execute(
                job_id,
                [job_service.Stage("slow", BlockingStage())],
                heartbeat_seconds=0.15,
            )

        try:
            with mock.patch.object(job_service, "renew", counting_renew):
                worker = threading.Thread(
                    target=context.run, args=(run_stage,), name="h66-tick", daemon=True
                )
                worker.start()
                self.assertTrue(started.wait(3.0))
                self.assertTrue(
                    any(name.startswith("job-heartbeat-") for name in _threads("job-heartbeat-"))
                )
                time.sleep(0.8)
                release.set()
                worker.join(6.0)
        finally:
            release.set()
            hermes_constants.reset_hermes_home_override(token)
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home
            shutil.rmtree(fallback, ignore_errors=True)
        # One renew happens before the stage opens; the heartbeat must add several more while it
        # runs. Before the H-66 fix each beat resolved the fallback home, raised NOT_FOUND, and
        # was swallowed, so this count stayed at 1.
        self.assertGreaterEqual(renewed["count"], 3, "the heartbeat must renew the lease mid-stage")
        self.assertEqual(job_service._view(job_id)["state"], "completed")


class CancellationTest(KernelCase):
    """Cancellation reaches a boundary, including when the blocking call times out."""

    def new_job(self, kind: str = "plan", brief: dict | None = None) -> str:
        return job_service.create(kind, brief or {"goal": "x"})["job_id"]

    def test_cancel_that_times_out_a_provider_call_ends_cancelled_not_failed(self) -> None:
        job_id = self.new_job()

        def run(lease):  # noqa: ANN001
            job_service.request_cancel(job_id)
            raise generation.ProviderTimeout(
                "coursebook.plan.generate exceeded its deadline",
                purpose="coursebook.plan.generate",
                deadline_s=0.2,
            )

        view = job_service.execute(job_id, [job_service.Stage("plan", run)])
        self.assertEqual(view["state"], "cancelled")
        self.assertIsNone(view["error"])

    def test_cancel_requested_job_is_never_left_in_a_live_state(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="dead-worker", now=T0)
        job_service.request_cancel(job_id, now=T0 + timedelta(seconds=1))
        result = job_service.reconcile_expired(now=T0 + timedelta(seconds=job_service.LEASE_SECONDS + 2))
        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(job_service._view(job_id)["state"], "cancelled")


class ReconciliationTest(KernelCase):
    """An expired ownerless lease is resolved live, without a process restart."""

    def test_expired_running_job_becomes_interrupted(self) -> None:
        job_id = job_service.create("plan", {"goal": "x"})["job_id"]
        job_service.claim(job_id, owner="dead-worker", now=T0)
        result = job_service.reconcile_expired(now=T0 + timedelta(seconds=job_service.LEASE_SECONDS + 2))
        self.assertEqual(result["interrupted"], 1)
        view = job_service._view(job_id)
        self.assertEqual(view["state"], "interrupted_requires_retry")
        self.assertIsNone(view["lease"])

    def test_a_live_lease_is_honoured(self) -> None:
        job_id = job_service.create("plan", {"goal": "x"})["job_id"]
        job_service.claim(job_id, owner="live-worker", now=T0)
        result = job_service.reconcile_expired(now=T0 + timedelta(seconds=5))
        self.assertEqual(result, {"interrupted": 0, "cancelled": 0})
        self.assertEqual(job_service._view(job_id)["state"], "running")

    def test_repeated_reconciliation_is_idempotent(self) -> None:
        job_id = job_service.create("plan", {"goal": "x"})["job_id"]
        job_service.claim(job_id, owner="dead-worker", now=T0)
        later = T0 + timedelta(seconds=job_service.LEASE_SECONDS + 2)
        self.assertEqual(job_service.reconcile_expired(now=later)["interrupted"], 1)
        self.assertEqual(job_service.reconcile_expired(now=later), {"interrupted": 0, "cancelled": 0})


class ReaperThreadTest(KernelCase):
    """The live reaper is a separate thread, so a stuck pump cannot stop reconciliation."""

    def tearDown(self) -> None:  # noqa: N802 - unittest API
        executor.stop()
        for thread in (executor._REAPER_THREAD, executor._TICK_THREAD):
            if thread is not None and callable(getattr(thread, "join", None)):
                thread.join(5.0)
        executor._STOP.clear()
        executor._TICK_THREAD = None
        executor._TICK_TASK = None
        executor._REAPER_THREAD = None
        super().tearDown()

    class _Ctx:
        def __init__(self) -> None:
            self.unloads: list = []

        def spawn_task(self, coro, *, name=None):  # noqa: ANN001
            coro.close()
            raise AssertionError("this test takes the no-running-loop branch")

        def on_unload(self, callback) -> None:  # noqa: ANN001
            self.unloads.append(callback)

    def test_start_tick_starts_a_lease_reaper(self) -> None:
        with mock.patch.dict(os.environ, {"COURSEBOOK_JOB_TICK_SECONDS": "0.05"}):
            executor.start_tick(self._Ctx())
        self.assertTrue(_threads("coursebook-job-reaper"), "the reaper must run beside the pump")

    def test_reaper_fixes_an_expired_job_without_a_restart(self) -> None:
        job_id = job_service.create("plan", {"goal": "x"})["job_id"]
        job_service.claim(job_id, owner="dead-worker", now=T0)
        self.assertEqual(job_service._view(job_id)["state"], "running")
        with mock.patch.dict(os.environ, {"COURSEBOOK_JOB_TICK_SECONDS": "0.05"}), mock.patch.object(
            executor, "REAPER_SECONDS", 0.1
        ):
            executor.start_tick(self._Ctx())
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if job_service._view(job_id)["state"] == "interrupted_requires_retry":
                    break
                time.sleep(0.05)
        self.assertEqual(job_service._view(job_id)["state"], "interrupted_requires_retry")


class EndToEndPumpTest(KernelCase):
    """The exact reproduction shape: a plan job whose provider stalls terminates, typed."""

    def setUp(self) -> None:  # noqa: N802 - unittest API
        super().setUp()
        self._validator = generation._VALIDATOR_LLM
        generation._VALIDATOR_LLM = None

    def tearDown(self) -> None:  # noqa: N802
        generation._VALIDATOR_LLM = self._validator
        super().tearDown()

    def test_stalled_provider_fails_the_plan_job_within_the_bound(self) -> None:
        release = threading.Event()
        calls = {"n": 0}

        class StallingLLM:
            def complete_structured(self, **kwargs):  # noqa: ANN003
                calls["n"] += 1
                release.wait(10.0)
                return _response()

        job_id = job_service.create("plan", {"goal": "Braise short ribs", "stage": "plan"})["job_id"]
        started = time.monotonic()
        try:
            with mock.patch.dict(
                os.environ, {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": "0.2"}
            ):
                views = executor.pump_once(llm=generation.PluginLLMAdapter(StallingLLM()))
        finally:
            release.set()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0, "the pump must return; it may not hang on the provider")
        self.assertEqual(calls["n"], 1)
        view = job_service._view(job_id)
        self.assertEqual(view["state"], "failed")
        self.assertEqual((view["error"] or {}).get("code"), "HOST_UNAVAILABLE")
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM jobs WHERE state = 'running'"),
            0,
            "no job may be left running after its bounded call returns",
        )
        self.assertEqual(len(views), 1)

    def test_no_running_row_survives_a_stalled_host_tool(self) -> None:
        release = threading.Event()

        class StallingHost:
            def dispatch_tool(self, name: str, args: dict, **kwargs):  # noqa: ANN001
                release.wait(10.0)
                return "{}"

        class ImmediateLLM:
            def complete_structured(self, **kwargs):  # noqa: ANN003
                raise AssertionError("research must fail before any provider call")

        seam = research.HermesToolSearch(StallingHost(), timeout_s=0.2)
        job_id = job_service.create("plan", {"goal": "Braise short ribs", "stage": "plan"})["job_id"]
        started = time.monotonic()
        try:
            executor.pump_once(llm=generation.PluginLLMAdapter(ImmediateLLM()), search=seam)
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 5.0)
        view = job_service._view(job_id)
        # The pump returned a terminal row: a timed-out host tool cannot leave `running` behind.
        self.assertNotEqual(view["state"], "running")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs WHERE state = 'running'"), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
