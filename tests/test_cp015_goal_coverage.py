"""CP-015a: the goal-coverage rule, as code.

Four distinct defects produced the three rejected Sourdough plans, and none of them is a prompt
line:

* research derived every query from the goal *string*, so a goal naming five capabilities searched
  one of them;
* selection ranked the whole candidate pool by publisher type, so query 0 could spend the page
  budget and the later queries were never fetched even when they ran;
* the excerpt cut landed mid-sentence, so a page that did state a fact could not carry it;
* and the goal-coverage criterion demanded the raw goal sentence as a deliverable promise, which a
  bounded ledger can never satisfy.

These tests pin the repairs: clause-derived queries (R-1a), stratified selection (R-1b),
sentence-bounded excerpts (R-3), the deterministic outcome-integrity gate (c1) and the registered
disclosure criterion (c2).
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from coursebook import research

from tests import blueprint_support

SOURDOUGH_GOAL = (
    "Keep a starter alive and bake a reliable open-crumb sourdough loaf at home: "
    "build the levain, develop the dough, shape, and bake with steam."
)

#: The capability clauses the goal names, in the goal's own order. The goal above has no comma
#: inside a clause, so the split is unambiguous; the head sentence contributes its two halves.
SOURDOUGH_CLAUSES = (
    "Keep a starter alive",
    "bake a reliable open-crumb sourdough loaf at home",
    "build the levain",
    "develop the dough",
    "shape",
    "bake with steam",
)


class ClauseDerivedQueryTest(unittest.TestCase):
    """R-1a: one query per capability the goal names, before the generic depth tail."""

    def _queries(self, **kwargs) -> list[str]:
        dials = {"depth": kwargs.pop("depth", "deep")}
        return research.derive_queries(
            SOURDOUGH_GOAL,
            recipe=kwargs.pop("recipe", "casual"),
            dials=dials,
            max_queries=kwargs.pop("max_queries", 12),
            **kwargs,
        )

    def test_one_query_per_capability_clause_in_goal_order(self) -> None:
        queries = self._queries()
        self.assertEqual(queries[0], SOURDOUGH_GOAL, "the goal itself is still the first query")
        for offset, clause in enumerate(SOURDOUGH_CLAUSES):
            self.assertIn(
                clause,
                queries,
                f"capability clause {clause!r} has no query: {queries}",
            )
            position = queries.index(clause)
            self.assertEqual(
                position,
                1 + offset,
                f"clauses must keep goal order, {clause!r} landed at {position}: {queries}",
            )

    def test_clause_queries_precede_the_generic_depth_tail(self) -> None:
        queries = self._queries()
        last_clause = queries.index("bake with steam")
        for generic in queries:
            if "reference documentation" in generic or "glossary" in generic:
                self.assertGreater(
                    queries.index(generic),
                    last_clause,
                    f"generic query {generic!r} would be fetched before a capability",
                )
        # The generic tail is still present at a deep budget: the reach was added, not traded.
        self.assertTrue(any("reference documentation" in query for query in queries))

    def test_a_small_cap_drops_the_generic_tail_not_a_capability(self) -> None:
        queries = self._queries(max_queries=4)
        self.assertEqual(len(queries), 4)
        self.assertEqual(
            queries,
            [SOURDOUGH_GOAL] + list(SOURDOUGH_CLAUSES[:3]),
            f"a bounded cell must truncate the generic tail first: {queries}",
        )

    def test_declared_domain_qualifier_joins_each_clause(self) -> None:
        queries = self._queries(subject_domain="technical_procedure", max_queries=12)
        self.assertIn("shape official procedure steps safety limits", queries)
        self.assertNotIn("shape", queries)

    def test_survey_and_one_off_keep_their_bounded_sets(self) -> None:
        self.assertEqual(self._queries(depth="survey"), [SOURDOUGH_GOAL])
        one_off = self._queries(recipe="one_off", depth="working")
        self.assertEqual(one_off[0], SOURDOUGH_GOAL)
        self.assertNotIn("shape", one_off)
        self.assertTrue(one_off[1].endswith("official instructions safety"))

    def test_a_goal_without_clause_boundaries_adds_nothing(self) -> None:
        queries = research.derive_queries(
            "Learn to prune a fruit tree",
            recipe="casual",
            dials={"depth": "working"},
            max_queries=6,
        )
        self.assertEqual(queries[0], "Learn to prune a fruit tree")
        self.assertEqual(len(queries), len(set(queries)), "duplicates must not survive the cap")


class _PerQuerySearch:
    """A search seam whose results differ per query and whose every page is fetchable."""

    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        self.queries: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        count = self.counts.get(query, 1)
        return [
            {
                "url": f"https://reference.example/{len(self.queries)}/{index}",
                "title": f"{query} {index}",
                "description": "snippet",
            }
            for index in range(min(count, limit))
        ]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        return {"url": url, "title": url, "content": "A sentence about sourdough. " * 20}


class StratifiedSelectionTest(unittest.TestCase):
    """R-1b: one page per query before a second from any query, same ceilings."""

    def test_one_page_per_query_before_a_second_from_any_query(self) -> None:
        candidates = []
        # Query 0 returns four reference pages, query 1 two, query 2 one — the old global sort
        # would have taken all four of query 0's pages first and never reached query 2.
        for query_index, urls in enumerate(
            (
                [f"https://reference.example/0/{i}" for i in range(4)],
                [f"https://web.example/1/{i}" for i in range(2)],
                ["https://archive.example/2/0"],
            )
        ):
            for position, url in enumerate(urls):
                candidates.append(
                    {
                        "url": url,
                        "title": url,
                        "query": f"q{query_index}",
                        "query_index": query_index,
                        "position": position,
                    }
                )
        ordered = research._stratified_candidates(candidates, 4)
        self.assertEqual(
            [item["query_index"] for item in ordered],
            [0, 1, 2, 0],
            "first pass must take query 0, 1, 2 once each before query 0's second page",
        )

    def test_publisher_rank_still_orders_within_one_query(self) -> None:
        candidates = [
            {"url": "https://blog.example/x", "title": "", "query": "q", "query_index": 0, "position": 0},
            {"url": "https://nasa.gov/x", "title": "", "query": "q", "query_index": 0, "position": 1},
            {"url": "https://other.example/x", "title": "", "query": "q", "query_index": 1, "position": 0},
        ]
        ordered = research._stratified_candidates(candidates, 2)
        self.assertEqual(
            [item["url"] for item in ordered],
            ["https://nasa.gov/x", "https://other.example/x"],
            "a government host still wins inside its own query, and query 1 still gets a page",
        )

    def test_the_later_query_is_actually_fetched(self) -> None:
        search = _PerQuerySearch({SOURDOUGH_GOAL: 5})
        budget = research.ResearchBudget(
            max_queries=4, max_results_per_query=5, max_pages=4, max_sources=4
        )
        run = research.run_research(
            SOURDOUGH_GOAL,
            recipe="casual",
            dials={"depth": "deep"},
            search=search,
            budget=budget,
        )
        self.assertEqual(run.status, "ok")
        self.assertEqual(len(search.queries), 4)
        used = {source.query for source in run.sources}
        self.assertIn(
            search.queries[1],
            used,
            "the second query's page must be fetched even though query 0 had five results",
        )


class SentenceBoundedExcerptTest(unittest.TestCase):
    """R-3: the window ends on a sentence boundary and never exceeds the ceiling."""

    def test_window_ends_on_a_sentence_boundary(self) -> None:
        page = "A sourdough starter is alive. Feed it daily. Mark the height after feeding to see it double. " * 30
        limit = research._MAX_EXCERPT
        text = research._excerpt(page, limit)
        self.assertLessEqual(len(text), limit)
        self.assertTrue(text.endswith("."), text[-80:])
        self.assertTrue(
            text.endswith((". ", "!", "?", ".")) or text[-1] in ".!?",
            "an excerpt must close on terminal punctuation, not inside a word",
        )

    def test_window_is_bounded_and_never_pads(self) -> None:
        # The contract change: this assertion used to require exactly 300 characters. A
        # sentence-bounded window can only be shorter, so the bound is now a ceiling.
        bounded = research._excerpt("prose " * 2000, 300)
        self.assertLessEqual(len(bounded), 300)
        sentence_page = "This is one sentence of several. " * 100
        sentence_bounded = research._excerpt(sentence_page, 300)
        self.assertLessEqual(len(sentence_bounded), 300)
        self.assertTrue(sentence_bounded.endswith("."), sentence_bounded[-40:])

    def test_no_boundary_before_the_ceiling_still_yields_the_plain_cut(self) -> None:
        text = research._excerpt("word " * 400, 100)
        self.assertEqual(len(text), 100)


#: The three stored Sourdough plans' contradiction, reconstructed from their recorded verdicts
#: (``docs/concept-parity/demo/cp015-run.json``): the plan promised a baked open-crumb loaf while
#: its own exclusions removed levain, dough development, shaping, steam and open crumb. The demo
#: backend's home was disposable, so the rows themselves are gone; the verdict text is verbatim and
#: three independent validators read the same promise and the same exclusions.
SOURDOUGH_OUTCOME = (
    "Keep a sourdough starter alive and active at home, then bake a reliable open-crumb sourdough "
    "loaf: build the levain, develop the dough, shape it, and bake with steam."
)
SOURDOUGH_EXCLUSIONS = [
    "Not covered — no supporting source: levain",
    "Not covered — no supporting source: dough development",
    "Not covered — no supporting source: shaping",
    "Not covered — no supporting source: steam baking",
    "Not covered — no supporting source: open crumb",
]
#: The same plan with the outcome narrowed to what the ledger actually supports.
SOURDOUGH_NARROWED_OUTCOME = (
    "Keep a sourdough starter alive and active at home, and tell when it is ready to bake with."
)


def _sourdough_plan(outcome: str) -> dict:
    plan = blueprint_support.blueprint_plan(scope="single", units=1, objectives_per_unit=1)
    plan["learner_outcome"] = outcome
    plan["exclusions"] = list(SOURDOUGH_EXCLUSIONS)
    return plan


def _rules(plan: dict) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe="casual",
        dials={},
        locale=None,
        ledger=[],
        scope="single",
    )


class OutcomeIntegrityTest(unittest.TestCase):
    """c1: a plan must not promise a capability its own exclusions remove."""

    def test_the_excluded_capabilities_are_read_from_the_prefix(self) -> None:
        plan = _sourdough_plan(SOURDOUGH_OUTCOME)
        self.assertEqual(
            gen.excluded_capabilities(plan),
            [
                "levain",
                "dough development",
                "shaping",
                "steam baking",
                "open crumb",
            ],
        )

    def test_an_unprefixed_exclusion_records_no_capability(self) -> None:
        plan = _sourdough_plan(SOURDOUGH_NARROWED_OUTCOME)
        plan["exclusions"] = ["No graded exam is scheduled", "Nothing beyond the outcome is claimed"]
        self.assertEqual(gen.excluded_capabilities(plan), [])

    def test_the_sourdough_plan_is_refused_by_the_rule_gate(self) -> None:
        plan = _sourdough_plan(SOURDOUGH_OUTCOME)
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan)
        reasons = "\n".join(caught.exception.reasons)
        for phrase in ("levain", "dough development", "shaping", "steam", "open crumb"):
            self.assertIn(phrase, reasons)
        self.assertIn("outcome integrity", reasons)

    def test_the_narrowed_plan_passes_the_same_gate(self) -> None:
        plan = _sourdough_plan(SOURDOUGH_NARROWED_OUTCOME)
        _rules(plan)

    def test_an_objective_title_or_evidence_target_may_not_promise_it_either(self) -> None:
        plan = _sourdough_plan(SOURDOUGH_NARROWED_OUTCOME)
        plan["objectives"][0]["title"] = "Shape a loaf so the crumb opens"
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan)
        self.assertTrue(any("in its title" in reason for reason in caught.exception.reasons))

        plan = _sourdough_plan(SOURDOUGH_NARROWED_OUTCOME)
        plan["objectives"][0]["evidence_criteria"] = ["Shows shaping without support"]
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan)
        self.assertTrue(any("evidence target" in reason for reason in caught.exception.reasons))

    def test_the_prompt_no_longer_asks_for_the_contradiction(self) -> None:
        rules = " ".join(gen._plan_sourcing_rules())
        self.assertNotIn(
            "say so in learner_outcome as well as in exclusions",
            rules,
            "the authoring rule must not ask for a capability the gate refuses",
        )
        self.assertIn("Not covered — no supporting source:", rules)
        self.assertIn("Do not name the excluded capability in learner_outcome", rules)


class DisclosureCriterionTest(unittest.TestCase):
    """c2: the completeness criterion is registered, rubricated and its pass split stays legal."""

    def test_the_criterion_is_registered_beside_objective_alignment(self) -> None:
        self.assertIn("goal_capability_disclosure", gen.VALIDATION_CRITERIA)
        self.assertIn("objective_alignment", gen.VALIDATION_CRITERIA)
        index = gen.VALIDATION_CRITERIA.index("objective_alignment")
        self.assertEqual(gen.VALIDATION_CRITERIA[index + 1], "goal_capability_disclosure")

    def test_every_criterion_is_owned_by_exactly_one_pass(self) -> None:
        owned = [name for batch in gen.VALIDATION_CRITERIA_PASSES for name in batch]
        self.assertEqual(tuple(owned), gen.VALIDATION_CRITERIA)
        self.assertEqual(len(owned), len(set(owned)))
        for batch in gen.VALIDATION_CRITERIA_PASSES:
            self.assertLessEqual(len(batch), 6, "a pass must answer a bounded set of criteria")

    def test_the_pass_that_owns_it_states_the_rubric(self) -> None:
        owning = next(
            batch for batch in gen.VALIDATION_CRITERIA_PASSES if "goal_capability_disclosure" in batch
        )
        text = gen.validation_pass_instructions(subject="plan", criteria=owning)
        self.assertIn("goal_capability_disclosure", text)
        self.assertIn("appears in neither is a reject", text)
        self.assertIn("disclosed, not covered", text)

    def test_a_lesson_validation_is_not_asked_for_a_plan_level_verdict(self) -> None:
        self.assertNotIn("goal_capability_disclosure", gen.LESSON_VALIDATION_CRITERIA)
        self.assertEqual(
            set(gen.LESSON_VALIDATION_CRITERIA),
            set(gen.VALIDATION_CRITERIA) - {"goal_capability_disclosure"},
        )

    def test_a_report_missing_it_is_malformed_not_a_pass(self) -> None:
        report = {
            "verdict": "pass",
            "criteria": [
                {"id": criterion, "verdict": "pass", "reason": "checked"}
                for criterion in gen.VALIDATION_CRITERIA
                if criterion != "goal_capability_disclosure"
            ],
            "rejections": [],
        }
        with self.assertRaises(gen.GenerationRejected) as caught:
            gen.validation_verdict(report, research_status="ok")
        self.assertIn("goal_capability_disclosure", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
