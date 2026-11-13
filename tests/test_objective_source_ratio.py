"""E2E S5/S6 — the objective floor follows the ledger and the ceiling follows the research cell.

Two defects, one contract:

* **S5** — the ``full`` floor was a bare count (12). A ledger that supported five capabilities was
  manufactured into twelve objectives by relabelling one capability three times ("recognise the
  parts" → "identify the parts with support" → "name the parts"), because the duplicate rule only
  refused objectives with an identical quote + target + criteria. The floor is now the ledger's
  distinct capability count when that is smaller than the band, and a plan short of the band must
  disclose the shortfall in ``exclusions``.
* **S6** — ``_BUDGET_MATRIX`` gave ``full``/``deep`` 16 sources against a 40-objective ceiling,
  so most of a full course could never be ``sourced``. The ceiling is now the research cell's
  (``max_sources × OBJECTIVES_PER_SOURCE``) and the ``full``/``deep`` cell carries the 20 sources
  the band's own ceiling needs.

Every case runs the same rule gate the pipeline runs, against a hand-built ledger — no provider is
called and no fixture is copied from a model.
"""

from __future__ import annotations

import json
import unittest

from coursebook import generation as gen
from coursebook import research

from tests.blueprint_support import blueprint_plan

#: Five capabilities, five sentences, plus one duplicate copy. The copy is deliberate: two pages
#: printing the same paragraph carry one capability, and the count must know that.
FIVE_CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("src_plate", "A printed circuit board holds the parts and the copper paths between them."),
    ("src_iron", "A soldering iron reaches about 350 degrees Celsius for a small joint."),
    ("src_tin", "Fresh solder wets a clean pad and flows toward the heat."),
    ("src_flux", "Flux removes the oxide that stops solder from wetting a pad."),
    ("src_joint", "A good joint is shiny, concave and pulls the part tight to the board."),
)
DUPLICATE_COPY = ("src_mirror", FIVE_CAPABILITIES[0][1])


def _ledger(*rows: tuple[str, str]) -> list[research.SourceRecord]:
    return [
        research.SourceRecord(
            source_id=source_id,
            url=f"https://example.invalid/{source_id}",
            title=f"Source {source_id}",
            publisher="Example Press",
            source_type="web_page",
            fetched_at="2026-11-12T12:00:00Z",
            published_at=None,
            content_hash=f"sha256:{index:064d}",
            excerpt=excerpt,
        )
        for index, (source_id, excerpt) in enumerate(rows)
    ]


def _shape(plan: dict, per_unit: list[int]) -> dict:
    """Trim a blueprint fixture to ``per_unit`` objectives per unit, renumbering contiguously.

    ``blueprint_support.blueprint_plan`` authors one objective count for every unit; a full plan
    whose units differ (3 + 2, or 5 × 5) has to be reshaped so every ordinal, check reference and
    ``target_lessons`` stays honest. Nothing here relaxes a rule: the result is a document the
    gate still reads in full.
    """
    kept: list[dict] = []
    for unit_ordinal, count in enumerate(per_unit, start=1):
        rows = [obj for obj in plan["objectives"] if int(obj["unit_ref"]) == unit_ordinal]
        kept.extend(rows[:count])
    originals = [int(obj["ordinal"]) for obj in kept]
    for ordinal, objective in enumerate(kept, start=1):
        objective["ordinal"] = ordinal
    by_ref = {int(check["objective_ref"]): check for check in plan["check_plan"]}
    plan["check_plan"] = []
    for ordinal, original in enumerate(originals, start=1):
        check = dict(by_ref[original])
        check["objective_ref"] = ordinal
        plan["check_plan"].append(check)
    plan["objectives"] = kept
    plan["units"] = plan["units"][: len(per_unit)]
    for unit, count in zip(plan["units"], per_unit):
        unit["target_lessons"] = count
    return plan


def _sourced(plan: dict, rows: list[tuple[str, str]]) -> dict:
    """Mark objective *i* sourced from row *i*, copying that row's sentence verbatim."""
    for objective, (source_id, excerpt) in zip(plan["objectives"], rows):
        objective["support"] = "sourced"
        objective["source_ids"] = [source_id]
        objective["source_quote"] = excerpt
    return plan


def _disclose(plan: dict) -> dict:
    plan["exclusions"].append(
        f"{gen.SHORTFALL_PREFIX} the ledger supports five capabilities (board, iron, solder, "
        "flux, joint) and this course carries five objectives against a 12-to-40 band"
    )
    return plan


def _rules(plan: dict, ledger: list[research.SourceRecord], scope: str, dials: dict | None = None):
    gen.enforce_plan_rules(
        plan,
        recipe="casual",
        dials=dict(dials or {}),
        locale=None,
        ledger=ledger,
        scope=scope,
    )


