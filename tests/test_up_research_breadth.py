"""Upgrade 33 — a deep pass spends its cell on breadth, not on the optional tail.

At HEAD the six deep-tail questions were appended after the clause block and the budget cell
truncated the list at the end. A five-clause goal at ``full``/``deep`` (a 12-query cell) spent
1 base + 5 clause + 2 sequencing + 1 qualifier = 9 slots, so only three of the six breadth
questions survived — and those three were the *least* useful ones: ``reference documentation``,
``official guidance`` and ``common mistakes``. The worked-examples, step-by-step and glossary
questions the depth dial promises were cut, so the plan then invented practice and sequencing
the ledger never covered.

The repair is an ordering decision, not a wider cell: the breadth questions are asked in
usefulness order, ahead of the optional reference/glossary tail, so truncation can only drop
the tail. Capability clauses keep their goal order and stay first — a breadth question never
displaces a capability, either in the query list or in stratified page selection — and the run
records how many breadth questions the cell still had to drop.

Evidence: ``tests/test_up_research_breadth.py::ResearchBreadthTest``.
"""

from __future__ import annotations

import unittest

from coursebook import research

#: Five capability clauses, the shape the defect report describes.
FIVE_CLAUSE_GOAL = (
    "Keep a starter alive and bake a reliable open-crumb loaf at home: "
    "build the levain, develop the dough, shape."
)
FIVE_CLAUSES = (
    "Keep a starter alive",
    "bake a reliable open-crumb loaf at home",
    "build the levain",
    "develop the dough",
    "shape",
)

#: Six clauses: one more than a 12-query cell can hold beside sequencing and the breadth core.
SIX_CLAUSE_GOAL = (
    "Keep a starter alive and bake a reliable open-crumb sourdough loaf at home: "
    "build the levain, develop the dough, shape, and bake with steam."
)


