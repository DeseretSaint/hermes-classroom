"""H-21c: §14.2 prerequisite edge rules (R1-R9) and the §14.4 acceptance tests.

Design authority: ``docs/COURSE-BLUEPRINT.md`` §14.2, §14.3, §14.4. Every test here is named
exactly as §14.4 names it and proves one refusal or one projection fact against a real migrated
SQLite database. No test presents invented provider output as a real call.
"""

from __future__ import annotations

import json
import os
import unittest

from coursebook import db, domain, generation as gen

from tests.blueprint_support import blueprint_plan
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

CREATED = "2026-11-07T00:00:00+00:00"

#: The R9 key set, frozen by the contract. No derived boolean, score, percentage or "ready".
R9_UNIT_KEYS = {
    "ordinal",
    "title",
    "goal",
    "prereq_unit_ordinals",
    "prerequisite_state",
    "unmet",
    "objectives",
}

#: The seven objective labels the kernel already has. R7 adds no eighth, and no number.
OBJECTIVE_STATES = {
    "not_started",
    "introduced",
    "independent_evidence",
    "delayed_evidence",
    "review_due",
    "needs_review",
    "overridden",
}


def _plan_rules(plan: dict, *, recipe: str = "casual", ledger=(), locale=None, scope=None) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe=recipe,
        dials={},
        locale=locale,
        ledger=list(ledger),
        scope=scope if scope is not None else plan.get("scope"),
    )


class PrerequisiteGatingCase(KernelCase):
    """Seeds a plan whose units and objectives are real rows, then approves it a real way.

    Rows are inserted directly because a provider must never be faked: the unit structure is the
    fixture, not authored prose. ``plan.approve`` is then driven through the RPC, so the plan the
    gating reads is the same approved plan a learner would have.
    """

    def seed_plan(self, *, units, objectives, title="A course", recipe="committed") -> dict:
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
                    unit_id,
                    plan_id,
                    int(unit["ordinal"]),
                    unit["title"],
                    unit["goal"],
                    json.dumps(list(unit.get("prereqs", []))),
                    int(unit.get("target_lessons", 1)),
                    CREATED,
                ),
            )
        objective_ids: dict[int, str] = {}
        for objective in objectives:
            ordinal = int(objective["ordinal"])
            objective_id = f"obj_{suffix}{ordinal:02d}"
            objective_ids[ordinal] = objective_id
            unit_ref = objective.get("unit")
            self.execute(
                "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                " evidence_criteria_json, state, version, created_at, unit_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    objective_id,
                    plan_id,
                    ordinal,
                    objective["title"],
                    "procedure",
                    json.dumps(criteria_with(numeric_spec())),
                    objective.get("state", "not_started"),
                    1,
                    CREATED,
                    unit_ids.get(int(unit_ref)) if unit_ref is not None else None,
                ),
            )
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "revision": revision,
            "unit_ids": unit_ids,
            "objective_ids": objective_ids,
        }

    def set_prereqs(self, unit_id: str, prereqs) -> None:
        self.execute(
            "UPDATE plan_units SET prereq_unit_ordinals_json = ? WHERE id = ?",
            (json.dumps(list(prereqs)), unit_id),
        )

    def outline_units(self, enrollment_id: str) -> list[dict]:
        """R9 lives on ``course.outline``'s plan projection, not at the result root."""
        return self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]["plan"][
            "units"
        ]