class LedgerCapabilityCountTest(unittest.TestCase):
    def test_a_duplicated_page_is_one_capability_not_two(self) -> None:
        ledger = _ledger(*FIVE_CAPABILITIES, DUPLICATE_COPY)
        self.assertEqual(len(ledger), 6)
        self.assertEqual(gen._ledger_capability_count(ledger), 5)

    def test_a_page_without_quotable_text_carries_no_capability(self) -> None:
        ledger = _ledger(*FIVE_CAPABILITIES)
        ledger.append(
            research.SourceRecord(
                source_id="src_empty",
                url="https://example.invalid/empty",
                title="Source with no body",
                publisher="Example Press",
                source_type="web_page",
                fetched_at="2026-11-12T12:00:00Z",
                published_at=None,
                content_hash="sha256:1",
                excerpt="",
            )
        )
        self.assertEqual(ledger[-1].excerpt_state, "no_body")
        self.assertEqual(gen._ledger_capability_count(ledger), 5)

    def test_an_empty_ledger_carries_none(self) -> None:
        self.assertEqual(gen._ledger_capability_count([]), 0)


class FullFloorFollowsTheLedgerTest(unittest.TestCase):
    """S5 acceptance: five sourced capabilities and five objectives is a legal full plan."""

    def _plan(self) -> dict:
        plan = _shape(blueprint_plan(scope="full", units=2, objectives_per_unit=3), [3, 2])
        return _disclose(_sourced(plan, list(FIVE_CAPABILITIES)))

    def test_five_capabilities_and_five_objectives_are_accepted(self) -> None:
        ledger = _ledger(*FIVE_CAPABILITIES, DUPLICATE_COPY)
        plan = self._plan()
        _rules(plan, ledger, "full")  # the disclosure is present, so nothing is refused
        self.assertEqual(len(plan["objectives"]), 5)
        self.assertTrue(gen.scope_shortfall_disclosed(plan))
        expectation = gen.SCOPE_EXPECTATIONS["full"]
        floor, ceiling = gen._scope_objective_band(
            {**expectation, "scope": "full"}, ledger
        )
        self.assertEqual((floor, ceiling), (5, 40))

    def test_the_same_plan_without_the_disclosure_is_refused(self) -> None:
        ledger = _ledger(*FIVE_CAPABILITIES)
        plan = self._plan()
        plan["exclusions"] = ["Nothing beyond the stated learner outcome is claimed"]
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger, "full")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn(gen.SHORTFALL_PREFIX, reasons)
        self.assertIn("5 distinct capabilities", reasons)
        self.assertIn("disclosed, never padded", reasons)

    def test_a_ledger_that_supports_the_band_still_holds_the_band_floor(self) -> None:
        # Twelve distinct capabilities: the full band's floor applies, and a five-objective plan
        # is refused as an under-delivery rather than excused as a shortfall.
        rows = tuple(
            (f"src_{index:02d}", f"Capability {index} is a distinct printed statement about joints.")
            for index in range(12)
        )
        ledger = _ledger(*rows)
        plan = self._plan()
        _disclose(plan)
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger, "full")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("so the floor applies", reasons)
        self.assertNotIn(gen.SHORTFALL_PREFIX, reasons)


