"""G5: contiguous scope bands, and a band violation that refuses instead of parking a plan.

The defect these cases pin, verified by running the rule gate on synthetic plans:

* ``SCOPE_EXPECTATIONS`` accepted single {1}, short {3-6} and full {12-40} objectives, so 2 and
  7-11 objectives — and 9-11 sections — had no legal scope at all. A 10-objective plan was refused
  at short ("requires 3 to 6") and again at full ("requires 12 to 40") with no suggestion.
* on the second violation the plan job wrote the document parked ``needs_review``, which
  ``plan.approve`` then refused ("no durable validation binding"): a dead artifact instead of a
  typed refusal.

Each case below fails on the pre-G5 code: the band-cover case on the holes, the pipeline case on
the parked document, and the envelope case on the missing ``details.reason``.
"""

from __future__ import annotations

import json
import unittest

from coursebook import contracts, generation as gen, job_service
from tests.blueprint_support import blueprint_plan
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    NOW,
    plan_job,
)


def _plan_rules(plan: dict, *, scope: str) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe="casual",
        dials={},
        locale=None,
        ledger=(),
        scope=scope,
    )


class ContiguousBandTest(unittest.TestCase):
    """Every objective and section count the plan schema allows has a legal scope."""

    def test_every_objective_count_from_one_to_the_schema_ceiling_is_representable(self) -> None:
        ceiling = int(gen.PLAN_SCHEMA_V2["properties"]["objectives"]["maxItems"])
        for objectives in range(1, ceiling + 1):
            with self.subTest(objectives=objectives):
                fits = gen.scope_band_fit(objectives=objectives, units=1)
                if objectives > 1:
                    # A multi-objective course may need more than one unit to fit the per-unit
                    # band, so ask the union over unit counts the schema allows.
                    fits = [
                        scope
                        for scope in gen.SCOPES
                        for units in range(1, 13)
                        if scope
                        in gen.scope_band_fit(objectives=objectives, units=units)
                    ]
                self.assertTrue(
                    fits,
                    f"{objectives} objectives fit no scope band: "
                    f"{gen.scope_bands_text()}",
                )

    def test_the_section_caps_are_contiguous_across_the_scopes(self) -> None:
        caps = {
            scope: gen._section_caps({**gen.SCOPE_EXPECTATIONS[scope], "scope": scope})
            for scope in gen.SCOPES
        }
        self.assertEqual(caps["single"], (1, 1))
        # 9-11 sections were the hole: the old table jumped from a short course of 8 sections to a
        # full course of 12. The short band now reaches 12 and full starts at 9.
        self.assertEqual(caps["short"], (8, 12))
        self.assertEqual(caps["full"], (8, 48))
        # The course-level band is the objective band plus the scope's review allowance: short has
        # up to 2 review sections, full up to 8 (and at most 2 per unit).
        bands = {"single": (1, 1), "short": (2, 12), "full": (9, 48)}
        for scope, (low, high) in bands.items():
            objective_low, objective_high = gen.SCOPE_EXPECTATIONS[scope]["blueprint_objectives"]
            self.assertEqual(low, objective_low)
            self.assertEqual(high, caps[scope][1])
        covered = set()
        for low, high in bands.values():
            covered.update(range(low, high + 1))
        self.assertEqual(
            [value for value in range(1, 49) if value not in covered],
            [],
            "every section count from 1 to 48 must sit inside one scope's band",
        )

    def test_two_objectives_now_have_a_scope(self) -> None:
        # 2 objectives had no legal scope: single is exactly 1 and the old short floor was 3.
        self.assertEqual(gen.scope_band_fit(objectives=2, units=1), ["short"])
        _plan_rules(blueprint_plan(scope="short", units=1, objectives_per_unit=2), scope="short")

    def test_ten_objectives_and_ten_sections_are_accepted_at_short(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=5)
        self.assertEqual(len(plan["objectives"]), 10)
        self.assertEqual(sum(unit["target_lessons"] for unit in plan["units"]), 10)
        _plan_rules(plan, scope="short")
        # The same shape is legal under the full dial too: the bands overlap at 9-10 on purpose.
        full = blueprint_plan(scope="full", units=2, objectives_per_unit=5)
        full["time_estimate"]["weeks"] = 12
        _plan_rules(full, scope="full")

    def test_eleven_sections_are_representable(self) -> None:
        # Ten owner sections plus one review section is an 11-section short course; it used to sit
        # between the short cap of 8 and the full floor of 12.
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=5, reviews=(0, 1))
        self.assertEqual(sum(unit["target_lessons"] for unit in plan["units"]), 11)
        _plan_rules(plan, scope="short")


