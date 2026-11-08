"""H-168: a course size sets a floor under the research pass.

The learner's depth dial is a preference, not a way to ask for a full course from a goal-only
survey. These tests pin the floor and, just as importantly, pin that an explicit executable
budget remains the hard ceiling.
"""
from __future__ import annotations

import unittest

from coursebook import research


class ExpandingSeam:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        slug = "-".join(query.lower().split())[:48] or "q"
        return [
            {
                "url": f"https://example.test/{slug}/{index}",
                "title": f"{query} {index}",
                "description": "snippet",
            }
            for index in range(limit)
        ]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        return {"url": url, "title": url, "content": "a bounded page body " * 20, "published_at": None}


class ScopeResearchFloorTest(unittest.TestCase):
    def test_the_floor_is_part_of_the_course_contract(self) -> None:
        self.assertEqual(research.SCOPE_MIN_DEPTH, {"single": "working", "short": "working", "full": "deep"})
        self.assertEqual(research.effective_depth("survey", "single"), "working")
        self.assertEqual(research.effective_depth("survey", "short"), "working")
        self.assertEqual(research.effective_depth("survey", "full"), "deep")
        self.assertEqual(research.effective_depth(None, "full"), "deep")
        self.assertEqual(research.effective_depth("working", "full"), "deep")
        self.assertEqual(research.effective_depth("deep", "single"), "deep")

    def test_a_full_course_survey_is_not_one_query(self) -> None:
        seam = ExpandingSeam()
        run = research.run_research(
            "Learn to braise short ribs safely",
            recipe="committed",
            dials={"depth": "survey"},
            scope="full",
            search=seam,
        )
        self.assertEqual(run.status, "ok")
        self.assertGreaterEqual(len(run.queries), 8)
        self.assertGreaterEqual(len(seam.queries), 8)
        self.assertLessEqual(len(run.queries), 12)
        self.assertEqual(len(seam.queries), len(run.queries))

    def test_a_short_course_survey_sees_the_curriculum_queries(self) -> None:
        seam = ExpandingSeam()
        run = research.run_research(
            "Order coffee in Japanese",
            recipe="committed",
            dials={"depth": "survey"},
            scope="short",
            search=seam,
        )
        self.assertGreaterEqual(len(run.queries), 4)
        self.assertTrue(
            any("how to teach curriculum sequence" in entry.get("query", "") for entry in run.queries),
            "the short floor must ask how the subject is sequenced",
        )

    def test_an_explicit_budget_remains_the_ceiling(self) -> None:
        seam = ExpandingSeam()
        run = research.run_research(
            "Order coffee in Japanese",
            recipe="committed",
            dials={"depth": "survey"},
            scope="full",
            search=seam,
            budget=research.ResearchBudget(
                max_queries=1, max_results_per_query=1, max_pages=1, max_sources=1
            ),
        )
        self.assertEqual(run.status, "ok")
        self.assertEqual(len(run.queries), 1)
        self.assertEqual(len(seam.queries), 1)

    def test_unknown_depth_or_scope_still_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            research.effective_depth("standard", "short")
        with self.assertRaises(ValueError):
            research.effective_depth("working", "course")


if __name__ == "__main__":
    unittest.main()