class PaddingIsRefusedTest(unittest.TestCase):
    """S5's other half: the three-variant padding fixture is refused, not rewarded."""

    QUOTE = FIVE_CAPABILITIES[1][1]

    def _three_variants(self) -> dict:
        plan = _shape(blueprint_plan(scope="short", units=1, objectives_per_unit=3), [3])
        variants = (
            ("Recognise the parts of a soldering iron in a labelled picture", "comprehension",
             "names the tip, the heater and the stand from a labelled picture"),
            ("Identify the parts of a soldering iron with support", "comprehension",
             "points to the part named by the instructor, from a closed list"),
            ("Name the parts of a soldering iron", "recall",
             "names the three parts unaided from memory"),
        )
        for objective, (title, target, criterion) in zip(plan["objectives"], variants):
            objective.update(
                {
                    "title": title,
                    "evidence_target": target,
                    "evidence_criteria": [criterion],
                    "support": "sourced",
                    "source_ids": ["src_iron"],
                    "source_quote": self.QUOTE,
                }
            )
        plan["check_plan"][2]["evidence_target"] = "recall"
        plan["check_plan"][1]["evidence_target"] = "comprehension"
        return plan

    def test_three_titles_over_one_capability_are_refused(self) -> None:
        # Different titles, different evidence targets and different criteria: the duplicate rule
        # alone cannot see this, and that is exactly the defect. The split cap can.
        ledger = _ledger(("src_iron", self.QUOTE))
        plan = self._three_variants()
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger, "short")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("sourced objective 3 over one capability", reasons)
        self.assertIn("at most 2 ordered sub-performances", reasons)
        self.assertIn(gen.SHORTFALL_PREFIX, reasons)

    def test_two_performances_of_one_capability_are_still_legal(self) -> None:
        # A short plan whose ledger supports one capability may carry that capability twice —
        # recognise, then unaided — provided it discloses the band it falls short of.
        ledger = _ledger(("src_iron", self.QUOTE))
        plan = _shape(blueprint_plan(scope="short", units=1, objectives_per_unit=2), [2])
        for objective, (title, target, criterion) in zip(
            plan["objectives"],
            (
                ("Recognise the parts of a soldering iron in a labelled picture", "comprehension",
                 "names the tip, the heater and the stand from a labelled picture"),
                ("Name the parts of a soldering iron unaided", "recall",
                 "names the three parts from memory with no list"),
            ),
        ):
            objective.update(
                {
                    "title": title,
                    "evidence_target": target,
                    "evidence_criteria": [criterion],
                    "support": "sourced",
                    "source_ids": ["src_iron"],
                    "source_quote": self.QUOTE,
                }
            )
        plan["check_plan"][1]["evidence_target"] = "recall"
        plan["exclusions"].append(
            f"{gen.SHORTFALL_PREFIX} the ledger supports one capability and this course carries "
            "two objectives against a 3-to-6 band"
        )
        _rules(plan, ledger, "short")
        self.assertEqual(len(plan["objectives"]), 2)


class CeilingFollowsTheResearchCellTest(unittest.TestCase):
    """S6: objectives <= max_sources × OBJECTIVES_PER_SOURCE, for the cell actually used.

    With the shipped matrix every scope's effective cell now supports its band's own ceiling (the
    invariant test below holds that), so the ceiling is a guard rather than a narrowing. To show
    it really is the cell's number and not the band's, the pre-S6 cell (``full``/``deep`` = 16
    sources, 0.4 sources per objective) is reinstated for one case: the same plan is then refused.
    """

    def setUp(self) -> None:
        self._saved = {scope: dict(cells) for scope, cells in research._BUDGET_MATRIX.items()}
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        research._BUDGET_MATRIX.clear()
        research._BUDGET_MATRIX.update({scope: dict(cells) for scope, cells in self._saved.items()})

    def _set_sources(self, scope: str, depth: str, sources: int) -> None:
        cells = dict(research._BUDGET_MATRIX[scope])
        queries, results, pages, _ = cells[depth]
        cells[depth] = (queries, results, max(pages, sources), sources)
        research._BUDGET_MATRIX[scope] = cells

    def _ledger(self, count: int = 13) -> list[research.SourceRecord]:
        return _ledger(
            *(
                (f"src_{index:02d}", f"Capability {index} is a distinct printed statement about joints.")
                for index in range(count)
            )
        )

    def _plan(self, per_unit: list[int]) -> dict:
        return _shape(
            blueprint_plan(scope="full", units=len(per_unit), objectives_per_unit=max(per_unit)),
            per_unit,
        )

    def _sourced_prefix(self, plan: dict, ledger_size: int) -> dict:
        for index, objective in enumerate(plan["objectives"]):
            if index >= ledger_size:
                objective["support"] = "unverified"
                continue
            objective["support"] = "sourced"
            objective["source_ids"] = [f"src_{index:02d}"]
            objective["source_quote"] = (
                f"Capability {index} is a distinct printed statement about joints."
            )
        return plan

    def test_the_binding_cell_is_the_one_the_job_runs(self) -> None:
        # A full course is always raised to ``deep`` by ``research.effective_depth``, whatever
        # depth the brief declares, so the ceiling read here is the deep cell's.
        expectation = {**gen.SCOPE_EXPECTATIONS["full"], "scope": "full"}
        for declared in (None, "survey", "working", "deep"):
            with self.subTest(declared=declared):
                _, ceiling = gen._scope_objective_band(expectation, self._ledger(20), depth=declared)
                self.assertEqual(ceiling, 40)

    def test_a_thirty_five_objective_full_plan_is_accepted_by_the_shipped_cell(self) -> None:
        # 20 sources x 2 = 40, so 35 objectives sit inside the cell; the 15 beyond the ledger's
        # capability count are declared gaps, never re-labelled claims.
        ledger = self._ledger(20)
        plan = self._sourced_prefix(self._plan([5, 5, 5, 5, 5, 5, 5]), 20)
        self.assertEqual(len(plan["objectives"]), 35)
        _rules(plan, ledger, "full")
        self.assertEqual(
            gen._ledger_capability_count(ledger),
            20,
        )

    def test_the_pre_s6_cell_refuses_the_same_plan(self) -> None:
        # The measured defect: 16 sources against a 40-objective band. Restore that cell and the
        # ceiling becomes 32, so the 35-objective plan is refused on the cell's number.
        self._set_sources("full", "deep", 16)
        expectation = {**gen.SCOPE_EXPECTATIONS["full"], "scope": "full"}
        band_floor = int(expectation["blueprint_objectives"][0])
        ledger = self._ledger(20)
        floor, ceiling = gen._scope_objective_band(expectation, ledger)
        self.assertEqual((floor, ceiling), (band_floor, 32))
        plan = self._sourced_prefix(self._plan([5, 5, 5, 5, 5, 5, 5]), 20)
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger, "full")
        reasons = " ".join(caught.exception.reasons)
        self.assertIn(f"requires {band_floor} to 32 objective(s)", reasons)


