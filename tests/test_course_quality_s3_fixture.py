"""H-173c: the repaired parent-led kitchen fixture, and the hazard fixture it must not soften.

The S3 sample has two artifacts with two different jobs:

- ``lesson_parent_unsafe.json`` is the hazard fixture. It exists to exercise the validator's
  ``hazard_age_appropriateness`` reject, so it is pinned by hash and must keep instructing the
  child to fill and switch on the kettle.
- ``lesson_parent_safe.json`` is the repaired quality fixture. It sorts cards, repeats the
  arm's-reach and unplugged-kettle rules in the parent notes, and aligns its rubric with the
  plan's evidence criteria.

These tests prove the quality fixes are in the repaired pair and that the hazard fixture was not
weakened to get them. They do not run the validator, do not change generation behavior and claim
no live provider output.

Run: ``python3 -m unittest tests.test_course_quality_s3_fixture``
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from coursebook import generation

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "generation"
RECORD = ROOT / "docs" / "reviews" / "H173c-S3-parent-kitchen-rescore.md"
PACKET = ROOT / "scripts" / "course_quality_review.py"

#: The unfixed artifact, exactly as the H-173 review recorded it. If either digest moves, the
#: hazard rejection stops describing bytes that exist and the S3 finding is no longer reproducible.
UNSAFE_LESSON_SHA256 = "0935dcb0f92866e4d229cb1e5c55da40ac7e56489b682c6b79fd98d338d7121a"
HAZARD_VALIDATION_SHA256 = "f6d0161427286da5d0341aa346aa5cd155266c1ea6a67a2724b9743e32165c48"

KETTLE_OPERATION = "Have the child fill the kettle at the sink and switch it on"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((FIXTURES / f"{name}.json").read_bytes()).hexdigest()


def load_packet_module():
    spec = importlib.util.spec_from_file_location("course_quality_review_s3", PACKET)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_errors(schema: dict, document: dict) -> list[str]:
    return [
        f"{list(error.path)}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(document)
    ]


class UnfixedHazardArtifactTest(unittest.TestCase):
    """The unfixed S3 lesson is still a hazard fixture, byte for byte."""

    def test_unsafe_lesson_hash_is_pinned(self) -> None:
        self.assertEqual(digest("lesson_parent_unsafe"), UNSAFE_LESSON_SHA256)

    def test_unsafe_lesson_still_instructs_kettle_operation(self) -> None:
        lesson = load("lesson_parent_unsafe")
        guided = [segment for segment in lesson["segments"] if segment["kind"] == "guided"]
        self.assertEqual(len(guided), 1)
        self.assertIn(KETTLE_OPERATION, guided[0]["body"])
        self.assertIn("switch it on", guided[0]["short"])

    def test_recorded_hazard_rejection_is_unchanged(self) -> None:
        self.assertEqual(digest("validation_reject_hazard"), HAZARD_VALIDATION_SHA256)
        validation = load("validation_reject_hazard")
        self.assertEqual(validation["verdict"], "reject")
        criteria = {entry["id"]: entry for entry in validation["criteria"]}
        self.assertEqual(criteria["hazard_age_appropriateness"]["verdict"], "fail")
        rejections = [
            entry
            for entry in validation["rejections"]
            if entry["criterion"] == "hazard_age_appropriateness"
        ]
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["item"], "segment:2")
        self.assertIn("kettle", rejections[0]["reason"].lower())


class RepairedPlanTest(unittest.TestCase):
    """D1 and D6 fixes live in the plan fixture and stay schema-valid."""

    def setUp(self) -> None:
        self.plan = load("plan_parent")

    def test_plan_still_validates_and_passes_parent_rules(self) -> None:
        self.assertEqual(schema_errors(generation.PLAN_SCHEMA_V1, self.plan), [])
        # Raises _RuleViolation if the repaired prose breaks a parent rule.
        generation.enforce_plan_rules(self.plan, recipe="parent", dials={}, locale=None, ledger=[])

    def test_outcome_names_the_union_of_the_objectives(self) -> None:
        outcome = self.plan["learner_outcome"].lower()
        for performance in ("names", "sorts", "kettle is a grown-up job", "explains one example"):
            self.assertIn(performance, outcome)

    def test_objective_one_states_the_pointing_criterion(self) -> None:
        criteria = self.plan["objectives"][0]["evidence_criteria"]
        self.assertEqual(len(criteria), 3)
        joined = " ".join(criteria).lower()
        self.assertIn("points at the warm object", joined)
        self.assertIn("one cold example", joined)
        self.assertIn("names one warm and one cold thing", joined)

    def test_kettle_rule_is_marked_as_a_parent_supplied_house_rule(self) -> None:
        self.assertIn("house rule", self.plan["evidence_note"].lower())
        self.assertIn("unverified", self.plan["evidence_note"].lower())
        exclusions = " ".join(self.plan["exclusions"]).lower()
        self.assertIn("parent-supplied house rule", exclusions)
        self.assertIn("not a general fact", exclusions)
        # The claim is bounded, not sourced: the plan still declares no fetched source.
        self.assertEqual(self.plan["source_ids"], [])
        self.assertTrue(all(obj["support"] == "unverified" for obj in self.plan["objectives"]))


class RepairedLessonTest(unittest.TestCase):
    """D3, D4 and D8 fixes live in the repaired lesson fixture."""

    def setUp(self) -> None:
        self.plan = load("plan_parent")
        self.lesson = load("lesson_parent_safe")
        self.text = json.dumps(self.lesson).lower()

    def test_lesson_validates_and_passes_parent_rules(self) -> None:
        self.assertEqual(schema_errors(generation.LESSON_SCHEMA, self.lesson), [])
        generation.enforce_lesson_rules(
            self.lesson,
            section=self.plan["sections"][0],
            objective=self.plan["objectives"][0],
            recipe="parent",
            locale=None,
            dials={},
            ledger=None,
        )

    def test_guided_step_is_the_safe_card_sort(self) -> None:
        guided = [segment for segment in self.lesson["segments"] if segment["kind"] == "guided"]
        self.assertEqual(len(guided), 1)
        body = guided[0]["body"].lower()
        self.assertIn("picture cards", body)
        self.assertIn("warm cards in one pile", body)
        self.assertIn("cold cards in the other", body)
        # The child never operates the kettle: the fixture says so positively and never instructs it.
        self.assertNotIn("fill the kettle", self.text)
        self.assertNotIn("switch it on", self.text)
        self.assertIn("never fills or switches on the kettle", self.text)

    def test_check_rubric_restates_the_objectives_criteria(self) -> None:
        objective = self.plan["objectives"][0]
        check = self.lesson["check"]
        self.assertEqual(check["evidence_target"], objective["evidence_target"])
        criteria = [entry["criterion"] for entry in check["rubric"]]
        self.assertEqual(criteria, ["names one of each", "points before naming", "cold example"])
        plan_criteria = " ".join(objective["evidence_criteria"]).lower()
        self.assertIn("points at the warm object", plan_criteria)
        self.assertIn("one cold example", plan_criteria)

    def test_worked_example_and_explanation_name_the_rule(self) -> None:
        steps = " ".join(self.lesson["worked_example"]["steps"]).lower()
        self.assertIn("because a grown-up heats water in it", steps)
        self.assertIn("because it keeps food cool", steps)
        self.assertIn("a grown-up always fills and switches on the kettle",
                      self.lesson["learner_explanation"].lower())

    def test_parent_notes_repeat_the_supervision_and_kettle_rules(self) -> None:
        notes = self.lesson["parent_notes"].lower()
        self.assertIn("within arm's reach", notes)
        self.assertIn("unplugged and out of reach", notes)
        self.assertNotIn("explore the kitchen freely", notes)
        self.assertEqual(
            self.lesson["supervision_notes"], self.plan["parent"]["supervision_notes"]
        )
        # A reach for the kettle has a stated next move, not a silent failure.
        self.assertIn("stop, move it further away and go back to the cards", notes)
        self.assertEqual(self.lesson["check"]["assistance_policy"]["hint"], "available")

    def test_every_reader_facing_place_marks_the_kettle_rule_as_a_house_rule(self) -> None:
        """H-173d D6: the plan's honesty mark must reach the copy that makes the claim."""

        model = self.lesson["segments"][0]
        places = {
            "segments[0].body": model["body"],
            "segments[0].short": model["short"],
            "learner_explanation": self.lesson["learner_explanation"],
            "learner_explanation_short": self.lesson["learner_explanation_short"],
            "parent_notes": self.lesson["parent_notes"],
        }
        for name, text in places.items():
            lowered = text.lower()
            self.assertIn("house rule", lowered, f"{name} states the kettle rule unmarked")
            self.assertIn(
                "not a general",
                lowered,
                f"{name} does not say the rule is not a general fact",
            )
        # The mark is a qualifier, not a deletion: the rule still reaches the reader.
        self.assertIn("hot water can burn", model["body"].lower())
        self.assertIn("fills or switches on the kettle", model["body"].lower())
        # The claim is bounded, not newly sourced.
        self.assertEqual(self.lesson["sources"], [])

    def test_lesson_claims_no_source_it_did_not_fetch(self) -> None:
        self.assertEqual(self.lesson["sources"], [])
        self.assertEqual(self.plan["source_ids"], [])
        for section in self.plan["sections"]:
            self.assertEqual(section["source_ids"], [])
        for objective in self.plan["objectives"]:
            self.assertEqual(objective["support"], "unverified")


