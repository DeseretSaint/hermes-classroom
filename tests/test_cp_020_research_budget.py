"""GEN-6: a multi-capability goal still researches what to learn first.

The audit's defect: curriculum and prerequisite queries were appended after the capability
clauses and the base qualifier, so at the default ``short``/``working`` cell (six queries) a
goal naming several capabilities spent every slot on the acts themselves. The learner got
sources about replacing a head gasket and re-torquing the bolts and nothing about what to
learn before either.

``research.derive_queries`` now allocates the cell before it builds the list: one slot is
held for the curriculum-sequence question once the cell is past the four-query floor, and the
capability block spends only the slots that remain. These tests pin that from the outside —
the final query set is what the research pass actually runs.
"""

from __future__ import annotations

import unittest

from coursebook import research

#: Four capabilities, the shape the audit reported: several acts and no sequence.
GASKET_GOAL = (
    "replace a head gasket, resurface the head, check the valve clearance, "
    "and re-torque the head bolts"
)
#: Two capabilities: the goal in the defect report.
TWO_STEP_GOAL = "replace a head gasket and re-torque the head bolts"
#: Six clauses: more capabilities than a six-query cell can hold.
SOURDOUGH_GOAL = (
    "Keep a starter alive and bake a reliable open-crumb sourdough loaf at home: "
    "build the levain, develop the dough, shape, and bake with steam."
)
SEQUENCING_MARKERS = ("curriculum sequence", "prerequisite knowledge")


def _is_sequencing(query: str) -> bool:
    return any(marker in query for marker in SEQUENCING_MARKERS)


def _queries(goal: str, *, scope: str = "short", depth: str = "working", **kwargs) -> list[str]:
    budget = research.budget_for(depth, scope)
    return research.derive_queries(
        goal,
        recipe=kwargs.pop("recipe", "casual"),
        dials={"depth": depth},
        max_queries=budget.max_queries,
        **kwargs,
    )


class SequencingSurvivesTheDefaultCellTest(unittest.TestCase):
    """The default short/working cell keeps a sequencing question for a multi-act goal."""

    def test_a_multi_capability_goal_keeps_a_sequencing_query(self) -> None:
        budget = research.budget_for("working", "short")
        self.assertEqual(budget.max_queries, 6, "the default cell is short/working = 6")

        queries = _queries(GASKET_GOAL)
        sequencing = [query for query in queries if _is_sequencing(query)]

        self.assertTrue(
            sequencing,
            f"at short/working a four-capability goal must still ask how the subject is "
            f"sequenced; got {queries}",
        )
        self.assertIn("how to teach curriculum sequence", sequencing[0])
        # The capability block is not traded away wholesale for the sequence.
        self.assertIn("replace a head gasket", queries)
        self.assertIn("re-torque the head bolts", queries)

    def test_the_prerequisite_question_survives_when_the_cell_has_room(self) -> None:
        queries = _queries(TWO_STEP_GOAL)
        joined = " | ".join(queries)
        self.assertIn("how to teach curriculum sequence", joined)
        self.assertIn("prerequisite knowledge learning progression", joined)

    def test_a_narrow_single_cell_trades_the_qualifier_for_the_sequence(self) -> None:
        # single/working is four queries: base, two acts, and the sequence. The generic
        # qualifier is what waits.
        queries = _queries(TWO_STEP_GOAL, scope="single")
        self.assertEqual(len(queries), 4)
        self.assertTrue([query for query in queries if _is_sequencing(query)], queries)
        self.assertFalse(
            [query for query in queries if "official procedure steps safety limits" in query],
            f"a four-query cell cannot hold both; the generic qualifier waits: {queries}",
        )

    def test_the_sequence_is_admitted_before_the_generic_qualifier(self) -> None:
        # Six clauses already exceed the cell, so something must give. The sequence wins the
        # last slot; the generic base qualifier is what waits.
        queries = _queries(SOURDOUGH_GOAL)
        sequencing = [query for query in queries if _is_sequencing(query)]
        self.assertTrue(sequencing, queries)
        sequence_index = queries.index(sequencing[0])
        for index, query in enumerate(queries):
            if "official procedure steps safety limits" in query or query.endswith(
                "beginner guide"
            ):
                self.assertGreater(
                    index,
                    sequence_index,
                    f"the generic qualifier {query!r} is admitted before the sequence: {queries}",
                )


class TheBudgetIsStillTheCeilingTest(unittest.TestCase):
    """GEN-6 reserves slots inside the cell; it never widens the cell."""

    def test_no_cell_is_exceeded_across_goals_and_scopes(self) -> None:
        goals = (GASKET_GOAL, TWO_STEP_GOAL, SOURDOUGH_GOAL, "Learn to prune a fruit tree")
        for goal in goals:
            for scope in ("single", "short", "full"):
                for depth in ("survey", "working", "deep"):
                    with self.subTest(goal=goal[:24], scope=scope, depth=depth):
                        budget = research.budget_for(depth, scope)
                        queries = research.derive_queries(
                            goal,
                            recipe="casual",
                            dials={"depth": depth},
                            max_queries=budget.max_queries,
                            subject_domain="technical_procedure",
                        )
                        self.assertLessEqual(
                            len(queries),
                            budget.max_queries,
                            f"{scope}/{depth} exceeded: {queries}",
                        )
                        self.assertEqual(
                            len(queries), len({query.casefold() for query in queries})
                        )

    def test_a_declared_domain_still_joins_each_capability_clause(self) -> None:
        queries = _queries(GASKET_GOAL, subject_domain="technical_procedure")
        self.assertIn("replace a head gasket official procedure steps safety limits", queries)
        self.assertTrue([query for query in queries if _is_sequencing(query)], queries)

    def test_the_deliberate_exceptions_are_unchanged(self) -> None:
        # A survey pass stays one query and a one-off brief buys no curriculum pass.
        self.assertEqual(_queries(GASKET_GOAL, depth="survey"), [GASKET_GOAL])
        one_off = _queries(GASKET_GOAL, recipe="one_off")
        self.assertEqual(one_off[0], GASKET_GOAL)
        self.assertFalse([query for query in one_off if _is_sequencing(query)], one_off)


class _RecordingSearch:
    """A search seam that returns one fetchable page per query."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        return [
            {
                "url": f"https://reference.example/{len(self.queries)}/{index}",
                "title": f"{query} {index}",
                "description": "snippet",
            }
            for index in range(min(limit, 2))
        ]

    def fetch(self, url: str, max_chars: int) -> dict:
        return {"url": url, "title": url, "content": "A sentence about the subject. " * 20}


class TheRecordedPassCarriesTheSequenceTest(unittest.TestCase):
    """The ledger the planner reads contains the sequencing query, not just the deriver."""

    def test_run_research_records_a_sequencing_query_at_short_working(self) -> None:
        seam = _RecordingSearch()
        run = research.run_research(
            GASKET_GOAL,
            recipe="casual",
            dials={"depth": "working"},
            scope="short",
            search=seam,
        )
        self.assertEqual(run.status, "ok", run.reason)
        recorded = [str(entry.get("query") or "") for entry in run.queries]
        self.assertEqual(recorded, seam.queries, "the recorded ledger is what was searched")
        self.assertTrue(
            [query for query in recorded if _is_sequencing(query)],
            f"the research ledger has no sequencing question: {recorded}",
        )
        self.assertLessEqual(len(recorded), research.budget_for("working", "short").max_queries)


if __name__ == "__main__":
    unittest.main()