class _NoResultSearch:
    """A seam that answers every query with zero results, so the pass stays fully visible."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        return []

    def fetch(self, url: str, max_chars: int) -> dict:  # pragma: no cover - nothing is fetched
        raise AssertionError(f"no candidate should be fetched, got {url}")


def _deep(goal: str, *, max_queries: int = 12, **kwargs) -> list[str]:
    return research.derive_queries(
        goal,
        recipe=kwargs.pop("recipe", "casual"),
        dials={"depth": "deep"},
        max_queries=max_queries,
        **kwargs,
    )


class ResearchBreadthTest(unittest.TestCase):
    """Breadth survives a clause-rich deep goal without displacing a capability."""

    def test_five_clause_goal_keeps_breadth_questions(self) -> None:
        queries = _deep(FIVE_CLAUSE_GOAL)
        self.assertLessEqual(len(queries), 12)
        # A unique phrase per question, never a count: the assertion has to name the query
        # the learner's depth dial promised, not merely observe that "some" tail survived.
        self.assertTrue(
            any(query.endswith(" common mistakes") for query in queries),
            f"the common-mistakes breadth question was truncated away: {queries}",
        )
        self.assertTrue(
            any(query.endswith(" examples and practice") for query in queries),
            f"the worked-examples breadth question was truncated away: {queries}",
        )

    def test_capability_queries_keep_goal_order_and_are_not_displaced(self) -> None:
        queries = _deep(FIVE_CLAUSE_GOAL)
        self.assertEqual(queries[0], FIVE_CLAUSE_GOAL, "the goal itself is still the first query")
        for offset, clause in enumerate(FIVE_CLAUSES):
            self.assertIn(clause, queries, f"capability clause {clause!r} was displaced: {queries}")
            self.assertEqual(
                queries.index(clause),
                1 + offset,
                f"capabilities must keep goal order, {clause!r} moved: {queries}",
            )
        last_capability = queries.index(FIVE_CLAUSES[-1])
        for marker in (" common mistakes", " examples and practice"):
            breadth_index = next(
                index for index, query in enumerate(queries) if query.endswith(marker)
            )
            self.assertGreater(
                breadth_index,
                last_capability,
                f"breadth question {marker.strip()!r} is fetched before a capability: {queries}",
            )

    def test_stratified_selection_never_fetches_breadth_before_a_capability(self) -> None:
        """The ordered-list proof: one page per query, in the goal's own order."""
        queries = _deep(FIVE_CLAUSE_GOAL)
        candidates = [
            {
                "url": f"https://example.org/{index}",
                "title": query,
                "query": query,
                "query_index": index,
                "position": 0,
            }
            for index, query in enumerate(queries)
        ]
        ordered = research._stratified_candidates(candidates, len(queries))
        capability_indices = set(range(len(FIVE_CLAUSES) + 1))  # base goal query + five clauses
        seen_breadth = False
        for candidate in ordered:
            if candidate["query_index"] in capability_indices:
                self.assertFalse(
                    seen_breadth,
                    "a breadth page was selected before the capability pages were reached",
                )
            else:
                seen_breadth = True
        self.assertEqual(
            [candidate["query_index"] for candidate in ordered[: len(FIVE_CLAUSES) + 1]],
            list(range(len(FIVE_CLAUSES) + 1)),
            "stratified selection must ask every capability before it deepens any question",
        )

    def test_a_binding_cell_records_the_breadth_it_dropped(self) -> None:
        budget = research.budget_for("deep", "full")
        run = research.run_research(
            FIVE_CLAUSE_GOAL,
            recipe="casual",
            dials={"depth": "deep"},
            scope="full",
            search=_NoResultSearch(),
            budget=budget,
        )
        # 6 breadth questions requested, 3 slots left after 1 base + 5 clauses + 2 sequencing
        # + 1 qualifier: reference documentation, official guidance and glossary wait.
        self.assertEqual(
            len(run.queries),
            budget.max_queries,
            f"the pass should have spent the whole cell: {[q['query'] for q in run.queries]}",
        )
        self.assertEqual(run.queries_breadth_dropped, 3)
        self.assertEqual(run.to_dict()["queries_breadth_dropped"], 3)

    def test_a_deep_goal_with_room_drops_no_breadth(self) -> None:
        run = research.run_research(
            "Learn to prune a fruit tree",
            recipe="casual",
            dials={"depth": "deep"},
            scope="full",
            search=_NoResultSearch(),
            budget=research.budget_for("deep", "full"),
        )
        self.assertEqual(run.queries_breadth_dropped, 0)

    def test_one_off_deep_query_set_is_byte_identical(self) -> None:
        """A one-off brief's breadth order is unchanged; the repair is for courses."""
        expected = [
            FIVE_CLAUSE_GOAL,
            f"{FIVE_CLAUSE_GOAL} official instructions safety",
            f"{FIVE_CLAUSE_GOAL} reference documentation",
            f"{FIVE_CLAUSE_GOAL} official guidance",
            f"{FIVE_CLAUSE_GOAL} common mistakes",
            f"{FIVE_CLAUSE_GOAL} examples and practice",
            f"{FIVE_CLAUSE_GOAL} step by step",
            f"{FIVE_CLAUSE_GOAL} glossary",
        ]
        self.assertEqual(_deep(FIVE_CLAUSE_GOAL, recipe="one_off"), expected)

    def test_single_survey_query_set_is_byte_identical(self) -> None:
        """A survey pass stays the goal itself, whatever the recipe."""
        self.assertEqual(
            research.derive_queries(
                "order coffee", recipe="committed", dials={"depth": "survey"}, max_queries=2
            ),
            ["order coffee"],
        )
        self.assertEqual(
            research.derive_queries(
                FIVE_CLAUSE_GOAL, recipe="casual", dials={"depth": "survey"}, max_queries=2
            ),
            [FIVE_CLAUSE_GOAL],
        )


if __name__ == "__main__":
    unittest.main()
