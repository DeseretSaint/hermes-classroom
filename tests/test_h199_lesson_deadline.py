"""H-199 regressions: ``lesson.generate``'s deadline is enforced on the call path.

The live defect (master ``127cce1``, real host seams): a lessons job against a 420 s deadline
failed at 888.4 s, and against a configured 600 s deadline it sat 16+ minutes with zero usage
rows and the deadline never fired. The deadline was a *post-hoc* elapsed-time verdict, not a
cancellation: the host's async sibling can block its own loop thread (then ``asyncio.wait_for``'s
timer never runs) or await ``asyncio.to_thread`` (then ``asyncio.run`` blocks in executor
shutdown *after* the timeout fired). Neither shape can be bounded from inside the coroutine.

Every case here is deterministic and offline: the "host" is a stub seam with the live host's
shape (``acomplete_structured``), and the only slowness is a deliberate sleep. Nothing asserts
provider output, token counts or spend.
"""

from __future__ import annotations

import asyncio
import os
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from coursebook import db, deadline as deadline_mod, executor, generation as gen, job_service

from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)

#: How long the stub seam blocks. Deliberately far past every deadline the tests declare, so a
#: case that returns faster than this can only have been cut off by the deadline itself.
BLOCK_SECONDS = 6.0


def _request_from_call(kwargs: dict) -> gen.LLMRequest:
    """Rebuild the ``LLMRequest`` the adapter sent, from the host-call kwargs it forwards."""
    input_text = ""
    for block in kwargs.get("input") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            input_text += block.get("text") or ""
    return gen.LLMRequest(
        purpose=str(kwargs.get("purpose") or ""),
        prompt_version="h199",
        system_prompt=str(kwargs.get("system_prompt") or ""),
        instructions=str(kwargs.get("instructions") or ""),
        input_text=input_text,
        schema=kwargs.get("json_schema") or {},
        schema_name=str(kwargs.get("schema_name") or ""),
        max_tokens=int(kwargs.get("max_tokens") or 4000),
        timeout_s=float(kwargs.get("timeout") or 300.0),
    )


def _host_result(response: gen.LLMResponse) -> SimpleNamespace:
    """The shape the host returns: same text/parsed/identity, plus a usage block."""
    return SimpleNamespace(
        text=response.text,
        parsed=response.parsed,
        provider=response.provider,
        model=response.model,
        usage=SimpleNamespace(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        ),
    )


class HostSeam:
    """The live host's shape: an async sibling that can block its own event loop.

    ``acomplete_structured`` sleeps with ``time.sleep`` — a synchronous provider client on the
    loop thread, which is exactly the live shape that made ``asyncio.wait_for`` unable to fire.
    The sync method is present on the real host too, and here it asserts: the async sibling must
    be the one used whenever the host exposes it.
    """

    def __init__(
        self,
        inner: FakeLLM,
        *,
        block_when=None,
        block_seconds: float = BLOCK_SECONDS,
    ) -> None:
        self.inner = inner
        self.block_when = block_when
        self.block_seconds = float(block_seconds)
        self.calls = 0
        self.blocked = 0

    async def acomplete_structured(self, **kwargs):  # noqa: ANN003 - host signature
        self.calls += 1
        if self.block_when is not None and self.block_when(self.calls):
            self.blocked += 1
            time.sleep(self.block_seconds)
        return _host_result(self.inner(_request_from_call(kwargs)))

    def complete_structured(self, **kwargs):  # noqa: ANN003 - must not be chosen
        raise AssertionError("the async sibling must be used when the host exposes it")

    def calls_for(self, purpose: str) -> int:
        return self.inner.calls_for(purpose)


def adapter(seam: HostSeam) -> gen.PluginLLMAdapter:
    """The production route: the host seam wrapped in the adapter the job runner calls."""
    return gen.PluginLLMAdapter(seam)


# ── the deadline is enforced on the call, not re-checked after it ───────────


