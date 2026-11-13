"""E2E S1/S3: a full course ends on its exit, and spaced review is a different form.

S1 — ``terminal_performance`` was schema-only: the plan rules read ``exit_performance`` and asked
for a procedure/transfer objective *somewhere in the last unit*, the lesson payload never carried
either field, and a full course could end on a recall section.

S3 — ``spaced_review`` was recipe decoration: a committed plan could schedule zero reviews, and a
review lesson copied its owner's stimulus byte for byte, so the learner answered identical items.

These fixtures pin the deterministic gates: a full plan whose last owner section is recall is
refused and named, a committed plan with no review is refused, a review that repeats its owner's
exact stimulus is refused, a review over an unwritten owner parks instead of failing the unit, and
the lesson payload carries the declared exit.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen

from tests.blueprint_support import NOW, blueprint_plan, unit_sections_document
from tests.test_cp015j_closed_owner_check import ClosedOwnerCheckCase


def enforce(plan: dict, *, recipe: str | None = None, goal: str | None = None) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe=recipe or str(plan.get("spaced_review") and "committed" or "casual"),
        dials={},
        locale=None,
        ledger=[],
        scope=plan.get("scope"),
        goal=goal,
    )


class FullCourseEndsOnItsExitTest(unittest.TestCase):
    def test_a_full_plan_ending_on_recall_is_refused_naming_the_last_section(self) -> None:
        plan = blueprint_plan(scope="full", units=2, objectives_per_unit=3, recipe="casual")
        final = plan["objectives"][-1]
        final["evidence_target"] = "recall"
        for item in plan["check_plan"]:
            if int(item["objective_ref"]) == int(final["ordinal"]):
                item["evidence_target"] = "recall"
                item["kind"] = "quiz"
        with self.assertRaises(gen._RuleViolation) as caught:
            enforce(plan)
        reasons = caught.exception.reasons
        self.assertTrue(
            any(
                "scope 'full'" in reason
                and "last owner section" in reason
                and f"objective {final['ordinal']}" in reason
                and "'recall'" in reason
                for reason in reasons
            ),
            reasons,
        )

    def test_a_performance_plan_must_end_on_the_performance_not_just_the_last_unit(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2, recipe="casual")
        # Perform the first objective of the last unit but leave the final section a quiz.
        last_unit = plan["units"][-1]
        first_of_last = next(
            obj for obj in plan["objectives"] if int(obj["unit_ref"]) == int(last_unit["ordinal"])
        )
        first_of_last["evidence_target"] = "procedure"
        for item in plan["check_plan"]:
            if int(item["objective_ref"]) == int(first_of_last["ordinal"]):
                item["evidence_target"] = "procedure"
                item["kind"] = "verification"
        plan["exit_performance"] = "performance"
        plan["terminal_performance"] = "Replace the front brake pads and torque the caliper."
        with self.assertRaises(gen._RuleViolation) as caught:
            enforce(plan)
        self.assertTrue(
            any("last owner section" in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_the_unit_gate_refuses_a_last_unit_that_moves_the_exit_off_the_last_owner(self) -> None:
        plan = blueprint_plan(scope="full", units=2, objectives_per_unit=3, recipe="casual")
        unit = plan["units"][-1]
        objectives = [
            obj for obj in plan["objectives"] if int(obj["unit_ref"]) == int(unit["ordinal"])
        ]
        sections = unit_sections_document(unit=unit, objectives=objectives, reviews=0)["sections"]
        # The final owner owns the middle objective of the unit, leaving the last owner a quiz.
        sections[-1]["primary_objective_ref"] = int(objectives[-2]["ordinal"])
        sections[-2]["primary_objective_ref"] = int(objectives[-1]["ordinal"])
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_unit_section_rules(
                sections,
                unit=unit,
                objectives=objectives,
                plan=plan,
                recipe="casual",
                dials={},
                locale=None,
                ledger=(),
                existing_owner_refs=(),
            )
        self.assertTrue(
            any(
                "last unit of a full course" in reason and "last owner section" in reason
                for reason in caught.exception.reasons
            ),
            caught.exception.reasons,
        )


class SpacedReviewDensityTest(unittest.TestCase):
    def test_a_committed_plan_with_zero_reviews_is_refused(self) -> None:
        plan = blueprint_plan(
            scope="short", units=1, objectives_per_unit=4, recipe="committed", reviews=(0,)
        )
        self.assertTrue(plan["spaced_review"])
        with self.assertRaises(gen._RuleViolation) as caught:
            enforce(plan, recipe="committed")
        self.assertTrue(
            any(
                "spaced_review is true" in reason
                and "schedules 0 review section(s)" in reason
                and "at least 1" in reason
                for reason in caught.exception.reasons
            ),
            caught.exception.reasons,
        )

    def test_a_committed_plan_with_the_required_reviews_passes(self) -> None:
        plan = blueprint_plan(
            scope="short", units=1, objectives_per_unit=4, recipe="committed", reviews=(1,)
        )
        enforce(plan, recipe="committed")

    def test_a_full_course_needs_one_review_per_four_owners(self) -> None:
        plan = blueprint_plan(
            scope="full", units=4, objectives_per_unit=3, recipe="committed", reviews=(0, 0, 0, 0)
        )
        with self.assertRaises(gen._RuleViolation) as caught:
            enforce(plan, recipe="committed")
        # 12 owners need ceil(12/4) = 3 reviews.
        self.assertTrue(
            any("at least 3" in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )


class ReviewVariantTest(unittest.TestCase):
    owner_stimulus = {
        "prompt": "Which phrase opens the interaction?",
        "format": "selection",
        "choices": ["ありがとうございます", "こんにちは", "さようなら"],
        "items": [],
    }

    def target(self, *, stimulus: dict | None = None) -> dict:
        return {
            "check": {
                "evidence_target": "discrimination",
                "stimulus": dict(stimulus or self.owner_stimulus),
            }
        }

    def check(self, *, prompt: str, choices: list[str] | None = None) -> dict:
        return {
            "evidence_target": "discrimination",
            "stimulus": {
                "prompt": prompt,
                "format": "selection",
                "choices": list(choices or self.owner_stimulus["choices"]),
                "items": [],
            },
        }

    def test_a_review_with_the_owners_exact_stimulus_is_refused(self) -> None:
        problems = gen.review_variant_problems(
            {"ordinal": 4},
            self.check(prompt=self.owner_stimulus["prompt"]),
            self.target(),
        )
        self.assertTrue(any("exact stimulus" in item for item in problems), problems)

    def test_a_review_with_new_items_for_the_same_target_passes(self) -> None:
        problems = gen.review_variant_problems(
            {"ordinal": 4},
            self.check(
                prompt="Name the greeting you use as you enter, without looking back at the model.",
                choices=["こんにちは", "ありがとうございます", "さようなら"],
            ),
            self.target(),
        )
        self.assertEqual(problems, [])

    def test_a_review_may_not_change_the_evidence_target(self) -> None:
        check = self.check(prompt="A different prompt")
        check["evidence_target"] = "recall"
        problems = gen.review_variant_problems({"ordinal": 4}, check, self.target())
        self.assertTrue(any("same evidence target" in item for item in problems), problems)


class LessonPayloadExitTest(unittest.TestCase):
    def test_the_lesson_payload_carries_the_declared_exit(self) -> None:
        plan = {
            "title": "A course with an exit",
            "learner_outcome": "The learner replaces the front brake pads.",
            "through_line": "Every section adds one move the final replacement needs.",
            "delivery": "self_study",
            "exit_performance": "performance",
            "terminal_performance": "Replace the front brake pads and torque the caliper.",
        }
        request = gen.build_lesson_request(
            plan=plan,
            section={"ordinal": 1, "title": "Naming the parts", "objective_refs": [1]},
            objective={"ordinal": 1, "evidence_target": "comprehension"},
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        payload = json.loads(request.input_text)
        self.assertEqual(payload["exit_performance"], "performance")
        self.assertEqual(
            payload["terminal_performance"],
            "Replace the front brake pads and torque the caliper.",
        )
        self.assertIn("declared exit", request.instructions)


class ReviewOverUnwrittenOwnerParksTest(ClosedOwnerCheckCase):
    """Do 3: a review whose target is unwritten parks; the unit job still completes."""

    def test_a_section_scoped_review_over_no_owner_lessons_is_parked_not_failed(self) -> None:
        result = gen.run_lesson_job(
            db.connect(),
            {
                "job_id": None,
                "brief": {
                    "plan_id": self.plan_id,
                    "unit_ordinal": 1,
                    "section_id": "sec_4",
                    "regenerate": True,
                },
            },
            self.lessons_llm(),
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=NOW,
        )
        review = next(item for item in result["lessons"] if item["section_id"] == "sec_4")
        self.assertEqual(review["state"], "needs_review")
        self.assertTrue(review.get("parked"))
        self.assertIn("owner lessons are not written yet", review["park_reason"])


if __name__ == "__main__":
    unittest.main()
