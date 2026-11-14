"""UP-41 — a job's attempt budget is a function of its stage chain's declared bounds.

At HEAD one constant bounded the whole chain: ``JOB_DEADLINE_SECONDS = 1800`` against a plan
stage whose own declared bounds legally allow two attempts of ``900 s generate + 600 s validate``
(3000 s). A slow-but-legal run therefore died ``HOST_UNAVAILABLE`` on its second attempt, and a
retry re-researched and died in the same place. The Desktop's two-stage lessons job was worse:
one unit's sections plus every section of its authoring in a single 1800 s budget.

The fix is structural, not a bigger constant: each stage declares its own attempt budget from the
purposes it calls and the attempts it may legally spend, the whole chain keeps an outer cap (the
chain's declared worst path, never below the deployment default, and an explicit operator override
still binding exactly), and the per-stage budget is recorded on the checkpoint so a resumed
attempt re-derives it instead of inheriting a spent one. The per-call purpose deadlines — the real
backstop against a stuck provider — are untouched.

This test shrinks the deployment default and the purpose deadlines so the fixtures' sleeps span
more than one attempt: both the refused-then-repaired plan job and the two-stage lessons job must
finish under the derived budgets, and at HEAD both die with ``job_deadline``.
"""

from __future__ import annotations

import contextlib
import os
import time
import unittest
from unittest import mock

from coursebook import deadline as deadline_mod
from coursebook import executor, generation as gen, job_service

from tests.blueprint_support import (
    NOW,
    blueprint_plan,
    narrowed_validation_answer,
    response,
    unit_sections_document,
    validation_answer,
    validation_pass,
)
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    lesson_from_request,
    validation_from_fixture,
)

#: The deployment default the test shrinks to: shorter than the fixture's two plan attempts and
#: shorter than the two-stage lessons chain, so at HEAD the job is cut mid-chain.
SHRUNK_DEFAULT_S = 0.4

#: The declared per-call bounds the test shrinks to (from 900/600/1200/240). Small enough that the
#: derived stage budgets are a few seconds, large enough that no fixture sleep approaches them.
SHRUNK_CALL_S = 5.0

#: One fixture call's sleep. Two plan attempts are four calls (> 1 s) and the lessons chain is
#: longer still, so each attempt's wall time crosses the shrunk default on its own: at HEAD the
#: second attempt starts with the budget already spent and is refused.
CALL_SLEEP_S = 0.25


def _slow(responder):
    """Wrap a fixture responder with a small real sleep (a provider that is slow, not stuck)."""

    def answer(request):
        time.sleep(CALL_SLEEP_S)
        return responder(request)

    return answer


class _FixtureRequest:
    """The subset of ``LLMRequest`` a fixture responder reads, rebuilt from the host's kwargs."""

    def __init__(self, **kwargs) -> None:
        self.purpose = str(kwargs.get("purpose") or "")
        self.schema = kwargs.get("json_schema") or {}
        self.schema_name = str(kwargs.get("schema_name") or "")
        self.instructions = str(kwargs.get("instructions") or "")
        self.system_prompt = str(kwargs.get("system_prompt") or "")
        self.input_text = "".join(
            str(part.get("text") or "")
            for part in (kwargs.get("input") or [])
            if isinstance(part, dict)
        )
        self.max_tokens = int(kwargs.get("max_tokens") or 0)
        self.timeout_s = float(kwargs.get("timeout") or 0.0)
        self.prompt_version = "fixture"


class SlowHostSeam:
    """The production host shape: a synchronous ``complete_structured`` the adapter bounds.

    The adapter runs a synchronous host call through ``deadline.BoundedCallPool``, which clamps
    every call to what is left of its budget and refuses one outright when it is spent. A raw
    fake callable bypasses that seam and would make this test green for the wrong reason.
    """

    def __init__(self, llm) -> None:
        self._llm = llm

    def complete_structured(self, **kwargs):  # noqa: ANN003 - host signature
        return self._llm(_FixtureRequest(**kwargs))


def _enum(request, key: str) -> list[str]:
    properties = (request.schema or {}).get("properties", {})
    return (
        (((properties.get(key) or {}).get("items") or {}).get("properties") or {})
        .get("id", {})
        .get("enum")
        or []
    )


def _claim_enum(request) -> list[str]:
    properties = (request.schema or {}).get("properties", {})
    return (
        (((properties.get("claim_verdicts") or {}).get("items") or {}).get("properties") or {})
        .get("item", {})
        .get("enum")
        or []
    )


