"""CP-015: the excerpt window must carry prose, not navigation chrome.

Live courses were rejected by the validator because every ledger excerpt ended inside a site's
navigation menu (``Search ## Suggested Searches - [Artemis]…``), so no objective's claim could be
grounded. These tests pin the content-first excerpt and the plan-authoring rules that close it.
"""

from __future__ import annotations

import unittest

from coursebook import generation, research

# A faithful fragment of NASA's extracted skywatching page: a search banner, a link menu, then the
# article. The old 600-character window landed entirely in the menu.
NASA_PAGE = """Search

## Suggested Searches

- [Artemis](https://science.nasa.gov/?search=Artemis)
- [ISS](https://science.nasa.gov/?search=ISS)
- [Roman](https://science.nasa.gov/?search=Roman)
- [Webb](https://science.nasa.gov/?search=Webb)

# Night Sky

The constellations you can see at night depend on your location on Earth and the time of year.
As Earth orbits the Sun, the part of the sky that faces away from the Sun at night changes, so the
constellations visible at midnight shift through the year. The Moon always has one half lit by the
Sun; the phase you see depends on how much of that sunlit half faces Earth.
"""


class ExcerptContentTest(unittest.TestCase):
    def test_leading_navigation_chrome_is_skipped(self) -> None:
        text = research._excerpt(NASA_PAGE, research._MAX_EXCERPT)
        self.assertTrue(text.startswith("# Night Sky"), text[:80])
        self.assertNotIn("Suggested Searches", text)
        self.assertNotIn("?search=Artemis", text)

    def test_real_prose_survives_the_skip(self) -> None:
        text = research._excerpt(NASA_PAGE, research._MAX_EXCERPT)
        self.assertIn("location on Earth and the time of year", text)
        self.assertIn("sunlit half faces Earth", text)

    def test_window_is_bounded(self) -> None:
        self.assertEqual(len(research._excerpt("prose " * 2000, 300)), 300)

    def test_plain_prose_is_not_stripped(self) -> None:
        text = research._excerpt("A constellation is a group of stars.\nIt has no boundary.", 200)
        self.assertTrue(text.startswith("A constellation is a group of stars."))

    def test_excerpt_budget_is_large_enough_to_carry_a_claim(self) -> None:
        # Regression: 600 characters measured inside a nav menu. A window below 1200 cannot hold
        # an explanation plus its context, so a future shrink must fail here.
        self.assertGreaterEqual(research._MAX_EXCERPT, 1200)
        self.assertEqual(research.ResearchBudget().max_excerpt_chars, research._MAX_EXCERPT)

    def test_untrusted_excerpt_honours_the_new_window(self) -> None:
        body = "Grounding sentence about Sun-Earth-Moon geometry. " * 40
        wrapped = generation._untrusted_excerpt(body[:1500])
        inner = wrapped.split("\n", 1)[1].rsplit("\n", 1)[0]
        self.assertGreater(len(inner), 900, "the envelope truncated an excerpt below the old cap")


class PlanSourcingRulesTest(unittest.TestCase):
    def test_both_plan_prompts_state_the_ledger_grounding_rule(self) -> None:
        for builder in (generation._plan_instructions, generation._plan_instructions_v2):
            with self.subTest(builder=builder.__name__):
                text = builder(
                    recipe="committed",
                    dials={},
                    locale="en-US",
                    research_status="ok",
                    level="beginner",
                    subject_domain="science",
                    scope="short",
                )
                # Ledger-first: the author starts from the excerpt, not the goal, and may not
                # add a mechanism, name or label the excerpt does not state.
                self.assertIn("Author the plan from the source ledger", text)
                self.assertIn("level of generality the excerpt actually supports", text)
                self.assertIn("single accepted answer", text)
                self.assertIn("evidence target must be the same class", text)
                # Fewer honest objectives beat padding; an unsupported capability is recorded
                # in exclusions instead of invented.
                self.assertIn("A course may be short", text)
                self.assertIn("Not covered — no supporting source:", text)
                self.assertNotIn("Cover the goal:", text)
                self.assertIn("assess every evidence criterion", text)

    def test_plan_prompt_versions_are_current(self) -> None:
        self.assertEqual(generation.PLAN_PROMPT_VERSION, "plan-prompt.v13")
        self.assertEqual(generation.PLAN_PROMPT_VERSION_V2, "plan-prompt.v14")


if __name__ == "__main__":
    unittest.main()
