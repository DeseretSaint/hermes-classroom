"""Durable job service: lease/fence, checkpoint, cancel states, restart recovery, no double spend."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, job_service
from tests.kernel_support import KernelCase

T0 = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)


class CountingStage:
    """A stage that records how many times it actually ran (i.e. how much spend happened)."""

    def __init__(self, name: str = "stage", *, artifact: bool = True, fail: bool = False,
                 cancel: bool = False, sleep_until_expired: bool = False) -> None:
        self.name = name
        self.runs = 0
        self.artifact = artifact
        self.fail = fail
        self.cancel = cancel
        self.sleep_until_expired = sleep_until_expired

    def __call__(self, lease: job_service.Lease) -> job_service.StageResult:
        self.runs += 1
        assert db.active_transactions() == 0, "provider work must run with no transaction open"
        if self.cancel:
            job_service.request_cancel(lease.job_id)
        if self.fail:
            raise RuntimeError("provider exploded")
        return job_service.StageResult(
            artifacts=["art_fake_1"] if self.artifact else [],
            usage=[job_service.UsageRecord(provider="fake", model=None, tokens={}, duration_ms=3,
                                           artifact_count=1 if self.artifact else 0)],
            checkpoint={self.name: True},
            message=f"{self.name} done",
        )


class JobServiceCase(KernelCase):
    def new_job(self, kind: str = "research", brief: dict | None = None, **kwargs) -> str:
        return self.ok("jobs.create", {"kind": kind, "brief": brief or {"goal": "x"}}, **kwargs)["result"]["job_id"]

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]


class CreationTest(JobServiceCase):
    def test_same_operation_id_never_mints_a_second_job(self) -> None:
        first = self.ok("jobs.create", {"kind": "research", "brief": {}}, operation_id="op-fixed-1")["result"]
        second = self.ok("jobs.create", {"kind": "research", "brief": {}}, operation_id="op-fixed-1")["result"]
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)

    def test_same_idempotency_key_and_payload_replays(self) -> None:
        payload = {"kind": "media", "brief": {"goal": "diagram"}}
        first = self.ok("jobs.create", payload, idempotency_key="key-job-1")["result"]
        second = self.ok("jobs.create", payload, idempotency_key="key-job-1")["result"]
        self.assertEqual(first, second)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)

    def test_same_key_different_payload_is_a_conflict(self) -> None:
        self.ok("jobs.create", {"kind": "media", "brief": {"goal": "a"}}, idempotency_key="key-job-2")
        error = self.err("jobs.create", {"kind": "media", "brief": {"goal": "b"}}, idempotency_key="key-job-2")
        self.assertEqual(error["code"], "IDEMPOTENCY_CONFLICT")


class LeaseFenceTest(JobServiceCase):
    def test_second_live_claim_is_refused(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(job_id, owner="worker-a", now=T0)
        with self.assertRaises(job_service.JobLeaseLost):
            job_service.claim(job_id, owner="worker-b", now=T0 + timedelta(seconds=5))
        self.assertEqual(job_service._view(job_id)["state"], "running")
        self.assertEqual(job_service._view(job_id)["attempt_id"], lease.attempt_id)

    def test_expired_lease_can_be_reclaimed_and_old_worker_is_fenced(self) -> None:
        job_id = self.new_job()
        old = job_service.claim(job_id, owner="worker-a", now=T0)
        stale = old
        new = job_service.claim(job_id, owner="worker-b", now=T0 + timedelta(seconds=job_service.LEASE_SECONDS + 1))
        self.assertNotEqual(stale.attempt_id, new.attempt_id)
        with self.assertRaises(job_service.JobLeaseLost):
            job_service.checkpoint(stale, stage="late", steps_done=1, steps_total=2, now=T0 + timedelta(seconds=200))
        # The new attempt still owns the row and its checkpoint was not clobbered.
        with self.assertRaises(job_service.JobLeaseLost):
            job_service.finish(stale, now=T0 + timedelta(seconds=200))
        self.assertEqual(job_service._view(job_id)["attempt_id"], new.attempt_id)

    def test_renew_extends_only_a_held_lease(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(job_id, owner="worker-a", now=T0)
        renewed = job_service.renew(lease, now=T0 + timedelta(seconds=10))
        self.assertGreater(renewed.expires_at, lease.expires_at)
        other = job_service.Lease(job_id, "att_someone_else", "worker-a", renewed.expires_at)
        with self.assertRaises(job_service.JobLeaseLost):
            job_service.renew(other, now=T0 + timedelta(seconds=11))

    def test_cancelled_job_cannot_be_claimed(self) -> None:
        job_id = self.new_job()
        job_service.request_cancel(job_id)
        with self.assertRaises(Exception) as caught:
            job_service.claim(job_id)
        self.assertEqual(getattr(caught.exception, "error", {}).get("code"), "JOB_STATE_INVALID")


class CancellationTest(JobServiceCase):
    def test_cancel_queued_spends_nothing(self) -> None:
        job_id = self.new_job()
        result = job_service.request_cancel(job_id)
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)

    def test_running_job_stops_at_the_next_stage_boundary(self) -> None:
        job_id = self.new_job()
        first = CountingStage("first")
        second = CountingStage("second")

        def cancel_between(lease):
            result = first(lease)
            job_service.request_cancel(lease.job_id)
            return result

        view = job_service.execute(
            job_id,
            [job_service.Stage("first", cancel_between), job_service.Stage("second", second)],
        )
        self.assertEqual(view["state"], "cancelled")
        self.assertEqual(first.runs, 1)
        self.assertEqual(second.runs, 0, "cancellation must stop future stages")
        # The completed stage's real usage is kept: you cannot un-spend a call that happened.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 1)

    def test_stage_that_finishes_during_cancel_becomes_completed_late(self) -> None:
        job_id = self.new_job()
        stage = CountingStage("pay", cancel=True)
        view = job_service.execute(job_id, [job_service.Stage("pay", stage)])
        self.assertEqual(view["state"], "completed_late")
        self.assertEqual(stage.runs, 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 1)
        # A completed_late job is terminal and cannot be cancelled again.
        error = self.err("jobs.cancel", {"job_id": job_id})
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")

    def test_cancel_requested_then_restart_becomes_cancelled(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="dead-worker")
        job_service.request_cancel(job_id)
        result = job_service.reconcile_startup(now=T0 + timedelta(hours=1))
        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(job_service._view(job_id)["state"], "cancelled")


class FailureAndRecoveryTest(JobServiceCase):
    def test_stage_failure_is_durable_and_retryable(self) -> None:
        job_id = self.new_job()
        failing = CountingStage("boom", fail=True)
        view = job_service.execute(job_id, [job_service.Stage("boom", failing)])
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"]["retryable"], True)
        self.assertIn("provider exploded", view["error"]["message"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs WHERE state = 'failed'"), 1)

    def test_restart_marks_running_job_interrupted_and_resume_keeps_checkpoint(self) -> None:
        job_id = self.new_job()
        lease = job_service.claim(job_id, owner="crashed-worker", now=T0)
        job_service.checkpoint(
            lease, stage="one", steps_done=1, steps_total=3, checkpoint={"one": True},
            artifact_ids=["art_done"], now=T0,
        )
        restarted = job_service.reconcile_startup(now=T0 + timedelta(hours=2))
        self.assertEqual(restarted["interrupted"], 1)
        view = job_service._view(job_id)
        self.assertEqual(view["state"], "interrupted_requires_retry")
        self.assertEqual(view["checkpoint"]["one"], True)
        resumed = job_service.resume(job_id, now=T0 + timedelta(hours=3))
        self.assertEqual(resumed["state"], "queued")
        self.assertEqual(resumed["checkpoint"]["one"], True)
        self.assertNotEqual(resumed["attempt_id"], lease.attempt_id)

    def test_resume_with_skip_does_not_repeat_a_finished_stage(self) -> None:
        job_id = self.new_job()
        first = CountingStage("one")
        second = CountingStage("two")

        def side_effects_then_crash(lease):
            first(lease)
            raise RuntimeError("crashed after the side effect, before the checkpoint")

        job_service.execute(job_id, [job_service.Stage("one", side_effects_then_crash)])
        self.assertEqual(job_service._view(job_id)["state"], "failed")
        job_service.resume(job_id)
        view = job_service.execute(
            job_id, [job_service.Stage("one", first), job_service.Stage("two", second)],
            skip_stages={"one"},
        )
        self.assertEqual(view["state"], "completed")
        self.assertEqual(first.runs, 1, "finished stage must not run again")
        self.assertEqual(second.runs, 1)

    def test_completed_job_is_terminal(self) -> None:
        job_id = self.new_job()
        job_service.execute(job_id, [job_service.Stage("one", CountingStage("one"))])
        error = self.err("jobs.cancel", {"job_id": job_id})
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")


class UsageTest(JobServiceCase):
    def test_usage_is_recorded_with_unknown_fields_null(self) -> None:
        job_id = self.new_job()
        job_service.execute(job_id, [job_service.Stage("one", CountingStage("one"))])
        rows = self.rows("SELECT provider, model, tokens_json, duration_ms, artifact_count FROM usage_events")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "fake")
        self.assertIsNone(rows[0]["model"], "an unknown model is null, never invented")
        self.assertEqual(rows[0]["duration_ms"], 3)
        self.assertEqual(rows[0]["artifact_count"], 1)

    def test_usage_summary_counts_recorded_artifacts_only(self) -> None:
        job_id = self.new_job()
        job_service.execute(job_id, [job_service.Stage("one", CountingStage("one"))])
        summary = self.ok("usage.summary", {})["result"]
        self.assertGreaterEqual(summary["artifacts"], 1)


if __name__ == "__main__":
    unittest.main()
