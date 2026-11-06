"""Deterministic validators and the bounded aux grading adapter.

The rules under test are the ones that keep a verdict honest: closed forms never touch a model,
an open response never passes when the grader could not finish, and invalid grader output is
refused instead of being coerced into a verdict.
"""

from __future__ import annotations

import time
import unittest

from coursebook import grading, validators


class NotationTest(unittest.TestCase):
    def test_normalization_folds_notation_not_meaning(self) -> None:
        self.assertEqual(validators.normalize_text("  Café\u00a0 "), "café")
        self.assertEqual(validators.normalize_text("\uff12\uff0b\uff12"), "2+2")
        self.assertEqual(validators.normalize_text("\u201cYes.\u201d"), "yes")
        self.assertNotEqual(validators.normalize_text("-3"), validators.normalize_text("3"))

    def test_numbers_accept_equivalent_forms(self) -> None:
        self.assertEqual(validators.parse_number("1/2"), validators.parse_number("0.5"))
        self.assertEqual(validators.parse_number("1,000"), validators.parse_number("1000"))
        self.assertEqual(validators.parse_number("50%"), validators.parse_number("0.5"))
        self.assertEqual(validators.parse_number("3.5e2"), validators.parse_number("350"))
        self.assertIsNone(validators.parse_number("about four"))

    def test_units_convert_within_a_dimension_only(self) -> None:
        self.assertEqual(validators.convert(validators.parse_number("350"), "cm", "m"), validators.parse_number("3.5"))
        self.assertIsNone(validators.convert(validators.parse_number("3"), "cm", "kg"))


class ClosedFormTest(unittest.TestCase):
    def outcome(self, reference: dict, answer: str | list, kind: str = "text") -> validators.Outcome:
        payload = {"kind": kind}
        if kind == "text":
            payload["text"] = answer
        else:
            payload["selection"] = answer
        return validators.grade_reference(reference, payload)

    def test_numeric_tolerance_and_units(self) -> None:
        reference = {"kind": "numeric", "value": "3.5", "tolerance": {"abs": "0.05"}, "unit": "cm",
                     "accepted_units": ["cm", "m"]}
        self.assertTrue(self.outcome(reference, "3.52 cm").met)
        self.assertTrue(self.outcome(reference, "0.0351 m").met)
        self.assertFalse(self.outcome(reference, "3.6").met)
        self.assertFalse(self.outcome(reference, "3.5").met, "a unitless answer is not a unit answer")
        self.assertFalse(self.outcome(reference, "3.5 kg").met)

    def test_numeric_relative_tolerance(self) -> None:
        reference = {"kind": "numeric", "value": "1000", "tolerance": {"rel": "0.02"}}
        self.assertTrue(self.outcome(reference, "1,019").met)
        self.assertFalse(self.outcome(reference, "1,021").met)

    def test_multiple_valid_answers(self) -> None:
        reference = {"kind": "exact", "answers": ["colour", "color"]}
        self.assertTrue(self.outcome(reference, "COLOR.").met)
        self.assertFalse(self.outcome(reference, "hue").met)

    def test_selection_is_order_insensitive_by_default(self) -> None:
        reference = {"kind": "selection", "answers": [["a", "b", "c"]]}
        self.assertTrue(self.outcome(reference, ["c", "A", " b"], kind="selection").met)
        self.assertFalse(self.outcome(reference, ["a", "b"], kind="selection").met)

    def test_unreadable_answer_is_not_yet_not_a_pass(self) -> None:
        outcome = self.outcome({"kind": "numeric", "value": "4"}, "four-ish")
        self.assertFalse(outcome.met)
        self.assertIn("not a number", outcome.observed)

    def test_verdict_mapping_never_passes_without_an_outcome(self) -> None:
        self.assertEqual(validators.verdict_for([]), "needs_retry")
        self.assertEqual(
            validators.verdict_for([validators.Outcome("c1", False, "-")]), "not_yet"
        )
        self.assertEqual(
            validators.verdict_for([validators.Outcome("c1", True, "-")]), "pass"
        )


