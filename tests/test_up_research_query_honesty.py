"""Upgrade 32 — a failed search query may not report the research pass as ok.

The failure this file pins: a seam that raises on eight of the nine bounded queries used to
record the errors on the query entries and then report ``status="ok"`` with no warning, so a plan
whose ledger came from a third of the questions looked like a clean pass. The pass now names the
arithmetic, and the per-query error travels with the job result.

Every test here runs offline with a deterministic fake LLM and a fake seam; nothing is fetched.
"""

from __future__ import annotations

import json
import sqlite3
import unittest

from coursebook import generation as gen
from coursebook import research
from tests.blueprint_support import (
    blueprint_plan,
    response as support_response,
    validation_pass,
    validation_responder,
)
from tests.test_generation import FakeLLM, NOW, plan_job

#: A fetched page that genuinely speaks to "Order coffee in Japanese". The relevance gate scores
#: the fetched body against the goal, so a seam standing in for a real pass must fetch real prose.
_ON_TOPIC_BODY = (
    "Order coffee in Japanese: say コーヒーをください at the counter and the staff will ask whether "
    "you want it hot or iced. A Japanese café lists the coffee order on the menu, and staff will "
    "repeat the order back. " * 8
)

class _SearchAnswersOnce:
    """A seam whose search raises on every query but the first.

    The one answered query returns a single fetchable URL, so the run has a real source and the
    only thing missing is the other questions — exactly the reported failure.
    """

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        if len(self.queries) > 1:
            raise research.ResearchUnavailable("search backend returned no answer")
        slug = "-".join(query.lower().split())[:60] or "q"
        return [{"url": f"https://example.org/{slug}/0", "title": query, "description": "s"}]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        return {"url": url, "title": url, "content": "page body text " * 20, "published_at": None}


class _SearchFlakyOnce:
    """A seam that answers every query but raises on exactly one of them."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        if len(self.queries) == 2:
            raise research.ResearchUnavailable("one flaky provider call")
        slug = "-".join(query.lower().split())[:60] or "q"
        return [
            {"url": f"https://example.org/{slug}/{index}", "title": query, "description": "s"}
            for index in range(limit)
        ]

    def fetch(self, url: str, max_chars: int) -> dict:
        # On-topic prose, not filler: the relevance gate judges the fetched body, and a page whose
        # only text is "page body text" carries nothing to score. This seam is about query
        # accounting, so its pages must look like the pass they are standing in for.
        return {"url": url, "title": url, "content": _ON_TOPIC_BODY, "published_at": None}


class ResearchQueryHonestyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_search_errors_degrade_the_pass(self) -> None:
        seam = _SearchAnswersOnce()
        scoped = blueprint_plan(scope="full", units=2, objectives_per_unit=6)
        result = gen.run_plan_job(
            self.connection,
            plan_job(dials={"depth": "deep"}, scope="full"),
            FakeLLM(
                {
                    "coursebook.plan.generate": support_response(scoped),
                    "coursebook.plan.validate": validation_responder(
                        support_response, validation_pass()
                    ),
                }
            ),
            seam,
            now=NOW,
            # Nine bounded questions is the pass this test is about: the cell is small enough
            # that the arithmetic is exact (8 of 9) and unchanged if the depth tail grows.
            research_budget=research.ResearchBudget(
                max_queries=9, max_results_per_query=5, max_pages=8, max_sources=8
            ),
        )

        # The seam answered exactly one of nine questions; the other eight raised. Before this
        # change the run reported "ok" here with no warning at all.
        self.assertEqual(len(seam.queries), 9)
        self.assertEqual(result["research"]["status"], "degraded")

        warnings = [warning for warning in result["warnings"] if "research degraded" in warning]
        self.assertTrue(warnings, f"no degraded warning in {result['warnings']!r}")
        self.assertIn("8 of 9", warnings[0])
        self.assertIn("1 fetched source", warnings[0])

        self.assertEqual(result["research"]["fetch_failures"], 0)
        self.assertEqual(len(result["research"]["query_results"]), 9)
        self.assertEqual(len(result["research"]["query_failures"]), 8)

        # The reviewer can see *which* question went unanswered, with its error.
        unanswered = {entry["query"] for entry in result["research"]["query_failures"]}
        self.assertEqual(unanswered, set(seam.queries[1:]))
        self.assertTrue(all(entry["error"] for entry in result["research"]["query_failures"]))

        run_row = self.connection.execute("SELECT * FROM gen_research_runs").fetchone()
        self.assertEqual(run_row["status"], "degraded")
        self.assertIn("8 of 9", run_row["reason"] or "")
        queries = json.loads(run_row["queries_json"])
        self.assertEqual(sum(1 for entry in queries if entry.get("error")), 8)

    def test_one_flaky_query_does_not_degrade_the_pass(self) -> None:
        """The adversarial bound: a lone flake stays ok, and its error is still on record."""
        seam = _SearchFlakyOnce()
        run = research.run_research(
            "Order coffee in Japanese",
            recipe="committed",
            dials={"depth": "deep"},
            locale="ja-JP",
            scope="full",
            search=seam,
            now=NOW,
        )
        self.assertGreaterEqual(len(run.queries), 4)
        self.assertEqual(len(run.query_failures), 1)
        self.assertEqual(len(run.failures), 0)
        self.assertEqual(run.status, "ok")
        self.assertIsNone(run.reason)
        self.assertIn(seam.queries[1], run.query_failures[0]["query"])

    def test_a_majority_of_query_failures_names_the_arithmetic_in_the_reason(self) -> None:
        seam = _SearchAnswersOnce()
        run = research.run_research(
            "Order coffee in Japanese",
            recipe="committed",
            dials={"depth": "deep"},
            locale="ja-JP",
            scope="full",
            search=seam,
            now=NOW,
        )
        self.assertEqual(run.status, "degraded")
        self.assertEqual(len(run.sources), 1)
        self.assertIsNotNone(run.reason)
        self.assertIn(f"{len(run.query_failures)} of {len(run.queries)}", run.reason)
        # A degraded pass is never a boolean: the run's own report carries the count too.
        self.assertEqual(run.to_dict()["query_failures"], run.query_failures)


if __name__ == "__main__":
    unittest.main()
