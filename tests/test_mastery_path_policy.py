"""H-154: mastery path and checkpoint policy against the real kernel and the policy module.

The doc is ``docs/MASTERY-PATH-POLICY.md``; the executable half is ``coursebook.mastery_path``.
These tests cover both: pure policy fixtures (node fields, checkpoint refusal, pass rule, failure
rule, spacing, interleaving) and real-state fixtures against a migrated SQLite database
(gate/delayed writes, no day-1 reset, no jump to the end, no path lock).

Nothing here invents provider output. The kernel fixtures are real rows inserted as fixtures and
driven through the real commands; the policy fixtures are plain dicts.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone

from coursebook import db, generation as gen, mastery_path as mp, policy, review
from tests.blueprint_support import blueprint_plan
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

CREATED = "2026-11-07T00:00:00+00:00"


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


class PolicyFixtureTest(unittest.TestCase):
    """Pure policy: no database, no provider, deterministic projections."""

    def test_the_check_families_mirror_generation_and_capability_policy(self) -> None:
        self.assertEqual(mp.CHECK_FAMILIES, gen.EVIDENCE_TARGETS)
        self.assertEqual(mp.CHECK_FAMILIES, policy.EVIDENCE_TARGETS)

    def test_every_evidence_target_has_its_own_pass_criterion(self) -> None:
        self.assertEqual(set(mp.PASS_CRITERIA), set(mp.CHECK_FAMILIES))
        self.assertIsNone(mp.STREAK_LENGTH)  # no universal "three in a row"
        for family in mp.CHECK_FAMILIES:
            criterion = mp.pass_criterion(family)
            self.assertEqual(criterion["gate_cold_passes"], 1)
            self.assertEqual(criterion["delayed_cold_passes"], 1)
            self.assertEqual(criterion["min_delay_days"], mp.LADDERS[family][0])
            self.assertNotIn("in a row", criterion["rule"])
            self.assertFalse(criterion["probabilistic_claim"])

    def test_a_node_projects_five_fields_from_real_plan_rows(self) -> None:
        unit = {"ordinal": 2, "prereq_unit_ordinals": [1], "title": "Unit 2"}
        objective = {
            "ordinal": 4,
            "title": "Can order food and ask the price without English",
            "evidence_target": "production",
        }
        check = {"evidence_target": "production"}
        node = mp.node(unit=unit, objective=objective, check=check)
        self.assertEqual(set(mp.NODE_FIELDS).issubset(node), True)
        self.assertEqual(node["exit_performance"],
                         "Can order food and ask the price without English")
        self.assertEqual(node["prerequisite_units"], [1])
        self.assertEqual(node["check_family"], "production")
        self.assertEqual(node["review_obligation"]["ladder_days"], [3, 7, 16, 35])
        self.assertEqual(node["checkpoints"], ["gate", "delayed"])
        self.assertEqual(mp.node_problems(node, check=check), [])

    def test_a_topic_label_is_refused_as_an_exit_performance(self) -> None:
        for title in ("Introduction to particles", "Japanese greetings vocabulary",
                      "Kitchen basics", ""):
            with self.subTest(title=title):
                self.assertTrue(mp.exit_performance_problems(title))
        self.assertEqual(mp.exit_performance_problems("Can ask for the bill politely"), [])

    def test_a_check_must_measure_the_nodes_own_family(self) -> None:
        node = mp.node(
            unit={"ordinal": 1},
            objective={"ordinal": 1, "title": "Can ask a price", "evidence_target": "production"},
            check={"evidence_target": "comprehension"},
        )
        problems = mp.node_problems(node, check={"evidence_target": "comprehension"})
        self.assertTrue(any("must measure" in problem for problem in problems))

    def test_gate_and_delayed_write_the_contracted_states(self) -> None:
        planned = mp.plan_checkpoints()
        self.assertEqual([item["kind"] for item in planned], ["gate", "delayed"])
        self.assertEqual(planned[0]["writes"], "independent_evidence")
        self.assertEqual(planned[1]["writes"], "delayed_evidence")

    def test_a_cumulative_checkpoint_is_refused_until_the_contract_exists(self) -> None:
        self.assertFalse(mp.checkpoint_supported("cumulative"))
        self.assertEqual(mp.drawable_checkpoints(), ("gate", "delayed"))
        with self.assertRaises(mp.UnsupportedCheckpoint) as caught:
            mp.plan_checkpoints(cumulative=True)
        self.assertIn("unit_scoped_check", str(caught.exception))
        node = mp.node(
            unit={"ordinal": 1},
            objective={"ordinal": 1, "title": "Can ask a price", "evidence_target": "production"},
        )
        node["checkpoints"] = ["gate", "delayed", "cumulative"]
        self.assertTrue(any("cannot record" in problem for problem in mp.node_problems(node)))

    def test_the_cumulative_contract_names_its_missing_capabilities(self) -> None:
        missing = mp.CUMULATIVE_CHECK_REQUIRES - mp.BACKEND_CAPABILITIES
        self.assertIn("unit_scoped_check", missing)
        self.assertIn("cumulative_check", missing)

    def test_one_miss_sets_needs_review_and_never_resets(self) -> None:
        self.assertEqual(mp.review_outcome(misses=1, forms=["quiz"]), "needs_review")
        self.assertFalse(mp.FAILURE_RULE["resets_course"])
        self.assertFalse(mp.FAILURE_RULE["locks_path"])

    def test_two_misses_on_the_same_form_do_not_trigger_re_teaching(self) -> None:
        self.assertEqual(mp.review_outcome(misses=2, forms=["quiz", "quiz"]), "needs_review")

    def test_two_misses_on_different_forms_trigger_re_teaching(self) -> None:
        self.assertEqual(mp.review_outcome(misses=2, forms=["quiz", "verification"]), "reteach")

    def test_a_failed_review_keeps_its_rung_and_a_pass_advances_one(self) -> None:
        ladder = mp.LADDERS["procedure"]
        self.assertEqual(mp.review_step(2, passed=False, ladder=ladder), 2)  # not day 1
        self.assertEqual(mp.review_step(2, passed=True, ladder=ladder), 3)
        self.assertEqual(mp.review_step(0, passed=False, ladder=ladder), 0)
        self.assertEqual(mp.review_step(len(ladder) - 1, passed=True, ladder=ladder),
                         len(ladder) - 1)  # a pass never jumps past the end
        self.assertEqual(mp.review_step(1, passed=True, ladder=ladder), 2)  # exactly one rung

    def test_interleaving_blocks_acquisition_and_groups_confusable_sets(self) -> None:
        items = [
            {"item": "wa", "confusable_set": "topic", "acquired": False},
        ]
        with self.assertRaises(ValueError):
            mp.review_sequence(items)
        acquired = [
            {"item": "wa", "confusable_set": "particle-topic", "acquired": True},
            {"item": "ga", "confusable_set": "particle-subject", "acquired": True},
            {"item": "no", "confusable_set": "particle-topic", "acquired": True},
        ]
        ordered = mp.review_sequence(acquired)
        self.assertEqual([item["item"] for item in ordered], ["wa", "no", "ga"])
        with self.assertRaises(ValueError):
            mp.review_sequence([{"item": "wa", "acquired": True}])  # no set = random mixing

    def test_the_v2_prompt_carries_the_mastery_policy(self) -> None:
        prompt = gen._plan_instructions_v2(
            recipe="casual",
            dials={},
            locale=None,
            research_status="none",
            scope="short",
        )
        self.assertIn("exit performance", prompt)
        self.assertIn("evidence_target is the node's check family", prompt)
        self.assertIn("cumulative checkpoint may not be drawn", prompt)

    def test_a_v2_plan_whose_check_measures_another_family_is_refused(self) -> None:
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, recipe="casual")
        plan["check_plan"][0]["evidence_target"] = "production"
        with self.assertRaises(gen.GenerationError) as caught:
            gen.enforce_plan_rules(plan, recipe="casual", dials={}, locale=None, ledger=[],
                                   scope="short")
        self.assertIn("check family", str(caught.exception))


class MasteryKernelCase(KernelCase):
    """Real rows, real commands. Fixtures, never a fabricated provider result."""

    def prepare_multi(self, count: int = 1) -> dict:
        course_id, plan_id = self.new_course()
        objective_ids = [self.seed_objective(plan_id, numeric_spec("42.7")) for _ in range(count)]
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id, "plan_id": plan_id, "enrollment_id": enrollment_id,
            "objective_ids": objective_ids, "revision": revision,
        }

    def pass_objective(self, lesson: dict, objective_id: str, answer: str = "42.7") -> dict:
        revision = int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))))
        opened = self.ok(
            "check.open", {"enrollment_id": lesson["enrollment_id"], "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        response = self.submit(
            {"enrollment_id": lesson["enrollment_id"], "check_id": opened["check_id"],
             "check_version": opened["check_version"], "revision": opened["revision"]},
            answer,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def fail_objective(self, lesson: dict, objective_id: str, answer: str = "0") -> dict:
        return self.pass_objective(lesson, objective_id, answer=answer)

    def backdate(self, objective_id: str, days: float = 10) -> None:
        self.execute(
            "UPDATE evidence SET created_at = ? WHERE objective_id = ? AND layer = 2",
            (_iso(days), objective_id),
        )

    def queue_item(self, enrollment_id: str, objective_id: str) -> dict:
        with db.read() as connection:
            queue = review.queue(connection, enrollment_id)
        return next(item for item in queue["items"] if item["objective_id"] == objective_id)

    def seed_plan(self, *, units, objectives, title="A course", recipe="committed") -> dict:
        """A prerequisite fixture; the real gating commands read these real rows."""
        course_id, plan_id = self.new_course(title=title, recipe=recipe)
        enrollment_id = self.new_enrollment(course_id)
        suffix = f"{os.urandom(3).hex()}"
        unit_ids: dict[int, str] = {}
        for unit in units:
            unit_id = f"unt_{suffix}{int(unit['ordinal']):02d}"
            unit_ids[int(unit["ordinal"])] = unit_id
            self.execute(
                "INSERT INTO plan_units (id, plan_id, ordinal, title, goal,"
                " prereq_unit_ordinals_json, target_lessons, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    unit_id, plan_id, int(unit["ordinal"]), unit["title"], unit["goal"],
                    json.dumps(list(unit.get("prereqs", []))), int(unit.get("target_lessons", 1)),
                    CREATED,
                ),
            )
        objective_ids: dict[int, str] = {}
        for objective in objectives:
            ordinal = int(objective["ordinal"])
            objective_id = f"obj_{suffix}{ordinal:02d}"
            objective_ids[ordinal] = objective_id
            self.execute(
                "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                " evidence_criteria_json, state, version, created_at, unit_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    objective_id, plan_id, ordinal, objective["title"], "procedure",
                    json.dumps(criteria_with(numeric_spec())),
                    objective.get("state", "not_started"), 1, CREATED,
                    unit_ids.get(int(objective["unit"])) if objective.get("unit") is not None
                    else None,
                ),
            )
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id, "plan_id": plan_id, "enrollment_id": enrollment_id,
            "revision": revision, "unit_ids": unit_ids, "objective_ids": objective_ids,
        }


class CheckpointStateTest(MasteryKernelCase):
    def test_a_cold_gate_pass_writes_independent_evidence(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        result = self.pass_objective(lesson, objective_id)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
            "independent_evidence",
        )
        self.assertEqual(
            self.scalar("SELECT kind FROM evidence WHERE layer = 2 AND objective_id = ?"
                        " ORDER BY created_at DESC LIMIT 1", (objective_id,)),
            "independent_evidence",
        )

    def test_a_gate_pass_moves_introduced_to_independent_evidence(self) -> None:
        """The contracted transition: a non-cold pass introduces, a cold pass makes it independent."""
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.execute("UPDATE objectives SET state = 'introduced' WHERE id = ?", (objective_id,))
        result = self.pass_objective(lesson, objective_id)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "cold")
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
            "independent_evidence",
        )

    def test_a_cold_delayed_pass_writes_delayed_evidence(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective_id,))
        result = self.pass_objective(lesson, objective_id)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
            "delayed_evidence",
        )
        self.assertEqual(
            self.scalar("SELECT kind FROM evidence WHERE layer = 2 AND objective_id = ?"
                        " ORDER BY created_at DESC LIMIT 1", (objective_id,)),
            "delayed_retrieval",
        )


class SpacingRuleTest(MasteryKernelCase):
    def test_a_gate_pass_starts_at_the_first_rung_not_the_last(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        item = self.queue_item(lesson["enrollment_id"], objective_id)
        ladder = mp.LADDERS["procedure"]
        self.assertEqual(item["step"], 0)
        self.assertEqual(item["interval_days"], ladder[0])
        self.assertNotEqual(item["interval_days"], ladder[-1])

    def test_a_delayed_pass_advances_exactly_one_rung(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        self.pass_objective(lesson, objective_id)
        self.backdate(objective_id, days=10)
        self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective_id,))
        self.pass_objective(lesson, objective_id)
        item = self.queue_item(lesson["enrollment_id"], objective_id)
        ladder = mp.LADDERS["procedure"]
        self.assertEqual(item["step"], 1)
        self.assertEqual(item["interval_days"], ladder[1])
        self.assertNotEqual(item["interval_days"], ladder[-1])

    def test_a_failed_review_keeps_its_rung_and_sets_needs_review(self) -> None:
        lesson = self.prepare_multi(1)
        objective_id = lesson["objective_ids"][0]
        # gate pass, then two delayed passes: the item is on rung 2.
        self.pass_objective(lesson, objective_id)
        for _ in range(2):
            self.backdate(objective_id, days=10)
            self.execute("UPDATE objectives SET state = 'review_due' WHERE id = ?", (objective_id,))
            self.pass_objective(lesson, objective_id)
        item = self.queue_item(lesson["enrollment_id"], objective_id)
        ladder = mp.LADDERS["procedure"]
        self.assertEqual(item["step"], 2)
        self.assertEqual(item["interval_days"], ladder[2])

        failed = self.fail_objective(lesson, objective_id)
        self.assertNotEqual(failed["verdict"], "pass")
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)),
            "needs_review",
        )
        after = self.queue_item(lesson["enrollment_id"], objective_id)
        self.assertEqual(after["state"], "needs_review")
        self.assertEqual(after["step"], 2)  # never reset to the first rung
        self.assertEqual(after["interval_days"], ladder[2])
        self.assertNotEqual(after["interval_days"], ladder[0])
        # The path is not locked: the objective is still in the review queue.
        self.assertGreaterEqual(after["interval_days"], 1)


class PathLockTest(MasteryKernelCase):
    def test_an_unmet_prerequisite_offers_continue_instead_of_locking(self) -> None:
        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.",
                 "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        revision = int(str(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (seeded["enrollment_id"],))))
        error = self.err(
            "check.open",
            {"enrollment_id": seeded["enrollment_id"],
             "objective_id": seeded["objective_ids"][2]},
            expected_revision=revision,
        )
        self.assertEqual(error["code"], "PREREQUISITE_UNMET")
        self.assertEqual(error["details"]["prerequisite_state"]["state"], "unmet")

        continued = self.ok(
            "check.open",
            {"enrollment_id": seeded["enrollment_id"],
             "objective_id": seeded["objective_ids"][2],
             "acknowledge_prerequisites": True},
            expected_revision=revision,
        )["result"]
        self.assertEqual(continued["prerequisite_state"]["state"], "unmet_acknowledged")
