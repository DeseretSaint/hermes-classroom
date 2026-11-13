"""G6: a running job whose worker is gone is failed ``WORKER_LOST``, and cancel settles it.

Live evidence (2026-11-13): a plan job sat ``running`` for thirty minutes with no progress and a
stale lease (``gen_call_waits`` beats: 0), and ``jobs.cancel`` left it running. The contract these
tests pin is cause-independent: an expired lease plus a stale heartbeat is a dead worker, never a
live job; a cancel of that row settles it to ``cancelled`` without needing a worker thread; and a
job whose lease/heartbeat is fresh is never touched by either path.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from coursebook import contracts, job_service
from tests.kernel_support import KernelCase


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkerLostWatchdogTest(KernelCase):
    """The liveness watchdog: expired lease + stale heartbeat => failed / WORKER_LOST."""

    def new_job(self) -> str:
        return self.ok("jobs.create", {"kind": "research", "brief": {"goal": "x"}})["result"]["job_id"]

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]

    def test_expired_lease_and_stale_heartbeat_becomes_failed_worker_lost(self) -> None:
        job_id = self.new_job()
        # Claimed long ago: the lease lapsed and the row's last heartbeat is older than the window.
        job_service.claim(
            job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        result = job_service.reconcile_expired()
        self.assertEqual(result["worker_lost"], 1, result)
        view = self.job(job_id)
        self.assertEqual(view["state"], "failed")
        self.assertIsNone(view["lease"], "a failed worker's lease must not survive")
        error = view["error"]
        self.assertEqual(error["code"], "HOST_UNAVAILABLE")
        self.assertEqual(error["category"], "capability")
        self.assertTrue(error["retryable"])
        self.assertEqual(error["details"]["reason"], "WORKER_LOST")
        self.assertTrue(error["details"].get("retry_hint"), error)
        # The durable record is the contract's own error shape, not a hand-rolled dict.
        contracts.validate_definition("cb.errors", "error", error)

    def test_the_failed_row_carries_a_real_retry_hint_and_resumes(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(
            job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        job_service.checkpoint(
            lease, stage="one", steps_done=1, steps_total=2, checkpoint={"one": True}, now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        job_service.reconcile_expired()
        view = self.job(job_id)
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["checkpoint"]["one"], True, "retry evidence must survive the watchdog")
        resumed = job_service.resume(job_id)
        self.assertEqual(resumed["state"], "queued")
        self.assertEqual(resumed["checkpoint"]["one"], True)

    def test_the_watchdog_window_is_configurable(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 1))
        with mock.patch.dict(os.environ, {"COURSEBOOK_WORKER_LOST_SECONDS": "1"}):
            self.assertEqual(job_service.worker_lost_after_seconds(), 1.0)
            self.assertEqual(job_service.reconcile_expired()["worker_lost"], 1)

    def test_a_live_heartbeat_is_never_overridden(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="live-worker", now=_now())
        result = job_service.reconcile_expired()
        self.assertEqual(result["worker_lost"], 0, result)
        self.assertEqual(self.job(job_id)["state"], "running")

    def test_a_renewed_heartbeat_extends_life(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(
            job_id, owner="live-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 10)
        )
        job_service.renew(lease, now=_now())
        result = job_service.reconcile_expired()
        self.assertEqual(result["worker_lost"], 0, result)
        self.assertEqual(self.job(job_id)["state"], "running")

    def test_repeated_watchdog_passes_are_idempotent(self) -> None:
        job_id = self.new_job()
        job_service.claim(
            job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        first = job_service.reconcile_expired()
        self.assertEqual(first["worker_lost"], 1)
        second = job_service.reconcile_expired()
        self.assertEqual(second["worker_lost"], 0, second)
        self.assertEqual(second["cancelled"], 0, second)
        self.assertEqual(self.job(job_id)["state"], "failed")


class CancelSettlesDeadWorkerTest(KernelCase):
    """``jobs.cancel`` on an expired-lease row is a settlement, not a request to nobody."""

    def new_job(self) -> str:
        return self.ok("jobs.create", {"kind": "research", "brief": {"goal": "x"}})["result"]["job_id"]

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]

    def test_cancel_of_an_expired_running_job_reaches_cancelled(self) -> None:
        job_id = self.new_job()
        job_service.claim(
            job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        result = self.ok("jobs.cancel", {"job_id": job_id})["result"]
        self.assertEqual(result["state"], "cancelled")
        view = self.job(job_id)
        self.assertEqual(view["state"], "cancelled")
        self.assertIsNone(view["lease"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs WHERE state = 'running'"), 0)

    def test_cancel_of_an_expired_running_job_is_not_a_no_op_across_the_states(self) -> None:
        job_id = self.new_job()
        job_service.claim(
            job_id, owner="dead-worker", now=_now() - timedelta(seconds=job_service.LEASE_SECONDS + 30)
        )
        self.ok("jobs.cancel", {"job_id": job_id})
        # A second cancel finds a terminal row and says so instead of silently "succeeding".
        error = self.err("jobs.cancel", {"job_id": job_id})
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")
        self.assertEqual(self.job(job_id)["state"], "cancelled")

    def test_cancel_of_a_live_running_job_still_asks_the_worker(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="live-worker", now=_now())
        result = self.ok("jobs.cancel", {"job_id": job_id})["result"]
        self.assertEqual(result["state"], "cancel_requested")
        self.assertEqual(self.job(job_id)["state"], "cancel_requested")
        # The watchdog honours the live lease; nobody is killed mid-stage.
        self.assertEqual(job_service.reconcile_expired()["cancelled"], 0)
        self.assertEqual(self.job(job_id)["state"], "cancel_requested")

    def test_a_cancel_requested_row_still_settles_once_its_lease_lapses(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(job_id, owner="dead-worker", now=_now())
        job_service.request_cancel(job_id)
        self.assertEqual(self.job(job_id)["state"], "cancel_requested")
        result = job_service.reconcile_expired(
            now=_parse(lease.expires_at) + timedelta(seconds=1)
        )
        self.assertEqual(result["cancelled"], 1, result)
        self.assertEqual(self.job(job_id)["state"], "cancelled")

    def test_cancel_queued_job_still_spends_nothing(self) -> None:
        job_id = self.new_job()
        self.assertEqual(self.ok("jobs.cancel", {"job_id": job_id})["result"]["state"], "cancelled")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