class JobDeadlineChainTest(UnitStageCase):
    """The chain's own declared path, not one constant, bounds each stage's attempt."""

    def _env(self) -> dict[str, str]:
        return {
            "COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
            "COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
            "COURSEBOOK_UNIT_SECTIONS_GENERATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
            "COURSEBOOK_UNIT_SECTIONS_VALIDATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
            "COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
            "COURSEBOOK_LESSON_VALIDATE_TIMEOUT_SECONDS": str(SHRUNK_CALL_S),
        }

    def _shrunk_deployment(self):
        """No operator override: the *default* cap is shrunk, and the purpose bounds with it."""
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.dict(os.environ, self._env(), clear=False))
        os.environ.pop(job_service.JOB_DEADLINE_ENV, None)
        stack.enter_context(
            mock.patch.object(job_service, "JOB_DEADLINE_SECONDS", SHRUNK_DEFAULT_S)
        )
        stack.enter_context(
            mock.patch.object(deadline_mod, "JOB_DEADLINE_SECONDS", SHRUNK_DEFAULT_S)
        )
        return stack

    # ── part 1: attempt 1 refused, attempt 2 must still run ─────────────────
    def _refusing_then_passing_validator(self) -> FakeLLM:
        """A validator that refuses the first criteria-bearing pass, then passes every later one."""
        state = {"refused": False}

        def validate(request):
            time.sleep(CALL_SLEEP_S)
            criteria = _enum(request, "criteria")
            claims = _claim_enum(request)
            if criteria and not state["refused"]:
                state["refused"] = True
                reason = "the cited source does not state the objective's evidence"
                document = {
                    "verdict": "reject",
                    "criteria": [
                        {
                            "id": criterion,
                            "verdict": "fail" if criterion == criteria[0] else "pass",
                            "reason": reason
                            if criterion == criteria[0]
                            else "nothing in the artifact contradicts this criterion",
                        }
                        for criterion in criteria
                    ],
                    "rejections": (
                        [
                            {"item": claims[0], "criterion": criteria[0], "reason": reason}
                        ]
                        if claims
                        else []
                    ),
                }
                return response(narrowed_validation_answer(request, document))
            return response(validation_answer(request))

        def author(request):
            time.sleep(CALL_SLEEP_S)
            return response(blueprint_plan(scope="single", recipe="committed"))

        return FakeLLM(
            {
                "coursebook.plan.generate": author,
                "coursebook.plan.validate": validate,
            }
        )

    def _run_plan_job(self) -> tuple[dict, FakeLLM]:
        brief = {
            "stage": "plan",
            "goal": "Order coffee in Japanese",
            "recipe": "committed",
            "dials": {},
            "locale": "ja-JP",
            "level": "L0",
            # A scoped brief selects the v2 plan schema; the fixture plan is a v2 blueprint.
            "scope": "single",
        }
        job_id = job_service.create("plan", brief, now=NOW)["job_id"]
        fake = self._refusing_then_passing_validator()
        llm = gen.PluginLLMAdapter(SlowHostSeam(fake))
        stages = executor.resolvers(llm=llm, search=FakeSearch(), now=NOW)[
            executor.JOB_KIND
        ](brief)
        view = job_service.execute(job_id, stages, now=NOW)
        return view, fake

    # ── part 2: the Desktop's two-stage lessons chain ───────────────────────
    def _two_stage_lessons(self, plan: dict, plan_id: str) -> tuple[dict, str]:
        unit = next(item for item in plan["units"] if int(item["ordinal"]) == 1)
        objectives = [
            item for item in plan["objectives"] if int(item["unit_ref"]) == 1
        ]
        reviews = max(0, int(unit["target_lessons"]) - len(objectives))
        sections = unit_sections_document(
            unit=unit, objectives=objectives, reviews=reviews
        )
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": _slow(
                    lambda _request: response(sections)
                ),
                "coursebook.unit_sections.validate": _slow(
                    lambda _request: response(validation_pass())
                ),
                "coursebook.lesson.generate": _slow(lesson_from_request()),
                "coursebook.lesson.validate": _slow(validation_from_fixture()),
            }
        )
        # The Desktop payload: no unit_ordinal, so the executor resolves the unit and chains the
        # two stages into one job.
        brief = {"stage": "lessons", "plan_id": plan_id, "enrollment_id": "enr_test"}
        job_id = job_service.create("plan", brief, now=NOW)["job_id"]
        stages = executor.resolvers(
            llm=gen.PluginLLMAdapter(SlowHostSeam(llm)), search=FakeSearch(), now=NOW
        )[executor.JOB_KIND](brief)
        view = job_service.execute(job_id, stages, now=NOW)
        return view, job_id

    # ── the acceptance case ─────────────────────────────────────────────────
    def test_second_plan_attempt_and_lessons_stage_complete(self) -> None:
        self._shrunk_deployment()

        # Part 1: attempt 1 is refused by a grounded validator rejection; attempt 2 must author
        # and validate inside the plan stage's *own* derived budget (2 x (5 + 5) = 20 s) even
        # though the deployment default is 0.4 s.
        plan_view, plan_llm = self._run_plan_job()
        self.assertIsNone(plan_view.get("error"), plan_view.get("error"))
        self.assertEqual(plan_view["state"], "completed", plan_view)
        self.assertEqual(
            plan_llm.calls_for("coursebook.plan.generate"),
            2,
            "attempt 2 never ran: the job was cut between the refused attempt and its repair",
        )
        self.assertGreaterEqual(plan_llm.calls_for("coursebook.plan.validate"), 2)
        self.assertFalse(
            (plan_view.get("error") or {}).get("details", {}).get("job_deadline"),
            "the plan job ended on its own deadline",
        )
        declared_plan = gen.plan_stage_budget_seconds()
        self.assertAlmostEqual(
            float(plan_view["checkpoint"]["stage_budgets"]["plan"]), declared_plan, places=3
        )
        self.assertGreater(
            declared_plan,
            SHRUNK_DEFAULT_S,
            "the derived plan budget is not larger than the deployment default it replaces",
        )
        # The derivation is live: shrinking the purpose bounds shrinks the stage budget, which is
        # what lets a resumed attempt re-derive rather than inherit a spent instant.
        with mock.patch.dict(os.environ, {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": "2.0"}):
            self.assertLess(gen.plan_stage_budget_seconds(), declared_plan)

        # Part 2: the Desktop lessons brief chains unit_sections -> lessons. The unit-sections
        # stage's own budget (2 x (5 + 5) = 20 s) must not be spent by the deployment default, and
        # the lessons stage must be reached instead of the job failing with job_deadline.
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=2, reviews=[0])
        _course_id, plan_id = self.seed(plan)
        lessons_view, _job_id = self._two_stage_lessons(plan, plan_id)
        self.assertIsNone(lessons_view.get("error"), lessons_view.get("error"))
        self.assertEqual(lessons_view["state"], "completed", lessons_view)
        # Both stages ran: the progress record ends on the lessons stage at its last step, and
        # both stages' budgets are on the checkpoint.
        self.assertEqual(lessons_view["progress"]["stage"], executor.LESSONS_STAGE)
        self.assertEqual(lessons_view["progress"]["steps_done"], 2)
        self.assertFalse(
            (lessons_view.get("error") or {}).get("details", {}).get("job_deadline"),
            "the two-stage lessons job ended on a spent deadline",
        )
        budgets = lessons_view["checkpoint"]["stage_budgets"]
        self.assertGreater(budgets[executor.UNIT_SECTIONS_STAGE], SHRUNK_DEFAULT_S)
        self.assertGreater(budgets[executor.LESSONS_STAGE], budgets[executor.UNIT_SECTIONS_STAGE])

    # ── the persisted budget is re-derived on a resumed attempt ────────────
    def test_a_resumed_attempt_rederives_its_stage_budget(self) -> None:
        """A failed attempt records its budget; the resumed attempt gets a freshly derived one."""
        self._shrunk_deployment()
        sound = {"seconds": 1.0}

        def failing(_lease):
            raise gen.ProviderFailure("the provider is unavailable")

        def passing(_lease):
            return job_service.StageResult(message="done")

        job_id = job_service.create("plan", {"stage": "plan"}, now=NOW)["job_id"]
        first = job_service.execute(
            job_id,
            [job_service.Stage("plan", failing, budget_seconds=lambda: sound["seconds"])],
            now=NOW,
        )
        self.assertEqual(first["state"], "failed", first)
        self.assertAlmostEqual(
            float(first["checkpoint"]["stage_budgets"]["plan"]), 1.0, places=3
        )

        job_service.resume(job_id, now=NOW)
        sound["seconds"] = 3.0
        second = job_service.execute(
            job_id,
            [job_service.Stage("plan", passing, budget_seconds=lambda: sound["seconds"])],
            now=NOW,
        )
        self.assertEqual(second["state"], "completed", second)
        self.assertAlmostEqual(
            float(second["checkpoint"]["stage_budgets"]["plan"]),
            3.0,
            places=3,
            msg="the resumed attempt inherited the spent attempt's budget instead of re-deriving",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