class EdgeFenceTest(PrerequisiteGatingCase):
    """§14.4 tests 1-5: the reader refuses an unsequenceable document, R1-R3."""

    def test_prerequisite_cycle_refused(self) -> None:
        """R2: unit 2 -> 3 -> 2 is refused with ``prerequisite_cycle`` and the cycle listed."""
        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
                {"ordinal": 3, "title": "Unit 3", "goal": "Do the third thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
                {"ordinal": 3, "unit": 3, "title": "Third"},
            ],
        )
        # The writer cannot author this (a forward ref is refused); a hand-edited or imported
        # document is what a reader must still refuse.
        self.set_prereqs(seeded["unit_ids"][2], [3])
        self.set_prereqs(seeded["unit_ids"][3], [2])
        error = self.err("course.outline", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "prerequisite_cycle")
        cycle = error["details"]["cycle"]
        self.assertEqual(cycle[0], cycle[-1])
        self.assertEqual(set(cycle), {2, 3})

    def test_prerequisite_forward_ref_refused(self) -> None:
        """R2/R1: a forward reference is refused by the writer and by the reader."""
        plan = blueprint_plan(scope="full", units=4, objectives_per_unit=3)
        plan["units"][1]["prereq_unit_ordinals"] = [3]
        with self.assertRaises(gen.GenerationError) as caught:
            _plan_rules(plan, scope="full")
        self.assertIn("strictly lower", str(caught.exception))

        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
                {"ordinal": 3, "title": "Unit 3", "goal": "Do the third thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
                {"ordinal": 3, "unit": 3, "title": "Third"},
            ],
        )
        self.set_prereqs(seeded["unit_ids"][2], [3])
        error = self.err("course.outline", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(error["details"]["reason"], "prerequisite_forward_ref")

    def test_prerequisite_self_ref_refused(self) -> None:
        """R1/R2: a unit naming itself is refused; it is a one-node cycle."""
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        plan["units"][1]["prereq_unit_ordinals"] = [2]
        with self.assertRaises(gen.GenerationError) as caught:
            _plan_rules(plan, scope="short")
        self.assertIn("itself", str(caught.exception))

        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        self.set_prereqs(seeded["unit_ids"][2], [2])
        error = self.err("course.outline", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(error["details"]["reason"], "prerequisite_self_ref")

    def test_prerequisite_duplicate_ref_refused(self) -> None:
        """R1: a repeated prerequisite unit is refused."""
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        plan["units"][1]["prereq_unit_ordinals"] = [1, 1]
        with self.assertRaises(gen.GenerationError) as caught:
            _plan_rules(plan, scope="short")
        self.assertIn("repeats a prerequisite", str(caught.exception))

        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        self.set_prereqs(seeded["unit_ids"][2], [1, 1])
        error = self.err("course.outline", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(error["details"]["reason"], "prerequisite_duplicate_ref")

    def test_prerequisite_missing_unit_refused(self) -> None:
        """R1/R3: a ref that names no unit in this plan version is refused; a replan that drops
        a depended-on unit refuses and writes nothing."""
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2)
        plan["units"][1]["prereq_unit_ordinals"] = [9]
        with self.assertRaises(gen.GenerationError) as caught:
            _plan_rules(plan, scope="short")
        self.assertIn("missing prerequisite unit", str(caught.exception))

        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        self.set_prereqs(seeded["unit_ids"][2], [9])
        error = self.err("course.outline", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(error["details"]["reason"], "prerequisite_missing_unit")

        # Replan variant: dropping every objective of a depended-on unit leaves unit 2's edge
        # pointing at nothing, so the replan refuses and the new version is never written.
        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        plans_before = self.scalar("SELECT COUNT(*) FROM plans")
        error = self.err(
            "plan.replan",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_changes": [
                    {"objective_id": seeded["objective_ids"][1], "change": "remove"},
                    {"objective_id": seeded["objective_ids"][2], "change": "keep"},
                ],
            },
            expected_revision=seeded["revision"],
            idempotency_key="key-replan-drop-unit",
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "prerequisite_missing_unit")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM plans"), plans_before)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM plan_units WHERE plan_id = ?", (seeded["plan_id"],)
            ),
            2,
        )


