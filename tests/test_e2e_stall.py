"""A stage that misses its deadline must leave a failed job, never a running one.

Written after a live probe's plan job sat at ``running`` with a stale lease for eighteen minutes
while the worker process had a single idle thread. The cause of that stall was not reproduced, so
this test asserts the contract that must hold regardless of cause: a stage exception (here a
provider call cut at a 0.2 s bound) leaves a terminal job with a readable error, never a job that
never finishes. If a future change lets a pump thread die without failing the row, this fails.
"""

from __future__ import annotations

import os
import threading
import unittest
from unittest import mock

from coursebook import executor, generation as gen

from tests.kernel_support import KernelCase


class PlanDeadlineJobTest(KernelCase):
    def test_a_plan_deadline_fails_the_job_instead_of_leaving_it_running(self) -> None:
        course_id, _plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        created = self.ok(
            "jobs.create",
            {
                "kind": "plan",
                "brief": {
                    "stage": "plan",
                    "course_id": course_id,
                    "enrollment_id": enrollment_id,
                    "goal": "Braise short ribs",
                    "recipe": "committed",
                    "scope": "short",
                    "subject_domain": "cooking",
                },
            },
        )["result"]
        release = threading.Event()

        class StallingHost:
            def complete_structured(self, **kwargs):  # noqa: ANN003 - host signature
                release.wait(10.0)
                raise AssertionError("the stalled call must be cut at its deadline first")

        adapter = gen.PluginLLMAdapter(StallingHost())
        try:
            with mock.patch.dict(
                os.environ, {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": "0.2"}
            ):
                executor.pump_once(limit=1, llm=adapter)
        finally:
            release.set()

        job = self.dispatch("jobs.get", {"job_id": created["job_id"]})["result"]["job"]
        self.assertIn(
            job["state"],
            {"failed", "cancelled"},
            f"a stage exception left the job in {job['state']!r}; the learner sees a job that "
            "never finishes",
        )
        error = job.get("error") or {}
        self.assertTrue(error.get("message"), job)


if __name__ == "__main__":
    unittest.main()
