"""UP-11: a transfer objective is measured by application, never by an option pick.

The kind map says a transfer check is a verification artifact or an observation. The lesson rule
carried an exemption for ``kind == "quiz"``, so a three-choice scenario question passed every
authoring gate and was graded by exact string match: the learner eliminated two options and
applied nothing. The exemption is gone. A transfer check may still ask a question, but it must be
a recorded verification of the learner's own attempt or a written response over a case the lesson
never worked — never a choice among supplied options. Plan rule 5b reads the same map, so a
contradictory plan is refused before authoring.

Run: ``python3 -m unittest tests.test_upgrade_transfer_kind``
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from coursebook import generation as gen
from coursebook import grading
from tests.blueprint_support import blueprint_plan

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "generation"

#: The one phrase both gates use to name the refusal. It is asserted literally because the
#: reason a learner/operator sees must name the family and the kind that contradicted it.
NAMED_REASON = "a 'transfer' check is measured by verification or observation, not 'quiz'"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def transfer_quiz_lesson() -> dict:
    lesson = fixture("lesson_ja")
    lesson["check"]["evidence_target"] = "transfer"
    return lesson


def transfer_verification_lesson() -> dict:
    """A recorded attempt over a counter the lesson never worked: kind and format verification."""
    lesson = fixture("lesson_ja")
    check = lesson["check"]
    labels = [
        "Greets the staff before opening the order",
        "Uses the polite request form for the drink",
        "Confirms the order the way a counter expects",
    ]
    check["evidence_target"] = "transfer"
    check["kind"] = "verification"
    check["stimulus"] = {
        "prompt": (
            "At a counter this page never worked through, greet the staff and open your order. "
            "Do it, then record what you actually did."
        ),
        "format": "verification",
        "choices": [],
        "items": [
            {"id": f"item_{index}", "label": label}
            for index, label in enumerate(labels, start=1)
        ],
    }
    check["learner_instructions"] = (
        "Do this at the counter first, then tick each step only after you did it. This records "
        "your attempt; it is not an independently watched performance."
    )
    check["rubric"] = [
        {"criterion": label, "weight": 1.0, "description": label} for label in labels
    ]
    return lesson


def lesson_rules(lesson: dict, *, recipe: str = "committed") -> None:
    gen.enforce_lesson_rules(
        lesson,
        section={},
        objective={"evidence_target": "transfer"},
        recipe=recipe,
        locale=None,
        dials={},
    )


class TransferKindTest(unittest.TestCase):
    def test_a_transfer_quiz_is_refused(self) -> None:
        """Before: the exemption accepted this check. After: it is refused by name."""
        with self.assertRaises(gen._RuleViolation) as caught:
            lesson_rules(transfer_quiz_lesson())
        reasons = " ".join(caught.exception.reasons)
        self.assertIn(NAMED_REASON, reasons)
        # A transfer verification — the honest form — still passes the same gate.
        lesson_rules(transfer_verification_lesson())

    def test_a_transfer_check_may_not_supply_options(self) -> None:
        """The weaker form is the option pick, whatever kind the author labels it."""
        lesson = transfer_verification_lesson()
        lesson["check"]["stimulus"] = {
            "prompt": "Which phrase opens this counter?",
            "format": "selection",
            "choices": ["ありがとうございます", "こんにちは", "さようなら"],
        }
        with self.assertRaises(gen._RuleViolation) as caught:
            lesson_rules(lesson)
        reasons = " ".join(caught.exception.reasons)
        self.assertIn("may not present supplied options", reasons)

    def test_a_transfer_verification_is_gradeable_without_a_model(self) -> None:
        """The honest form is not a dead end: it takes the provider-free confirmation lane.

        The adversarial note on UP-11 says removing the quiz exemption without fixing the
        ungradeable open lane would leave transfer un-authorable. A verification checklist seals a
        ``rubric_only`` reference and its items are confirmation-shaped, so grading routes it to
        ``grade_confirmation`` — no model, no ``needs_retry`` — and records ``self_reported``
        evidence, which is exactly what an unattended attempt can honestly claim.
        """
        lesson = transfer_verification_lesson()
        lesson_rules(lesson)
        reference = gen._reference_payload(lesson["check"])
        self.assertEqual(reference["kind"], "rubric_only")
        self.assertIsNotNone(
            grading.confirmation_items(reference, lesson["check"]["stimulus"]),
            "a transfer verification checklist must route to the confirmation lane",
        )


class PlanRuleFiveBTest(unittest.TestCase):
    """Rule 5b refuses the contradiction in the plan, before any lesson is authored."""

    def plan_with(self, *, target: str, kind: str) -> dict:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="casual")
        plan["objectives"][0]["evidence_target"] = target
        plan["check_plan"][0]["evidence_target"] = target
        plan["check_plan"][0]["kind"] = kind
        return plan

    def plan_rules(self, plan: dict) -> None:
        gen.enforce_plan_rules(
            plan,
            recipe="casual",
            dials={},
            locale=None,
            ledger=[],
            scope="single",
        )

    def test_a_plan_cannot_declare_a_quiz_for_a_transfer_objective(self) -> None:
        with self.assertRaises(gen._RuleViolation) as caught:
            self.plan_rules(self.plan_with(target="transfer", kind="quiz"))
        reasons = " ".join(caught.exception.reasons)
        self.assertIn(NAMED_REASON, reasons)

    def test_a_plan_may_declare_a_verification_for_a_transfer_objective(self) -> None:
        self.plan_rules(self.plan_with(target="transfer", kind="verification"))


if __name__ == "__main__":
    unittest.main()