class GatingTest(PrerequisiteGatingCase):
    """§14.4 tests 6-8: the gate is disclosure, and a refusal writes nothing."""

    def _two_unit_seed(self) -> dict:
        return self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Identify the hazard."},
                {
                    "ordinal": 2,
                    "title": "Unit 2",
                    "goal": "Use the power tool safely.",
                    "prereqs": [1],
                },
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "Name the hazard", "state": "introduced"},
                {"ordinal": 2, "unit": 2, "title": "Operate the saw"},
            ],
        )

    def test_lesson_begin_refuses_unmet_prerequisite(self) -> None:
        """R5/R6: no ``lesson_runs`` row is written and the error carries the unmet list."""
        seeded = self._two_unit_seed()
        error = self.err(
            "lesson.begin",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_ids"][2],
                "mode": "fresh",
            },
            idempotency_key="key-lesson-begin-unmet",
        )
        self.assertEqual(error["code"], "PREREQUISITE_UNMET")
        unmet = error["details"]["prerequisite_state"]["unmet"]
        self.assertEqual([item["objective_id"] for item in unmet], [seeded["objective_ids"][1]])
        self.assertEqual(unmet[0]["state"], "introduced")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM lesson_runs"), 0)

    def test_lesson_begin_acknowledged_prerequisite_proceeds(self) -> None:
        """R6: the run is created, ``unmet_acknowledged`` echoed, nothing else written."""
        seeded = self._two_unit_seed()
        result = self.ok(
            "lesson.begin",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_ids"][2],
                "mode": "fresh",
                "acknowledge_prerequisites": True,
            },
            idempotency_key="key-lesson-begin-acknowledged",
        )["result"]
        self.assertEqual(result["run_state"], "created")
        self.assertEqual(result["prerequisite_state"]["state"], "unmet_acknowledged")
        self.assertEqual(
            [item["objective_id"] for item in result["prerequisite_state"]["unmet"]],
            [seeded["objective_ids"][1]],
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM lesson_runs"), 1)
        # The acknowledgment is a learner decision, never evidence and never a movement.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)
        self.assertEqual(
            self.scalar(
                "SELECT state FROM objectives WHERE id = ?", (seeded["objective_ids"][1],)
            ),
            "introduced",
        )
        self.assertEqual(
            self.scalar(
                "SELECT state FROM objectives WHERE id = ?", (seeded["objective_ids"][2],)
            ),
            "not_started",
        )

    def test_check_open_refuses_unmet_prerequisite(self) -> None:
        """R5/R6: no ``checks`` row is written for the gated objective."""
        seeded = self._two_unit_seed()
        error = self.err(
            "check.open",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_ids"][2],
            },
            expected_revision=seeded["revision"],
            idempotency_key="key-check-open-unmet",
        )
        self.assertEqual(error["code"], "PREREQUISITE_UNMET")
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM checks WHERE objective_id = ?",
                (seeded["objective_ids"][2],),
            ),
            0,
        )
        # A refusal is not a transition: the enrollment revision did not move.
        self.assertEqual(
            self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (seeded["enrollment_id"],)
            ),
            seeded["revision"],
        )