class BandViolationIsTypedTest(unittest.TestCase):
    """The rule gate marks a band-only violation so the caller can refuse it typed."""

    def test_a_band_only_violation_carries_the_band_context(self) -> None:
        plan = blueprint_plan(scope="full", units=1, objectives_per_unit=1)
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(plan, scope="full")
        self.assertTrue(caught.exception.band_only, caught.exception.reasons)
        band = caught.exception.band or {}
        self.assertEqual(band.get("scope"), "full")
        self.assertEqual(band.get("objectives"), 1)
        self.assertEqual(band.get("units"), 1)

    def test_a_mixed_violation_is_not_marked_band_only(self) -> None:
        # Out of band *and* a duplicate sourced performance: a human review acts on the second
        # reason, so the parked path stays.
        plan = blueprint_plan(scope="full", units=1, objectives_per_unit=1)
        plan["objectives"][0].update(
            {
                "support": "sourced",
                "source_ids": ["src-1"],
                "source_quote": "the excerpt states the capability",
                "evidence_criteria": ["names the phase from the sky alone"],
            }
        )
        plan["objectives"].append(
            {
                **plan["objectives"][0],
                "ordinal": 2,
            }
        )
        plan["check_plan"].append({**plan["check_plan"][0], "objective_ref": 2})
        with self.assertRaises(gen._RuleViolation) as caught:
            _plan_rules(plan, scope="full")
        self.assertFalse(caught.exception.band_only)

    def test_the_refusal_names_the_learner_action_and_the_legal_scope(self) -> None:
        too_large = gen.scope_band_refusal(scope="short", objectives=24, units=4)
        self.assertIn("too large for a short course", str(too_large))
        self.assertIn("full holds 9 to 40 objective(s)", str(too_large))

        too_small = gen.scope_band_refusal(scope="full", objectives=1, units=1)
        self.assertIn("small enough for a short course", str(too_small))
        self.assertIn("short", str(too_small).split("Legal scopes are:")[1])

    def test_the_refusal_is_contract_legal_and_names_the_reason(self) -> None:
        refusal = gen.scope_band_refusal(scope="full", objectives=1, units=1)
        envelope = job_service._stage_error(refusal)
        contracts.validate_definition("cb.errors", "error", envelope)
        self.assertEqual(envelope["code"], "VALIDATION_FAILED")
        self.assertFalse(envelope["retryable"])
        self.assertEqual(envelope["details"]["reason"], "scope_band")
        self.assertEqual(envelope["details"]["scope"], "full")
        self.assertEqual(envelope["details"]["objectives"], 1)
        self.assertEqual(envelope["details"]["legal_scopes"], ["single"])


class BandViolationWritesNoPlanTest(GenerationTestBase):
    """End to end: a 1-objective answer under the full dial refuses and stores nothing."""

    def test_a_one_objective_full_answer_refuses_and_writes_no_plan(self) -> None:
        author_calls: list[dict] = []

        def one_objective_full(request: gen.LLMRequest) -> gen.LLMResponse:
            author_calls.append(json.loads(request.input_text))
            from tests.blueprint_support import response as support_response

            return support_response(blueprint_plan(scope="full", units=1, objectives_per_unit=1))

        llm = FakeLLM(
            {
                "coursebook.plan.generate": one_objective_full,
                "coursebook.plan.validate": lambda request: self.fail(
                    "a band violation must be refused before a validator is paid"
                ),
            }
        )
        plans_before = self.count("plans")
        documents_before = self.count("gen_plan_documents")
        with self.assertRaises(gen.ScopeBandRefused) as caught:
            gen.run_plan_job(
                self.connection,
                plan_job(
                    goal="Read the Moon's phases and predict the next full moon",
                    recipe="casual",
                    locale=None,
                    scope="full",
                ),
                llm,
                FakeSearch(),
                now=NOW,
            )
        refusal = caught.exception
        # The refusal names the learner's action and the scope that legally holds this goal.
        self.assertIn("small enough for a short course", str(refusal))
        self.assertIn("short", str(refusal))
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertEqual(refusal.reason, "scope_band")
        self.assertEqual(refusal.error_details["legal_scopes"], ["single"])
        # Two authoring attempts were spent, and no plan row or document was written.
        self.assertEqual(len(author_calls), 2)
        self.assertEqual(self.count("plans"), plans_before)
        self.assertEqual(self.count("gen_plan_documents"), documents_before)
        self.assertIsInstance(refusal, gen.ScopeBandRefused)


if __name__ == "__main__":
    unittest.main()
