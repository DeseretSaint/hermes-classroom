"""Governed research jobs: budgets, cancellation accounting, ledger write, no hook research."""

from __future__ import annotations

import unittest
from unittest import mock

from coursebook import db, hooks, job_service, research, workers
from tests.kernel_support import KernelCase


class FakeSeam:
    """A real search/extract seam with deterministic pages and a call counter."""

    def __init__(self, *, pages: dict[str, str] | None = None, cancel_on_search: bool = False,
                 cancel_on_fetch: bool = False, unavailable: bool = False) -> None:
        self.pages = pages or {}
        self.searches: list[str] = []
        self.fetches: list[str] = []
        self.cancel_on_search = cancel_on_search
        self.cancel_on_fetch = cancel_on_fetch
        self.unavailable = unavailable
        self._lease: job_service.Lease | None = None

    def bind(self, lease: job_service.Lease) -> None:
        self._lease = lease

    def search(self, query: str, limit: int) -> list[dict]:
        self.searches.append(query)
        if self.unavailable:
            raise research.ResearchUnavailable("search backend offline")
        if self.cancel_on_search and self._lease is not None:
            job_service.request_cancel(self._lease.job_id)
        return [{"url": f"https://example.test/{i}", "title": f"Page {i}", "description": "d"}
                for i in range(min(limit, 1))]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        if self.cancel_on_fetch and self._lease is not None:
            job_service.request_cancel(self._lease.job_id)
        return {"url": url, "title": "Page", "content": self.pages.get(url, "authoritative body " * 20)}


class ResearchJobTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, _ = self.new_course()

    def run_job(self, seam: FakeSeam, **budget) -> tuple[dict, FakeSeam]:
        def factory(lease: job_service.Lease) -> FakeSeam:
            seam.bind(lease)
            return seam

        request = workers.ResearchRequest(
            goal="braise short ribs safely", course_id=self.course_id,
            budget=research.ResearchBudget(**budget) if budget else research.ResearchBudget(),
        )
        return workers.run_research_job(request, factory), seam

    def test_research_job_records_ledger_and_real_usage(self) -> None:
        view, seam = self.run_job(FakeSeam())
        self.assertEqual(view["state"], "completed")
        self.assertGreaterEqual(len(seam.searches), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_research_runs"), 1)
        ledger = self.rows("SELECT * FROM sources")
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["url"], "https://example.test/0")
        self.assertEqual(ledger[0]["support_status"], "unassessed")
        providers = {row["provider"] for row in self.rows("SELECT provider FROM usage_events")}
        self.assertIn("web_search", providers)
        self.assertIn("web_extract", providers)
        self.assertTrue(all(row["model"] is None for row in self.rows("SELECT model FROM usage_events")))

    def test_budget_caps_the_number_of_live_calls(self) -> None:
        view, seam = self.run_job(FakeSeam(), max_queries=1, max_results_per_query=1,
                                  max_pages=1, max_sources=1)
        self.assertEqual(view["state"], "completed")
        self.assertLessEqual(len(seam.searches), 1, "the executable budget caps live searches")
        self.assertLessEqual(len(seam.fetches), 1)

    def test_declared_depth_selects_the_budget_cell(self) -> None:
        deep = workers.ResearchRequest(goal="g", dials={"depth": "deep"})
        survey = workers.ResearchRequest(goal="g", dials={"depth": "survey"})
        self.assertGreater(deep.effective_budget.max_queries, survey.effective_budget.max_queries)
        self.assertEqual(deep.as_brief()["budget"]["max_queries"], 9)
        self.assertEqual(survey.as_brief()["budget"]["max_queries"], 3)
        with self.assertRaises(ValueError):
            workers.ResearchRequest(goal="g", dials={"depth": "standard"}).effective_budget

    def test_cancel_before_start_spends_nothing(self) -> None:
        job_id = self.ok("jobs.create", {"kind": "research", "brief": {}})["result"]["job_id"]
        job_service.request_cancel(job_id)
        seam = FakeSeam()
        view = job_service.execute(job_id, workers.research_stages(
            workers.ResearchRequest(goal="g"), lambda lease: seam.bind(lease) or seam))
        self.assertEqual(view["state"], "cancelled")
        self.assertEqual(seam.searches, [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 0)

    def test_cancel_during_research_stops_future_calls_and_keeps_paid_usage(self) -> None:
        view, seam = self.run_job(FakeSeam(cancel_on_search=True))
        self.assertEqual(view["state"], "cancelled")
        self.assertLessEqual(len(seam.fetches), 1, "the fetch after the cancel boundary must not run")
        # The search that actually happened is recorded; nothing is fabricated for the rest.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM usage_events"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM sources"), 0)

    def test_unavailable_search_is_honest_not_silent(self) -> None:
        view, _ = self.run_job(FakeSeam(unavailable=True))
        self.assertEqual(view["state"], "completed")
        self.assertEqual(view["checkpoint"]["research_status"], "unavailable")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM sources"), 0)

    def test_reconnect_does_not_duplicate_the_ledger(self) -> None:
        first, _ = self.run_job(FakeSeam())
        second, _ = self.run_job(FakeSeam())
        self.assertEqual(first["state"], "completed")
        self.assertEqual(second["state"], "completed")
        # Same URL re-fetched: the ledger keeps one row per URL, not a duplicate per job.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM sources"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM gen_research_runs"), 2)


class GradingHookTest(unittest.TestCase):
    def test_pre_turn_hook_never_runs_deep_research(self) -> None:
        with mock.patch.object(workers, "run_research_job", side_effect=AssertionError("research in hook")):
            self.assertIsNone(hooks.pre_llm_call(session_id="s", user_message="hello"))
            self.assertIsNone(hooks.post_llm_call(session_id="s", assistant_response="hi"))

    def test_hooks_module_does_not_import_a_search_seam(self) -> None:
        self.assertFalse(hasattr(hooks, "run_research"))
        self.assertFalse(hasattr(hooks, "research"))


if __name__ == "__main__":
    unittest.main()