class LessonDeadlineTest(GenerationTestBase):
    def lesson_script(self, validate, generate=None) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate or lesson_from_request(),
                "coursebook.lesson.validate": validate,
            }
        )

    def run_lessons(self, plan_result: dict, llm, job_id: str = "job-h199-1") -> dict:
        return gen.run_lesson_job(
            self.connection,
            {"job_id": job_id, "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=32),
        )

    def test_a_blocking_host_seam_is_cut_off_at_the_declared_deadline(self) -> None:
        plan_result = self.approved_plan()
        seam = HostSeam(self.lesson_script(validation_from_fixture()), block_when=lambda call: True)
        with mock.patch.dict(
            os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "0.4"}
        ):
            started = time.monotonic()
            try:
                with self.assertRaises(gen.ProviderTimeout) as caught:
                    self.run_lessons(plan_result, adapter(seam))
            finally:
                elapsed = time.monotonic() - started
        # The stub blocks for BLOCK_SECONDS; anything under it is the deadline stopping the call.
        self.assertLess(elapsed, 3.0, f"deadline did not bound the call: waited {elapsed:.1f}s")
        self.assertGreaterEqual(seam.blocked, 1)
        self.assertEqual(caught.exception.purpose, "coursebook.lesson.generate")
        self.assertEqual(caught.exception.deadline_s, 0.4)
        self.assertIn("0 of 4 sections are saved", str(caught.exception))

    def test_a_heartbeat_row_exists_while_the_call_is_still_in_flight(self) -> None:
        plan_result = self.approved_plan()
        seam = HostSeam(self.lesson_script(validation_from_fixture()), block_when=lambda call: True)
        with mock.patch.dict(
            os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "1.2"}
        ), mock.patch.object(deadline_mod, "WAIT_HEARTBEAT_SECONDS", 0.2):
            with self.assertRaises(gen.ProviderTimeout):
                self.run_lessons(plan_result, adapter(seam), job_id="job-h199-beat")
        rows = gen.call_waits(self.connection, "job-h199-beat")
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        # The call never returned (the stub is still sleeping), so every beat on this row was
        # emitted *during* the wait — that is the liveness that was missing live.
        self.assertEqual(row["purpose"], "coursebook.lesson.generate")
        self.assertEqual(row["state"], "timeout")
        self.assertGreaterEqual(row["beats"], 3, row)
        self.assertGreaterEqual(row["elapsed_ms"], 800, row)
        self.assertEqual(row["job_id"], "job-h199-beat")

    def test_a_returned_call_closes_its_wait_row(self) -> None:
        plan_result = self.approved_plan()
        seam = HostSeam(self.lesson_script(validation_from_fixture()))
        with mock.patch.object(deadline_mod, "WAIT_HEARTBEAT_SECONDS", 0.2):
            result = self.run_lessons(plan_result, adapter(seam), job_id="job-h199-return")
        self.assertEqual(len(result["lessons"]), 4)
        rows = gen.call_waits(self.connection, "job-h199-return")
        self.assertTrue(rows)
        self.assertTrue(all(row["state"] == "returned" for row in rows), rows)

    def test_already_saved_sections_survive_and_the_retry_does_not_re_author_them(self) -> None:
        plan_result = self.approved_plan()
        author = lesson_from_request()
        # Call 1/2 author and validate section 1; call 3 (section 2's generate) blocks.
        first = HostSeam(
            self.lesson_script(validation_from_fixture(), generate=author),
            block_when=lambda call: call == 3,
        )
        with mock.patch.dict(
            os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "0.4"}
        ):
            started = time.monotonic()
            with self.assertRaises(gen.ProviderTimeout) as caught:
                self.run_lessons(plan_result, adapter(first), job_id="job-h199-partial")
            elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0, f"deadline did not bound the call: waited {elapsed:.1f}s")
        self.assertIn("1 of 4 sections are saved", str(caught.exception))
        self.assertEqual(self.count("gen_lessons"), 1)
        # Three call rows: section 1's generate and validation returned, section 2's generate was
        # cut off at its deadline.
        rows = gen.call_waits(self.connection, "job-h199-partial")
        self.assertEqual(len(rows), 3, rows)
        self.assertEqual(sorted(row["state"] for row in rows), ["returned", "returned", "timeout"])
        saved = {row["section_id"]: row["id"] for row in self.rows("SELECT id, section_id FROM gen_lessons")}

        # Retry: only the three missing sections are authored; the saved one is reused as-is.
        retry = self.lesson_script(validation_from_fixture())
        second = self.run_lessons(plan_result, retry, job_id="job-h199-retry")
        self.assertEqual(len(second["lessons"]), 4)
        self.assertEqual(retry.calls_for("coursebook.lesson.generate"), 3)
        after = {row["section_id"]: row["id"] for row in self.rows("SELECT id, section_id FROM gen_lessons")}
        self.assertEqual(len(after), 4)
        for section_id, lesson_id in saved.items():
            self.assertEqual(after[section_id], lesson_id, "a saved section was re-authored")