class PlanRequestStatesTheDerivedBandTest(unittest.TestCase):
    """The author is told the band the gate enforces, in the prompt and in the payload rules."""

    def test_the_request_carries_the_ledger_floor_and_the_cell_ceiling(self) -> None:
        ledger = _ledger(*FIVE_CAPABILITIES)
        run = research.ResearchRun("ok", [], ledger, None)
        request = gen.build_plan_request(
            goal="Learn to solder through-hole joints that hold",
            recipe="casual",
            dials={},
            locale=None,
            research_run=run,
            scope="full",
        )
        self.assertIn("Produce 2 to 12 unit(s) and 5 to 40 objective(s)", request.instructions)
        band_low, band_high = gen.SCOPE_EXPECTATIONS["full"]["blueprint_objectives"]
        self.assertIn(
            f"The 'full' band is {band_low} to {band_high} objective(s)", request.instructions
        )
        self.assertIn("carry 5 distinct capabilities", request.instructions)
        payload = json.loads(request.input_text)
        self.assertEqual(payload["rules"]["objective_count"], [5, 40])
        self.assertEqual(payload["rules"]["objective_band"], [band_low, band_high])


class TheBandInvariantTest(unittest.TestCase):
    """The card's invariant: ``max_sources × OBJECTIVES_PER_SOURCE >= blueprint_objectives[1]``.

    It holds for single, short and full — i.e. no scope's band asks for more objectives than its
    richest research cell can source. A cell that cannot reach the band's ceiling is a contract
    defect (S6), so this test fails loudly instead of letting a course be authored that could
    never be sourced.
    """

    def test_every_scope_can_source_its_band_ceiling(self) -> None:
        for scope in gen.SCOPES:
            with self.subTest(scope=scope):
                band_high = int(gen.SCOPE_EXPECTATIONS[scope]["blueprint_objectives"][1])
                richest = max(
                    research.budget_for(depth, scope).max_sources
                    for depth in research.DEPTH_VALUES
                )
                self.assertGreaterEqual(
                    richest * research.OBJECTIVES_PER_SOURCE,
                    band_high,
                    f"{scope}: {richest} sources cannot source {band_high} objectives",
                )

    def test_every_cell_is_internally_consistent(self) -> None:
        # The ceiling never drops below the band's floor in a cell that can reach it, and no cell
        # asks for more objectives than it has sources for.
        for scope in gen.SCOPES:
            expectation = {**gen.SCOPE_EXPECTATIONS[scope], "scope": scope}
            band_low = int(expectation["blueprint_objectives"][0])
            for depth in research.DEPTH_VALUES:
                with self.subTest(scope=scope, depth=depth):
                    budget = research.budget_for(depth, scope)
                    ceiling = min(
                        int(expectation["blueprint_objectives"][1]),
                        budget.max_sources * research.OBJECTIVES_PER_SOURCE,
                    )
                    self.assertGreaterEqual(budget.max_sources, ceiling / 2)
                    # A single-capability ledger binds the floor; it can never exceed the ceiling.
                    floor, _ = gen._scope_objective_band(
                        expectation,
                        _ledger(("src_one", "A soldering iron reaches about 350 degrees Celsius.")),
                        depth=depth,
                    )
                    self.assertLessEqual(floor, ceiling)
                    self.assertGreaterEqual(floor, 1)
                    self.assertGreaterEqual(band_low, floor)

    def test_the_full_deep_cell_was_raised_to_meet_the_band(self) -> None:
        # The measured S6 numbers: single/working 4, short/working 8, full/deep 16 was 0.4 sources
        # per objective against a 40-objective ceiling. The cell is now 20.
        self.assertEqual(research.budget_for("working", "single").max_sources, 4)
        self.assertEqual(research.budget_for("working", "short").max_sources, 8)
        self.assertEqual(research.budget_for("deep", "full").max_sources, 20)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
