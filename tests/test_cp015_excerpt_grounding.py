"""CP-015: the excerpt window must carry prose, not navigation chrome.

Live courses were rejected by the validator because every ledger excerpt ended inside a site's
navigation menu (``Search ## Suggested Searches - [Artemis]…``), so no objective's claim could be
grounded. These tests pin the content-first excerpt and the plan-authoring rules that close it.
"""

from __future__ import annotations

import json
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
        # CP-015a R-3 changed this contract by ruling: the window now ends on the last sentence
        # boundary at or before the ceiling, so it can only be shorter than the ceiling and the
        # old "== 300" assertion is now a "<= 300" plus a boundary assertion.
        self.assertLessEqual(len(research._excerpt("prose " * 2000, 300)), 300)
        bounded = research._excerpt("A starter is alive and active. " * 100, 300)
        self.assertLessEqual(len(bounded), 300)
        self.assertTrue(bounded.endswith("."), bounded[-40:])

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
                # A check exercises the capability, not the source's wording; a goal the ledger
                # cannot support is recorded in exclusions and kept out of the learner_outcome
                # (CP-015a: naming it there is refused by the rule gate); a prerequisite edge must
                # name a shared concept.
                self.assertIn("not to recall the source's wording", text)
                self.assertIn("Do not name the excluded capability in learner_outcome", text)
                self.assertIn("false ordering", text)

    def test_plan_prompt_versions_are_current(self) -> None:
        # CP-015g/D1-F1 states three more shared rules (the check's kind follows the objective's
        # evidence target, the casual self-check form rule, the objective claim-link rule) on this
        # same rule text, so both plan labels advance rather than reusing v17/v18. W2-9 then
        # deletes the declared-gap prohibition from the shared sourcing rule, advancing both again.
        self.assertEqual(generation.PLAN_PROMPT_VERSION, "plan-prompt.v22")
        self.assertEqual(generation.PLAN_PROMPT_VERSION_V2, "plan-prompt.v25")


class SourceBriefFitsTheRequestTest(unittest.TestCase):
    """A deep research pass must fit the plan request without cutting the JSON or the ledger.

    Live: ten sources at the 1200-character window made a short-scope plan request 25 636 bytes
    against the 24 000-byte bound, and the job failed before the author model was called.
    """

    def _sources(self, count: int = 10, chars: int = 1200) -> list[research.SourceRecord]:
        body = ("The Moon's phases follow from its position relative to the Sun and Earth. " * 40)[:chars]
        return [
            research.SourceRecord(
                source_id=f"src_{index:02d}",
                url=f"https://example.invalid/{index}",
                title=f"Source {index}",
                publisher="Example Press",
                source_type="web_page",
                fetched_at="2026-11-10T12:00:00Z",
                published_at=None,
                content_hash="sha256:0",
                excerpt=body,
            )
            for index in range(count)
        ]

    def _size(self, payload: dict) -> int:
        return len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _payload(self) -> dict:
        # The rest of a real plan request (curriculum brief, capability policy, rules) is about
        # ten kilobytes; the ledger is what tips a deep pass over the bound.
        return {"goal": "Read the night sky", "plan_context": "rule " * 2000, "sources": []}

    def test_the_unfitted_ledger_would_overflow_the_bound(self) -> None:
        payload = self._payload()
        payload["sources"] = generation._source_brief(self._sources())
        self.assertGreater(self._size(payload), generation.REQUEST_BYTES_BOUNDS["short"])

    def test_a_deep_ledger_is_shrunk_not_dropped(self) -> None:
        limit = generation.REQUEST_BYTES_BOUNDS["short"]
        sources = self._sources()
        payload = self._payload()
        brief = generation._fit_source_brief(payload, sources, limit=limit)
        payload["sources"] = brief
        self.assertEqual([row["source_id"] for row in brief], [source.source_id for source in sources])
        self.assertLessEqual(self._size(payload), limit)
        # The window shrank; the text is still the fetched prose, not a stub.
        inner = brief[0]["untrusted_excerpt"].split("\n")[1]
        self.assertGreater(len(inner), 300)
        self.assertLess(len(inner), research._MAX_EXCERPT)


if __name__ == "__main__":
    unittest.main()