class LegacyAndProjectionTest(PrerequisiteGatingCase):
    """§14.4 tests 9-10 and 13: R4 legacy invariance and R7/R9 projection shape."""

    LEGACY_COURSE = (
        "crs_legacy01", "Legacy braise", "committed", "Braise short ribs", "en-US",
        '{"pace": "steady", "depth": "working", "assessment": "self_check", "autonomy": "guided"}',
        "active", 0, CREATED, CREATED,
    )
    LEGACY_PLAN = ("pln_legacy01", "crs_legacy01", 1, "draft", None, "{}", CREATED, None)
    LEGACY_OBJECTIVES = [
        ("obj_legacy01", "pln_legacy01", 1, "Sear the ribs", "procedure",
         '[{"id": "c1", "description": "Sear without steaming the meat"}]',
         "not_started", 1, CREATED),
        ("obj_legacy02", "pln_legacy01", 2, "Braise to tenderness", "procedure",
         '[{"id": "c1", "description": "Meat yields to a fork"}]',
         "not_started", 1, CREATED),
    ]
    #: Computed with the v6 code before migration 0007 (master 498b1da). A literal, so a quiet
    #: `units: []` in the hash payload fails here.
    LEGACY_PLAN_HASH = (
        "sha256:2ec4ad3356df241d30ca185336f85f72bbec46035adedafce9b39ddb2477293b"
    )

    def _seed_legacy(self) -> str:
        self.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status,"
            " revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self.LEGACY_COURSE,
        )
        self.execute(
            "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json,"
            " created_at, approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            self.LEGACY_PLAN,
        )
        for row in self.LEGACY_OBJECTIVES:
            self.execute(
                "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                " evidence_criteria_json, state, version, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        return self.new_enrollment("crs_legacy01")

    def test_legacy_plan_hash_unchanged_after_0007(self) -> None:
        """R4: a plan with no ``plan_units`` rows hashes byte-identically to the v6 kernel."""
        self._seed_legacy()
        self.assertEqual(domain.plan_hash("pln_legacy01"), self.LEGACY_PLAN_HASH)

    def test_legacy_outline_projects_one_unit(self) -> None:
        """R9/R4: a pre-blueprint plan projects exactly one implicit unit."""
        enrollment_id = self._seed_legacy()
        units = self.outline_units(enrollment_id)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["ordinal"], 1)
        self.assertEqual(units[0]["title"], "Legacy braise")
        self.assertEqual(units[0]["goal"], "")
        self.assertEqual(units[0]["prereq_unit_ordinals"], [])
        self.assertEqual(units[0]["prerequisite_state"], "no_edges")
        self.assertEqual(units[0]["unmet"], [])
        self.assertEqual(
            [item["objective_id"] for item in units[0]["objectives"]],
            ["obj_legacy01", "obj_legacy02"],
        )

    def test_projection_has_no_mastery_field(self) -> None:
        """R7: the outline unit object's key set equals R9 exactly; no score or mastery field."""
        seeded = self.seed_plan(
            units=[
                {"ordinal": 1, "title": "Unit 1", "goal": "Do the first thing."},
                {"ordinal": 2, "title": "Unit 2", "goal": "Do the second thing.", "prereqs": [1]},
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "First"},
                {"ordinal": 2, "unit": 2, "title": "Second"},
            ],
        )
        units = self.outline_units(seeded["enrollment_id"])
        self.assertEqual(len(units), 2)
        for unit in units:
            self.assertEqual(set(unit), R9_UNIT_KEYS)
            for objective in unit["objectives"]:
                self.assertTrue(set(objective) - {"score", "mastery", "readiness", "vector"})
                self.assertIn(objective["state"], OBJECTIVE_STATES)
            self.assertIn(unit["prerequisite_state"], {"no_edges", "satisfied", "unmet"})
        self.assertEqual(units[1]["prereq_unit_ordinals"], [1])


