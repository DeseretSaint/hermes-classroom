"""H-182/D10 — the plan-stage single-call deadline is measured, and a miss is actionable.

The retired H-182/D1-D3 run could not finish a plan: ``coursebook.plan.generate`` exceeded its
declared 240 s deadline, then an operator-raised 480 s deadline, while the provider call was still
outstanding (``audit/visual/h182-repair/EVIDENCE.md``). The same stage had taken 222 s on the same
provider the same day, so the declared bound sat *below* observed behaviour and every plan near the
tail failed as a transport error instead of a quality signal.

These tests are the regression for the decision, not for the constant's existence:

* the resolved default must admit every plan generation actually measured on the author route,
  and must sit above the largest call that was cut off and never answered — the old 240 s value
  fails this;
* a miss must reach the parent as one honest state: purpose, declared bound, the *elapsed* wait,
  and the next action. No silent retry loop.

The measurement table is copied from the packets named beside each entry; nothing here invents a
provider latency. The fakes only provide structure — no test asserts real provider output.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import unittest
from unittest import mock

from coursebook import generation as gen
from coursebook import job_service
from tests.test_generation import NOW, FakeSearch, plan_job

#: Every *successful* ``coursebook.plan.generate`` call recorded on the author route
#: (Nous ``deepseek/deepseek-v4.1-flash-1017``), with the packet it came from.
#:
#: H-187 packet          — audit/adversarial/live-generation-2026-11-08/evidence/*.json
#: H-192 / H-192b / c    — audit/adversarial/live-generation-2026-11-08-h192/evidence/*.json
#: H-182 cold walk       — audit/visual/h182-repair/EVIDENCE.md ("the parent cold walk saw the
#:                         same stage take 222 s")
MEASURED_PLAN_GENERATE_SECONDS: tuple[tuple[str, float], ...] = (
    ("h192c/single attempt 1", 23.914),
    ("h192b/single", 32.387),
    ("h192/single rerun 2", 40.454),
    ("h192c/single attempt 2", 45.174),
    ("h187/single", 53.212),
    ("h192b/full", 83.045),
    ("h187/full", 106.590),
    ("h192/full", 131.245),
    ("h182/parent cold walk", 222.000),
    ("h192/single rerun 1", 324.965),
    ("h187/short", 339.802),
    ("h192b/short", 348.200),
)

#: Calls that were cut at their declared bound and never answered, so the true duration is at
#: least the bound. The largest one (H-192 full-scope retry at 600 s) is the floor the new default
#: must clear, or it would keep reproducing the reported failure.
CENSORED_FLOOR_SECONDS = 600.0

MEASURED_P95_SECONDS = 348.2  # nearest rank, n=12


class MeasuredPlanDeadlineTest(unittest.TestCase):
    """The declared default is above measured behaviour (fails on the old 240 s value)."""

    def test_the_declared_bound_admits_every_measured_plan_generation(self) -> None:
        declared = gen.provider_timeout_s("coursebook.plan.generate")
        for label, seconds in MEASURED_PLAN_GENERATE_SECONDS:
            self.assertLess(
                seconds,
                declared,
                f"{label} took {seconds:g}s; a {declared:g}s declared bound would cut a real "
                "plan generation and report it as a host failure",
            )
        self.assertGreaterEqual(declared, MEASURED_P95_SECONDS)
        self.assertGreater(
            declared,
            CENSORED_FLOOR_SECONDS,
            "the declared bound must sit above the largest measured call that was cut off "
            f"(>={CENSORED_FLOOR_SECONDS:g}s) or it reproduces H-182/D10",
        )

    def test_the_old_240_second_default_would_have_failed_measured_calls(self) -> None:
        # This is the regression itself: with the previous default, at least one *successful*
        # measured plan generation and two censored calls sat beyond the bound.
        over_old = [label for label, seconds in MEASURED_PLAN_GENERATE_SECONDS if seconds > 240.0]
        self.assertIn("h192b/short", over_old)
        self.assertIn("h187/short", over_old)
        self.assertNotEqual(gen.provider_timeout_s("coursebook.plan.generate"), 240.0)

    def test_the_one_definition_point_still_honours_an_operator_override(self) -> None:
        # Raising the default is policy, not a removal of operator control: a deployment may
        # still lower or raise it, and the request builder reads the same resolution.
        with mock.patch.dict(
            os.environ, {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": "240"}
        ):
            self.assertEqual(gen.provider_timeout_s("coursebook.plan.generate"), 240.0)
            self.assertEqual(gen._timeout_for("coursebook.plan.generate", None), 240.0)
        self.assertEqual(
            gen._timeout_for("coursebook.plan.generate", None),
            gen.provider_timeout_s("coursebook.plan.generate"),
        )

    def test_the_purpose_env_name_is_still_the_documented_one(self) -> None:
        self.assertEqual(
            gen.PROVIDER_TIMEOUT_ENV["coursebook.plan.generate"],
            "COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS",
        )


class DeadlineIsActionableTest(unittest.TestCase):
    """A fired bound is one honest state: purpose, elapsed, destination, next action."""

    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def _stalled_plan_job(self) -> gen.ProviderTimeout:
        release = threading.Event()

        class StallingHost:
            def complete_structured(self, **kwargs):  # noqa: ANN003
                release.wait(10.0)
                raise AssertionError("the stalled call must be cut at its deadline first")

        adapter = gen.PluginLLMAdapter(StallingHost())
        try:
            with mock.patch.dict(
                os.environ, {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": "0.25"}
            ):
                with self.assertRaises(gen.ProviderTimeout) as caught:
                    gen.run_plan_job(
                        self.connection, plan_job(), adapter, FakeSearch(), now=NOW
                    )
        finally:
            release.set()
        return caught.exception

    def test_a_fired_bound_names_the_elapsed_wait_and_the_next_action(self) -> None:
        error = self._stalled_plan_job()
        self.assertEqual(error.purpose, "coursebook.plan.generate")
        self.assertEqual(error.deadline_s, 0.25)
        self.assertIsNotNone(error.duration_ms, "the elapsed wait must reach the error record")
        self.assertGreaterEqual(int(error.duration_ms), 200)
        text = str(error)
        self.assertIn("waited", text)
        # Destination: nothing durable was written, and the message says so.
        self.assertIn("no plan was written", text)
        # Next action: a real retry of this stage, or the documented operator knob.
        self.assertIn("run this stage again as a new job", text)
        self.assertIn("COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS", text)
        # H-182/D1: the retry is a real attempt, not a silent replay of a draft.
        self.assertIn("research and authoring run again", text)
        # Honest state: no plan document exists after a bound miss.
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) AS n FROM gen_plan_documents"
                ).fetchone()["n"]
            ),
            0,
        )

    def test_the_job_error_carries_the_bound_and_the_elapsed_wait(self) -> None:
        error = self._stalled_plan_job()
        record = job_service._stage_error(error)
        details = record["details"]
        self.assertEqual(record["code"], "HOST_UNAVAILABLE")
        self.assertEqual(details["purpose"], "coursebook.plan.generate")
        self.assertEqual(details["deadline_s"], 0.25)
        self.assertIsNotNone(details["duration_ms"])
        self.assertGreaterEqual(int(details["duration_ms"]), 200)
        self.assertIn("run this stage again as a new job", record["message"])

    def test_a_successful_call_is_not_declared_late(self) -> None:
        # Guard the other direction: raising the bound must not turn a prompt answer into a
        # failure, and the no-op path must stay a no-op.
        answer = gen.LLMResponse(text="{}", parsed={}, provider="fake", model="fake")
        request = gen.LLMRequest(
            purpose="coursebook.plan.generate",
            prompt_version="test",
            system_prompt="test",
            instructions="test",
            input_text="{}",
            schema={"type": "object"},
            schema_name="test",
            max_tokens=8,
            timeout_s=gen.provider_timeout_s("coursebook.plan.generate"),
        )
        usage = gen._Usage(gen.default_cost_budget())
        self.assertIs(gen._call_llm(lambda _request: answer, request, usage), answer)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