class RescoreRecordTest(unittest.TestCase):
    """The new record is a valid review and re-scores the five fixed dimensions at 3 or 4."""

    def test_record_passes_the_packet_checker(self) -> None:
        module = load_packet_module()
        self.assertTrue(RECORD.is_file())
        self.assertEqual(module.check_record(RECORD.read_text(encoding="utf-8")), [])

    def test_fixed_dimensions_are_rescored_at_three_or_four(self) -> None:
        text = RECORD.read_text(encoding="utf-8")
        scores = {}
        for match in re.finditer(r"^### (D[1-8]) .*?^Score: (\d)$", text, re.MULTILINE | re.DOTALL):
            scores[match.group(1)] = int(match.group(2))
        self.assertEqual(sorted(scores), [f"D{index}" for index in range(1, 9)])
        for dimension_id in ("D1", "D3", "D4", "D6", "D8"):
            self.assertGreaterEqual(scores[dimension_id], 3, f"{dimension_id} was not repaired")

    def test_record_does_not_claim_a_live_validation_or_a_learner_run(self) -> None:
        text = RECORD.read_text(encoding="utf-8")
        self.assertIn("not run for the repaired pair", text)
        self.assertIn("no learner has received this fixture", text)
        self.assertIn("H-173d", text)


class D6CopyRecordTest(unittest.TestCase):
    """H-173d's S3 D6 finding: the house-rule mark now reaches the copy that makes the claim."""

    RECORD = ROOT / "docs" / "reviews" / "H173d-S3-D6-house-rule-copy.md"

    def test_record_passes_the_packet_checker(self) -> None:
        module = load_packet_module()
        self.assertTrue(self.RECORD.is_file())
        self.assertEqual(module.check_record(self.RECORD.read_text(encoding="utf-8")), [])

    def test_d6_is_rescored_at_three_from_the_lesson_copy(self) -> None:
        text = self.RECORD.read_text(encoding="utf-8")
        match = re.search(
            r"^### D6 .*?^Score: (\d)$.*?^Evidence: (.*?)^Follow-up:",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if match is None:
            self.fail("D6 block is missing from the re-score record")
        self.assertEqual(int(match.group(1)), 3)
        evidence = match.group(2).lower()
        self.assertIn("segments[0].body", evidence)
        self.assertIn("house rule", evidence)
        self.assertIn("parent_notes", evidence)

    def test_record_is_author_scored_and_claims_no_live_run(self) -> None:
        text = self.RECORD.read_text(encoding="utf-8")
        self.assertIn("not independent", text)
        self.assertIn("not be cited as one", text.lower())
        self.assertIn("no provider call was made", text.lower())


if __name__ == "__main__":
    unittest.main()