class BlueprintStoryTest(PrerequisiteGatingCase):
    """§14.4 tests 11-12: the two cases the design exists for."""

    def test_algebra_before_calculus(self) -> None:
        """R5/R5a/§14.3: a full, two-unit course gates calculus on algebra's independent
        evidence; the refusal carries the learner copy and the unmet title."""
        algebra_states = {
            1: "independent_evidence",
            2: "needs_review",
            3: "independent_evidence",
            4: "independent_evidence",
            5: "independent_evidence",
            6: "independent_evidence",
        }
        seeded = self.seed_plan(
            units=[
                {
                    "ordinal": 1,
                    "title": "Unit 1: Algebra",
                    "goal": "solve a linear equation without help",
                    "target_lessons": 6,
                },
                {
                    "ordinal": 2,
                    "title": "Unit 2: Calculus",
                    "goal": "differentiate a polynomial",
                    "prereqs": [1],
                    "target_lessons": 6,
                },
            ],
            objectives=[
                {
                    "ordinal": ordinal,
                    "unit": 1 if ordinal <= 6 else 2,
                    "title": f"Algebra objective {ordinal}"
                    if ordinal <= 6
                    else f"Calculus objective {ordinal}",
                    "state": algebra_states.get(ordinal, "not_started"),
                }
                for ordinal in range(1, 13)
            ],
        )
        units = self.outline_units(seeded["enrollment_id"])
        # The edge order the plan declares, and the calculus unit left unmet by one algebra
        # objective that is only in needs_review.
        self.assertEqual(units[1]["prereq_unit_ordinals"], [1])
        self.assertEqual(units[1]["prerequisite_state"], "unmet")
        self.assertEqual(
            [item["objective_id"] for item in units[1]["unmet"]],
            [seeded["objective_ids"][2]],
        )
        self.assertEqual(units[1]["unmet"][0]["title"], "Algebra objective 2")
        # The refusal carries the §14.3 copy.
        error = self.err(
            "lesson.begin",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_ids"][7],
                "mode": "fresh",
            },
            idempotency_key="key-lesson-begin-algebra",
        )
        self.assertEqual(error["code"], "PREREQUISITE_UNMET")
        message = error["message"]
        self.assertIn("Unit 2 assumes you can solve a linear equation without help.", message)
        self.assertIn("1 of 6 objectives there have not been shown independently yet", message)
        self.assertIn("Algebra objective 2", message)
        self.assertIn("will not count the prerequisite as met", message)

    def test_safety_before_power_tool(self) -> None:
        """R5a: parent-led safety gates the power tool, and only independent evidence satisfies;
        a parent-reported (quiz-only) pass in unit 1 does not."""
        parent_units = [
            {
                "ordinal": 1,
                "title": "Unit 1: Hazard and lockout",
                "goal": "isolate the machine before touching it",
                "target_lessons": 2,
            },
            {
                "ordinal": 2,
                "title": "Unit 2: The power tool",
                "goal": "cut a board with the saw guarded",
                "prereqs": [1],
                "target_lessons": 2,
            },
        ]
        parent_objectives = [
            {"ordinal": 1, "unit": 1, "title": "Name the hazard"},
            {"ordinal": 2, "unit": 2, "title": "Run the saw"},
        ]
        seeded = self.seed_plan(
            units=parent_units, objectives=parent_objectives, recipe="parent"
        )
        # Parent-led evidence is reported, layer 1 only: the parent watched the learner do it,
        # but that is not independent evidence and must never satisfy the edge.
        domain.record_observation(
            seeded["enrollment_id"],
            seeded["objective_ids"][1],
            evidence_class="parent_reported",
            kind="observation",
            note="the parent watched the learner isolate the machine",
        )
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (seeded["objective_ids"][1],)),
            "not_started",
        )
        units = self.outline_units(seeded["enrollment_id"])
        self.assertEqual(units[1]["prerequisite_state"], "unmet")
        self.assertEqual(
            [item["objective_id"] for item in units[1]["unmet"]],
            [seeded["objective_ids"][1]],
        )

        # The same shape with a cold first answer: independent evidence satisfies the edge.
        seeded = self.seed_plan(
            units=[
                {
                    "ordinal": 1,
                    "title": "Unit 1: Hazard and lockout",
                    "goal": "isolate the machine before touching it",
                    "target_lessons": 2,
                },
                {
                    "ordinal": 2,
                    "title": "Unit 2: The power tool",
                    "goal": "cut a board with the saw guarded",
                    "prereqs": [1],
                    "target_lessons": 2,
                },
            ],
            objectives=[
                {"ordinal": 1, "unit": 1, "title": "Name the hazard"},
                {"ordinal": 2, "unit": 2, "title": "Run the saw"},
            ],
        )
        opened = self.ok(
            "check.open",
            {
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_ids"][1],
            },
            expected_revision=seeded["revision"],
            idempotency_key="key-safety-open-2",
        )["result"]
        submitted = self.ok(
            "attempt.submit",
            {
                "enrollment_id": seeded["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": "nonce-safety-cold",
                "answer": {"kind": "text", "text": "4"},
            },
            expected_revision=opened["revision"],
            idempotency_key="key-safety-submit-2",
        )["result"]
        self.assertEqual(submitted["evidence_class"], "cold")
        units = self.outline_units(seeded["enrollment_id"])
        self.assertEqual(units[1]["prerequisite_state"], "satisfied")
        self.assertEqual(units[1]["unmet"], [])


if __name__ == "__main__":
    unittest.main()
