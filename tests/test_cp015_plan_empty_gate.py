"""CP-015: a generated draft with no objectives must never be approvable.

Live evidence: after a plan job whose provider call outlived the job deadline (CP-044), the
course row was left with the draft plan ``course.create`` writes — one unit, zero objectives —
and the plan review reported ``validation.approvable: true`` because a plan with no generation
document takes the manual-authoring path. The driver would have approved an empty course and then
exported it. The approval gate now fails closed on an empty plan, and the driver refuses it too.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from coursebook import domain

from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "scripts" / "cp015-demo-courses.py"


class EmptyPlanIsNotApprovableTest(KernelCase):
    def test_draft_plan_with_no_objectives_is_not_approvable(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        outline = self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]
        plan = outline["plan"]
        self.assertEqual(plan["plan_id"], plan_id)
        self.assertEqual(outline["objectives"], [])
        # The review surface must not offer approval for a plan with nothing in it. The reason is
        # the contract's `plan_not_validated` (the wire has no separate empty-plan reason); the
        # detail names the actual condition.
        self.assertFalse(plan["validation"]["approvable"])
        self.assertEqual(plan["validation"]["reason"], "plan_not_validated")
        self.assertIn("no objectives", plan["validation"]["detail"])

    def test_approval_is_refused_with_a_typed_reason(self) -> None:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        error = self.err(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id,
             "plan_hash": domain.plan_hash(plan_id)},
            expected_revision=0,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "plan_empty")

    def test_a_plan_with_an_objective_still_takes_the_manual_path(self) -> None:
        # The gate must not break manual authoring: the same draft becomes approvable once the
        # author states an objective, which is the only content approval can carry.
        course_id, plan_id = self.new_course()
        self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        outline = self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]
        self.assertTrue(outline["plan"]["validation"]["approvable"])

    def test_driver_refuses_to_export_or_approve_an_empty_plan(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        self.assertIn("refusing to approve a plan with no objectives", source)
        self.assertIn("carries no objectives; not approvable", source)
        # The provider call can outlive the job deadline (CP-044), so the driver owns its bound.
        self.assertIn("PLAN_ATTEMPT_TIMEOUT_S", source)
        self.assertLessEqual(
            float(source.split("PLAN_ATTEMPT_TIMEOUT_S = ", 1)[1].splitlines()[0]),
            600.0,
        )


if __name__ == "__main__":
    unittest.main()
