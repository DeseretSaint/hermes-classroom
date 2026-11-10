"""H-43: the plan-scope table may not wear the v2 contract's clothes.

Two honesty defects from H-40 (D3/D4): the ``full`` scope note rendered a v1 sentence beside the
v2 band, and ``SCOPE_EXPECTATIONS[scope]["objectives"]`` held the pre-blueprint range under a name
a reader would take for the enforced v2 band. These cases pin the copy, not the policy: no
enforced bound or prompt semantics change here, so the v1 and v2 prompt lines are asserted
exactly as the kernel already authored them.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen, research


def _rendered(scope: str) -> gen.LLMRequest:
    return gen.build_plan_request(
        goal="Learn to solder through-hole joints that hold",
        recipe="casual",
        dials={},
        locale=None,
        research_run=research.ResearchRun("unavailable", [], [], "none"),
        scope=scope,
    )


class ScopeTableNamesItsContractsTest(unittest.TestCase):
    """D4: the v1 range is named for its contract and never borrows the v2 key."""

    def test_no_scope_exposes_a_bare_objectives_range(self) -> None:
        # A reader who picks ``objectives`` instead of ``blueprint_objectives`` would report the
        # wrong contract. The key must not exist at all.
        for scope, expectation in gen.SCOPE_EXPECTATIONS.items():
            with self.subTest(scope=scope):
                self.assertNotIn(
                    "objectives",
                    expectation,
                    "a bare 'objectives' range reads as the enforced v2 band",
                )

    def test_the_legacy_range_survives_only_under_an_explicit_v1_name(self) -> None:
        for scope, expectation in gen.SCOPE_EXPECTATIONS.items():
            with self.subTest(scope=scope):
                self.assertIn("blueprint_objectives", expectation)
                self.assertIn("v1_objectives", expectation)
                v1_low, v1_high = expectation["v1_objectives"]
                self.assertLessEqual(v1_low, v1_high)
                # The two contracts genuinely differ for every scope; that is why the names matter.
                self.assertNotEqual(
                    tuple(expectation["v1_objectives"]),
                    tuple(expectation["blueprint_objectives"]),
                )

    def test_a_scope_range_that_differs_from_the_v2_band_is_marked_v1(self) -> None:
        # The generic rule from the card: equality with the v2 band needs no marking, anything
        # else must carry the v1 marker in its key.
        for scope, expectation in gen.SCOPE_EXPECTATIONS.items():
            with self.subTest(scope=scope):
                for key, value in expectation.items():
                    if not isinstance(value, tuple) or len(value) != 2:
                        continue
                    if tuple(value) == tuple(expectation["blueprint_objectives"]):
                        continue
                    self.assertTrue(
                        key.startswith("v1_") or key.startswith("blueprint_")
                        or key == "unit_objectives",
                        f"{scope}.{key} states a range that is neither the v2 band nor "
                        "explicitly marked v1",
                    )


class ScopeCopyInTheRenderedPromptsTest(unittest.TestCase):
    """D3: each prompt states its own band on the scope bullet, and no stale sentence survives."""

    STALE = "standard objective range stands"

    def test_full_v2_prompt_states_the_v2_band_and_not_the_v1_sentence(self) -> None:
        request = _rendered("full")
        self.assertEqual(request.prompt_version, gen.PLAN_PROMPT_VERSION_V2)
        text = request.instructions
        self.assertIn("Scope: full", text)
        self.assertIn("Produce 2 to 12 unit(s) and 12 to 40 objective(s)", text)
        self.assertNotIn(self.STALE, text)
        self.assertNotIn(self.STALE, gen.SCOPE_EXPECTATIONS["full"]["note"])

    def test_every_v2_prompt_states_the_band_its_scope_enforces(self) -> None:
        for scope in gen.SCOPES:
            with self.subTest(scope=scope):
                expectation = gen.SCOPE_EXPECTATIONS[scope]
                unit_low, unit_high = expectation["blueprint_units"]
                obj_low, obj_high = expectation["blueprint_objectives"]
                text = _rendered(scope).instructions
                self.assertIn(
                    f"Produce {unit_low} to {unit_high} unit(s) and "
                    f"{obj_low} to {obj_high} objective(s)",
                    text,
                )
                self.assertNotIn(self.STALE, text)

    def test_the_v1_prompt_still_asks_for_the_v1_range(self) -> None:
        # No prompt-semantics change: an unscoped/legacy brief keeps the range it always had.
        # H-89 adds the vocabulary-inventory block, so the prompt version advances (v4 -> v6)
        # without changing that range; H-195 adds the through-line and prerequisite-assumption
        # requirements and advances the label again (v6 -> v8), still with the same range.
        self.assertEqual(gen.PLAN_PROMPT_VERSION, "plan-prompt.v11")
        for scope, expected in (("single", "4 to 5"), ("short", "4 to 6"), ("full", "4 to 8")):
            with self.subTest(scope=scope):
                text = gen._plan_instructions(
                    recipe="committed",
                    dials={},
                    locale=None,
                    research_status="unavailable",
                    scope=scope,
                )
                self.assertIn(f"Produce {expected} objectives", text)
                self.assertNotIn(self.STALE, text)
        unscoped = gen._plan_instructions(
            recipe="committed", dials={}, locale=None, research_status="unavailable"
        )
        self.assertIn("Produce 4 to 8 objectives", unscoped)


if __name__ == "__main__":
    unittest.main()
