"""Upgrade 46 — unit prerequisites are validated as a DAG, not "a list of ints".

Design authority: ``docs/UPGRADES-50-2026-11-14.md`` §46 and ``docs/OSS-LANDSCAPE-2026-11-14.md``
§3. The plan gate must refuse a cycle, a dangling ordinal and a redundant transitive edge, each
with a typed reason that names the offending ordinals. It must never *infer* a prerequisite and it
must keep accepting a linear plan.

The named acceptance test is
``PrereqDagTest::test_a_cycle_is_refused_with_its_ordinals``.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from coursebook import mastery_path as mp

from tests.blueprint_support import blueprint_plan


def _plan_with_edges(edges: dict[int, list[int]]) -> dict:
    """A schema-valid ``coursebook.plan.v2`` whose unit edges are exactly ``edges``.

    Units are built linearly by the fixture, then each unit's declared edge list is replaced, so
    the document is the one a hand-edited/imported plan would carry. Objectives and check plan are
    left untouched: this test is about the edge graph, not about the rest of the plan.
    """
    plan = blueprint_plan(scope="short", units=len(edges), objectives_per_unit=2)
    for unit in plan["units"]:
        unit["prereq_unit_ordinals"] = list(edges[int(unit["ordinal"])])
    return plan


def _plan_rules(plan: dict) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe="casual",
        dials={},
        locale=None,
        ledger=[],
        scope=plan.get("scope"),
    )


class PrereqDagTest(unittest.TestCase):
    """The plan gate builds the unit DAG and refuses what cannot be sequenced."""

    def test_a_cycle_is_refused_with_its_ordinals(self) -> None:
        """2 -> 3 -> 2 returns VALIDATION_FAILED with ``prerequisite_cycle`` and both ordinals."""
        plan = _plan_with_edges({1: [], 2: [3], 3: [2]})
        with self.assertRaises(gen.PrerequisiteDagRefused) as caught:
            _plan_rules(plan)
        refusal = caught.exception
        self.assertEqual(refusal.code, "VALIDATION_FAILED")
        self.assertEqual(refusal.reason, "prerequisite_cycle")
        self.assertEqual(sorted(refusal.error_details["ordinals"]), [2, 3])
        # The refusal names the closing path, so an operator can read the loop itself.
        self.assertEqual(refusal.error_details["cycle"][0], refusal.error_details["cycle"][-1])

    def test_a_linear_plan_still_passes(self) -> None:
        """The same fixture, sequenced linearly, is not refused."""
        _plan_rules(_plan_with_edges({1: [], 2: [1], 3: [2]}))
        self.assertEqual(mp.prerequisite_dag_problems([
            {"ordinal": 1, "prereq_unit_ordinals": []},
            {"ordinal": 2, "prereq_unit_ordinals": [1]},
            {"ordinal": 3, "prereq_unit_ordinals": [2]},
        ]), [])

    def test_a_dangling_ordinal_is_refused_with_its_ordinal(self) -> None:
        """A prerequisite that names no unit is refused, not stored and skipped at gating."""
        plan = _plan_with_edges({1: [], 2: [1], 3: [7]})
        with self.assertRaises(gen.PrerequisiteDagRefused) as caught:
            _plan_rules(plan)
        refusal = caught.exception
        self.assertEqual(refusal.reason, "prerequisite_missing_unit")
        self.assertEqual(refusal.error_details["unit_ordinal"], 3)
        self.assertEqual(refusal.error_details["prerequisite_ordinal"], 7)

    def test_a_redundant_transitive_edge_is_refused(self) -> None:
        """3 -> 1 is implied by 3 -> 2 -> 1, so stating it is a second, contradictory ranking."""
        plan = _plan_with_edges({1: [], 2: [1], 3: [1, 2]})
        with self.assertRaises(gen.PrerequisiteDagRefused) as caught:
            _plan_rules(plan)
        refusal = caught.exception
        self.assertEqual(refusal.reason, "prerequisite_redundant_edge")
        self.assertEqual(refusal.error_details["unit_ordinal"], 3)
        self.assertEqual(refusal.error_details["prerequisite_ordinal"], 1)

    def test_a_cycle_is_named_before_the_forward_half(self) -> None:
        """The reader's own reason names the cycle, never only its forward half."""
        plan = _plan_with_edges({1: [], 2: [3], 3: [2]})
        problems = mp.prerequisite_dag_problems(
            [dict(unit) for unit in plan["units"]]
        )
        self.assertEqual([problem["reason"] for problem in problems], ["prerequisite_cycle"])
        self.assertEqual(sorted(problems[0]["ordinals"]), [2, 3])

    def test_the_job_service_reports_validation_failed_with_the_reason(self) -> None:
        """The typed cause reaches ``jobs.get``: VALIDATION_FAILED, not INTERNAL_ERROR."""
        from coursebook import job_service

        with self.assertRaises(gen.PrerequisiteDagRefused) as caught:
            _plan_rules(_plan_with_edges({1: [], 2: [3], 3: [2]}))
        error = job_service._stage_error(caught.exception)
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "prerequisite_cycle")
        self.assertEqual(sorted(error["details"]["ordinals"]), [2, 3])

    def test_the_networkx_pin_is_declared_for_the_python_floor(self) -> None:
        """The DAG builder is a declared dependency, pinned where its requires-python fits."""
        from pathlib import Path

        import yaml

        manifest = yaml.safe_load(
            (Path(gen.__file__).resolve().parent.parent / "plugin.yaml").read_text(encoding="utf-8")
        )
        deps = [str(dep) for dep in manifest.get("python_dependencies") or []]
        pins = [dep for dep in deps if dep.split(">")[0].split("=")[0].strip() == "networkx"]
        self.assertEqual(len(pins), 1, "networkx must be declared exactly once")
        self.assertIn(">=3.7", pins[0], "3.7 is the first release requiring Python >=3.12")
        self.assertIn("<4", pins[0])

    @unittest.skipUnless(mp._networkx is not None, "networkx pin is not installed")
    def test_both_graph_backends_name_the_same_problems(self) -> None:
        """The declared builder and the dependency-free fallback must not disagree.

        A host without the pin still refuses a cycle, so the two code paths are part of one
        contract; a divergence would make the refusal depend on what was installed.
        """
        fixtures = [
            [{"ordinal": 1, "prereq_unit_ordinals": []},
             {"ordinal": 2, "prereq_unit_ordinals": [1]},
             {"ordinal": 3, "prereq_unit_ordinals": [2]}],
            [{"ordinal": 1, "prereq_unit_ordinals": []},
             {"ordinal": 2, "prereq_unit_ordinals": [3]},
             {"ordinal": 3, "prereq_unit_ordinals": [2]}],
            [{"ordinal": 1, "prereq_unit_ordinals": []},
             {"ordinal": 2, "prereq_unit_ordinals": [1]},
             {"ordinal": 3, "prereq_unit_ordinals": [7]}],
            [{"ordinal": 1, "prereq_unit_ordinals": []},
             {"ordinal": 2, "prereq_unit_ordinals": [1]},
             {"ordinal": 3, "prereq_unit_ordinals": [1, 2]}],
        ]
        declared = [mp.prerequisite_dag_problems(units) for units in fixtures]
        installed = mp._networkx
        mp._networkx = None
        try:
            fallback = [mp.prerequisite_dag_problems(units) for units in fixtures]
        finally:
            mp._networkx = installed
        self.assertEqual(declared, fallback)