# ── the job row: HOST_UNAVAILABLE, the partial-sections message, bounded time ──


class LessonDeadlineJobTest(KernelCase):
    """The Desktop's lessons brief through the real executor, job service and database."""

    def _approved_plan(self) -> dict:
        connection = db.connect()
        try:
            result = gen.run_plan_job(
                connection,
                plan_job(),
                FakeLLM(
                    {
                        "coursebook.plan.generate": plan_from_fixture(),
                        "coursebook.plan.validate": validation_from_fixture(),
                    }
                ),
                FakeSearch(),
                now=NOW,
            )
            connection.execute(
                "UPDATE plans SET state = 'approved', approved_at = ? WHERE id = ?",
                ("2026-11-06T12:05:00Z", result["plan_id"]),
            )
        finally:
            connection.close()
        return result

    def test_the_lesson_job_fails_host_unavailable_in_bounded_wall_time(self) -> None:
        plan = self._approved_plan()
        brief = {"stage": "lessons", "plan_id": plan["plan_id"]}
        job_id = job_service.create("plan", brief, now=NOW)["job_id"]
        seam = HostSeam(
            FakeLLM(
                {
                    "coursebook.lesson.generate": lesson_from_request(),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            ),
            block_when=lambda call: call == 1,
        )
        stages = executor.resolvers(llm=adapter(seam), search=FakeSearch(), now=NOW)[executor.JOB_KIND](brief)
        started = time.monotonic()
        with mock.patch.dict(os.environ, {"COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": "0.5"}):
            view = job_service.execute(job_id, stages, now=NOW)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0, f"the job was not bounded: {elapsed:.1f}s")
        self.assertEqual(seam.blocked, 1)
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"]["code"], "HOST_UNAVAILABLE")
        self.assertEqual(view["error"]["category"], "capability")
        self.assertTrue(view["error"]["retryable"])
        self.assertIn("sections are saved", view["error"]["message"])
        self.assertEqual(view["error"]["details"]["purpose"], "coursebook.lesson.generate")
        with db.read() as connection:
            waits = gen.call_waits(connection, job_id)
        self.assertEqual(len(waits), 1, waits)
        self.assertEqual(waits[0]["state"], "timeout")


class DeadlineModuleTest(unittest.TestCase):
    """The bounded wait itself, independent of the pipeline."""

    def test_a_coroutine_that_blocks_its_loop_is_cut_off_on_the_callers_clock(self) -> None:
        async def blocked():
            time.sleep(BLOCK_SECONDS)

        started = time.monotonic()
        with self.assertRaises(deadline_mod.DeadlineExceeded) as caught:
            deadline_mod.run_async_bounded(blocked, timeout_s=0.2, label="stub")
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertEqual(caught.exception.deadline_s, 0.2)

    def test_a_coroutine_awaiting_a_thread_is_cut_off_on_the_callers_clock(self) -> None:
        async def blocked():
            await asyncio.to_thread(time.sleep, BLOCK_SECONDS)

        started = time.monotonic()
        with self.assertRaises(deadline_mod.DeadlineExceeded):
            deadline_mod.run_async_bounded(blocked, timeout_s=0.2, label="stub")
        self.assertLess(time.monotonic() - started, 2.0)

    def test_the_wait_heartbeats_while_it_waits(self) -> None:
        async def blocked():
            time.sleep(0.6)

        beats: list[float] = []
        with self.assertRaises(deadline_mod.DeadlineExceeded):
            deadline_mod.run_async_bounded(
                blocked, timeout_s=0.5, label="stub", on_wait=beats.append, heartbeat_s=0.1
            )
        self.assertGreaterEqual(len(beats), 3, beats)
        self.assertEqual(beats, sorted(beats))

    def test_a_wait_heartbeat_that_raises_never_decides_the_call(self) -> None:
        async def quick():
            await asyncio.sleep(0.05)
            return "ok"

        def broken(_elapsed: float) -> None:
            raise RuntimeError("the liveness writer is down")

        self.assertEqual(
            deadline_mod.run_async_bounded(quick, timeout_s=2.0, label="stub", on_wait=broken),
            "ok",
        )
