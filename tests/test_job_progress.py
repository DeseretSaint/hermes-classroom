"""H-139: the job activity/usage read model is honest at every stage and every failure.

The pane's only question is "is this long wait work or breakage?", and the backend must answer it
from durable state: the stage it actually checkpointed, the time actually elapsed, the actions the
command layer actually accepts, and the usage rows actually recorded against this job id. These
tests cover each resting state, a provider failure, idempotent cancellation, and the two read
failures that must be *named* instead of rendering as `queued`/0%.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from jsonschema import Draft202012Validator

from coursebook import contracts, db, generation as gen, job_service
from tests.kernel_support import KernelCase

T0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)


class CountingStage:
    """A real stage: records spend and returns a checkpoint (no provider)."""

    def __init__(self, name: str = "stage", *, artifact: int = 1) -> None:
        self.name = name
        self.runs = 0
        self.artifact = artifact

    def __call__(self, lease: job_service.Lease) -> job_service.StageResult:
        self.runs += 1
        assert db.active_transactions() == 0
        return job_service.StageResult(
            artifacts=[f"art_{self.name}"] if self.artifact else [],
            usage=[
                job_service.UsageRecord(
                    provider="fake",
                    model="fake-1",
                    tokens={},
                    duration_ms=7,
                    artifact_count=self.artifact,
                )
            ],
            checkpoint={self.name: True},
            message=f"{self.name} done",
        )


class ProgressCase(KernelCase):
    def new_job(self, kind: str = "plan", brief: dict | None = None) -> str:
        return self.ok("jobs.create", {"kind": kind, "brief": brief or {"goal": "x"}})["result"]["job_id"]

    def job(self, job_id: str) -> dict:
        return self.ok("jobs.get", {"job_id": job_id})["result"]["job"]

    def activity(self, job_id: str) -> dict:
        return self.job(job_id)["activity"]

    def assert_contract_legal(self, job: dict) -> None:
        document = contracts.contract("cb.jobs")
        Draft202012Validator({**document, "$ref": "#/job"}, registry=contracts.registry()).validate(job)


class StageReadTest(ProgressCase):
    def test_a_queued_job_names_the_brief_stage_and_invents_no_total(self) -> None:
        for brief_stage in ("plan", "unit_sections", "lessons"):
            with self.subTest(stage=brief_stage):
                job_id = self.new_job(brief={"stage": brief_stage, "goal": "x"})
                activity = self.activity(job_id)
                self.assertEqual(activity["stage"], brief_stage)
                self.assertEqual(activity["stage_source"], "brief")
                self.assertIsNone(activity["steps_total"], "an unknown total is null, never 0")
                self.assertEqual(activity["steps_done"], 0)
                self.assertTrue(activity["can_cancel"])
                self.assertFalse(activity["terminal"])
                self.assertFalse(activity["can_retry"])
                self.assertEqual(activity["elapsed_basis"], "created_to_now")
                self.assertIsInstance(activity["elapsed_seconds"], int)
                self.assertNotIn("percent", activity, "no percentage is invented")
        # The import family's stage is served by the same read, with no plan-brief enum involved.
        import_job = self.ok(
            "jobs.create",
            {"kind": "import", "brief": {"stage": "syllabus_parse", "syllabus_id": "syl_12345678", "revision": 1}},
        )["result"]["job_id"]
        activity = self.activity(import_job)
        self.assertEqual(activity["stage"], "syllabus_parse")
        self.assertEqual(activity["stage_source"], "brief")

    def test_a_naive_durable_stamp_still_measures_elapsed(self) -> None:
        # Older rows (and hand-written fixtures) store ``2026-01-01`` with no offset. Treating it
        # as naive raised inside the read; the honest answer is a number in UTC.
        job_id = self.new_job()
        self.execute(
            "UPDATE jobs SET created_at = '2026-01-01', updated_at = '2026-01-01' WHERE id = ?",
            (job_id,),
        )
        activity = self.activity(job_id)
        self.assertIsInstance(activity["elapsed_seconds"], int)
        self.assertGreaterEqual(activity["elapsed_seconds"], 0)

    def test_a_queued_job_with_no_named_stage_says_queued_not_none(self) -> None:
        job_id = self.new_job(brief={})
        activity = self.activity(job_id)
        self.assertIsNone(activity["stage"])
        self.assertEqual(activity["stage_source"], "queued")

    def test_a_checkpointed_stage_wins_over_the_brief(self) -> None:
        job_id = self.new_job(brief={"stage": "plan"})
        lease = job_service.claim(job_id, owner="worker-a", now=T0)
        job_service.checkpoint(
            lease, stage="research", steps_done=1, steps_total=None,
            message="gathered 4 sources", checkpoint={"sources": 4}, now=T0,
        )
        activity = self.activity(job_id)
        self.assertEqual(activity["stage"], "research")
        self.assertEqual(activity["stage_source"], "checkpoint")
        self.assertEqual(activity["steps_done"], 1)
        self.assertIsNone(activity["steps_total"])
        self.assertEqual(activity["message"], "gathered 4 sources")
        self.assertEqual(activity["last_progress_at"], "2026-11-07T12:00:00Z")

    def test_elapsed_is_measured_and_says_what_it_measured(self) -> None:
        job_id = self.new_job()
        self.execute(
            "UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2026-11-07T10:00:00Z", "2026-11-07T10:00:00Z", job_id),
        )
        running_activity = self.activity(job_id)
        self.assertEqual(running_activity["elapsed_basis"], "created_to_now")
        self.assertGreaterEqual(running_activity["elapsed_seconds"], 0)

        self.execute(
            "UPDATE jobs SET state = 'failed', error_json = '{}', updated_at = ? WHERE id = ?",
            ("2026-11-07T10:02:05Z", job_id),
        )
        rested = self.activity(job_id)
        self.assertEqual(rested["elapsed_basis"], "created_to_updated")
        self.assertEqual(rested["elapsed_seconds"], 125, "a resting job stops the clock at updated_at")


class TerminalStateTest(ProgressCase):
    def test_a_finished_job_reports_terminal_and_its_real_usage(self) -> None:
        job_id = self.new_job(brief={"stage": "lessons"})
        stage = CountingStage("lessons", artifact=2)
        view = job_service.execute(job_id, [job_service.Stage("lessons", stage)])
        self.assertEqual(view["state"], "completed")

        job = self.job(job_id)
        activity = job["activity"]
        self.assertTrue(activity["terminal"])
        self.assertFalse(activity["can_cancel"])
        self.assertFalse(activity["can_retry"])
        self.assertEqual(activity["elapsed_basis"], "created_to_updated")
        self.assertEqual(activity["stage"], "lessons")
        self.assertEqual(activity["usage"]["calls"], 1)
        self.assertEqual(activity["usage"]["providers"], ["fake"])
        self.assertEqual(activity["usage"]["models"], ["fake-1"])
        self.assertEqual(activity["usage"]["artifacts"], 2)
        self.assertIsNone(activity["usage"]["cost_usd"])
        self.assertEqual(activity["usage"]["unknown_cost_calls"], 1)
        self.assert_contract_legal(job)

    def test_a_provider_failure_is_retryable_and_names_its_class(self) -> None:
        job_id = self.new_job(brief={"stage": "lessons"})

        def provider_raised(lease):
            raise gen.ProviderFailure("provider exploded", purpose="coursebook.lesson.generate")

        view = job_service.execute(job_id, [job_service.Stage("lessons", provider_raised)])
        self.assertEqual(view["state"], "failed")

        job = self.job(job_id)
        self.assertEqual(job["error"]["code"], "HOST_UNAVAILABLE")
        activity = job["activity"]
        self.assertEqual(activity["stage"], "lessons")
        self.assertFalse(activity["terminal"], "failed rests but is retryable, not terminal")
        self.assertTrue(activity["can_retry"])
        self.assertFalse(activity["can_cancel"])
        self.assertEqual(activity["elapsed_basis"], "created_to_updated")
        self.assertEqual(activity["usage"]["calls"], 0, "a failed call records no usage it cannot prove")

    def test_an_interrupted_job_offers_retry_and_cancel(self) -> None:
        job_id = self.new_job(brief={"stage": "plan"})
        job_service.claim(job_id, owner="dead-worker", now=T0)
        job_service.reconcile_startup(now=T0 + timedelta(hours=1))
        activity = self.activity(job_id)
        self.assertTrue(activity["can_retry"])
        self.assertTrue(activity["can_cancel"], "jobs.cancel accepts interrupted_requires_retry -> cancelled")
        self.assertFalse(activity["terminal"])

    def test_a_cancelled_job_is_terminal_and_offers_nothing(self) -> None:
        job_id = self.new_job()
        self.ok("jobs.cancel", {"job_id": job_id})
        activity = self.activity(job_id)
        self.assertTrue(activity["terminal"])
        self.assertFalse(activity["can_cancel"])
        self.assertFalse(activity["can_retry"])
        self.assertEqual(activity["elapsed_basis"], "created_to_updated")


class CancellationIdempotenceTest(ProgressCase):
    def test_repeated_cancel_intent_moves_the_state_once_and_mints_nothing(self) -> None:
        job_id = self.new_job()
        job_service.claim(job_id, owner="worker-a", now=T0)
        first = job_service.request_cancel(job_id, now=T0)
        second = job_service.request_cancel(job_id, now=T0)
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "cancel_requested")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)

        activity = self.activity(job_id)
        self.assertFalse(activity["can_cancel"], "a second cancel control would do nothing")
        self.assertFalse(activity["terminal"])

    def test_cancel_after_completion_is_refused_and_does_not_duplicate(self) -> None:
        job_id = self.new_job()
        job_service.execute(job_id, [job_service.Stage("one", CountingStage("one"))])
        error = self.err("jobs.cancel", {"job_id": job_id})
        self.assertEqual(error["code"], "JOB_NOT_CANCELLABLE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)


class UsageReadTest(ProgressCase):
    def test_usage_is_sourced_from_the_rows_recorded_for_this_job(self) -> None:
        job_id = self.new_job()
        other_job = self.new_job()
        for identifier, job, provider, model, tokens, artifacts in (
            ("use_1", job_id, "nous", "deepseek", {"input_tokens": 100, "output_tokens": 20, "cost_usd": 0.02}, 1),
            ("use_2", job_id, "nous", "deepseek", {"input": 50, "output": 10}, 0),
            ("use_3", job_id, "media", None, {}, 2),
            ("use_4", other_job, "nous", "deepseek", {"input_tokens": 999, "cost_usd": 9.0}, 5),
        ):
            self.execute(
                "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model,"
                " tokens_json, duration_ms, artifact_count, recorded_at) VALUES (?,?,NULL,?,?,?,?,?,?)",
                (identifier, job, provider, model, json.dumps(tokens), 5, artifacts, "2026-11-07T12:00:00Z"),
            )
        usage = self.activity(job_id)["usage"]
        self.assertEqual(usage["calls"], 3, "another job's rows never leak into this job's meter")
        self.assertEqual(usage["tokens"], {"input": 150, "output": 30, "cache_read": None, "cache_write": None})
        self.assertAlmostEqual(usage["cost_usd"], 0.02)
        self.assertEqual(usage["unknown_cost_calls"], 2)
        self.assertEqual(usage["artifacts"], 3)
        self.assertEqual(usage["providers"], ["media", "nous"])
        self.assertEqual(usage["models"], ["deepseek"])

    def test_a_job_with_no_recorded_call_reports_nulls_not_zero(self) -> None:
        usage = self.activity(self.new_job())["usage"]
        self.assertEqual(usage["calls"], 0)
        self.assertEqual(usage["tokens"], {"input": None, "output": None, "cache_read": None, "cache_write": None})
        self.assertIsNone(usage["cost_usd"])
        self.assertEqual(usage["unknown_cost_calls"], 0)
        self.assertEqual(usage["artifacts"], 0)


class NamedReadFailureTest(ProgressCase):
    def test_an_unreadable_progress_column_is_a_named_error_not_zero_progress(self) -> None:
        job_id = self.new_job()
        self.execute("UPDATE jobs SET progress_json = 'not-json' WHERE id = ?", (job_id,))
        error = self.err("jobs.get", {"job_id": job_id})
        self.assertEqual(error["code"], "INTERNAL_ERROR")
        self.assertTrue(error["retryable"])
        self.assertEqual(error["details"]["reason"], "job_progress_unreadable")
        self.assertEqual(error["details"]["column"], "progress_json")
        self.assertNotIn("result", self.dispatch("jobs.get", {"job_id": job_id}))

    def test_an_unreadable_brief_is_also_named(self) -> None:
        job_id = self.new_job()
        self.execute("UPDATE jobs SET brief_json = '[1,2]' WHERE id = ?", (job_id,))
        error = self.err("jobs.get", {"job_id": job_id})
        self.assertEqual(error["details"]["reason"], "job_progress_unreadable")
        self.assertEqual(error["details"]["column"], "brief_json")

    def test_a_list_keeps_its_shape_and_marks_the_unreadable_row(self) -> None:
        healthy = self.new_job(brief={"stage": "plan"})
        broken = self.new_job(brief={"stage": "plan"})
        self.execute("UPDATE jobs SET progress_json = 'not-json' WHERE id = ?", (broken,))
        listed = self.ok("jobs.list", {})["result"]["jobs"]
        by_id = {item["job_id"]: item for item in listed}
        self.assertTrue(by_id[healthy]["activity"]["readable"])
        broken_activity = by_id[broken]["activity"]
        self.assertFalse(broken_activity["readable"])
        self.assertIsNone(broken_activity["stage"])
        self.assertIsNone(broken_activity["steps_done"], "unreadable is null, not a zero that reads as 'not started'")
        self.assertIsNone(broken_activity["steps_total"])

    def test_an_unknown_job_is_not_found_not_a_blank_progress(self) -> None:
        error = self.err("jobs.get", {"job_id": "job_missing"})
        self.assertEqual(error["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
