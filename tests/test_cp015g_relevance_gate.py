"""CP-015g quality: an off-topic source cannot reach the plan digest or support an objective.

Measured on a real-provider pass for the unseen topic "prune a fig tree": seven fetched pages,
two unrelated to the goal (an FAO meat-processing page and a forestry tree-identification page).
Both happened to bind zero claims, so the plan was honest — but by luck, not by rule. These tests
pin the rule: ``research.run_research`` scores every fetched page against the goal's own content
words (``coursebook.relevance``), admits only pages above the coverage floor as ``SourceRecord``
rows, and records every refusal in the run's ``dropped`` ledger with its query, score and reason.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from coursebook import db, generation as gen, relevance, research
from coursebook.research import ResearchBudget, SourceRecord
from tests.kernel_support import KernelCase
from tests.test_generation import (
    NOW,
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

GOAL = "prune a fig tree"

#: A page that speaks to the goal: title, URL and body all carry ``prune``/``fig``/``tree``.
ON_TOPIC_BODY = (
    "Pruning a fig tree: cut in late winter while the tree is dormant. Remove crossing branches "
    "and shorten the previous season's growth; a fig carries fruit on new wood, so pruning "
    "shapes the tree and keeps the crop within reach. Feed the tree in spring."
)

#: The two pages the measured pass actually carried. Neither is about figs.
OFF_TOPIC_PAGES = {
    "https://www.fao.org/meat-guidelines": (
        "Guidelines for slaughtering, meat cutting and further processing",
        "Slaughtering hygiene, carcass dressing, meat cutting lines and further processing of "
        "animal products under inspection.",
    ),
    "https://forestry.extension.wisc.edu/tree-identification": (
        "Tree Identification – Forestry & Wildlife",
        "Identify a tree by bark, needles, leaves and winter twigs; a forestry field key for "
        "wildlife habitat surveys.",
    ),
}


class MixedSearchSeam:
    """One on-topic result plus one off-topic result per query, for an unseen topic."""

    def __init__(self) -> None:
        self.searches: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.searches.append(query)
        off_topic = list(OFF_TOPIC_PAGES)
        results = [
            {
                "url": f"https://www.rhs.org.uk/fig-pruning/{len(self.searches)}",
                "title": "Pruning fig trees: a practical guide",
                "description": "how to prune a fig tree",
            },
            {
                "url": off_topic[(len(self.searches) - 1) % len(off_topic)],
                "title": OFF_TOPIC_PAGES[off_topic[(len(self.searches) - 1) % len(off_topic)]][0],
                "description": "unrelated reference result",
            },
        ]
        return results[:limit]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        if url in OFF_TOPIC_PAGES:
            title, body = OFF_TOPIC_PAGES[url]
            return {"url": url, "title": title, "content": body, "published_at": None}
        return {
            "url": url,
            "title": "Pruning fig trees: a practical guide",
            "content": ON_TOPIC_BODY,
            "published_at": None,
        }


def _run(seam=None, *, goal: str = GOAL) -> research.ResearchRun:
    return research.run_research(
        goal,
        recipe="committed",
        dials={"depth": "working"},
        scope="short",
        search=seam or MixedSearchSeam(),
        budget=ResearchBudget(
            max_queries=3, max_results_per_query=2, max_pages=8, max_sources=8
        ),
    )


def _soldering_gate() -> dict:
    """The recorded H-40 soldering pass, scored on its full fetched bodies."""
    transcript = json.loads(
        (
            Path(__file__).resolve().parent.parent
            / "audit"
            / "adversarial"
            / "harness-e2e"
            / "transcripts"
            / "soldering_full.json"
        ).read_text(encoding="utf-8")
    )
    return relevance.gate_pages(
        transcript["scenario"]["goal"],
        [
            {"title": entry["title"], "url": entry["url"], "text": entry["content"]}
            for entry in transcript["research"]["pages"]
        ],
    )


class GateArithmeticTest(unittest.TestCase):
    def test_the_goal_is_reduced_to_its_own_content_words(self) -> None:
        self.assertEqual(relevance.goal_terms(GOAL), ["prun", "fig", "tree"])

    def test_the_measured_pages_are_classified_as_the_pass_measured_them(self) -> None:
        gate = relevance.gate_pages(
            GOAL,
            [
                {"url": "https://rhs.org.uk/fig", "title": "Pruning fig trees", "text": ON_TOPIC_BODY},
                {
                    "url": "https://www.fao.org/meat-guidelines",
                    "title": OFF_TOPIC_PAGES["https://www.fao.org/meat-guidelines"][0],
                    "text": OFF_TOPIC_PAGES["https://www.fao.org/meat-guidelines"][1],
                },
                {
                    "url": "https://forestry.extension.wisc.edu/tree-identification",
                    "title": OFF_TOPIC_PAGES["https://forestry.extension.wisc.edu/tree-identification"][0],
                    "text": OFF_TOPIC_PAGES["https://forestry.extension.wisc.edu/tree-identification"][1],
                },
            ],
        )
        verdicts = {item["url"]: item for item in gate["verdicts"]}
        self.assertEqual(verdicts["https://rhs.org.uk/fig"]["verdict"], relevance.ON_TOPIC)
        self.assertEqual(
            verdicts["https://www.fao.org/meat-guidelines"]["verdict"], relevance.OFF_TOPIC
        )
        self.assertEqual(
            verdicts["https://forestry.extension.wisc.edu/tree-identification"]["verdict"],
            relevance.OFF_TOPIC,
        )
        # The forestry page matched only "tree"; the meat page matched nothing at all. Both carry
        # an explicit verdict and a reason, not silence.
        forestry = verdicts["https://forestry.extension.wisc.edu/tree-identification"]
        self.assertEqual(forestry["matched"], ["tree"])
        self.assertIn("below", forestry["reason"])
        # The sentence carries the page's own ratio, not the floor constant, so a reader can
        # reproduce the refusal without opening the module.
        ratio = forestry["score"] / gate["best_score"]
        self.assertIn(f"{ratio:.2f} of this pass's best page", forestry["reason"])
        self.assertIn(f"below the {relevance.RELATIVE_MARGIN:.2f} line", forestry["reason"])
        self.assertEqual(verdicts["https://www.fao.org/meat-guidelines"]["matched"], [])

    def test_an_unscoreable_goal_admits_every_page_and_says_why(self) -> None:
        gate = relevance.gate_pages("", [{"url": "https://x.test/a", "title": "a", "text": "b"}])
        self.assertEqual(gate["terms"], [])
        self.assertEqual(gate["dropped"], [])
        self.assertTrue(gate["verdicts"][0]["reason"])

    def test_when_no_page_clears_the_floor_the_pass_is_kept_whole(self) -> None:
        # A vague goal (or a provider that returned only noise) is a bad profile, not a reason to
        # silently empty a ledger the job paid for.
        gate = relevance.gate_pages(
            "become a better person",
            [
                {"url": "https://a.test", "title": "Meat processing", "text": "slaughter hygiene"},
                {"url": "https://b.test", "title": "Bark keys", "text": "needles twigs"},
            ],
        )
        self.assertTrue(gate["floor_tripped"])
        self.assertEqual(gate["dropped"], [])
        self.assertEqual(len(gate["kept"]), 2)

    def test_a_compound_goal_does_not_drop_a_genuinely_on_topic_expert_page(self) -> None:
        # The H-40 recorded soldering pass: a CU Boulder soldering resource uses six of the goal's
        # thirteen terms and scores 0.38 against a best page at 1.00. An absolute floor alone
        # refused it; the recorded packet then lost a real source.
        gate = _soldering_gate()
        self.assertEqual(gate["dropped"], [], [v["url"] for v in gate["verdicts"]])
        self.assertFalse(gate["floor_tripped"])
        boulder = [
            item for item in gate["verdicts"] if "physicslabs.colorado.edu" in item["url"]
        ]
        self.assertEqual(len(boulder), 1)
        self.assertLess(boulder[0]["score"], relevance.MIN_COVERAGE)
        self.assertGreaterEqual(boulder[0]["score"], relevance.RELATIVE_MARGIN * gate["best_score"])
        self.assertEqual(boulder[0]["verdict"], relevance.ON_TOPIC)

    def test_a_relative_admission_prints_the_pages_own_ratio_not_the_margin(self) -> None:
        # The defect this pins: every relatively-admitted page said it "reaches 0.35 of this pass's
        # best page" — the constant — whatever it actually reached. Here the CU Boulder page is
        # 0.382 against a 1.000 best, so its ratio (0.38) and the line (0.35) are different
        # strings; the sentence must carry the ratio and keep 0.35 only as the line compared to.
        gate = _soldering_gate()
        boulder = [
            item for item in gate["verdicts"] if "physicslabs.colorado.edu" in item["url"]
        ][0]
        ratio = boulder["score"] / gate["best_score"]
        self.assertNotAlmostEqual(ratio, relevance.RELATIVE_MARGIN, places=2)
        self.assertIn(f"reaches {ratio:.2f} of this pass's best page", boulder["reason"])
        self.assertIn(f"above the {relevance.RELATIVE_MARGIN:.2f} line", boulder["reason"])
        self.assertNotIn(
            f"reaches {relevance.RELATIVE_MARGIN:.2f} of this pass's best page", boulder["reason"]
        )
        # Every page the relative half admits tells its own ratio, not a shared constant.
        relative = [
            item
            for item in gate["verdicts"]
            if item["verdict"] == relevance.ON_TOPIC
            and item["score"] < relevance.MIN_COVERAGE
        ]
        self.assertGreaterEqual(len(relative), 1, "the packet must exercise the relative half")
        for item in relative:
            own = item["score"] / gate["best_score"]
            self.assertIn(f"reaches {own:.2f} of this pass's best page", item["reason"])


class ResearchGateTest(unittest.TestCase):
    def test_a_mixed_pass_keeps_only_the_on_topic_pages(self) -> None:
        seam = MixedSearchSeam()
        run = _run(seam)
        self.assertEqual(run.status, "ok")
        self.assertTrue(run.sources)
        self.assertTrue(run.dropped)
        for source in run.sources:
            self.assertNotIn(source.url, OFF_TOPIC_PAGES)
            self.assertGreaterEqual(source.relevance_score, relevance.MIN_COVERAGE)
        for entry in run.dropped:
            self.assertIn(entry["url"], OFF_TOPIC_PAGES)
            self.assertEqual(entry["verdict"], relevance.OFF_TOPIC)
            self.assertTrue(entry["query"], "a dropped page records the query that found it")
            self.assertIsInstance(entry["relevance_score"], float)
            self.assertTrue(entry["reason"], "a dropped page records why it was dropped")

    def test_the_run_ledger_summary_is_reproducible(self) -> None:
        run = _run()
        self.assertEqual(run.relevance["terms"], ["prun", "fig", "tree"])
        self.assertEqual(run.relevance["min_coverage"], relevance.MIN_COVERAGE)
        self.assertEqual(run.relevance["kept"], len(run.sources))
        self.assertEqual(run.relevance["dropped"], len(run.dropped))
        self.assertFalse(run.relevance["floor_tripped"])
        # The reason text stored in the ledger is non-empty and byte-identical on a re-run: the
        # verdict copy is deterministic, not a timestamp or a counter.
        again = _run()
        self.assertTrue(all(entry["reason"] for entry in run.dropped))
        self.assertEqual(
            [entry["reason"] for entry in run.dropped],
            [entry["reason"] for entry in again.dropped],
        )

    def test_the_dropped_rows_are_carried_in_the_run_dict(self) -> None:
        payload = _run().to_dict()
        self.assertEqual(
            sorted(entry["url"] for entry in payload["dropped"]),
            sorted(OFF_TOPIC_PAGES),
        )
        self.assertTrue(all("reason" in entry for entry in payload["dropped"]))


class PlanDigestTest(unittest.TestCase):
    """The plan author sees ``run.sources`` and nothing else — the gate is the guard."""

    def _payload(self, run: research.ResearchRun) -> dict:
        request = gen.build_plan_request(
            goal=GOAL,
            recipe="committed",
            dials={"depth": "working"},
            locale=None,
            research_run=run,
            scope="short",
            subject_domain="vocational",
        )
        return json.loads(request.input_text)

    def test_the_plan_digest_carries_no_off_topic_row(self) -> None:
        run = _run()
        payload = self._payload(run)
        self.assertTrue(payload["sources"])
        self.assertNotIn("fao.org", json.dumps(payload["sources"]))
        self.assertNotIn("forestry.extension.wisc.edu", json.dumps(payload["sources"]))
        # The author is told in the research reason that some fetched pages were refused; the
        # digest itself carries only the admitted rows.
        self.assertIn("dropped", payload["research"]["reason"])
        self.assertEqual(
            {row["source_id"] for row in payload["sources"]},
            {source.source_id for source in run.sources},
        )

    def test_a_plan_cannot_cite_a_dropped_page_even_if_the_model_invents_the_id(self) -> None:
        run = _run()
        dropped_url = sorted(OFF_TOPIC_PAGES)[0]
        # A model that read a stale transcript might cite the dropped page. The ledger check is
        # against the ids the run actually admitted, so an id derived from a dropped row is
        # refused before the plan is stored — it can never become an objective's support.
        fake_id = f"src-{dropped_url}"
        plan = {
            "objectives": [
                {
                    "ordinal": 1,
                    "title": "Prune a fig tree",
                    "evidence_target": "comprehension",
                    "support": "sourced",
                    "source_ids": [fake_id],
                    "source_quote": "slaughtering hygiene",
                }
            ],
            "sections": [{"ordinal": 1, "objective_refs": [1], "source_ids": [fake_id]}],
        }
        with self.assertRaises(gen.GenerationRejected) as caught:
            gen._enforce_plan_rules_v1(
                plan,
                recipe="committed",
                dials={},
                locale=None,
                ledger=list(run.sources),
                scope=None,
                goal=GOAL,
            )
        self.assertIn("never fetched", str(caught.exception))


class LedgerPersistenceTest(KernelCase):
    """The drop is durable: the snapshot records it and no ledger row admits it."""

    def setUp(self) -> None:
        super().setUp()
        self.course_id, _ = self.new_course()

    def test_the_run_records_why_each_page_was_dropped_and_rows_only_keep_the_kept(self) -> None:
        run = _run()
        with db.transaction() as connection:
            gen.ensure_schema(connection)
            run_id = gen._persist_research(
                connection, course_id=self.course_id, job_id=None, run=run, now=None
            )
        with db.read() as connection:
            row = connection.execute(
                "SELECT sources_json, dropped_json FROM gen_research_runs WHERE id = ?", (run_id,)
            ).fetchone()
            ledger = connection.execute(
                "SELECT url, claim_count FROM sources WHERE course_id = ?", (self.course_id,)
            ).fetchall()
        sources_json = json.loads(row["sources_json"])
        dropped_json = json.loads(row["dropped_json"])
        self.assertEqual(len(sources_json), len(run.sources))
        self.assertEqual(sorted(entry["url"] for entry in dropped_json), sorted(OFF_TOPIC_PAGES))
        self.assertTrue(all(entry["reason"] and entry["query"] for entry in dropped_json))
        # The stored copy names the page's own ratio and the line it missed, not a bare constant.
        self.assertTrue(
            all("of this pass's best page" in entry["reason"] for entry in dropped_json)
        )
        self.assertTrue(
            all(
                f"below the {relevance.RELATIVE_MARGIN:.2f} line" in entry["reason"]
                for entry in dropped_json
            )
        )
        ledger_urls = {str(item["url"]) for item in ledger}
        self.assertTrue(ledger_urls)
        self.assertFalse(ledger_urls & set(OFF_TOPIC_PAGES))

    def test_claim_count_is_zero_for_a_source_no_objective_cites(self) -> None:
        run = _run()
        kept = run.sources[0].source_id
        plan = {
            "objectives": [{"ordinal": 1, "source_ids": [kept]}],
            "sections": [{"ordinal": 1, "source_ids": []}],
        }
        with db.transaction() as connection:
            gen.ensure_schema(connection)
            gen._persist_research(
                connection, course_id=self.course_id, job_id=None, run=run, plan=plan, now=None
            )
        with db.read() as connection:
            rows = {
                str(item["id"]): int(item["claim_count"])
                for item in connection.execute(
                    "SELECT id, claim_count FROM sources WHERE course_id = ?", (self.course_id,)
                )
            }
        self.assertEqual(rows[kept], 1)
        for source in run.sources[1:]:
            self.assertEqual(rows[source.source_id], 0)


class DroppedIdentityTest(unittest.TestCase):
    def test_a_dropped_page_is_never_a_source_record(self) -> None:
        run = _run()
        self.assertTrue(all(isinstance(source, SourceRecord) for source in run.sources))
        self.assertTrue(all("source_id" not in entry for entry in run.dropped))


class EndToEndPlanCitationTest(GenerationTestBase):
    """The acceptance path: a mixed search pass yields a stored plan citing only the on-topic row."""

    def test_a_mixed_pass_stores_a_plan_citing_only_the_on_topic_source(self) -> None:
        on_topic_url = "https://www.ncausa.org/ordering-coffee-in-japan"
        pages = {
            on_topic_url: {
                "title": "How to order coffee in Japan",
                "publisher": "National Coffee Association",
                "published_at": None,
                "content": (
                    "Order coffee in Japanese with a simple phrase: コーヒーをください. "
                    "In a Japanese café, say the coffee order clearly and wait. " * 8
                ),
            },
            "https://www.fao.org/meat-guidelines": {
                "title": "Guidelines for slaughtering, meat cutting and further processing",
                "publisher": "FAO",
                "published_at": None,
                "content": "Slaughtering hygiene, carcass dressing and meat cutting lines " * 8,
            },
            "https://forestry.extension.wisc.edu/tree-identification": {
                "title": "Tree Identification – Forestry & Wildlife",
                "publisher": "UW Extension",
                "published_at": None,
                "content": "Identify a tree by bark, needles, leaves and winter twigs " * 8,
            },
        }
        llm = FakeLLM(
            {
                "coursebook.plan.generate": plan_from_fixture(),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(
            self.connection,
            plan_job(),
            llm,
            FakeSearch(pages),
            now=NOW,
            research_budget=research.ResearchBudget(
                max_queries=1, max_results_per_query=3, max_pages=3, max_sources=3
            ),
        )
        self.assertEqual(result["status"], "draft")

        document = json.loads(
            self.rows(
                "SELECT document_json FROM gen_plan_documents WHERE plan_id = ?",
                (result["plan_id"],),
            )[0]["document_json"]
        )
        plan = document["plan"]
        cited = {
            str(sid)
            for objective in plan["objectives"]
            for sid in objective.get("source_ids") or []
        }
        self.assertTrue(cited, "the fixture plan must cite the admitted source")

        sources = self.rows("SELECT id, url, claim_count FROM sources")
        by_id = {str(row["id"]): row for row in sources}
        self.assertEqual({by_id[sid]["url"] for sid in cited}, {on_topic_url})
        self.assertEqual(
            {str(row["url"]) for row in sources},
            {on_topic_url},
            "an off-topic page must not become a ledger row",
        )
        self.assertTrue(all(int(by_id[sid]["claim_count"]) >= 1 for sid in cited))

        runs = self.rows("SELECT dropped_json, sources_json FROM gen_research_runs")
        self.assertEqual(len(runs), 1)
        dropped = json.loads(runs[0]["dropped_json"])
        self.assertEqual(
            sorted(entry["url"] for entry in dropped),
            sorted([url for url in pages if url != on_topic_url]),
        )
        self.assertTrue(all(entry["query"] and entry["reason"] for entry in dropped))


if __name__ == "__main__":
    unittest.main()