class GradingGateTest(unittest.TestCase):
    def tearDown(self) -> None:
        grading.configure_aux_grader(None)

    def test_closed_reference_is_graded_without_the_aux_lane(self) -> None:
        result = grading.grade(
            reference={"kind": "numeric", "value": "4"},
            rubric={"pass_rule": "all"},
            stimulus={},
            answer={"kind": "text", "text": "4"},
            attempt_id="att_0001_x",
        )
        self.assertEqual(result.verdict, "pass")
        self.assertEqual(result.provenance["grader"], "deterministic:numeric")

    def test_provenance_carries_a_hash_never_the_reference(self) -> None:
        result = grading.grade(
            reference={"kind": "exact", "answers": ["the-hidden-key"]},
            rubric=None,
            stimulus=None,
            answer={"kind": "text", "text": "the-hidden-key"},
            attempt_id="att_0002_x",
        )
        blob = repr(result.provenance)
        self.assertNotIn("the-hidden-key", blob)
        self.assertRegex(result.provenance["reference_sha256"], r"^sha256:[a-f0-9]{64}$")

    def test_open_response_without_an_aux_lane_fails_closed(self) -> None:
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(
                reference={"kind": "rubric_only"}, rubric={}, stimulus={},
                answer={"kind": "text", "text": "an essay"}, attempt_id="att_0003_x",
            )

    def test_aux_invalid_output_is_refused(self) -> None:
        grading.configure_aux_grader(lambda **kwargs: {"verdict": "pass", "criteria": "nope"}, task_name="t")
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(reference={"kind": "rubric_only"}, rubric={}, stimulus={},
                          answer={"kind": "text", "text": "x"}, attempt_id="att_0004_x")

    def test_aux_pass_with_unmet_criteria_is_refused(self) -> None:
        grading.configure_aux_grader(
            lambda **kwargs: {"verdict": "pass", "criteria": [{"id": "c1", "observed": "missing", "met": False}]},
            task_name="t",
        )
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(reference={"kind": "rubric_only"}, rubric={}, stimulus={},
                          answer={"kind": "text", "text": "x"}, attempt_id="att_0005_x")

    def test_aux_exception_is_refused(self) -> None:
        def boom(**kwargs):
            raise RuntimeError("provider down")

        grading.configure_aux_grader(boom, task_name="t")
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(reference={"kind": "rubric_only"}, rubric={}, stimulus={},
                          answer={"kind": "text", "text": "x"}, attempt_id="att_0006_x")

    def test_aux_deadline_is_bounded(self) -> None:
        def slow(**kwargs):
            time.sleep(0.4)
            return {"verdict": "pass", "criteria": [{"id": "c1", "observed": "-", "met": True}]}

        grading.configure_aux_grader(slow, task_name="t")
        started = time.monotonic()
        with self.assertRaises(grading.GradingUnavailable):
            grading.grade(reference={"kind": "rubric_only"}, rubric={}, stimulus={},
                          answer={"kind": "text", "text": "x"}, attempt_id="att_0007_x", deadline_ms=50)
        self.assertLess(time.monotonic() - started, 0.3)

    def test_valid_aux_result_is_accepted(self) -> None:
        grading.configure_aux_grader(
            lambda **kwargs: {"verdict": "partial",
                              "criteria": [{"id": "c1", "observed": "partly", "met": False}],
                              "rationale": "half the steps"}, task_name="aux-test",
        )
        result = grading.grade(reference={"kind": "rubric_only"}, rubric={"construct": "production"},
                               stimulus={}, answer={"kind": "text", "text": "x"}, attempt_id="att_0008_x")
        self.assertEqual(result.verdict, "partial")
        self.assertEqual(result.criteria[0]["observed"], "partly")
        self.assertEqual(result.provenance["grader"], "aux:aux-test")


if __name__ == "__main__":
    unittest.main()
